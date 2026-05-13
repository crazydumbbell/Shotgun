"""Drive `flutter test` for a generated integration_test.

Owns the orchestration: codegen → entitlements patch → flutter test → cleanup.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .codegen import write_integration_test
from .config import ShotgunConfig
from .entitlements import sandbox_disabled


class CaptureError(RuntimeError):
    """Raised when `flutter test` exits non-zero."""


def run_capture(
    config: ShotgunConfig,
    project_root: Path,
    *,
    device: str = "macos",
    flutter_bin: str = "flutter",
    keep_generated: bool = False,
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
            proc = subprocess.run(cmd, cwd=project_root, env=env, check=False)
        if proc.returncode != 0:
            raise CaptureError(
                f"flutter test exited with code {proc.returncode}"
            )
    finally:
        if not keep_generated:
            try:
                generated.unlink()
            except FileNotFoundError:
                pass

    return out_root
