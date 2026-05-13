"""Codegen output checks. The Dart compiler is the source of truth, but
these tests catch broken templates / import paths before we ever invoke
flutter test."""

from __future__ import annotations

from pathlib import Path

import pytest

from shotgun_cli.codegen import render_integration_test
from shotgun_cli.config import ShotgunConfig


def _cfg(**overrides):
    data = {
        "devices": {"ios": [{"name": "6.7", "size": [1290, 2796]}]},
        "locales": ["en"],
        "scenes": [{"id": "home", "route": "/"}],
    }
    if "app" in overrides:
        data["app"] = overrides.pop("app")
    data.update(overrides)
    return ShotgunConfig.model_validate(data)


def test_no_setup_file_means_no_import_or_call(tmp_project: Path):
    out = render_integration_test(_cfg(), tmp_project)
    assert "shotgun_setup" not in out
    assert "_shotgun_setup.dart" not in out


def test_integration_test_setup_uses_relative_import(tmp_project: Path):
    cfg = _cfg(app={"setup_file": "integration_test/_shotgun_setup.dart"})
    out = render_integration_test(cfg, tmp_project)
    assert "import '_shotgun_setup.dart' as _shotgun_setup;" in out
    assert "_shotgun_setup.shotgunSetup();" in out


def test_lib_setup_uses_package_import(tmp_project: Path):
    cfg = _cfg(app={"setup_file": "lib/shotgun_setup.dart"})
    out = render_integration_test(cfg, tmp_project)
    assert (
        "import 'package:fake_app/shotgun_setup.dart' as _shotgun_setup;"
        in out
    )


def test_setup_file_outside_allowed_dirs_raises(tmp_project: Path):
    cfg = _cfg(app={"setup_file": "tools/setup.dart"})
    with pytest.raises(ValueError) as exc:
        render_integration_test(cfg, tmp_project)
    assert "integration_test/" in str(exc.value)


def test_setup_fn_override(tmp_project: Path):
    cfg = _cfg(app={
        "setup_file": "integration_test/_shotgun_setup.dart",
        "setup_fn": "myCustomSetup",
    })
    out = render_integration_test(cfg, tmp_project)
    assert "_shotgun_setup.myCustomSetup();" in out


def test_root_widget_import_override_respected(tmp_project: Path):
    cfg = _cfg(app={
        "entry": "lib/main.dart",
        "root_widget": "MyApp",
        "root_widget_import": "package:fake_app/app.dart",
    })
    out = render_integration_test(cfg, tmp_project)
    assert "import 'package:fake_app/app.dart';" in out
    # The default-derived import must NOT also appear.
    assert "import 'package:fake_app/main.dart';" not in out


def test_root_widget_not_declared_in_entry_raises(tmp_project: Path):
    # Simulate the export re-export case: main.dart only re-exports MyApp,
    # it does not declare it. Codegen should fail loudly pointing at
    # `root_widget_import`, not let Dart explode with "Couldn't find constructor".
    (tmp_project / "lib" / "main.dart").write_text(
        "export 'app.dart' show MyApp;\n", encoding="utf-8",
    )
    cfg = _cfg()
    with pytest.raises(ValueError) as exc:
        render_integration_test(cfg, tmp_project)
    msg = str(exc.value)
    assert "root_widget_import" in msg
    assert "MyApp" in msg


def test_root_widget_declared_directly_passes(tmp_project: Path):
    (tmp_project / "lib" / "main.dart").write_text(
        "import 'package:flutter/material.dart';\n"
        "class MyApp extends StatelessWidget {\n"
        "  const MyApp({super.key});\n"
        "  @override Widget build(BuildContext c) => const SizedBox();\n"
        "}\n",
        encoding="utf-8",
    )
    out = render_integration_test(_cfg(), tmp_project)
    assert "import 'package:fake_app/main.dart';" in out


def test_bootstrap_fn_emits_await_call(tmp_project: Path):
    cfg = _cfg(app={
        "setup_file": "integration_test/_shotgun_setup.dart",
        "bootstrap_fn": "shotgunBootstrap",
    })
    out = render_integration_test(cfg, tmp_project)
    # Bootstrap call must appear inside the testWidgets body, awaited,
    # before setLocale (so dotenv etc. are ready when the widget builds).
    assert "await _shotgun_setup.shotgunBootstrap();" in out
    bootstrap_idx = out.index("await _shotgun_setup.shotgunBootstrap();")
    setlocale_idx = out.index("ShotgunCapture.setLocale")
    assert bootstrap_idx < setlocale_idx


def test_bootstrap_fn_without_setup_file_rejected():
    with pytest.raises(Exception) as exc:
        ShotgunConfig.model_validate({
            "app": {"bootstrap_fn": "shotgunBootstrap"},
            "devices": {"ios": [{"name": "6.7", "size": [1290, 2796]}]},
            "locales": ["en"],
            "scenes": [{"id": "home", "route": "/"}],
        })
    assert "bootstrap_fn" in str(exc.value)
    assert "setup_file" in str(exc.value)


def test_routes_emitted_in_matrix_order(tmp_project: Path):
    cfg = _cfg(
        locales=["en", "ko"],
        scenes=[
            {"id": "home", "route": "/", "caption": {"en": "h", "ko": "h"}},
            {"id": "detail", "route": "/x", "caption": {"en": "d", "ko": "d"}},
        ],
    )
    out = render_integration_test(cfg, tmp_project)
    # 2 locales × 2 scenes × 1 device = 4 shots. Match the constructor
    # call inside the const list rather than the class definition.
    assert out.count("  _Shot(") == 4
    # Indices are 1-based and per-scene.
    assert "index: 1," in out
    assert "index: 2," in out
