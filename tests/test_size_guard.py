#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Issue #39: no read path in the package had a file-size ceiling.

kibsu's stated job is scanning ARBITRARY third-party repositories (`report /path/to/any/repo`;
`survey` clones public repos), and nothing stops a scanned repo from git-tracking one
multi-gigabyte `.md` file - every scanner slurped it whole with `.read()`. Most sites wrapped
the read in `except Exception` (which a cleanly-raised MemoryError does satisfy), but the
realistic failure on the deployment target is the kernel OOM-killer's SIGKILL, which no except
clause sees - and learn.py's read had no guard of any kind.

The fix: a MAX_READ_BYTES ceiling (5 MB - generous for instruction markdown) checked via
os.path.getsize before every scan-path read, oversized files skipped with a printed reason on
stderr (stdout stays clean for --json). These two end-to-end tests pin the two primary
scanning surfaces; the same constant-and-guard pattern is applied to check/discover/guide/
learn in the same change. Per CONTRIBUTING rule 4 both ran RED first: pre-fix the oversized
file was read successfully and COUNTED, so the exclusion assertions failed."""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from support import make_repo, run_tool

BIG = ("x" * 79 + "\n") * (6 * 1024 * 1024 // 80)  # ~6 MB of lines, over the 5 MB ceiling


class SizeGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="kibsu_test_sizeguard_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_index_skips_an_oversized_doc_with_a_printed_reason(self):
        repo = make_repo(self.tmpdir, {
            "docs/normal.md": "# Normal\n\nsmall and indexable\n",
            "docs/huge.md": BIG,
        })
        exit_code, _out, err = run_tool("index", repo, "-o", ".kibsu/index.json")
        self.assertEqual(exit_code, 0, "stderr=%r" % err[:500])

        with open(os.path.join(repo, ".kibsu", "index.json"), encoding="utf-8") as fh:
            idx = json.load(fh)
        paths = [d["path"] for d in idx["docs"]]
        self.assertIn("docs/normal.md", paths)
        self.assertNotIn("docs/huge.md", paths,
                         "an over-ceiling file must be skipped, not slurped")
        self.assertIn("huge.md", err, "the skip must be DISCLOSED, not silent")

    def test_audit_skips_an_oversized_unit_with_a_printed_reason(self):
        repo = make_repo(self.tmpdir, {
            ".claude/skills/normal-skill.md": "# Skill\n\nRun `pytest tests/` first.\n",
            ".claude/skills/huge-skill.md": BIG,
        })
        exit_code, out, err = run_tool(
            "audit", os.path.join(repo, ".claude", "skills"), "--json",
        )
        self.assertEqual(exit_code, 0, "stderr=%r" % err[:500])
        result = json.loads(out)
        self.assertEqual(result["all"]["units"], 1,
                         "only the normal skill is measurable; the oversized one is skipped")
        self.assertIn("huge-skill.md", err, "the skip must be DISCLOSED, not silent")


if __name__ == "__main__":
    unittest.main()
