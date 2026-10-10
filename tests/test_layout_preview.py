import pytest
from rich.console import Console
from eidolon.adapters.hyprland.comparator import ConfigChange
from eidolon.models import Finding, Label, Severity
from eidolon.report import render_effect_view, _parse_monitor_state

def _run_preview_test(changes, capsys):
    console = Console(width=80)
    render_effect_view(changes)
    captured = capsys.readouterr()
    return captured.out

def test_parse_monitor_state():
    m = _parse_monitor_state("Res: 1920x1080@60 | Pos: 0x0 | Scale: 1.5", "DP-1")
    assert m is not None
    assert m.name == "DP-1"
    assert m.w == 1920
    assert m.h == 1080
    assert m.x == 0
    assert m.y == 0
    assert m.scale == 1.5
    
    # unsupported parsing
    assert _parse_monitor_state("Res: preferred | Pos: auto | Scale: auto", "DP-2") is None

def test_layout_preview_valid_change(capsys):
    ch = ConfigChange(
        category="Monitor",
        item_id="DP-1",
        before_state="Res: 1920x1080@60 | Pos: 0x0 | Scale: 1",
        after_state="Res: 2560x1440@144 | Pos: 0x0 | Scale: 1",
        findings=[]
    )
    out = _run_preview_test([ch], capsys)
    assert "Layout preview" in out
    assert "BEFORE" in out
    assert "AFTER" in out
    assert "1920x1080" in out
    assert "2560x1440" in out

def test_layout_preview_unsupported_mode(capsys):
    f = Finding(
        rule_id="HYP-004", title="Mode Error",
        label=Label.VERIFIED, severity=Severity.ERROR,
        evidence="Mode not available", recommendation="", source=""
    )
    ch = ConfigChange(
        category="Monitor",
        item_id="DP-1",
        before_state="Res: 1920x1080@60 | Pos: 0x0 | Scale: 1",
        after_state="Res: 9999x9999@999 | Pos: 0x0 | Scale: 1",
        findings=[f]
    )
    out = _run_preview_test([ch], capsys)
    assert "Layout preview" in out
    assert "Mode not available (verified)" in out

def test_layout_preview_scale_change(capsys):
    ch = ConfigChange(
        category="Monitor",
        item_id="DP-1",
        before_state="Res: 1920x1080@60 | Pos: 0x0 | Scale: 1",
        after_state="Res: 1920x1080@60 | Pos: 0x0 | Scale: 2",
        findings=[]
    )
    out = _run_preview_test([ch], capsys)
    assert "Layout preview" in out
    assert "Scale: 1" in out
    assert "Scale: 2" in out

def test_layout_preview_no_monitor_change(capsys):
    ch = ConfigChange(
        category="Keybind",
        item_id="super:t",
        before_state="exec kitty",
        after_state="exec alacritty",
        findings=[]
    )
    out = _run_preview_test([ch], capsys)
    assert "Layout preview" not in out
    assert "EFFECT VIEW" in out
