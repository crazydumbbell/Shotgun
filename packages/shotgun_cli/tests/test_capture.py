"""Capture-side log filtering and failure-summary checks. We don't run
flutter test here — we exercise the pure-Python helpers directly with
synthetic log lines."""

from __future__ import annotations

from shotgun_cli.capture import (
    _BENIGN_LINE_SUBSTRINGS,
    _FailureContext,
    _format_failure_summary,
    _is_benign,
)


def test_benign_substrings_match_known_noise():
    assert _is_benign("flutter: Failed to foreground app; open returned 1")
    assert _is_benign("warning: 'scanHexInt32' is deprecated")
    assert _is_benign("note: Function declarations must include a prototype")


def test_benign_does_not_swallow_real_errors():
    assert not _is_benign(
        "Couldn't find constructor 'MyApp'."
    )
    assert not _is_benign(
        "═══════ EXCEPTION CAUGHT BY WIDGETS LIBRARY ═══════"
    )


def test_failure_summary_includes_shot_id_and_cause():
    ctx = _FailureContext(
        shot_id="ios/6.7/en/home",
        error_lines=[
            "",
            "═══════ EXCEPTION CAUGHT BY WIDGETS LIBRARY ═══════",
            "The following NotInitializedError was thrown building MyHome:",
            "NotInitializedError",
            "#0      DotEnv.env (package:flutter_dotenv/...)",
            "#1      MyHome.build (package:my_app/home.dart:42:5)",
        ],
    )
    summary = _format_failure_summary(ctx)
    assert summary is not None
    assert "ios/6.7/en/home" in summary
    # Picks the framework error preamble, not the raw stack frame.
    assert "EXCEPTION CAUGHT" in summary or "NotInitializedError" in summary


def test_failure_summary_returns_none_when_no_context():
    assert _format_failure_summary(_FailureContext()) is None


def test_failure_summary_trims_long_cause():
    ctx = _FailureContext(
        shot_id="ios/6.7/en/home",
        error_lines=["FlutterError: " + ("x" * 500)],
    )
    summary = _format_failure_summary(ctx)
    assert summary is not None
    assert summary.endswith("...")
    assert len(summary) < 320  # one line, with margin for prefix


def test_benign_list_nonempty():
    # Sanity: someone shouldn't accidentally empty the list and silently
    # turn the filter into a no-op.
    assert len(_BENIGN_LINE_SUBSTRINGS) >= 3
