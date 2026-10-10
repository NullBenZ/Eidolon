import os
import sys
import shutil
import subprocess
import tempfile
import hashlib
from datetime import datetime
from pathlib import Path
from rich.console import Console
from rich.prompt import Confirm, Prompt
from .diff import compute_diff

console = Console()


def get_file_hash(path: Path) -> str:
    """Returns the SHA256 hash of a file's contents."""
    if not path.exists():
        return ""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        hasher.update(f.read())
    return hasher.hexdigest()


def backup_file(path: Path) -> Path:
    """Creates a timestamped backup of the file in the same directory."""
    if not path.exists():
        return None
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = path.with_name(f"{path.name}.{timestamp}.bak")
    shutil.copy2(path, backup_path)
    return backup_path


def resolve_target(path: Path) -> Path:
    """Resolves symlinks, asking the user for confirmation."""
    if path.is_symlink():
        real_path = path.resolve()
        console.print(f"[yellow]Warning: {path} is a symlink.[/yellow]")
        console.print(f"Real target is: [bold]{real_path}[/bold]")
        if not Confirm.ask("Do you want to edit the real target?"):
            console.print("Aborted.")
            sys.exit(0)
        return real_path
    return path


def check_writable(path: Path):
    """Refuse to edit if the file is not writable."""
    if not os.access(path, os.W_OK):
        console.print(f"[red]Error: File {path} is not writable.[/red]")
        console.print("Explanation: EIDOLON does not use sudo. Please adjust file permissions or run as a different user.")
        sys.exit(1)


def run_editor(path: Path):
    """Opens nano on the given file path using a subprocess list, not a shell string."""
    subprocess.run(["nano", str(path)])


def handle_edit(target_path: str, show_diff: bool = False, debug: bool = False):
    path = Path(target_path)
    if not path.exists():
        console.print(f"[red]Error: File {path} does not exist.[/red]")
        sys.exit(1)

    path = resolve_target(path)
    check_writable(path)

    original_hash = get_file_hash(path)
    original_content = path.read_text()

    with tempfile.TemporaryDirectory() as tempdir:
        temp_path = Path(tempdir) / path.name
        shutil.copy2(path, temp_path)

        while True:
            run_editor(temp_path)

            edited_content = temp_path.read_text()
            if original_content == edited_content:
                console.print("No changes made.")
                return

            diff_text = compute_diff(original_content, edited_content, fromfile=str(path), tofile="edited")
            
            from eidolon.adapters.hyprland import parse_config, parse_hyprctl_monitors, run_checks
            from eidolon.adapters.hyprland.comparator import compare_configs
            from eidolon.report import render_effect_view
            
            old_config = parse_config(original_content)
            new_config = parse_config(edited_content)
            
            def has_hypr_directives(cfg):
                return len(cfg.monitors) > 0 or len(cfg.binds) > 0 or len(cfg.execs) > 0 or len(cfg.sources) > 0
                
            is_hypr = ("hyprland" in path.name.lower()) or has_hypr_directives(old_config) or has_hypr_directives(new_config)
            
            if not is_hypr:
                console.print("\n[bold cyan]Format not supported yet.[/bold cyan]")
                console.print(diff_text)
            else:
                if show_diff:
                    console.print("\n[bold]Raw Diff:[/bold]")
                    console.print(diff_text)
                    
                monitors_info = None
                try:
                    result = subprocess.run(["hyprctl", "monitors"], capture_output=True, text=True)
                    if result.returncode == 0:
                        monitors_info = parse_hyprctl_monitors(result.stdout)
                        if debug:
                            console.print("[dim debug]Parsed monitors from hyprctl:[/dim debug]")
                            for m in monitors_info:
                                console.print(f"[dim debug]- {m.name}: active={m.active_mode}, available={len(m.available_modes)}[/dim debug]")
                except FileNotFoundError:
                    if debug:
                        console.print("[dim debug]hyprctl not found.[/dim debug]")
                    
                new_findings = run_checks(new_config, path.parent, monitors_info)
                changes = compare_configs(old_config, new_config, new_findings)
                
                render_effect_view(changes)

            choice = Prompt.ask("Action", choices=["apply", "discard", "edit again"], default="apply")
            if choice == "discard":
                console.print("Changes discarded.")
                return
            elif choice == "edit again":
                continue
            elif choice == "apply":
                current_hash = get_file_hash(path)
                if current_hash != original_hash:
                    console.print("[red]Conflict: The original file has changed since the session began![/red]")
                    console.print("Aborting to prevent overwriting someone else's changes.")
                    sys.exit(1)

                backup_path = backup_file(path)
                if backup_path:
                    console.print(f"Backup saved to: {backup_path}")
                
                shutil.copy2(temp_path, path)
                console.print("[green]Changes applied successfully.[/green]")
                return


def handle_undo(target_path: str):
    path = Path(target_path)
    if not path.exists():
        console.print(f"[red]Error: File {path} does not exist.[/red]")
        sys.exit(1)
        
    backups = sorted(path.parent.glob(f"{path.name}.*.bak"))
    if not backups:
        console.print(f"[red]No backups found for {path}[/red]")
        sys.exit(1)

    latest_backup = backups[-1]
    console.print(f"Restoring from {latest_backup}")

    # Optionally backup the current state before undoing
    backup_file(path)
    
    shutil.copy2(latest_backup, path)
    console.print("[green]Undo successful. Previous state restored.[/green]")
