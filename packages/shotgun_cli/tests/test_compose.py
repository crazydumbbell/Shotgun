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


def test_studio_renders(fake_screenshot: Path, tmp_path: Path):
    """Studio preset uses an off-white solid background, caption below
    the phone. Verify both: canvas size unchanged, and the top strip
    (above where the phone lands) is the studio background color."""
    img = _render(fake_screenshot, tmp_path / "studio.png", "studio")
    assert img.size == (1290, 2796)
    # Top-right corner — definitely above the phone, definitely not
    # caption (caption is below).
    patch = list(img.crop((1100, 50, 1200, 150)).getdata())
    expected = (241, 242, 245)
    for r, g, b in patch[:10]:
        assert abs(r - expected[0]) <= 3
        assert abs(g - expected[1]) <= 3
        assert abs(b - expected[2]) <= 3


def test_frame_default_keeps_screen_pixels(fake_screenshot: Path, tmp_path: Path):
    """When a frame asset is used, the screenshot must still be visible
    through the cut-out screen rect — not covered by the frame PNG.

    Renders the same screenshot twice: once with the default frame,
    once with frame_id=None (synthetic bezel). Both should show the
    light top half of the fake_screenshot inside the phone region.
    """
    from shotgun_cli.compose import Preset, PhoneConfig, compose

    out_framed = tmp_path / "framed.png"
    out_synth = tmp_path / "synth.png"
    compose(fake_screenshot, out_framed, "Caption", Preset(name="vivid_gradient"))
    no_frame = Preset(name="x", phone=PhoneConfig(frame_id=None))
    compose(fake_screenshot, out_synth, "Caption", no_frame)

    framed = Image.open(out_framed)
    synth = Image.open(out_synth)
    # Pick a vertical column down the phone center; count light pixels
    # (the top half of fake_screenshot is (245,247,250)). Both renders
    # should hit a similar count — proves the frame path didn't blot
    # the screen out with dark frame pixels.
    def light_pixels(img: Image.Image) -> int:
        col = img.crop((640, 0, 650, 2796)).convert("RGB")
        return sum(
            1 for r, g, b in col.getdata()
            if r > 220 and g > 220 and b > 220
        )
    assert light_pixels(framed) > 200, "framed render shows no screenshot"
    assert light_pixels(synth) > 200, "synthetic render shows no screenshot"


def test_compose_grid_smoke(fake_screenshot: Path, tmp_path: Path):
    """compose_grid should tile multiple composed PNGs onto one canvas."""
    from shotgun_cli.compose import compose_grid

    # Produce 4 throwaway composed images.
    paths = []
    for i in range(4):
        p = tmp_path / f"comp_{i}.png"
        _render(fake_screenshot, p, "minimal")
        paths.append(p)

    out = tmp_path / "grid.png"
    compose_grid(paths, out, cols=4)
    grid = Image.open(out)
    # Default canvas size in compose_grid.
    assert grid.size == (3200, 2400)
    assert grid.mode == "RGB"
