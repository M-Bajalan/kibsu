#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for `python -m kibsu index` - the deterministic markdown index.

index.py is a builder, not a pass/fail checker: it has no adversarial "defect" to plant, because
its entire job is a pure function of repo state (git commit dates, sorted paths, sorted keys, no
wall-clock stamp - see its own module docstring, "WHY DETERMINISTIC IS A FEATURE, NOT A DETAIL").
Its own EXIT CODES are undocumented as a labeled section, but the source is explicit: `main()`
returns 0 in every normal path, and 3 only if `--verify-determinism` catches two in-process builds
disagreeing.

So the two required tests here are the ones the plan's own table calls for, and they are not the
usual defect/clean pair used for the other seven tools:

  "positive": prove the tool's central claim - determinism - actually holds. Two INDEPENDENT
  `python -m kibsu index --stdout` invocations (separate subprocesses, not the in-process
  `--verify-determinism` self-check, which only ever compares two builds inside the same
  interpreter) must produce byte-identical output for the same repo. `--verify-determinism`
  itself is also exercised, to confirm the tool's own self-check mechanism reports success.

  "negative": per the plan's table, this is not a clean-fixture defect check but the read-only
  guarantee itself - `--stdout` must never write into the repo it indexes.

No tool source file is modified anywhere in this suite; there is deliberately no test here that
forces --verify-determinism to report FAILURE, because the only way to make ns_index.py produce
non-deterministic output would be to change kibsu/index.py itself, which the hard rules forbid.
"""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from support import make_repo, run_tool, assert_repo_untouched

FIXTURE_FILES = {
    "docs/doc1.md": (
        "---\n"
        "type: doc\n"
        "tags:\n"
        "  - alpha\n"
        "  - beta\n"
        "---\n"
        "# Doc 1\n"
        "Some content.\n"
    ),
    "docs/doc2.md": "# Doc 2 (no frontmatter)\nplain content\n",
}


class IndexTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="kibsu_test_index_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_two_independent_runs_are_byte_identical(self):
        """Two SEPARATE subprocess invocations of `index --stdout` against the unchanged repo
        must produce byte-for-byte identical output - the whole point of ns_index.py. This is a
        stronger check than the tool's own in-process `--verify-determinism` (which only ever
        compares two builds inside the same interpreter, in the same call): it would catch a
        real regression like an accidental wall-clock timestamp or an unsorted iteration order
        that happened to be stable only within a single process."""
        repo = make_repo(self.tmpdir, FIXTURE_FILES)

        exit_code_1, stdout_1, stderr_1 = run_tool("index", repo, "--stdout")
        exit_code_2, stdout_2, stderr_2 = run_tool("index", repo, "--stdout")

        self.assertEqual(exit_code_1, 0, "stderr=%r" % stderr_1)
        self.assertEqual(exit_code_2, 0, "stderr=%r" % stderr_2)
        self.assertEqual(stdout_1, stdout_2, "two independent runs produced different output")
        assert_repo_untouched(repo)

    def test_verify_determinism_flag_reports_success(self):
        """The tool's own self-check mechanism (`--verify-determinism`, which builds twice in one
        process and diffs) must report success on an ordinary fixture, exit 0, and print the
        `[ok] determinism` confirmation line."""
        repo = make_repo(self.tmpdir, FIXTURE_FILES)

        exit_code, stdout, stderr = run_tool(
            "index", repo, "--verify-determinism", "--stdout",
        )

        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)
        self.assertIn("[ok] determinism", stdout)
        assert_repo_untouched(repo)

    def test_stdout_mode_writes_nothing_to_the_repo(self):
        """`--stdout` is index.py's read-only mode (the default writes exactly one file,
        `.kibsu/index.json`, into the target repo - see the module docstring). With --stdout,
        nothing must be written anywhere under the repo."""
        repo = make_repo(self.tmpdir, FIXTURE_FILES)

        exit_code, stdout, stderr = run_tool("index", repo, "--stdout")

        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)
        self.assertIn('"schema"', stdout)
        assert_repo_untouched(repo)
        self.assertFalse(
            os.path.exists(os.path.join(repo, ".kibsu", "index.json")),
            "--stdout must not have written .kibsu/index.json",
        )


if __name__ == "__main__":
    unittest.main()
