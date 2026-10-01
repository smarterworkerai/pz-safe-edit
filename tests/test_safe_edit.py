from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "pz-safe-edit" / "scripts" / "safe_edit.py"
SPEC = importlib.util.spec_from_file_location("safe_edit", SCRIPT)
assert SPEC and SPEC.loader
safe_edit = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = safe_edit
SPEC.loader.exec_module(safe_edit)


class SafeEditTest(unittest.TestCase):
    def _files(self, root: Path, source: str, old: str, new: str) -> tuple[Path, Path, Path]:
        target = root / "target.py"
        old_file = root / "old.txt"
        new_file = root / "new.txt"
        target.write_text(source, encoding="utf-8")
        old_file.write_text(old, encoding="utf-8")
        new_file.write_text(new, encoding="utf-8")
        return target, old_file, new_file

    def test_check_is_read_only_and_diff_is_reviewable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target, old_file, new_file = self._files(root, "before\nOLD\nafter\n", "OLD\n", "NEW\n")
            before = target.read_bytes()
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--root", str(root), "--path", "target.py",
                 "--old-file", str(old_file), "--new-file", str(new_file), "--check", "--diff"],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(target.read_bytes(), before)
            self.assertIn("--- a/target.py", result.stdout)
            self.assertIn("+NEW", result.stdout)
            self.assertIn("safe-edit: checked", result.stderr)

    def test_apply_replaces_one_block_and_preserves_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target, _old_file, _new_file = self._files(root, "before\nOLD\nafter\n", "OLD\n", "NEW\n")
            os.chmod(target, 0o640)
            result, _diff = safe_edit.replace_exact_once(root=root, target="target.py", old="OLD\n", new="NEW\n")
            self.assertTrue(result.changed)
            self.assertEqual(result.matches, 1)
            self.assertEqual(target.read_text(encoding="utf-8"), "before\nNEW\nafter\n")
            self.assertEqual(target.stat().st_mode & 0o777, 0o640)

    def test_refusal_exit_code_is_two_and_non_destructive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target, old_file, new_file = self._files(root, "before\nafter\n", "OLD\n", "NEW\n")
            before = target.read_bytes()
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--root", str(root), "--path", "target.py",
                 "--old-file", str(old_file), "--new-file", str(new_file)],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("found 0", result.stderr)
            self.assertEqual(target.read_bytes(), before)

    def test_zero_match_is_non_destructive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target, _old_file, _new_file = self._files(root, "before\nafter\n", "OLD\n", "NEW\n")
            before = target.read_bytes()
            with self.assertRaisesRegex(safe_edit.EditError, "found 0"):
                safe_edit.replace_exact_once(root=root, target="target.py", old="OLD\n", new="NEW\n")
            self.assertEqual(target.read_bytes(), before)

    def test_multiple_matches_are_non_destructive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target, _old_file, _new_file = self._files(root, "OLD\nOLD\n", "OLD\n", "NEW\n")
            before = target.read_bytes()
            with self.assertRaisesRegex(safe_edit.EditError, "found 2"):
                safe_edit.replace_exact_once(root=root, target="target.py", old="OLD\n", new="NEW\n")
            self.assertEqual(target.read_bytes(), before)

    def test_explicit_expected_count_applies_repeated_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target, _old_file, _new_file = self._files(root, "OLD\nOLD\n", "OLD\n", "NEW\n")
            result, _diff = safe_edit.replace_exact_once(
                root=root, target="target.py", old="OLD\n", new="NEW\n", expected_count=2)
            self.assertEqual((result.matches, target.read_text(encoding="utf-8")), (2, "NEW\nNEW\n"))

    def test_target_cannot_escape_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(safe_edit.EditError, "must remain under root"):
                safe_edit.replace_exact_once(root=root, target="../outside.txt", old="OLD", new="NEW")

    def test_target_symlink_is_rejected_without_touching_its_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "destination.txt"
            destination.write_text("OLD\n", encoding="utf-8")
            (root / "target.txt").symlink_to(destination.name)
            with self.assertRaisesRegex(safe_edit.EditError, "must not be a symlink"):
                safe_edit.replace_exact_once(root=root, target="target.txt", old="OLD\n", new="NEW\n")
            self.assertEqual(destination.read_text(encoding="utf-8"), "OLD\n")

    def test_non_utf8_target_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "binary.bin").write_bytes(b"\xff\xfe OLD \xff")
            with self.assertRaisesRegex(safe_edit.EditError, "not valid UTF-8"):
                safe_edit.replace_exact_once(root=root, target="binary.bin", old="OLD", new="NEW")


if __name__ == "__main__":
    unittest.main()
