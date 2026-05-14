# Phase 2 — Real-simulator capture

## Why this exists

Phase 1's macOS-host backend has a hard ceiling: it can only capture what's inside the Flutter widget tree. The captured pixels are perfect, but the *world around the app* is missing — no real iOS status bar, no system keyboard, no share sheet, no permission dialog, no notification banner.

For marketing screenshots that need to *feel like a real phone*, that ceiling is fatal. A composed PNG with a synthetic 9:41 stamp and no keyboard is recognizably fake — it's the uncanny-valley of app marketing.

Phase 2 adds a second capture backend that runs the user's app inside a real iOS Simulator (or Android emulator) and screenshots the simulator's own framebuffer via `xcrun simctl io booted screenshot` / `adb exec-out screencap`. The result is pixel-identical to what the user would see on their own phone, including every native overlay.

The Phase 1 macOS backend stays. It's faster (~8s vs ~30–60s per shot), works in headless CI, and is plenty for users who only need framed mockups. Phase 2 is opt-in via `advanced.backend: ios_sim` (or `android_emu`).

## High-level data flow (new backend)

```
┌────────────────────────┐
│  User's Flutter app    │
│  (with shotgun_runner  │
│   + URL scheme reg'd)  │
└──────────┬─────────────┘
           │  shotgun.yaml
           ▼
┌─────────────────────────────────────────────────────────┐
│  shotgun_cli (Python)                                   │
│  ───────────────────                                    │
│  1. Read shotgun.yaml                                   │
│  2. Boot the right simulator (per device matrix entry)  │
│  3. Set locale + status bar overrides via simctl        │
│  4. `flutter run` the app onto the booted sim           │
│  5. For each scene:                                     │
│       a. `simctl openurl myapp://<route>`               │
│       b. wait `settle_ms`                               │
│       c. (optional) trigger native overlay              │
│       d. `simctl io booted screenshot raw.png`          │
│  6. Tear down simulator                                 │
│  7. Compose / collage via existing compose.py pipeline  │
└─────────────────────────────────────────────────────────┘
```

The big shift: shotgun is no longer a *test runner*. It's a *simulator orchestrator*. The Flutter app under capture is a normal release-mode app, not a `flutter_test` binary.

## Why deeplinks (not integration_test, not app-internal IPC)

We considered three routing strategies. Deeplinks won decisively:

| | integration_test on sim | App-internal control hook | URL deeplinks (chosen) |
|---|---|---|---|
| Captures system keyboard / share sheet | No — flutter_test owns the surface | Yes | **Yes** |
| User onboarding cost | ~Same as Phase 1 | High — IPC bootstrap + dart-define + maintain debug branch | Low — `Info.plist` URL scheme + one Flutter listener |
| Release-build safety | N/A (test build) | Risky — debug backdoor could ship to prod | Zero risk — standard OS feature |
| State precision | High | High | Moderate (needs settle delay) |
| Implementation complexity in shotgun | Reuses Phase 1 codegen | New IPC module (~300 LoC) | Thin wrapper around `simctl openurl` |

Deeplinks are how every real iOS app handles cold-state navigation already (email links, push notifications, marketing campaigns). Asking users to register one URL scheme is asking them to do something they probably should anyway.

The one tradeoff — settle time — is easily bounded. `pumpAndSettle`-equivalent in this world is `wait until first frame after navigation`, which we approximate with a configurable `settle_ms` (default 1200ms, override per scene).

## What the user has to do

To opt into the iOS-sim backend, the user adds three things to their app:

**1. URL scheme in `ios/Runner/Info.plist`:**

```xml
<key>CFBundleURLTypes</key>
<array>
  <dict>
    <key>CFBundleURLSchemes</key>
    <array><string>shotgun</string></array>
  </dict>
</array>
```

(Users who already have a deeplink scheme reuse theirs — shotgun reads the scheme name from yaml.)

**2. A Flutter deeplink listener** (one of: `go_router`, `auto_route`, manual `WidgetsBindingObserver`). If they have one, they're done. If not, they add one.

**3. Add the URL scheme to `android/app/src/main/AndroidManifest.xml`** (Android backend only):

```xml
<intent-filter>
  <action android:name="android.intent.action.VIEW" />
  <data android:scheme="shotgun" />
</intent-filter>
```

That's it. No SDK to integrate, no dart-define flags, no debug-only code paths.

## yaml schema additions

```yaml
advanced:
  backend: ios_sim       # default: macos_host (Phase 1, unchanged)
  scheme: shotgun        # URL scheme prefix used by simctl openurl
  settle_ms: 1200        # default settle wait after deeplink (override per scene below)
  boot_timeout_s: 90     # simulator boot ceiling

devices:
  ios:
    - name: "6.7"
      size: [1290, 2796]
      sim_runtime: "com.apple.CoreSimulator.SimRuntime.iOS-17-5"  # which Xcode runtime
      sim_device: "iPhone 15 Pro Max"                              # which device profile
  android:
    - name: phone
      size: [1080, 1920]
      emu_avd: "Pixel_7_API_34"   # AVD name from `avdmanager list`

scenes:
  - id: list
    route: /                       # already exists — used as the deeplink path
    settle_ms: 800                 # NEW: per-scene override
    pre_capture:                   # NEW: optional native triggers
      - { action: keyboard_show }  # focus first text field
      - { action: wait, ms: 400 }
    caption: { ko: "..." }
```

`pre_capture` is a small DSL for things deeplinks can't express:
- `keyboard_show` — taps the first visible `EditableText` so the system keyboard rises
- `share_sheet` — taps the share button (selector configured per scene)
- `notification` — posts a fake notification via `simctl push`
- `wait, ms: N` — explicit dwell

The DSL is deliberately tiny. Anything more complex should be a separate deeplink (e.g. `myapp://detail/1?focusSearch=true`) handled inside the app.

## Module layout

```
packages/shotgun_cli/src/shotgun_cli/
├── backends/                  ← NEW
│   ├── __init__.py
│   ├── base.py                # CaptureBackend ABC
│   ├── macos_host.py          # existing code, refactored into a backend
│   ├── ios_sim.py             # NEW
│   └── android_emu.py         # NEW (stretch — may slip to Phase 2.5)
├── capture.py                 # now a thin dispatcher → backends[name].run()
├── compose.py                 # unchanged
├── codegen.py                 # ONLY used by macos_host backend now
└── config.py                  # adds backend / scheme / sim_runtime fields
```

`CaptureBackend` ABC:

```python
class CaptureBackend(Protocol):
    name: str
    def prepare(self, config: ShotgunConfig, project_root: Path) -> None: ...
    def capture_one(self, entry: ShotMatrixEntry, out_path: Path) -> None: ...
    def teardown(self) -> None: ...
```

`ios_sim` backend internals:

```
prepare():
  resolve sim_device + sim_runtime → UDID via `xcrun simctl list -j`
  `simctl boot <udid>` if not already booted
  `simctl status_bar override` (time 9:41, full battery, full signal)
  `simctl spawn <udid> defaults write -g AppleLanguages '("<locale>")'`
  `flutter run -d <udid> --release` (background process, wait until first frame)

capture_one(entry):
  `simctl openurl <udid> <scheme>://<entry.scene.route_for_deeplink>`
  for action in entry.scene.pre_capture: dispatch
  sleep(entry.scene.settle_ms or config.advanced.settle_ms)
  `simctl io <udid> screenshot <out_path>`

teardown():
  kill flutter run process
  `simctl shutdown <udid>` (configurable: --keep-sim for fast re-runs)
```

## Status bar handling

In Phase 1 we *stamped* the status bar in Pillow after capture. With a real simulator, the status bar is real pixels. We use `simctl status_bar override` to make it deterministic:

```
xcrun simctl status_bar booted override \
  --time "9:41" --batteryState charged --batteryLevel 100 \
  --cellularBars 4 --wifiBars 3 --dataNetwork wifi
```

This runs once during `prepare()`. The stamping code in `compose.py` becomes a no-op for `ios_sim` backend (gated by config check).

## Locale switching

`flutter test` has a test binding that lets the macos_host backend force `tester.platformDispatcher.locales` per shot. `flutter run` (which ios_sim uses) doesn't — so locale has to be injected from outside the Dart VM.

**Chosen approach (PR-C.2): `--dart-define=SHOTGUN_LOCALE=<lang>` + app-side adapter.**

Shotgun ships `ShotgunLocale.fromEnv()` in `shotgun_runner`. User adds one line:

```dart
MaterialApp(
  locale: ShotgunLocale.fromEnv(),   // null when SHOTGUN_LOCALE unset
  ...
)
```

The ios_sim backend loops `for locale in config.locales: restart flutter run with SHOTGUN_LOCALE=<locale>`. Because `--dart-define` is a compile-time constant, hot-restart can't re-evaluate it — we have to terminate and re-spawn `flutter run`. The first build is ~30s; subsequent restarts are incremental (~10–15s) since the build cache survives.

**Why not system-level `AppleLanguages` override?** Considered: `simctl spawn <udid> defaults write -g AppleLanguages '("<locale>")'` followed by a sim reboot. Pros: zero user-app changes. Cons: ~45s reboot per locale (vs. ~10–15s incremental flutter rebuild). For the contract_analyzer reference (already wired for `flutter_localizations`), the one-line app change is the right tradeoff. Reserve system-level as a future opt-in when a user explicitly refuses to touch their app.

**Why not deeplink query param (`myapp://search?locale=ko`)?** Forces every deeplink listener in the user app to plumb locale through the routing layer. Far more invasive than a one-line `MaterialApp.locale` change.

**Loop ordering**: (device → locale → scene). Locale is outer-of-flutter-run because dart-define switching requires a process restart. Scene is innermost because deeplinks are cheap (~1s each). Reversing this would multiply the flutter-run restart cost by `len(scenes)`.

## Per-shot performance budget

Real-sim capture is fundamentally slower. We aim for:

- Cold boot (per simulator): ≤45s
- Per-shot after boot: ≤8s
  - `openurl` + settle: ~2s
  - `pre_capture` actions: ~1–3s
  - `simctl io screenshot`: ~1s
  - locale switch (if any): ~3–5s
- Teardown: ≤10s

For a 2 device × 2 locale × 3 scene matrix = 12 shots, expect ~4 min wall time. That's ~5× Phase 1, acceptable for the realism gain.

## CI strategy

- `macos_host` backend (Phase 1): keep as the CI smoke test. Fast, deterministic, runs on every commit.
- `ios_sim` backend: gated behind a manual workflow trigger or `[ios-sim]` commit-message tag. macOS-14 runners have Xcode + simulators pre-installed but boot time eats minutes. Don't run on every push.
- `android_emu` backend: similar, ubuntu-latest with hardware-acceleration enabled actions (`reactivecircus/android-emulator-runner`).

## Phasing

This is too big for a single PR. Split into four:

**PR-A — Backend abstraction (no behavior change) — ✅ DONE**
Extract Phase 1 `capture.py` logic into `backends/macos_host.py` behind the new ABC. Wire `advanced.backend: macos_host` as default. Existing examples pass unchanged.
- `backends/{__init__,base,macos_host}.py` created. `capture.py` is now a thin dispatcher.
- `advanced.backend` field added to `config.py` with `macos_host` default.
- `notes_app` 12/12 captures byte-identical to pre-refactor. `pytest packages/shotgun_cli` 32/32 green.

**PR-B — iOS simulator backend, minimum viable — ✅ DONE**
`backends/ios_sim.py` with: boot, status-bar override, single locale, deeplink routing, screenshot, teardown. No `pre_capture` DSL yet. `examples/contract_analyzer/` switched to it.
- `xcrun simctl bootstatus` for boot, `status_bar override` for clean 9:41, `openurl` for routing, `io screenshot` for capture.
- `--release`/`--profile` aren't supported in iOS simulators (no JIT-less runtime), so the backend uses plain `flutter run` (debug).
- iOS shows an "Open in <App>?" confirm dialog the first time a backgrounded app receives a deeplink in a session. The backend primes it once with the root route, dismisses via AppleScript Return keystroke, then runs the real capture loop. Subsequent `openurl` calls usually skip the dialog.
- `app_links` ^6.3.2 added to `contract_analyzer`. URL scheme registered in `ios/Runner/Info.plist`. `_DeeplinkRouter` widget wraps `MaterialApp` with a `navigatorKey` and listens via `AppLinks().uriLinkStream`.
- Result: real iPhone 17 Pro Max status bar (9:41, Dynamic Island, battery 100%), real SF Pro Korean text rendering, real iOS dPR (~3.0), no `_s` scale hack needed (the example detects dPR > 1.5 and skips scaling).

**PR-C.1 — `pre_capture` DSL (`keyboard_show` + `wait`) — ✅ DONE**
- `SceneConfig.pre_capture: list[dict]` with whitelist validator (`config.py`). Unknown actions rejected at load time.
- `IosSimBackend._dispatch_action()` handles `wait` (sleep `ms`) and `keyboard_show` (toggle software keyboard + dwell 0.6s for entrance anim).
- `keyboard_show` implementation surprise: `defaults write com.apple.iphonesimulator ConnectHardwareKeyboard -bool false` does *not* take effect on an already-running Simulator GUI session — the pref is read at app launch only. The reliable trigger is the `I/O → Keyboard → Toggle Software Keyboard` menu (Cmd-K), driven via AppleScript (`_toggle_software_keyboard()`). Falls back gracefully when osascript or accessibility permission is missing.
- `contract_analyzer` gained a `ContractSearchPage` (autofocus TextField + recent searches + keyword chips) and a `_DeeplinkRouter._handleUri` fix (`popUntil(isFirst)` + `addPostFrameCallback`) so deeplinks landing on a new route don't race the NavigatorState rebuild.
- Verified: `shotgun capture` on `examples/contract_analyzer/` produces 3 PNGs with system Korean keyboard visible on `03_search.png`, real 9:41 status bar, Dynamic Island. `compose` + `compose-grid` render ±5° rotated 3-phone collage under `dark_studio` preset. `pytest packages/shotgun_cli` 32/32 green.

**PR-C.2 — multi-locale — ✅ DONE**
- `ShotgunLocale.fromEnv()` helper in `shotgun_runner` reads `String.fromEnvironment('SHOTGUN_LOCALE')` and returns a `Locale?`. User wires it once into `MaterialApp.locale`. Returns `null` when unset → app falls back to system locale.
- `IosSimBackend._capture_one_device` now groups by locale internally and delegates each locale to `_capture_one_locale`, which restarts `flutter run` with `--dart-define=SHOTGUN_LOCALE=<lang>`. Status-bar override and hardware-keyboard restoration still happen exactly once per device.
- `_start_flutter_run` gained `extra_dart_defines: dict[str, str]`. Shotgun-managed keys take precedence over user-supplied collisions (otherwise the loop value gets silently shadowed and every shot renders the same locale).
- 6 new unit tests in `tests/test_ios_sim_backend.py` lock in the contract: one flutter-run per locale, every invocation carries `SHOTGUN_LOCALE=<lang>`, user dart_defines merge alongside, single-locale path still works. Mocks subprocess.Popen/run + screenshot writes; runs on any host without a real simulator.

**PR-C.3 — extra actions**
`share_sheet`, `notification`. Probably AppleScript click on share-sheet button selector, and `simctl push` for notifications.

**PR-D — Android emulator backend**
Mirrors `ios_sim` with `adb`, `emulator -avd`, `adb exec-out screencap`. Likely simpler since no status-bar override semantics.

Each PR ends with the same Definition of Done as Phase 1: full pipeline runs end-to-end against `examples/contract_analyzer`, produces a marketing-ready PNG, no regressions in `pytest packages/shotgun_cli`.

## Risks and unknowns

- **Simulator runtime version drift.** A user's Xcode might not have the runtime we hardcoded in yaml. Resolution: yaml accepts `sim_runtime: latest` as a default, shotgun picks the newest installed.
- **`flutter run --release` failures.** Some Flutter app structures (custom main, multi-entry) won't boot cleanly from CLI. Fallback: let the user provide their own boot command via `advanced.boot_command`.
- **Deeplink doesn't reach the listener if app cold-started by `openurl`.** Need to test — if true, prepare() must launch the app first with no URL, then `openurl` for each scene. (Most likely outcome.)
- **System keyboard varies by iOS version.** A screenshot with iOS 17 keyboard vs iOS 16 keyboard differs visually. Pin a default runtime in yaml; document this.
- **`simctl status_bar override` is per-simulator, persists across reboots.** We must reset on teardown to avoid polluting the user's other dev work.
- **Android: screencap on emulators with skin/frame includes the emulator chrome.** We capture into a temp file and crop. Compose pipeline reused.

## What stays the same

- `compose.py`, `compose-grid`, all presets (including `dark_studio`)
- `examples/contract_analyzer` UI code — only its `shotgun.yaml` changes to add `backend: ios_sim`
- `shotgun_runner` Dart package — unchanged (the deeplink listener is user-side)
- `codegen.py` — used only by `macos_host` backend, untouched

## What changes for `examples/contract_analyzer` specifically

To exercise the new backend:

1. Add URL scheme to `ios/Runner/Info.plist` (Flutter 3.x reads it via standard deeplink machinery)
2. Replace the `Navigator.pushNamed`-based routes with a `WidgetsBindingObserver.didChangeAppLifecycleState` + `PlatformDispatcher.instance.onPlatformBrightnessChanged` listener that maps `shotgun://list` → `/`, `shotgun://contract/1` → `/contract/1` (we'll likely just add `uni_links` as a dev_dependency to keep this short)
3. Update `shotgun.yaml`:
   ```yaml
   advanced:
     backend: ios_sim
     scheme: shotgun
   scenes:
     - id: list
       route: /            # deeplink becomes shotgun://
       caption: { ko: "..." }
   ```
4. Drop `lib/main.dart`'s `_s = 2.2` scale hack — the real simulator uses real text scaling.

The composed output should be visually indistinguishable from a screenshot the user took on their own iPhone, with `dark_studio` styling layered around it.
