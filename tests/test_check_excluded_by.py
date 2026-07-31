#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regression test for kibsu/check.py's excluded_by() cross-OS case sensitivity bug.

excluded_by() decides whether a baseline.json glob (e.g. "docs/archive/**") should skip a path
that came from `git ls-files` - already canonical, since git is case-sensitive on every OS and
records exactly the casing a file was committed with. The decision used fnmatch.fnmatch(), which
calls os.path.normcase() on BOTH operands before matching: a no-op on POSIX, but a lowercasing
pass on Windows (see cpython's fnmatch.py). That makes the SAME baseline.json exclude DIFFERENT
files depending on which OS runs the check - a pattern written as "docs/archive/**" silently also
swallows "Docs/Archive/x.md" and "docs/ARCHIVE/x.md" on Windows, while this project's own 3-OS CI
matrix (.github/workflows/*, ubuntu + macos + windows) treats those as distinct, uncovered paths
on the other two. Since the path is already canonical, the match must be case-exact too -
fnmatch.fnmatchcase(), never fnmatch.fnmatch().

Only reproduces on a platform where os.path.normcase folds case (Windows) - written to run there
directly, against the real stdlib fnmatch behavior, rather than mocking normcase to fake it
everywhere.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kibsu import check


@unittest.skipUnless(
    os.name == "nt",
    "fnmatch.fnmatch only normcases (lowercases) on Windows; on POSIX fnmatch.fnmatch and "
    "fnmatchcase already agree on every path below, so this regression cannot reproduce there.",
)
class ExcludedByCaseSensitivityTests(unittest.TestCase):
    def test_pattern_does_not_bleed_into_a_differently_cased_directory(self):
        """'docs/archive/**' must exclude only 'docs/archive/...' - not 'Docs/Archive/...' nor
        'docs/ARCHIVE/...'. git ls-files is case-sensitive on every OS; the exclude decision has
        to agree, or the same baseline.json protects a different file set depending on the OS
        that runs the check."""
        patterns = ["docs/archive/**"]

        self.assertIsNone(
            check.excluded_by("Docs/Archive/x.md", patterns),
            "a differently-cased directory must NOT be excluded by a lower-case pattern",
        )
        self.assertIsNone(
            check.excluded_by("docs/ARCHIVE/x.md", patterns),
            "a differently-cased directory must NOT be excluded by a lower-case pattern",
        )

    def test_pattern_still_excludes_its_own_exact_case(self):
        """Positive control: the same pattern must still exclude the exact-case path it names -
        the fix tightens matching to case-exact, it does not turn matching off."""
        self.assertEqual(
            check.excluded_by("docs/archive/x.md", ["docs/archive/**"]),
            "docs/archive/**",
        )


if __name__ == "__main__":
    unittest.main()
