"""shotgun.yaml schema and loader.

Parses the user's config into typed Pydantic models so the rest of the
pipeline (codegen, capture, compose) can rely on validated input.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry: str = "lib/main.dart"
    root_widget: str = "MyApp"
    package: str | None = None  # defaults to the Flutter app's package name
    flavor: str | None = None
    dart_defines: dict[str, str] = Field(default_factory=dict)

    # Optional path (relative to project root) to a Dart file that exports a
    # top-level `void shotgunSetup()` function. The generated integration_test
    # imports it and invokes the function once before any shots run. Used for
    # things like registering a go_router handler via
    # `ShotgunCapture.setRouterHandler`.
    setup_file: str | None = None
    setup_fn: str = "shotgunSetup"


class DeviceSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    size: tuple[int, int]

    @field_validator("size", mode="before")
    @classmethod
    def _coerce_size(cls, v: Any) -> Any:
        if isinstance(v, list) and len(v) == 2:
            return tuple(v)
        return v


class DevicesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ios: list[DeviceSpec] = Field(default_factory=list)
    android: list[DeviceSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def _at_least_one(self) -> DevicesConfig:
        if not self.ios and not self.android:
            raise ValueError("devices: at least one ios or android entry required")
        return self


_VALID_PRESETS = {"vivid_gradient", "minimal", "feature_callout"}


class ThemeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preset: str = "vivid_gradient"
    gradient: list[str] | None = None
    font: str | None = None
    accent: str | None = None

    @field_validator("preset")
    @classmethod
    def _preset_known(cls, v: str) -> str:
        if v not in _VALID_PRESETS:
            raise ValueError(
                f"theme.preset {v!r} unknown. "
                f"Valid: {', '.join(sorted(_VALID_PRESETS))}"
            )
        return v


class SceneOnly(BaseModel):
    model_config = ConfigDict(extra="forbid")

    devices: list[str] | None = None
    locales: list[str] | None = None


class SceneConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    route: str = "/"
    caption: dict[str, str] = Field(default_factory=dict)
    setup: list[dict[str, Any]] = Field(default_factory=list)
    mock: dict[str, Any] = Field(default_factory=dict)
    only: SceneOnly | None = None

    @field_validator("id")
    @classmethod
    def _id_safe(cls, v: str) -> str:
        if not v or not all(c.isalnum() or c in "_-" for c in v):
            raise ValueError(
                f"scene id {v!r} must be non-empty and contain only [A-Za-z0-9_-]"
            )
        return v


class OutputConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dir: str = "shotgun_output"


class StatusBarConfig(BaseModel):
    """Stamp an idealised status bar (time, battery, signal) on top of
    each iOS shot. Apple's app store guidelines suggest 9:41 + full bars.

    `normalize: false` → no-op. Only applied to ios devices for now —
    Android phone shots are left untouched.
    """
    model_config = ConfigDict(extra="forbid")

    normalize: bool = False
    time: str = "9:41"
    color: str = "#000000"  # text color; ignored when style="light"
    style: str = "auto"     # "auto" | "light" | "dark"


class AdvancedConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pixel_ratio: float = 1.0
    status_bar: StatusBarConfig = Field(default_factory=StatusBarConfig)


_DEFAULT_DEVICES = DevicesConfig(
    ios=[DeviceSpec(name="6.7", size=(1290, 2796))],
    android=[],
)


class ShotgunConfig(BaseModel):
    """Top-level shotgun.yaml model."""

    model_config = ConfigDict(extra="forbid")

    app: AppConfig = Field(default_factory=AppConfig)
    devices: DevicesConfig = Field(default_factory=lambda: _DEFAULT_DEVICES)
    locales: list[str] = Field(default_factory=lambda: ["en"])
    theme: ThemeConfig = Field(default_factory=ThemeConfig)
    scenes: list[SceneConfig]
    output: OutputConfig = Field(default_factory=OutputConfig)
    advanced: AdvancedConfig = Field(default_factory=AdvancedConfig)

    @model_validator(mode="after")
    def _captions_cover_locales(self) -> ShotgunConfig:
        for i, scene in enumerate(self.scenes):
            if not scene.caption:
                continue
            for loc in self.locales:
                if loc not in scene.caption:
                    raise ValueError(
                        f"scenes[{i}].caption.{loc}: required when locales includes {loc!r}"
                    )
        return self

    def iter_matrix(self) -> list[ShotMatrixEntry]:
        """Expand the config into one entry per (device, locale, scene)."""
        out: list[ShotMatrixEntry] = []
        device_pairs: list[tuple[str, DeviceSpec]] = [
            ("ios", d) for d in self.devices.ios
        ] + [("android", d) for d in self.devices.android]
        for platform, device in device_pairs:
            device_key = f"{platform}/{device.name}"
            for locale in self.locales:
                for index, scene in enumerate(self.scenes, start=1):
                    if scene.only:
                        if scene.only.devices and device_key not in scene.only.devices:
                            continue
                        if scene.only.locales and locale not in scene.only.locales:
                            continue
                    out.append(
                        ShotMatrixEntry(
                            platform=platform,
                            device=device,
                            locale=locale,
                            scene=scene,
                            index=index,
                        )
                    )
        return out


class ShotMatrixEntry(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    platform: str
    device: DeviceSpec
    locale: str
    scene: SceneConfig
    index: int

    @property
    def device_key(self) -> str:
        return f"{self.platform}/{self.device.name}"

    def capture_path(self, root: Path) -> Path:
        return (
            root
            / self.platform
            / self.device.name
            / self.locale
            / f"{self.index:02d}_{self.scene.id}.png"
        )


def load_config(path: Path) -> ShotgunConfig:
    """Parse and validate a `shotgun.yaml` file."""
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top-level must be a mapping")
    return ShotgunConfig.model_validate(data)
