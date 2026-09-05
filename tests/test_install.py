#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for `python -m kibsu install` - wires ns_check to `git commit`, reversibly.

install.py's module docstring now carries an explicit "EXIT CODES" section (added as part of
plan 6.1, closing the gap with check.py/guide.py/discover.py, which already had one), matching
install.py's real behaviour as read from the source: `install()`/`uninstall()` return 0 on
success (including --dry-run) and 3 on every REFUSED path; `status()` always returns 0.

THE PROPERTY THAT MATTERS MOST, per the task: every `git commit` that is meant to exercise the
installed hook is run with cwd = the throwaway fixture repo, via a plain subprocess `git commit`
(never through run_tool, which always runs `python -m kibsu ...` from PACKAGE_ROOT). The hook's
generated shell script never invokes anything through the `kibsu` package: it execs the VENDORED
`.kibsu/bin/check.py` directly, by hard-coded path (see install.py's HOOK template) - never
`python -m kibsu`, so it never depends on kibsu being pip-installed or importable anywhere on this
machine. Before every such commit, `assert_vendored_copy_matches_source(repo, "check.py", ...)`
proves - in the test itself, not by assumption - that the files at that hard-coded path really are
this checkout's vendored snapshot, byte-for-byte, which is exactly why this works at all in a bare
clone and exactly what needs proving regardless of what else happens to be importable.

Only kibsu/install.py's own vendoring/hooksPath/refusal logic is exercised here - the STALE
detection itself (what check.py reports and why) is covered in test_check.py and reused as a
black box: a hook-blocked commit here is verified by exit code and by the presence of check.py's
own "commit blocked by ns_check" text, not by re-deriving STALE semantics.
"""
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from support import (
    assert_repo_untouched,
    assert_vendored_copy_matches_source,
    make_repo,
    run_git,
    run_tool,
)

IDENTITY = ("-c", "user.email=kibsu-tests@example.com", "-c", "user.name=Kibsu Tests")


def _commit_all(repo, message):
    rc, out, err = run_git(repo, "add", "-A")
    assert rc == 0, "git add -A failed: %s" % (err or out)
    rc, out, err = run_git(repo, *(IDENTITY + ("commit", "-q", "-m", message)))
    assert rc == 0, "git commit failed: %s" % (err or out)


def _commit_count(repo):
    rc, out, err = run_git(repo, "rev-list", "--count", "HEAD")
    assert rc == 0, "git rev-list failed: %s" % (err or out)
    return int(out.strip())


def _hooks_path(repo):
    rc, out, _ = run_git(repo, "config", "--get", "core.hooksPath")
    return out.strip() if rc == 0 else None


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="kibsu_test_install_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _prepare_repo_with_clean_index(self):
        """A repo with one tracked doc, an index built and committed against its CURRENT
        content, so a plain `check --staged` run right after would be clean."""
        repo = make_repo(self.tmpdir, {"doc.md": "version one\n"})
        idx_exit, _out, idx_err = run_tool("index", repo, "-o", ".kibsu/index.json")
        self.assertEqual(idx_exit, 0, "stderr=%r" % idx_err)
        _commit_all(repo, "build index matching current content")
        return repo

    # ---- positive: --install wires a hook that actually blocks -----------------------------
    def test_install_vendors_tools_and_blocks_a_commit_that_should_fail(self):
        repo = self._prepare_repo_with_clean_index()

        exit_code, stdout, stderr = run_tool("install", repo, "--install")
        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)
        self.assertIn("INSTALLED", stdout)

        # vendored into the repo, per install.py's own "PORTABLE AS OF v1.1.0" design
        for name in ("check.py", "index.py", "install.py"):
            self.assertTrue(
                os.path.isfile(os.path.join(repo, ".kibsu", "bin", name)),
                "expected .kibsu/bin/%s to be vendored" % name,
            )
        self.assertTrue(os.path.isfile(os.path.join(repo, ".kibsu", "hooks", "pre-commit")))
        self.assertEqual(_hooks_path(repo), ".kibsu/hooks".replace("/", os.sep))

        # commit the install artifacts themselves, exactly as a real user would before doing
        # anything else - otherwise the next `git add -A` below would stage them for the FIRST
        # time as part of the "should be blocked" attempt, muddying what is under test.
        _commit_all(repo, "install the pre-commit hook")
        commits_before = _commit_count(repo)

        # THE precondition: the files at .kibsu/bin/{check,index,install}.py - the hard-coded
        # paths the installed hook execs - must really be this checkout's vendored snapshot. If
        # that ever silently stopped being true (a stale copy from a prior install.py version, a
        # hand-edited stand-in), every assertion below about "this works from a vendored copy,
        # not an installed kibsu" would stop meaning anything without any test failing to say so
        # - so it is asserted here, not assumed.
        assert_vendored_copy_matches_source(repo, "check.py", "index.py", "install.py")

        # change doc.md and stage it WITHOUT rebuilding the index - the index is now stale
        # relative to what is staged, which is exactly what check.py's STALE rule blocks on.
        with open(os.path.join(repo, "doc.md"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write("version two, index not rebuilt\n")
        rc, out, err = run_git(repo, "add", "-A")
        self.assertEqual(rc, 0, "git add -A failed: %s" % (err or out))

        rc, out, err = run_git(repo, *(IDENTITY + ("commit", "-m", "should be blocked")))

        self.assertNotEqual(rc, 0, "expected the commit to be BLOCKED by the hook")
        combined = out + err
        self.assertIn("commit blocked by ns_check", combined)
        self.assertEqual(
            _commit_count(repo), commits_before,
            "a blocked commit must not have created a new commit",
        )

    # ---- negative: a commit that should pass ------------------------------------------------
    def test_install_allows_a_commit_that_should_pass(self):
        repo = self._prepare_repo_with_clean_index()

        exit_code, _stdout, stderr = run_tool("install", repo, "--install")
        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)
        _commit_all(repo, "install the pre-commit hook")
        commits_before = _commit_count(repo)

        assert_vendored_copy_matches_source(repo, "check.py", "index.py", "install.py")

        # change doc.md AND rebuild the index using the VENDORED copy, exactly as a fresh clone
        # (with no kibsu import available) would have to - this is the whole point of vendoring.
        with open(os.path.join(repo, "doc.md"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write("version two, index rebuilt\n")
        rebuild = subprocess.run(
            [sys.executable, os.path.join(repo, ".kibsu", "bin", "index.py"), repo,
             "-o", ".kibsu/index.json"],
            cwd=repo, capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        self.assertEqual(rebuild.returncode, 0, "vendored index.py failed: %r" % rebuild.stderr)

        rc, out, err = run_git(repo, "add", "-A")
        self.assertEqual(rc, 0, "git add -A failed: %s" % (err or out))

        rc, out, err = run_git(repo, *(IDENTITY + ("commit", "-m", "should pass")))

        self.assertEqual(rc, 0, "expected the commit to be ALLOWED; stdout=%r stderr=%r" % (out, err))
        self.assertEqual(
            _commit_count(repo), commits_before + 1,
            "a passing commit must have created exactly one new commit",
        )

    # ---- round-trip: uninstall restores core.hooksPath EXACTLY -----------------------------
    def test_uninstall_restores_previous_hookspath_exactly(self):
        repo = self._prepare_repo_with_clean_index()
        before = _hooks_path(repo)
        self.assertIsNone(before, "fixture repo must start with core.hooksPath unset")

        exit_code, _stdout, stderr = run_tool("install", repo, "--install")
        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)
        self.assertIsNotNone(_hooks_path(repo))

        exit_code, stdout, stderr = run_tool("install", repo, "--uninstall")
        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)
        self.assertIn("UNINSTALLED", stdout)

        after = _hooks_path(repo)
        self.assertEqual(
            after, before,
            "core.hooksPath must return to EXACTLY its pre-install value (None/unset here)",
        )
        self.assertFalse(os.path.isfile(os.path.join(repo, ".kibsu", "hooks", "pre-commit")))
        self.assertFalse(os.path.isfile(os.path.join(repo, ".kibsu", "bin", "check.py")))

    def test_uninstall_restores_a_pre_existing_custom_hookspath(self):
        """The round-trip target must be the value BEFORE install, not just "unset" - so this
        variant starts from a repo that already points core.hooksPath somewhere else."""
        repo = make_repo(self.tmpdir, {"doc.md": "hello\n"})
        custom_dir = os.path.join(repo, "custom-hooks")
        os.makedirs(custom_dir, exist_ok=True)
        rc, out, err = run_git(repo, "config", "core.hooksPath", "custom-hooks")
        self.assertEqual(rc, 0, "git config failed: %s" % (err or out))
        before = _hooks_path(repo)
        self.assertEqual(before, "custom-hooks")

        # --force is required: install() refuses to silently take over an already-set
        # core.hooksPath (see the separate refusal test below for that path un-forced).
        exit_code, stdout, stderr = run_tool("install", repo, "--install", "--force")
        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)
        self.assertNotEqual(_hooks_path(repo), before)

        exit_code, stdout, stderr = run_tool("install", repo, "--uninstall")
        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)

        self.assertEqual(
            _hooks_path(repo), before,
            "uninstall must restore the PRIOR custom hooksPath exactly, not merely unset it",
        )

    def test_reinstall_force_does_not_overwrite_previous_hookspath_with_our_own(self):
        """A second --install --force must not record kibsu's own hooks dir as what to restore.

        `prev = current_hookspath(root)` answers "what is set right now", which after a first
        install is `.kibsu/hooks`. So re-running --install --force over an existing install
        overwrote previous_hookspath with OUR path, and --uninstall then "restored"
        core.hooksPath to a directory whose hook it had just deleted: the user's real setting
        lost, and no hooks running at all. Reproduced end to end before the fix - the record
        went `.myhooks` -> `.kibsu\\hooks`, and uninstall left core.hooksPath at `.kibsu\\hooks`.
        """
        repo = make_repo(self.tmpdir, {"doc.md": "hello\n"})
        os.makedirs(os.path.join(repo, "custom-hooks"), exist_ok=True)
        rc, out, err = run_git(repo, "config", "core.hooksPath", "custom-hooks")
        self.assertEqual(rc, 0, "git config failed: %s" % (err or out))

        exit_code, _stdout, stderr = run_tool("install", repo, "--install", "--force")
        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)
        with io.open(os.path.join(repo, ".kibsu", "install.json"), encoding="utf-8") as fh:
            first = json.load(fh)
        self.assertEqual(first["previous_hookspath"], "custom-hooks")

        # The re-install. This is the step that used to lose the answer.
        exit_code, _stdout, stderr = run_tool("install", repo, "--install", "--force")
        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)
        with io.open(os.path.join(repo, ".kibsu", "install.json"), encoding="utf-8") as fh:
            second = json.load(fh)
        self.assertEqual(
            second["previous_hookspath"], "custom-hooks",
            "a forced re-install must carry the ORIGINAL previous_hookspath forward, "
            "not re-capture kibsu's own hooks dir",
        )

        exit_code, _stdout, stderr = run_tool("install", repo, "--uninstall")
        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)
        self.assertEqual(_hooks_path(repo), "custom-hooks",
                         "uninstall after a forced re-install must still restore the user's own path")

    def test_reinstall_force_records_a_genuinely_new_hookspath_set_since_install(self):
        """The complement: if the user pointed core.hooksPath somewhere else AFTER installing,
        that is a real previous value and must be recorded as one - the carry-forward applies
        only when the current value is in fact ours."""
        repo = make_repo(self.tmpdir, {"doc.md": "hello\n"})
        exit_code, _stdout, stderr = run_tool("install", repo, "--install")
        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)

        os.makedirs(os.path.join(repo, "later-hooks"), exist_ok=True)
        rc, out, err = run_git(repo, "config", "core.hooksPath", "later-hooks")
        self.assertEqual(rc, 0, "git config failed: %s" % (err or out))

        exit_code, _stdout, stderr = run_tool("install", repo, "--install", "--force")
        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)
        with io.open(os.path.join(repo, ".kibsu", "install.json"), encoding="utf-8") as fh:
            rec = json.load(fh)
        self.assertEqual(rec["previous_hookspath"], "later-hooks")

    # ---- refusal: an already-set core.hooksPath is never silently overwritten -------------
    def test_install_refuses_when_hookspath_already_set(self):
        repo = make_repo(self.tmpdir, {"doc.md": "hello\n"})
        rc, out, err = run_git(repo, "config", "core.hooksPath", "some-other-hooks")
        self.assertEqual(rc, 0, "git config failed: %s" % (err or out))

        exit_code, stdout, stderr = run_tool("install", repo, "--install")

        self.assertEqual(exit_code, 3, "expected REFUSED (3); stderr=%r" % stderr)
        self.assertIn("REFUSED", stdout)
        self.assertEqual(
            _hooks_path(repo), "some-other-hooks",
            "a refused install must not touch core.hooksPath",
        )
        self.assertFalse(os.path.isdir(os.path.join(repo, ".kibsu", "bin")))
        self.assertFalse(os.path.isfile(os.path.join(repo, ".kibsu", "install.json")))
        assert_repo_untouched(repo)

    # ---- --status: a read-only report, documented as always 0 ------------------------------
    # ---- uninstall never reaches outside the repo it was pointed at -----------------------

    def test_uninstall_refuses_paths_that_resolve_outside_the_repo(self):
        """A tampered install.json must not turn `--uninstall` into an arbitrary file delete.

        kibsu is pointed at repos it did NOT author - that is the whole job - so .kibsu/install.json
        is untrusted input read off disk, not our own bookkeeping. Before the containment check,
        uninstall built its delete list with a bare os.path.join(root, declared), which silently
        DISCARDS root when `declared` is absolute and happily walks out of the tree on "..".
        Both canaries below are deleted by the unfixed code.
        """
        repo = self._prepare_repo_with_clean_index()
        exit_code, _stdout, stderr = run_tool("install", repo, "--install")
        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)

        outside = os.path.dirname(os.path.abspath(repo))
        traversal_canary = os.path.join(outside, "traversal_canary.txt")
        absolute_canary = os.path.join(outside, "absolute_canary.txt")
        for c in (traversal_canary, absolute_canary):
            with io.open(c, "w", encoding="utf-8") as fh:
                fh.write("must survive uninstall\n")

        ij_path = os.path.join(repo, ".kibsu", "install.json")
        with io.open(ij_path, encoding="utf-8") as fh:
            rec = json.load(fh)
        rec["files_written"] = list(rec.get("files_written", [])) + [
            "../traversal_canary.txt",                       # walks out with ".."
            absolute_canary.replace("\\", "/"),              # absolute: os.path.join drops root
        ]
        with io.open(ij_path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(rec))

        exit_code, stdout, stderr = run_tool("install", repo, "--uninstall")
        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)

        self.assertTrue(os.path.isfile(traversal_canary),
                        "uninstall deleted a file outside the repo via '..' traversal")
        self.assertTrue(os.path.isfile(absolute_canary),
                        "uninstall deleted a file outside the repo via an absolute path")
        # The skip is announced, never silent - the same disclosure rule the size guard follows.
        self.assertIn("refusing to remove", stderr)

    def test_status_exits_zero_and_never_writes_on_a_plain_repo(self):
        """Per install.py's EXIT CODES section, --status always returns 0 - it is a read-only
        report with nothing to fail on, even against a repo that was never installed into (no
        .kibsu/, no core.hooksPath). Not exercised by any test above, which only ever call
        --install/--uninstall."""
        repo = make_repo(self.tmpdir, {"doc.md": "hello\n"})

        exit_code, stdout, stderr = run_tool("install", repo, "--status")

        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)
        self.assertIn("core.hooksPath", stdout)
        assert_repo_untouched(repo)

    def test_install_records_wall_clock_time_and_head_at_install(self):
        """installed_at must record wall-clock install time, while head_at_install records head commit time."""
        repo = self._prepare_repo_with_clean_index()

        exit_code, stdout, stderr = run_tool("install", repo, "--install")
        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)

        ij_path = os.path.join(repo, ".kibsu", "install.json")
        self.assertTrue(os.path.isfile(ij_path))
        with open(ij_path, "r", encoding="utf-8") as fh:
            rec = json.load(fh)

        self.assertIn("installed_at", rec)
        self.assertIn("head_at_install", rec)
        self.assertIsNotNone(rec["installed_at"])

        rc, out, _ = run_git(repo, "log", "-1", "--format=%cI")
        self.assertEqual(rc, 0)
        self.assertEqual(rec["head_at_install"], out.strip())

        exit_code, stdout_status, _ = run_tool("install", repo, "--status")
        self.assertEqual(exit_code, 0)
        self.assertIn("head at install", stdout_status)


class CarriedPreCommitTests(unittest.TestCase):
    """Issue #33: install()'s carry-forward list excluded `pre-commit` unconditionally while
    core.hooksPath redirected git away from .git/hooks - so a repo's pre-existing pre-commit
    hook silently stopped firing: not copied, not chained, not in carried_hooks, invisible in
    the dry-run preview. That contradicted the module docstring's own guarantee ("nothing is
    left behind and nothing is silently disabled") word for word.

    The fix carries it as `pre-commit.carried`, and the generated hook execs it FIRST - its
    failure still blocks, exactly as it did before kibsu arrived. Both tests below ran RED
    against the pre-fix installer (no .carried file; the old hook's evidence file never
    written; a failing old hook no longer blocking anything). Real `git commit` subprocesses
    against the throwaway repo, same as every other hook test in this file."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="kibsu_test_install_carried_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _repo_with_old_precommit(self, hook_body):
        repo = make_repo(self.tmpdir, {"doc.md": "version one\n"})
        idx_exit, _out, idx_err = run_tool("index", repo, "-o", ".kibsu/index.json")
        self.assertEqual(idx_exit, 0, "stderr=%r" % idx_err)
        _commit_all(repo, "build index matching current content")
        hook = os.path.join(repo, ".git", "hooks", "pre-commit")
        if not os.path.isdir(os.path.dirname(hook)):
            os.makedirs(os.path.dirname(hook))
        with open(hook, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(hook_body)
        # The OR-with-existing-mode idiom install.py itself uses - a bare 0o755 mask
        # is the exact overly-permissive-chmod shape CodeQL rightly flags.
        os.chmod(hook, os.stat(hook).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return repo

    def test_issue_33_preexisting_precommit_is_carried_and_still_runs(self):
        repo = self._repo_with_old_precommit(
            '#!/bin/sh\necho carried-hook-ran > "$(git rev-parse --show-toplevel)/hook_evidence.txt"\nexit 0\n'
        )
        exit_code, stdout, stderr = run_tool("install", repo, "--install")
        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)
        self.assertTrue(os.path.isfile(os.path.join(repo, ".kibsu", "hooks", "pre-commit.carried")),
                        "the old pre-commit must be carried, not silently disabled")

        import json as _json
        with open(os.path.join(repo, ".kibsu", "install.json"), encoding="utf-8") as fh:
            rec = _json.load(fh)
        self.assertIn("pre-commit.carried", rec["carried_hooks"], rec)

        with open(os.path.join(repo, "doc.md"), "a", encoding="utf-8", newline="\n") as fh:
            fh.write("more\n")
        run_tool("index", repo, "-o", ".kibsu/index.json")
        rc, _out2, err2 = run_git(repo, "add", "-A")
        self.assertEqual(rc, 0)
        rc, out3, err3 = run_git(repo, *(IDENTITY + ("commit", "-q", "-m", "with both hooks")))
        self.assertEqual(rc, 0, "commit should pass both hooks: %s %s" % (out3, err3))
        self.assertTrue(os.path.isfile(os.path.join(repo, "hook_evidence.txt")),
                        "the carried hook's own logic must actually FIRE on commit")

    def test_issue_33_failing_carried_hook_still_blocks_the_commit(self):
        repo = self._repo_with_old_precommit(
            '#!/bin/sh\necho "old hook says no" >&2\nexit 1\n'
        )
        exit_code, _stdout, stderr = run_tool("install", repo, "--install")
        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)

        commits_before = _commit_count(repo)
        with open(os.path.join(repo, "doc.md"), "a", encoding="utf-8", newline="\n") as fh:
            fh.write("more\n")
        # Re-index BEFORE committing so kibsu's own check is clean - the carried hook must be
        # the ONLY thing standing, or this test would go red/green for the wrong reason.
        run_tool("index", repo, "-o", ".kibsu/index.json")
        run_git(repo, "add", "-A")
        rc, _out, _err = run_git(repo, *(IDENTITY + ("commit", "-q", "-m", "must be blocked")))
        self.assertNotEqual(rc, 0, "the carried hook exits 1 - the commit must block, "
                                    "exactly as it did before kibsu arrived")
        self.assertEqual(_commit_count(repo), commits_before)


if __name__ == "__main__":
    unittest.main()
