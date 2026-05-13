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
    # Optional explicit import for `root_widget`. Codegen normally derives
    # the import from `entry`, which only works when `root_widget` is
    # *declared* in that file. Dart's `export ... show X` re-exports are not
    # resolved, so apps that put their root widget in (say) `lib/app.dart`
    # and `export 'app.dart' show MyApp;` from main.dart will fail to build.
    # Set this to a Dart import path (`package:my_app/app.dart`) to point
    # codegen at the real declaration.
    root_widget_import: str | None = None
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

    # Optional bootstrap hook. When set, codegen calls `<bootstrap_fn>()` in
    # the generated test's `main()` *before any shots run*, awaiting it if it
    # returns a Future. Use this to mirror initialization your app's real
    # `main()` performs before `runApp` — e.g. `dotenv.load()`,
    # `MobileAds.initialize()`, `Firebase.initializeApp()`. Without this hook
    # shotgun renders the root widget directly and those globals stay
    # uninitialized, which usually crashes the first frame.
    #
    # The hook lives in `setup_file` (so existing router setup files can host
    # both `shotgunSetup` and a bootstrap function).
    bootstrap_fn: str | None = None

    @field_validator("root_widget_import")
    @classmethod
    def _root_widget_import_shape(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not (v.startswith("package:") or v.endswith(".dart")):
            raise ValueError(
                "app.root_widget_import must be a Dart import string like "
                "'package:my_app/app.dart' (or a path ending in .dart)"
            )
        return v

    @model_validator(mode="after")
    def _bootstrap_requires_setup_file(self) -> AppConfig:
        if self.bootstrap_fn and not self.setup_file:
            raise ValueError(
                "app.bootstrap_fn requires app.setup_file (the bootstrap "
                "function must live in a Dart file that codegen can import)"
            )
        return self


class DeviceSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    size: tuple[int, int]
    # Used only by the `ios_sim` backend — which simulator device profile
    # to boot (`xcrun simctl list devicetypes` shows valid values).
    # Defaulted in the backend so users on `macos_host` can ignore it.
    sim_device: str | None = None
    # Optional iOS runtime pin. `latest` (default) lets the backend pick
    # the newest installed runtime. Or specify e.g.
    # `com.apple.CoreSimulator.SimRuntime.iOS-26-4`.
    sim_runtime: str | None = None
    # Used only by the `android_emu` backend (Phase 2 stretch).
    emu_avd: str | None = None

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


_VALID_PRESETS = {"vivid_gradient", "minimal", "feature_callout", "studio", "dark_studio"}


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
    # Used only by the `ios_sim` backend. Wait this long (ms) between
    # `openurl` and screenshot. Falls back to `advanced.settle_ms`. Bump
    # this for scenes with animations or async data loads.
    settle_ms: int | None = None
    # Used only by the `ios_sim` backend. List of actions the backend
    # runs *after* settling but *before* the screenshot. Each item is a
    # mapping like `{ action: keyboard_show }` or `{ action: wait, ms: 400 }`.
    # See PHASE2.md for the action vocabulary. Unknown actions are
    # rejected at config-load time.
    pre_capture: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("pre_capture")
    @classmethod
    def _pre_capture_known(cls, v: list[dict[str, Any]]) -> list[dict[str, Any]]:
        valid_actions = {"keyboard_show", "wait"}
        for i, item in enumerate(v):
            action = item.get("action")
            if action not in valid_actions:
                raise ValueError(
                    f"scenes[*].pre_capture[{i}].action {action!r} unknown. "
                    f"Valid: {', '.join(sorted(valid_actions))}"
                )
            if action == "wait" and not isinstance(item.get("ms"), int):
                raise ValueError(
                    f"scenes[*].pre_capture[{i}] wait action needs integer 'ms'"
                )
        return v

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


_VALID_BACKENDS = {"macos_host", "ios_sim"}


class AdvancedConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pixel_ratio: float = 1.0
    status_bar: StatusBarConfig = Field(default_factory=StatusBarConfig)
    # Which capture backend orchestrates the run. `macos_host` is the
    # Phase 1 backend: `flutter test -d macos` with `setSurfaceSize`.
    # `ios_sim` drives a real iOS Simulator via `xcrun simctl` for shots
    # that include real system chrome (status bar, keyboard, share sheet).
    # See docs/PHASE2.md.
    backend: str = "macos_host"
    # URL scheme used by `ios_sim` (and `android_emu`) to navigate via
    # `simctl openurl <scheme>://<route>`. The user's app must declare
    # this scheme in Info.plist and route deeplinks to their app routes.
    scheme: str = "shotgun"
    # Default wait (ms) after `openurl` before the screenshot is taken.
    # Override per scene via `scenes[].settle_ms`. Phase 1 backend ignores.
    settle_ms: int = 1200
    # Hard ceiling on simulator boot time. Long first boots after Xcode
    # updates can exceed 60s; raise this if your CI hits the wall.
    boot_timeout_s: int = 90
    # Optional override for `flutter run` shell command. Leave None to use
    # the default `flutter run -d <udid> --release`. Set this when the
    # app has a custom entrypoint (e.g. `--target=lib/main_dev.dart`).
    boot_command: str | None = None

    @field_validator("backend")
    @classmethod
    def _backend_known(cls, v: str) -> str:
        if v not in _VALID_BACKENDS:
            raise ValueError(
                f"advanced.backend {v!r} unknown. "
                f"Valid: {', '.join(sorted(_VALID_BACKENDS))}"
            )
        return v


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
