"""End-to-end compose checks. Each test renders a real PNG and asserts
*shape*, not pixel equality — golden-image diffing belongs in a separate
visual-regression layer."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from shotgun_cli.compose import (
    StatusBarOptions, compose, preset_by_name,
)


def _render(raw: Path, out: Path, name: str, **kwargs) -> Image.Image:
    compose(raw, out, "Caption\nhere", preset_by_name(name), **kwargs)
    return Image.open(out)


def test_vivid_gradient_renders(fake_screenshot: Path, tmp_path: Path):
    img = _render(fake_screenshot, tmp_path / "vg.png", "vivid_gradient")
    assert img.size == (1290, 2796)
    assert img.mode == "RGB"


def test_minimal_uses_solid_background(fake_screenshot: Path, tmp_path: Path):
    img = _render(fake_screenshot, tmp_path / "min.png", "minimal")
    # Sample a 100x100 patch in the top-right corner where neither caption
    # nor phone is drawn. Should be the `minimal` preset's background.
    patch = img.crop((1100, 50, 1200, 150)).getdata()
    pixels = list(patch)
    expected = (248, 249, 251)
    # Allow a small drift for any anti-aliasing the surrounding layers
    # might bleed in (in practice it's exact, but don't be brittle).
    for r, g, b in pixels[:10]:
        assert abs(r - expected[0]) <= 3
        assert abs(g - expected[1]) <= 3
        assert abs(b - expected[2]) <= 3


def test_feature_callout_adds_yellow_pixels(
    fake_screenshot: Path, tmp_path: Path,
):
    vg = _render(fake_screenshot, tmp_path / "vg.png", "vivid_gradient")
    fc = _render(fake_screenshot, tmp_path / "fc.png", "feature_callout")
    # The callout color (255, 209, 102) shouldn't appear in the plain
    # gradient. Compare counts — feature_callout should have many more.
    def yellowish(img: Image.Image) -> int:
        n = 0
        for r, g, b in img.getdata():
            if 240 <= r <= 255 and 195 <= g <= 220 and 90 <= b <= 115:
                n += 1
        return n
    assert yellowish(fc) > yellowish(vg) + 200


def test_status_bar_stamps_top_strip(fake_screenshot: Path, tmp_path: Path):
    """The status-bar stamp should darken the top edge of an otherwise
    light screenshot. Operates directly on the raw image (no phone
    framing) so the test isn't tied to layout constants."""
    from shotgun_cli.compose import _stamp_status_bar

    src = Image.open(fake_screenshot).convert("RGBA")
    stamped = _stamp_status_bar(
        src, time_text="9:41", style="auto", color_hex="#000000",
    )

    # Top 100px strip — uniform (245,247,250) before stamping.
    def dark_pixels(img: Image.Image) -> int:
        strip = img.crop((0, 0, img.size[0], 100)).convert("RGB")
        return sum(
            1 for r, g, b in strip.getdata()
            if r < 80 and g < 80 and b < 80
        )

    assert dark_pixels(stamped) > 200
    assert dark_pixels(src) == 0


def test_unknown_preset_raises():
    import pytest
    with pytest.raises(KeyError):
        preset_by_name("does_not_exist")
