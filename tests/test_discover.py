#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for `python -m kibsu discover` - what is configured here, and what actually runs?

Per kibsu/discover.py's own EXIT CODES docstring:
    0  nothing inert
    1  something is declared but dead
    3  cannot run

The flagship check is the UNENFORCED GATE: a command the repo's own agent instructions (e.g.
CLAUDE.md) tell an agent to run before committing, that appears in no CI workflow and no git
hook. That is exactly the defect discover.py exists to find, so it is exactly what the positive
fixture plants: a CLAUDE.md that names `script.py` in a backtick-quoted command, with `script.py`
present in the repo but invoked by nothing. The negative fixture is the same repo with one
difference - a CI workflow that actually runs `script.py` - so the same instruction is now
enforced and discover.py must report nothing inert.
"""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from support import make_repo, run_tool, assert_repo_untouched


class DiscoverTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="kibsu_test_discover_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_unenforced_gate_is_reported_as_inert(self):
        """A script named in CLAUDE.md's own gate language, invoked by no automation at all,
        must be flagged INERT and exit 1 - this is the tool's entire reason to exist."""
        repo = make_repo(self.tmpdir, {
            "script.py": "print('hi')\n",
            "CLAUDE.md": "Before commit, run `python script.py` to check everything.\n",
        })

        exit_code, stdout, stderr = run_tool("discover", repo, "--json")

        self.assertEqual(exit_code, 1, "expected INERT_FOUND (1); stderr=%r" % stderr)
        self.assertIn('"state": "INERT"', stdout)
        self.assertIn("script.py", stdout)
        assert_repo_untouched(repo)

    def test_ci_enforced_gate_is_not_inert(self):
        """The identical instruction, but this time a CI workflow actually runs the mandated
        script - discover.py must find nothing declared-but-dead and exit 0."""
        repo = make_repo(self.tmpdir, {
            "script.py": "print('hi')\n",
            "CLAUDE.md": "Before commit, run `python script.py` to check everything.\n",
            ".github/workflows/ci.yml": (
                "name: CI\n"
                "on: [push]\n"
                "jobs:\n"
                "  check:\n"
                "    runs-on: ubuntu-latest\n"
                "    steps:\n"
                "      - run: python script.py\n"
            ),
        })

        exit_code, stdout, stderr = run_tool("discover", repo, "--json")

        self.assertEqual(exit_code, 0, "expected OK (0); stderr=%r" % stderr)
        self.assertNotIn('"state": "INERT"', stdout)
        assert_repo_untouched(repo)


    def test_a_different_script_whose_name_contains_the_gate_does_not_enforce_it(self):
        """The gate classifier used bare substring containment, so any CI line mentioning a
        LONGER filename marked the mandated script live: "lint.py" is inside "pylint.py".

        The repo below mandates `lint.py` and runs `pylint.py` - a different file, doing
        different work. Before the fix discover reported the gate as enforced and `guide`
        passed that on as ENFORCED, so the tool asserted an enforcement that did not exist -
        exactly the class of unbacked claim it is built to find.
        """
        repo = make_repo(self.tmpdir, {
            "lint.py": "print('the mandated gate')\n",
            "pylint.py": "print('a different script entirely')\n",
            "CLAUDE.md": "Before commit, run `python lint.py` to check everything.\n",
            ".github/workflows/ci.yml": (
                "name: CI\n"
                "on: [push]\n"
                "jobs:\n"
                "  check:\n"
                "    runs-on: ubuntu-latest\n"
                "    steps:\n"
                "      - run: python pylint.py\n"
            ),
        })

        exit_code, stdout, stderr = run_tool("discover", repo, "--json")

        self.assertEqual(exit_code, 1,
                         "lint.py is run by nothing - expected INERT_FOUND (1); stderr=%r" % stderr)
        self.assertIn('"state": "INERT"', stdout)
        assert_repo_untouched(repo)

    def test_a_path_qualified_invocation_still_counts_as_enforcement(self):
        """The complement, so the boundary rule cannot quietly become too strict: a separator
        before the name is a normal way to invoke it, not a different file."""
        repo = make_repo(self.tmpdir, {
            "lint.py": "print('the mandated gate')\n",
            "CLAUDE.md": "Before commit, run `python lint.py` to check everything.\n",
            ".github/workflows/ci.yml": (
                "name: CI\n"
                "on: [push]\n"
                "jobs:\n"
                "  check:\n"
                "    runs-on: ubuntu-latest\n"
                "    steps:\n"
                "      - run: python ./lint.py --strict\n"
            ),
        })

        exit_code, stdout, stderr = run_tool("discover", repo, "--json")

        self.assertEqual(exit_code, 0, "expected OK (0); stderr=%r" % stderr)
        self.assertNotIn('"state": "INERT"', stdout)
        assert_repo_untouched(repo)


class DangerousFlagTests(unittest.TestCase):
    """K-1 (issue #68): an instruction that hands out a gate-removing flag with no approval
    or prohibition rule adjacent is a standing free pass, and must read INERT. The motivating
    incident: docs granted --auto-approve --skip-dq unconditionally, an agent used them on a
    destructive run, and every gate that would have caught the wrong scope was off by design.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="kibsu_test_k1_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_an_ungated_dangerous_flag_reads_inert(self):
        repo = make_repo(self.tmpdir, {
            "CLAUDE.md": (
                "# Working here\n\n"
                "When the pipeline is slow, run `python pipeline.py --auto-approve --skip-dq`\n"
                "and move on to the next task.\n"
            ),
            "pipeline.py": "print('hi')\n",
            ".github/workflows/ci.yml": (
                "name: CI\non: [push]\njobs:\n  check:\n"
                "    runs-on: ubuntu-latest\n    steps:\n      - run: python pipeline.py\n"
            ),
        })

        exit_code, stdout, stderr = run_tool("discover", repo, "--json")

        self.assertEqual(exit_code, 1, "an ungated dangerous flag is a finding; stderr=%r" % stderr)
        self.assertIn('"Dangerous flags"', stdout)
        self.assertIn("CLAUDE.md:3", stdout)
        assert_repo_untouched(repo)

    def test_a_gated_mention_and_a_prohibition_are_not_findings(self):
        """The two shapes that must NOT fire: a grant with an adjacent approval rule, and a
        prohibition - "never run --force" is the opposite of handing the flag out."""
        repo = make_repo(self.tmpdir, {
            "CLAUDE.md": (
                "# Working here\n\n"
                "You may run `python pipeline.py --auto-approve` ONLY with a quoted,\n"
                "dated approval marker from the owner.\n\n"
                "Never run anything with --force in this repository.\n"
            ),
            "pipeline.py": "print('hi')\n",
            ".github/workflows/ci.yml": (
                "name: CI\non: [push]\njobs:\n  check:\n"
                "    runs-on: ubuntu-latest\n    steps:\n      - run: python pipeline.py\n"
            ),
        })

        exit_code, stdout, stderr = run_tool("discover", repo, "--json")

        self.assertEqual(exit_code, 0, "gated + prohibited mentions are healthy; stderr=%r\n%s"
                         % (stderr, stdout))
        self.assertIn('"Dangerous flags"', stdout)
        self.assertIn('"live"', stdout)
        assert_repo_untouched(repo)


class ScopeDefaultTests(unittest.TestCase):
    """K-2 (issue #69): a mandated entry point whose data-scope default is a hardcoded date
    literal is a time bomb with a checkable signature - true the day it was written, stale
    ever after, and the day an argument is omitted it silently scopes a destructive run to a
    months-old window. Universe = doc-mandated scripts only, never the whole tree."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="kibsu_test_k2_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_a_literal_month_default_in_a_mandated_script_reads_inert(self):
        repo = make_repo(self.tmpdir, {
            "CLAUDE.md": "Before shipping, run `python pipeline.py` to load the data.\n",
            "pipeline.py": (
                "import argparse\n"
                "RUN_MONTH = \"2026-06\"\n"
                "print(RUN_MONTH)\n"
            ),
            ".github/workflows/ci.yml": (
                "name: CI\non: [push]\njobs:\n  check:\n"
                "    runs-on: ubuntu-latest\n    steps:\n      - run: python pipeline.py\n"
            ),
        })

        exit_code, stdout, stderr = run_tool("discover", repo, "--json")

        self.assertEqual(exit_code, 1, "a stale literal scope default is a finding; stderr=%r" % stderr)
        self.assertIn('"Scope defaults"', stdout)
        self.assertIn("pipeline.py:2", stdout)
        assert_repo_untouched(repo)

    def test_a_derived_scope_is_clean_and_unmandated_files_are_out_of_universe(self):
        """The complement, twice over: a mandated script that DERIVES its scope is LIVE, and a
        date literal in a file the instructions never mention is not this check's business -
        the tool must not become a repo-wide linter."""
        repo = make_repo(self.tmpdir, {
            "CLAUDE.md": "Before shipping, run `python pipeline.py` to load the data.\n",
            "pipeline.py": (
                "import datetime\n"
                "RUN_MONTH = datetime.date.today().strftime(\"%Y-%m\")\n"
                "print(RUN_MONTH)\n"
            ),
            ".github/workflows/ci.yml": (
                "name: CI\non: [push]\njobs:\n  check:\n"
                "    runs-on: ubuntu-latest\n    steps:\n      - run: python pipeline.py\n"
            ),
            "unrelated_fixture.py": "FROZEN = \"2020-01\"\n",
        })

        exit_code, stdout, stderr = run_tool("discover", repo, "--json")

        self.assertEqual(exit_code, 0, "derived scope + out-of-universe literal; stderr=%r\n%s"
                         % (stderr, stdout))
        self.assertIn('"Scope defaults"', stdout)
        self.assertNotIn("unrelated_fixture.py", stdout)
        assert_repo_untouched(repo)


if __name__ == "__main__":
    unittest.main()
