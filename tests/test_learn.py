#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for `python -m kibsu learn` - does the knowledge base still tell the truth?

Per kibsu/learn.py's own EXIT CODES docstring (same meanings as ns_check.py/ns_report.py):
    0  clean
    1  findings
    3  cannot run

The positive fixture plants exactly the two rot classes the docstring highlights: a DANGLING
`[[wikilink]]` that resolves nowhere, and a ROTTED citation to a backtick-quoted path that no
longer exists anywhere in the repo. `--private-store` is pointed at a real, but empty, directory
so the dangling-link check actually resolves to DANGLING rather than the unrelated SKIP outcome
that occurs when no private store can be located at all (that SKIP path is a different, honest
"could not check" state - it must not be confused with a genuine finding, so the fixture is
built to avoid it). The negative fixture's note and citation both resolve: a sibling note with a
matching stem for the `[[wikilink]]`, and a real tracked file for the citation.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from support import make_repo, run_tool, assert_repo_untouched


class LearnTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="kibsu_test_learn_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_dangling_link_and_rotted_citation_exit_one(self):
        """A note with a wikilink to a note that does not exist, and a citation to a file that
        does not exist - both are real findings (not SKIPs), so learn.py must exit FINDINGS (1)."""
        empty_private_store = os.path.join(self.tmpdir, "_empty_private_store")
        os.makedirs(empty_private_store)
        repo = make_repo(self.tmpdir, {
            "docs/memory/note_a.md": (
                "See [[missing_note]] for details, and check `missing/nope.py` "
                "for the implementation.\n"
            ),
        })

        exit_code, stdout, stderr = run_tool(
            "learn", repo, "--private-store", empty_private_store, "--json",
        )

        self.assertEqual(exit_code, 1, "expected FINDINGS (1); stderr=%r" % stderr)
        result = json.loads(stdout)
        kinds = {f["kind"] for f in result["findings"]}
        self.assertIn("DANGLING", kinds)
        self.assertIn("ROTTED", kinds)
        assert_repo_untouched(repo)

    def test_all_links_and_citations_resolve_exit_zero(self):
        """Two notes link to each other by stem, and the one citation points at a file that is
        actually tracked in the repo - nothing rots, so learn.py must exit clean (0)."""
        empty_private_store = os.path.join(self.tmpdir, "_empty_private_store")
        os.makedirs(empty_private_store)
        repo = make_repo(self.tmpdir, {
            "docs/memory/note_a.md": (
                "See [[note_b]] for details, and check `existing/file.py` "
                "for the implementation.\n"
            ),
            "docs/memory/note_b.md": "Referenced from [[note_a]]. Nothing else here.\n",
            "existing/file.py": "print('real file')\n",
        })

        exit_code, stdout, stderr = run_tool(
            "learn", repo, "--private-store", empty_private_store, "--json",
        )

        self.assertEqual(exit_code, 0, "expected OK (0); stderr=%r" % stderr)
        result = json.loads(stdout)
        self.assertEqual(result["findings"], [])
        assert_repo_untouched(repo)


if __name__ == "__main__":
    unittest.main()
