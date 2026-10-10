from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from typing import List
from eidolon.adapters.hyprland.comparator import ConfigChange

console = Console()

def render_effect_view(changes: List[ConfigChange]):
    if not changes:
        console.print("[green]No semantic changes detected.[/green]")
        return
        
    console.print("\n[bold cyan]=== EFFECT VIEW ===[/bold cyan]\n")
    
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
            table.add_row("MEANING", f"[italic]{change.meaning}[/italic]")
            
        panel = Panel(table, border_style="cyan", padding=(1, 2))
        console.print(panel)
        console.print()
