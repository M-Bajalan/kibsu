#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for `python -m kibsu guide` - what does the agent actually have to remember?

Per kibsu/guide.py's own EXIT CODES docstring:
    0  no drift
    1  instructions ask agents to remember enforced things
    3  cannot run

DRIFT is the check: an instruction that tells an agent to REMEMBER something ("before commit,
run X") when a mechanism (CI, in this fixture) already enforces X. That drift only ever grows,
and it is the one thing this tool exists to catch, so it is exactly what the positive fixture
plants: CLAUDE.md mandates a script, a CI workflow already runs it (so guide.py's own
`discover()` call classifies it ENFORCED), and the CLAUDE.md text still uses "before commit"
language about it. The negative fixture mandates the same kind of script, but nothing enforces
it (no CI, no hook) - so the state is "ON YOU" and there is nothing for the agent to stop
remembering.

IMPORTANT, undocumented-in-the-docstring behaviour found while writing this test: exit code 1
is NOT unconditional on drift being present. `guide.py`'s own EXIT CODES section reads
"1  instructions ask agents to remember enforced things" with no qualifier, but the source
(`return DRIFT if (a.check and d) else OK`) only returns 1 when `--check` is ALSO passed; without
it, `guide <repo>` prints the exact same drift finding to stdout and still exits 0. This is
verified below in test_drift_without_check_flag_still_exits_zero and reported back verbatim -
per the task's hard rules, the test records this real behaviour rather than treating the
docstring as ground truth.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from support import make_repo, run_tool, assert_repo_untouched

CI_WORKFLOW = (
    "name: CI\n"
    "on: [push]\n"
    "jobs:\n"
    "  check:\n"
    "    runs-on: ubuntu-latest\n"
    "    steps:\n"
    "      - run: python script.py\n"
)
CLAUDE_MD = "Before commit, run `python script.py` to check everything.\n"


class GuideTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="kibsu_test_guide_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_drift_with_check_flag_exits_one(self):
        """CI already enforces `script.py`, but CLAUDE.md still tells the agent to remember it
        ("before commit, run ..."). With --check, guide.py must report drift and exit 1."""
        repo = make_repo(self.tmpdir, {
            "script.py": "print('hi')\n",
            "CLAUDE.md": CLAUDE_MD,
            ".github/workflows/ci.yml": CI_WORKFLOW,
        })

        exit_code, stdout, stderr = run_tool("guide", repo, "--check", "--json")

        self.assertEqual(exit_code, 1, "expected DRIFT (1); stderr=%r" % stderr)
        result = json.loads(stdout)
        self.assertEqual(len(result["drift"]), 1)
        self.assertEqual(result["drift"][0]["command"], "script.py")
        assert_repo_untouched(repo)

    def test_no_enforcement_means_no_drift(self):
        """The same mandate, but nothing anywhere enforces it (no CI, no hook) - the command is
        classified ON YOU, not ENFORCED, so there is nothing for the agent to be told to stop
        remembering. --check must exit 0."""
        repo = make_repo(self.tmpdir, {
            "script.py": "print('hi')\n",
            "CLAUDE.md": CLAUDE_MD,
        })

        exit_code, stdout, stderr = run_tool("guide", repo, "--check", "--json")

        self.assertEqual(exit_code, 0, "expected OK (0); stderr=%r" % stderr)
        result = json.loads(stdout)
        self.assertEqual(result["drift"], [])
        assert_repo_untouched(repo)

    def test_drift_without_check_flag_still_exits_zero(self):
        """Documents real, verified behaviour that the module's own EXIT CODES docstring does not
        qualify: without --check, the identical drift-producing fixture from
        test_drift_with_check_flag_exits_one still prints the drift finding, but exits 0, not 1.
        This is not a bug we are fixing - it is the actual contract, recorded so nobody asserts
        the docstring's unqualified "1" instead of the code's real, --check-gated behaviour."""
        repo = make_repo(self.tmpdir, {
            "script.py": "print('hi')\n",
            "CLAUDE.md": CLAUDE_MD,
            ".github/workflows/ci.yml": CI_WORKFLOW,
        })

        exit_code, stdout, stderr = run_tool("guide", repo)

        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)
        self.assertIn("REMEMBER something a machine", stdout)
        assert_repo_untouched(repo)


if __name__ == "__main__":
    unittest.main()
