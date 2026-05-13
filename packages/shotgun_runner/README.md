# shotgun_runner

Dart package that lives inside the user's Flutter app as a `dev_dependency`.

Responsible for:

- Hosting the `integration_test` driver
- Honoring `setSurfaceSize` from the CLI
- Injecting mock data into the app
- Capturing the rendered PNG and writing it to disk

Implementation comes in Phase 1. See [../../docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md).
