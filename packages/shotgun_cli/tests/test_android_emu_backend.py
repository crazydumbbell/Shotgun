"""android_emu backend — multi-locale loop, deeplink shape, screencap path.

Like `test_ios_sim_backend.py`, all external tools (`adb`, `emulator`,
`flutter run`) are mocked so this runs on any host without an actual
Android SDK / AVD. The goal is to lock the contract that PR-D
introduced:

  - One `flutter run` per locale, restarted per locale (dart-define is a
    compile-time constant — same constraint as ios_sim).
  - Every flutter-run carries `--dart-define=SHOTGUN_LOCALE=<lang>`.
  - User dart_defines merge in alongside; shotgun-managed keys win
    collisions.
  - SystemUI demo-mode is enabled exactly once per device and disabled
    on teardown.
  - `am start` carries the package id + the right scheme://route URL.
  - `screencap` streams PNG bytes to disk per shot, partitioned by
    platform/device/locale.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from shotgun_cli.backends.android_emu import AndroidEmuBackend
from shotgun_cli.backends.base import CaptureError
from shotgun_cli.config import ShotgunConfig


def _cfg(**overrides) -> ShotgunConfig:
    data = {
        "devices": {"android": [{
            "name": "phone",
            "size": [1080, 2400],
            "emu_avd": "Pixel_9_API_36",
        }]},
        "locales": ["en", "ko"],
        "scenes": [
            {"id": "home", "route": "/"},
            {"id": "detail", "route": "/x"},
        ],
        "advanced": {"backend": "android_emu"},
        "app": {"package_id": "com.example.fake"},
    }
    data.update(overrides)
    return ShotgunConfig.model_validate(data)


class _FakeFlutterProc:
    """Same shape as the one in test_ios_sim_backend — emits a ready
    banner then EOF so `_wait_for_first_frame` exits immediately."""

    def __init__(self) -> None:
        self._lines = iter(["Flutter run key commands.\n", ""])
        self._alive = True

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
        self._alive = False

    def wait(self, timeout=None):
        return 0

    def kill(self) -> None:
        self._alive = False


@pytest.fixture
def patched_backend(monkeypatch, tmp_path: Path):
    started: list[list[str]] = []
    adb_calls: list[list[str]] = []
    screencap_writes: list[Path] = []

    def fake_run(cmd, check=False, text=False, capture_output=False, timeout=None):
        # `adb` and `emulator` both flow through this. `emulator
        # -list-avds` needs to return our fake AVD so the backend's
        # availability check passes.
        adb_calls.append(list(cmd))
        if "emulator" in cmd[0] and "-list-avds" in cmd:
            return subprocess.CompletedProcess(
                cmd, 0, stdout="Pixel_9_API_36\n", stderr="",
            )
        if cmd[0].endswith("adb") and "devices" in cmd:
            # Pretend an emulator is already booted so we skip the
            # _start_emulator + _wait_for_boot path. Those code paths
            # have their own coverage in test_android_emu_boot_path.
            return subprocess.CompletedProcess(
                cmd, 0,
                stdout="List of devices attached\nemulator-5554\tdevice\n",
                stderr="",
            )
        # All adb shell / am broadcast / am start invocations succeed
        # silently — the backend only inspects exit code.
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    def fake_popen(cmd, **kwargs):
        # Only `flutter run` is launched via Popen by android_emu in the
        # already-booted path. Capture the cmd shape and hand back the
        # fake proc.
        started.append(list(cmd))
        return _FakeFlutterProc()

    def fake_subprocess_run_bytes(cmd, check=False, capture_output=False):
        # `screencap` uses `subprocess.run(..., capture_output=True)` with
        # bytes (no text=True), distinct from `_run`. Hand back PNG-ish
        # bytes so the byte-size print is non-zero.
        if cmd[0].endswith("adb") and "screencap" in cmd:
            return subprocess.CompletedProcess(
                cmd, 0, stdout=b"\x89PNG\r\n\x1a\nfake", stderr=b"",
            )
        return subprocess.CompletedProcess(cmd, 0, stdout=b"", stderr=b"")

    def routing_run(cmd, **kwargs):
        # Distinguish the bytes-mode screencap call (capture_output=True
        # without text=True) from the text-mode helpers.
        if "screencap" in cmd:
            return fake_subprocess_run_bytes(cmd, **kwargs)
        return fake_run(cmd, **kwargs)

    monkeypatch.setattr(
        "shotgun_cli.backends.android_emu.subprocess.run", routing_run,
    )
    monkeypatch.setattr(
        "shotgun_cli.backends.android_emu.subprocess.Popen", fake_popen,
    )
    monkeypatch.setattr(
        "shotgun_cli.backends.android_emu.time.sleep", lambda *_: None,
    )

    project_root = tmp_path / "fake_app"
    project_root.mkdir()
    (project_root / "pubspec.yaml").write_text("name: fake\n")

    return {
        "started": started,
        "adb_calls": adb_calls,
        "screencap_writes": screencap_writes,
        "project_root": project_root,
    }


def _flutter_invocations(started):
    return [c for c in started if c[:2] == ["flutter", "run"]]


def test_multi_locale_restarts_flutter_per_locale(patched_backend):
    cfg = _cfg()
    AndroidEmuBackend().run(cfg, patched_backend["project_root"])

    invocations = _flutter_invocations(patched_backend["started"])
    assert len(invocations) == 2

    # Each invocation targets the same emulator serial.
    serials = {c[c.index("-d") + 1] for c in invocations}
    assert serials == {"emulator-5554"}


def test_each_flutter_run_carries_shotgun_locale(patched_backend):
    cfg = _cfg()
    AndroidEmuBackend().run(cfg, patched_backend["project_root"])

    seen: set[str] = set()
    for cmd in _flutter_invocations(patched_backend["started"]):
        defines = [
            cmd[i + 1] for i, tok in enumerate(cmd) if tok == "--dart-define"
        ]
        shotgun_defines = [d for d in defines if d.startswith("SHOTGUN_LOCALE=")]
        assert len(shotgun_defines) == 1
        seen.add(shotgun_defines[0].split("=", 1)[1])
    assert seen == {"en", "ko"}


def test_user_dart_defines_merge_with_shotgun_locale(patched_backend):
    cfg = _cfg(app={
        "package_id": "com.example.fake",
        "dart_defines": {"API_BASE": "https://example.com"},
    })
    AndroidEmuBackend().run(cfg, patched_backend["project_root"])

    for cmd in _flutter_invocations(patched_backend["started"]):
        defines = [
            cmd[i + 1] for i, tok in enumerate(cmd) if tok == "--dart-define"
        ]
        assert "API_BASE=https://example.com" in defines
        assert any(d.startswith("SHOTGUN_LOCALE=") for d in defines)


def test_shotgun_locale_overrides_user_collision(patched_backend):
    cfg = _cfg(app={
        "package_id": "com.example.fake",
        "dart_defines": {"SHOTGUN_LOCALE": "fr"},
    })
    AndroidEmuBackend().run(cfg, patched_backend["project_root"])

    for cmd in _flutter_invocations(patched_backend["started"]):
        defines = [
            cmd[i + 1] for i, tok in enumerate(cmd) if tok == "--dart-define"
        ]
        shotgun_defines = [d for d in defines if d.startswith("SHOTGUN_LOCALE=")]
        assert len(shotgun_defines) == 1
        assert shotgun_defines[0].split("=", 1)[1] in {"en", "ko"}


def test_am_start_carries_package_id_and_deeplink(patched_backend):
    cfg = _cfg()
    AndroidEmuBackend().run(cfg, patched_backend["project_root"])

    am_starts = [
        c for c in patched_backend["adb_calls"]
        if "am" in c and "start" in c
    ]
    # 2 locales × 2 scenes = 4 deeplink openings.
    assert len(am_starts) == 4

    for cmd in am_starts:
        assert "com.example.fake" in cmd
        # The URL follows `-d`.
        d_idx = cmd.index("-d")
        url = cmd[d_idx + 1]
        assert url.startswith("shotgun://")


def test_demo_mode_enabled_once_disabled_on_teardown(patched_backend):
    cfg = _cfg()
    AndroidEmuBackend().run(cfg, patched_backend["project_root"])

    demo_broadcasts = [
        c for c in patched_backend["adb_calls"]
        if "com.android.systemui.demo" in c
    ]
    enter_cmds = [c for c in demo_broadcasts
                  if "enter" in c and c[c.index("enter") - 1] == "command"]
    exit_cmds = [c for c in demo_broadcasts
                 if "exit" in c and c[c.index("exit") - 1] == "command"]
    # Demo mode is entered once per device (not per locale).
    assert len(enter_cmds) == 1
    assert len(exit_cmds) == 1


def test_missing_package_id_rejected():
    cfg = _cfg(app={})  # no package_id
    with pytest.raises(CaptureError) as exc:
        AndroidEmuBackend().run(cfg, Path("/tmp/nope"))
    assert "package_id" in str(exc.value)


def test_missing_avd_field_rejected(patched_backend):
    cfg = _cfg(devices={"android": [{
        "name": "phone", "size": [1080, 2400],
        # emu_avd intentionally omitted
    }]})
    with pytest.raises(CaptureError) as exc:
        AndroidEmuBackend().run(cfg, patched_backend["project_root"])
    assert "emu_avd" in str(exc.value)


def test_unknown_avd_rejected(monkeypatch, tmp_path: Path):
    """If the user types an AVD name that isn't registered, the backend
    must reject with a friendly list of available AVDs instead of
    blowing up later when `emulator -avd <typo>` fails."""

    def fake_run(cmd, **kwargs):
        if "emulator" in cmd[0] and "-list-avds" in cmd:
            return subprocess.CompletedProcess(
                cmd, 0, stdout="Pixel_9_API_36\n", stderr="",
            )
        if cmd[0].endswith("adb") and "devices" in cmd:
            # No emulator running.
            return subprocess.CompletedProcess(
                cmd, 0,
                stdout="List of devices attached\n",
                stderr="",
            )
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(
        "shotgun_cli.backends.android_emu.subprocess.run", fake_run,
    )

    project_root = tmp_path / "fake_app"
    project_root.mkdir()
    (project_root / "pubspec.yaml").write_text("name: fake\n")

    cfg = _cfg(devices={"android": [{
        "name": "phone", "size": [1080, 2400],
        "emu_avd": "Pixel_99_API_99",  # not registered
    }]})

    with pytest.raises(CaptureError) as exc:
        AndroidEmuBackend().run(cfg, project_root)
    assert "Pixel_99_API_99" in str(exc.value)
    assert "Pixel_9_API_36" in str(exc.value)


def test_unimplemented_action_is_skipped_not_raised(monkeypatch, capsys):
    """A yaml shared between ios_sim and android_emu may carry
    `keyboard_show` actions. Android can't honor them yet but must not
    blow up — the screenshot still happens, with a stderr note."""
    backend = AndroidEmuBackend()
    monkeypatch.setattr(
        "shotgun_cli.backends.android_emu.time.sleep", lambda *_: None,
    )

    # Should not raise.
    backend._dispatch_action(
        {"action": "keyboard_show"},
        adb="adb", serial="emulator-5554",
    )
    captured = capsys.readouterr()
    assert "keyboard_show" in captured.err
    assert "not implemented" in captured.err


def test_wait_action_honored(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr(
        "shotgun_cli.backends.android_emu.time.sleep",
        lambda s: sleeps.append(s),
    )
    AndroidEmuBackend()._dispatch_action(
        {"action": "wait", "ms": 750},
        adb="adb", serial="emulator-5554",
    )
    assert sleeps == [0.75]
