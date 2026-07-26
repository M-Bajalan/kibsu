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


if __name__ == "__main__":
    unittest.main()
