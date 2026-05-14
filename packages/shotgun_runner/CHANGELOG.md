# Changelog

## 0.1.0 — 2026-05-15

First publishable cut. Used in production by the `shotgun` CLI for App
Store and Play Store screenshot pipelines on real iOS Simulators and
Android emulators.

### Added
- `ShotgunCapture.framedApp` / `setLocale` / `resizeFor` /
  `navigateTo` / `capture` — the integration_test surface that the
  Python CLI generates code against.
- `ShotgunRouterHandler` + `ShotgunCapture.setRouterHandler` for
  declarative-router apps (`go_router`, `auto_route`, `beamer`).
- `ShotgunLocale.fromEnv()` — reads the `SHOTGUN_LOCALE`
  `--dart-define` injected by the `ios_sim` and `android_emu` backends
  so `MaterialApp(locale: ShotgunLocale.fromEnv())` honors the
  per-shot locale.

### Notes
- Public API surface is intentionally small. Add this as a regular
  `dependency` only when wiring `ShotgunLocale.fromEnv()` into
  `MaterialApp.locale`; otherwise `dev_dependency` is enough.
