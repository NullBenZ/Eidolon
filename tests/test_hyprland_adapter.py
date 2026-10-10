import pytest
from pathlib import Path
from unittest.mock import patch
from eidolon.adapters.hyprland import (
    parse_config, parse_hyprctl_monitors, run_checks, Mode
)
from eidolon.models import Label

def test_parse_hyprctl_monitors(tmp_path):
    fixture_path = Path(__file__).parent / "fixtures" / "monitor_edp1.txt"
    monitors = parse_hyprctl_monitors(fixture_path.read_text())
    
    assert len(monitors) == 1
    m = monitors[0]
    assert m.name == "eDP-1"
    assert m.active_mode.resolution == "1920x1200"
    assert m.active_mode.refresh_rate == 60.003
    assert len(m.available_modes) == 1
    assert m.available_modes[0].resolution == "1920x1200"
    assert m.available_modes[0].refresh_rate == 60.00

def test_parse_config_variables():
    content = "$mod = SUPER\nbind = $mod, Return, exec, alacritty\n"
    config = parse_config(content)
    assert config.variables["mod"] == "SUPER"
    assert len(config.binds) == 1
    b = config.binds[0]
    assert b.mods == "SUPER"

def test_check_duplicate_binds():
    content = "bind=SUPER,Return,exec,kitty\nbind=SUPER,Return,exec,alacritty\n"
    config = parse_config(content)
    findings = run_checks(config, Path("/tmp"), [])
    dup_findings = [f for f in findings if f.rule_id == "HYP-001"]
    assert len(dup_findings) >= 2

def test_check_monitor_modes(tmp_path):
    fixture_path = Path(__file__).parent / "fixtures" / "monitor_edp1.txt"
    monitors_info = parse_hyprctl_monitors(fixture_path.read_text())
    
    # Valid mode (tolerance)
    c1 = parse_config("monitor=eDP-1,1920x1200@60,0x0,1")
    f1 = run_checks(c1, Path("/tmp"), monitors_info)
    assert not any(f.rule_id == "HYP-004" for f in f1)
    
    # Invalid mode
    c2 = parse_config("monitor=eDP-1,1920x1080@144,0x0,1")
    f2 = run_checks(c2, Path("/tmp"), monitors_info)
    assert any(f.rule_id == "HYP-004" for f in f2)
    
    # Special keyword
    c3 = parse_config("monitor=eDP-1,preferred,auto,1")
    f3 = run_checks(c3, Path("/tmp"), monitors_info)
    assert not any(f.rule_id == "HYP-004" for f in f3)

@patch("shutil.which")
def test_check_exec_commands(mock_which):
    mock_which.return_value = None # Nothing is installed
    c = parse_config("exec-once=waybar\nexec = dbus-update\n")
    f = run_checks(c, Path("/tmp"), [])
    exec_findings = [x for x in f if x.rule_id == "HYP-005"]
    assert len(exec_findings) == 2

def test_check_source_paths(tmp_path):
    # Create a real file
    existing_file = tmp_path / "macchiato.conf"
    existing_file.touch()
    
    content = f"source = {existing_file.name}\nsource = non_existent.conf\n"
    c = parse_config(content)
    f = run_checks(c, tmp_path, [])
    source_findings = [x for x in f if x.rule_id == "HYP-006"]
    assert len(source_findings) == 1
    assert "non_existent.conf" in source_findings[0].evidence
