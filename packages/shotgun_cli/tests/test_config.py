"""Schema-level validation: catches the most common config mistakes
before we burn a flutter test cycle on them."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from shotgun_cli.config import ShotgunConfig


def _base(**overrides):
    data = {
        "devices": {"ios": [{"name": "6.7", "size": [1290, 2796]}]},
        "locales": ["en"],
        "scenes": [{"id": "home", "route": "/"}],
    }
    data.update(overrides)
    return data


def test_minimal_config_loads():
    cfg = ShotgunConfig.model_validate(_base())
    assert cfg.scenes[0].id == "home"
    assert cfg.theme.preset == "vivid_gradient"


def test_unknown_preset_rejected():
    with pytest.raises(ValidationError) as exc:
        ShotgunConfig.model_validate(_base(theme={"preset": "neon_glow"}))
    assert "neon_glow" in str(exc.value)


def test_known_presets_accepted():
    for name in ("vivid_gradient", "minimal", "feature_callout"):
        cfg = ShotgunConfig.model_validate(_base(theme={"preset": name}))
        assert cfg.theme.preset == name


def test_caption_must_cover_every_locale():
    data = _base(locales=["en", "ko"], scenes=[{
        "id": "home", "route": "/",
        "caption": {"en": "hi"},
    }])
    with pytest.raises(ValidationError) as exc:
        ShotgunConfig.model_validate(data)
    assert "ko" in str(exc.value)


def test_matrix_expansion_and_only_filter():
    data = _base(
        devices={
            "ios": [{"name": "6.7", "size": [1290, 2796]}],
            "android": [{"name": "phone", "size": [1080, 1920]}],
        },
        locales=["en", "ko"],
        scenes=[
            {"id": "home", "route": "/"},
            {"id": "detail", "route": "/x",
             "only": {"devices": ["ios/6.7"]}},
        ],
    )
    cfg = ShotgunConfig.model_validate(data)
    entries = cfg.iter_matrix()
    # 2 devices × 2 locales × 1 universal scene = 4
    # + 2 locales × 1 ios-only scene             = 2
    assert len(entries) == 6
    assert {(e.platform, e.scene.id) for e in entries} == {
        ("ios", "home"), ("ios", "detail"),
        ("android", "home"),
    }


def test_status_bar_defaults_off():
    cfg = ShotgunConfig.model_validate(_base())
    assert cfg.advanced.status_bar.normalize is False
    assert cfg.advanced.status_bar.time == "9:41"


def test_setup_file_optional():
    cfg = ShotgunConfig.model_validate(_base())
    assert cfg.app.setup_file is None
    assert cfg.app.setup_fn == "shotgunSetup"


# --- pre_capture action validators (PR-C.3) ------------------------------

def _scene_with_action(action: dict):
    return _base(scenes=[{"id": "s", "route": "/", "pre_capture": [action]}])


def test_pre_capture_known_actions_accepted():
    for action in (
        {"action": "keyboard_show"},
        {"action": "wait", "ms": 400},
        {"action": "keyboard_locale"},
        {
            "action": "notification",
            "bundle_id": "com.example.app",
            "payload": {"aps": {"alert": "Hi"}},
        },
        {"action": "share_sheet", "target": "Share"},
    ):
        ShotgunConfig.model_validate(_scene_with_action(action))


def test_pre_capture_unknown_action_rejected():
    with pytest.raises(ValidationError) as exc:
        ShotgunConfig.model_validate(_scene_with_action({"action": "tap_xy"}))
    assert "tap_xy" in str(exc.value)


def test_notification_requires_bundle_id_and_payload():
    with pytest.raises(ValidationError) as exc:
        ShotgunConfig.model_validate(_scene_with_action(
            {"action": "notification", "payload": {"aps": {"alert": "x"}}}
        ))
    assert "bundle_id" in str(exc.value)


def test_notification_payload_must_be_mapping():
    with pytest.raises(ValidationError) as exc:
        ShotgunConfig.model_validate(_scene_with_action({
            "action": "notification",
            "bundle_id": "com.example.app",
            "payload": "{\"aps\": {}}",  # string, not a dict
        }))
    assert "payload" in str(exc.value)


def test_share_sheet_requires_string_target():
    with pytest.raises(ValidationError) as exc:
        ShotgunConfig.model_validate(_scene_with_action(
            {"action": "share_sheet"}
        ))
    assert "target" in str(exc.value)
