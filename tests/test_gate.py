#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for `python -m kibsu gate` - the commit gate driven by configured commands.

Per gate.py's own module docstring:
    EXIT CODES
      0  pass, or could-not-run (fail-safe)      1  BLOCKED - a new violation

Every "cmd" entry under .kibsu.json's "gates" key is a bare, standalone script (no `import
kibsu`, no `from kibsu import ...`) - `tests/fixtures/gate_widgets.py` and `gate_flaky.py`
(written per-test into the fixture repo, not checked in here) simply read a text file and print
the shared `[RULE] Title (N): / "    - item"` contract gate.py's own docstring documents. This
means the configured gate commands themselves have no bearing on the "is kibsu importable"
question at all - only gate.py and config.py (vendored into .kibsu/bin/ at install time) matter
for that, exactly as install.py vendors check.py/index.py for the same reason.

Every commit meant to exercise the installed hook is a real `git commit` subprocess with
cwd = the throwaway repo (never run_tool, which always runs from PACKAGE_ROOT). Before each one,
`assert_vendored_copy_matches_source(repo, "gate.py", "config.py")` proves - in the test, not by
assumption - that the path gate.py's own HOOK template hard-codes ("$root/.kibsu/bin/gate.py")
really is this checkout's vendored snapshot, byte-for-byte. That is the property that actually
matters: the hook execs that path directly, never `python -m kibsu`, so it never depends on
whether `kibsu` happens to be importable anywhere on this machine.
"""
import os
import shutil
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

# A minimal gate command: reads widgets.txt (one violation description per non-blank line) and
# prints the shared "[RULE] Title (N): / '    - item'" contract every configured gate command is
# expected to speak (see gate.py's own module docstring). Deliberately has no dependency on
# kibsu at all - a real gate command in the wild is somebody's own linter, not kibsu's code.
GATE_WIDGETS_SCRIPT = (
    "import os\n"
    "lines = []\n"
    "if os.path.isfile('widgets.txt'):\n"
    "    with open('widgets.txt', encoding='utf-8') as f:\n"
    "        lines = [l.strip() for l in f if l.strip()]\n"
    "print('[R1] Widgets (%d):' % len(lines))\n"
    "for l in lines:\n"
    "    print('    - %s' % l)\n"
)

# A gate command that can never run in this environment - the "cannot_run_exit" case.
GATE_FLAKY_SCRIPT = (
    "import sys\n"
    "sys.stderr.write('gate_flaky: this checker cannot run here\\n')\n"
    "sys.exit(42)\n"
)


def _commit_all(repo, message):
    rc, out, err = run_git(repo, "add", "-A")
    assert rc == 0, "git add -A failed: %s" % (err or out)
    rc, out, err = run_git(repo, *(IDENTITY + ("commit", "-q", "-m", message)))
    assert rc == 0, "git commit failed: %s" % (err or out)


def _commit_count(repo):
    rc, out, err = run_git(repo, "rev-list", "--count", "HEAD")
    assert rc == 0, "git rev-list failed: %s" % (err or out)
    return int(out.strip())


def _write(repo, relpath, content):
    full = os.path.join(repo, relpath.replace("/", os.sep))
    parent = os.path.dirname(full)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    with open(full, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(content)


class GateTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="kibsu_test_gate_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _install_with_one_accepted_violation(self, extra_files=None):
        """A repo with the "widgets" gate configured, one pre-existing violation ("a") already
        baselined, and the hook installed and committed. Returns the repo path."""
        files = {
            "gate_widgets.py": GATE_WIDGETS_SCRIPT,
            "widgets.txt": "a\n",
            ".kibsu.json": '{"gates": [{"name": "widgets", "cmd": ["python", "gate_widgets.py"]}]}\n',
        }
        if extra_files:
            files.update(extra_files)
        repo = make_repo(self.tmpdir, files)

        baseline_exit, _out, baseline_err = run_tool("gate", "--baseline", "--repo", repo)
        self.assertEqual(baseline_exit, 0, "stderr=%r" % baseline_err)
        self.assertTrue(os.path.isfile(os.path.join(repo, ".kibsu", "gate_baseline.json")))
        _commit_all(repo, "accept the pre-existing widgets violation")

        install_exit, install_out, install_err = run_tool(
            "gate", "--install", "--apply", "--repo", repo,
        )
        self.assertEqual(install_exit, 0, "stderr=%r" % install_err)
        self.assertIn("INSTALLED", install_out)
        for name in ("gate.py", "config.py"):
            self.assertTrue(os.path.isfile(os.path.join(repo, ".kibsu", "bin", name)))
        _commit_all(repo, "install the gate hook")
        return repo

    # ---- positive: a new violation blocks, and is named --------------------------------
    def test_new_violation_blocks_commit_and_names_it(self):
        repo = self._install_with_one_accepted_violation()
        commits_before = _commit_count(repo)
        assert_vendored_copy_matches_source(repo, "gate.py", "config.py")

        with open(os.path.join(repo, "widgets.txt"), "a", encoding="utf-8", newline="\n") as fh:
            fh.write("b\n")
        rc, out, err = run_git(repo, "add", "-A")
        self.assertEqual(rc, 0, "git add -A failed: %s" % (err or out))

        rc, out, err = run_git(repo, *(IDENTITY + ("commit", "-m", "introduce a new violation")))

        self.assertNotEqual(rc, 0, "expected the commit to be BLOCKED")
        combined = out + err
        self.assertIn("COMMIT BLOCKED by kibsu gate", combined)
        self.assertIn("[R1] b", combined)
        self.assertEqual(_commit_count(repo), commits_before)

    # ---- negative: clean vs baseline allows the commit ----------------------------------
    def test_clean_against_baseline_allows_commit(self):
        repo = self._install_with_one_accepted_violation(
            extra_files={"README.md": "# hi\n"},
        )
        commits_before = _commit_count(repo)
        assert_vendored_copy_matches_source(repo, "gate.py", "config.py")

        # a legitimate change that does not touch widgets.txt at all - the gate's output is
        # therefore identical to what was baselined.
        with open(os.path.join(repo, "README.md"), "a", encoding="utf-8", newline="\n") as fh:
            fh.write("more stuff\n")
        rc, out, err = run_git(repo, "add", "-A")
        self.assertEqual(rc, 0, "git add -A failed: %s" % (err or out))

        rc, out, err = run_git(repo, *(IDENTITY + ("commit", "-m", "unrelated, clean change")))

        self.assertEqual(rc, 0, "expected the commit to be ALLOWED; stdout=%r stderr=%r" % (out, err))
        self.assertIn("kibsu gate: PASS", out + err)
        self.assertEqual(_commit_count(repo), commits_before + 1)

    # ---- gitignored: a violation on an ignored path never blocks --------------------------
    def test_gitignored_violation_does_not_block(self):
        repo = self._install_with_one_accepted_violation(
            extra_files={".gitignore": "build/output.log\n"},
        )
        commits_before = _commit_count(repo)
        assert_vendored_copy_matches_source(repo, "gate.py", "config.py")

        # a "new" violation, per identity, but it names a path git itself ignores - gate.py's
        # `ignored()` must exclude it from blocking (see gate.py's PATHISH_RE / ignored()).
        with open(os.path.join(repo, "widgets.txt"), "a", encoding="utf-8", newline="\n") as fh:
            fh.write("build/output.log has junk\n")
        rc, out, err = run_git(repo, "add", "-A")
        self.assertEqual(rc, 0, "git add -A failed: %s" % (err or out))

        rc, out, err = run_git(
            repo, *(IDENTITY + ("commit", "-m", "violation on a gitignored path only")),
        )

        self.assertEqual(rc, 0, "expected the commit to be ALLOWED; stdout=%r stderr=%r" % (out, err))
        self.assertIn("kibsu gate: PASS", out + err)
        self.assertIn("not gated (gitignored", out + err)
        self.assertEqual(_commit_count(repo), commits_before + 1)

    # ---- cannot-run: one gate skipped with a warning, the other still enforced -----------
    def test_gate_that_cannot_run_is_skipped_and_others_still_enforce(self):
        files = {
            "gate_widgets.py": GATE_WIDGETS_SCRIPT,
            "gate_flaky.py": GATE_FLAKY_SCRIPT,
            "widgets.txt": "a\n",
            ".kibsu.json": (
                '{"gates": ['
                '{"name": "widgets", "cmd": ["python", "gate_widgets.py"]}, '
                '{"name": "flaky", "cmd": ["python", "gate_flaky.py"], "cannot_run_exit": 42}'
                ']}\n'
            ),
        }
        repo = make_repo(self.tmpdir, files)

        # baseline: "flaky" cannot run even now and is NOT recorded; "widgets" is.
        baseline_exit, baseline_out, baseline_err = run_tool("gate", "--baseline", "--repo", repo)
        self.assertEqual(baseline_exit, 0, "stderr=%r" % baseline_err)
        self.assertIn("flaky", baseline_out)
        self.assertIn("CANNOT RUN", baseline_out)
        _commit_all(repo, "baseline widgets; flaky cannot be baselined")

        install_exit, _out, install_err = run_tool("gate", "--install", "--apply", "--repo", repo)
        self.assertEqual(install_exit, 0, "stderr=%r" % install_err)
        _commit_all(repo, "install the gate hook")
        commits_before = _commit_count(repo)
        assert_vendored_copy_matches_source(repo, "gate.py", "config.py")

        # widgets.txt is UNCHANGED (still just "a", matching the baseline) - so if the surviving
        # gate is still genuinely evaluated (not merely skipped along with the flaky one), the
        # commit must be ALLOWED. A README touch is enough to trigger the hook.
        _write(repo, "README.md", "# hi\n")
        rc, out, err = run_git(repo, "add", "-A")
        self.assertEqual(rc, 0, "git add -A failed: %s" % (err or out))

        rc, out, err = run_git(repo, *(IDENTITY + ("commit", "-m", "flaky gate is down")))

        combined = out + err
        self.assertEqual(rc, 0, "expected ALLOWED (fail-safe skip); stdout=%r stderr=%r" % (out, err))
        self.assertIn("CANNOT RUN", combined)
        self.assertIn("flaky", combined)
        # proof the OTHER gate was actually run and judged, not silently skipped too:
        self.assertIn("widgets clean", combined)
        self.assertEqual(_commit_count(repo), commits_before + 1)

    # ---- fail-safe: the vendored gate.py itself goes missing -----------------------------
    def test_missing_vendored_gate_allows_commit_with_warning(self):
        repo = self._install_with_one_accepted_violation()
        os.remove(os.path.join(repo, ".kibsu", "bin", "gate.py"))
        commits_before = _commit_count(repo)
        # gate.py itself was just deliberately removed above - that IS this test's scenario, so
        # only config.py's identity is provable here. What matters (that the hook's warning names
        # the exact missing path and still allows the commit) is asserted directly, below.
        assert_vendored_copy_matches_source(repo, "config.py")

        # a genuine NEW violation - if the fail-safe path did not fire, this would BLOCK.
        with open(os.path.join(repo, "widgets.txt"), "a", encoding="utf-8", newline="\n") as fh:
            fh.write("b\n")
        rc, out, err = run_git(repo, "add", "-A")
        self.assertEqual(rc, 0, "git add -A failed: %s" % (err or out))

        rc, out, err = run_git(
            repo, *(IDENTITY + ("commit", "-m", "gate.py missing, should still be allowed")),
        )

        self.assertEqual(rc, 0, "expected ALLOWED despite a real new violation; stdout=%r stderr=%r" % (out, err))
        self.assertIn("gate.py missing from", err)
        self.assertIn("commit ALLOWED, nothing was verified", err)
        self.assertEqual(_commit_count(repo), commits_before + 1)

    # ---- no gates configured: an honest abstention, not a silent pass --------------------
    def test_no_gates_configured_is_an_explicit_abstention(self):
        repo = make_repo(self.tmpdir, {"README.md": "# hi\n"})

        exit_code, stdout, stderr = run_tool("gate", "--check", "--repo", repo)

        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)
        self.assertIn("no gates configured", stdout)
        self.assertIn("nothing was checked", stdout)
        assert_repo_untouched(repo)


if __name__ == "__main__":
    unittest.main()
