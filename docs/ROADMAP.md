# Roadmap

The shotgun roadmap is split into three phases. Each phase ends with a usable, demoable artifact — no phase is "internal only."

The bias is toward **getting a single end-to-end happy path working first**, then widening. A pretty README with a working `counter_app` demo is worth more than 80% feature coverage with no demo.

---

## Phase 1 — End-to-end skeleton

**Goal:** A user can clone shotgun, run it against the bundled `examples/counter_app`, and get *one* composed screenshot out the other end. Internal milestone, not yet public.

**Scope:**

- [ ] `shotgun_runner` Dart package
  - [ ] `ShotgunRunner.bootstrap()` entrypoint
  - [ ] Screenshot capture via `integration_test` + `binding.takeScreenshot()`
  - [ ] `setSurfaceSize` for one fixed size (1290×2796, iPhone 6.7)
- [ ] `shotgun_cli` Python CLI
  - [ ] `shotgun init` — drops `shotgun.yaml` + sample scene file into cwd
  - [ ] `shotgun capture` — codegens integration_test, runs `flutter test -d macos`, collects PNGs
  - [ ] `shotgun compose` — applies `vivid_gradient` preset (gradient bg + frame + caption)
- [ ] `examples/counter_app` — minimal Flutter app with one wired scene
- [ ] One preset: `vivid_gradient`
- [ ] One device: iOS 6.7"
- [ ] One locale: English

**Done when:** `cd examples/counter_app && shotgun capture && shotgun compose` produces a single 1290×2796 PNG with a purple gradient, the counter screen framed inside an iPhone mockup, and a caption above.

---

## Phase 2 — Public-ready MVP

**Goal:** First public release. README has GIF demos. Indie devs can install and use it on their own apps.

**Scope:**

- [ ] Multi-device matrix (iOS 6.7 / 6.5 / 5.5 / iPad + Android phone / tablet)
- [ ] Multi-locale (any list of locale codes)
- [ ] Multi-scene with route navigation
- [ ] Per-scene captions and mock data
- [ ] Three more presets:
  - [ ] `minimal` (white bg, large caption, subtle shadow)
  - [ ] `feature_callout` (arrow + circled element + short caption)
  - [ ] `lifestyle` (hand/desk background composite — stretch goal)
- [ ] Status bar normalization (9:41, full battery)
- [ ] Config validation with helpful errors
- [ ] CI: every commit runs the full pipeline on `examples/counter_app` and uploads the output as a build artifact (this *is* the regression test)
- [ ] Pretty README with:
  - [ ] Animated GIF of `shotgun capture` running
  - [ ] Before/after comparison
  - [ ] Side-by-side preset gallery
  - [ ] Five-minute quickstart that actually works

**Done when:**
- Published to pub.dev (`shotgun_runner`) and PyPI (`shotgun-cli`)
- A second example app exists (`examples/notes_app` — list + detail + form)
- Three indie devs outside the project have used it on a real app and given feedback

---

## Phase 3 — Ecosystem

**Goal:** shotgun has enough surface area that the community can extend it without forking.

**Scope:**

- [ ] Plugin architecture for custom presets
- [ ] `presets/` becomes a directory of YAML files; users drop their own in
- [ ] `shotgun preset add <url>` to install community presets
- [ ] Dark mode / theme variant support per scene
- [ ] Pro-mode mock data (Dart-side hooks for complex state)
- [ ] fastlane integration (`shotgun deliver` thin wrapper)
- [ ] Optional: Web/desktop store assets (Microsoft Store, Mac App Store)
- [ ] Optional: animated previews (.mp4) — but only if a clear contributor steps up
- [ ] Contribution guide, code of conduct, issue templates
- [ ] Discord or GitHub Discussions

**Done when:**
- ≥3 community-contributed presets merged
- ≥1 external maintainer with merge rights
- 500+ GitHub stars (not a real metric, just a vibe check)

---

## Non-goals (forever, probably)

- **Native screenshot generation for non-Flutter apps** — scope creep
- **Store upload automation** — `fastlane` already does this, we wrap it at most
- **A SaaS product** — at least not from this repo. Keeping the open-source pure
- **Replacing designers** — shotgun makes "good enough" defaults reachable; a designer's bespoke layout will always be better

---

## How to influence this roadmap

Open an issue with the `roadmap` label. The bar for shifting things is "an indie dev who would use this *today* if it had X." Generic "would be nice to have Y" requests are deferred.
