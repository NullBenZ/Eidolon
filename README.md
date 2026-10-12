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

Code finds the facts. **Gemma** (via the Gemini API) explains them in plain English and suggests a fix. The status of each finding always comes from code, never from the model, and a basic guard drops an AI explanation that contradicts a verified error. If the AI fails, times out, or you pass `--no-ai`, you still get the full verified report.

### Suggest mode (experimental)

```bash
eidolon suggest ~/.config/hypr/monitors.conf "set my screen to 1920x1200 at 60Hz with scale 1"
```

**Gemma proposes, code verifies, you approve.**

1. Gemma proposes config lines from your plain-English request.
2. Each line passes a safety filter first: it must be a single `monitor` line, with no shell chaining.
3. The lines go into the temp copy only, then run through the same checks as a manual edit.
4. The change is labeled **AI-suggested**. An AI suggestion is never VERIFIED. Only code checks produce VERIFIED.
5. You choose apply, discard, or edit again.

Gemma can suggest wrong values. The checks catch what they know about (for example, an unsupported monitor mode), so read every suggestion before you apply it. Currently limited to Hyprland monitor lines. Anything else prints "not supported yet" and changes nothing.

### Layout preview

For monitor changes, Eidolon draws a schematic BEFORE / AFTER layout in the terminal. It is **not a screenshot**. Box sizes come from resolution divided by scale, and the layout is labeled LIKELY. If the new mode isn't available on your screen, the AFTER box turns red, and that part is VERIFIED.

## Safety

- Edits happen on a temp copy, never the real file.
- Before applying, Eidolon checks a SHA-256 hash of the original. If something else changed the file, it refuses to apply.
- Every apply makes a timestamped `.bak` backup.
- `eidolon undo PATH` restores from backups, newest first. Each backup is used once.
- `nano` is launched without a shell. Config contents are never executed.
- No sudo is used.
- The API key is read from `.env` (which is git-ignored) and is never printed in error messages.

## Install

Requires Python 3.10 or newer (developed on 3.14) and `nano`. The Hyprland checks use `hyprctl`.

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
eidolon edit ~/.config/hypr/hyprland.conf      # edit with checks
eidolon edit PATH --no-ai                       # fully offline, verified checks only
eidolon edit PATH --show-diff                   # also show the raw line diff
eidolon suggest PATH "plain-English request"    # AI proposes, code verifies (experimental)
eidolon undo PATH                               # restore the most recent unused backup
eidolon doctor [--test-ai]                      # check dependencies and AI setup
```

## What the Hyprland adapter checks

- Monitor mode vs the modes `hyprctl monitors` reports for your screen
- Duplicate keybinds across the whole file
- Commands in `exec`, `exec-once` and `bind ... exec` lines exist in your PATH
- `source = ...` paths exist
- `$variables` expand correctly
- Lines it does not understand are reported as UNKNOWN or shown as a raw diff, never silently dropped as safe

## Status

**Working and tested by hand:**
- Safe edit flow: temp copy, hash check, apply, discard, and backup
- Apply never happens on a bare Enter
- Undo of the latest change, including after `suggest`
- Monitor mode, duplicate bind, and command-in-PATH checks
- Checks work in separately sourced keybind files (valid syntax)
- Schematic layout preview for monitor changes
- Gemma explanations, with fallback to verified-only output
- `eidolon suggest` for monitor lines: valid proposals, unsupported-mode flagging, and out-of-scope requests

**In progress or not fully verified:**
- Undo across several applies (covered by automated tests; manual testing still ongoing)
- Malformed bind lines in sourced files (for example `Super+T` instead of `SUPER, T`) fall back to a raw diff and are not yet reported as UNKNOWN
- Exec lines with a `[rule]` prefix or `VAR=value` prefix may be misreported
- Hyprland submaps are not specially handled (untested)
- Duplicate-bind cards are not grouped into one card in every case
- The Gemma call sometimes times out on the free tier. The tool falls back to verified-only output.
- Layout preview boxes can get tall on small terminals
- `suggest` supports monitor lines only, and "edit again" inside `suggest` reopens the original file, not the AI's proposal
- No check yet for removing your last terminal-launching keybind

## Limits

Eidolon lowers risk. It does not guarantee a config is safe. The parser understands only part of Hyprland's syntax, and anything else is reported as UNKNOWN or shown as a raw diff. It will never turn a finding it cannot prove into a VERIFIED one. It has only been tested on Arch Linux with Hyprland.

**Privacy:** AI explanations send the changed settings and check results to the Gemini API. `suggest` sends your request plus your existing monitor lines (or the file's non-comment lines if there are none). `--no-ai` sends nothing.

## Development

```bash
pip install -e ".[dev]"
pytest
```

## Roadmap

- Local model support (Ollama), so configs never leave your machine
- `suggest` for keybinds and startup commands
- More adapters: SSH, systemd, Git
- A check for removing your last terminal-launching keybind

## Contributing

Adapters are the extension point. Each one is a parser plus a set of checks, with tests. Look in `eidolon/adapters/` and open an issue or a pull request.

## License

MIT. See `LICENSE`.

---

Built at Hacktoberfest Hack Day Amaravati x FOSS SRM AP.
