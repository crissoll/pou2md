import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tcpou_to_mermaid.watcher import LockGuard, is_process_running, _scan_files, _get_lock_path


class TestWatcher(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_lock_guard_acquire_and_release(self):
        lock_file = self.test_dir / ".pou2md.lock"
        guard = LockGuard(lock_file)

        self.assertTrue(guard.acquire())
        self.assertTrue(lock_file.exists())
        self.assertEqual(lock_file.read_text(encoding="utf-8").strip(), str(os.getpid()))

        # Clean release
        guard.release()
        self.assertFalse(lock_file.exists())

    def test_lock_guard_detects_active_process(self):
        lock_file = self.test_dir / ".pou2md.lock"
        # Simulate active lock by another process
        lock_file.write_text("12345", encoding="utf-8")

        with patch("tcpou_to_mermaid.watcher.is_process_running", return_value=True):
            guard = LockGuard(lock_file)
            self.assertFalse(guard.acquire())

    def test_lock_guard_overwrites_stale_lock(self):
        lock_file = self.test_dir / ".pou2md.lock"
        # Simulate stale lock by deceased process
        lock_file.write_text("9999999", encoding="utf-8")

        with patch("tcpou_to_mermaid.watcher.is_process_running", return_value=False):
            guard = LockGuard(lock_file)
            self.assertTrue(guard.acquire())
            self.assertEqual(lock_file.read_text(encoding="utf-8").strip(), str(os.getpid()))
            guard.release()

    def test_scan_files_filters_tcpou(self):
        pou1 = self.test_dir / "FB1.TcPOU"
        pou1.write_text("<TcPou/>", encoding="utf-8")
        pou_lower = self.test_dir / "FB3.tcpou"
        pou_lower.write_text("<TcPou/>", encoding="utf-8")

        sub = self.test_dir / "Sub"
        sub.mkdir()
        pou2 = sub / "FB2.TcPOU"
        pou2.write_text("<TcPou/>", encoding="utf-8")

        other = self.test_dir / "readme.md"
        other.write_text("# Hello", encoding="utf-8")

        # Flat scan
        flat_snapshot = _scan_files(self.test_dir, recursive=False)
        self.assertIn(pou1, flat_snapshot)
        self.assertIn(pou_lower, flat_snapshot)
        self.assertNotIn(pou2, flat_snapshot)
        self.assertNotIn(other, flat_snapshot)

        # Recursive scan
        rec_snapshot = _scan_files(self.test_dir, recursive=True)
        self.assertIn(pou1, rec_snapshot)
        self.assertIn(pou2, rec_snapshot)
        self.assertNotIn(other, rec_snapshot)

    def test_scan_files_detects_mtime_changes(self):
        pou = self.test_dir / "FB1.TcPOU"
        pou.write_text("<TcPou/>", encoding="utf-8")
        before = _scan_files(self.test_dir, recursive=False)
        pou.write_text("<TcPou changed='true'/>", encoding="utf-8")
        changed_at = before[pou][0] + 1_000_000
        os.utime(pou, ns=(changed_at, changed_at))
        after = _scan_files(self.test_dir, recursive=False)

        self.assertNotEqual(before[pou], after[pou])

    def test_scan_files_applies_exclusions(self):
        keep = self.test_dir / "Keep.TcPOU"
        skip = self.test_dir / "Skip.TcPOU"
        keep.write_text("<TcPou/>", encoding="utf-8")
        skip.write_text("<TcPou/>", encoding="utf-8")

        snapshot = _scan_files(self.test_dir, recursive=False, exclude=("Skip.TcPOU",))

        self.assertIn(keep, snapshot)
        self.assertNotIn(skip, snapshot)

    def test_get_lock_path(self):
        # When output directory is specified
        p1 = _get_lock_path(self.test_dir, output=str(self.test_dir / "out"))
        self.assertEqual(p1, self.test_dir / "out" / ".pou2md.lock")

        # When output unified file is specified
        p2 = _get_lock_path(self.test_dir, output=str(self.test_dir / "out.md"))
        self.assertEqual(p2, self.test_dir / ".out.md.lock")

if __name__ == "__main__":
    unittest.main()
