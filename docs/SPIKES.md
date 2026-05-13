# Spikes log

A running log of small experiments validating shotgun's core assumptions before we commit to building them properly.

Each spike has a hypothesis, a result, and what we learned. When a spike pays off, its findings are folded back into [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Spike 1 — Headless capture at exact pixel size

**Date:** 2026-05-13
**Hypothesis:** We can render a Flutter app via `flutter test -d macos` and emit a PNG at an arbitrary store-required pixel size (1290×2796) without spinning up a simulator.

**Setup:** `examples/spike_counter` — Flutter's default counter app with `integration_test` added and one capture test.

**What worked:**
- `binding.setSurfaceSize(Size(1290, 2796))` + `tester.view.physicalSize = ...` + `tester.view.devicePixelRatio = 1.0`
- Wrapping `MyApp()` in a `RepaintBoundary` with a `GlobalKey` (NOT using `renderViewElement.renderObject` — that yields a `_ReusableRenderView`, not a `RenderRepaintBoundary`)
- `boundary.toImage(pixelRatio: 1.0)` → `toByteData(format: ui.ImageByteFormat.png)` → write to disk

**Result:** ✅ `PNG image data, 1290 x 2796, 8-bit/color RGBA, non-interlaced`, ~35 KB.

**Surprises:**
- macOS Flutter apps are sandboxed by default (`DebugProfile.entitlements` sets `app-sandbox: true`). Writing to a relative path lands in `~/Library/Containers/<bundle_id>/Data/`, **not** the project folder.
- A benign warning `Failed to foreground app; open returned 1` appears in the log but does not affect the result. Test still passes and the PNG is correct.

**Decisions folded into architecture:**
1. `shotgun_runner` must inject a `RepaintBoundary` around the user's root widget (or the user wires it explicitly via a helper).
2. `shotgun_runner` must patch `macos/Runner/DebugProfile.entitlements` to set `app-sandbox: false` for the duration of a capture run, then restore it.
3. The CLI passes the output path via the `SHOTGUN_OUT_DIR` environment variable as an absolute path. The Dart side reads `Platform.environment['SHOTGUN_OUT_DIR']` and writes there.

---

## Spike 2 — Multi-resolution matrix in one build

**Date:** 2026-05-13
**Hypothesis:** A single `flutter test` invocation can emit screenshots at multiple resolutions (iOS 6.7", 6.5", 5.5", Android phone) by looping `testWidgets` over a device list, sharing one build.

**Setup:** Same spike app. Capture test was extended to iterate over 4 devices, each calling `setSurfaceSize` to its target dimensions.

**Result:** ✅ All 4 PNGs produced at exact dimensions, total wall time **~11 seconds** (most of which is the macOS app build; per-test capture is sub-second).

```
ios/6.7/home.png       1290x2796
ios/6.5/home.png       1242x2688
ios/5.5/home.png       1242x2208
android/phone/home.png 1080x1920
```

**Why this matters:** Build cost is paid once per `flutter test` invocation. As the matrix grows (devices × locales × scenes), the marginal cost per shot is just the surface resize + pump + PNG encode. Back-of-envelope: a typical indie app with 5 scenes × 4 devices × 3 locales = 60 shots should complete in under a minute on a Mac.

**Decisions folded into architecture:**
1. Codegen should emit **one** integration_test file with N nested `testWidgets`, not N separate test files. One build, one process, N captures.
2. Per-locale captures: same idea — the test loop sets locale + mock data per iteration before pumping.
3. We do **not** need to parallelize `flutter test` invocations across cores for typical use. Single-process serial loop is already fast enough.

---

## Spike 3 — Python composition prototype

**Date:** 2026-05-13
**Hypothesis:** Pillow can take a raw screenshot PNG and produce a marketing-ready store image with vivid gradient background, device frame, and caption — in pure Python, no headless browser needed.

**Setup:** `spike/compose_spike.py`. Takes a raw screenshot, outputs a composited PNG at the same dimensions.

**Iterations:**

- **v1** — naive layout: caption clipped at edges, phone bled off canvas, no real bezel. *Worked* in the sense that pixels appeared, but unusable.
- **v2** — size-to-fit caption (binary search on font size), phone height-constrained to available space, side padding. Layout bugs gone.
- **v3** — vivid gradient + radial highlight, real-looking bezel + Dynamic-Island notch, soft drop shadow, caption stroke for legibility on busy bg. Phone looks like a phone.
- **v4** — stroke thinned (font.size / 80 instead of / 40). No more cartoon outline.

**Result:** ✅ Pillow alone produces a credibly marketing-grade composite. Per-image render time **~0.3 seconds**.

**Surprises:**
- Rendering the gradient at 1/4 resolution and upsampling is visually indistinguishable from full-res but ~16× faster. Pure-Python pixel loops at 1290×2796 are too slow without this trick.
- Caption stroke is a real readability win on vivid gradients — without it, white text washes out against the lighter portion of the gradient.
- The blank counter app screenshot exposes a fact: a single-content widget looks empty inside a phone frame. This is a **content** problem, not a composition problem — real apps with real screens will fill the space naturally.

**Decisions folded into architecture:**
1. `shotgun_cli` composition module structure: pure functions per layer (gradient, highlight, frame, notch, shadow, caption). Each preset is a recipe combining these layers.
2. Render-at-low-res-then-upscale is the right pattern for gradient/highlight masks. Document this for future preset contributors.
3. Caption stroke is on by default but should be a per-preset knob — `minimal` preset probably wants it off.
4. The phone bezel/notch is a stylized abstraction, **not** a real device frame PNG. Phase 1 ships with this. Phase 2 can add optional `frame_image: <png>` for users who want a true Apple/Pixel mockup overlay.

---

## Phase 1 entry — packages assembled

**Date:** 2026-05-13

With all three spikes green, the spike code was promoted into real packages:

- `packages/shotgun_runner/` — Dart package exposing `ShotgunCapture.framedApp(...)`, `.resizeFor(...)`, `.capture(...)`. The full integration test for `examples/counter_app` is now 18 lines (down from ~60 in the spike).
- `packages/shotgun_cli/` — Python package installable with `pip install -e .`. Exposes `shotgun init`, `shotgun compose`. Internally, `compose.py` is the spike's `compose_spike.py` reorganized into pure functions parameterized by `Preset` dataclasses.
- `examples/counter_app/` — the former `spike/` directory, now positioned as the canonical demo. End-to-end matrix capture + compose runs against it in ~12 seconds.

**Verified:** 4 device sizes × 1 scene round-trip cleanly. The 5.5" capture (shortest aspect ratio) lays out correctly, confirming the auto-fit logic for the phone vertical dimension works across device classes.

**Next milestones (Phase 1 finish line):**
1. ✅ `shotgun capture` subcommand that codegens an integration_test from a `shotgun.yaml` and runs `flutter test`.
2. ✅ `shotgun.yaml` parsing + Pydantic validation.
3. ⏳ Multi-scene support (config side is done; needs a fixture app with >1 route to truly exercise it).
4. ✅ macOS entitlements auto-patching (so users don't have to flip the `app-sandbox` key by hand).

---

## Phase 1 finish-line entry — full pipeline driven by `shotgun.yaml`

**Date:** 2026-05-13

The four finish-line pieces above are wired up. End-to-end run on `examples/counter_app/`:

```
$ shotgun capture                # 4 devices × 2 locales × 1 scene = 8 shots
$ shotgun compose                # → 8 store-ready PNGs at exact dimensions
```

**New modules in `shotgun_cli`:**
- `config.py` — Pydantic-validated `ShotgunConfig`. `iter_matrix()` expands `(device, locale, scene)` and applies `scenes[].only` filters.
- `codegen.py` — Jinja2 template renders `integration_test/_shotgun_generated.dart`. One `testWidgets` per matrix entry, wrapping the user's root widget in `Localizations` per-locale.
- `entitlements.py` — context manager that flips `com.apple.security.app-sandbox` to `<false/>` for the duration of `flutter test`, then restores the original entitlement in `finally`. No-op on non-macOS projects.
- `capture.py` — orchestrates codegen → entitlements patch → `flutter test -d macos` → cleanup.

**API addition in `shotgun_runner`:** `ShotgunCapture.capture()` now accepts optional `locale` and `fileName` params so codegen can lay out files as `<out>/<platform>/<device>/<locale>/<NN>_<sceneId>.png`.

**Surprises:**
- Dart does not auto-coerce `int` → `double`, so the template must emit `1290.0`, not `1290`. Caught only at `flutter test` build time, not at codegen time.
- The first `flutter test` in a fresh `build/` is ~2 min (macOS app build). Re-runs are ~1 sec — the matrix loop adds essentially nothing on top of the build.
- Entitlements patch/restore was verified by flipping the file to `<true/>` and re-running: capture still succeeded (proof the patch took effect mid-run), and the file came back as `<true/>` afterward.

**Decisions folded into architecture:**
1. `_shotgun_generated.dart` is treated as a build artifact — generated on every `shotgun capture`, deleted afterward unless `--keep-generated`. Users should `.gitignore` it.
2. `app.root_widget` is a required-feeling but defaulted (`MyApp`) field in `shotgun.yaml`. We don't try to auto-detect the root widget from the user's `main.dart`; an explicit name is simpler and survives refactors.
3. Each locale gets its own `Localizations` widget at the root of the captured tree. Apps that use `flutter_localizations` will need to pass their own delegates eventually — left as a Phase 2 hook.

---

## Phase 1.5 — second example, multi-scene, multi-locale

**Date:** 2026-05-13

`examples/notes_app/` was added as a richer second fixture: a 3-route notes app (home / detail / search) with Korean + English content. This is the first real exercise of the multi-scene code path — `counter_app` only had `/`.

**Matrix:** 2 devices × 2 locales × 3 scenes = **12 shots**, captured + composed in **~8 sec per pass** (after the first cold macOS build).

**Bugs that surfaced (all driven by hitting the matrix with a real app):**

1. **Locales weren't switching.** Wrapping the user's root in a `Localizations` widget did nothing — `MaterialApp` rebuilds its own `Localizations` from `PlatformDispatcher.locale`. Fix: new `ShotgunCapture.setLocale(tester, langCode)` writes `tester.platformDispatcher.locale[s]TestValue` before pumpWidget. Verified: en/ko raw PNGs now differ in size (different glyphs rendered).

2. **`MaterialLocalizations` missing for ko.** With locale=ko but no `localizationsDelegates` in `MaterialApp`, the framework throws on widgets that need `MaterialLocalizations` (e.g. `BackButton`). Fix is on the *user's* side, not shotgun: add `flutter_localizations` + `GlobalMaterialLocalizations.delegate`. notes_app demonstrates the correct setup; docs should call this out.

3. **Korean caption rendered as tofu boxes.** Pillow `_FONT_CANDIDATES` only listed Latin fonts. Fix: script-aware fallback. `_script_of(text)` detects Hangul / CJK / latin; `_KO_CANDIDATES` uses `AppleSDGothicNeo.ttc` (face index 4 ≈ Bold), `_CJK_CANDIDATES` uses Hiragino. Verified: 작은 디테일도 / 놓치지 마세요 now renders correctly.

**New shotgun_runner API:** `ShotgunCapture.setLocale(tester, languageCode)` + `ShotgunCapture.navigateTo(tester, routeName)`. The latter finds the root `Navigator` after pumpWidget and pushes the named route — that's how multi-scene works without the user wiring anything custom.

**Codegen change:** the generated test no longer wraps the user widget in `Localizations`. Instead it calls `setLocale` before `pumpWidget` and `navigateTo` after `pumpAndSettle`. The user's `MaterialApp` is the source of truth for routes + localizations.

**Decisions folded into architecture:**
1. `MaterialApp.routes` (or `onGenerateRoute`) is the assumed multi-scene mechanism. Apps using `go_router` / `auto_route` will need a Phase 2 hook to accept a programmatic navigation function — left for later.
2. Pillow font fallback ships with macOS paths only; Linux/CI builds need explicit Noto CJK paths in the candidate list. README should call this out.
3. We will *not* try to auto-add `flutter_localizations` to the user's pubspec. Multi-locale capture requires the user to set up localizations correctly — shotgun docs explain it.
