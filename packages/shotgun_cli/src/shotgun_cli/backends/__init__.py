"""Capture backends.

A backend owns *how* raw screenshots are produced. The default
`macos_host` backend drives `flutter test -d macos` with surface-size
overrides — fast, headless, runs in CI. Future backends will drive a
real iOS Simulator (`ios_sim`) or Android emulator (`android_emu`) via
`xcrun simctl` / `adb` for marketing shots that need real system chrome.

The CLI selects a backend via `advanced.backend` in `shotgun.yaml` and
calls `get_backend(name).run(...)`. See `base.CaptureBackend` for the
contract every backend implements.
"""

from __future__ import annotations

from .base import CaptureBackend, CaptureError
from .ios_sim import IosSimBackend
from .macos_host import MacosHostBackend

_REGISTRY: dict[str, CaptureBackend] = {
    "macos_host": MacosHostBackend(),
    "ios_sim": IosSimBackend(),
}


def get_backend(name: str) -> CaptureBackend:
    """Return the backend registered under `name`.

    Raises KeyError when the name is unknown. The caller (CLI) surfaces
    this as a config-validation error — though `AdvancedConfig` already
    rejects unknown names at parse time, so this is belt-and-suspenders.
    """
    try:
        return _REGISTRY[name]
    except KeyError:
        raise KeyError(
            f"unknown capture backend {name!r}. "
            f"Available: {', '.join(sorted(_REGISTRY))}"
        ) from None


__all__ = ["CaptureBackend", "CaptureError", "get_backend"]
