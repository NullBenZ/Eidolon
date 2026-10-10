import pytest
from pathlib import Path
from unittest.mock import patch
from eidolon.adapters.hyprland.parser import parse_config
from eidolon.adapters.hyprland.checks import run_checks
from eidolon.adapters.hyprland.monitor_parser import parse_hyprctl_monitors
from eidolon.adapters.hyprland.comparator import compare_configs
from eidolon.models import Label

def test_monitor_check_fails_correctly(tmp_path):
    fixture_path = Path(__file__).parent / "fixtures" / "monitor_edp1.txt"
    monitors_info = parse_hyprctl_monitors(fixture_path.read_text())
    
    config_text = "monitor = eDP-1, 2560x1440@165, 0x0, 1.2"
    c = parse_config(config_text)
    f = run_checks(c, tmp_path, monitors_info)
    
    assert any(x.rule_id == "HYP-004" for x in f)
    err = next(x for x in f if x.rule_id == "HYP-004")
    assert err.label == Label.VERIFIED
    assert "available modes" in err.evidence.lower()
    
    changes = compare_configs(parse_config(""), c, f)
    mon_change = next(x for x in changes if x.category == "Monitor")
    assert any(fnd.rule_id == "HYP-004" for fnd in mon_change.findings)


def test_monitor_check_preferred_is_ok(tmp_path):
    fixture_path = Path(__file__).parent / "fixtures" / "monitor_edp1.txt"
    monitors_info = parse_hyprctl_monitors(fixture_path.read_text())
    
    config_text = "monitor = eDP-1, preferred, auto, 1"
    c = parse_config(config_text)
    f = run_checks(c, tmp_path, monitors_info)
    assert not any(x.rule_id == "HYP-004" for x in f)


def test_duplicate_keybinds_detected(tmp_path):
    config_text = "bind = SUPER, T, exec, kitty\nbind = SUPER, T, exec, kitty"
    c = parse_config(config_text)
    f = run_checks(c, tmp_path, [])
    
    # there should be TWO findings, one for each line
    dup_findings = [x for x in f if x.rule_id == "HYP-001"]
    assert len(dup_findings) == 2
    
    changes = compare_configs(parse_config(""), c, f)
    bind_change = next(x for x in changes if x.category == "Keybind")
    assert len(bind_change.findings) > 0


@patch("shutil.which")
def test_typo_inside_binds_caught(mock_which, tmp_path):
    mock_which.return_value = None
    config_text = "bind = SUPER, T, exec, firefoxxxxxxxxxxxxxxx"
    c = parse_config(config_text)
    f = run_checks(c, tmp_path, [])
    
    err = next(x for x in f if x.rule_id == "HYP-005")
    assert err.label == Label.VERIFIED
    assert "firefoxxxxxxxxxxxxxxx" in err.evidence
    

@patch("shutil.which")
def test_exec_once_not_in_path(mock_which, tmp_path):
    mock_which.return_value = None
    config_text = "exec-once = alacrrity"
    c = parse_config(config_text)
    f = run_checks(c, tmp_path, [])
    
    err = next(x for x in f if x.rule_id == "HYP-005")
    assert err.label == Label.VERIFIED
    assert "alacrrity" in err.evidence
    

def test_garbage_line_unknown(tmp_path):
    config_text = "this is garbage"
    c = parse_config(config_text)
    f = run_checks(c, tmp_path, [])
    
    changes = compare_configs(parse_config(""), c, f)
    assert any(x.category == "Unknown" for x in changes)
    unk = next(x for x in changes if x.category == "Unknown")
    assert unk.after_state == "this is garbage"
    assert any(fnd.rule_id == "HYP-000" for fnd in unk.findings)


def test_changed_bind_shows_before_after():
    old_text = "bind = SUPER, T, exec, kitty"
    new_text = "bind = SUPER, T, exec, alacritty"
    
    old_c = parse_config(old_text)
    new_c = parse_config(new_text)
    
    changes = compare_configs(old_c, new_c, [])
    assert len(changes) == 1
    ch = changes[0]
    assert ch.category == "Keybind"
    assert ch.before_state == "exec kitty"
    assert ch.after_state == "exec alacritty"
