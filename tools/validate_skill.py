#!/usr/bin/env python3
"""Check the skill against the Agent Skills specification (agentskills.io/specification)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def frontmatter(text: str) -> dict[str, object]:
    if not text.startswith("---\n"):
        raise ValueError("frontmatter must start at byte 0")
    end = text.find("\n---\n", 4)
    if end == -1:
        raise ValueError("frontmatter closing delimiter missing")
    data: dict[str, object] = {}
    current: dict[str, str] | None = None
    folded: str | None = None
    for line in text[4:end].splitlines():
        if folded is not None:
            if line.startswith("  "):
                data[folded] = (str(data[folded]) + " " + line.strip()).strip()
                continue
            folded = None
        if line.startswith("  ") and current is not None:
            key, _, value = line.strip().partition(":")
            current[key.strip()] = value.strip().strip('"')
            continue
        current = None
        key, _, value = line.partition(":")
        value = value.strip()
        if value == ">-":
            data[key] = ""
            folded = key
        elif value == "":
            current = {}
            data[key] = current
        else:
            data[key] = value.strip('"')
    return data


def main() -> int:
    errors: list[str] = []
    for skill_dir in sorted(path for path in SKILLS.iterdir() if path.is_dir()):
        skill = skill_dir / "SKILL.md"
        if not skill.is_file():
            errors.append(f"{skill_dir.name}: SKILL.md missing")
            continue
        text = skill.read_text(encoding="utf-8")
        try:
            meta = frontmatter(text)
        except ValueError as exc:
            errors.append(f"{skill_dir.name}: {exc}")
            continue
        name = str(meta.get("name", ""))
        if name != skill_dir.name or not NAME.fullmatch(name) or len(name) > 64:
            errors.append(f"{skill_dir.name}: name {name!r} must equal the folder and match the spec")
        description = str(meta.get("description", ""))
        if not 1 <= len(description) <= 1024:
            errors.append(f"{skill_dir.name}: description length {len(description)} outside 1..1024")
        compatibility = meta.get("compatibility")
        if compatibility is not None and not 1 <= len(str(compatibility)) <= 500:
            errors.append(f"{skill_dir.name}: compatibility length outside 1..500")
        metadata = meta.get("metadata")
        if metadata is not None and (not isinstance(metadata, dict)
                                     or not all(isinstance(v, str) for v in metadata.values())):
            errors.append(f"{skill_dir.name}: metadata must be a flat string map")
        for forbidden in ("version", "author"):
            if forbidden in meta:
                errors.append(f"{skill_dir.name}: top-level {forbidden!r} belongs under metadata")
        body_lines = text.count("\n")
        if body_lines > 500:
            errors.append(f"{skill_dir.name}: SKILL.md has {body_lines} lines (limit 500)")
        for ref in re.findall(r"`((?:scripts|references|assets)/[^`]+)`", text):
            if not (skill_dir / ref.split()[0]).exists():
                errors.append(f"{skill_dir.name}: referenced file {ref!r} does not exist")
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("OK: skills are spec-conformant")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
