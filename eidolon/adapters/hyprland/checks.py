import os
import shutil
from pathlib import Path
from typing import List, Optional
from eidolon.models import Finding, Label, Severity
from .models import HyprlandConfig, MonitorInfo

def check_duplicate_binds(config: HyprlandConfig) -> List[Finding]:
    """Check B: Duplicate keybinding across the whole file."""
    findings = []
    
    # Store a list of every bind with its line number, then group by combo
    bind_map = {}
    for bind in config.binds:
        key_sig = f"{bind.mods.strip().lower()}:{bind.key.strip().lower()}"
        if key_sig not in bind_map:
            bind_map[key_sig] = []
        bind_map[key_sig].append(bind)
        
    for key_sig, binds in bind_map.items():
        if len(binds) > 1:
            line_nums = ", ".join(str(b.line_number) for b in binds)
            # Add a finding for EACH duplicate line so it shows up on all of them
            for b in binds:
                findings.append(Finding(
                    rule_id="HYP-001",
                    title="Duplicate Keybinding",
                    label=Label.VERIFIED,
                    severity=Severity.WARNING,
                    evidence=f"Binding '{binds[0].mods} {binds[0].key}' is defined on lines: {line_nums}.",
                    recommendation="Remove or change the duplicate keybindings.",
                    source="Hyprland Adapter",
                    line_number=b.line_number
                ))
            
    return findings


def check_monitor_modes(config: HyprlandConfig, monitors_info: Optional[List[MonitorInfo]]) -> List[Finding]:
    """Check C: Monitor mode not offered by hyprctl monitors output."""
    findings = []
    
    if monitors_info is None or len(monitors_info) == 0:
        # We need this to attach to ALL monitors in the config since we can't verify them
        reason = "hyprctl monitors command failed or is unavailable." if monitors_info is None else "hyprctl returned no monitors."
        for monitor in config.monitors:
            findings.append(Finding(
                rule_id="HYP-002",
                title="Monitor Mode Validation Unavailable",
                label=Label.UNKNOWN,
                severity=Severity.INFO,
                evidence=reason,
                recommendation="Ensure hyprctl is installed and Hyprland is running.",
                source="Hyprland Adapter",
                line_number=monitor.line_number
            ))
        return findings

    special_keywords = {"preferred", "highres", "highrr", "auto", "disable"}
    
    for monitor in config.monitors:
        res_str = monitor.resolution.lower()
        if not res_str or res_str in special_keywords:
            continue
            
        if "@" in res_str:
            res_part, rr_part = res_str.split("@", 1)
            try:
                config_rr = float(rr_part)
            except ValueError:
                continue
        else:
            res_part = res_str
            config_rr = None
            
        target_info = next((m for m in monitors_info if m.name == monitor.name), None)
        if not target_info and monitor.name != "":
            findings.append(Finding(
                rule_id="HYP-003",
                title="Unknown Monitor",
                label=Label.UNKNOWN,
                severity=Severity.WARNING,
                evidence=f"Monitor '{monitor.name}' is not currently connected.",
                recommendation="Check if the monitor name is correct.",
                source="Hyprland Adapter",
                line_number=monitor.line_number
            ))
            continue
            
        if target_info:
            mode_found = False
            for mode in target_info.available_modes:
                if mode.resolution == res_part:
                    if config_rr is None:
                        mode_found = True
                        break
                    if abs(mode.refresh_rate - config_rr) <= 0.5:
                        mode_found = True
                        break
                        
            if not mode_found:
                avail = ", ".join(f"{m.resolution}@{m.refresh_rate}Hz" for m in target_info.available_modes)
                findings.append(Finding(
                    rule_id="HYP-004",
                    title="Unsupported Monitor Mode",
                    label=Label.VERIFIED,
                    severity=Severity.ERROR,
                    evidence=f"Mode {res_str} not available. Available modes: {avail}",
                    recommendation="Use an available mode or a keyword like 'preferred'.",
                    source="Hyprland Adapter",
                    line_number=monitor.line_number
                ))
                
    return findings


def check_exec_commands(config: HyprlandConfig) -> List[Finding]:
    """Check D: exec / exec-once command not found on PATH."""
    findings = []
    
    # Also check binds whose dispatcher is exec or execr
    commands_to_check = []
    for ex in config.execs:
        commands_to_check.append((ex.command, ex.line_number))
    for b in config.binds:
        if b.dispatcher in ("exec", "execr"):
            commands_to_check.append((b.arg, b.line_number))
            
    for cmd, line_num in commands_to_check:
        cmd_parts = cmd.split()
        if not cmd_parts:
            continue
            
        executable = cmd_parts[0]
        # Ignore shell variables or subshells (can't evaluate statically easily)
        if executable.startswith("$") or executable.startswith("~"):
            findings.append(Finding(
                rule_id="HYP-007",
                title="Dynamic Command Cannot Be Verified",
                label=Label.UNKNOWN,
                severity=Severity.INFO,
                evidence=f"Command '{executable}' uses shell constructs.",
                recommendation="Ensure it evaluates to a valid executable.",
                source="Hyprland Adapter",
                line_number=line_num
            ))
            continue
            
        if not shutil.which(executable):
            findings.append(Finding(
                rule_id="HYP-005",
                title="Executable Not Found",
                label=Label.VERIFIED,
                severity=Severity.ERROR,
                evidence=f"Command '{executable}' is not in PATH.",
                recommendation="Install the required package or provide an absolute path.",
                source="Hyprland Adapter",
                line_number=line_num
            ))
            
    return findings


def check_source_paths(config: HyprlandConfig, config_dir: Path) -> List[Finding]:
    """Check E: source = path does not exist."""
    findings = []
    
    for src in config.sources:
        path_str = os.path.expanduser(src.path)
        path = Path(path_str)
        
        if not path.is_absolute():
            path = config_dir / path
            
        if not path.exists():
            findings.append(Finding(
                rule_id="HYP-006",
                title="Source File Not Found",
                label=Label.VERIFIED,
                severity=Severity.ERROR,
                evidence=f"Included file '{src.path}' does not exist.",
                recommendation="Create the file or correct the path.",
                source="Hyprland Adapter",
                line_number=src.line_number
            ))
            
    return findings


def run_checks(config: HyprlandConfig, config_dir: Path, monitors_info: Optional[List[MonitorInfo]] = None) -> List[Finding]:
    findings = []
    findings.extend(check_duplicate_binds(config))
    findings.extend(check_monitor_modes(config, monitors_info))
    findings.extend(check_exec_commands(config))
    findings.extend(check_source_paths(config, config_dir))
    return findings
