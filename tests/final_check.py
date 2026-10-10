"""
Final validation script: runs the exact six inputs the user requested
and prints the result for each one.
"""
import sys
from pathlib import Path
from unittest.mock import patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from eidolon.adapters.hyprland.parser import parse_config
from eidolon.adapters.hyprland.checks import run_checks
from eidolon.adapters.hyprland.monitor_parser import parse_hyprctl_monitors
from eidolon.adapters.hyprland.comparator import compare_configs
from eidolon.models import Label

fixture_path = Path(__file__).parent / "fixtures" / "monitor_edp1.txt"
monitors_info = parse_hyprctl_monitors(fixture_path.read_text())

def show_result(name, config_text, monitors=None, mock_which_none=False):
    """Run checks on a config snippet and print what we found."""
    print(f"\n{'='*60}")
    print(f"INPUT: {name}")
    print(f"Config: {config_text}")
    print(f"{'='*60}")
    
    c = parse_config(config_text)
    
    if mock_which_none:
        with patch("shutil.which", return_value=None):
            findings = run_checks(c, Path("/tmp"), monitors if monitors is not None else [])
    else:
        findings = run_checks(c, Path("/tmp"), monitors if monitors is not None else [])
    
    changes = compare_configs(parse_config(""), c, findings)
    
    if not findings and not changes:
        print("  No findings, no changes.")
    
    for f in findings:
        print(f"  FINDING: [{f.label.value}] [{f.severity.value}] {f.rule_id}: {f.evidence}")
    
    for ch in changes:
        print(f"  CHANGE:  {ch.category} '{ch.item_id}' | before={ch.before_state} | after={ch.after_state}")
        for f in ch.findings:
            print(f"           STATUS: [{f.label.value}] {f.evidence}")

# 1. Duplicate bind
show_result(
    "Duplicate bind",
    "bind = SUPER, T, exec, kitty\nbind = SUPER, T, exec, kitty"
)

# 2. Bind typo
show_result(
    "Bind typo",
    "bind = SUPER, T, exec, firefoxxxxxxxxxxxxxxx",
    mock_which_none=True
)

# 3. Monitor 2560x1440@165 (should fail)
show_result(
    "Monitor 2560x1440@165",
    "monitor = eDP-1, 2560x1440@165, 0x0, 1.2",
    monitors=monitors_info
)

# 4. Monitor preferred (should be OK)
show_result(
    "Monitor preferred",
    "monitor = eDP-1, preferred, auto, 1",
    monitors=monitors_info
)

# 5. exec-once alacrrity (typo, should fail)
show_result(
    "exec-once alacrrity",
    "exec-once = alacrrity",
    mock_which_none=True
)

# 6. Garbage line
show_result(
    "Garbage line",
    "this is garbage"
)
