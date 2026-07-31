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


class ArtifactInstanceCountTests(unittest.TestCase):
    """v0.4.0's INSTANCE-COUNT phantom redesign (public issue #14 plus the two bugs hiding behind
    it - see audit.py's glob_re()/check_artifacts()).

    Before this: `{...}` placeholder segments survived re.escape() as LITERAL characters, so a
    mandate like `logs/report_{date}.md` could only ever match a file that literally contained a
    brace - it always read as phantom no matter how many real report_2026-07-30.md files a repo
    had. Fixed by expanding `{...}` to "any run of non-slash characters", identically to how `*`
    already expands - applied to the directory prefix too, so a brace in a directory segment no
    longer gets dropped for the wrong reason ("path prefix does not exist") before the phantom
    check ever sees it.

    Every fixture here uses a skill file under `.claude/skills/` (matching the existing tests'
    fixture shape) plus files committed at the REPO ROOT, because check_artifacts() walks the
    whole git repo (via git_root()), not just the audited subdirectory - a mandated artifact can
    live anywhere in the tree.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="kibsu_test_audit_artifacts_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _artifact(self, result, token):
        arts = [a for a in result["artifacts"] if a["artifact"] == token]
        self.assertEqual(
            len(arts), 1,
            "expected exactly one artifact record for %r, got %r" % (token, arts),
        )
        return arts[0]

    def test_issue_14_templated_mandate_with_committed_match_is_not_phantom(self):
        """The issue #14 repro: `logs/report_{date}.md` mandated, and a real
        logs/report_2026-07-30.md committed. Must NOT be phantom, must show match_count >= 1,
        and must be flagged templated=True so a reader knows this was a pattern check, not a
        literal one."""
        repo = make_repo(self.tmpdir, {
            ".claude/skills/example-skill.md": (
                "# Reporting Skill\n\n"
                "Write `logs/report_{date}.md` after each nightly run.\n"
            ),
            "logs/report_2026-07-30.md": "nightly report\n",
        })

        exit_code, stdout, stderr = run_tool(
            "audit", os.path.join(repo, ".claude", "skills"), "--json", "--artifacts",
        )
        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)
        result = json.loads(stdout)
        art = self._artifact(result, "logs/report_{date}.md")

        self.assertTrue(art["in_scope"], art)
        self.assertTrue(art["templated"], art)
        self.assertGreaterEqual(art["match_count"], 1, art)
        self.assertTrue(art["in_tree"], art)
        self.assertFalse(art["unverifiable_pattern"], art)
        self.assertFalse(art["phantom"], art)
        assert_repo_untouched(repo)

    def test_templated_mandate_with_zero_matches_is_still_phantom(self):
        """The anti-laundering case the council was explicit about: braces must not launder a
        mandate nobody ever served. Same mandate as above, same in-scope directory (`logs/`
        exists, via a real committed file), but nothing matching `report_{date}.md` was ever
        committed - this must still be reported phantom, with match_count == 0."""
        repo = make_repo(self.tmpdir, {
            ".claude/skills/example-skill.md": (
                "# Reporting Skill\n\n"
                "Write `logs/report_{date}.md` after each nightly run.\n"
            ),
            "logs/README.md": "not a report\n",
        })

        exit_code, stdout, stderr = run_tool(
            "audit", os.path.join(repo, ".claude", "skills"), "--json", "--artifacts",
        )
        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)
        result = json.loads(stdout)
        art = self._artifact(result, "logs/report_{date}.md")

        self.assertTrue(art["in_scope"], art)
        self.assertTrue(art["templated"], art)
        self.assertEqual(art["match_count"], 0, art)
        self.assertFalse(art["unverifiable_pattern"], art)
        self.assertTrue(art["phantom"], art)
        assert_repo_untouched(repo)

    def test_bare_placeholder_basename_is_unverifiable_not_phantom(self):
        """`{name}.md` retains no literal character beyond its extension - there is nothing left
        to search FOR, so it lands in the new unverifiable_pattern bucket: neither phantom
        (nothing was actually checked) nor served (nothing was actually found)."""
        repo = make_repo(self.tmpdir, {
            ".claude/skills/example-skill.md": (
                "# Notes Skill\n\n"
                "Create `{name}.md` for each entry.\n"
            ),
        })

        exit_code, stdout, stderr = run_tool(
            "audit", os.path.join(repo, ".claude", "skills"), "--json", "--artifacts",
        )
        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)
        result = json.loads(stdout)
        art = self._artifact(result, "{name}.md")

        self.assertTrue(art["in_scope"], art)
        self.assertTrue(art["templated"], art)
        self.assertTrue(art["unverifiable_pattern"], art)
        self.assertFalse(art["phantom"], art)
        assert_repo_untouched(repo)

    def test_brace_in_directory_segment_is_prefix_checked_with_pattern(self):
        """The wrong-reason-drop bug: a brace in a DIRECTORY segment used to make the path-prefix
        filter compare `{lang}` to real directory names literally, always lose, and get dropped
        as out-of-scope before the phantom check ever ran. `docs/{lang}/README.md` mandated,
        `docs/en/README.md` really committed - must be in-scope and not phantom."""
        repo = make_repo(self.tmpdir, {
            ".claude/skills/example-skill.md": (
                "# Translation Skill\n\n"
                "Save `docs/{lang}/README.md` after translating.\n"
            ),
            "docs/en/README.md": "hello\n",
        })

        exit_code, stdout, stderr = run_tool(
            "audit", os.path.join(repo, ".claude", "skills"), "--json", "--artifacts",
        )
        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)
        result = json.loads(stdout)
        art = self._artifact(result, "docs/{lang}/README.md")

        self.assertTrue(art["in_scope"], art)
        self.assertIsNone(art["out_of_scope_reason"], art)
        self.assertTrue(art["templated"], art)
        self.assertGreaterEqual(art["match_count"], 1, art)
        self.assertFalse(art["phantom"], art)
        assert_repo_untouched(repo)

    def test_literal_mandate_phantom_behaviour_unchanged(self):
        """Regression guard: a plain literal mandate that was never committed must behave exactly
        as it did before this redesign - phantom, not templated, not unverifiable."""
        repo = make_repo(self.tmpdir, {
            ".claude/skills/example-skill.md": (
                "# Changelog Skill\n\n"
                "Update `CHANGELOG.md` after every release.\n"
            ),
        })

        exit_code, stdout, stderr = run_tool(
            "audit", os.path.join(repo, ".claude", "skills"), "--json", "--artifacts",
        )
        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)
        result = json.loads(stdout)
        art = self._artifact(result, "CHANGELOG.md")

        self.assertTrue(art["in_scope"], art)
        self.assertFalse(art["templated"], art)
        self.assertEqual(art["match_count"], 0, art)
        self.assertFalse(art["in_tree"], art)
        self.assertFalse(art["in_history"], art)
        self.assertFalse(art["unverifiable_pattern"], art)
        self.assertTrue(art["phantom"], art)
        assert_repo_untouched(repo)


if __name__ == "__main__":
    unittest.main()
