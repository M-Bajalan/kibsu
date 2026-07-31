#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for `python -m kibsu report` - the read-only readiness report.

Per kibsu/report.py's own EXIT CODES docstring:
    0  the report is complete - every check ran.
    3  the report ran but is INCOMPLETE - at least one check could not run.
    Findings NEVER make this non-zero - only a check that could not run does.

So the defect this tool exists to surface is not "low score", it is "a check that could not
run at all" (SKIP), because that is the one condition report.py itself calls out as making its
own output untrustworthy. The positive fixture is a bare repo with no `.kibsu/index.json`, no
catalog file anywhere, and no agent-instruction directory (`.claude/skills`, `.agents/skills`,
etc.) - under that shape, three of the five checks (VERIFIABILITY, CONTINUITY, HISTORY) cannot
run at all and report.py must exit 3. The negative fixture gives it everything those three
checks need - a `docs/index.json` (satisfies "has index" and is the file HISTORY replays
against), 10 markdown docs sharing one frontmatter key (satisfies "conventions" - >=80% of
>=10 frontmattered docs promotes a REQUIRED key), and a `.claude/skills/*.md` agent-instruction
file (satisfies VERIFIABILITY/CONTINUITY) - so every check runs and report.py must exit 0.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from support import make_repo, run_tool, assert_repo_untouched


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="kibsu_test_report_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_no_index_and_no_agent_instruction_dir_skips_and_exits_three(self):
        """No .kibsu/index.json, no docs/index.json, no .claude/skills (or any other
        agent-instruction dir) - VERIFIABILITY, CONTINUITY and HISTORY cannot run at all.
        report.py must say so (SKIP, not a silent pass) and exit CANNOT_RUN (3)."""
        repo = make_repo(self.tmpdir, {
            "README.md": "# Just a readme\n",
        })

        exit_code, stdout, stderr = run_tool("report", repo, "--json")

        self.assertEqual(exit_code, 3, "expected CANNOT_RUN (3); stderr=%r" % stderr)
        result = json.loads(stdout)
        self.assertFalse(result["complete"])
        self.assertGreater(result["skipped"], 0, "expected at least one SKIPped check")
        assert_repo_untouched(repo)

    def test_index_and_conventions_present_completes_and_exits_zero(self):
        """An index (docs/index.json), 10 docs sharing one frontmatter key (an enforceable
        convention), and an agent-instruction dir with real skill content - every one of the
        five checks can now run, so report.py must exit OK (0), regardless of the individual
        findings' pass/fail marks."""
        files = {
            "docs/index.json": '{"generated": true}\n',
            ".claude/skills/example-skill.md": (
                "# Example Skill\n\n"
                "Run `pytest tests/` before committing.\n"
                "- [ ] Confirm the build passes\n"
            ),
        }
        for i in range(10):
            files["docs/doc%d.md" % i] = (
                "---\ntype: doc\n---\n# Doc %d\nSome content for doc %d.\n" % (i, i)
            )
        repo = make_repo(self.tmpdir, files)

        exit_code, stdout, stderr = run_tool("report", repo, "--json")

        self.assertEqual(exit_code, 0, "expected OK (0); stderr=%r" % stderr)
        result = json.loads(stdout)
        self.assertTrue(result["complete"])
        self.assertEqual(result["skipped"], 0)
        assert_repo_untouched(repo)

    def test_continuity_warns_not_oks_on_an_unverifiable_pattern_only_mandate(self):
        """A mandate whose expanded basename keeps no literal character beyond the extension
        (`{name}.md`) proves nothing either way - audit.py's own `unverifiable_pattern` bucket
        exists precisely because no hit or miss on a pattern like that means anything (see
        kibsu/audit.py's --definitions). Before this fix, a skill whose ONLY mandated artifact
        was unverifiable-pattern still read as a clean OK ("all N promised artifacts exist"),
        because `phantom` is always False on an unverifiable mandate - a braced path flipping
        what should be unproven evidence into a passing CONTINUITY finding. It must read WARN,
        never OK, when nothing was actually verified either way."""
        repo = make_repo(self.tmpdir, {
            ".claude/skills/notes.md": (
                "# Notes Skill\n\n"
                "Create `{name}.md` for each entry.\n"
            ),
        })

        exit_code, stdout, stderr = run_tool("report", repo, "--json")

        result = json.loads(stdout)
        continuity = next(f for f in result["findings"] if f["title"] == "Resume after a break")
        self.assertNotEqual(continuity["mark"], "+", "must never read OK on unverifiable-only "
                                                      "evidence: %r" % continuity)
        self.assertEqual(continuity["mark"], "!", continuity)
        assert_repo_untouched(repo)


if __name__ == "__main__":
    unittest.main()
