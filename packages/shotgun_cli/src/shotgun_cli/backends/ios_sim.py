"""iOS Simulator backend.

Boots a real iOS Simulator via `xcrun simctl`, runs the user's app on
it with `flutter run`, and screenshots the simulator's own framebuffer
per scene. Captures system chrome (status bar, keyboard, share sheet)
— the things the macOS-host backend physically can't see.

Multi-locale (PR-C.2): there is no test binding inside `flutter run`,
so `tester.platformDispatcher.locales` (the macos_host approach) is not
available. Instead we pass `--dart-define=SHOTGUN_LOCALE=<lang>` and the
user's `MaterialApp` reads it via `ShotgunLocale.fromEnv()`. Since
`--dart-define` is a compile-time constant, switching locales requires
restarting `flutter run`. Loop order: device (outer, one boot) → locale
(restart flutter run) → scene (cheap deeplinks).

See `docs/PHASE2.md` for the design rationale.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

from ..config import DeviceSpec, ShotgunConfig, ShotMatrixEntry
from .base import CaptureError


# Default device profile when `device.sim_device` is unset.
_DEFAULT_SIM_DEVICE = "iPhone 17 Pro Max"

# Tag for shotgun-created simulator instances. Lets us identify and
# reuse our own clones across runs without colliding with the user's
# hand-curated simulators in Xcode.
_SIM_NAME_PREFIX = "shotgun-"


def _run(
    cmd: list[str],
    *,
    check: bool = True,
    capture: bool = True,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    """Thin wrapper around `subprocess.run` with text=True and stderr
    folded into stdout when capturing. Raises CaptureError on non-zero
    exit when `check=True`."""
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


def _resolve_runtime(pinned: str | None) -> str:
    """Return a concrete iOS runtime identifier.

    `pinned` may be None (pick latest), `"latest"`, or a full identifier
    like `com.apple.CoreSimulator.SimRuntime.iOS-26-4`.
    """
    proc = _run(["xcrun", "simctl", "list", "runtimes", "-j"])
    runtimes = json.loads(proc.stdout)["runtimes"]
    ios = [
        r for r in runtimes
        if r.get("isAvailable", False)
        and r.get("identifier", "").startswith(
            "com.apple.CoreSimulator.SimRuntime.iOS-"
        )
    ]
    if not ios:
        raise CaptureError(
            "no installed iOS simulator runtimes — open Xcode and "
            "install one under Settings → Platforms."
        )
    if pinned and pinned != "latest":
        for r in ios:
            if r["identifier"] == pinned:
                return r["identifier"]
        raise CaptureError(
            f"sim_runtime {pinned!r} not installed. Available: "
            + ", ".join(r["identifier"] for r in ios)
        )
    # `version` like "26.4" — sort lexicographically by tuple of ints.
    def _ver(r: dict) -> tuple[int, ...]:
        return tuple(int(p) for p in re.findall(r"\d+", r.get("version", "0")))
    ios.sort(key=_ver, reverse=True)
    return ios[0]["identifier"]


def _resolve_devicetype(profile: str) -> str:
    """Map a human name like 'iPhone 17 Pro Max' to its
    `com.apple.CoreSimulator.SimDeviceType.*` identifier."""
    proc = _run(["xcrun", "simctl", "list", "devicetypes", "-j"])
    types = json.loads(proc.stdout)["devicetypes"]
    for t in types:
        if t["name"] == profile:
            return t["identifier"]
    raise CaptureError(
        f"sim_device {profile!r} not found. Run "
        "`xcrun simctl list devicetypes` to see valid names."
    )


def _create_sim(name: str, devicetype: str, runtime: str) -> str:
    """Create a fresh simulator instance, return its UDID."""
    proc = _run(["xcrun", "simctl", "create", name, devicetype, runtime])
    return proc.stdout.strip()


def _find_existing_sim(name: str) -> str | None:
    """Return UDID of an existing simulator with this exact name, or None."""
    proc = _run(["xcrun", "simctl", "list", "devices", "-j"])
    devices = json.loads(proc.stdout)["devices"]
    for runtime_devices in devices.values():
        for d in runtime_devices:
            if d.get("name") == name and d.get("isAvailable", False):
                return d["udid"]
    return None


def _boot_and_wait(udid: str, timeout_s: int) -> None:
    """Boot the simulator and wait until it reports Booted state."""
    _run(["xcrun", "simctl", "bootstatus", udid, "-b"], timeout=timeout_s, capture=False)


def _disable_hardware_keyboard() -> None:
    """Disconnect the simulator's hardware-keyboard pairing so that
    focused TextFields raise the *software* keyboard. Without this the
    sim defaults to forwarding host-Mac keystrokes and the on-screen
    keyboard never appears — which is exactly the system chrome the
    `keyboard_show` action exists to capture.

    `defaults write` updates the Simulator app's global preference;
    affects all subsequent boots. Restored to `true` on teardown so the
    user's normal dev workflow isn't disrupted.
    """
    subprocess.run(
        ["defaults", "write", "com.apple.iphonesimulator",
         "ConnectHardwareKeyboard", "-bool", "false"],
        check=False, capture_output=True,
    )


def _restore_hardware_keyboard() -> None:
    subprocess.run(
        ["defaults", "write", "com.apple.iphonesimulator",
         "ConnectHardwareKeyboard", "-bool", "true"],
        check=False, capture_output=True,
    )


def _set_status_bar(udid: str, *, time_str: str = "9:41") -> None:
    """Apply a clean App Store-style status bar override."""
    _run([
        "xcrun", "simctl", "status_bar", udid, "override",
        "--time", time_str,
        "--batteryState", "charged",
        "--batteryLevel", "100",
        "--cellularBars", "4",
        "--wifiBars", "3",
        "--dataNetwork", "wifi",
    ])


def _clear_status_bar(udid: str) -> None:
    _run(["xcrun", "simctl", "status_bar", udid, "clear"], check=False)


def _open_url(udid: str, url: str) -> None:
    _run(["xcrun", "simctl", "openurl", udid, url])


def _dismiss_open_dialog() -> None:
    """Dismiss iOS's "Open in <App>?" confirmation that springs up when a
    simulator receives an `openurl` for a scheme owned by an already-
    running app. simctl provides no flag to suppress it, so we send a
    Return keystroke to the active Simulator window via AppleScript —
    Return activates the highlighted "Open" button.

    Best-effort: if osascript or accessibility permission is missing,
    we swallow the error and let the screenshot include the dialog
    (still useful for debugging).
    """
    script = (
        'tell application "Simulator" to activate\n'
        'delay 0.3\n'
        'tell application "System Events" to keystroke return'
    )
    try:
        subprocess.run(
            ["osascript", "-e", script],
            check=False, capture_output=True, text=True, timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass


def _toggle_software_keyboard() -> None:
    """Click "I/O → Keyboard → Toggle Software Keyboard" in the
    Simulator app menu (Cmd-K). This is the only reliable way to force
    the on-screen keyboard up when a TextField is focused — the
    `defaults write ConnectHardwareKeyboard false` route silently
    no-ops on already-running GUI sessions.

    Best-effort: if osascript is missing or accessibility permission
    isn't granted, swallow the error. The screenshot will be missing
    the keyboard but the rest of the scene is still useful.
    """
    script = (
        'tell application "Simulator" to activate\n'
        'delay 0.2\n'
        'tell application "System Events"\n'
        '  tell process "Simulator"\n'
        '    click menu item "Toggle Software Keyboard" of menu "Keyboard" '
        'of menu item "Keyboard" of menu "I/O" of menu bar 1\n'
        '  end tell\n'
        'end tell'
    )
    try:
        subprocess.run(
            ["osascript", "-e", script],
            check=False, capture_output=True, text=True, timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass


def _screenshot(udid: str, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _run([
        "xcrun", "simctl", "io", udid, "screenshot",
        "--type=png", str(out_path),
    ])


def _shutdown(udid: str) -> None:
    _run(["xcrun", "simctl", "shutdown", udid], check=False)


def _deeplink_url(scheme: str, route: str) -> str:
    """Build a `<scheme>://<route>` URL.

    Routes start with `/` in shotgun.yaml (Flutter convention). For the
    deeplink, we strip the leading slash so `myapp:///contract/1` doesn't
    have a stray empty host segment. iOS treats either as equivalent, but
    the stripped form is what most Flutter deeplink listeners actually
    see in `Uri.host`.
    """
    path = route.lstrip("/")
    return f"{scheme}://{path}" if path else f"{scheme}://"


class IosSimBackend:
    """iOS Simulator backend. PR-B MVP: single locale, deeplink routing,
    real status bar override, no pre_capture DSL.

    Boots a dedicated shotgun-tagged simulator instance per device entry
    (one boot serves all scenes for that device). Reuses existing
    shotgun-tagged sims if found — keeps `shotgun capture` re-runs fast.
    """

    name = "ios_sim"

    def run(
        self,
        config: ShotgunConfig,
        project_root: Path,
        *,
        flutter_bin: str = "flutter",
        keep_generated: bool = False,
        verbose: bool = False,
    ) -> Path:
        if not config.devices.ios:
            raise CaptureError(
                "ios_sim backend needs at least one ios device entry."
            )
        if config.devices.android:
            print(
                "[shotgun] ios_sim backend ignores android devices in this run",
                file=sys.stderr, flush=True,
            )

        project_root = project_root.resolve()
        out_root = (project_root / config.output.dir).resolve()
        out_root.mkdir(parents=True, exist_ok=True)

        entries = [e for e in config.iter_matrix() if e.platform == "ios"]
        if not entries:
            return out_root

        # Group entries by device (one sim boot serves all scenes for that device).
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
        profile = device.sim_device or _DEFAULT_SIM_DEVICE
        runtime = _resolve_runtime(device.sim_runtime)
        devicetype = _resolve_devicetype(profile)
        sim_name = f"{_SIM_NAME_PREFIX}{profile.replace(' ', '_')}"

        udid = _find_existing_sim(sim_name) or _create_sim(
            sim_name, devicetype, runtime
        )
        # Disable hardware-keyboard forwarding before boot so the very
        # first focused TextField raises the software keyboard. Setting
        # this after boot doesn't take effect until the sim restarts.
        _disable_hardware_keyboard()
        print(f"[shotgun] booting {profile} ({udid[:8]}...)", flush=True)
        _boot_and_wait(udid, config.advanced.boot_timeout_s)

        # Group entries by locale within this device. SHOTGUN_LOCALE is a
        # compile-time `--dart-define`, so switching locales requires
        # restarting `flutter run`. Putting locale on the outer loop keeps
        # the restart count minimal (== number of locales) and lets each
        # restart serve every scene for that locale via cheap deeplinks.
        by_locale: dict[str, list[ShotMatrixEntry]] = {}
        for entry in entries:
            by_locale.setdefault(entry.locale, []).append(entry)

        try:
            _set_status_bar(udid, time_str=config.advanced.status_bar.time)
            for locale, locale_entries in by_locale.items():
                self._capture_one_locale(
                    config, project_root, out_root, udid, locale,
                    locale_entries,
                    flutter_bin=flutter_bin, verbose=verbose,
                )
        finally:
            _clear_status_bar(udid)
            _restore_hardware_keyboard()
            # Leave the sim booted — re-running shotgun is much faster
            # when the next `bootstatus` is a no-op. Users who want a
            # clean tear-down can `xcrun simctl shutdown all`.

    def _capture_one_locale(
        self,
        config: ShotgunConfig,
        project_root: Path,
        out_root: Path,
        udid: str,
        locale: str,
        entries: list[ShotMatrixEntry],
        *,
        flutter_bin: str,
        verbose: bool,
    ) -> None:
        """One `flutter run` lifecycle for a single (device, locale) pair."""
        flutter_proc: subprocess.Popen[str] | None = None
        try:
            print(f"[shotgun] locale={locale}", flush=True)
            flutter_proc = self._start_flutter_run(
                project_root, udid, config,
                flutter_bin=flutter_bin, verbose=verbose,
                extra_dart_defines={"SHOTGUN_LOCALE": locale},
            )
            self._wait_for_first_frame(flutter_proc, verbose=verbose)

            scheme = config.advanced.scheme
            settle_default = config.advanced.settle_ms

            # iOS shows an "Open in <App>?" confirm the first time a
            # backgrounded app receives a deeplink in a session. Prime it
            # once with the root route so the dialog appears, get
            # dismissed, and is out of the way before the real capture
            # loop starts.
            _open_url(udid, _deeplink_url(scheme, "/"))
            time.sleep(0.8)
            _dismiss_open_dialog()
            time.sleep(1.5)

            for entry in entries:
                url = _deeplink_url(scheme, entry.scene.route)
                _open_url(udid, url)
                # Dialog was already primed during the warmup openurl
                # above. Sending Return again here risks activating a
                # button in the actual app (search-keyboard return, list
                # tap, etc.) — so we just wait.
                settle_ms = entry.scene.settle_ms or settle_default
                time.sleep(settle_ms / 1000)

                for action in entry.scene.pre_capture:
                    self._dispatch_action(action)

                out_path = entry.capture_path(out_root)
                _screenshot(udid, out_path)
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

    def _dispatch_action(self, action: dict) -> None:
        """Run one `scenes[*].pre_capture` action.

        Keep this small and predictable: each action should be a thin
        wrapper around a simctl / AppleScript call with no app-side
        coordination. App-side state (which TextField has focus, what
        the share-sheet selector is) belongs in the user's app code,
        triggered by the deeplink itself.
        """
        kind = action.get("action")
        if kind == "wait":
            time.sleep(int(action["ms"]) / 1000)
        elif kind == "keyboard_show":
            # `defaults write ConnectHardwareKeyboard false` is supposed
            # to make a focused TextField raise the software keyboard,
            # but in practice the Simulator GUI ignores the pref on
            # already-running sessions. The reliable trigger is the
            # "I/O → Keyboard → Toggle Software Keyboard" menu (Cmd-K).
            # We send the menu click via AppleScript. Best-effort: if
            # accessibility permission is missing we just dwell.
            _toggle_software_keyboard()
            time.sleep(0.6)
        # Validation in config.py guarantees no other kinds reach here.

    def _start_flutter_run(
        self,
        project_root: Path,
        udid: str,
        config: ShotgunConfig,
        *,
        flutter_bin: str,
        verbose: bool,
        extra_dart_defines: dict[str, str] | None = None,
    ) -> subprocess.Popen[str]:
        """Launch `flutter run` as a background process on the booted sim.

        `extra_dart_defines` are merged into `config.app.dart_defines` for
        this invocation only. Shotgun-managed keys (`SHOTGUN_LOCALE`) take
        precedence over user-supplied ones with the same name — if the
        user already sets `SHOTGUN_LOCALE` in their yaml, the multi-locale
        loop's value is what actually drives rendering.
        """
        if config.advanced.boot_command:
            cmd = config.advanced.boot_command.split()
        else:
            # iOS simulators don't accept --release or --profile (no JIT
            # support in the Simulator runtime), so we run in debug mode.
            # The DartVM service banner doubles as our ready signal.
            cmd = [flutter_bin, "run", "-d", udid]
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
        """Block until `flutter run` prints its "Flutter run key commands"
        banner — the proxy for "first frame rendered, app is interactive."
        """
        assert proc.stdout is not None
        deadline = time.time() + timeout_s
        ready_markers = (
            "Flutter run key commands.",        # debug / profile
            "An Observatory debugger",          # legacy
            "A Dart VM Service",                # release-debug bridge
            "Syncing files to device",          # newer flutter versions
            "to hot reload",                    # newer flutter versions
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
                # Drain a bit more so subsequent reads don't block, then
                # consider the app ready.
                time.sleep(1.5)
                return
        raise CaptureError(
            f"flutter run did not reach a ready state within {timeout_s}s"
        )
