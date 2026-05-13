# shotgun_cli

Python CLI that orchestrates the screenshot pipeline.

Subcommands (planned):

- `shotgun init` — scaffold `shotgun.yaml` and a sample scene file
- `shotgun capture` — codegen integration_test, run `flutter test`, collect PNGs
- `shotgun compose` — apply preset (background, frame, caption) to raw PNGs
- `shotgun preset` — list / add / preview presets

Implementation comes in Phase 1. See [../../docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md).
