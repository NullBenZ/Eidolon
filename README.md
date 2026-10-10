# Eidolon

**See the consequences before you commit the change.**

Eidolon is a safety layer for editing Linux config files. You edit a temporary copy, and before anything touches the real file, Eidolon checks your changes against the real state of your machine and shows what will happen.

Right now it has an adapter for **Hyprland**. The design lets anyone add more.

## The problem

One wrong line in a config can break your desktop, and you usually find out after you save. Tools like `hyprctl configerrors` only check a config that is already loaded. Eidolon checks the draft *before* it is applied, using facts from your actual machine (for example, which monitor modes your screen really supports).

## How it works

1. `eidolon edit PATH` resolves symlinks (so dotfile and stow setups work) and copies the file to a temp location.
2. It opens the copy in `nano`.
3. When you exit, it compares old and new as structured settings, not as a raw text diff.
4. It runs checks against your real machine.
5. It shows an **Effect View**: a BEFORE / AFTER card for each changed setting, with a status.
6. You choose: apply, discard, or edit again. Nothing is applied by default.

Every finding has one of three labels:

| Label | Meaning |
|---|---|
| **VERIFIED** | Proven by code on your machine. |
| **LIKELY** | A reasonable inference, not proven. |
| **UNKNOWN** | Eidolon has no rule for it and makes no claim. |

### Where AI fits

Code finds the facts. **Gemma** (via the Gemini API) only explains them in plain English and suggests a fix. It never decides what is true. If the AI fails, times out, or you pass `--no-ai`, you still get the full verified report.

## Safety

- Edits happen on a temp copy, never the real file.
- Before applying, Eidolon checks a SHA-256 hash of the original. If something else changed the file, it refuses to apply.
- Every apply makes a timestamped `.bak` backup.
- `eidolon undo PATH` restores from backups.
- `nano` is launched without a shell. Config contents are never executed.
- No sudo is used.

## Install

Requires Python 3 (developed on 3.14) and `nano`. The Hyprland checks use `hyprctl`.

```bash
git clone https://github.com/NullBenZ/Eidolon.git
cd Eidolon
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

For AI explanations, copy the example env file and add your Gemini API key:

```bash
cp .env.example .env
# edit .env and set GEMINI_API_KEY
```

Check your setup:

```bash
eidolon doctor
eidolon doctor --test-ai
```

## Usage

```bash
eidolon edit ~/.config/hypr/hyprland.conf     # edit with checks
eidolon edit PATH --no-ai                      # fully offline, verified checks only
eidolon edit PATH --show-diff                  # also show the raw line diff
eidolon undo PATH                              # restore the most recent unused backup
```

## What the Hyprland adapter checks

- Monitor mode vs the modes `hyprctl monitors` reports for your screen
- Duplicate keybinds across the whole file
- Commands in `exec` and `exec-once` lines exist in your PATH
- `source = ...` paths exist
- `$variables` expand correctly
- Lines it does not understand are reported as UNKNOWN, never silently dropped

## Status

**Working and tested by hand:**
- Safe edit flow: temp copy, hash check, apply, discard, and backup
- Apply never happens on a bare Enter
- Undo of the latest change
- Hyprland checks listed above
- Gemma explanations, with fallback to verified-only output

**In progress or not fully verified:**
- Undo across several applies (covered by automated tests; manual testing still ongoing)
- Keybinds defined in separately sourced files
- Duplicate-bind cards are not grouped into one card in every case
- The Gemma call sometimes times out on the free tier. The tool falls back to verified-only output.
- No check yet for removing your last terminal-launching keybind

## Limits

Eidolon lowers risk. It does not guarantee a config is safe. The parser understands only part of Hyprland's syntax, and anything else is reported as UNKNOWN. It will never turn a finding it cannot prove into a VERIFIED one.

## Roadmap

- Local model support (Ollama), so configs never leave your machine
- More adapters: SSH, systemd, Git
- A schematic layout preview for monitor changes

## Contributing

Adapters are the extension point. Each one is a parser plus a set of checks, with tests. Look in `eidolon/adapters/` and open an issue or a pull request.

## License

MIT. See `LICENSE`.

---

Built at Hacktoberfest Hack Day Amaravati x FOSS SRM AP.
