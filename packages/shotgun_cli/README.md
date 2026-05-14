# shotgun_cli

Python CLI for [shotgun](https://github.com/crazydumbbell/Shotgun) — a
tool for producing App Store / Play Store screenshots of a Flutter app
at exact pixel dimensions, in every locale you ship.

This is the orchestrator: a `shotgun.yaml` describes the matrix
(devices × locales × scenes), and the CLI runs each shot, composes it
with a preset, and writes ready-to-upload PNGs.

## Install

```bash
pip install shotgun-cli
```

You also need the Dart-side package in your Flutter app:

```yaml
# pubspec.yaml
dev_dependencies:
  shotgun_runner: ^0.1.0
```

## Quick start

```bash
cd my_flutter_app
shotgun init                  # writes shotgun.yaml + an example scene
shotgun capture               # generates integration_test, runs the matrix
shotgun compose               # applies preset (background, phone frame, caption)
shotgun compose-grid          # bonus: 3-phone collage for hero shots
```

The default backend (`macos_host`) runs `flutter test -d macos` for
fast, headless captures. Switch to `ios_sim` for real iOS Simulator
chrome (status bar, system keyboard, share sheet) or `android_emu` for
real Android emulator chrome. Each backend is selectable via one line
in `shotgun.yaml`:

```yaml
advanced:
  backend: ios_sim          # or `android_emu` / `macos_host`
```

## Capabilities

- Three backends — `macos_host`, `ios_sim`, `android_emu`
- Matrix iteration: device × locale × scene
- `pre_capture` action DSL: `wait` / `keyboard_show` / `keyboard_locale` /
  `notification` / `share_sheet`
- 5 compose presets: `vivid_gradient` / `minimal` / `feature_callout` /
  `studio` / `dark_studio`
- Realistic phone frames bundled (CC0 PommePlate)
- Multi-phone collage output
- Declarative-router (go_router / auto_route) hook
- iOS status bar normalize (9:41 / 100% / Dynamic Island)
- Android SystemUI demo-mode for the same look on Play Store shots

## Documentation

- [Full README](https://github.com/crazydumbbell/Shotgun) — setup walkthrough
- [docs/CONFIG_SCHEMA.md](https://github.com/crazydumbbell/Shotgun/blob/main/docs/CONFIG_SCHEMA.md) — full yaml reference
- [docs/PHASE2.md](https://github.com/crazydumbbell/Shotgun/blob/main/docs/PHASE2.md) — backend designs

## License

MIT.
