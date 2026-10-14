#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for `python -m kibsu explain` - the lines behind the percentage.

`report` says "47.8% of your procedural instructions are verifiable" and stops. `audit`
breaks that down to units and stops there too. Neither says WHICH lines, so a reader who
accepts the number has nothing to act on. `explain` lists them as `path:line  text`.

What has to be true of it, and is checked here:

  1. It explains the SAME number. The lines it lists for procedure units are exactly the gap
     in the headline: listed == instructions - checkable, compared against a separate `audit`
     run rather than against its own arithmetic. A list that explains a different number than
     the one `report` printed is worse than no list.
  2. The line numbers are the FILE's. The scorer works on the body after the frontmatter is
     stripped; a number off by the frontmatter's length sends the reader to the wrong line in
     every file that declares a genre - which is every file this tool tells you to write.
     Expected numbers below are derived from the fixture text, not from the tool.
  3. It does not move the measurement. Asking the scorer to keep its line records must leave
     every count where it was, and `audit --json` without the new flag must not grow a key -
     `evidence/` is regenerated from that output.
  4. Doctrine is not a to-do list. A doctrine unit scores 0% by design; listing its lines as
     things to fix would push authors to trade judgement for ceremony. Not listed by default,
     and the output says how many were held back.
  5. It reads only.

Per CONTRIBUTING rule 4 the control for "it finds lines" is a unit where every instruction is
checkable, which must list nothing and say so."""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from support import PACKAGE_ROOT, make_repo, run_tool, assert_repo_untouched

sys.path.insert(0, PACKAGE_ROOT)
from kibsu import audit, explain, report  # noqa: E402 -- must follow the sys.path.insert above

DEPLOY = (
    "---\n"
    "genre: procedure\n"
    "---\n"
    "# Deploy\n"
    "\n"
    "- Run `python build.py` before release.\n"
    "- You must keep the team informed.\n"
    "- Always think about the reader first.\n"
    "- [ ] Confirm the release notes are written\n"
    "- Never skip the review step.\n"
)
DEPLOY_CLAIMABLE = ("- You must keep the team informed.",
                    "- Always think about the reader first.",
                    "- Never skip the review step.")
DEPLOY_CHECKABLE = ("- Run `python build.py` before release.",
                    "- [ ] Confirm the release notes are written")

THINKING = (
    "---\n"
    "genre: doctrine\n"
    "---\n"
    "# Thinking\n"
    "\n"
    "- Always name the hidden assumption.\n"
    "- You should prefer the simpler reading.\n"
)


def file_line(content, text):
    """Where `text` sits in the file, counted the way an editor counts - independently of
    anything kibsu computes."""
    return content.split("\n").index(text) + 1


class ExplainTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="kibsu_test_explain_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _repo(self, files=None):
        return make_repo(self.tmpdir, files or {
            ".claude/skills/deploy.md": DEPLOY,
            ".claude/skills/thinking.md": THINKING,
        })

    def _json(self, repo, *args):
        exit_code, stdout, stderr = run_tool("explain", repo, "--json", *args)
        self.assertEqual(exit_code, 0, "stderr=%r stdout=%r" % (stderr, stdout))
        return json.loads(stdout)

    def _unit(self, result, name):
        hits = [u for u in result["units"] if u["file"].endswith(name)]
        self.assertEqual(len(hits), 1, "expected one unit ending %r in %r"
                         % (name, [u["file"] for u in result["units"]]))
        return hits[0]

    def test_every_instruction_is_listed_with_its_file_line_and_verdict(self):
        repo = self._repo()

        unit = self._unit(self._json(repo), "deploy.md")

        self.assertEqual(unit["file"], ".claude/skills/deploy.md")
        self.assertEqual(unit["genre"], "procedure")
        by_text = {rec["text"]: rec for rec in unit["lines"]}
        for text in DEPLOY_CLAIMABLE:
            self.assertEqual(by_text[text]["verdict"], "claimable", by_text[text])
            self.assertEqual(by_text[text]["line"], file_line(DEPLOY, text), by_text[text])
            self.assertEqual(by_text[text]["why"], [])
        for text in DEPLOY_CHECKABLE:
            self.assertEqual(by_text[text]["verdict"], "checkable", by_text[text])
            self.assertEqual(by_text[text]["line"], file_line(DEPLOY, text), by_text[text])
        self.assertIn("command", by_text[DEPLOY_CHECKABLE[0]]["why"])
        self.assertEqual(by_text[DEPLOY_CHECKABLE[1]]["why"], ["tick-box"])
        assert_repo_untouched(repo)

    def test_the_listed_lines_are_exactly_the_gap_in_the_number_audit_reports(self):
        """Against a SEPARATE audit run, not explain's own sums."""
        repo = self._repo()
        skills = os.path.join(repo, ".claude", "skills")
        exit_code, stdout, _ = run_tool("audit", skills, "--json")
        self.assertEqual(exit_code, 0)
        headline = json.loads(stdout)["procedure_only"]

        result = self._json(repo)

        listed = [rec for u in result["units"] if u["genre"] == "procedure"
                  for rec in u["lines"] if rec["verdict"] == "claimable"]
        self.assertEqual(len(listed), headline["instructions"] - headline["checkable"])
        self.assertEqual(len(listed), 3)
        self.assertEqual(result["procedure_only"], headline)

    def test_human_output_is_path_colon_line_and_lists_only_what_cannot_be_checked(self):
        repo = self._repo()

        exit_code, stdout, stderr = run_tool("explain", repo)

        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)
        for text in DEPLOY_CLAIMABLE:
            self.assertIn(".claude/skills/deploy.md:%d" % file_line(DEPLOY, text), stdout)
            self.assertIn(text.lstrip("- "), stdout)
        self.assertNotIn("python build.py", stdout, "a checkable line is not on the to-do list")
        self.assertIn("40.0%", stdout)
        self.assertIn("2 of 5", stdout)
        self.assertIn("Nothing was written to this repo", stdout)
        assert_repo_untouched(repo)

    def test_doctrine_is_held_back_by_default_and_the_output_says_so(self):
        repo = self._repo()

        _, default_out, _ = run_tool("explain", repo)
        _, all_out, _ = run_tool("explain", repo, "--all-genres")

        self.assertNotIn("name the hidden assumption", default_out)
        self.assertIn("1 doctrine unit", default_out)
        self.assertIn("name the hidden assumption", all_out)
        self.assertIn(".claude/skills/thinking.md:%d"
                      % file_line(THINKING, "- Always name the hidden assumption."), all_out)

    def test_negative_control_a_fully_checkable_procedure_lists_nothing_and_says_so(self):
        repo = self._repo({
            ".claude/skills/build.md": (
                "---\ngenre: procedure\n---\n# Build\n\n"
                "- Run `python build.py` first.\n"
                "- [ ] Confirm `dist/app.zip` exists\n"
            ),
        })

        result = self._json(repo)
        _, stdout, _ = run_tool("explain", repo)

        self.assertEqual([rec for u in result["units"] for rec in u["lines"]
                          if rec["verdict"] == "claimable"], [])
        self.assertIn("nothing to list", stdout)
        self.assertNotIn("build.md:", stdout)

    def test_no_agent_instructions_is_could_not_explain_and_exits_three(self):
        repo = self._repo({"README.md": "# Just a readme\n"})

        exit_code, stdout, _ = run_tool("explain", repo)

        self.assertEqual(exit_code, 3)
        self.assertIn("COULD NOT EXPLAIN", stdout)
        assert_repo_untouched(repo)

    def test_a_bom_and_frontmatter_do_not_shift_the_line_numbers(self):
        content = "﻿" + DEPLOY
        repo = self._repo({".claude/skills/deploy.md": content})

        unit = self._unit(self._json(repo), "deploy.md")

        by_text = {rec["text"]: rec["line"] for rec in unit["lines"]}
        for text in DEPLOY_CLAIMABLE + DEPLOY_CHECKABLE:
            self.assertEqual(by_text[text], file_line(DEPLOY, text), text)

    def test_a_file_with_no_frontmatter_counts_from_line_one(self):
        content = "# Rules\n\n- You must keep the team informed.\n"
        repo = self._repo({"AGENTS.md": content})

        result = self._json(repo, "--all-genres")

        unit = self._unit(result, "AGENTS.md")
        self.assertEqual([(rec["line"], rec["text"]) for rec in unit["lines"]],
                         [(3, "- You must keep the team informed.")])

    def test_a_skill_md_layout_reports_the_file_not_the_directory(self):
        repo = self._repo({"skills/gate/SKILL.md": DEPLOY})

        unit = self._unit(self._json(repo), "SKILL.md")

        self.assertEqual(unit["file"], "skills/gate/SKILL.md")

    def test_unit_narrows_the_listing_to_matching_files(self):
        repo = self._repo()

        _, stdout, _ = run_tool("explain", repo, "--all-genres", "--unit", "thinking")

        self.assertIn("thinking.md:", stdout)
        self.assertNotIn("deploy.md:", stdout)

    def test_long_listings_are_capped_and_say_how_much_was_cut(self):
        body = "".join("- You must remember rule number %d.\n" % n for n in range(1, 16))
        repo = self._repo({".claude/skills/rules.md": "---\ngenre: procedure\n---\n# Rules\n\n" + body})

        _, capped, _ = run_tool("explain", repo)
        _, full, _ = run_tool("explain", repo, "--full")

        self.assertEqual(capped.count("rules.md:"), explain.LINES_PER_UNIT)
        self.assertIn("%d more" % (15 - explain.LINES_PER_UNIT), capped)
        self.assertIn("15 instruction(s)", capped)
        self.assertIn("Showing %d" % explain.LINES_PER_UNIT, capped,
                      "a capped listing must not read as the whole of it")
        self.assertEqual(full.count("rules.md:"), 15)
        self.assertNotIn("Showing", full)

    def test_it_looks_where_report_looks(self):
        """Identity, not equality: the percentage being explained is report's, so the
        instruction directory has to be found - and the scorer run, and its failures read - by
        report's own code. Since #112 that is one resolver (an explicit --skills, then the
        directory search, then the root-file fallback) and one scorer call, and explain holds no
        copy of either: a local definition here would fail this test."""
        self.assertIs(explain.resolve_skills, report.resolve_skills)
        self.assertIs(explain.run_scorer, report.run_scorer)


class ScorerUnmovedTests(unittest.TestCase):
    """Keeping the line records is observation only. No count may depend on it."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="kibsu_test_explain_scorer_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_keeping_line_records_changes_no_count(self):
        for text in (DEPLOY, THINKING, "﻿" + DEPLOY, "# Rules\n\n- Run `make test`.\n"):
            plain = audit.analyse(text)
            kept = audit.analyse(text, keep_lines=True)
            records = kept.pop("line_records")
            self.assertEqual(kept, plain)
            self.assertEqual(len(records), plain["instructions"])
            self.assertEqual(len([r for r in records if r["verdict"] == "checkable"]),
                             plain["checkable"])
            self.assertEqual(len([r for r in records if r["verdict"] == "claimable"]),
                             plain["claimable"])

    def test_audit_json_grows_no_key_unless_lines_are_asked_for(self):
        """`evidence/` is regenerated from this output; a key that appears by default would
        rewrite every published file."""
        repo = make_repo(self.tmpdir, {".claude/skills/deploy.md": DEPLOY})
        skills = os.path.join(repo, ".claude", "skills")

        _, plain_out, _ = run_tool("audit", skills, "--json")
        _, lines_out, _ = run_tool("audit", skills, "--json", "--lines")

        plain, with_lines = json.loads(plain_out)["skills"][0], json.loads(lines_out)["skills"][0]
        self.assertNotIn("line_records", plain)
        self.assertNotIn("file", plain)
        self.assertIn("line_records", with_lines)
        self.assertEqual(with_lines["file"], "deploy.md")
        self.assertEqual({k: v for k, v in with_lines.items()
                          if k not in ("line_records", "file")}, plain)

    def test_negative_control_checkable_because_separates_the_two_verdicts(self):
        self.assertEqual(audit.checkable_because("- You must keep the team informed.", False, 0), [])
        self.assertEqual(audit.checkable_because("- [ ] Confirm it", True, 0), ["tick-box"])
        self.assertIn("file", audit.checkable_because("- Write `docs/summary.md`.", False, 0))
        self.assertIn("exit/diff/assertion",
                      audit.checkable_because("- The build must pass.", False, 0))


if __name__ == "__main__":
    unittest.main()
