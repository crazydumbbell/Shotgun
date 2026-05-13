// Optional shotgun setup hook. Registered via `app.setup_file` in
// shotgun.yaml. Runs once before any shot.
//
// notes_app uses `MaterialApp.routes`, so the default Navigator-based
// route handler already works — this file exists mainly to exercise the
// hook plumbing and to demonstrate the pattern declarative-router apps
// (go_router, auto_route, etc.) would follow.

import 'dart:async';

import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shotgun_runner/shotgun_runner.dart';

void shotgunSetup() {
  // ignore: avoid_print
  print('[shotgun] setup hook invoked');
  ShotgunCapture.setRouterHandler((tester, route) async {
    // ignore: avoid_print
    print('[shotgun] router hook → $route');
    final navigatorFinder = find.byType(Navigator);
    final navigator = tester.state<NavigatorState>(navigatorFinder.first);
    // pushNamed completes only when the pushed route is popped, so kick
    // it off without awaiting and let pumpAndSettle drain the frame.
    unawaited(navigator.pushNamed<void>(route));
  });
}
