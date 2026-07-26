#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for `python -m kibsu install` - wires ns_check to `git commit`, reversibly.

install.py's module docstring now carries an explicit "EXIT CODES" section (added as part of
plan 6.1, closing the gap with check.py/guide.py/discover.py, which already had one), matching
install.py's real behaviour as read from the source: `install()`/`uninstall()` return 0 on
success (including --dry-run) and 3 on every REFUSED path; `status()` always returns 0.

THE PROPERTY THAT MATTERS MOST, per the task: every `git commit` that is meant to exercise the
installed hook is run with cwd = the throwaway fixture repo, via a plain subprocess `git commit`
(never through run_tool, which always runs `python -m kibsu ...` from PACKAGE_ROOT - a directory
where `import kibsu` trivially succeeds and would prove nothing about the clone-and-run case this
tool exists for). Before every such commit, `assert_kibsu_not_importable(repo)` proves - in the
test itself, not by assumption - that a Python process started from that repo directory cannot
import kibsu. The hook's generated shell script never invokes anything through the `kibsu`
package either: it execs the VENDORED `.kibsu/bin/check.py` directly (see install.py's HOOK
template), which is exactly why this works at all in a bare clone.

Only kibsu/install.py's own vendoring/hooksPath/refusal logic is exercised here - the STALE
detection itself (what check.py reports and why) is covered in test_check.py and reused as a
black box: a hook-blocked commit here is verified by exit code and by the presence of check.py's
own "commit blocked by ns_check" text, not by re-deriving STALE semantics.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from support import (
    assert_kibsu_not_importable,
    assert_repo_untouched,
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

        # THE precondition: a plain `python -c "import kibsu"` run from inside this throwaway
        # repo must fail. If it ever silently started succeeding (e.g. a stray PYTHONPATH, or a
        # future change that runs the hook from a different cwd), every assertion below about
        # "this works even when kibsu isn't importable" would stop meaning anything without any
        # test failing to say so - so it is asserted here, not assumed.
        assert_kibsu_not_importable(repo)

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

        assert_kibsu_not_importable(repo)

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


if __name__ == "__main__":
    unittest.main()
