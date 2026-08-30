#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for `tools/refresh_readme_counts.py` - the producer for #29's guard.

The guard (tests/test_readme_counts.py) made a stale paragraph impossible to SHIP. It did not
make one impossible to WRITE, and since it measures the repo's own lines and cases, every code
change moves the measured truth and the paragraph has to be hand-edited to match. Measured cost
on 2026-08-28: seven concurrent PRs all touched that one paragraph, each merge invalidated the
other six, and every re-sync's only real conflict was those four numbers.

This tool produces the number instead of asking someone to author it. What must be true of it:

  1. It agrees with the guard BY CONSTRUCTION, not by coincidence - it imports the guard's own
     measure(), so a second implementation cannot drift from the first. That is asserted by
     identity below, because "we wrote them the same way" is exactly the promise #29 proves
     nobody keeps.
  2. Rewriting touches ONLY the four numbers. A tool that reflows the paragraph while fixing it
     would make every code PR a prose diff, which is the friction it exists to remove.
  3. --check can go red. Per CONTRIBUTING rule 4 the negative control drives it against a
     doctored paragraph and asserts the staleness is caught and NOTHING is written.
"""
import contextlib
import io
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from support import PACKAGE_ROOT

sys.path.insert(0, os.path.join(PACKAGE_ROOT, "tools"))
import refresh_readme_counts as tool  # noqa: E402
import test_readme_counts as guard  # noqa: E402


class SharedMeasurementTests(unittest.TestCase):
    def test_the_tool_uses_the_guards_own_measurement_not_a_copy(self):
        """Identity, not equality. Two implementations that agree today are the setup for the
        drift #29 documents; one implementation cannot drift from itself."""
        self.assertIs(tool.measure, guard.measure)
        self.assertIs(tool.CLAIM_RE, guard.CLAIM_RE)
        self.assertIs(tool.claims, guard.claims)


class RefreshTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="kibsu_test_refresh_")
        self.fixture = os.path.join(self.tmpdir, "README.md")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write(self, text):
        with io.open(self.fixture, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)

    def _read(self):
        with io.open(self.fixture, encoding="utf-8") as fh:
            return fh.read()

    def _run(self, argv):
        """Invoke the tool in-process with its output captured.

        In-process rather than as a subprocess so the identity assertion above stays meaningful
        (a subprocess would re-import and could hide a divergence), and captured so a passing
        suite stays readable - the tool is chatty by design when run by a human.
        """
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = tool.main(argv)
        return rc, out.getvalue(), err.getvalue()

    def _paragraph(self, kibsu_lines, kibsu_files, tests_lines, cases):
        # The real paragraph's shape, line break included - the sentence spans two lines in
        # README.md and the rewrite must not join them.
        return ("intro line that must not move\n\n"
                "**It is small enough to actually read.** %s lines across %s files in `kibsu/`, plus\n"
                "%s lines of tests running %s cases. That is an evening, not a quarter.\n\n"
                "trailing line that must not move\n" % (kibsu_lines, kibsu_files, tests_lines, cases))

    def test_a_stale_paragraph_is_refreshed_to_the_measured_truth(self):
        truth = guard.measure()
        self._write(self._paragraph("4,111", "9", "3,258", "120"))

        rc, _out, _err = self._run([self.fixture])

        self.assertEqual(rc, 0)
        self.assertEqual(guard.claims(self._read()), truth)

    def test_only_the_numbers_move(self):
        """Byte-for-byte: refreshing a doctored copy must reproduce the correct one exactly -
        same prose, same line break inside the sentence, same trailing newline."""
        truth = guard.measure()
        correct = self._paragraph("{:,}".format(truth["kibsu_lines"]), truth["kibsu_files"],
                                  "{:,}".format(truth["tests_lines"]), truth["cases"])
        self._write(self._paragraph("4,111", "9", "3,258", "120"))

        self._run([self.fixture])

        self.assertEqual(self._read(), correct)

    def test_refreshing_an_already_correct_paragraph_changes_nothing(self):
        truth = guard.measure()
        correct = self._paragraph("{:,}".format(truth["kibsu_lines"]), truth["kibsu_files"],
                                  "{:,}".format(truth["tests_lines"]), truth["cases"])
        self._write(correct)

        rc, _out, _err = self._run([self.fixture])

        self.assertEqual(rc, 0)
        self.assertEqual(self._read(), correct, "idempotent: a fresh paragraph is left alone")

    def test_check_goes_red_on_a_stale_paragraph_and_writes_nothing(self):
        """Rule 4's negative control. A checker that cannot fail is a tick, not a check."""
        stale = self._paragraph("4,111", "9", "3,258", "120")
        self._write(stale)

        rc, _out, _err = self._run(["--check", self.fixture])

        self.assertEqual(rc, 1, "--check must report a stale paragraph as a failure")
        self.assertEqual(self._read(), stale, "--check must never write")

    def test_check_is_green_on_a_correct_paragraph(self):
        truth = guard.measure()
        self._write(self._paragraph("{:,}".format(truth["kibsu_lines"]), truth["kibsu_files"],
                                    "{:,}".format(truth["tests_lines"]), truth["cases"]))

        self.assertEqual(self._run(["--check", self.fixture])[0], 0)

    def test_a_missing_paragraph_is_an_error_not_a_silent_pass(self):
        """If the paragraph is reworded out of CLAIM_RE's reach, the honest answer is "I cannot
        tell", not "fine" - the same posture the rest of the codebase takes about unknowns."""
        self._write("a README with no count-it-yourself paragraph at all\n")

        self.assertEqual(self._run([self.fixture])[0], 2)
        self.assertEqual(self._run(["--check", self.fixture])[0], 2)


if __name__ == "__main__":
    unittest.main()
