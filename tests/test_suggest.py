"""Tests for the 'eidolon suggest' command."""

import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from eidolon.core import (
    handle_suggest,
    _filter_suggested_lines,
    _apply_suggestion_to_content,
)
from eidolon.ai import GemmaProvider, SuggestionReply


# ---------------------------------------------------------------------------
# Unit tests for the safety filter
# ---------------------------------------------------------------------------

def test_filter_accepts_valid_monitor_line():
    accepted, rejected = _filter_suggested_lines([
        "monitor = eDP-1, 1920x1080@60, 0x0, 1",
    ])
    assert len(accepted) == 1
    assert len(rejected) == 0


def test_filter_rejects_non_monitor_line():
    accepted, rejected = _filter_suggested_lines([
        "bind = SUPER, T, exec, kitty",
    ])
    assert len(accepted) == 0
    assert len(rejected) == 1
    assert "not a monitor line" in rejected[0]


def test_filter_rejects_shell_chaining():
    accepted, rejected = _filter_suggested_lines([
        "monitor = eDP-1, 1920x1080@60, 0x0, 1 && echo pwned",
    ])
    assert len(accepted) == 0
    assert "shell chaining" in rejected[0]


def test_filter_rejects_pipe():
    accepted, rejected = _filter_suggested_lines([
        "monitor = eDP-1, 1920x1080@60, 0x0, 1 | tee /tmp/x",
    ])
    assert len(accepted) == 0
    assert "shell chaining" in rejected[0]


def test_filter_rejects_semicolon():
    accepted, rejected = _filter_suggested_lines([
        "monitor = eDP-1, 1920x1080; rm -rf /",
    ])
    assert len(accepted) == 0
    assert "shell chaining" in rejected[0]


def test_filter_rejects_empty_line():
    accepted, rejected = _filter_suggested_lines(["", "  "])
    assert len(accepted) == 0
    assert len(rejected) == 2


# ---------------------------------------------------------------------------
# Unit tests for _apply_suggestion_to_content
# ---------------------------------------------------------------------------

def test_apply_replaces_existing_monitor():
    original = "monitor = eDP-1, 1920x1080@60, 0x0, 1\nbind = SUPER, T, exec, kitty"
    result = _apply_suggestion_to_content(original, [
        "monitor = eDP-1, 2560x1440@144, 0x0, 1.5",
    ])
    lines = result.splitlines()
    assert lines[0] == "monitor = eDP-1, 2560x1440@144, 0x0, 1.5"
    assert lines[1] == "bind = SUPER, T, exec, kitty"
    assert len(lines) == 2  # no duplicate added


def test_apply_appends_new_monitor():
    original = "monitor = eDP-1, 1920x1080@60, 0x0, 1"
    result = _apply_suggestion_to_content(original, [
        "monitor = DP-1, 2560x1440@144, 1920x0, 1",
    ])
    lines = result.splitlines()
    assert len(lines) == 2
    assert "DP-1" in lines[1]


# ---------------------------------------------------------------------------
# Unit tests for _parse_suggestion_reply
# ---------------------------------------------------------------------------

def test_parse_suggestion_reply_valid():
    raw = json.dumps({
        "lines": ["monitor = eDP-1, 2560x1440@144, 0x0, 1.5"],
        "explanation": "Changed resolution and refresh rate."
    })
    reply, err = GemmaProvider._parse_suggestion_reply(raw)
    assert err is None
    assert len(reply.lines) == 1
    assert reply.explanation == "Changed resolution and refresh rate."


def test_parse_suggestion_reply_fenced():
    raw = '```json\n{"lines": ["monitor = eDP-1, 2560x1440@144, 0x0, 1.5"], "explanation": "ok"}\n```'
    reply, err = GemmaProvider._parse_suggestion_reply(raw)
    assert err is None
    assert len(reply.lines) == 1


def test_parse_suggestion_reply_malformed():
    raw = "this is not json at all"
    reply, err = GemmaProvider._parse_suggestion_reply(raw)
    assert reply is None
    assert "malformed JSON" in err


# ---------------------------------------------------------------------------
# Integration tests for handle_suggest (mocked AI)
# ---------------------------------------------------------------------------

HYPR_CONFIG = """\
monitor = eDP-1, 1920x1080@60, 0x0, 1
bind = SUPER, T, exec, kitty
exec-once = waybar
"""

def _fake_subprocess_run(cmd, **kwargs):
    """Fake subprocess.run that returns failure for hyprctl."""
    import subprocess
    if cmd[0] == "hyprctl":
        return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="")
    return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="")


def _make_mock_provider(reply_json):
    """Create a GemmaProvider mock that returns a given JSON string."""
    mock_provider = MagicMock(spec=GemmaProvider)
    mock_provider.is_configured = True

    if reply_json is None:
        mock_provider.suggest.return_value = (None, "AI call failed: timeout")
    else:
        reply, err = GemmaProvider._parse_suggestion_reply(reply_json)
        mock_provider.suggest.return_value = (reply, err)

    return mock_provider


@patch("eidolon.core.subprocess.run", side_effect=_fake_subprocess_run)
@patch("eidolon.core.Prompt.ask", return_value="apply")
def test_suggest_valid(mock_ask, mock_run, tmp_path):
    """Valid AI suggestion replaces an existing monitor line."""
    test_file = tmp_path / "hyprland.conf"
    test_file.write_text(HYPR_CONFIG)

    reply_json = json.dumps({
        "lines": ["monitor = eDP-1, 2560x1440@144, 0x0, 1.5"],
        "explanation": "Changed to 1440p at 144Hz with 1.5x scale."
    })

    with patch("eidolon.ai.GemmaProvider") as MockCls:
        MockCls.return_value = _make_mock_provider(reply_json)
        handle_suggest(str(test_file), "set my monitor to 2560x1440 144hz")

    content = test_file.read_text()
    assert "2560x1440@144" in content
    assert "1920x1080@60" not in content  # replaced, not duplicated


@patch("eidolon.core.subprocess.run", side_effect=_fake_subprocess_run)
@patch("eidolon.core.Prompt.ask", return_value="d")
def test_suggest_discard(mock_ask, mock_run, tmp_path):
    """Discarding keeps the original file unchanged."""
    test_file = tmp_path / "hyprland.conf"
    test_file.write_text(HYPR_CONFIG)

    reply_json = json.dumps({
        "lines": ["monitor = eDP-1, 2560x1440@144, 0x0, 1.5"],
        "explanation": "Changed."
    })

    with patch("eidolon.ai.GemmaProvider") as MockCls:
        MockCls.return_value = _make_mock_provider(reply_json)
        handle_suggest(str(test_file), "set my monitor to 2560x1440 144hz")

    assert test_file.read_text() == HYPR_CONFIG


@patch("eidolon.core.subprocess.run", side_effect=_fake_subprocess_run)
def test_suggest_malformed_json(mock_run, tmp_path, capsys):
    """Malformed JSON from AI prints error and changes nothing."""
    test_file = tmp_path / "hyprland.conf"
    test_file.write_text(HYPR_CONFIG)

    with patch("eidolon.ai.GemmaProvider") as MockCls:
        mock_prov = MagicMock(spec=GemmaProvider)
        mock_prov.is_configured = True
        mock_prov.suggest.return_value = (None, "AI returned malformed JSON: ...")
        MockCls.return_value = mock_prov
        handle_suggest(str(test_file), "set my monitor resolution to 4k")

    assert test_file.read_text() == HYPR_CONFIG
    captured = capsys.readouterr()
    assert "AI failed" in captured.out


@patch("eidolon.core.subprocess.run", side_effect=_fake_subprocess_run)
def test_suggest_ai_failure(mock_run, tmp_path, capsys):
    """AI timeout/failure prints error and changes nothing."""
    test_file = tmp_path / "hyprland.conf"
    test_file.write_text(HYPR_CONFIG)

    with patch("eidolon.ai.GemmaProvider") as MockCls:
        MockCls.return_value = _make_mock_provider(None)  # None = failure
        handle_suggest(str(test_file), "set my monitor resolution to 4k")

    assert test_file.read_text() == HYPR_CONFIG
    captured = capsys.readouterr()
    assert "AI failed" in captured.out


def test_suggest_out_of_scope(tmp_path, capsys):
    """A request outside scope prints 'not supported yet' and changes nothing."""
    test_file = tmp_path / "hyprland.conf"
    test_file.write_text(HYPR_CONFIG)

    handle_suggest(str(test_file), "add a keybind for launching firefox")

    assert test_file.read_text() == HYPR_CONFIG
    captured = capsys.readouterr()
    assert "Not supported yet" in captured.out


@patch("eidolon.core.subprocess.run", side_effect=_fake_subprocess_run)
def test_suggest_rejected_by_safety_filter(mock_run, tmp_path, capsys):
    """A suggested line that fails the safety filter is rejected."""
    test_file = tmp_path / "hyprland.conf"
    test_file.write_text(HYPR_CONFIG)

    reply_json = json.dumps({
        "lines": ["exec = rm -rf / && echo pwned"],
        "explanation": "Totally safe trust me."
    })

    with patch("eidolon.ai.GemmaProvider") as MockCls:
        MockCls.return_value = _make_mock_provider(reply_json)
        handle_suggest(str(test_file), "set my monitor to something")

    assert test_file.read_text() == HYPR_CONFIG
    captured = capsys.readouterr()
    assert "rejected" in captured.out.lower()


def test_suggest_no_ai_flag(tmp_path, capsys):
    """--no-ai refuses politely."""
    test_file = tmp_path / "hyprland.conf"
    test_file.write_text(HYPR_CONFIG)

    handle_suggest(str(test_file), "set my monitor to 4k", no_ai=True)

    assert test_file.read_text() == HYPR_CONFIG
    captured = capsys.readouterr()
    assert "needs AI" in captured.out
