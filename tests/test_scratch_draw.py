from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from typing import Optional, List

class ParsedMon:
    def __init__(self, name, w, h, x, y, scale, res_str, pos_str, scale_str):
        self.name = name
        self.w = w; self.h = h
        self.x = x; self.y = y
        self.scale = scale
        self.res_str = res_str
        self.pos_str = pos_str
        self.scale_str = scale_str
        self.term_w = 0; self.term_h = 0
        self.term_x = 0; self.term_y = 0
        self.is_after = False
        self.is_error = False
        self.error_text = ""

def _parse_monitor_state(state_str: str, name: str) -> Optional[ParsedMon]:
    if not state_str: return None
    import re
    m = re.match(r"Res:\s*(.*?)\s*\|\s*Pos:\s*(.*?)\s*\|\s*Scale:\s*(.*)", state_str)
    if not m: return None
    res, pos, scale_str = m.groups()
    
    res_m = re.match(r"(\d+)x(\d+)", res)
    if not res_m: return None
    w, h = int(res_m.group(1)), int(res_m.group(2))
    
    pos_m = re.match(r"(\d+)x(\d+)", pos)
    if not pos_m: return None
    x, y = int(pos_m.group(1)), int(pos_m.group(2))
    
    try:
        scale = float(scale_str)
    except ValueError:
        return None
        
    return ParsedMon(name, w, h, x, y, scale, res, pos, scale_str)

def test_draw():
    m1 = _parse_monitor_state("Res: 1920x1080@60 | Pos: 0x0 | Scale: 1", "DP-1")
    m2 = _parse_monitor_state("Res: 1920x1080@60 | Pos: 1920x0 | Scale: 1", "DP-2")
    m2.is_after = True
    m2.is_error = True
    m2.error_text = "Mode not available"
    
    mons = [m1, m2]
    
    max_eff_x = 1
    for m in mons:
        max_eff_x = max(max_eff_x, m.x + (m.w / m.scale))
        
    scale_factor = 80 / max_eff_x
    for m in mons:
        m.term_w = max(25, int((m.w / m.scale) * scale_factor))
        m.term_h = max(8, int((m.h / m.scale) * scale_factor / 2))
        m.term_x = int(m.x * scale_factor)
        m.term_y = int(m.y * scale_factor / 2)
        
    max_tx = max((m.term_x + m.term_w for m in mons), default=0)
    max_ty = max((m.term_y + m.term_h for m in mons), default=0)
    
    chars = [[" " for _ in range(max_tx)] for _ in range(max_ty)]
    styles = [[None for _ in range(max_tx)] for _ in range(max_ty)]
    
    c = Console()
    for m in mons:
        content = f"[bold]{m.name}[/bold]\n{m.res_str}\nPos: {m.pos_str}\nScale: {m.scale_str}"
        style = "blue"
        if m.is_after and m.is_error:
            style = "red"
            content += f"\n\n[red]{m.error_text} (verified)[/red]"
            
        p = Panel(content, width=m.term_w, height=m.term_h, style=style, expand=True)
        lines = c.render_lines(p, c.options.update(width=m.term_w))
        
        for row_idx, line in enumerate(lines):
            cy = m.term_y + row_idx
            if cy >= max_ty: continue
            cx = m.term_x
            for seg in line:
                for char in seg.text:
                    if char != "\n" and cx < max_tx:
                        chars[cy][cx] = char
                        styles[cy][cx] = seg.style
                    cx += 1
                    
    for cy in range(max_ty):
        line_text = Text()
        for cx in range(max_tx):
            line_text.append(chars[cy][cx], style=styles[cy][cx])
        c.print(line_text)

test_draw()
