---
name: pz-safe-edit
description: >-
  Applies one exact, reviewed text replacement to a UTF-8 file atomically, refusing
  when the old block does not occur exactly the expected number of times. Use as the
  deterministic fallback when the agent's native edit or patch tool is unavailable or
  has failed, when an edit must be previewed as a diff before it is written, or when
  a change must never be applied fuzzily. Not for broad refactors or binary files.
license: MIT
compatibility: Requires Python 3.11 or newer; no third-party packages.
metadata:
  suite: pz-safe-edit
  version: "1.0.0"
  author: smarterworkerai
---

# Safe edit

Replace exactly one occurrence (or an explicitly stated count) of an old text block with a new one. Zero or extra matches, a non-UTF-8 file, a symlink, or a path outside `--root` mean nothing is written.

## When to use

- The native edit or patch tool is unavailable, or it failed and you have its exact error text.
- An edit must be reviewed as a unified diff before it is applied.
- The replacement must be exact; approximate or whole-file rewrites are not acceptable.

Do not use it for multi-file or structural refactors (use a codemod with a dry run), or for files that are not UTF-8 text.

## Steps

1. Read the current target block immediately before editing; copy it verbatim into an "old" snippet file and write the replacement into a "new" snippet file.
2. Preview:
   ```bash
   python3 scripts/safe_edit.py --root . --path path/to/file.py \
     --old-file /tmp/old.txt --new-file /tmp/new.txt --check --diff
   ```
3. Review the diff. If the tool reports `found 0` or `found 2`, re-read the file and fix the snippet; never lower `--expected-count` just to make the edit apply.
4. Apply by running the identical command without `--check`.
5. Run `git diff --check` and the narrowest relevant test.

`--expected-count N` is for a deliberately repeated replacement you have verified independently; it is not a fuzzy mode.

## Guarantees

- Resolves the target under `--root`; rejects path escapes and symlinks; requires a regular UTF-8 file.
- Counts exact matches before touching anything.
- Writes through a same-directory temporary file, `fsync`, and atomic `os.replace`; preserves the file mode; aborts if the file changed between read and write.
- Prints `before_sha256` and `after_sha256` on stderr for the status report; the diff goes to stdout only with `--diff`.
- Exit code 0 on success (checked or applied), 2 on any refusal.

## Reporting

State the path, the match count, both checksums, and whether the run was `checked` or `applied`. If you fell back to this tool because a native tool failed, quote that tool's exact error.
