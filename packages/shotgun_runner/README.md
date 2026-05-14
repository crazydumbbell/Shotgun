# shotgun_runner

Dart side of [shotgun](https://github.com/crazydumbbell/Shotgun) — a tool
for producing App Store / Play Store screenshots of a Flutter app at
exact pixel dimensions, in every locale you ship.

This package lives inside your Flutter app and exposes the
`integration_test`-facing API that the `shotgun` Python CLI generates
code against.

## Install

```yaml
# pubspec.yaml
dependencies:
  shotgun_runner: ^0.1.0   # only need it under `dependencies` if you
                           # wire ShotgunLocale.fromEnv() into MaterialApp.locale.
                           # otherwise dev_dependencies is enough.

dev_dependencies:
  integration_test:
    sdk: flutter
```

Install the Python CLI separately:

```bash
pip install shotgun-cli      # (coming to PyPI)
# or, until then:
pip install "git+https://github.com/crazydumbbell/Shotgun#subdirectory=packages/shotgun_cli"
```

Then drop a `shotgun.yaml` at your project root and run `shotgun
capture`. The CLI generates `integration_test/_shotgun_generated.dart`
on the fly — most users never touch this package's API directly.

## Minimal usage (multi-locale)

If you want shotgun to render each shot under a different `Locale`
without reaching into the user app for every backend, add the one-line
adapter:

```dart
import 'package:flutter/material.dart';
import 'package:flutter/localizations.dart';
import 'package:shotgun_runner/shotgun_runner.dart';

MaterialApp(
  locale: ShotgunLocale.fromEnv(),   // null when SHOTGUN_LOCALE unset
  supportedLocales: const [Locale('en'), Locale('ko')],
  localizationsDelegates: const [
    GlobalMaterialLocalizations.delegate,
    GlobalWidgetsLocalizations.delegate,
    GlobalCupertinoLocalizations.delegate,
  ],
  home: const Home(),
);
```

`ShotgunLocale.fromEnv()` returns `null` when the app is running
normally, so your usual system-locale fallback keeps working.

## Declarative router (go_router, auto_route, beamer)

Register a `ShotgunRouterHandler` in a setup file that the CLI imports:

```dart
// integration_test/_shotgun_setup.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:shotgun_runner/shotgun_runner.dart';
import 'package:go_router/go_router.dart';
import 'package:my_app/router.dart';

void shotgunSetup() {
  ShotgunCapture.setRouterHandler((WidgetTester tester, String route) async {
    appRouter.go(route);
    await tester.pumpAndSettle();
  });
}
```

Then in `shotgun.yaml`:

```yaml
app:
  setup_file: integration_test/_shotgun_setup.dart
```

## Full docs

See the [top-level README](https://github.com/crazydumbbell/Shotgun) for
the matrix model (device × locale × scene), the three capture backends
(`macos_host` / `ios_sim` / `android_emu`), composition presets, and
end-to-end examples.
