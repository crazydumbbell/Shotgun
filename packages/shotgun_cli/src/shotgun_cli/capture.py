"""Capture entrypoint — dispatches to the configured backend.

Phase 1 had a single backend (`flutter test -d macos`), so `capture.py`
*was* the macOS-host driver. Phase 2 introduces multiple backends, so
this module is now a thin dispatcher that picks one based on
`config.advanced.backend`. The actual orchestration lives in
`backends/<name>.py`.

The public surface (`run_capture`, `CaptureError`) is unchanged — the
CLI keeps importing both from here.
"""

from __future__ import annotations

from pathlib import Path

from .backends import CaptureError, get_backend
from .config import ShotgunConfig

__all__ = ["CaptureError", "run_capture"]


def run_capture(
    config: ShotgunConfig,
    project_root: Path,
    *,
    device: str = "macos",
    flutter_bin: str = "flutter",
    keep_generated: bool = False,
    verbose: bool = False,
) -> Path:
    """Dispatch to the backend named by `config.advanced.backend`.

    Returns the raw output directory the backend wrote to.
    """
    backend = get_backend(config.advanced.backend)
    # `device` is only meaningful for the macos_host backend (it's the
    # `flutter test -d <device>` target). Future backends ignore it.
    if backend.name == "macos_host":
        return backend.run(
            config, project_root,
            flutter_bin=flutter_bin,
            keep_generated=keep_generated,
            verbose=verbose,
            device=device,
        )
    return backend.run(
        config, project_root,
        flutter_bin=flutter_bin,
        keep_generated=keep_generated,
        verbose=verbose,
    )
