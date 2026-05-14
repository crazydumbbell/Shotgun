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
  # Override when `root_widget` is declared in a different file than `entry`
  # (e.g. main.dart only does `export 'app.dart' show MyApp;`). Dart's
  # re-exports are not resolved by codegen, so point it at the real file.
  root_widget_import: "package:my_app/app.dart"
  flavor: null                    # optional flutter --flavor
  # Android applicationId (the dotted bundle id used by `am start` to
  # bypass the disambiguator dialog). Required only when
  # `advanced.backend: android_emu`. Ignored by macos_host / ios_sim.
  package_id: com.example.myapp
  dart_defines:                   # optional --dart-define key=value pairs
    SHOTGUN_MODE: "true"
  # Optional setup hook for declarative-router apps. Must live under
  # integration_test/ or lib/; exports a top-level `void shotgunSetup()`
  # (override the name with `setup_fn`). Typical use: register a
  # ShotgunRouterHandler for go_router / auto_route.
  setup_file: integration_test/_shotgun_setup.dart
  setup_fn: shotgunSetup
  # Optional async bootstrap hook. Called inside each shot's testWidgets
  # body, *before* the root widget is pumped. Use to mirror initialization
  # your real `main()` performs before `runApp` — dotenv.load(),
  # MobileAds.initialize(), Firebase.initializeApp(), etc. Without this hook
  # shotgun renders the widget directly and those globals stay uninitialized,
  # which usually crashes the first frame. Lives in the same `setup_file`.
  bootstrap_fn: shotgunBootstrap

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
    # When `advanced.backend: android_emu`, each android entry also needs
    # `emu_avd:` — the name of an AVD registered in Android Studio
    # (Tools → Device Manager → Create Device). Required for the
    # android_emu backend, ignored elsewhere.
    # - { name: "phone", size: [1080, 2400], emu_avd: "Pixel_9_API_36" }

  # For ios_sim:
  #   - sim_device: a name from `xcrun simctl list devicetypes`
  #     (e.g. "iPhone 17 Pro Max")
  #   - sim_runtime: an iOS runtime identifier; omit for latest.

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
  preset: vivid_gradient          # vivid_gradient | minimal | feature_callout | studio
  gradient: ["#667EEA", "#764BA2"]
  font: "Pretendard"              # falls back to Inter if not installed
  accent: "#FFD166"

# Built-in presets:
#   vivid_gradient   — bold gradient bg + radial highlight + framed phone
#   minimal          — clean light bg, dark caption above, soft phone shadow
#   feature_callout  — vivid_gradient + decorative ring + arrow
#   studio           — off-white bg + small dark caption *below* the phone
#                      (lookbook style — pairs with `shotgun compose-grid`)
#
# All presets use a CC0 device-frame PNG by default (PommePlate, iPhone 11
# Pro Max bezel). Set `phone.frame_id: null` in advanced config to fall
# back to the synthetic bezel+notch drawer.

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

## `pre_capture` actions (ios_sim backend only)

Each scene may carry a `pre_capture:` list. The backend runs the actions after the deeplink-driven `openurl` has settled but *before* the screenshot. Actions are executed top-to-bottom on the booted simulator. The `macos_host` backend ignores `pre_capture` entirely.

```yaml
scenes:
  - id: search
    route: /search
    pre_capture:
      - { action: keyboard_show }
      - { action: wait, ms: 400 }
      - { action: keyboard_locale }              # cycle to next input source
      - { action: wait, ms: 600 }
  - id: notif_state
    route: /inbox
    pre_capture:
      - action: notification
        bundle_id: com.example.contractanalyzer
        payload:
          aps:
            alert:
              title: "New risk flagged"
              body: "Your residential lease has 4 risky clauses"
            badge: 1
            sound: default
      - { action: wait, ms: 1400 }               # let banner animate in
  - id: detail_share
    route: /contract/1
    pre_capture:
      - { action: share_sheet, target: "Share contract" }
      - { action: wait, ms: 1000 }               # let sheet slide up
```

| Action | Required keys | What it does |
| --- | --- | --- |
| `wait` | `ms` (int) | `time.sleep(ms / 1000)` between actions. |
| `keyboard_show` | — | Tells Simulator's I/O menu to toggle the software keyboard on. Best-effort: silently no-ops if macOS accessibility permission is missing. |
| `keyboard_locale` | — | Presses the globe (🌐) key to cycle input sources. **Prerequisite**: user has added ≥2 keyboards in the simulator's Settings → General → Keyboard → Keyboards. The action only advances one step — chain multiple to skip past sources. |
| `notification` | `bundle_id` (str), `payload` (mapping) | Delivers an APNs banner via `xcrun simctl push`. `payload` is the full APNs body (must contain an `aps` key). Banner takes ~1s to animate in — follow with `wait: ms ≥ 1200`. |
| `share_sheet` | `target` (str) | Clicks the button whose accessibility name matches `target`. App must expose a recognizable label (Flutter `IconButton(tooltip:)` auto-promotes to accessibility name). Best-effort. |

**Permissions reminder**: `keyboard_show`, `keyboard_locale`, and `share_sheet` rely on AppleScript driving the Simulator UI, which needs macOS Accessibility permission for whichever terminal you run `shotgun` from (System Settings → Privacy & Security → Accessibility). `notification` uses `simctl push` directly and needs no special permission. All four are silent on failure — the screenshot still happens, but without the desired UI state.

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
