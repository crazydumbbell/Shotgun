// Optional shotgun setup hook. Registered via `app.setup_file` in
// shotgun.yaml. contract_analyzer uses `MaterialApp.routes`, so the
// default Navigator-based route handler already works — this hook just
// makes navigation explicit and mirrors the notes_app pattern.

import 'dart:async';

import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shotgun_runner/shotgun_runner.dart';

void shotgunSetup() {
  ShotgunCapture.setRouterHandler((tester, route) async {
    final navigatorFinder = find.byType(Navigator);
    final navigator = tester.state<NavigatorState>(navigatorFinder.first);
    unawaited(navigator.pushNamed<void>(route));
  });
}
