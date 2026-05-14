"""ios_sim backend — multi-locale loop and dart-define injection.

`flutter run` and `xcrun simctl` are mocked so this test runs on any
host (no actual simulator needed). The goal is to lock in the contract
that PR-C.2 introduced:

  - `flutter run` is restarted per locale (not per scene, not per device).
  - Each restart carries `--dart-define=SHOTGUN_LOCALE=<lang>`.
  - User-supplied `dart_defines` are merged in alongside.
  - Status-bar override / hardware-keyboard restoration still happens
    exactly once per device, not per locale.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from shotgun_cli.backends.ios_sim import IosSimBackend
from shotgun_cli.config import ShotgunConfig


def _cfg(**overrides) -> ShotgunConfig:
    data = {
        "devices": {"ios": [{"name": "6.7", "size": [1290, 2796]}]},
        "locales": ["en", "ko"],
        "scenes": [
            {"id": "home", "route": "/"},
            {"id": "detail", "route": "/x"},
        ],
        "advanced": {"backend": "ios_sim"},
    }
    data.update(overrides)
    return ShotgunConfig.model_validate(data)


class _FakeFlutterProc:
    """Stand-in for `subprocess.Popen` returned by `_start_flutter_run`.

    Emits one ready-banner line and then EOF, so `_wait_for_first_frame`
    exits its loop on the first read. `poll()` returns `None` while
    "alive" so `_capture_one_locale`'s finally-block terminates it.
    """

    def __init__(self) -> None:
        self._lines = iter(["Flutter run key commands.\n", ""])
        self._alive = True
        self.terminated = False
        self.killed = False

    @property
    def stdout(self):
        return self

    def readline(self) -> str:
        try:
            return next(self._lines)
        except StopIteration:
            return ""

    def poll(self):
        return None if self._alive else 0

    def terminate(self) -> None:
        self.terminated = True
        self._alive = False

    def wait(self, timeout=None):
        return 0

    def kill(self) -> None:
        self.killed = True


@pytest.fixture
def patched_backend(monkeypatch, tmp_path: Path):
    """Patch every external call ios_sim makes: simctl, defaults,
    osascript, time.sleep, screenshot disk writes, and `flutter run`."""
    started: list[list[str]] = []
    simctl_calls: list[list[str]] = []
    screenshots: list[Path] = []

    runtimes_json = json.dumps({
        "runtimes": [{
            "identifier": "com.apple.CoreSimulator.SimRuntime.iOS-26-4",
            "version": "26.4",
            "isAvailable": True,
        }],
    })
    devicetypes_json = json.dumps({
        "devicetypes": [{
            "name": "iPhone 17 Pro Max",
            "identifier": "com.apple.CoreSimulator.SimDeviceType.iPhone-17-Pro-Max",
        }],
    })
    devices_json = json.dumps({"devices": {}})

    def fake_run(cmd, check=False, text=False, capture_output=False,
                 timeout=None):
        # Pillage the args list looking for the simctl subcommand.
        if cmd[0] == "xcrun" and cmd[1] == "simctl":
            simctl_calls.append(list(cmd))
            sub = cmd[2]
            stdout = ""
            if sub == "list" and cmd[3] == "runtimes":
                stdout = runtimes_json
            elif sub == "list" and cmd[3] == "devicetypes":
                stdout = devicetypes_json
            elif sub == "list" and cmd[3] == "devices":
                stdout = devices_json
            elif sub == "create":
                stdout = "FAKE-UDID-1234\n"
            return subprocess.CompletedProcess(
                cmd, 0, stdout=stdout, stderr=""
            )
        if cmd[0] == "defaults":
            return subprocess.CompletedProcess(cmd, 0, stdout=b"", stderr=b"")
        if cmd[0] == "osascript":
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    def fake_popen(cmd, **kwargs):
        # Only `flutter run` should reach Popen — the simctl wrapper uses
        # subprocess.run.
        started.append(list(cmd))
        return _FakeFlutterProc()

    def fake_screenshot(udid, out_path):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"\x89PNG\r\n\x1a\nfake")
        screenshots.append(out_path)

    monkeypatch.setattr("shotgun_cli.backends.ios_sim.subprocess.run", fake_run)
    monkeypatch.setattr(
        "shotgun_cli.backends.ios_sim.subprocess.Popen", fake_popen
    )
    monkeypatch.setattr(
        "shotgun_cli.backends.ios_sim._screenshot", fake_screenshot
    )
    # Don't actually sleep in unit tests.
    monkeypatch.setattr("shotgun_cli.backends.ios_sim.time.sleep", lambda *_: None)

    project_root = tmp_path / "fake_app"
    project_root.mkdir()
    (project_root / "pubspec.yaml").write_text("name: fake\n")

    return {
        "started": started,
        "simctl_calls": simctl_calls,
        "screenshots": screenshots,
        "project_root": project_root,
    }


def test_multi_locale_restarts_flutter_per_locale(patched_backend):
    """Two locales → two `flutter run` invocations, one boot."""
    cfg = _cfg()
    IosSimBackend().run(cfg, patched_backend["project_root"])

    flutter_invocations = [
        c for c in patched_backend["started"] if c[:2] == ["flutter", "run"]
    ]
    assert len(flutter_invocations) == 2, flutter_invocations

    # Each invocation should target the same booted UDID.
    udids = {c[c.index("-d") + 1] for c in flutter_invocations}
    assert udids == {"FAKE-UDID-1234"}

    # Boot happens once across the whole run, even for 2 locales.
    bootstatus_calls = [
        c for c in patched_backend["simctl_calls"]
        if len(c) >= 3 and c[2] == "bootstatus"
    ]
    assert len(bootstatus_calls) == 1


def test_each_flutter_run_carries_shotgun_locale_define(patched_backend):
    cfg = _cfg()
    IosSimBackend().run(cfg, patched_backend["project_root"])

    flutter_invocations = [
        c for c in patched_backend["started"] if c[:2] == ["flutter", "run"]
    ]
    seen_locales: set[str] = set()
    for cmd in flutter_invocations:
        # `--dart-define KEY=VALUE` pairs as separate argv tokens.
        defines = [
            cmd[i + 1] for i, tok in enumerate(cmd)
            if tok == "--dart-define"
        ]
        shotgun_defines = [
            d for d in defines if d.startswith("SHOTGUN_LOCALE=")
        ]
        assert len(shotgun_defines) == 1, (
            f"expected one SHOTGUN_LOCALE define per run, got {defines}"
        )
        seen_locales.add(shotgun_defines[0].split("=", 1)[1])
    assert seen_locales == {"en", "ko"}


def test_user_dart_defines_merge_with_shotgun_locale(patched_backend):
    cfg = _cfg(app={"dart_defines": {"API_BASE": "https://example.com"}})
    IosSimBackend().run(cfg, patched_backend["project_root"])

    flutter_invocations = [
        c for c in patched_backend["started"] if c[:2] == ["flutter", "run"]
    ]
    for cmd in flutter_invocations:
        defines = [
            cmd[i + 1] for i, tok in enumerate(cmd) if tok == "--dart-define"
        ]
        assert any(d == "API_BASE=https://example.com" for d in defines), (
            f"user dart_define dropped: {defines}"
        )
        assert any(d.startswith("SHOTGUN_LOCALE=") for d in defines), defines


def test_shotgun_locale_overrides_user_value_if_collision(patched_backend):
    """If a user shoves `SHOTGUN_LOCALE` into their own dart_defines, the
    per-locale loop value must win — otherwise the loop is silently a no-op."""
    cfg = _cfg(app={"dart_defines": {"SHOTGUN_LOCALE": "fr"}})
    IosSimBackend().run(cfg, patched_backend["project_root"])

    flutter_invocations = [
        c for c in patched_backend["started"] if c[:2] == ["flutter", "run"]
    ]
    for cmd in flutter_invocations:
        defines = [
            cmd[i + 1] for i, tok in enumerate(cmd) if tok == "--dart-define"
        ]
        shotgun_defines = [
            d for d in defines if d.startswith("SHOTGUN_LOCALE=")
        ]
        # Exactly one (the loop's) — `fr` from user config gets shadowed.
        assert len(shotgun_defines) == 1
        assert shotgun_defines[0].split("=", 1)[1] in {"en", "ko"}


def test_single_locale_still_works(patched_backend):
    """The PR-B happy path (single locale) must keep working post-PR-C.2 —
    one boot, one flutter run, SHOTGUN_LOCALE set to that one locale."""
    cfg = _cfg(locales=["en"])
    IosSimBackend().run(cfg, patched_backend["project_root"])

    flutter_invocations = [
        c for c in patched_backend["started"] if c[:2] == ["flutter", "run"]
    ]
    assert len(flutter_invocations) == 1
    cmd = flutter_invocations[0]
    defines = [cmd[i + 1] for i, tok in enumerate(cmd) if tok == "--dart-define"]
    assert "SHOTGUN_LOCALE=en" in defines


def test_screenshots_written_per_locale(patched_backend):
    cfg = _cfg()
    IosSimBackend().run(cfg, patched_backend["project_root"])

    # 1 device × 2 locales × 2 scenes = 4 screenshots.
    assert len(patched_backend["screenshots"]) == 4
    locales_in_paths = {p.parent.name for p in patched_backend["screenshots"]}
    assert locales_in_paths == {"en", "ko"}


# --- PR-C.3 _dispatch_action ----------------------------------------------

def test_dispatch_notification_calls_simctl_push(monkeypatch):
    """`notification` action must shell out to `simctl push <udid> <bundle>
    <payload-file>` and write the payload JSON to a temp file."""
    captured: dict[str, Any] = {}

    def fake_run(cmd, **kwargs):
        if cmd[:2] == ["xcrun", "simctl"] and cmd[2] == "push":
            captured["cmd"] = list(cmd)
            with open(cmd[5], encoding="utf-8") as fh:
                captured["payload"] = json.load(fh)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr("shotgun_cli.backends.ios_sim.subprocess.run", fake_run)
    monkeypatch.setattr("shotgun_cli.backends.ios_sim.time.sleep", lambda *_: None)

    IosSimBackend()._dispatch_action(
        {
            "action": "notification",
            "bundle_id": "com.example.app",
            "payload": {"aps": {"alert": "Hello"}},
        },
        udid="UDID-NOTIF",
    )

    assert captured["cmd"][:5] == [
        "xcrun", "simctl", "push", "UDID-NOTIF", "com.example.app",
    ]
    assert captured["payload"] == {"aps": {"alert": "Hello"}}
    # Temp file should have been deleted after the simctl call.
    assert not Path(captured["cmd"][5]).exists()


def test_dispatch_keyboard_locale_sends_globe_keystroke(monkeypatch):
    osascripts: list[str] = []

    def fake_run(cmd, **kwargs):
        if cmd[0] == "osascript":
            osascripts.append(cmd[2])
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr("shotgun_cli.backends.ios_sim.subprocess.run", fake_run)
    monkeypatch.setattr("shotgun_cli.backends.ios_sim.time.sleep", lambda *_: None)

    IosSimBackend()._dispatch_action(
        {"action": "keyboard_locale"}, udid="UDID-KB",
    )

    assert len(osascripts) == 1
    # The script must press space with control held (= globe key).
    assert "key code 49" in osascripts[0]
    assert "control down" in osascripts[0]


def test_dispatch_share_sheet_clicks_by_accessibility_name(monkeypatch):
    osascripts: list[str] = []

    def fake_run(cmd, **kwargs):
        if cmd[0] == "osascript":
            osascripts.append(cmd[2])
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr("shotgun_cli.backends.ios_sim.subprocess.run", fake_run)
    monkeypatch.setattr("shotgun_cli.backends.ios_sim.time.sleep", lambda *_: None)

    IosSimBackend()._dispatch_action(
        {"action": "share_sheet", "target": "Share contract"},
        udid="UDID-SHARE",
    )

    assert len(osascripts) == 1
    # AppleScript must embed the literal accessibility name.
    assert '"Share contract"' in osascripts[0]
    assert "click (first button whose name is" in osascripts[0]


def test_dispatch_share_sheet_escapes_quotes_in_target(monkeypatch):
    """Targets with embedded quotes must not break the AppleScript literal."""
    osascripts: list[str] = []

    def fake_run(cmd, **kwargs):
        if cmd[0] == "osascript":
            osascripts.append(cmd[2])
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr("shotgun_cli.backends.ios_sim.subprocess.run", fake_run)
    monkeypatch.setattr("shotgun_cli.backends.ios_sim.time.sleep", lambda *_: None)

    IosSimBackend()._dispatch_action(
        {"action": "share_sheet", "target": 'Open "settings"'},
        udid="UDID-SHARE-Q",
    )

    assert len(osascripts) == 1
    # The inner quotes around `settings` must be backslash-escaped so the
    # outer pair stays balanced.
    assert '\\"settings\\"' in osascripts[0]
