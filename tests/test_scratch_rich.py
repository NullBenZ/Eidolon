from rich.console import Console
from rich.panel import Panel
from rich.text import Text

def test_canvas():
    c = Console()
    p = Panel("[bold red]Hello[/bold red]", width=10, height=3)
    
    # render
    lines = c.render_lines(p, c.options.update(width=10))
    for line in lines:
        for seg in line:
            print(f"TEXT: {repr(seg.text)} STYLE: {seg.style}")
            
test_canvas()
