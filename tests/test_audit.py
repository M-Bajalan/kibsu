#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for `python -m kibsu audit` - the checkable:claimable ratio of an agent skill set.

audit.py's module docstring now carries an "EXIT CODES" section (added as part of plan 6.1,
closing the gap with discover/report/guide/learn, which already had one): 0 = the audit ran to
completion, in text or --json; 1 = no .md files were found under <path> - the only other code
this tool returns. The ratio itself, however low, never changes the exit code; that is
documented explicitly rather than left to be inferred from the source.

Because checkability never drives the exit code, the positive/negative distinction here is made
in the --json body instead: a skill written entirely as prose obligations ("you must always...",
"never skip...") with no backtick command, no named file, no checkbox, and no exit-code language
must score 0.0% checkable; a skill written as concrete, verifiable steps (an inline command, a
named file, a checkbox) must score 100%. Both fixtures still assert exit_code == 0, since that
is the tool's actual, verified behaviour for a populated skills directory either way.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from support import make_repo, run_tool, assert_repo_untouched


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="kibsu_test_audit_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_claimable_only_instructions_score_zero_percent(self):
        """Every instruction here is a pure prose obligation - a reviewer could never confirm any
        of them happened from the repo alone. checkable must be 0 of N, exit 0 (audit.py never
        fails on a low ratio; it only fails when no markdown exists at all)."""
        repo = make_repo(self.tmpdir, {
            ".claude/skills/example-skill.md": (
                "# Claimable Skill\n\n"
                "You must always verify the user's intent before making any change.\n"
                "Never skip the review step, no matter how small.\n"
            ),
        })

        exit_code, stdout, stderr = run_tool(
            "audit", os.path.join(repo, ".claude", "skills"), "--json",
        )
        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)

        result = json.loads(stdout)
        self.assertGreater(result["all"]["instructions"], 0)
        self.assertEqual(result["all"]["checkable"], 0)
        self.assertEqual(result["all"]["pct"], 0.0)
        assert_repo_untouched(repo)

    def test_checkable_instructions_score_full_percent(self):
        """Every instruction here names something a reviewer CAN confirm from the repo alone: an
        inline command, a named file, a checkbox. checkable must equal instructions (100%)."""
        repo = make_repo(self.tmpdir, {
            ".claude/skills/example-skill.md": (
                "# Checkable Skill\n\n"
                "Run `pytest tests/` before committing.\n"
                "Update `CHANGELOG.md` with your changes.\n"
                "- [ ] Confirm the build passes\n"
            ),
        })

        exit_code, stdout, stderr = run_tool(
            "audit", os.path.join(repo, ".claude", "skills"), "--json",
        )
        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)

        result = json.loads(stdout)
        self.assertGreater(result["all"]["instructions"], 0)
        self.assertEqual(result["all"]["checkable"], result["all"]["instructions"])
        self.assertEqual(result["all"]["pct"], 100.0)
        assert_repo_untouched(repo)

    def test_populated_directory_without_json_exits_zero(self):
        """audit.py's own docstring now carries an EXIT CODES section (0 = ran to completion,
        text or --json; 1 = no .md found). The two tests above only ever call --json; this one
        exercises the plain-text path on a populated directory to prove exit 0 is not an
        artifact of --json specifically - it is documented as the code for 'ran to completion'
        regardless of output mode."""
        repo = make_repo(self.tmpdir, {
            ".claude/skills/example-skill.md": "# A Skill\n\nDo the thing.\n",
        })

        exit_code, stdout, stderr = run_tool(
            "audit", os.path.join(repo, ".claude", "skills"),
        )

        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)
        self.assertIn("skill-audit", stdout)
        assert_repo_untouched(repo)

    def test_uppercase_extension_file_token_is_mandated(self):
        """Sibling of issue #14: FILE_TOKEN (audit.py's mandated-artifact extractor) was compiled
        without re.IGNORECASE, so an uppercase-extension mandate like `NOTES.MD` was invisible -
        never extracted into `mandated`, never counted checkable, never phantom-checked, even
        though the artifact-verb + backtick-file shape is identical to the lowercase case. A
        skill that mandates `NOTES.MD` must show up in `mandated` the same way one that mandates
        `notes.md` does."""
        repo = make_repo(self.tmpdir, {
            ".claude/skills/example-skill.md": (
                "# Uppercase Mandate Skill\n\n"
                "Update `NOTES.MD` every time you finish a task.\n"
            ),
        })

        exit_code, stdout, stderr = run_tool(
            "audit", os.path.join(repo, ".claude", "skills"), "--json",
        )
        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)

        result = json.loads(stdout)
        mandated_tokens = {m["tok"] for m in result["skills"][0]["mandated"]}
        self.assertIn("NOTES.MD", mandated_tokens)
        assert_repo_untouched(repo)

    def test_uppercase_extension_line_scores_checkable(self):
        """Sibling of issue #14: PATHY (the bare, non-backtick file-name detector that feeds the
        `checkable` test) was also compiled without re.IGNORECASE, so a line naming an
        uppercase-extension file with no backticks - e.g. "Update NOTES.MD after every run." -
        never matched PATHY and was scored CLAIMABLE even though a reviewer can plainly confirm
        the named file from the repo alone."""
        repo = make_repo(self.tmpdir, {
            ".claude/skills/example-skill.md": (
                "# Uppercase Path Skill\n\n"
                "Update NOTES.MD after every run.\n"
            ),
        })

        exit_code, stdout, stderr = run_tool(
            "audit", os.path.join(repo, ".claude", "skills"), "--json",
        )
        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)

        result = json.loads(stdout)
        self.assertEqual(result["all"]["instructions"], 1)
        self.assertEqual(result["all"]["checkable"], 1)
        assert_repo_untouched(repo)

    def test_lowercase_mandate_still_works(self):
        """Guard: the IGNORECASE fix must not change behaviour for the ordinary lowercase case
        that already worked - `notes.md` must still be extracted into `mandated` exactly as
        before."""
        repo = make_repo(self.tmpdir, {
            ".claude/skills/example-skill.md": (
                "# Lowercase Mandate Skill\n\n"
                "Update `notes.md` every time you finish a task.\n"
            ),
        })

        exit_code, stdout, stderr = run_tool(
            "audit", os.path.join(repo, ".claude", "skills"), "--json",
        )
        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)

        result = json.loads(stdout)
        mandated_tokens = {m["tok"] for m in result["skills"][0]["mandated"]}
        self.assertIn("notes.md", mandated_tokens)
        assert_repo_untouched(repo)

    def test_no_markdown_found_exits_one(self):
        """Per audit.py's EXIT CODES section: a directory with no markdown files makes audit.py
        print "no .md found under ..." and return 1 - the only exit code besides 0 this tool has
        at all."""
        repo = make_repo(self.tmpdir, {
            ".claude/skills/.gitkeep": "",
        })
        empty_dir = os.path.join(repo, ".claude", "skills")

        exit_code, stdout, stderr = run_tool("audit", empty_dir)

        self.assertEqual(exit_code, 1, "stderr=%r" % stderr)
        self.assertIn("no .md found under", stdout)
        assert_repo_untouched(repo)


if __name__ == "__main__":
    unittest.main()
