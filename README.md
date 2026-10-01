# pz-safe-edit

**An [Agent Skill](https://agentskills.io) for exact, atomic text replacements: the edit is applied only when the old block occurs exactly as expected, and never otherwise.**

[![CI](https://github.com/smarterworkerai/pz-safe-edit/actions/workflows/ci.yml/badge.svg)](https://github.com/smarterworkerai/pz-safe-edit/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

Works with any agent that supports Agent Skills (Claude Code, Codex, Cursor, Gemini CLI, GitHub Copilot, Hermes Agent, …). Python 3.11+, standard library only.

## Why

Agents sometimes lose their native edit tool mid-task, or need to show a reviewer exactly what will change before changing it. Hand-written patches and `git apply --recount` guesses are how files get corrupted. This skill gives the agent one safe primitive instead: an exact-once replacement with a dry run, a unified diff, checksums, and an atomic write.

## What it does

```text
old snippet + new snippet + target file
        │
        ▼
 count exact matches ──≠ expected──▶ refuse (exit 2, nothing written)
        │ = expected
        ▼
 --check: print diff, stop        apply: temp file → fsync → atomic replace, mode preserved
```

Refuses path escapes, symlinks, non-UTF-8 files, and a target that changed between read and write.

## Install

Copy `skills/pz-safe-edit/` into your agent's skills directory:

| Agent | Directory |
|---|---|
| Claude Code | `~/.claude/skills/pz-safe-edit/` (user) or `<repo>/.claude/skills/pz-safe-edit/` (project) |
| Hermes Agent | `<hermes-home>/skills/pz-safe-edit/` |
| Others | see your agent's Agent Skills documentation |

```bash
git clone https://github.com/smarterworkerai/pz-safe-edit.git
cp -r pz-safe-edit/skills/pz-safe-edit ~/.claude/skills/
```

The script also works standalone: `python3 skills/pz-safe-edit/scripts/safe_edit.py --help`.

## Usage

```bash
# 1. preview
python3 scripts/safe_edit.py --root . --path src/app.py \
  --old-file /tmp/old.txt --new-file /tmp/new.txt --check --diff

# 2. apply the identical command without --check
python3 scripts/safe_edit.py --root . --path src/app.py \
  --old-file /tmp/old.txt --new-file /tmp/new.txt --diff
```

| Option | Meaning |
|---|---|
| `--root` | directory the target must stay under (default: current directory) |
| `--path` | target file, relative to `--root` |
| `--old-file` / `--new-file` | UTF-8 snippet files holding the exact old and new blocks |
| `--expected-count N` | required number of exact matches (default 1) |
| `--check` | validate and diff only; write nothing |
| `--diff` | print a unified diff to stdout |

Exit code 0 means checked or applied; 2 means refused, with the reason on stderr.

## Development

```bash
python3 -m unittest discover -q
python3 tools/validate_skill.py
```

## License

MIT
