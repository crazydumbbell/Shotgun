"""macOS entitlements patcher.

Flutter macOS apps default to sandboxed (`com.apple.security.app-sandbox: true`),
which means any file written by the running app lands in
`~/Library/Containers/<bundle>/Data/...` instead of the path we asked for.
For capture we need to disable the sandbox temporarily, then restore it.

Used as a context manager:

    with sandbox_disabled(project_root):
        run_flutter_test(...)

If the file does not exist (non-macOS project, or user already ejected
the default), the context manager is a no-op.
"""

from __future__ import annotations

import re
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

_DEBUG = "macos/Runner/DebugProfile.entitlements"
_KEY = "com.apple.security.app-sandbox"

# Match `<key>com.apple.security.app-sandbox</key>` followed by a `<true/>`
# or `<false/>` (allowing whitespace/newlines between them).
_PATTERN = re.compile(
    rf"(<key>{re.escape(_KEY)}</key>\s*)(<true/>|<false/>)",
    re.DOTALL,
)


def _entitlements_path(project_root: Path) -> Path:
    return project_root / _DEBUG


@contextmanager
def sandbox_disabled(project_root: Path) -> Iterator[None]:
    """Flip app-sandbox off for the lifetime of the context, then restore.

    Restoration runs in a `finally`, so even if the wrapped block crashes
    the original entitlement is put back.
    """
    path = _entitlements_path(project_root)
    if not path.exists():
        yield
        return

    # Self-heal: a prior run that was killed before the `finally` ran will
    # leave a `.shotgun-bak` next to the entitlements file. That backup is
    # the real pre-patch content; restore it before doing anything else.
    backup = path.with_suffix(path.suffix + ".shotgun-bak")
    if backup.exists():
        shutil.copy2(backup, path)
        backup.unlink()

    original = path.read_text(encoding="utf-8")
    if not _PATTERN.search(original):
        # Key absent. We don't insert it — that's a deliberate user choice.
        yield
        return

    patched = _PATTERN.sub(rf"\1<false/>", original)
    if patched == original:
        # Already false. Nothing to do.
        yield
        return

    shutil.copy2(path, backup)
    path.write_text(patched, encoding="utf-8")
    try:
        yield
    finally:
        path.write_text(original, encoding="utf-8")
        try:
            backup.unlink()
        except FileNotFoundError:
            pass
