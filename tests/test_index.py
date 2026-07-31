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

    def test_nonexistent_path_cannot_run_and_creates_nothing(self):
        """main() must validate the target path before build()/write - the same guard
        discover.py already has for the identical input (`if not os.path.isdir(root): print
        "CANNOT RUN: ... is not a directory"; return CANNOT_RUN`, discover.py lines ~129-130).

        Without that guard, `python -m kibsu index <typo>` silently CREATES the directory: git
        commands fail against the missing cwd (caught, treated as "not a git repo"), the
        filesystem walk over a missing path just yields zero files, and the final
        `os.makedirs(os.path.dirname(out), exist_ok=True)` - meant only to create `.kibsu/` -
        creates the typo'd path itself as a side effect and reports a fabricated clean success:
        exit 0, `.kibsu/index.json` written into a brand-new directory that did not exist a
        moment ago. Exit code 3 matches CANNOT_RUN as used identically by discover.py, check.py,
        guide.py, learn.py and report.py."""
        missing = os.path.join(self.tmpdir, "does-not-exist")
        self.assertFalse(os.path.isdir(missing))

        exit_code, stdout, stderr = run_tool("index", missing)

        self.assertEqual(exit_code, 3, "stdout=%r stderr=%r" % (stdout, stderr))
        self.assertFalse(
            os.path.exists(missing),
            "index.py must not create the target path just by being pointed at it",
        )

    def test_existing_repo_behavior_is_unchanged_by_the_guard(self):
        """The new path guard must not disturb the ordinary, existing-directory path: a plain
        `python -m kibsu index <repo> --stdout` against a real repo still exits 0 and produces
        the index, exactly as before the guard was added."""
        repo = make_repo(self.tmpdir, FIXTURE_FILES)

        exit_code, stdout, stderr = run_tool("index", repo, "--stdout")

        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)
        self.assertIn('"schema"', stdout)
        assert_repo_untouched(repo)


if __name__ == "__main__":
    unittest.main()
