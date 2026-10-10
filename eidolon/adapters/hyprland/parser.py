import re
from typing import Dict, List
from .models import (
    HyprlandConfig, MonitorDirective, BindDirective, ExecDirective, SourceDirective, UnknownDirective
)

def expand_variables(line: str, variables: Dict[str, str]) -> str:
    """Expands $VAR with its value, prioritizing longer variable names first."""
    sorted_vars = sorted(variables.keys(), key=len, reverse=True)
    res = line
    for v in sorted_vars:
        # replace exact variable (not a substring of a longer var)
        # using simple replace since vars start with $
        res = res.replace(f"${v}", variables[v])
    return res

def parse_config(content: str) -> HyprlandConfig:
    config = HyprlandConfig()
    config.raw_lines = content.splitlines()
    
    # First pass: collect variables ($VAR = value)
    var_pattern = re.compile(r'^\s*\$([a-zA-Z0-9_]+)\s*=\s*(.*)$')
    
    for line in config.raw_lines:
        line_no_comment = line.split('#')[0].strip()
        if not line_no_comment:
            continue
        m = var_pattern.match(line_no_comment)
        if m:
            config.variables[m.group(1)] = m.group(2).strip()

    # Second pass: parse directives
    for i, line in enumerate(config.raw_lines):
        line_num = i + 1
        line_no_comment = line.split('#')[0].strip()
        if not line_no_comment:
            continue
            
        expanded = expand_variables(line_no_comment, config.variables)
        
        # skip variable definitions
        if var_pattern.match(line_no_comment):
            continue
        
        # parse monitor
        if expanded.startswith("monitor") and "=" in expanded:
            val = expanded.split("=", 1)[1].strip()
            parts = [p.strip() for p in val.split(',')]
            name = parts[0] if len(parts) > 0 else ""
            res = parts[1] if len(parts) > 1 else ""
            pos = parts[2] if len(parts) > 2 else ""
            scale = parts[3] if len(parts) > 3 else ""
            config.monitors.append(MonitorDirective(
                raw_line=line, line_number=line_num,
                name=name, resolution=res, position=pos, scale=scale
            ))
                
        # parse bind
        elif expanded.startswith("bind"):
            m = re.match(r'^(bind[a-z]*)\s*=\s*(.*)$', expanded)
            parsed_bind = False
            if m:
                variant = m.group(1)
                args_str = m.group(2)
                # Split by comma
                parts = [p.strip() for p in args_str.split(',')]
                
                # Check for valid modifier and known dispatcher
                # Hyprland binds have at least 3 parts: mod, key, dispatcher
                if len(parts) >= 3:
                    mods = parts[0]
                    key = parts[1]
                    dispatcher = parts[2]
                    arg = ",".join(parts[3:]) if len(parts) > 3 else ""
                    
                    # Basic validation for "valid modifier field" and "known dispatcher"
                    # User said "does not have a valid modifier field and a known dispatcher"
                    # We can check if mods is well-formed (e.g. no '+', space)
                    # and dispatcher is known.
                    known_dispatchers = {"exec", "execr", "killactive", "workspace", "movetoworkspace", "togglefloating", "fullscreen", "pseudo", "pin", "exit"}
                    # The user specifically complained about "Super+T" (which uses + instead of , or is invalid in Hyprland)
                    if "+" not in mods and dispatcher in known_dispatchers:
                        config.binds.append(BindDirective(
                            raw_line=line, line_number=line_num,
                            variant=variant, mods=mods, key=key, dispatcher=dispatcher, arg=arg
                        ))
                        parsed_bind = True
                        
            if not parsed_bind:
                config.unknowns.append(UnknownDirective(
                    raw_line=line, line_number=line_num,
                    content=expanded
                ))
        
        # parse exec / exec-once
        elif expanded.startswith("exec-once") and "=" in expanded:
            val = expanded.split("=", 1)[1].strip()
            config.execs.append(ExecDirective(
                raw_line=line, line_number=line_num,
                is_once=True, command=val
            ))
        elif expanded.startswith("exec") and not expanded.startswith("exec-once") and "=" in expanded:
            val = expanded.split("=", 1)[1].strip()
            config.execs.append(ExecDirective(
                raw_line=line, line_number=line_num,
                is_once=False, command=val
            ))
            
        # parse source
        elif expanded.startswith("source") and "=" in expanded:
            val = expanded.split("=", 1)[1].strip()
            config.sources.append(SourceDirective(
                raw_line=line, line_number=line_num,
                path=val
            ))
        else:
            config.unknowns.append(UnknownDirective(
                raw_line=line, line_number=line_num,
                content=expanded
            ))
            
    return config
