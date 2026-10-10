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
from support import make_repo, run_git, run_tool, assert_repo_untouched


class RootInstructionFileReportTests(unittest.TestCase):
    """`kibsu report` on the layout the README leads with must measure, not abstain."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="kibsu_test_report_root_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_a_root_agents_md_is_measured_not_reported_as_absent(self):
        """Before the fallback, a repo whose ONLY file was AGENTS.md was told
        "no agent-instruction directory found. Nothing here tells agents how to work." - at a
        repo that plainly does. Q3 and Q4 both abstained, so the flagship first-run command
        printed three unanswerable questions to every newcomer using the documented layout.
        """
        repo = make_repo(self.tmpdir, {
            "AGENTS.md": (
                "- Run `python -m pytest` before every commit.\n"
                "- Create `docs/decisions.md` when you make an architectural choice.\n"
            ),
        })
        exit_code, stdout, stderr = run_tool("report", repo)
        # 3 is report's own CANNOT_RUN, earned here by Q5 alone (no index to check history
        # against). What matters is that Q3/Q4 no longer abstain - before the fallback this
        # same repo abstained on THREE questions, two of them for want of a directory.
        self.assertIn(exit_code, (0, 3), "stderr=%r" % stderr)
        self.assertNotIn("no agent-instruction directory found", stdout)

        def line_for(question):
            hits = [ln for ln in stdout.splitlines() if question in ln]
            self.assertEqual(len(hits), 1, "expected one %r line in:\n%s" % (question, stdout))
            return hits[0]

        self.assertNotIn("COULD NOT CHECK", line_for("Prove they followed"))
        self.assertNotIn("COULD NOT CHECK", line_for("Resume after a break"))
        assert_repo_untouched(repo)


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


def _commit_all(repo, message):
    """Stage everything and commit with an inline identity - never the machine's global config."""
    rc, out, err = run_git(repo, "add", "-A")
    assert rc == 0, "git add -A failed: %s" % (err or out)
    rc, out, err = run_git(
        repo,
        "-c", "user.email=kibsu-tests@example.com",
        "-c", "user.name=Kibsu Tests",
        "commit", "-q", "-m", message,
    )
    assert rc == 0, "git commit failed: %s" % (err or out)


def _write(repo, relpath, content):
    full = os.path.join(repo, relpath.replace("/", os.sep))
    if not os.path.isdir(os.path.dirname(full)):
        os.makedirs(os.path.dirname(full))
    with open(full, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(content)


class HistoryReplayTests(unittest.TestCase):
    """Question 5 replays commits against the index the repository claims to keep. Both tests
    drive the same question; what differs is whether that index has any history to replay."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="kibsu_test_report_history_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _history(self, repo):
        exit_code, stdout, stderr = run_tool("report", repo, "--json")
        result = json.loads(stdout)
        return exit_code, next(f for f in result["findings"]
                               if f["title"] == "Follow your own rules")

    def test_an_index_that_was_never_committed_is_not_replayed(self):
        """`kibsu index` writes .kibsu/index.json, and a repository is free to gitignore it and
        build it on demand. Such an index has no history, so every commit that added a doc
        "failed to update it" - check.py's own backtest docstring calls that number meaningless.
        report used to print it anyway: following this tool's own quickstart turned Q5 from
        `?` into an accusation of 100% of the eligible commits. It must say it could not check."""
        repo = make_repo(self.tmpdir, {
            ".gitignore": ".kibsu/index.json\n",
            "docs/one.md": "---\ntype: doc\n---\n# One\n",
        })
        _write(repo, "docs/two.md", "---\ntype: doc\n---\n# Two\n")
        _commit_all(repo, "add docs/two.md")
        _write(repo, ".kibsu/index.json", '{"generated": true}\n')   # ignored, never committed

        exit_code, history = self._history(repo)

        self.assertEqual(history["mark"], "?", history)
        self.assertIn("never been committed", history["detail"])
        self.assertEqual(exit_code, 3, "a check that could not run must exit CANNOT_RUN")
        assert_repo_untouched(repo)

    def test_negative_control_a_committed_index_left_stale_is_convicted_with_the_real_count(self):
        """The control for the test above: the same question against an index that DOES have
        history must still convict - and the denominator is the commits actually replayed.
        The line used to read "of your last 200 commits" on a repository that had two."""
        repo = make_repo(self.tmpdir, {
            "docs/index.json": '{"generated": true}\n',
            "docs/one.md": "---\ntype: doc\n---\n# One\n",
        })
        _write(repo, "docs/two.md", "---\ntype: doc\n---\n# Two\n")
        _commit_all(repo, "add docs/two.md without touching the index")

        exit_code, history = self._history(repo)

        self.assertEqual(history["mark"], "x", history)
        self.assertIn("1 of your last 2 commits", history["detail"])
        assert_repo_untouched(repo)


if __name__ == "__main__":
    unittest.main()
