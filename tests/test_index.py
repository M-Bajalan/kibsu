#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for `python -m kibsu index` - the deterministic markdown index.

index.py is a builder, not a pass/fail checker: it has no adversarial "defect" to plant, because
its entire job is a pure function of repo state (git commit dates, sorted paths, sorted keys, no
wall-clock stamp - see its own module docstring, "WHY DETERMINISTIC IS A FEATURE, NOT A DETAIL").
Its own EXIT CODES are undocumented as a labeled section, but the source is explicit: `main()`
returns 0 in every normal path, and 3 only if `--verify-determinism` catches two in-process builds
disagreeing.

So the two required tests here are the ones the plan's own table calls for, and they are not the
usual defect/clean pair used for the other seven tools:

  "positive": prove the tool's central claim - determinism - actually holds. Two INDEPENDENT
  `python -m kibsu index --stdout` invocations (separate subprocesses, not the in-process
  `--verify-determinism` self-check, which only ever compares two builds inside the same
  interpreter) must produce byte-identical output for the same repo. `--verify-determinism`
  itself is also exercised, to confirm the tool's own self-check mechanism reports success.

  "negative": per the plan's table, this is not a clean-fixture defect check but the read-only
  guarantee itself - `--stdout` must never write into the repo it indexes.

No tool source file is modified anywhere in this suite; there is deliberately no test here that
forces --verify-determinism to report FAILURE, because the only way to make ns_index.py produce
non-deterministic output would be to change kibsu/index.py itself, which the hard rules forbid.
"""
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from support import make_repo, run_git, run_tool, assert_repo_untouched

FIXTURE_FILES = {
    "docs/doc1.md": (
        "---\n"
        "type: doc\n"
        "tags:\n"
        "  - alpha\n"
        "  - beta\n"
        "---\n"
        "# Doc 1\n"
        "Some content.\n"
    ),
    "docs/doc2.md": "# Doc 2 (no frontmatter)\nplain content\n",
}


def _track(repo, message):
    """git add -A + commit, identity passed inline so no global config is touched."""
    rc, out, err = run_git(repo, "add", "-A")
    assert rc == 0, "git add -A failed: %s" % (err or out)
    rc, out, err = run_git(repo, "-c", "user.email=kibsu-tests@example.com",
                           "-c", "user.name=Kibsu Tests", "commit", "-q", "-m", message)
    assert rc == 0, "git commit failed: %s" % (err or out)


def _symlinks_available(tmpdir):
    """Can this machine make a symlink at all?

    Not a platform check: Windows permits symlinks only under Developer Mode or an elevated
    process, so `os.name` answers the wrong question and would skip on capable Windows boxes
    while erroring on locked-down ones. Ask the filesystem instead.
    """
    probe_target = os.path.join(tmpdir, "_probe_target")
    probe_link = os.path.join(tmpdir, "_probe_link")
    try:
        with open(probe_target, "w", encoding="utf-8") as fh:
            fh.write("x")
        os.symlink(probe_target, probe_link)
        os.remove(probe_link)
        return True
    except (OSError, NotImplementedError, AttributeError):
        return False


class SymlinkContainmentTests(unittest.TestCase):
    """A scanned repo must not be able to read files outside itself through a symlink.

    os.walk() does not descend directory symlinks (followlinks defaults to False), but a
    symlinked FILE is followed by open() like any other, and git tracks such a link happily as
    mode 120000. Measured before the fix on a repo carrying `leak.md -> ../outside_secret.md`:
    index read straight through it and copied the outside file's frontmatter VERBATIM into
    idx.json, with its keys surfacing in the derived taxonomy too. kibsu is pointed at repos it
    did not author - the survey clones ten - so that is untrusted content reaching a committed
    artifact.
    """

    def setUp(self):
        # make_repo() returns tmpdir ITSELF as the repo root, so the link target needs a
        # genuinely separate tree - a sibling file under the same tmpdir would be in-repo.
        self.tmpdir = tempfile.mkdtemp(prefix="kibsu_test_symlink_")
        self.outsidedir = tempfile.mkdtemp(prefix="kibsu_test_symlink_outside_")
        if not _symlinks_available(self.tmpdir):
            self.skipTest("this machine cannot create symlinks (Windows without Developer Mode)")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        shutil.rmtree(self.outsidedir, ignore_errors=True)

    def test_index_does_not_read_through_a_link_that_leaves_the_repo(self):
        outside = os.path.join(self.outsidedir, "outside_secret.md")
        with open(outside, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("---\nsecret_key: SHOULD-NOT-LEAK\n---\ntop secret contents\n")

        repo = make_repo(self.tmpdir, {"doc.md": "# a real doc\n"})
        os.symlink(outside, os.path.join(repo, "leak.md"))
        # Track it. make_repo() commits before the link exists, and index reads
        # `git ls-files` when the tree is a repo - so an untracked link never reaches
        # the read site and the test would pass without exercising the guard at all.
        _track(repo, "add the outward link")

        out_path = os.path.join(self.outsidedir, "idx.json")
        exit_code, _stdout, stderr = run_tool("index", repo, "-o", out_path)
        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)

        with io.open(out_path, encoding="utf-8") as fh:
            idx = json.load(fh)
        blob = json.dumps(idx)
        self.assertNotIn("SHOULD-NOT-LEAK", blob,
                         "content from OUTSIDE the repo reached the index")
        self.assertNotIn("secret_key", blob,
                         "frontmatter from outside the repo reached the index and its taxonomy")
        self.assertEqual([d["path"] for d in idx["docs"]], ["doc.md"])
        # Skipped, never silently - the same disclosure rule the size guard follows.
        self.assertIn("resolves outside the repo", stderr)

    def test_a_link_that_stays_inside_the_repo_is_still_read(self):
        """The complement: containment is about leaving the tree, not about links as such."""
        repo = make_repo(self.tmpdir, {
            "doc.md": "# a real doc\n",
            "docs/target.md": "---\nkind: inside\n---\nin-repo content\n",
        })
        os.symlink(os.path.join(repo, "docs", "target.md"), os.path.join(repo, "alias.md"))
        _track(repo, "add the in-repo link")

        out_path = os.path.join(self.outsidedir, "idx2.json")
        exit_code, _stdout, stderr = run_tool("index", repo, "-o", out_path)
        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)

        with io.open(out_path, encoding="utf-8") as fh:
            idx = json.load(fh)
        self.assertIn("alias.md", [d["path"] for d in idx["docs"]],
                      "an in-repo link must still be indexed - the guard is about escaping "
                      "the tree, not about symlinks being suspicious")


class IndexTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="kibsu_test_index_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_two_independent_runs_are_byte_identical(self):
        """Two SEPARATE subprocess invocations of `index --stdout` against the unchanged repo
        must produce byte-for-byte identical output - the whole point of ns_index.py. This is a
        stronger check than the tool's own in-process `--verify-determinism` (which only ever
        compares two builds inside the same interpreter, in the same call): it would catch a
        real regression like an accidental wall-clock timestamp or an unsorted iteration order
        that happened to be stable only within a single process."""
        repo = make_repo(self.tmpdir, FIXTURE_FILES)

        exit_code_1, stdout_1, stderr_1 = run_tool("index", repo, "--stdout")
        exit_code_2, stdout_2, stderr_2 = run_tool("index", repo, "--stdout")

        self.assertEqual(exit_code_1, 0, "stderr=%r" % stderr_1)
        self.assertEqual(exit_code_2, 0, "stderr=%r" % stderr_2)
        self.assertEqual(stdout_1, stdout_2, "two independent runs produced different output")
        assert_repo_untouched(repo)

    def test_verify_determinism_flag_reports_success(self):
        """The tool's own self-check mechanism (`--verify-determinism`, which builds twice in one
        process and diffs) must report success on an ordinary fixture, exit 0, and print the
        `[ok] determinism` confirmation line."""
        repo = make_repo(self.tmpdir, FIXTURE_FILES)

        exit_code, stdout, stderr = run_tool(
            "index", repo, "--verify-determinism", "--stdout",
        )

        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)
        self.assertIn("[ok] determinism", stdout)
        assert_repo_untouched(repo)

    def test_stdout_mode_writes_nothing_to_the_repo(self):
        """`--stdout` is index.py's read-only mode (the default writes exactly one file,
        `.kibsu/index.json`, into the target repo - see the module docstring). With --stdout,
        nothing must be written anywhere under the repo."""
        repo = make_repo(self.tmpdir, FIXTURE_FILES)

        exit_code, stdout, stderr = run_tool("index", repo, "--stdout")

        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)
        self.assertIn('"schema"', stdout)
        assert_repo_untouched(repo)
        self.assertFalse(
            os.path.exists(os.path.join(repo, ".kibsu", "index.json")),
            "--stdout must not have written .kibsu/index.json",
        )

    def test_nonexistent_path_cannot_run_and_creates_nothing(self):
        """main() must validate the target path before build()/write - the same guard
        discover.py already has for the identical input (`if not os.path.isdir(root): print
        "CANNOT RUN: ... is not a directory"; return CANNOT_RUN`, discover.py lines ~129-130).

        Without that guard, `python -m kibsu index <typo>` silently CREATES the directory: git
        commands fail against the missing cwd (caught, treated as "not a git repo"), the
        filesystem walk over a missing path just yields zero files, and the final
        `os.makedirs(os.path.dirname(out), exist_ok=True)` - meant only to create `.kibsu/` -
        creates the typo'd path itself as a side effect and reports a fabricated clean success:
        exit 0, `.kibsu/index.json` written into a brand-new directory that did not exist a
        moment ago. Exit code 3 matches CANNOT_RUN as used identically by discover.py, check.py,
        guide.py, learn.py and report.py."""
        missing = os.path.join(self.tmpdir, "does-not-exist")
        self.assertFalse(os.path.isdir(missing))

        exit_code, stdout, stderr = run_tool("index", missing)

        self.assertEqual(exit_code, 3, "stdout=%r stderr=%r" % (stdout, stderr))
        self.assertFalse(
            os.path.exists(missing),
            "index.py must not create the target path just by being pointed at it",
        )

    def test_existing_repo_behavior_is_unchanged_by_the_guard(self):
        """The new path guard must not disturb the ordinary, existing-directory path: a plain
        `python -m kibsu index <repo> --stdout` against a real repo still exits 0 and produces
        the index, exactly as before the guard was added."""
        repo = make_repo(self.tmpdir, FIXTURE_FILES)

        exit_code, stdout, stderr = run_tool("index", repo, "--stdout")

        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)
        self.assertIn('"schema"', stdout)
        assert_repo_untouched(repo)


if __name__ == "__main__":
    unittest.main()
