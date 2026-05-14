"""Android emulator backend.

Mirror of `ios_sim` for Android: boots a user-registered AVD with
`emulator -avd <name>`, runs the user's app on it with `flutter run`,
and captures the framebuffer via `adb exec-out screencap`. Drives
navigation with `am start -W -a VIEW -d <deeplink>`.

Two notable differences from `ios_sim`:

- AVDs are *not* created by shotgun. The user registers one in Android
  Studio (Tools → Device Manager → Create Device), then names it in
  `devices.android[].emu_avd`. Auto-create requires sdkmanager + system
  image downloads, which is too heavy a side-effect for a screenshot
  tool.
- Status-bar normalization uses SystemUI's "demo mode" broadcasts, not
  a dedicated simctl-style override. We enable demo mode, push a fixed
  clock/battery/wifi state, and disable it again on teardown.

Multi-locale uses the same `--dart-define=SHOTGUN_LOCALE` mechanism as
`ios_sim` (`flutter run` has no test binding either), so the loop shape
is identical: device (one boot) → locale (restart flutter run) → scene
(cheap deeplinks).

`pre_capture` actions: only `wait` is honored in this PR. The Android
analogues of `keyboard_show` / `keyboard_locale` / `share_sheet` need a
different toolchain (`adb shell ime`, `uiautomator dump`, etc.) and are
deferred to a later PR. Unknown actions are *not* rejected at runtime —
they're already rejected at config-load time by the shared whitelist.
Actions that exist but aren't implemented here are silently skipped
with a stderr note so a yaml shared between iOS and Android doesn't
fail outright on Android.

See `docs/PHASE2.md` for the design rationale.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from ..config import DeviceSpec, ShotgunConfig, ShotMatrixEntry
from .base import CaptureError


def _sdk_root() -> Path:
    """Resolve the Android SDK root. Honors `ANDROID_HOME` /
    `ANDROID_SDK_ROOT` env vars (the documented contract), falling back
    to the macOS default install path."""
    for var in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        val = os.environ.get(var)
        if val:
            return Path(val)
    return Path.home() / "Library" / "Android" / "sdk"


def _adb_bin() -> str:
    """Locate `adb`. Prefer the PATH copy (lets users override via
    asdf / brew installs); fall back to the SDK-bundled binary."""
    sdk_adb = _sdk_root() / "platform-tools" / "adb"
    if sdk_adb.exists():
        return str(sdk_adb)
    return "adb"


def _emulator_bin() -> str:
    sdk_emu = _sdk_root() / "emulator" / "emulator"
    if sdk_emu.exists():
        return str(sdk_emu)
    return "emulator"


def _run(
    cmd: list[str],
    *,
    check: bool = True,
    capture: bool = True,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    """Thin wrapper around `subprocess.run` with text=True. Mirrors the
    `ios_sim._run` helper so the two backends read alike."""
    try:
        proc = subprocess.run(
            cmd,
            check=False,
            text=True,
            capture_output=capture,
            timeout=timeout,
        )
    except FileNotFoundError as e:
        raise CaptureError(f"{cmd[0]} not found on PATH: {e}") from None
    except subprocess.TimeoutExpired as e:
        raise CaptureError(f"{' '.join(cmd)} timed out after {timeout}s") from e
    if check and proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-5:]
        raise CaptureError(
            f"{' '.join(cmd)} exited {proc.returncode}\n"
            + "\n".join(tail)
        )
    return proc


def _list_avds() -> list[str]:
    """Return the user's registered AVD names. Used for friendly error
    messages when `emu_avd` doesn't match anything."""
    try:
        proc = _run([_emulator_bin(), "-list-avds"], check=False)
    except CaptureError:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def _running_emulator_serial(adb: str) -> str | None:
    """First `emulator-<port>` serial currently visible to adb, or None.

    We re-attach to an already-booted emulator when we find one so that
    `shotgun capture` re-runs skip the ~30s emulator cold start. This
    mirrors `ios_sim`'s "leave the sim booted on teardown" stance.
    """
    proc = _run([adb, "devices"], check=False)
    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].startswith("emulator-") and parts[1] == "device":
            return parts[0]
    return None


def _wait_for_boot(adb: str, serial: str, timeout_s: int) -> None:
    """Block until `getprop sys.boot_completed` returns `1`. `adb
    wait-for-device` only waits for the daemon, not for SystemUI."""
    deadline = time.time() + timeout_s
    _run([adb, "-s", serial, "wait-for-device"], timeout=timeout_s)
    while time.time() < deadline:
        proc = _run(
            [adb, "-s", serial, "shell", "getprop", "sys.boot_completed"],
            check=False,
        )
        if proc.stdout.strip() == "1":
            return
        time.sleep(1.5)
    raise CaptureError(
        f"emulator {serial} did not finish booting within {timeout_s}s"
    )


def _enable_demo_mode(adb: str, serial: str, *, time_str: str) -> None:
    """Apply a clean SystemUI demo-mode status bar (`9:41`, 100%, 4-bar
    wifi). Requires `sysui_demo_allowed=1`; we set it ourselves.

    The colon in the time gets stripped because the SystemUI broadcast
    extra expects HHMM, not HH:MM.
    """
    hhmm = time_str.replace(":", "")
    _run([
        adb, "-s", serial, "shell", "settings", "put", "global",
        "sysui_demo_allowed", "1",
    ])
    # Switch demo mode on.
    _run([
        adb, "-s", serial, "shell", "am", "broadcast",
        "-a", "com.android.systemui.demo",
        "-e", "command", "enter",
    ])
    # Clock.
    _run([
        adb, "-s", serial, "shell", "am", "broadcast",
        "-a", "com.android.systemui.demo",
        "-e", "command", "clock",
        "-e", "hhmm", hhmm,
    ])
    # Battery — 100% and not charging (a charging glyph looks like a leak).
    _run([
        adb, "-s", serial, "shell", "am", "broadcast",
        "-a", "com.android.systemui.demo",
        "-e", "command", "battery",
        "-e", "level", "100",
        "-e", "plugged", "false",
    ])
    # Network — full bars, no cellular slot.
    _run([
        adb, "-s", serial, "shell", "am", "broadcast",
        "-a", "com.android.systemui.demo",
        "-e", "command", "network",
        "-e", "wifi", "show",
        "-e", "level", "4",
        "-e", "mobile", "hide",
    ])
    # Hide notifications icons so the bar matches the App Store look.
    _run([
        adb, "-s", serial, "shell", "am", "broadcast",
        "-a", "com.android.systemui.demo",
        "-e", "command", "notifications",
        "-e", "visible", "false",
    ])


def _disable_demo_mode(adb: str, serial: str) -> None:
    _run([
        adb, "-s", serial, "shell", "am", "broadcast",
        "-a", "com.android.systemui.demo",
        "-e", "command", "exit",
    ], check=False)


def _start_emulator(avd: str) -> subprocess.Popen[str]:
    """Boot an AVD in the background. `-no-snapshot-load` ensures a
    deterministic state per run; `-no-boot-anim` shaves a few seconds.

    We don't pass `-no-window` here: a visible emulator is what users
    expect on a workstation, and it costs nothing in our case (we don't
    drive UI through xdotool the way iOS uses AppleScript)."""
    cmd = [
        _emulator_bin(), "-avd", avd,
        "-no-snapshot-load",
        "-no-boot-anim",
    ]
    print(f"[shotgun] booting AVD: {' '.join(cmd)}", flush=True)
    return subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )


def _open_url(adb: str, serial: str, package: str, url: str) -> None:
    """`am start -W -a VIEW -d <url> <package>` is the canonical Android
    deeplink invocation. `-W` makes it block until the activity is in
    the foreground — Android equivalent of waiting for openurl to settle.

    Passing the package explicitly skips the disambiguator dialog when
    multiple apps claim the URL scheme; on a fresh AVD shotgun's app is
    usually the only handler anyway."""
    _run([
        adb, "-s", serial, "shell", "am", "start", "-W",
        "-a", "android.intent.action.VIEW",
        "-d", url,
        package,
    ])


def _screenshot(adb: str, serial: str, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # `adb exec-out screencap -p` streams the PNG to stdout (no temp
    # file on the device). The trailing newline-translation hazard that
    # `shell screencap` had on older builds is gone in exec-out mode.
    proc = subprocess.run(
        [adb, "-s", serial, "exec-out", "screencap", "-p"],
        check=False,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise CaptureError(
            f"adb screencap failed (exit {proc.returncode}): "
            f"{(proc.stderr or b'').decode('utf-8', 'replace')[:200]}"
        )
    out_path.write_bytes(proc.stdout)


def _deeplink_url(scheme: str, route: str) -> str:
    """Mirror `ios_sim._deeplink_url`. `<scheme>://<route>` with the
    leading slash stripped from the route."""
    path = route.lstrip("/")
    return f"{scheme}://{path}" if path else f"{scheme}://"


class AndroidEmuBackend:
    """Android emulator backend. Mirror of `IosSimBackend` with adb /
    emulator -avd / SystemUI demo-mode in place of simctl.

    Boots one emulator per device entry (one per AVD; we don't try to
    juggle multiple AVDs in parallel). Re-attaches to an already-running
    emulator-* serial if present, so re-runs of `shotgun capture` are
    fast.
    """

    name = "android_emu"

    def run(
        self,
        config: ShotgunConfig,
        project_root: Path,
        *,
        flutter_bin: str = "flutter",
        keep_generated: bool = False,
        verbose: bool = False,
    ) -> Path:
        if not config.devices.android:
            raise CaptureError(
                "android_emu backend needs at least one android device "
                "entry."
            )
        if config.devices.ios:
            print(
                "[shotgun] android_emu backend ignores ios devices in this run",
                file=sys.stderr, flush=True,
            )
        if not config.app.package_id:
            raise CaptureError(
                "android_emu backend requires app.package_id (e.g. "
                "'com.example.myapp') so `am start` can target the right "
                "app and bypass the disambiguator dialog."
            )

        project_root = project_root.resolve()
        out_root = (project_root / config.output.dir).resolve()
        out_root.mkdir(parents=True, exist_ok=True)

        entries = [e for e in config.iter_matrix() if e.platform == "android"]
        if not entries:
            return out_root

        by_device: dict[str, list[ShotMatrixEntry]] = {}
        for entry in entries:
            by_device.setdefault(entry.device.name, []).append(entry)

        for device_name, device_entries in by_device.items():
            device = device_entries[0].device
            self._capture_one_device(
                config, project_root, out_root, device, device_entries,
                flutter_bin=flutter_bin, verbose=verbose,
            )

        return out_root

    def _capture_one_device(
        self,
        config: ShotgunConfig,
        project_root: Path,
        out_root: Path,
        device: DeviceSpec,
        entries: list[ShotMatrixEntry],
        *,
        flutter_bin: str,
        verbose: bool,
    ) -> None:
        if not device.emu_avd:
            raise CaptureError(
                f"devices.android[name={device.name!r}] needs an "
                f"`emu_avd` field. Available AVDs: "
                f"{', '.join(_list_avds()) or '(none registered)'}. "
                "Register one in Android Studio → Device Manager."
            )
        avd = device.emu_avd
        if avd not in _list_avds():
            raise CaptureError(
                f"AVD {avd!r} not registered. Available: "
                f"{', '.join(_list_avds()) or '(none)'}"
            )

        adb = _adb_bin()
        # Re-attach to an already-running emulator if there is one. This
        # is mostly a developer-loop optimization — fresh AVDs cold-boot
        # in ~30s, but re-runs of `shotgun capture` skip that entirely.
        emu_proc: subprocess.Popen[str] | None = None
        serial = _running_emulator_serial(adb)
        if serial is None:
            emu_proc = _start_emulator(avd)
            _wait_for_boot(adb, "emulator-5554", config.advanced.boot_timeout_s)
            serial = "emulator-5554"

        # Group by locale inside the device — same rationale as ios_sim:
        # SHOTGUN_LOCALE is a compile-time dart-define so each locale
        # needs its own `flutter run` lifecycle. Outer scope = locale,
        # inner = scene (cheap am-start deeplinks).
        by_locale: dict[str, list[ShotMatrixEntry]] = {}
        for entry in entries:
            by_locale.setdefault(entry.locale, []).append(entry)

        try:
            _enable_demo_mode(
                adb, serial,
                time_str=config.advanced.status_bar.time,
            )
            for locale, locale_entries in by_locale.items():
                self._capture_one_locale(
                    config, project_root, out_root, adb, serial, locale,
                    locale_entries,
                    flutter_bin=flutter_bin, verbose=verbose,
                )
        finally:
            _disable_demo_mode(adb, serial)
            # Leave the emulator booted. `emu_proc.terminate()` would
            # save resources but cold boots are ~30s — the user can shut
            # it down via `adb emu kill` when they're done.
            if emu_proc is not None and verbose:
                print(
                    f"[shotgun] emulator {serial} left running "
                    f"(adb emu kill to stop)",
                    flush=True,
                )

    def _capture_one_locale(
        self,
        config: ShotgunConfig,
        project_root: Path,
        out_root: Path,
        adb: str,
        serial: str,
        locale: str,
        entries: list[ShotMatrixEntry],
        *,
        flutter_bin: str,
        verbose: bool,
    ) -> None:
        flutter_proc: subprocess.Popen[str] | None = None
        try:
            print(f"[shotgun] locale={locale}", flush=True)
            flutter_proc = self._start_flutter_run(
                project_root, serial, config,
                flutter_bin=flutter_bin, verbose=verbose,
                extra_dart_defines={"SHOTGUN_LOCALE": locale},
            )
            self._wait_for_first_frame(flutter_proc, verbose=verbose)

            scheme = config.advanced.scheme
            settle_default = config.advanced.settle_ms
            package = config.app.package_id  # validated upstream

            for entry in entries:
                url = _deeplink_url(scheme, entry.scene.route)
                _open_url(adb, serial, package, url)
                settle_ms = entry.scene.settle_ms or settle_default
                time.sleep(settle_ms / 1000)

                for action in entry.scene.pre_capture:
                    self._dispatch_action(action, adb, serial)

                out_path = entry.capture_path(out_root)
                _screenshot(adb, serial, out_path)
                size = out_path.stat().st_size
                print(
                    f"[shotgun] {entry.platform}/{entry.device.name}"
                    f"/{entry.locale}/{entry.index:02d}_{entry.scene.id} "
                    f"  {size}B",
                    flush=True,
                )
        finally:
            if flutter_proc is not None and flutter_proc.poll() is None:
                flutter_proc.terminate()
                try:
                    flutter_proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    flutter_proc.kill()

    def _dispatch_action(self, action: dict, adb: str, serial: str) -> None:
        """Run one `pre_capture` action on Android.

        Only `wait` is implemented in this PR. Other actions
        (`keyboard_show`, `keyboard_locale`, `notification`,
        `share_sheet`) are accepted at config-load time so a yaml shared
        between iOS and Android doesn't fail validation, but skipped at
        runtime with a stderr note. They need different toolchains
        (`adb shell ime`, `adb shell cmd notification post`, uiautomator
        button click) and land in a later PR.
        """
        kind = action.get("action")
        if kind == "wait":
            time.sleep(int(action["ms"]) / 1000)
            return
        print(
            f"[shotgun] android_emu: skipping {kind!r} action "
            f"(not implemented in this backend yet)",
            file=sys.stderr, flush=True,
        )

    def _start_flutter_run(
        self,
        project_root: Path,
        serial: str,
        config: ShotgunConfig,
        *,
        flutter_bin: str,
        verbose: bool,
        extra_dart_defines: dict[str, str] | None = None,
    ) -> subprocess.Popen[str]:
        """Launch `flutter run -d <emulator-serial>`.

        Unlike iOS, Android emulators *do* support `--release` and
        `--profile`, but debug mode keeps parity with `ios_sim` and
        avoids R8 minification surprises. The DartVM banner is still
        our ready signal.
        """
        if config.advanced.boot_command:
            cmd = config.advanced.boot_command.split()
        else:
            cmd = [flutter_bin, "run", "-d", serial]
            merged = {**config.app.dart_defines, **(extra_dart_defines or {})}
            for key, value in merged.items():
                cmd.extend(["--dart-define", f"{key}={value}"])
            if config.app.flavor:
                cmd.extend(["--flavor", config.app.flavor])
        print(f"[shotgun] launching app: {' '.join(cmd)}", flush=True)
        return subprocess.Popen(
            cmd,
            cwd=project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

    def _wait_for_first_frame(
        self,
        proc: subprocess.Popen[str],
        *,
        verbose: bool,
        timeout_s: int = 600,
    ) -> None:
        """Same banner-matching approach as `ios_sim._wait_for_first_frame`.

        `flutter run` prints either "A Dart VM Service is available" or
        "Flutter run key commands." once the app is interactive. Either
        is good enough to start firing deeplinks at it.
        """
        assert proc.stdout is not None
        deadline = time.time() + timeout_s
        ready_markers = (
            "Flutter run key commands.",
            "An Observatory debugger",
            "A Dart VM Service",
            "Syncing files to device",
            "to hot reload",
        )
        while time.time() < deadline:
            if proc.poll() is not None:
                raise CaptureError(
                    f"flutter run exited prematurely with code "
                    f"{proc.returncode}"
                )
            line = proc.stdout.readline()
            if not line:
                time.sleep(0.05)
                continue
            line = line.rstrip("\n")
            if verbose:
                print(f"[flutter] {line}", flush=True)
            if any(m in line for m in ready_markers):
                time.sleep(1.5)
                return
        raise CaptureError(
            f"flutter run did not reach a ready state within {timeout_s}s"
        )
