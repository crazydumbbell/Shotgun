# Architecture

## High-level data flow

```
┌────────────────────────┐
│  User's Flutter app    │
│  (with shotgun_runner  │
│   as dev_dependency)   │
└──────────┬─────────────┘
           │
           │  shotgun.yaml (scenes, devices, locales, theme)
           ▼
┌────────────────────────────────────────────────┐
│  shotgun_cli (Python)                          │
│  ────────────────────                          │
│  1. Read shotgun.yaml                          │
│  2. Generate integration_test code (codegen)   │
│  3. Spawn `flutter test` per device × locale   │
│  4. Collect raw PNGs                           │
│  5. Compose with preset (frame + bg + caption) │
│  6. Output to output/<platform>/<size>/<lang>/ │
└────────────────────────────────────────────────┘
```

## Two-package split

| Package | Language | Distribution | Role |
|---|---|---|---|
| `shotgun_runner` | Dart | pub.dev (dev_dependency) | Runs inside the user's app. Provides screenshot capture API + mock data injection helpers. |
| `shotgun_cli` | Python | pip / homebrew | Orchestrates everything else. Reads config, generates test code, invokes Flutter toolchain, composes images. |

**Why split?**

- Dart code that runs inside a Flutter app *must* be a Dart package — there's no escape from this.
- Image composition in Dart is painful (no Pillow equivalent). Python has Pillow, ImageMagick bindings, and a deep ecosystem.
- CLI in Python means we can ship via `pip` / `pipx` / `homebrew` without forcing users to deal with Dart globals.

## Capture: how we render without simulators

Flutter's `integration_test` package supports **headless rendering on the host OS**. Specifically:

- **macOS host → `flutter test -d macos`**: app runs as a desktop window. We force the surface size via `binding.setSurfaceSize(...)`.
- **Linux host → `flutter test -d linux`**: same idea.
- **CI (headless Linux) → Xvfb wrapping `flutter test -d linux`**: same idea, no display server.

`setSurfaceSize` lets us *lie* about the device size. The app renders as if it were on a 6.7" iPhone, even though it's running in a macOS window. The captured PNG is the exact pixel grid we'd see on real hardware.

The pixel output is **device-class-agnostic** because Flutter draws everything itself — no native iOS/Android widgets, no platform chrome leaking in.

### What about platform-specific UI?

For `Platform.isIOS` / `Platform.isAndroid` branches, we set `debugDefaultTargetPlatformOverride` to force Cupertino or Material rendering paths. So a single capture run can emit both iOS-style and Android-style versions of the same scene.

## Mock data injection

The runner exposes a hook the user wires into their app once:

```dart
// lib/main.dart (or main_shotgun.dart)
void main() {
  ShotgunRunner.bootstrap(
    onMockData: (sceneId, locale) => MockRegistry.forScene(sceneId, locale),
  );
  runApp(MyApp());
}
```

The user's repository / data layer queries `ShotgunRunner.isActive` (false in production) and substitutes the registered mock when true. This keeps the production code path untouched.

**Two modes for the user:**

1. **Easy mode** — mock data lives in `shotgun.yaml` as YAML. Runner deserializes it. Good for simple list/detail screens.
2. **Pro mode** — user writes Dart that returns full domain objects. Needed when models have complex behavior.

## Composition pipeline (Python side)

```
raw screenshot PNG
       │
       ▼
[1] Status bar normalization     ← optional: stamp 9:41, full battery
       │
       ▼
[2] Device frame overlay         ← Apple/Google official frames per size
       │
       ▼
[3] Background generation        ← gradient / image / solid per preset
       │
       ▼
[4] Caption typesetting          ← per-locale font + size + position
       │
       ▼
[5] Final canvas assembly        ← exact store-required dimensions
       │
       ▼
output PNG
```

Each step is a pure function `Image -> Image`, so presets are just compositions of these steps with different parameters.

## Preset system

A preset is a YAML file that declares how to compose. Example (`presets/vivid_gradient.yaml`):

```yaml
name: vivid_gradient
background:
  type: gradient
  direction: 135deg
  colors: ["{{theme.gradient[0]}}", "{{theme.gradient[1]}}"]
frame:
  type: device_native    # iPhone/Pixel frame matching the target size
  shadow: { blur: 60, opacity: 0.3, y: 20 }
caption:
  font: "{{theme.font | default: 'Inter'}}"
  size: 72
  weight: 800
  color: "#FFFFFF"
  position: { y: 0.1, align: center }
  max_lines: 2
device_offset: { y: 0.55, scale: 0.85 }
```

Presets are user-overridable. Drop a custom `presets/my_brand.yaml` into your project and reference `preset: my_brand`.

## Dependencies (planned)

**Dart side (`shotgun_runner`):**
- `integration_test` (Flutter SDK)
- `flutter_test` (Flutter SDK)
- No other runtime deps — keep the footprint tiny inside user's app

**Python side (`shotgun_cli`):**
- `click` — CLI framework
- `pyyaml` — config parsing
- `pillow` — image composition
- `pydantic` — config validation
- `jinja2` — codegen for integration_test files

## Out of scope (for now)

- Store upload automation (let `fastlane deliver/supply` handle that — we just produce assets)
- Video preview generation (.mp4 store previews)
- A/B testing of screenshot variants
- Web/desktop app store assets
