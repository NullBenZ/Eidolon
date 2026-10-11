import os
import sys
import shutil
import subprocess
import tempfile
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Tuple
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
    counter = 1
    while backup_path.exists():
        backup_path = path.with_name(f"{path.name}.{timestamp}_{counter}.bak")
        counter += 1
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


def handle_edit(target_path: str, show_diff: bool = False, debug: bool = False, no_ai: bool = False):
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
                
                # --- AI Explanation ---
                ai_err = None
                overall_summary = None
                if not no_ai and changes:
                    from eidolon.ai import GemmaProvider, changes_to_ai_items, _is_contradiction
                    provider = GemmaProvider()
                    if not provider.is_configured:
                        ai_err = "API key not configured"
                    else:
                        items = changes_to_ai_items(changes)
                        
                        import time
                        start_time = time.time()
                        reply = None
                        
                        try:
                            with console.status("[dim]Asking Gemma... (Ctrl+C to skip)[/dim]"):
                                reply, ai_err = provider.explain(items)
                                if not reply and "Skipped" not in str(ai_err):
                                    if debug:
                                        console.print(f"[dim debug]AI call failed ({ai_err}), retrying once...[/dim debug]")
                                    reply, ai_err = provider.explain(items)
                        except KeyboardInterrupt:
                            ai_err = "Skipped by user"
                            console.print("\n[yellow]AI explanation skipped.[/yellow]")
                            
                        if debug:
                            elapsed = time.time() - start_time
                            console.print(f"[dim debug]AI call took {elapsed:.2f} seconds[/dim debug]")

                        if reply:
                            overall_summary = reply.overall
                            meaning_map = {eff.id: eff.meaning for eff in reply.effects}
                            fix_map = {eff.id: eff.fix for eff in reply.effects}
                            for ch in changes:
                                ch_id = f"{ch.category}:{ch.item_id}"
                                if ch_id in meaning_map:
                                    meaning = meaning_map[ch_id]
                                    if _is_contradiction(meaning, ch.findings):
                                        pass
                                    else:
                                        ch.meaning = meaning
                                        ch.fix = fix_map.get(ch_id)

                render_effect_view(changes, overall_summary)
                if ai_err:
                    console.print(f"[dim]AI explanation unavailable ({ai_err}). Showing verified checks only.[/dim]\n")

            import termios
            import sys
            if sys.stdin.isatty():
                try:
                    termios.tcflush(sys.stdin, termios.TCIFLUSH)
                except Exception:
                    pass

            while True:
                choice = Prompt.ask("Action", choices=["apply", "a", "discard", "d", "edit again", "e"])
                if choice in ["a", "apply"]:
                    choice = "apply"
                elif choice in ["d", "discard"]:
                    choice = "discard"
                elif choice in ["e", "edit again"]:
                    choice = "edit again"
                break
                
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
    if path.name.endswith(".bak"):
        console.print("[red]pass the original file path[/red]")
        sys.exit(1)
        
    if not path.exists():
        console.print(f"[red]Error: File {path} does not exist.[/red]")
        sys.exit(1)
        
    backups = sorted(path.parent.glob(f"{path.name}.*.bak"))
    if not backups:
        console.print("[red]nothing left to undo[/red]")
        sys.exit(1)

    latest_backup = backups[-1]
    console.print(f"Restoring from {latest_backup.name}")

    # Backup the current state before undoing using .pre-undo suffix
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pre_undo_path = path.with_name(f"{path.name}.{timestamp}.pre-undo")
    shutil.copy2(path, pre_undo_path)
    
    shutil.copy2(latest_backup, path)
    
    # Mark the used backup as .restored
    restored_path = latest_backup.with_suffix(".restored")
    latest_backup.rename(restored_path)
    
    console.print("[green]Undo successful. Previous state restored.[/green]")


def handle_doctor(test_ai: bool = False):
    """Check system dependencies and configuration."""
    console.print("[bold cyan]=== EIDOLON DOCTOR ===[/bold cyan]\n")
    
    # 1. Nano
    nano_path = shutil.which("nano")
    if nano_path:
        console.print(f"[green]✓[/green] nano installed ({nano_path})")
    else:
        console.print("[red]✗[/red] nano not found in PATH")
        
    # 2. Hyprctl
    hyprctl_path = shutil.which("hyprctl")
    if hyprctl_path:
        console.print(f"[green]✓[/green] hyprctl installed ({hyprctl_path})")
    else:
        console.print("[yellow]![/yellow] hyprctl not found (monitor checks will fall back to UNKNOWN)")
        
    # 3. AI Config
    from eidolon.ai import GemmaProvider
    provider = GemmaProvider()
    if provider.is_configured:
        console.print(f"[green]✓[/green] Gemma API key configured (model: {provider.model_name})")
        if test_ai:
            with console.status("[dim]Testing AI connection...[/dim]"):
                ok, msg = provider.test_connection()
            if ok:
                console.print(f"  [green]✓ Test call successful:[/green] {msg}")
            else:
                console.print(f"  [red]✗ Test call failed:[/red] {msg}")
    else:
        console.print("[yellow]![/yellow] Gemma API key not configured. AI predictions will be disabled.")


# ---------------------------------------------------------------------------
# Safety filter for AI-suggested lines
# ---------------------------------------------------------------------------

_SHELL_CHAIN_CHARS = {";", "&&", "||", "|"}

def _filter_suggested_lines(lines: List[str]) -> Tuple[List[str], List[str]]:
    """
    Validate AI-suggested lines. Returns (accepted, rejected_reasons).
    Only monitor lines are in scope.
    """
    accepted = []
    rejected = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            rejected.append(f"Empty line rejected")
            continue
        if "\n" in stripped:
            rejected.append(f"Rejected (multi-statement): {stripped[:60]}")
            continue
        if not stripped.startswith("monitor"):
            rejected.append(f"Rejected (not a monitor line): {stripped[:60]}")
            continue
        # Check for shell chaining characters anywhere in the line
        for ch in _SHELL_CHAIN_CHARS:
            if ch in stripped:
                rejected.append(f"Rejected (shell chaining '{ch}'): {stripped[:60]}")
                break
        else:
            accepted.append(stripped)
    return accepted, rejected


def _apply_suggestion_to_content(original_content: str, accepted_lines: List[str]) -> str:
    """
    Apply accepted monitor lines to file content.
    If a line for the same monitor name exists, replace it. Otherwise append.
    """
    import re
    result_lines = original_content.splitlines()
    used = set()

    for new_line in accepted_lines:
        # Extract monitor name from the suggested line
        m = re.match(r'^monitor\s*=\s*([^,]+)', new_line)
        if not m:
            result_lines.append(new_line)
            continue
        mon_name = m.group(1).strip()

        replaced = False
        for i, existing in enumerate(result_lines):
            existing_stripped = existing.strip()
            em = re.match(r'^monitor\s*=\s*([^,]+)', existing_stripped)
            if em and em.group(1).strip() == mon_name and i not in used:
                result_lines[i] = new_line
                used.add(i)
                replaced = True
                break
        if not replaced:
            result_lines.append(new_line)

    return "\n".join(result_lines)


def handle_suggest(target_path: str, request: str, no_ai: bool = False, debug: bool = False):
    """Handle the 'eidolon suggest' command."""
    if no_ai:
        console.print("[yellow]The suggest command needs AI. Use without --no-ai.[/yellow]")
        return

    path = Path(target_path)
    if not path.exists():
        console.print(f"[red]Error: File {path} does not exist.[/red]")
        sys.exit(1)

    path = resolve_target(path)
    check_writable(path)

    original_hash = get_file_hash(path)
    original_content = path.read_text()

    # Scope guard: only monitor requests are supported
    monitor_keywords = ["monitor", "resolution", "display", "screen", "scale", "refresh", "hz"]
    if not any(kw in request.lower() for kw in monitor_keywords):
        console.print("[yellow]Not supported yet.[/yellow] The suggest command currently handles monitor changes only.")
        return

    # Extract relevant context lines (existing monitor lines)
    from eidolon.adapters.hyprland import parse_config
    old_config = parse_config(original_content)
    context_lines = [m.raw_line for m in old_config.monitors]
    if not context_lines:
        # No existing monitors — give all lines as context so AI knows the file
        context_lines = [l for l in original_content.splitlines() if l.strip() and not l.strip().startswith("#")]

    # --- AI call ---
    from eidolon.ai import GemmaProvider, SuggestionReply
    provider = GemmaProvider()
    if not provider.is_configured:
        console.print("[red]AI unavailable: API key not configured. Cannot run suggest.[/red]")
        return

    import time
    start_time = time.time()
    reply = None
    ai_err = None

    try:
        with console.status("[dim]Asking Gemma for suggestions... (Ctrl+C to skip)[/dim]"):
            reply, ai_err = provider.suggest(request, context_lines)
            if not reply and ai_err and "Skipped" not in ai_err:
                if debug:
                    console.print(f"[dim debug]AI call failed ({ai_err}), retrying once...[/dim debug]")
                reply, ai_err = provider.suggest(request, context_lines)
    except KeyboardInterrupt:
        console.print("\n[yellow]AI suggestion skipped.[/yellow]")
        return

    if debug:
        elapsed = time.time() - start_time
        console.print(f"[dim debug]AI call took {elapsed:.2f} seconds[/dim debug]")

    if not reply:
        console.print(f"[red]AI failed: {ai_err}. No changes made.[/red]")
        return

    if not reply.lines:
        console.print(f"[yellow]AI returned no suggestions.[/yellow]")
        if reply.explanation:
            console.print(f"Reason: {reply.explanation}")
        return

    if reply.explanation:
        console.print(f"\n[bold]AI explanation:[/bold] {reply.explanation}\n")

    # --- Safety filter ---
    accepted, rejected = _filter_suggested_lines(reply.lines)
    if rejected:
        for r in rejected:
            console.print(f"[red]⚠ {r}[/red]")
    if not accepted:
        console.print("[red]All suggested lines were rejected by the safety filter. No changes made.[/red]")
        return

    console.print(f"[green]Accepted {len(accepted)} suggested line(s).[/green]")
    for line in accepted:
        console.print(f"  [dim]→[/dim] {line}")
    console.print()

    # --- Apply to temp copy and run checks ---
    with tempfile.TemporaryDirectory() as tempdir:
        temp_path = Path(tempdir) / path.name
        edited_content = _apply_suggestion_to_content(original_content, accepted)
        temp_path.write_text(edited_content)

        diff_text = compute_diff(original_content, edited_content, fromfile=str(path), tofile="AI-suggested")

        from eidolon.adapters.hyprland import parse_config, parse_hyprctl_monitors, run_checks
        from eidolon.adapters.hyprland.comparator import compare_configs
        from eidolon.report import render_effect_view

        new_config = parse_config(edited_content)

        monitors_info = None
        try:
            result = subprocess.run(["hyprctl", "monitors"], capture_output=True, text=True)
            if result.returncode == 0:
                monitors_info = parse_hyprctl_monitors(result.stdout)
        except FileNotFoundError:
            if debug:
                console.print("[dim debug]hyprctl not found.[/dim debug]")

        new_findings = run_checks(new_config, path.parent, monitors_info)
        changes = compare_configs(old_config, new_config, new_findings)

        if not changes:
            console.print("[green]No semantic changes detected.[/green]")
            return

        # Label all changes as AI-suggested
        for ch in changes:
            ch.meaning = f"[AI-suggested] {ch.meaning}" if ch.meaning else "[AI-suggested]"

        render_effect_view(changes)
        console.print("[dim italic]Note: AI suggestions are never VERIFIED. Only code checks produce VERIFIED status.[/dim italic]\n")

        # --- Prompt (no default, stdin flush) ---
        import termios
        if sys.stdin.isatty():
            try:
                termios.tcflush(sys.stdin, termios.TCIFLUSH)
            except Exception:
                pass

        while True:
            choice = Prompt.ask("Action", choices=["apply", "a", "discard", "d", "edit again", "e"])
            if choice in ["a", "apply"]:
                choice = "apply"
            elif choice in ["d", "discard"]:
                choice = "discard"
            elif choice in ["e", "edit again"]:
                choice = "edit again"
            break

        if choice == "discard":
            console.print("Changes discarded.")
            return
        elif choice == "edit again":
            # Hand off to the normal edit flow with the suggested content as starting point
            shutil.copy2(temp_path, Path(tempdir) / "edit_copy")
            edit_copy = Path(tempdir) / "edit_copy"
            shutil.copy2(temp_path, edit_copy)
            console.print("[dim]Opening editor with the AI suggestion applied...[/dim]")
            handle_edit(str(path), debug=debug)
            return
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
            console.print("[green]AI suggestion applied successfully.[/green]")
            return
