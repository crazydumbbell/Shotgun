import 'dart:async';
import 'dart:io';
import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';

/// Target device descriptor — used to size the rendered surface to match
/// a specific store listing requirement (e.g. App Store 6.7").
class ShotgunDevice {
  const ShotgunDevice({
    required this.platform,
    required this.name,
    required this.width,
    required this.height,
  });

  /// `"ios"` or `"android"`. Used in the output path: `<platform>/<name>/`.
  final String platform;

  /// Short name like `"6.7"` or `"phone"`. Used in the output path.
  final String name;

  /// Physical pixel width to render at.
  final double width;

  /// Physical pixel height to render at.
  final double height;

  Size get size => Size(width, height);
}

/// Signature for a pluggable router handler. shotgun invokes this for every
/// scene whose route is not `'/'`. Implementations should kick off
/// navigation to [route] and return — shotgun calls `pumpAndSettle()`
/// afterwards.
///
/// **Do not** `await navigator.pushNamed(route)` here: that future only
/// completes when the route is popped, so the handler would hang. Either
/// `unawaited(navigator.pushNamed(route))` it or use a fire-and-forget
/// router API like `GoRouter.of(context).go(route)`.
///
/// Register a handler via [ShotgunCapture.setRouterHandler] when your app
/// uses a declarative router (go_router, auto_route, beamer, etc.) — the
/// default implementation only knows how to drive `MaterialApp.routes` /
/// `onGenerateRoute` via the root [Navigator].
typedef ShotgunRouterHandler = Future<void> Function(
  WidgetTester tester,
  String route,
);

/// Capture helper used inside `testWidgets` callbacks.
///
/// Wrap your app in [framedApp] before pumping, then call [capture] after
/// `pumpAndSettle()`. The PNG lands under the directory pointed to by the
/// `SHOTGUN_OUT_DIR` environment variable (or `shotgun_output/` by default).
class ShotgunCapture {
  ShotgunCapture._();

  static final GlobalKey _captureKey = GlobalKey();
  static ShotgunRouterHandler? _routerHandler;

  /// Replace the default Navigator-based route handler.
  ///
  /// Call this from a setup hook that runs before the generated tests when
  /// the app uses a declarative router. shotgun will then dispatch every
  /// non-`/` route through your handler instead of trying `Navigator.pushNamed`.
  ///
  /// Example for `go_router`:
  ///
  /// ```dart
  /// // integration_test/_shotgun_setup.dart
  /// import 'package:flutter/widgets.dart';
  /// import 'package:go_router/go_router.dart';
  /// import 'package:shotgun_runner/shotgun_runner.dart';
  ///
  /// void registerShotgunRouter() {
  ///   ShotgunCapture.setRouterHandler((tester, route) async {
  ///     final element = tester.element(find.byType(MaterialApp));
  ///     GoRouter.of(element).go(route);
  ///   });
  /// }
  /// ```
  static void setRouterHandler(ShotgunRouterHandler? handler) {
    _routerHandler = handler;
  }

  /// Wrap [child] so the resulting subtree can be captured as a single image.
  ///
  /// Use this instead of pumping the bare app widget — without a
  /// [RepaintBoundary] under our control, we can't reliably grab the pixels.
  static Widget framedApp(Widget child) {
    return RepaintBoundary(key: _captureKey, child: child);
  }

  /// Navigate the pumped app to [routeName] and settle.
  ///
  /// Resolution order:
  /// 1. If a custom handler was registered via [setRouterHandler] (e.g. a
  ///    `go_router` adapter), delegate to it.
  /// 2. Otherwise drive the root [Navigator] with `pushNamed` — works for
  ///    apps using `MaterialApp.routes` or `onGenerateRoute`.
  ///
  /// Pass `'/'` to skip — that's the initial route, already laid out by
  /// the time you call this.
  static Future<void> navigateTo(WidgetTester tester, String routeName) async {
    if (routeName == '/') return;
    final handler = _routerHandler;
    if (handler != null) {
      await handler(tester, routeName);
      await tester.pumpAndSettle();
      return;
    }
    final navigatorFinder = find.byType(Navigator);
    if (navigatorFinder.evaluate().isEmpty) {
      // ignore: avoid_print
      print('[shotgun] no Navigator in tree; skipping route $routeName');
      return;
    }
    final navigator = tester.state<NavigatorState>(navigatorFinder.first);
    unawaited(navigator.pushNamed<void>(routeName));
    await tester.pumpAndSettle();
  }

  /// Resize the surface to [device]'s dimensions before the next pump.
  ///
  /// Call this *before* `pumpWidget` so the first frame is laid out at the
  /// target size. Also adjusts the `tester.view` so MediaQuery sees the
  /// correct device pixel ratio.
  static Future<void> resizeFor(
    WidgetTester tester,
    ShotgunDevice device,
  ) async {
    final binding = TestWidgetsFlutterBinding.instance;
    await binding.setSurfaceSize(device.size);
    tester.view.physicalSize = device.size;
    tester.view.devicePixelRatio = 1.0;
  }

  /// Force the test environment's reported locale to [languageCode].
  ///
  /// Most apps build their `MaterialApp` and let it resolve the system
  /// locale internally — wrapping their root in `Localizations(...)` does
  /// nothing because `MaterialApp` rebuilds its own `Localizations` from
  /// the `PlatformDispatcher` locales. This sets that source of truth.
  ///
  /// Call before `pumpWidget`.
  static void setLocale(WidgetTester tester, String languageCode) {
    tester.platformDispatcher.localesTestValue = [Locale(languageCode)];
    tester.platformDispatcher.localeTestValue = Locale(languageCode);
  }

  /// Capture the currently-pumped widget tree as a PNG.
  ///
  /// The output path is
  /// `<outDir>/<device.platform>/<device.name>[/<locale>]/<fileName>.png`,
  /// where `<outDir>` comes from the `SHOTGUN_OUT_DIR` environment variable
  /// (falling back to `shotgun_output/`).
  ///
  /// If [locale] is provided, it's inserted as a directory level between
  /// the device and the file. [fileName] defaults to [sceneId] but can be
  /// overridden when codegen needs to encode a scene index in the name.
  ///
  /// Must be called after at least one `pumpAndSettle()` so layout is stable.
  static Future<File> capture({
    required ShotgunDevice device,
    required String sceneId,
    String? locale,
    String? fileName,
  }) async {
    final ctx = _captureKey.currentContext;
    if (ctx == null) {
      throw StateError(
        'ShotgunCapture.capture() called before framedApp() was pumped. '
        'Wrap your root widget in ShotgunCapture.framedApp(...).',
      );
    }
    final boundary = ctx.findRenderObject()! as RenderRepaintBoundary;
    final ui.Image image = await boundary.toImage(pixelRatio: 1.0);
    final ByteData? byteData =
        await image.toByteData(format: ui.ImageByteFormat.png);
    if (byteData == null) {
      throw StateError('Failed to encode screenshot as PNG.');
    }
    final Uint8List bytes = byteData.buffer.asUint8List();

    final outRoot = Platform.environment['SHOTGUN_OUT_DIR'] ?? 'shotgun_output';
    final segments = <String>[outRoot, device.platform, device.name];
    if (locale != null) segments.add(locale);
    final outDir = Directory(segments.join('/'));
    if (!outDir.existsSync()) outDir.createSync(recursive: true);
    final name = fileName ?? sceneId;
    final file = File('${outDir.path}/$name.png');
    await file.writeAsBytes(bytes);

    final tag = locale != null
        ? '${device.platform}/${device.name}/$locale/$name'
        : '${device.platform}/${device.name}/$name';
    // ignore: avoid_print
    print('[shotgun] $tag  ${image.width}x${image.height}  ${bytes.length}B');
    return file;
  }
}
