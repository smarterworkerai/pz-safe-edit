#!/usr/bin/env python3
"""Apply one exact UTF-8 text replacement safely and atomically.

This is a deterministic fallback for an unavailable agent-native patch tool. It
is intentionally not a fuzzy patch engine: the expected old text must occur the
configured number of times (one by default), otherwise no target write occurs.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import os
import stat
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


class EditError(RuntimeError):
    """Raised when the exact-once edit contract cannot be met."""


@dataclass(frozen=True)
class EditResult:
    path: Path
    matches: int
    before_sha256: str
    after_sha256: str
    changed: bool


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_utf8(path: Path, label: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise EditError(f"{label} does not exist: {path}") from exc
    except UnicodeDecodeError as exc:
        raise EditError(f"{label} is not valid UTF-8: {path}") from exc


def _resolve_target(root: Path, requested: str) -> Path:
    root = root.resolve()
    requested_path = Path(requested)
    lexical_candidate = requested_path if requested_path.is_absolute() else root / requested_path
    if lexical_candidate.is_symlink():
        raise EditError(f"target must not be a symlink: {requested}")
    candidate = lexical_candidate.resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise EditError(f"target must remain under root {root}: {requested}") from exc
    if not candidate.is_file():
        raise EditError(f"target is not a regular file: {requested}")
    return candidate


def _atomic_write(path: Path, content: bytes, expected_stat: os.stat_result) -> None:
    current_stat = path.stat()
    if (current_stat.st_dev, current_stat.st_ino, current_stat.st_size, current_stat.st_mtime_ns) != (
        expected_stat.st_dev,
        expected_stat.st_ino,
        expected_stat.st_size,
        expected_stat.st_mtime_ns,
    ):
        raise EditError(f"target changed after it was read: {path}")

    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".safe-edit", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as temporary:
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.chmod(temporary_path, stat.S_IMODE(expected_stat.st_mode))
        os.replace(temporary_path, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def replace_exact_once(
    *, root: Path, target: str, old: str, new: str, expected_count: int = 1, check: bool = False
) -> tuple[EditResult, str]:
    if expected_count < 1:
        raise EditError("expected count must be at least one")
    if not old:
        raise EditError("old text must not be empty")

    target_path = _resolve_target(root, target)
    expected_stat = target_path.stat()
    before_bytes = target_path.read_bytes()
    try:
        before = before_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise EditError(f"target is not valid UTF-8: {target}") from exc

    matches = before.count(old)
    if matches != expected_count:
        raise EditError(f"expected {expected_count} exact match(es), found {matches}: {target}")

    after = before.replace(old, new)
    after_bytes = after.encode("utf-8")
    diff = "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"a/{target_path.relative_to(root.resolve())}",
            tofile=f"b/{target_path.relative_to(root.resolve())}",
        )
    )
    result = EditResult(
        path=target_path,
        matches=matches,
        before_sha256=_sha256(before_bytes),
        after_sha256=_sha256(after_bytes),
        changed=before_bytes != after_bytes,
    )
    if not check and result.changed:
        _atomic_write(target_path, after_bytes, expected_stat)
    return result, diff


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="repository root; defaults to the current directory")
    parser.add_argument("--path", required=True, help="UTF-8 target file path, relative to --root")
    parser.add_argument("--old-file", required=True, help="file containing the exact old UTF-8 block")
    parser.add_argument("--new-file", required=True, help="file containing the replacement UTF-8 block")
    parser.add_argument("--expected-count", type=int, default=1, help="required exact old-block count (default: 1)")
    parser.add_argument("--check", action="store_true", help="validate only; do not write the target")
    parser.add_argument("--diff", action="store_true", help="print a unified diff to stdout")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        old = _read_utf8(Path(args.old_file), "old-text file")
        new = _read_utf8(Path(args.new_file), "new-text file")
        result, diff = replace_exact_once(
            root=Path(args.root),
            target=args.path,
            old=old,
            new=new,
            expected_count=args.expected_count,
            check=args.check,
        )
    except EditError as exc:
        print(f"safe-edit: error: {exc}", file=sys.stderr)
        return 2

    if args.diff:
        sys.stdout.write(diff)
    mode = "checked" if args.check else "applied"
    print(
        f"safe-edit: {mode} path={result.path} matches={result.matches} "
        f"before_sha256={result.before_sha256} after_sha256={result.after_sha256}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
