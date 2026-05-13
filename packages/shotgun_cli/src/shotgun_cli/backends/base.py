"""Capture-backend protocol shared by every implementation."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ..config import ShotgunConfig


class CaptureError(RuntimeError):
    """Raised when a backend's underlying process exits non-zero."""


class CaptureBackend(Protocol):
    """Produces one raw PNG per (device, locale, scene) entry.

    A backend's `run()` is the whole orchestration — boot whatever it
    needs to boot, iterate the matrix, write PNGs to disk, tear down.
    The CLI only knows the contract below; everything else is internal
    to the backend.

    Backends write to `<project_root>/<config.output.dir>/<platform>/
    <device.name>/<locale>/NN_<scene.id>.png` (see
    `ShotMatrixEntry.capture_path`). The CLI verifies presence; backends
    surface failures via `CaptureError`.
    """

    name: str

    def run(
        self,
        config: ShotgunConfig,
        project_root: Path,
        *,
        flutter_bin: str = "flutter",
        keep_generated: bool = False,
        verbose: bool = False,
    ) -> Path:
        """Run the full capture matrix. Returns the raw output root."""
        ...
