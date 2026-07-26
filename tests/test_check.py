#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for `python -m kibsu check` - the gate that is meant to be wired to `git commit`.

Per kibsu/check.py's own EXIT CODES docstring:
    EXIT CODES   0 clean · 1 violations (BLOCK) · 2 warnings only · 3 cannot run

Four distinct exit codes are documented, and none may be assumed - each is exercised here
against a fixture built to produce exactly that value, nothing else:

    3  CANNOT RUN   no .kibsu/index.json exists yet to compare against.
    1  VIOLATIONS   a tracked .md changed since the index was built - the STALE check, and the
                    one the task explicitly asks for: "a repo whose index is STALE relative to a
                    changed doc".
    0  clean        the index was (re)built against the exact content now on disk / committed.
    2  WARNINGS_ONLY  the TAXONOMY check's softer half: a doc root clears the promotion floor
                    (>=10 frontmattered docs, >=80% share for a key - derived in index.py's
                    derive_taxonomy) and one in-scope doc under that root carries NO frontmatter
                    at all. check.py treats "no frontmatter where a taxonomy is enforced" as a
                    WARNING (NO-FRONTMATTER), distinct from "has frontmatter but is missing a
                    required key", which is a VIOLATION (TAXONOMY). Getting a warnings-only run
                    with zero violations requires deliberately keeping every frontmatter'd doc
                    compliant while leaving exactly one doc bare.

check.py never mutates a repo (no --receipt is passed in any test here), so every scenario also
asserts `assert_repo_untouched` after the run.
"""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from support import make_repo, run_git, run_tool, assert_repo_untouched


def _commit_all(repo, message):
    """Stage everything and commit with an inline identity - never the machine's global config,
    matching the discipline make_repo already establishes for the initial fixture commit."""
    rc, out, err = run_git(repo, "add", "-A")
    assert rc == 0, "git add -A failed: %s" % (err or out)
    rc, out, err = run_git(
        repo,
        "-c", "user.email=kibsu-tests@example.com",
        "-c", "user.name=Kibsu Tests",
        "commit", "-q", "-m", message,
    )
    assert rc == 0, "git commit failed: %s" % (err or out)


class CheckTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="kibsu_test_check_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # ---- CANNOT_RUN (3) --------------------------------------------------------------------
    def test_no_index_cannot_run_exits_three(self):
        """No .kibsu/index.json has ever been built here. check.py must refuse to guess and
        exit CANNOT_RUN (3), not silently pass."""
        repo = make_repo(self.tmpdir, {"doc.md": "hello\n"})

        exit_code, stdout, stderr = run_tool("check", repo)

        self.assertEqual(exit_code, 3, "stderr=%r" % stderr)
        self.assertIn("CANNOT RUN", stdout)
        self.assertIn("no index at", stdout)
        assert_repo_untouched(repo)

    # ---- VIOLATIONS (1) - the positive control ---------------------------------------------
    def test_stale_index_reports_violation_and_exits_one(self):
        """The exact scenario the task names: a repo whose index is STALE relative to a changed
        doc. The index is built and committed against doc.md's ORIGINAL content; doc.md is then
        edited and committed again with no matching index rebuild - check.py must detect the
        content-hash mismatch, report it as a STALE violation, and exit VIOLATIONS (1)."""
        repo = make_repo(self.tmpdir, {"doc.md": "version one\n"})

        idx_exit, idx_out, idx_err = run_tool("index", repo, "-o", ".kibsu/index.json")
        self.assertEqual(idx_exit, 0, "stderr=%r" % idx_err)
        _commit_all(repo, "build index for version one")

        with open(os.path.join(repo, "doc.md"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write("version two\n")
        _commit_all(repo, "change doc.md without rebuilding the index")

        exit_code, stdout, stderr = run_tool("check", repo)

        self.assertEqual(exit_code, 1, "expected VIOLATIONS (1); stderr=%r" % stderr)
        self.assertIn("STALE", stdout)
        self.assertIn("doc.md", stdout)
        self.assertIn("FAIL", stdout)
        assert_repo_untouched(repo)

    # ---- OK (0) - the negative control ------------------------------------------------------
    def test_freshly_built_index_is_clean_exits_zero(self):
        """Identical shape to the STALE fixture, but the index is (re)built AFTER doc.md reaches
        its final content and both are committed together - nothing has drifted, so check.py
        must report PASS and exit OK (0)."""
        repo = make_repo(self.tmpdir, {"doc.md": "version one\n"})

        idx_exit, idx_out, idx_err = run_tool("index", repo, "-o", ".kibsu/index.json")
        self.assertEqual(idx_exit, 0, "stderr=%r" % idx_err)
        _commit_all(repo, "build index matching current content")

        exit_code, stdout, stderr = run_tool("check", repo)

        self.assertEqual(exit_code, 0, "expected OK (0); stderr=%r" % stderr)
        self.assertIn("PASS", stdout)
        self.assertIn("0 violations, 0 warnings", stdout)
        assert_repo_untouched(repo)

    # ---- WARNINGS_ONLY (2) ------------------------------------------------------------------
    def test_bare_doc_under_enforced_root_warns_without_blocking(self):
        """docs/ carries 10 frontmatter'd docs sharing `type:` (>=10 docs, 100% share - clears
        index.py's promotion floor, so the root becomes enforceable) plus one doc with NO
        frontmatter at all. Every frontmatter'd doc has the required key, so there is no TAXONOMY
        violation; the bare doc trips the softer NO-FRONTMATTER warning instead. Zero violations
        and one-or-more warnings is exactly WARNINGS_ONLY (2), not VIOLATIONS (1) - check.py
        deliberately distinguishes "missing frontmatter entirely" (warn) from "has frontmatter
        but missing the required key" (block)."""
        files = {}
        for i in range(10):
            files["docs/doc%02d.md" % i] = "---\ntype: note\n---\n# Doc %d\n" % i
        files["docs/doc_bare.md"] = "# No frontmatter here\n"
        repo = make_repo(self.tmpdir, files)

        idx_exit, idx_out, idx_err = run_tool("index", repo, "-o", ".kibsu/index.json")
        self.assertEqual(idx_exit, 0, "stderr=%r" % idx_err)
        _commit_all(repo, "build index over the docs/ taxonomy fixture")

        exit_code, stdout, stderr = run_tool("check", repo)

        self.assertEqual(exit_code, 2, "expected WARNINGS_ONLY (2); stderr=%r" % stderr)
        self.assertIn("NO-FRONTMATTER", stdout)
        self.assertIn("doc_bare.md", stdout)
        self.assertNotIn("TAXONOMY", stdout)
        self.assertIn("PASS with", stdout)
        assert_repo_untouched(repo)


if __name__ == "__main__":
    unittest.main()
