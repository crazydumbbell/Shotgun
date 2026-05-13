"""Drive `flutter test` for a generated integration_test.

Owns the orchestration: codegen → entitlements patch → flutter test → cleanup.

Also filters `flutter test` stdout to keep the user-facing log readable:
known-benign warnings are hidden unless `verbose=True`, and on failure a
one-line summary (which shot + which widget) is printed before the raw
stack trace.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .codegen import write_integration_test
from .config import ShotgunConfig
from .entitlements import sandbox_disabled


class CaptureError(RuntimeError):
    """Raised when `flutter test` exits non-zero."""


# Known benign log lines we hide unless verbose. Each entry is a substring
# match — cheap and explicit. Add new ones here as users report them.
_BENIGN_LINE_SUBSTRINGS: tuple[str, ...] = (
    # macOS desktop runner: harmless when running headless; flutter test
    # still drives the test bindings correctly.
    "Failed to foreground app",
    # pdfx and similar packages still ship pre-Dart-3 helpers. These are
    # the *package's* problem, not shotgun's — and they bury the actual
    # shotgun output under hundreds of lines on a cold build.
    "scanHexInt32 is deprecated",
    "Function declarations must include a prototype",
    "warning: 'scanHexInt32'",
)

# Lines that say "this is a real flutter test event we care about". Used
# to bound the failure-context window we scan for a one-line summary.
_TEST_START_RE = re.compile(r"^\s*\d+:\d+\s+\+\s*\d+.*:\s+(.+)$")
# When a testWidgets case fails, flutter prints something like:
#   00:42 +5 -1: ios/6.7/en/home [E]
# We use the route segment as the shot identifier in the summary.
_TEST_FAIL_RE = re.compile(
    r"^\s*\d+:\d+\s+\+\s*\d+\s+-\s*\d+\s*:\s+(?P<id>\S+)\s+\[E\]\s*$"
)


@dataclass
class _FailureContext:
    """Accumulator for the most recent test failure we've seen on stdout."""

    shot_id: str | None = None
    error_lines: list[str] = field(default_factory=list)

    def likely_root_cause(self) -> str | None:
        """Pick the most informative single line from the captured error.

        Heuristic: prefer the first line that mentions a Flutter widget
        error class or a thrown exception; otherwise the first non-empty
        non-stack-frame line.
        """
        for line in self.error_lines:
            stripped = line.strip()
            if not stripped:
                continue
            # Skip raw stack frames (`#42  Foo.bar (package:...)`).
            if stripped.startswith("#") and "(" in stripped:
                continue
            # Common Flutter framework error preambles.
            if any(
                marker in stripped
                for marker in (
                    "═══", "EXCEPTION CAUGHT", "FlutterError", "Exception:",
                    "Error:", "NotInitializedError", "StateError",
                    "Couldn't find", "Bad state",
                )
            ):
                return stripped
        for line in self.error_lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                return stripped
        return None


def _is_benign(line: str) -> bool:
    return any(needle in line for needle in _BENIGN_LINE_SUBSTRINGS)


def _stream_and_filter(
    proc: subprocess.Popen[str], *, verbose: bool,
) -> _FailureContext:
    """Pipe `proc.stdout` to our stdout, filtering benign lines and
    tracking the most recent test failure context."""
    ctx = _FailureContext()
    in_error_block = False
    assert proc.stdout is not None
    for raw in proc.stdout:
        line = raw.rstrip("\n")

        if not verbose and _is_benign(line):
            continue

        fail_match = _TEST_FAIL_RE.match(line)
        if fail_match:
            ctx.shot_id = fail_match.group("id")
            ctx.error_lines = []
            in_error_block = True
        elif in_error_block:
            # A new test start line ends the previous failure's error block.
            if _TEST_START_RE.match(line) and not fail_match:
                in_error_block = False
            else:
                ctx.error_lines.append(line)

        print(line, flush=True)
    return ctx


def run_capture(
    config: ShotgunConfig,
    project_root: Path,
    *,
    device: str = "macos",
    flutter_bin: str = "flutter",
    keep_generated: bool = False,
    verbose: bool = False,
) -> Path:
    """Generate the integration_test, run flutter test, return the output dir."""
    project_root = project_root.resolve()
    out_root = (project_root / config.output.dir).resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    generated = write_integration_test(config, project_root)

    env = os.environ.copy()
    env["SHOTGUN_OUT_DIR"] = str(out_root)

    cmd: list[str] = [flutter_bin, "test", "-d", device, str(generated)]
    for key, value in config.app.dart_defines.items():
        cmd.extend(["--dart-define", f"{key}={value}"])
    if config.app.flavor:
        cmd.extend(["--flavor", config.app.flavor])

    try:
        with sandbox_disabled(project_root):
            proc = subprocess.Popen(
                cmd,
                cwd=project_root,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            ctx = _stream_and_filter(proc, verbose=verbose)
            returncode = proc.wait()
        if returncode != 0:
            summary = _format_failure_summary(ctx)
            if summary:
                # Print summary to stderr so it stands out from the
                # already-printed raw output and survives stdout redirection.
                print(f"\n[shotgun] {summary}", file=sys.stderr, flush=True)
            raise CaptureError(
                f"flutter test exited with code {returncode}"
                + (f" — {summary}" if summary else "")
            )
    finally:
        if not keep_generated:
            try:
                generated.unlink()
            except FileNotFoundError:
                pass

    return out_root


def _format_failure_summary(ctx: _FailureContext) -> str | None:
    """Render the captured failure as a single line, or None if nothing
    actionable was captured."""
    cause = ctx.likely_root_cause()
    if not ctx.shot_id and not cause:
        return None
    parts: list[str] = ["failed"]
    if ctx.shot_id:
        parts.append(f"at {ctx.shot_id}")
    if cause:
        # Trim very long cause lines so the summary stays one-line-ish.
        if len(cause) > 240:
            cause = cause[:237] + "..."
        parts.append(f"— {cause}")
    return " ".join(parts)
