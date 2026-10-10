import re
from typing import List
from .models import MonitorInfo, Mode

def parse_hyprctl_monitors(output: str) -> List[MonitorInfo]:
    """Parses the output of 'hyprctl monitors' into MonitorInfo objects."""
    monitors = []
    current_monitor = None
    
    for line in output.splitlines():
        line = line.rstrip() # specifically instructed to strip trailing whitespace
        if not line:
            continue
            
        # e.g., Monitor eDP-1 (ID 0):
        m_monitor = re.match(r'^Monitor\s+(.+)\s+\(ID \d+\):$', line)
        if m_monitor:
            if current_monitor:
                monitors.append(current_monitor)
            current_monitor = MonitorInfo(name=m_monitor.group(1))
            continue
            
        if current_monitor:
            line_stripped = line.strip()
            # e.g., 1920x1200@60.00300 at 0x0
            if " at " in line_stripped and "x" in line_stripped and "@" in line_stripped:
                # active mode
                parts = line_stripped.split(" at ")[0]
                if "@" in parts:
                    res, rr = parts.split("@")
                    try:
                        current_monitor.active_mode = Mode(resolution=res, refresh_rate=float(rr))
                    except ValueError:
                        pass
                        
            elif line_stripped.startswith("availableModes:"):
                # e.g., availableModes: 1920x1200@60.00Hz 
                modes_str = line_stripped[15:].strip()
                if modes_str:
                    for mode_str in modes_str.split():
                        if "@" in mode_str:
                            res, rr = mode_str.split("@")
                            rr = rr.replace("Hz", "")
                            try:
                                current_monitor.available_modes.append(Mode(resolution=res, refresh_rate=float(rr)))
                            except ValueError:
                                pass
                                
    if current_monitor:
        monitors.append(current_monitor)
        
    return monitors
