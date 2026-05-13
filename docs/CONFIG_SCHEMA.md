# `shotgun.yaml` schema

This file is the single source of truth for what shotgun produces. It lives at the root of a user's Flutter project.

## Minimal example

```yaml
scenes:
  - id: home
    route: /
```

That's it. Everything else defaults. Running `shotgun capture && shotgun compose` would emit a single iPhone 6.7" screenshot in English with the default `vivid_gradient` preset.

## Full schema

```yaml
# ───────────────────────────────────────────────────────
# app: how to launch the user's Flutter app for capture
# ───────────────────────────────────────────────────────
app:
  entry: lib/main.dart            # default; can be lib/main_shotgun.dart
  root_widget: MyApp              # name of the root widget class to pump
  flavor: null                    # optional flutter --flavor
  dart_defines:                   # optional --dart-define key=value pairs
    SHOTGUN_MODE: "true"
  # Optional setup hook for declarative-router apps. Must live under
  # integration_test/ or lib/; exports a top-level `void shotgunSetup()`
  # (override the name with `setup_fn`). Typical use: register a
  # ShotgunRouterHandler for go_router / auto_route.
  setup_file: integration_test/_shotgun_setup.dart
  setup_fn: shotgunSetup

# ───────────────────────────────────────────────────────
# devices: which sizes to emit
# ───────────────────────────────────────────────────────
devices:
  ios:
    - { name: "6.7",  size: [1290, 2796] }   # iPhone 15 Pro Max
    - { name: "6.5",  size: [1242, 2688] }   # iPhone 11 Pro Max
    - { name: "5.5",  size: [1242, 2208] }   # iPhone 8 Plus
    - { name: "ipad", size: [2048, 2732] }   # iPad Pro 12.9"
  android:
    - { name: "phone",  size: [1080, 1920] }
    - { name: "tablet", size: [1600, 2560] }

# Built-in shorthand:
# devices: { preset: "store_required" }
# → expands to all dimensions the App Store + Play Store actually require

# ───────────────────────────────────────────────────────
# locales: which languages to render
# ───────────────────────────────────────────────────────
locales: [ko, en, ja]
# Each locale is passed to the runner via env. The user's app is expected
# to honor it (e.g. via `Localizations` / `intl`).

# ───────────────────────────────────────────────────────
# theme: branding tokens used by presets
# ───────────────────────────────────────────────────────
theme:
  preset: vivid_gradient          # vivid_gradient | minimal | feature_callout
  gradient: ["#667EEA", "#764BA2"]
  font: "Pretendard"              # falls back to Inter if not installed
  accent: "#FFD166"

# Built-in presets:
#   vivid_gradient   — bold gradient bg + radial highlight + framed phone
#   minimal          — clean light bg, dark caption, soft phone shadow
#   feature_callout  — vivid_gradient + decorative ring + arrow

# ───────────────────────────────────────────────────────
# scenes: the actual screens you want
# ───────────────────────────────────────────────────────
scenes:
  - id: home
    route: /
    caption:
      ko: "당신의 하루를\n더 가볍게"
      en: "Make your day\nlighter"
      ja: "あなたの一日を\nもっと軽く"
    # Optional: pre-capture setup
    setup:
      - tap: { key: "skip_intro" }
      - wait_for: { key: "home_loaded" }
    # Optional: per-scene mock data override
    mock:
      ko: { user_name: "김민지", posts: [...] }
      en: { user_name: "Mary", posts: [...] }

  - id: detail
    route: /items/sample
    caption:
      ko: "한 번의 탭으로 끝"
      en: "Done in one tap"

  - id: search_results
    route: /search?q=coffee
    caption:
      ko: "원하는 걸 빠르게"
      en: "Find it fast"
    # Optional: only emit this scene for certain devices/locales
    only:
      devices: ["ios/6.7", "android/phone"]
      locales: ["ko", "en"]

# ───────────────────────────────────────────────────────
# output: where files land
# ───────────────────────────────────────────────────────
output:
  dir: shotgun_output
  # Naming: {platform}/{device}/{locale}/{index}_{scene_id}.png
  # → shotgun_output/ios/6.7/ko/01_home.png

# ───────────────────────────────────────────────────────
# advanced: optional knobs
# ───────────────────────────────────────────────────────
advanced:
  status_bar:
    normalize: true               # stamp 9:41 + 100% battery on iOS shots
    time: "9:41"
    style: auto                   # auto | light | dark
    color: "#000000"              # used when style=auto can't decide
  parallelism: 4                  # how many `flutter test` to run concurrently
  pixel_ratio: 3.0                # capture density; higher = sharper but slower
```

The status-bar stamp is applied to the raw screenshot *before* phone framing,
so it sits inside the rendered phone bezel. It's iOS-only — Android shots are
left untouched. Your app should leave the top ~44pt (SafeArea) free, otherwise
the stamp will overlap your content.

## Resolution order

When the same key is settable at multiple levels:

1. `scenes[].mock` overrides `mock_data` at the root
2. `scenes[].only` filters the device/locale matrix
3. `theme` is shallow-merged with the preset's defaults
4. CLI flags (`--locale`, `--device`) override config

## Validation

`shotgun_cli` validates the file with Pydantic on every run. Errors are reported with the path:

```
✗ scenes[2].caption.ko: required when locales includes 'ko'
✗ devices.ios[0].size: must be [width, height], not [height, width]
✗ theme.gradient: must be a list of 2 hex colors
```

## Open questions

- **Multi-scene transitions**: should we support "navigate from A to B, capture both" as one declaration, or always one scene = one capture?
- **Animated state**: how do users say "wait for the hero animation to settle before capturing"? Probably `setup.wait_for.duration`.
- **Dark mode**: separate `themes` (plural) key, or a per-scene `brightness` override? Leaning toward per-scene.
