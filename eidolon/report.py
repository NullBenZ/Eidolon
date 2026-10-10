from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from typing import List, Optional
import re
from eidolon.adapters.hyprland.comparator import ConfigChange

console = Console()

class ParsedMon:
    def __init__(self, name: str, w: int, h: int, x: int, y: int, scale: float, res_str: str, pos_str: str, scale_str: str):
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
    m = re.match(r"Res:\s*(.*?)\s*\|\s*Pos:\s*(.*?)\s*\|\s*Scale:\s*(.*)", state_str)
    if not m: return None
    res, pos, scale_str = m.groups()
    
    res_m = re.match(r"(\d+)x(\d+)(?:@([\d.]+))?", res)
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

def _draw_scene(mons: List[ParsedMon], title: str, console_obj: Console, scale_factor: float):
    if not mons:
        return
        
    for m in mons:
        m.term_w = max(25, int((m.w / m.scale) * scale_factor))
        m.term_h = max(8, int((m.h / m.scale) * scale_factor / 2))
        m.term_x = int(m.x * scale_factor)
        m.term_y = int(m.y * scale_factor / 2)
        
    max_tx = max((m.term_x + m.term_w for m in mons), default=0)
    max_ty = max((m.term_y + m.term_h for m in mons), default=0)
    
    if max_tx == 0 or max_ty == 0:
        return
        
    chars = [[" " for _ in range(max_tx)] for _ in range(max_ty)]
    styles = [[None for _ in range(max_tx)] for _ in range(max_ty)]
    
    c = Console()
    for m in mons:
        content = f"[bold]{m.name}[/bold]\n{m.res_str}\nPos: {m.pos_str}\nScale: {m.scale_str}"
        style = "blue"
        if m.is_after and m.is_error:
            style = "red"
            content += f"\n\n[red]{m.error_text} (verified)[/red]"
            
        p = Panel(content, width=m.term_w, height=m.term_h, style=style)
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
                    
    console_obj.print(f"[bold]{title}[/bold]")
    for cy in range(max_ty):
        line_text = Text()
        for cx in range(max_tx):
            line_text.append(chars[cy][cx], style=styles[cy][cx])
        console_obj.print(line_text)
    console_obj.print()

def _render_layout_preview(changes: List[ConfigChange], console_obj: Console):
    before_mons = []
    after_mons = []
    
    for ch in changes:
        if ch.category == "Monitor":
            if ch.before_state:
                b_mon = _parse_monitor_state(ch.before_state, ch.item_id)
                if not b_mon: return # parse failed, abort preview
                before_mons.append(b_mon)
                
            if ch.after_state:
                a_mon = _parse_monitor_state(ch.after_state, ch.item_id)
                if not a_mon: return # parse failed, abort preview
                a_mon.is_after = True
                errors = [f for f in ch.findings if f.severity.value == "ERROR"]
                if errors:
                    a_mon.is_error = True
                    a_mon.error_text = errors[0].evidence
                after_mons.append(a_mon)

    if not before_mons and not after_mons:
        return
        
    max_eff_x = 1
    for m in before_mons + after_mons:
        max_eff_x = max(max_eff_x, m.x + (m.w / m.scale))
        
    term_width_cap = min(console_obj.width - 2 if console_obj.width else 80, 80)
    scale_factor = term_width_cap / max_eff_x
        
    console_obj.print("[bold cyan]Layout preview (schematic, not a screenshot) [LIKELY][/bold cyan]\n")
    if before_mons:
        _draw_scene(before_mons, "BEFORE", console_obj, scale_factor)
    if after_mons:
        _draw_scene(after_mons, "AFTER", console_obj, scale_factor)

def render_effect_view(changes: List[ConfigChange], overall_summary: str = None):
    if not changes:
        console.print("[green]No semantic changes detected.[/green]")
        return
        
    console.print("\n[bold cyan]=== EFFECT VIEW ===[/bold cyan]\n")
    
    _render_layout_preview(changes, console)
    
    if overall_summary and len(changes) >= 2:
        console.print(Panel(f"[italic]{overall_summary}[/italic]", title="AI Summary", border_style="magenta", padding=(0, 2)))
        console.print()
    
    for change in changes:
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column(style="dim", width=12)
        table.add_column()
        
        # Category & Item
        item_text = f"[bold]{change.category}:[/bold] {change.item_id}"
        table.add_row("ITEM", item_text)
        
        # Before / After
        if change.before_state and change.after_state:
            table.add_row("BEFORE", f"[red]{change.before_state}[/red]")
            table.add_row("AFTER", f"[green]{change.after_state}[/green]")
        elif change.after_state:
            table.add_row("ADDED", f"[green]{change.after_state}[/green]")
        elif change.before_state:
            table.add_row("REMOVED", f"[red]{change.before_state}[/red]")
            
        # Status (Findings)
        if change.findings:
            status_texts = []
            for f in change.findings:
                color = "red" if f.severity.value == "ERROR" else "yellow" if f.severity.value == "WARNING" else "blue"
                status_texts.append(f"[{color}][{f.label.value}][/] {f.evidence}")
            table.add_row("STATUS", "\n".join(status_texts))
        else:
            if change.category == "Monitor":
                table.add_row("STATUS", "[green][OK][/green] Checked: Monitor mode")
            elif change.category == "Keybind":
                table.add_row("STATUS", "[green][OK][/green] Checked: Duplicates, Exec paths")
            elif change.category == "Startup":
                table.add_row("STATUS", "[green][OK][/green] Checked: Exec paths")
            elif change.category == "Source":
                table.add_row("STATUS", "[green][OK][/green] Checked: File exists")
            elif change.category == "Unknown":
                table.add_row("STATUS", "[yellow][UNKNOWN][/yellow] Not checked: Directive not understood")
            else:
                table.add_row("STATUS", "[green][OK][/green] No issues found.")
            
        # AI Meaning
        if change.meaning:
            table.add_row("MEANING", f"[magenta]Predicted effect (AI):[/magenta] {change.meaning}")
        # AI Fix
        if getattr(change, "fix", None):
            table.add_row("FIX", f"[magenta]AI Suggestion:[/magenta] {change.fix}")
            
        panel = Panel(table, border_style="cyan", padding=(1, 2))
        console.print(panel)
        console.print()
