/// shotgun_runner — capture screenshots of a Flutter app at exact pixel
/// dimensions for App Store / Play Store listings.
///
/// Used inside an `integration_test/` file. The Python CLI generates that
/// file from `shotgun.yaml`; you can also write it by hand.
///
/// ## Declarative router support
///
/// The default route handler drives the root [Navigator] via `pushNamed`,
/// which only works for apps using `MaterialApp.routes` / `onGenerateRoute`.
/// If your app uses `go_router`, `auto_route`, or another declarative
/// router, register a [ShotgunRouterHandler] via
/// [ShotgunCapture.setRouterHandler] before the generated tests run.
///
/// See the doc on [ShotgunCapture.setRouterHandler] for a copy-pasteable
/// `go_router` snippet.
library;

export 'src/shotgun_capture.dart'
    show ShotgunCapture, ShotgunDevice, ShotgunRouterHandler;
export 'src/shotgun_locale.dart' show ShotgunLocale;
