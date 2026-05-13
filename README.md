# shotgun

> Generate App Store / Play Store screenshots for your Flutter app — automatically, beautifully, in one shot.

**shotgun** is a zero-config screenshot factory for Flutter apps. Point it at your project, define a few scenes, and get production-ready store listing assets in minutes — across iOS sizes, Android sizes, and every language you ship in.

```bash
shotgun init       # generates shotgun.yaml + sample scene
shotgun capture    # runs your app headlessly via `flutter test -d macos`
shotgun compose    # renders gradient backgrounds, frames, captions
open shotgun_output_composed/
```

<p align="center">
  <em>(GIF demo coming in Phase 2 — see <a href="docs/ROADMAP.md">ROADMAP</a>)</em>
</p>

---

## 목차 / Table of Contents

- [Status](#status)
- [Why shotgun](#why-shotgun)
- [Requirements](#requirements)
- [Install](#install)
- [5분 안에 첫 스크린샷 만들기 / 5-minute quick start](#5분-안에-첫-스크린샷-만들기--5-minute-quick-start)
- [shotgun.yaml — full schema](#shotgunyaml--full-schema)
- [What your app needs to provide](#what-your-app-needs-to-provide)
- [How it works](#how-it-works)
- [Compose presets](#compose-presets)
- [Localization (한국어 / CJK)](#localization-한국어--cjk)
- [Status bar normalization](#status-bar-normalization)
- [Declarative routers (go_router, auto_route, beamer)](#declarative-routers-go_router-auto_route-beamer)
- [Try the example apps](#try-the-example-apps)
- [Troubleshooting](#troubleshooting)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

---

## Status

Phase 1 + 1.5 complete. Full `init → capture → compose` pipeline runs from a single `shotgun.yaml`, verified on two example apps (`examples/counter_app`, `examples/notes_app`) across a 2 devices × 2 locales × 3 scenes matrix (12/12 passing). Python unit tests 18/18. CI runs pytest + `flutter analyze` + a macOS capture smoke test on every push.

See [docs/STATUS.md](docs/STATUS.md) for the current handoff state and [docs/ROADMAP.md](docs/ROADMAP.md) for what's next.

**Not yet on pub.dev / PyPI** — install via Git dependency (see [Install](#install)). First registry release is targeted for Phase 2. Until then, `pip install git+...` and the `git:` directive in `pubspec.yaml` work the same way without the clone-and-symlink dance.

---

## Why shotgun

You built the app. You shipped the features. Now the store listing asks for:

- iPhone 6.7" screenshots × 5
- iPhone 6.5" screenshots × 5
- iPad screenshots × 5
- Android Phone screenshots × 5
- Android Tablet screenshots × 5
- ...times every language you support

That's hundreds of images. Today, the options are:

| Existing tool | The pain |
|---|---|
| `fastlane snapshot` / `screengrab` | Native-only, two codebases, no Flutter awareness |
| `screenshots` (pub.dev) | Abandoned, null-safety incomplete |
| Figma + manual screenshots | Slow, inconsistent, doesn't scale per language |
| Previewed.app, Screenshots.pro | Paid, manual, no data automation |

**shotgun** is for the indie Flutter developer who wants:

1. **One source of truth** — your Flutter widgets, your scene definitions
2. **Headless** — no simulator/emulator dance (runs on `flutter test -d macos`)
3. **Designer-grade output** — vivid gradients, branded captions, marketing-ready
4. **Per-language** automation — define captions in YAML, get localized images

---

## Requirements

| | Min version | Notes |
|---|---|---|
| Flutter | 3.41+ | Dart 3.11+ |
| Python  | 3.10+ | shotgun CLI is Python (Pillow + Click + Pydantic + Jinja2) |
| OS for `shotgun capture` | macOS | Capture runs on `flutter test -d macos`. Linux/Windows capture not yet supported. |
| OS for `shotgun compose` | macOS / Linux / Windows | Pillow only — works anywhere |

**Why macOS for capture?** shotgun captures by running your app on the macOS desktop target, not the iOS/Android simulator. This is faster (no simulator boot), more deterministic (no orientation/scaling drift), and avoids paid macOS CI runners for everything except the capture step. The trade-off: capture itself has to run on a Mac. Compose can run on any CI.

---

## Install

shotgun is two packages — a Python CLI (`shotgun_cli`) that drives capture/compose, and a Dart helper (`shotgun_runner`) your app depends on. **You don't need to clone this repo to use it** — both packages install directly from GitHub.

### 1. Install the Python CLI

```bash
# Recommended: install into a venv so it doesn't pollute your global Python
python3 -m venv ~/.shotgun-venv
source ~/.shotgun-venv/bin/activate

pip install "git+https://github.com/crazydumbbell/Shotgun.git#subdirectory=packages/shotgun_cli"

shotgun --help    # verify
```

> Want it on your PATH permanently? Either keep that venv active in your shell rc, or use [`pipx`](https://pipx.pypa.io/): `pipx install "git+https://github.com/crazydumbbell/Shotgun.git#subdirectory=packages/shotgun_cli"`.

### 2. Add the Dart runner to your Flutter app

In **your** Flutter app's `pubspec.yaml`:

```yaml
dev_dependencies:
  shotgun_runner:
    git:
      url: https://github.com/crazydumbbell/Shotgun.git
      path: packages/shotgun_runner
      ref: main                  # or a specific tag once we publish releases
  integration_test:
    sdk: flutter
```

```bash
flutter pub get
```

That's it — no clone, no absolute paths, no copy/paste. Your teammates and CI will resolve the dependency the same way.

> **Pin to a specific version** once you ship: replace `ref: main` with a commit SHA (`ref: 86d3fae`) or git tag (`ref: v0.1.0`). Recommended for production projects so a shotgun update doesn't surprise you.

### Updating later

```bash
# Python CLI
pip install --upgrade --force-reinstall \
  "git+https://github.com/crazydumbbell/Shotgun.git#subdirectory=packages/shotgun_cli"

# Dart runner — in your Flutter app
flutter pub upgrade shotgun_runner
```

---

## 5분 안에 첫 스크린샷 만들기 / 5-minute quick start

The fastest way to see results is to run the bundled `examples/notes_app`. **For this you do need a local checkout** (the examples are inside the repo):

```bash
git clone https://github.com/crazydumbbell/Shotgun.git
cd Shotgun/examples/notes_app
flutter pub get
shotgun capture && shotgun compose
open shotgun_output_composed/
```

You'll get **12 composed PNGs** (2 devices × 2 locales × 3 scenes). First cold build ≈ 2 minutes; incremental ≈ 8 seconds per shot.

### Then point it at your own app

In your own Flutter project (no clone needed — you already added `shotgun_runner` via git in [Install](#install)):

```bash
cd /path/to/your_flutter_app
shotgun init                # writes ./shotgun.yaml (sample)
$EDITOR shotgun.yaml        # define scenes, devices, locales
shotgun capture             # → shotgun_output/<platform>/<device>/<locale>/NN_<scene>.png
shotgun compose             # → shotgun_output_composed/...
```

The output is a matrix laid out as:

```
shotgun_output_composed/
├── ios/
│   ├── 6.7/
│   │   ├── en/
│   │   │   ├── 01_home.png
│   │   │   ├── 02_search.png
│   │   │   └── 03_detail.png
│   │   └── ko/
│   │       └── ...
│   └── 6.5/
│       └── ...
└── android/
    └── phone/
        └── ...
```

Drop these directly into App Store Connect / Google Play Console.

---

## shotgun.yaml — full schema

A minimal example:

```yaml
app:
  entry: lib/main.dart        # your app's main()
  root_widget: MyApp          # the widget pumped in tests
  # setup_file: integration_test/_shotgun_setup.dart   # optional, for go_router etc.

devices:
  ios:
    - { name: "6.7", size: [1290, 2796] }      # iPhone 6.7"
    - { name: "6.5", size: [1242, 2688] }      # iPhone 6.5"
  android:
    - { name: "phone",  size: [1080, 1920] }
    - { name: "tablet", size: [1600, 2560] }

locales: [en, ko, ja]

theme:
  preset: vivid_gradient       # vivid_gradient | minimal | feature_callout

advanced:
  status_bar:
    normalize: true             # iOS only — stamp 9:41 + 100% battery
    time: "9:41"
    style: auto                 # auto | light | dark

scenes:
  - id: home
    route: /
    caption:
      en: "Every thought,\nin one place"
      ko: "모든 생각을\n한곳에"
      ja: "すべての思考を\nひとつに"

  - id: search
    route: /search
    caption:
      en: "Find anything,\nin a flash"
      ko: "무엇이든\n빠르게 검색"
      ja: "なんでも\n素早く検索"

  - id: detail
    route: /note/1
    only: [ios]                  # optional: limit this scene to specific platforms
    caption:
      en: "Beautiful detail views"
      ko: "아름다운 상세 화면"
      ja: "美しい詳細ビュー"
```

See [docs/CONFIG_SCHEMA.md](docs/CONFIG_SCHEMA.md) for the full spec and [examples/notes_app/shotgun.yaml](examples/notes_app/shotgun.yaml) for a working reference.

---

## What your app needs to provide

`examples/notes_app/` is the reference implementation. To make your app shotgun-ready:

1. **Add the dev dependency** on `shotgun_runner` (see [Install](#install)).
2. **Use `MaterialApp.routes` (or `onGenerateRoute`)** for each scene route — or wire a [router hook](#declarative-routers-go_router-auto_route-beamer) for declarative routers like `go_router`.
3. **For multi-locale**, declare `flutter_localizations` in `pubspec.yaml` and pass `localizationsDelegates` + `supportedLocales` to your `MaterialApp`. shotgun forces the locale via `PlatformDispatcher` before `pumpWidget`.
4. **For non-Latin captions** (Korean, Japanese, Chinese, etc.) you need a CJK-capable font installed on the machine running `shotgun compose`. macOS ships Apple SD Gothic Neo / PingFang — shotgun picks them up automatically. See [Localization](#localization-한국어--cjk) below for Linux/CI.
5. **macOS entitlements**: `macos/Runner/DebugProfile.entitlements` must exist. shotgun patches `com.apple.security.app-sandbox` to `<false/>` for the duration of `capture` and restores it on exit (even if you Ctrl-C — there's a self-heal on the next run).

---

## How it works

```
shotgun.yaml
   │
   ▼
shotgun capture
   ├─ codegen → integration_test/_shotgun_generated.dart  (one testWidgets per shot)
   ├─ entitlements <true/> → <false/>                     (auto-restore on exit / next run)
   ├─ flutter test -d macos                               (runs every shot)
   └─ writes shotgun_output/<platform>/<device>/<locale>/NN_<scene>.png
   │
   ▼
shotgun compose
   └─ Pillow → gradient + phone frame + caption → shotgun_output_composed/...
```

Each generated `testWidgets` block sets the locale, resizes the test view, pumps your `MaterialApp`, navigates to the scene route, and captures the framed subtree to a PNG. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the design rationale.

---

## Compose presets

Three presets ship out of the box. Set with `theme.preset:` in `shotgun.yaml`, or override per-run with `shotgun compose --preset <name>`.

| Preset | Look | Use case |
|---|---|---|
| `vivid_gradient` (default) | Bold gradient background, large white caption, phone frame | Consumer/social/lifestyle apps |
| `minimal` | Clean white background, dark caption, subtle frame | Productivity, fintech, dev tools |
| `feature_callout` | Vivid gradient + ring highlight + arrow | "Tap here!" feature emphasis |

Preview a single screenshot quickly:

```bash
shotgun compose shotgun_output/ios/6.7/en/01_home.png /tmp/preview.png --preset minimal
open /tmp/preview.png
```

---

## Localization (한국어 / CJK)

shotgun captures and composes in any language your `MaterialApp` supports. The two pieces:

**Capture side** — set `locales: [en, ko, ja, ...]` in `shotgun.yaml`. shotgun forces each via `PlatformDispatcher.localeTestValue` before pumping the widget, so your `Localizations.of` and `AppLocalizations` calls resolve correctly.

**Compose side (font rendering)** — Pillow needs a CJK-capable font on the host. shotgun's font resolver checks, in order:

| Platform | Default font candidates |
|---|---|
| macOS | Apple SD Gothic Neo (KO), PingFang SC (CJK), Helvetica Neue (Latin) |
| Linux | Noto Sans CJK KR/SC/JP, DejaVu Sans (install via `apt-get install fonts-noto-cjk`) |
| Windows | Malgun Gothic, Microsoft YaHei, Segoe UI |

Override with environment variables if you need exact control:

```bash
export SHOTGUN_FONT_LATIN=/path/to/Inter-Bold.ttf
export SHOTGUN_FONT_KO=/path/to/Pretendard-Bold.otf
export SHOTGUN_FONT_CJK=/path/to/NotoSansCJK-Bold.ttc
shotgun compose
```

If captions render as 두부 (tofu / `▯`), the font for that script wasn't found — check the warning printed to stderr on the first compose call.

---

## Status bar normalization

App Store rejects screenshots with messy status bars (low battery, weird carrier names, 11:47 AM, etc.). Enable normalization in `shotgun.yaml`:

```yaml
advanced:
  status_bar:
    normalize: true
    time: "9:41"        # the canonical Apple demo time
    style: auto         # auto | light | dark
```

When enabled, shotgun stamps `9:41` + a full battery glyph onto iOS shots between raw capture and phone framing. `style: auto` samples the top strip of your screenshot and picks white or black text automatically.

Your app should leave a ~44pt SafeArea at the top so the stamp doesn't overlap content. Android shots are untouched.

---

## Declarative routers (go_router, auto_route, beamer)

If your app doesn't use `MaterialApp.routes` / `onGenerateRoute`, the default `Navigator.pushNamed` fallback won't work. Provide a router hook:

```yaml
# shotgun.yaml
app:
  entry: lib/main.dart
  root_widget: MyApp
  setup_file: integration_test/_shotgun_setup.dart
```

```dart
// integration_test/_shotgun_setup.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:shotgun_runner/shotgun_runner.dart';
import 'package:your_app/main.dart';   // for the global router instance

Future<void> shotgunSetup() async {
  ShotgunCapture.setRouterHandler((WidgetTester tester, String route) async {
    // For go_router — fire-and-forget, don't await
    appRouter.go(route);
    await tester.pumpAndSettle();
  });
}
```

shotgun codegen will import `_shotgun_setup.dart` and call `shotgunSetup()` at the start of `main()`. `'/'` is treated as a no-op (your app's initial route).

**Important**: inside the handler, do **not** `await pushNamed` — it will hang. Use fire-and-forget APIs (`context.go`, `unawaited(...)`).

---

## Try the example apps

Two reference apps live in [examples/](examples/):

```bash
# Tiny single-route example (Flutter default counter)
cd examples/counter_app
flutter pub get
shotgun capture && shotgun compose

# Full 3-route notes app with localization
cd examples/notes_app
flutter pub get
shotgun capture && shotgun compose
```

`notes_app` exercises everything: multi-locale, multi-device, named routes, scene filtering, and the router hook setup file. Use it as a template.

---

## Troubleshooting

<details>
<summary><strong><code>shotgun capture</code> hangs on <code>flutter test -d macos</code></strong></summary>

- Make sure `macos/Runner/DebugProfile.entitlements` exists. shotgun won't create it for you — it's part of your Flutter project's macOS scaffolding.
- If you've called `await pushNamed(...)` inside a router handler, it will hang. Switch to fire-and-forget (`unawaited(...)` or `context.go(...)`).
- First build is genuinely slow (~2 min). Subsequent shots are ~8 sec each.
</details>

<details>
<summary><strong>Korean/CJK captions render as <code>▯▯▯</code> (tofu)</strong></summary>

- macOS should "just work." If not, check the stderr warning shotgun prints on the first compose run.
- Linux/CI: `sudo apt-get install fonts-noto-cjk` (Ubuntu/Debian).
- Override directly: `export SHOTGUN_FONT_KO=/abs/path/to/your-font.otf`.
</details>

<details>
<summary><strong>App opens with sandbox / network errors after capture</strong></summary>

shotgun patches `com.apple.security.app-sandbox` to `<false/>` during capture and restores it on exit. If you Ctrl-C mid-run and the file is left modified, the **next** `shotgun capture` self-heals from the `.shotgun-bak` sibling. Or restore manually:

```bash
mv macos/Runner/DebugProfile.entitlements.shotgun-bak \
   macos/Runner/DebugProfile.entitlements
```
</details>

<details>
<summary><strong><code>shotgun_runner</code> import not resolving</strong></summary>

- Did you run `flutter pub get` after adding the path dependency?
- The path in `pubspec.yaml` must be **absolute** when using `path:` against a sibling repo, or relative-from-pubspec when in a monorepo.
- Restart your IDE's Dart analyzer.
</details>

<details>
<summary><strong>Captions overlap the status bar</strong></summary>

Your app needs to leave a ~44pt SafeArea at the top. Wrap your root scaffold body in `SafeArea(top: true, ...)` or add explicit top padding equal to `MediaQuery.of(context).padding.top`.
</details>

For anything else, [open an issue](https://github.com/crazydumbbell/Shotgun/issues) with:
- Your `shotgun.yaml`
- The output of `shotgun capture` (or last 50 lines of `flutter test` stderr)
- Flutter / Dart / Python / macOS versions (`flutter --version && python3 --version && sw_vers`)

---

## Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md). Highlights still ahead:

- First pub.dev / PyPI release
- Animated GIF / video demo in this README
- Golden-image visual regression (current unit tests check shape, not pixels)
- `lifestyle` preset (phone on top of curated background imagery)
- A dedicated `examples/notes_app_gorouter/` to exercise the declarative-router hook end-to-end

---

## Contributing

Contributions are very welcome — this is early-stage and there's a lot of low-hanging fruit. A few ways to help:

- **Try it on your real app** and [open an issue](https://github.com/crazydumbbell/Shotgun/issues) when something is unclear, broken, or unexpectedly works. Real-world friction reports are the most valuable contribution right now.
- **Add a compose preset** in [`packages/shotgun_cli/src/shotgun_cli/compose.py`](packages/shotgun_cli/src/shotgun_cli/compose.py) (`vivid_gradient`, `minimal`, `feature_callout` are existing examples). PRs should include a unit test and a sample image.
- **Pick something from the roadmap** — declarative-router end-to-end example, lifestyle preset, golden-image regression. Comment on or open an issue first so we can sync on scope.
- **Fix typos / docs** — no issue needed, just send a PR.

### Dev setup

```bash
git clone https://github.com/crazydumbbell/Shotgun.git
cd Shotgun
python3 -m venv .venv && source .venv/bin/activate
pip install -e "packages/shotgun_cli[dev]"

# Run the test suite (18 cases)
pytest packages/shotgun_cli

# Smoke test the example
cd examples/notes_app && flutter pub get
shotgun capture && shotgun compose
```

CI ([.github/workflows/ci.yml](.github/workflows/ci.yml)) runs pytest + `flutter analyze` on every push, plus a full capture/compose smoke on macOS for `notes_app`. Make sure both stay green before requesting review.

### PR checklist

- [ ] `pytest packages/shotgun_cli` passes locally
- [ ] `flutter analyze` clean in any example app you touched
- [ ] `examples/notes_app` capture+compose still produces 12 PNGs
- [ ] New behavior covered by a test (Pydantic schema, codegen output, or Pillow shape test)
- [ ] README / `docs/CONFIG_SCHEMA.md` updated if you added a user-facing knob

---

## License

[MIT](LICENSE). Use it, fork it, ship paid apps with it — just keep the license notice.
