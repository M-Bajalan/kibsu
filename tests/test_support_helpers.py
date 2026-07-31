#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for support.py's own assert_vendored_copy_matches_source() guard.

This guard replaces assert_kibsu_not_importable(), which asserted `import kibsu` fails in a
subprocess run from a throwaway repo directory - a precondition that is FALSE the moment kibsu is
pip-installed anywhere on the machine (the maintainer's own machine, any dogfooding contributor's
- not a hypothetical; it is why this file exists). That check was a proxy for a property it never
verified directly: gate.py's and install.py's HOOK templates never run `python -m kibsu` - they
exec a hard-coded path, "$root/.kibsu/bin/<tool>.py", vendored into the repo at install time (see
gate.py's own HOOK comment and install.py's "PORTABLE AS OF v1.1.0" note). Python always runs
exactly the file it is given by path, so once that file's identity is pinned down there is nothing
left to infer about "which copy ran".

A guard that can never fail proves nothing - which is exactly what was wrong with the old one on a
machine with kibsu installed, and exactly what must NOT be true of its replacement. So this module
tests the new guard itself, both ways: it must pass on a genuine match, and it must FAIL - loudly,
with an AssertionError, not a silent pass - on a tampered or missing vendored copy. Every case
below builds its own scratch "source_root" and "repo"; the real kibsu checkout is never touched.
"""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from support import assert_vendored_copy_matches_source


class VendoredCopyGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="kibsu_test_support_helpers_")
        self.source_root = os.path.join(self.tmpdir, "source", "kibsu")
        self.repo = os.path.join(self.tmpdir, "repo")
        os.makedirs(self.source_root)
        os.makedirs(os.path.join(self.repo, ".kibsu", "bin"))

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write(self, path, content):
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)

    # ---- positive: a genuine vendored copy (byte-identical to source) passes silently -----
    def test_passes_when_vendored_copy_matches_source(self):
        self._write(os.path.join(self.source_root, "gate.py"), "print('hello from gate.py')\n")
        self._write(
            os.path.join(self.repo, ".kibsu", "bin", "gate.py"),
            "print('hello from gate.py')\n",
        )

        # must not raise
        assert_vendored_copy_matches_source(self.repo, "gate.py", source_root=self.source_root)

    # ---- negative control: a TAMPERED vendored copy must fail, never pass silently --------
    def test_fails_when_vendored_copy_diverges_from_source(self):
        self._write(os.path.join(self.source_root, "gate.py"), "print('hello from gate.py')\n")
        self._write(
            os.path.join(self.repo, ".kibsu", "bin", "gate.py"),
            "print('a tampered copy, not what shipped')\n",
        )

        with self.assertRaises(AssertionError):
            assert_vendored_copy_matches_source(self.repo, "gate.py", source_root=self.source_root)

    # ---- negative control: an ABSENT vendored copy must fail, never pass silently ---------
    def test_fails_when_vendored_copy_is_absent(self):
        self._write(os.path.join(self.source_root, "gate.py"), "print('hello from gate.py')\n")
        # deliberately do NOT write .kibsu/bin/gate.py - the "moved, deleted, broken reinstall"
        # case gate.py's own HOOK template already fails safe on at commit time; the guard used
        # to prove test preconditions must fail just as loudly when asked about it directly.

        with self.assertRaises(AssertionError):
            assert_vendored_copy_matches_source(self.repo, "gate.py", source_root=self.source_root)

    # ---- multiple tool_names: one bad file among several good ones still fails ------------
    def test_fails_if_any_one_of_several_tool_names_diverges(self):
        self._write(os.path.join(self.source_root, "gate.py"), "print('gate')\n")
        self._write(os.path.join(self.source_root, "config.py"), "print('config')\n")
        self._write(os.path.join(self.repo, ".kibsu", "bin", "gate.py"), "print('gate')\n")
        self._write(os.path.join(self.repo, ".kibsu", "bin", "config.py"), "print('TAMPERED')\n")

        with self.assertRaises(AssertionError):
            assert_vendored_copy_matches_source(
                self.repo, "gate.py", "config.py", source_root=self.source_root,
            )


if __name__ == "__main__":
    unittest.main()
