"""Composition pipeline.

Takes a raw screenshot PNG and a preset config, produces a marketing-ready
store image at the same pixel dimensions.

The pipeline is a series of pure functions, each layer composed on top of
the last:

    gradient bg → radial highlight → caption → phone (bezel + notch) → shadow

A preset is a dataclass of knobs. Each public preset (vivid_gradient,
minimal, etc.) is just a different set of values for the same knobs.
"""

from __future__ import annotations

import math
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


# ───────────────────────────────────────────────────────
# Preset config
# ───────────────────────────────────────────────────────
@dataclass
class GradientConfig:
    start: tuple[int, int, int] = (118, 92, 240)   # #765CF0
    end: tuple[int, int, int] = (236, 72, 153)     # #EC4899
    angle_deg: float = 145.0


@dataclass
class HighlightConfig:
    color: tuple[int, int, int] = (255, 255, 255)
    opacity: int = 70                              # 0-255
    center: tuple[float, float] = (0.25, 0.18)     # canvas fraction
    radius: float = 0.55                           # of max(w, h)


@dataclass
class CaptionConfig:
    color: tuple[int, int, int] = (255, 255, 255)
    stroke_color: tuple[int, int, int] = (0, 0, 0)
    stroke_opacity: int = 60
    stroke_divisor: int = 80                       # stroke_width = font_size/divisor
    top_ratio: float = 0.07
    side_padding_ratio: float = 0.08
    max_height_ratio: float = 0.18
    line_spacing: int = 12


@dataclass
class PhoneConfig:
    scale: float = 0.74                            # phone width / canvas width
    bottom_margin_ratio: float = 0.04
    caption_to_phone_gap_ratio: float = 0.025
    bezel_color: tuple[int, int, int] = (12, 12, 14)
    bezel_thickness_ratio: float = 0.018
    outer_corner_radius_ratio: float = 0.085
    inner_corner_radius_ratio: float = 0.062
    notch_width_ratio: float = 0.32
    notch_height_ratio: float = 0.033              # of inner_width
    notch_top_offset_ratio: float = 0.015          # of inner_width
    shadow_blur: int = 90
    shadow_offset_y: int = 40
    shadow_opacity: int = 120


@dataclass
class StatusBarOptions:
    """Runtime knobs for the iOS status-bar stamp. Mirrors the shotgun.yaml
    `advanced.status_bar` block, decoupled so `compose()` doesn't pull in
    the Pydantic config types.
    """
    enabled: bool = False
    time: str = "9:41"
    color: str = "#000000"
    style: str = "auto"  # "auto" | "light" | "dark" | "custom"


@dataclass
class CalloutConfig:
    """Decorative shapes drawn alongside the caption.

    Used by `feature_callout`. `circle` draws a translucent ring at a
    canvas-relative center; `arrow` draws a curved arrow from a start to
    an end point. Coordinates are fractions of the canvas (0..1).
    """
    enabled: bool = False
    color: tuple[int, int, int] = (255, 209, 102)  # #FFD166
    stroke_ratio: float = 0.006                    # of canvas width
    circle_center: tuple[float, float] | None = None
    circle_radius: float = 0.12                    # of min(canvas w, h)
    arrow_start: tuple[float, float] | None = None
    arrow_end: tuple[float, float] | None = None


@dataclass
class Preset:
    name: str = "vivid_gradient"
    gradient: GradientConfig | None = field(default_factory=GradientConfig)
    highlight: HighlightConfig | None = field(default_factory=HighlightConfig)
    caption: CaptionConfig = field(default_factory=CaptionConfig)
    phone: PhoneConfig = field(default_factory=PhoneConfig)
    callout: CalloutConfig = field(default_factory=CalloutConfig)
    background: tuple[int, int, int] = (255, 255, 255)  # used when gradient=None


def preset_by_name(name: str) -> Preset:
    """Resolve a `theme.preset` value to a fully-configured Preset.

    Unknown names raise `KeyError` — caller should surface that as a
    config validation error.
    """
    factory = _PRESETS.get(name)
    if factory is None:
        raise KeyError(name)
    return factory()


def _preset_vivid_gradient() -> Preset:
    return Preset(name="vivid_gradient")


def _preset_minimal() -> Preset:
    """Clean white background, dark caption, soft drop shadow."""
    return Preset(
        name="minimal",
        gradient=None,
        highlight=None,
        background=(248, 249, 251),
        caption=CaptionConfig(
            color=(20, 22, 28),
            stroke_color=(0, 0, 0),
            stroke_opacity=0,         # no stroke on light backgrounds
            stroke_divisor=999,
        ),
        phone=PhoneConfig(shadow_opacity=80, shadow_blur=110),
    )


def _preset_feature_callout() -> Preset:
    """vivid_gradient + decorative ring + arrow pointing at the phone."""
    base = Preset(name="feature_callout")
    base.callout = CalloutConfig(
        enabled=True,
        color=(255, 209, 102),
        stroke_ratio=0.007,
        circle_center=(0.78, 0.32),
        circle_radius=0.11,
        arrow_start=(0.74, 0.34),
        arrow_end=(0.58, 0.42),
    )
    return base


_PRESETS: dict[str, "callable[[], Preset]"] = {  # type: ignore[type-arg]
    "vivid_gradient": _preset_vivid_gradient,
    "minimal": _preset_minimal,
    "feature_callout": _preset_feature_callout,
}


# ───────────────────────────────────────────────────────
# Layers
# ───────────────────────────────────────────────────────
def _linear_gradient(size: tuple[int, int], cfg: GradientConfig) -> Image.Image:
    w, h = size
    rad = math.radians(cfg.angle_deg)
    dx, dy = math.cos(rad), math.sin(rad)
    corners = [(0, 0), (w, 0), (0, h), (w, h)]
    projs = [x * dx + y * dy for x, y in corners]
    p_min, p_max = min(projs), max(projs)
    span = p_max - p_min if p_max != p_min else 1.0

    # 1/4-res render is visually identical to full-res after upsampling
    # and ~16x faster on big canvases.
    sw, sh = max(1, w // 4), max(1, h // 4)
    img = Image.new("RGB", (sw, sh))
    px = img.load()
    sr, sg, sb = cfg.start
    er, eg, eb = cfg.end
    for y in range(sh):
        for x in range(sw):
            proj = (x * 4) * dx + (y * 4) * dy
            t = (proj - p_min) / span
            px[x, y] = (
                round(sr + (er - sr) * t),
                round(sg + (eg - sg) * t),
                round(sb + (eb - sb) * t),
            )
    return img.resize((w, h), Image.BILINEAR)


def _radial_highlight(base: Image.Image, cfg: HighlightConfig) -> Image.Image:
    w, h = base.size
    cx, cy = int(w * cfg.center[0]), int(h * cfg.center[1])
    radius = int(max(w, h) * cfg.radius)

    scale = 4
    sw, sh = max(1, w // scale), max(1, h // scale)
    mask = Image.new("L", (sw, sh), 0)
    ImageDraw.Draw(mask).ellipse(
        [(cx // scale - radius // scale, cy // scale - radius // scale),
         (cx // scale + radius // scale, cy // scale + radius // scale)],
        fill=cfg.opacity,
    )
    mask = mask.filter(ImageFilter.GaussianBlur(radius // (scale * 2)))
    mask = mask.resize((w, h), Image.BILINEAR)

    overlay = Image.new("RGBA", (w, h), cfg.color + (0,))
    overlay.putalpha(mask)
    out = base.convert("RGBA")
    out.alpha_composite(overlay)
    return out


def _rounded(img: Image.Image, radius: int) -> Image.Image:
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [(0, 0), (img.size[0] - 1, img.size[1] - 1)],
        radius=radius, fill=255,
    )
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    return out


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    v = value.lstrip("#")
    if len(v) == 3:
        v = "".join(c * 2 for c in v)
    return (int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16))


def _stamp_status_bar(
    screenshot: Image.Image,
    *,
    time_text: str,
    style: str,
    color_hex: str,
) -> Image.Image:
    """Return a copy of `screenshot` with an iOS-style status bar painted
    over its top edge.

    The bar is sized as a fraction of the screenshot height — roughly 4%
    — which matches how Apple's mockups crop their notched devices. We
    don't render OS chrome (signal arcs, wifi fan); instead a clean
    `time · 100% battery` strip. Good enough for store listings, and
    importantly device-independent.
    """
    w, h = screenshot.size
    bar_h = max(48, int(h * 0.038))
    side = int(w * 0.07)
    out = screenshot.copy()
    draw = ImageDraw.Draw(out)

    # Sample a tiny strip of the existing pixels to pick text color when
    # style="auto" — dark text on light backgrounds, vice versa.
    if style == "auto":
        strip = out.crop((0, 0, w, bar_h)).convert("L")
        avg = sum(strip.getdata()) / max(1, strip.size[0] * strip.size[1])
        rgb = (255, 255, 255) if avg < 128 else (20, 22, 28)
    elif style == "light":
        rgb = (255, 255, 255)
    elif style == "dark":
        rgb = (20, 22, 28)
    else:
        rgb = _hex_to_rgb(color_hex)

    font_size = int(bar_h * 0.55)
    font = _find_font(font_size, time_text)

    # Time, left side, vertically centered.
    text_bbox = draw.textbbox((0, 0), time_text, font=font)
    text_h = text_bbox[3] - text_bbox[1]
    ty = (bar_h - text_h) // 2 - text_bbox[1]
    draw.text((side, ty), time_text, fill=rgb, font=font)

    # Battery glyph, right side. Pure shapes — no glyph font dependency.
    batt_w = int(bar_h * 0.95)
    batt_h = int(bar_h * 0.42)
    batt_x = w - side - batt_w
    batt_y = (bar_h - batt_h) // 2
    radius = max(2, batt_h // 4)
    draw.rounded_rectangle(
        [(batt_x, batt_y), (batt_x + batt_w, batt_y + batt_h)],
        radius=radius, outline=rgb, width=max(2, batt_h // 8),
    )
    # Positive terminal nub.
    nub_w = max(2, batt_h // 6)
    nub_h = batt_h // 2
    draw.rounded_rectangle(
        [(batt_x + batt_w, batt_y + (batt_h - nub_h) // 2),
         (batt_x + batt_w + nub_w, batt_y + (batt_h + nub_h) // 2)],
        radius=nub_w // 2, fill=rgb,
    )
    # 100% fill (small inset).
    inset = max(2, batt_h // 6)
    draw.rounded_rectangle(
        [(batt_x + inset, batt_y + inset),
         (batt_x + batt_w - inset, batt_y + batt_h - inset)],
        radius=max(1, radius - inset), fill=rgb,
    )

    return out


def _draw_callout(canvas: Image.Image, cfg: CalloutConfig) -> None:
    """Stamp ring + arrow on the canvas in-place. No-op when disabled."""
    if not cfg.enabled:
        return
    w, h = canvas.size
    stroke = max(2, int(w * cfg.stroke_ratio))
    color = cfg.color + (235,)
    draw = ImageDraw.Draw(canvas)

    if cfg.circle_center is not None:
        cx = int(w * cfg.circle_center[0])
        cy = int(h * cfg.circle_center[1])
        r = int(min(w, h) * cfg.circle_radius)
        draw.ellipse(
            [(cx - r, cy - r), (cx + r, cy + r)],
            outline=color, width=stroke,
        )

    if cfg.arrow_start is not None and cfg.arrow_end is not None:
        sx, sy = int(w * cfg.arrow_start[0]), int(h * cfg.arrow_start[1])
        ex, ey = int(w * cfg.arrow_end[0]), int(h * cfg.arrow_end[1])
        draw.line([(sx, sy), (ex, ey)], fill=color, width=stroke)
        # Arrowhead — two short segments perpendicular to the line.
        dx, dy = ex - sx, ey - sy
        length = math.hypot(dx, dy) or 1.0
        ux, uy = dx / length, dy / length
        head = int(min(w, h) * 0.025)
        # Rotate ±150° from the direction vector to get arrowhead legs.
        for angle in (math.radians(150), math.radians(-150)):
            cos_a, sin_a = math.cos(angle), math.sin(angle)
            hx = ex + int(head * (ux * cos_a - uy * sin_a))
            hy = ey + int(head * (ux * sin_a + uy * cos_a))
            draw.line([(ex, ey), (hx, hy)], fill=color, width=stroke)


def _drop_shadow(img: Image.Image, blur: int, opacity: int) -> Image.Image:
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    alpha = img.split()[3]
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    shadow.putalpha(alpha.point(lambda v: min(opacity, v)))
    return shadow.filter(ImageFilter.GaussianBlur(blur))


def _render_phone(
    screenshot: Image.Image, outer_w: int, cfg: PhoneConfig,
) -> Image.Image:
    sw, sh = screenshot.size
    aspect = sh / sw
    bezel = int(outer_w * cfg.bezel_thickness_ratio)
    inner_w = outer_w - 2 * bezel
    inner_h = int(inner_w * aspect)
    outer_h = inner_h + 2 * bezel

    outer_radius = int(outer_w * cfg.outer_corner_radius_ratio)
    inner_radius = int(outer_w * cfg.inner_corner_radius_ratio)

    phone = Image.new("RGBA", (outer_w, outer_h), (0, 0, 0, 0))
    mask = Image.new("L", (outer_w, outer_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [(0, 0), (outer_w - 1, outer_h - 1)], radius=outer_radius, fill=255,
    )
    bezel_layer = Image.new("RGBA", (outer_w, outer_h), cfg.bezel_color + (255,))
    phone.paste(bezel_layer, (0, 0), mask)

    inner = screenshot.resize((inner_w, inner_h), Image.LANCZOS).convert("RGBA")
    phone.alpha_composite(_rounded(inner, inner_radius), (bezel, bezel))

    notch_w = int(inner_w * cfg.notch_width_ratio)
    notch_h = int(inner_w * cfg.notch_height_ratio)
    notch_x = bezel + (inner_w - notch_w) // 2
    notch_y = bezel + int(inner_w * cfg.notch_top_offset_ratio)
    ImageDraw.Draw(phone).rounded_rectangle(
        [(notch_x, notch_y), (notch_x + notch_w, notch_y + notch_h)],
        radius=int(notch_h * 0.5), fill=cfg.bezel_color + (255,),
    )
    return phone


# ───────────────────────────────────────────────────────
# Font handling
# ───────────────────────────────────────────────────────
# Each entry is (path, ttc_index). `ttc_index` is used for .ttc collections
# to pick a specific face (e.g. the Bold variant of a font family).
#
# Lists are merged per-platform at lookup time — macOS uses Apple fonts
# first then falls through to Noto/DejaVu, Linux does the reverse. This
# avoids spending IO probing /System paths on Linux and /usr/share paths
# on macOS for every shot.

_LATIN_MACOS: list[tuple[str, int]] = [
    ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 0),
    ("/System/Library/Fonts/Helvetica.ttc", 1),  # Helvetica Bold
    ("/Library/Fonts/Arial Bold.ttf", 0),
    ("/System/Library/Fonts/Avenir Next.ttc", 1),
]

_LATIN_LINUX: list[tuple[str, int]] = [
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 0),
    ("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 0),
    ("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf", 0),  # Arch
    ("/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf", 0),  # Fedora
    ("/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf", 0),
    ("/usr/share/fonts/google-noto/NotoSans-Bold.ttf", 0),
]

_LATIN_WINDOWS: list[tuple[str, int]] = [
    ("C:/Windows/Fonts/arialbd.ttf", 0),
    ("C:/Windows/Fonts/segoeuib.ttf", 0),
]

# Korean (Hangul). AppleSDGothicNeo is a `.ttc` — face index 4 ≈ Bold.
_KO_MACOS: list[tuple[str, int]] = [
    ("/System/Library/Fonts/AppleSDGothicNeo.ttc", 4),
    ("/System/Library/Fonts/AppleSDGothicNeo.ttc", 0),
    ("/System/Library/Fonts/Supplemental/AppleGothic.ttf", 0),
]

# Linux Noto CJK ships per-region (KR/JP/SC/TC) or as the unified
# `NotoSansCJK-Bold.ttc` collection — packaging differs by distro.
_KO_LINUX: list[tuple[str, int]] = [
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 1),  # KR face
    ("/usr/share/fonts/truetype/noto/NotoSansCJKkr-Bold.otf", 0),
    ("/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc", 1),  # Arch
    ("/usr/share/fonts/google-noto-cjk/NotoSansCJK-Bold.ttc", 1),  # Fedora
    ("/usr/share/fonts/opentype/noto/NotoSansKR-Bold.otf", 0),
    ("/usr/share/fonts/google-noto/NotoSansKR-Bold.otf", 0),
]

_KO_WINDOWS: list[tuple[str, int]] = [
    ("C:/Windows/Fonts/malgunbd.ttf", 0),  # Malgun Gothic Bold
]

# Japanese & Chinese.
_CJK_MACOS: list[tuple[str, int]] = [
    ("/System/Library/Fonts/Hiragino Sans GB.ttc", 1),
    ("/System/Library/Fonts/Hiragino Sans GB.ttc", 0),
]

_CJK_LINUX: list[tuple[str, int]] = [
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 0),  # JP face
    ("/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc", 0),
    ("/usr/share/fonts/google-noto-cjk/NotoSansCJK-Bold.ttc", 0),
    ("/usr/share/fonts/truetype/noto/NotoSansCJKjp-Bold.otf", 0),
]

_CJK_WINDOWS: list[tuple[str, int]] = [
    ("C:/Windows/Fonts/YuGothB.ttc", 0),
]


def _is_macos() -> bool:
    return sys.platform == "darwin"


def _is_windows() -> bool:
    return sys.platform.startswith("win")


def _platform_chain(macos: list, linux: list, windows: list) -> list[tuple[str, int]]:
    """Return candidates in the right order for the current OS.

    Same-platform fonts come first, the other platforms follow as a
    weak fallback (helpful when running inside containers or with
    cross-mounted font directories).
    """
    if _is_macos():
        return macos + linux + windows
    if _is_windows():
        return windows + linux + macos
    return linux + macos + windows


def _env_overrides(env_key: str) -> list[tuple[str, int]]:
    """Read a comma-separated list of `path[:index]` from an env var.

    Empty / unset → []. Lets CI environments point shotgun at exact
    font files without patching the source.
    """
    raw = os.environ.get(env_key)
    if not raw:
        return []
    out: list[tuple[str, int]] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            path, idx = part.rsplit(":", 1)
            try:
                out.append((path, int(idx)))
                continue
            except ValueError:
                pass
        out.append((part, 0))
    return out


def _script_of(text: str) -> str:
    """Detect dominant script: 'ko', 'cjk', or 'latin'.

    Korean is its own bucket because the macOS Apple SD Gothic font is the
    right choice — Hiragino has Hangul glyphs but spacing is off for Korean.
    """
    has_hangul = any("가" <= c <= "힣" for c in text)
    if has_hangul:
        return "ko"
    # CJK Unified Ideographs, Hiragana, Katakana
    has_cjk = any(
        "぀" <= c <= "ヿ"  # Hiragana + Katakana
        or "一" <= c <= "鿿"  # CJK Unified
        for c in text
    )
    if has_cjk:
        return "cjk"
    return "latin"


def _candidates_for(text: str) -> list[tuple[str, int]]:
    latin = _env_overrides("SHOTGUN_FONT_LATIN") + _platform_chain(
        _LATIN_MACOS, _LATIN_LINUX, _LATIN_WINDOWS
    )
    script = _script_of(text)
    if script == "ko":
        return (
            _env_overrides("SHOTGUN_FONT_KO")
            + _platform_chain(_KO_MACOS, _KO_LINUX, _KO_WINDOWS)
            + latin
        )
    if script == "cjk":
        return (
            _env_overrides("SHOTGUN_FONT_CJK")
            + _platform_chain(_CJK_MACOS, _CJK_LINUX, _CJK_WINDOWS)
            + latin
        )
    return latin


_FALLBACK_WARNED: set[str] = set()


def _warn_fallback(script: str) -> None:
    if script in _FALLBACK_WARNED:
        return
    _FALLBACK_WARNED.add(script)
    print(
        f"[shotgun] warning: no font found for script {script!r}; "
        "captions will fall back to PIL's bitmap default. "
        f"Install Noto (e.g. `apt install fonts-noto-cjk`) or set "
        f"SHOTGUN_FONT_{script.upper()} to a TTF/OTF path.",
        file=sys.stderr,
    )


def _find_font(size: int, text: str = "") -> ImageFont.FreeTypeFont:
    for path, index in _candidates_for(text):
        try:
            return ImageFont.truetype(path, size, index=index)
        except OSError:
            continue
    _warn_fallback(_script_of(text))
    return ImageFont.load_default()


def _fit_font(
    draw: ImageDraw.ImageDraw, text: str, max_w: int, max_h: int, spacing: int,
) -> tuple[ImageFont.FreeTypeFont, tuple[int, int, int, int]]:
    lo, hi = 24, max_h
    font = _find_font(lo, text)
    bbox = draw.multiline_textbbox((0, 0), text, font=font, align="center", spacing=spacing)
    best = (font, bbox)
    while lo <= hi:
        mid = (lo + hi) // 2
        f = _find_font(mid, text)
        b = draw.multiline_textbbox((0, 0), text, font=f, align="center", spacing=spacing)
        if (b[2] - b[0]) <= max_w and (b[3] - b[1]) <= max_h:
            best = (f, b)
            lo = mid + 1
        else:
            hi = mid - 1
    return best


# ───────────────────────────────────────────────────────
# Public entrypoint
# ───────────────────────────────────────────────────────
def compose(
    screenshot_path: Path,
    output_path: Path,
    caption: str,
    preset: Preset | None = None,
    *,
    status_bar: "StatusBarOptions | None" = None,
) -> Path:
    """Compose a marketing-ready store image. Returns the output path.

    `status_bar` is an optional `StatusBarOptions` instance; when supplied
    and `enabled=True`, an iOS-style status bar (time + battery) is
    stamped on top of the screenshot before phone framing.
    """
    p = preset or Preset()
    screenshot = Image.open(screenshot_path).convert("RGBA")
    if status_bar is not None and status_bar.enabled:
        screenshot = _stamp_status_bar(
            screenshot,
            time_text=status_bar.time,
            style=status_bar.style,
            color_hex=status_bar.color,
        )
    canvas_w, canvas_h = screenshot.size

    # 1. background
    if p.gradient is not None:
        bg = _linear_gradient((canvas_w, canvas_h), p.gradient)
    else:
        bg = Image.new("RGB", (canvas_w, canvas_h), p.background)
    if p.highlight is not None:
        canvas = _radial_highlight(bg, p.highlight)
    else:
        canvas = bg.convert("RGBA")

    # 2. caption
    cc = p.caption
    draw = ImageDraw.Draw(canvas)
    max_w = int(canvas_w * (1 - 2 * cc.side_padding_ratio))
    max_h = int(canvas_h * cc.max_height_ratio)
    font, bbox = _fit_font(draw, caption, max_w, max_h, cc.line_spacing)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    cap_top = int(canvas_h * cc.top_ratio)
    tx = (canvas_w - text_w) // 2 - bbox[0]
    ty = cap_top - bbox[1]
    stroke_w = max(1, font.size // cc.stroke_divisor)
    draw.multiline_text(
        (tx, ty), caption, font=font, fill=cc.color,
        align="center", spacing=cc.line_spacing,
        stroke_width=stroke_w,
        stroke_fill=cc.stroke_color + (cc.stroke_opacity,),
    )
    cap_bottom = cap_top + text_h

    # 3. phone (sized to fit remaining space)
    pc = p.phone
    gap = int(canvas_h * pc.caption_to_phone_gap_ratio)
    bottom_margin = int(canvas_h * pc.bottom_margin_ratio)
    avail_h = canvas_h - cap_bottom - gap - bottom_margin

    outer_w = int(canvas_w * pc.scale)
    bezel = int(outer_w * pc.bezel_thickness_ratio)
    inner_w = outer_w - 2 * bezel
    aspect = screenshot.size[1] / screenshot.size[0]
    outer_h = int(inner_w * aspect) + 2 * bezel
    if outer_h > avail_h:
        outer_h = avail_h
        inner_h = outer_h - 2 * bezel
        inner_w = int(inner_h / aspect)
        outer_w = inner_w + 2 * bezel

    phone = _render_phone(screenshot, outer_w, pc)
    shadow = _drop_shadow(phone, pc.shadow_blur, pc.shadow_opacity)

    phone_x = (canvas_w - outer_w) // 2
    phone_y = cap_bottom + gap
    canvas.alpha_composite(shadow, (phone_x, phone_y + pc.shadow_offset_y))
    canvas.alpha_composite(phone, (phone_x, phone_y))

    # 4. decorative callouts (rings, arrows) — drawn on top so they
    # frame the phone rather than being hidden behind it.
    _draw_callout(canvas, p.callout)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(output_path, "PNG", optimize=True)
    return output_path
