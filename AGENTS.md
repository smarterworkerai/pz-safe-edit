# Instructions for agents working on this repository

- The skill is `skills/pz-safe-edit/`; `SKILL.md` must stay spec-conformant (`python3 tools/validate_skill.py`) and under 500 lines.
- `scripts/safe_edit.py` uses the standard library only and must keep its guarantees: exact-count matching, no write on refusal, path containment, symlink rejection, atomic replace with preserved mode, exit code 2 on refusal.
- Validate with `python3 -m unittest discover -q` and `python3 tools/validate_skill.py`.
- Bump `metadata.version` in `SKILL.md` when the script's behaviour or options change; tag releases `v<version>`.
