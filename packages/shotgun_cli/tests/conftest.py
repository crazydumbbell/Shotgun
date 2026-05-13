"""Shared fixtures for shotgun_cli tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """A minimal fake Flutter project: pubspec + integration_test dir."""
    (tmp_path / "pubspec.yaml").write_text("name: fake_app\n", encoding="utf-8")
    (tmp_path / "integration_test").mkdir()
    (tmp_path / "lib").mkdir()
    return tmp_path


@pytest.fixture
def fake_screenshot(tmp_path: Path) -> Path:
    """Synthetic 1290x2796 RGB PNG with two color bands (light top,
    darker bottom) — large enough that status-bar stamping has somewhere
    to write and the auto-color picker has a deterministic signal.
    """
    path = tmp_path / "raw.png"
    img = Image.new("RGB", (1290, 2796), (245, 247, 250))
    # Bottom half darker, used by the script_of branch tests indirectly.
    bottom = Image.new("RGB", (1290, 1398), (40, 42, 54))
    img.paste(bottom, (0, 1398))
    img.save(path, "PNG")
    return path
