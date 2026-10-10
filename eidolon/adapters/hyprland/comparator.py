from dataclasses import dataclass
from typing import List, Optional
from eidolon.models import Finding, Label, Severity
from .models import HyprlandConfig

@dataclass
class ConfigChange:
    category: str
    item_id: str
    before_state: Optional[str]
    after_state: Optional[str]
    findings: List[Finding]
    meaning: Optional[str] = None

def _find_finding_for_line(findings: List[Finding], line_num: int) -> List[Finding]:
    res = []
    for f in findings:
        if f.line_number == line_num:
            res.append(f)
    return res

def compare_configs(old_c: HyprlandConfig, new_c: HyprlandConfig, new_findings: List[Finding]) -> List[ConfigChange]:
    changes = []
    
    # Compare Monitors (by name)
    old_mons = {m.name: m for m in old_c.monitors}
    new_mons = {m.name: m for m in new_c.monitors}
    for name, new_m in new_mons.items():
        state_str = f"Res: {new_m.resolution} | Pos: {new_m.position} | Scale: {new_m.scale}"
        old_m = old_mons.get(name)
        old_state_str = f"Res: {old_m.resolution} | Pos: {old_m.position} | Scale: {old_m.scale}" if old_m else None
        
        if old_state_str != state_str:
            f = _find_finding_for_line(new_findings, new_m.line_number)
            changes.append(ConfigChange("Monitor", name if name else "All", old_state_str, state_str, f))
            
    for name, old_m in old_mons.items():
        if name not in new_mons:
            old_state_str = f"Res: {old_m.resolution} | Pos: {old_m.position} | Scale: {old_m.scale}"
            changes.append(ConfigChange("Monitor", name if name else "All", old_state_str, None, []))

    # Compare Keybinds (by signature: mods + key)
    def bind_sig(b): return f"{b.mods.strip().lower()}:{b.key.strip().lower()}"
    old_binds = {bind_sig(b): b for b in old_c.binds}
    new_binds = {}
    for b in new_c.binds:
        # User might have added duplicates, if so the duplicate check creates findings for them
        sig = bind_sig(b)
        # In case of duplicate bindings in new_c, we still want to show them if they differ from old
        # But wait, compare_configs compares old state vs new state. If there are duplicates, 
        # just append a change for each or just use the last one but collect all findings.
        # Actually, let's group by sig to avoid overwriting.
        if sig not in new_binds:
            new_binds[sig] = []
        new_binds[sig].append(b)
        
    for sig, new_b_list in new_binds.items():
        for new_b in new_b_list:
            state_str = f"{new_b.dispatcher} {new_b.arg}"
            old_b = old_binds.get(sig)
            old_state_str = f"{old_b.dispatcher} {old_b.arg}" if old_b else None
            
            if old_state_str != state_str or len(new_b_list) > 1:
                # If there are duplicates, we should show it.
                f = _find_finding_for_line(new_findings, new_b.line_number)
                changes.append(ConfigChange("Keybind", sig, old_state_str, state_str, f))
            
    for sig, old_b in old_binds.items():
        if sig not in new_binds:
            old_state_str = f"{old_b.dispatcher} {old_b.arg}"
            changes.append(ConfigChange("Keybind", sig, old_state_str, None, []))
            
    # Compare Execs (by command)
    old_execs = {e.command: e for e in old_c.execs}
    new_execs = {e.command: e for e in new_c.execs}
    for cmd, new_e in new_execs.items():
        state = "exec-once" if new_e.is_once else "exec"
        old_e = old_execs.get(cmd)
        if not old_e:
            f = _find_finding_for_line(new_findings, new_e.line_number)
            changes.append(ConfigChange("Startup", cmd, None, state, f))
        elif old_e.is_once != new_e.is_once:
            old_state = "exec-once" if old_e.is_once else "exec"
            f = _find_finding_for_line(new_findings, new_e.line_number)
            changes.append(ConfigChange("Startup", cmd, old_state, state, f))
            
    for cmd, old_e in old_execs.items():
        if cmd not in new_execs:
            old_state = "exec-once" if old_e.is_once else "exec"
            changes.append(ConfigChange("Startup", cmd, old_state, None, []))
            
    # Compare Sources (by path)
    old_srcs = {s.path: s for s in old_c.sources}
    new_srcs = {s.path: s for s in new_c.sources}
    for path, new_s in new_srcs.items():
        if path not in old_srcs:
            f = _find_finding_for_line(new_findings, new_s.line_number)
            changes.append(ConfigChange("Source", path, None, "included", f))
    for path, old_s in old_srcs.items():
        if path not in new_srcs:
            changes.append(ConfigChange("Source", path, "included", None, []))

    # Add Unknowns
    for unk in new_c.unknowns:
        # if it wasn't in old config, it's a new unknown
        if not any(u.content == unk.content for u in old_c.unknowns):
            f = _find_finding_for_line(new_findings, unk.line_number)
            # Add a default finding if none exists
            if not f:
                f = [Finding(rule_id="HYP-000", title="Unknown Directive", label=Label.UNKNOWN, severity=Severity.INFO, evidence=f"line {unk.line_number} not understood", recommendation="", source="Hyprland Adapter", line_number=unk.line_number)]
            changes.append(ConfigChange("Unknown", "Directive", None, unk.content, f))

    return changes
