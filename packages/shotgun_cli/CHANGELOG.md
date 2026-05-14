# Changelog

## 0.1.0 — 2026-05-15

First PyPI-ready cut. Two-package companion to `shotgun_runner` 0.1.0
on pub.dev. Phase 2 of the project is feature-complete: matrix
iteration, multi-locale, real iOS Simulator + Android emulator
backends, `pre_capture` action DSL, 5 compose presets, multi-phone
collage.

### Capture backends
- `macos_host` (Phase 1) — `flutter test -d macos` with
  `setSurfaceSize` overrides. Fast, headless, runs in CI.
- `ios_sim` (Phase 2) — real iOS Simulator via `xcrun simctl`. Real
  status bar override (`9:41`, Dynamic Island, 100% battery), system
  keyboard, share sheet. Single-AVD multi-locale via
  `--dart-define=SHOTGUN_LOCALE` + `ShotgunLocale.fromEnv()` adapter.
- `android_emu` (Phase 2) — real Android emulator via `adb` +
  `emulator -avd` + `am start` + SystemUI demo-mode broadcasts.

### `pre_capture` action DSL
- `wait { ms: ... }` — `time.sleep` between actions.
- `keyboard_show` (ios_sim) — toggle the simulator software keyboard.
- `keyboard_locale` (ios_sim) — cycle keyboard input source via globe key.
- `notification { bundle_id, payload }` (ios_sim) — APNs banner via
  `simctl push`.
- `share_sheet { target }` (ios_sim) — accessibility-name click to
  open the share sheet.

### Compose
- 5 presets: `vivid_gradient`, `minimal`, `feature_callout`, `studio`,
  `dark_studio`.
- Realistic phone frames bundled (CC0 PommePlate iPhone XS Max / 11 Pro
  Max / SE 2nd gen).
- `shotgun compose-grid` — 4-column multi-phone collage with fixed
  ±5° rotation and cast shadow.

### Quality
- 58 unit tests covering config validation, codegen, compose, status
  bar stamping, frame compositing, and three capture backends with
  subprocess mocking (no host SDK required).
- `shotgun capture --verbose` toggle + benign-line filter for
  uncluttered output.
- Failure summary on stderr (`+N -1 : <id> [E]` line + first framework
  error preamble) before the raw stack.

### Known limits
- `pre_capture` actions other than `wait` are no-ops on `android_emu`
  (they validate, but only `wait` is implemented). Other actions will
  land in a follow-up release.
- End-to-end Android capture has not yet been run against a real AVD
  on the development machine; the backend is covered by unit tests
  that lock cmd shape and multi-locale flow.
