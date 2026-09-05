#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Issue #29's structural fix: the README's "count it yourself" paragraph can no longer ship
stale, because this suite refuses to pass while it is.

The paragraph published exact code/test counts four separate times that were already wrong
when readers ran the printed commands (CORRECTIONS.md records the first two incidents; #29
the third; the fourth drifted in the nine days AFTER #29 was filed, while every other
finding was being fixed - the class does not die by diligence). The commands always
outranked the prose; now the suite enforces that the prose agrees with them.

Self-updating by construction: the measurement below is the README's own printed commands'
logic - same glob, same splitlines, same discovery count that `python -m unittest discover`
prints as "Ran N" (equivalence verified before this guard was written: Ran 170 ==
countTestCases 170) - and this file's own lines and tests are part of what it measures, so
adding tests moves the measured truth, and the README must move with it. Per CONTRIBUTING
rule 4 the negative control drives the checker against a doctored paragraph and asserts the
mismatch is caught; the match test itself ran RED against the stale README (5,034/3,909/144
vs the real 5,216/4,533/170) before the numbers were refreshed in the same change."""
import io
import os
import pathlib
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from support import PACKAGE_ROOT

CLAIM_RE = re.compile(
    r"([\d,]+) lines across (\d+) files in `kibsu/`, plus\s+"
    r"([\d,]+) lines of tests running (\d+) cases"
)


def measure():
    """The README's own verification commands, as functions - byte-for-byte the same logic
    the paragraph tells the reader to run."""
    def count(sub):
        files = sorted(pathlib.Path(PACKAGE_ROOT, sub).glob("*.py"))
        return len(files), sum(len(p.read_text(encoding="utf-8").splitlines()) for p in files)

    kibsu_files, kibsu_lines = count("kibsu")
    tests_files, tests_lines = count("tests")
    cases = unittest.TestLoader().discover(os.path.join(PACKAGE_ROOT, "tests")).countTestCases()
    return {"kibsu_files": kibsu_files, "kibsu_lines": kibsu_lines,
            "tests_lines": tests_lines, "cases": cases}


def claims(readme_text):
    m = CLAIM_RE.search(readme_text)
    if not m:
        return None
    return {"kibsu_lines": int(m.group(1).replace(",", "")),
            "kibsu_files": int(m.group(2)),
            "tests_lines": int(m.group(3).replace(",", "")),
            "cases": int(m.group(4))}


class ReadmeCountGuardTests(unittest.TestCase):
    def test_readme_counts_match_what_its_own_commands_print(self):
        with io.open(os.path.join(PACKAGE_ROOT, "README.md"), encoding="utf-8") as fh:
            claimed = claims(fh.read())
        self.assertIsNotNone(claimed, "the 'count it yourself' paragraph is missing or "
                                       "reworded - update CLAIM_RE with it, never delete "
                                       "the guard")
        self.assertEqual(claimed, measure(),
                         "README's published counts disagree with what its own commands "
                         "print - update the paragraph (the commands outrank the prose)")

    def test_guard_detects_a_stale_paragraph(self):
        """Rule 4's negative control: a doctored paragraph with yesterday's numbers must be
        caught, or this guard is a tick that cannot go red."""
        doctored = ("**It is small enough to actually read.** 4,781 lines across 14 files "
                    "in `kibsu/`, plus\n3,258 lines of tests running 120 cases.")
        parsed = claims(doctored)
        self.assertIsNotNone(parsed)
        self.assertNotEqual(parsed, measure(),
                            "the 2026-08-07 stale numbers must read as a mismatch")


if __name__ == "__main__":
    unittest.main()
