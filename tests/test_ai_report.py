"""
Show AI mock output for the report.
"""
import sys
from pathlib import Path
from eidolon.models import Finding, Label, Severity
from eidolon.adapters.hyprland.comparator import ConfigChange
from eidolon.report import render_effect_view

f = Finding(
    rule_id="HYP-004", title="Bad mode", label=Label.VERIFIED,
    severity=Severity.ERROR, evidence="Mode not available",
    recommendation="Fix it", source="Hyprland Adapter", line_number=1,
)
ch = ConfigChange(
    category="Monitor", item_id="eDP-1",
    before_state="1920x1200@60", after_state="2560x1440@165",
    findings=[f],
    meaning="The laptop screen will likely go blank or display an error message because it does not support 165Hz.",
    fix="Change to 1920x1200@60.00Hz or use the 'preferred' keyword."
)

ch2 = ConfigChange(
    category="Keybind", item_id="super:t",
    before_state=None, after_state="exec kitty",
    findings=[]
)

render_effect_view([ch, ch2], "You changed a monitor mode and added a keybind, which might cause screen issues.")
