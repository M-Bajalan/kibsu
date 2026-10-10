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
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from support import PACKAGE_ROOT

CLAIM_RE = re.compile(
    r"([\d,]+) lines across (\d+) files in `kibsu/`, plus\s+"
    r"([\d,]+) lines of tests running (\d+) cases"
)


class CannotCount(RuntimeError):
    """Discovery could not import every test module, so there is no honest case count."""


def count_cases(start_dir):
    """The case count `python -m unittest discover -s tests` reports from the clone root.

    That command gets two things for free which a function has to arrange. The clone root is
    first on sys.path, so `import kibsu` means this checkout; called from tools/ instead, it
    meant whatever kibsu happened to be pip-installed. And a test module that fails to import
    is loud there - an E and exit 1 - whereas a bare countTestCases() takes unittest's
    stand-in for the failed module as ONE case and returns a total that is quietly short.

    Together those produced a wrong number with exit 0: on a machine carrying an older
    installed kibsu, a test module importing a name that release lacked failed to load, the
    count came back seven short, and tools/refresh_readme_counts.py wrote it into the README
    and printed "refreshed" (2026-10-10; the suite then failed on the tool's own output). So
    the root goes on the path, and a load error raises instead of being counted."""
    if PACKAGE_ROOT not in sys.path:
        sys.path.insert(0, PACKAGE_ROOT)
    loader = unittest.TestLoader()
    cases = loader.discover(start_dir).countTestCases()
    if loader.errors:
        raise CannotCount(
            "cannot count the test cases - %d test module(s) failed to import, and unittest "
            "counts each failed module as one case. First failure:\n%s"
            % (len(loader.errors), loader.errors[0].strip()[-600:]))
    return cases


def measure():
    """The README's own verification commands, as functions - byte-for-byte the same logic
    the paragraph tells the reader to run."""
    def count(sub):
        files = sorted(pathlib.Path(PACKAGE_ROOT, sub).glob("*.py"))
        return len(files), sum(len(p.read_text(encoding="utf-8").splitlines()) for p in files)

    kibsu_files, kibsu_lines = count("kibsu")
    tests_files, tests_lines = count("tests")
    cases = count_cases(os.path.join(PACKAGE_ROOT, "tests"))
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


class CountCasesTests(unittest.TestCase):
    """count_cases() must refuse a total it cannot stand behind."""

    GOOD = ("import unittest\n\n\n"
            "class T(unittest.TestCase):\n"
            "    def test_one(self):\n"
            "        pass\n")

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="kibsu_test_count_cases_")
        self._path = list(sys.path)
        self._modules = set(sys.modules)

    def tearDown(self):
        # discover() puts its start dir on sys.path and imports the fixtures by bare name.
        sys.path[:] = self._path
        for name in set(sys.modules) - self._modules:
            del sys.modules[name]
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _fixture(self, name, text):
        with io.open(os.path.join(self.tmpdir, name), "w", encoding="utf-8") as fh:
            fh.write(text)

    def test_modules_that_all_import_are_counted(self):
        self._fixture("test_kibsu_count_fixture_good.py", self.GOOD)
        self.assertEqual(count_cases(self.tmpdir), 1)

    def test_negative_control_a_module_that_fails_to_import_is_not_counted_as_one_case(self):
        """Before the refusal this returned 2: the good module's one case, plus unittest's
        stand-in for the module that never loaded."""
        self._fixture("test_kibsu_count_fixture_good.py", self.GOOD)
        self._fixture("test_kibsu_count_fixture_broken.py",
                      "import kibsu_no_such_module_for_this_fixture\n")
        with self.assertRaises(CannotCount) as caught:
            count_cases(self.tmpdir)
        self.assertIn("kibsu_no_such_module_for_this_fixture", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
