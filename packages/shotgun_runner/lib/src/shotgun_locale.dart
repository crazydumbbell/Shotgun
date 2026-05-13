import 'package:flutter/widgets.dart';

/// Read the locale shotgun wants the app to render under, from the
/// `SHOTGUN_LOCALE` compile-time `--dart-define`.
///
/// The `ios_sim` backend can't reach into `tester.platformDispatcher` the way
/// the `macos_host` backend does (there is no test binding inside a real
/// `flutter run`). Instead, shotgun passes the desired locale via
/// `--dart-define=SHOTGUN_LOCALE=<lang>` and the user's `MaterialApp` reads
/// it to force `locale:` for that boot.
///
/// Returns `null` when `SHOTGUN_LOCALE` is unset (i.e. running normally, not
/// under shotgun) — pass that through to `MaterialApp.locale` and the app
/// falls back to its usual system-locale resolution.
///
/// Accepts the same forms `Locale.fromSubtags` understands:
///   - `"ko"`           → `Locale('ko')`
///   - `"ko_KR"`        → `Locale('ko', 'KR')`
///   - `"zh_Hant_HK"`   → `Locale.fromSubtags(languageCode: 'zh',
///                          scriptCode: 'Hant', countryCode: 'HK')`
///
/// Wire-up (one line in your app's `MaterialApp`):
///
/// ```dart
/// import 'package:shotgun_runner/shotgun_runner.dart';
///
/// MaterialApp(
///   locale: ShotgunLocale.fromEnv(),
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: const Home(),
/// )
/// ```
class ShotgunLocale {
  ShotgunLocale._();

  static const String _envKey = 'SHOTGUN_LOCALE';

  /// Compile-time value of `--dart-define=SHOTGUN_LOCALE`. Empty when unset.
  static const String _raw = String.fromEnvironment(_envKey);

  /// Return the shotgun-requested locale, or `null` when not running under
  /// shotgun.
  static Locale? fromEnv() {
    if (_raw.isEmpty) return null;
    return _parse(_raw);
  }

  /// `true` when the app is currently rendering for a shotgun capture.
  /// Useful for hiding analytics banners, debug overlays, etc.
  static bool get isActive => _raw.isNotEmpty;

  static Locale _parse(String raw) {
    final parts = raw.split('_');
    if (parts.length == 1) {
      return Locale(parts[0]);
    }
    if (parts.length == 2) {
      return Locale(parts[0], parts[1]);
    }
    // `zh_Hant_HK` form: language _ script _ region.
    return Locale.fromSubtags(
      languageCode: parts[0],
      scriptCode: parts[1],
      countryCode: parts[2],
    );
  }
}
