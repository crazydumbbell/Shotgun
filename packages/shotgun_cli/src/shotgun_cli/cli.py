"""shotgun command-line entrypoint."""

from __future__ import annotations

from pathlib import Path

import click

from . import __version__
from .capture import CaptureError, run_capture
from .compose import (
    Preset, StatusBarOptions, compose as compose_image, preset_by_name,
)
from .config import load_config


def _resolve_config(config_path: Path | None) -> tuple[Path, Path]:
    """Return (config_path, project_root)."""
    cfg = config_path or (Path.cwd() / "shotgun.yaml")
    cfg = cfg.resolve()
    if not cfg.exists():
        raise click.UsageError(
            f"no shotgun.yaml at {cfg}. run `shotgun init` first."
        )
    return cfg, cfg.parent


@click.group()
@click.version_option(__version__, "-V", "--version")
def main() -> None:
    """Generate App Store / Play Store screenshots for Flutter apps."""


@main.command()
@click.option(
    "--force", is_flag=True,
    help="Overwrite an existing shotgun.yaml.",
)
def init(force: bool) -> None:
    """Drop a starter `shotgun.yaml` into the current directory."""
    target = Path.cwd() / "shotgun.yaml"
    if target.exists() and not force:
        click.echo(f"refusing to overwrite {target} (use --force).", err=True)
        raise SystemExit(1)
    target.write_text(_STARTER_YAML)
    click.echo(f"wrote {target}")
    click.echo("next: run `shotgun capture` to grab raw screenshots.")


@main.command()
@click.option(
    "--config", "config_path",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Path to shotgun.yaml (default: ./shotgun.yaml).",
)
@click.option(
    "--device", default="macos", show_default=True,
    help="`flutter test -d <device>` target. macOS is the only supported "
         "headless target today.",
)
@click.option(
    "--flutter", "flutter_bin", default="flutter", show_default=True,
    help="Path to the `flutter` binary.",
)
@click.option(
    "--keep-generated", is_flag=True,
    help="Don't delete the generated _shotgun_generated.dart after the run.",
)
def capture(
    config_path: Path | None, device: str, flutter_bin: str, keep_generated: bool,
) -> None:
    """Render raw screenshots from your app via `flutter test`."""
    cfg_path, project_root = _resolve_config(config_path)
    config = load_config(cfg_path)
    click.echo(f"using {cfg_path}")
    click.echo(
        f"capturing {len(config.iter_matrix())} shot(s) "
        f"({len(config.scenes)} scene(s) × {len(config.locales)} locale(s) × "
        f"{len(config.devices.ios) + len(config.devices.android)} device(s))"
    )
    try:
        out_root = run_capture(
            config, project_root,
            device=device, flutter_bin=flutter_bin,
            keep_generated=keep_generated,
        )
    except CaptureError as e:
        raise click.ClickException(str(e)) from None
    click.echo(f"raw screenshots in {out_root}")
    click.echo("next: run `shotgun compose` to render store-ready images.")


@main.command("compose")
@click.argument("screenshot", required=False, type=click.Path(path_type=Path))
@click.argument("output", required=False, type=click.Path(path_type=Path))
@click.option(
    "--config", "config_path",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Path to shotgun.yaml. If supplied (or present in cwd), the whole "
         "matrix is composed and SCREENSHOT/OUTPUT are ignored.",
)
@click.option(
    "--caption", default=None,
    help="Caption text for single-image mode. Ignored when --config is used.",
)
@click.option(
    "--preset", "preset_name", default=None,
    help="Preset name for single-image mode "
         "(vivid_gradient, minimal, feature_callout).",
)
def compose_cmd(
    screenshot: Path | None,
    output: Path | None,
    config_path: Path | None,
    caption: str | None,
    preset_name: str | None,
) -> None:
    """Compose screenshots into store-ready marketing images.

    With a `shotgun.yaml` in the current directory (or `--config`), iterates
    the full matrix produced by `shotgun capture`.

    Without one, falls back to single-image mode:
    `shotgun compose <screenshot.png> <output.png>`.
    """
    default_yaml = Path.cwd() / "shotgun.yaml"
    use_matrix = config_path is not None or default_yaml.exists()

    if use_matrix:
        cfg_path, project_root = _resolve_config(config_path)
        config = load_config(cfg_path)
        capture_root = (project_root / config.output.dir).resolve()
        composed_root = capture_root.parent / f"{capture_root.name}_composed"
        composed_root.mkdir(parents=True, exist_ok=True)
        try:
            preset = preset_by_name(config.theme.preset)
        except KeyError:
            raise click.UsageError(
                f"unknown theme.preset {config.theme.preset!r}. "
                "Valid: vivid_gradient, minimal, feature_callout."
            ) from None

        entries = config.iter_matrix()
        click.echo(f"composing {len(entries)} image(s) → {composed_root}")
        missing: list[Path] = []
        for entry in entries:
            shot_path = (
                capture_root / entry.platform / entry.device.name / entry.locale
                / f"{entry.index:02d}_{entry.scene.id}.png"
            )
            if not shot_path.exists():
                missing.append(shot_path)
                continue
            caption_text = entry.scene.caption.get(entry.locale, "")
            out_path = (
                composed_root / entry.platform / entry.device.name / entry.locale
                / f"{entry.index:02d}_{entry.scene.id}.png"
            )
            sb = config.advanced.status_bar
            status_bar = StatusBarOptions(
                enabled=sb.normalize and entry.platform == "ios",
                time=sb.time, color=sb.color, style=sb.style,
            )
            compose_image(
                shot_path, out_path, caption_text, preset,
                status_bar=status_bar,
            )
            click.echo(f"  ✓ {out_path.relative_to(composed_root.parent)}")
        if missing:
            click.echo(
                f"warning: {len(missing)} raw screenshot(s) missing — "
                "did `shotgun capture` succeed?",
                err=True,
            )
            for m in missing[:5]:
                click.echo(f"  missing: {m}", err=True)
        click.echo(f"done. composed images in {composed_root}")
        return

    if screenshot is None or output is None:
        raise click.UsageError(
            "single-image mode needs SCREENSHOT and OUTPUT, e.g.\n"
            "  shotgun compose raw.png out.png"
        )
    if not screenshot.exists():
        raise click.UsageError(f"no such file: {screenshot}")
    caption_text = (caption or "Make your day\\nlighter").replace("\\n", "\n")
    try:
        preset = preset_by_name(preset_name) if preset_name else Preset()
    except KeyError:
        raise click.UsageError(
            f"unknown preset {preset_name!r}. "
            "Valid: vivid_gradient, minimal, feature_callout."
        ) from None
    result = compose_image(screenshot, output, caption_text, preset)
    click.echo(f"wrote {result}")


_STARTER_YAML = """\
# shotgun.yaml — App Store / Play Store screenshot config.
# See docs/CONFIG_SCHEMA.md for the full spec.

app:
  entry: lib/main.dart
  root_widget: MyApp

devices:
  ios:
    - { name: "6.7", size: [1290, 2796] }
  android:
    - { name: "phone", size: [1080, 1920] }

locales: [en]

theme:
  preset: vivid_gradient

scenes:
  - id: home
    route: /
    caption:
      en: "Make your day\\nlighter"
"""


if __name__ == "__main__":
    main()
