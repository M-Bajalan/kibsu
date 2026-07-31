#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regression tests for the interpreter-resolution bug in the two installed pre-commit hook
templates: kibsu/gate.py's HOOK and kibsu/install.py's HOOK.

WHY THIS FILE EXISTS
  Both templates used to resolve `python` the same fragile way:

      command -v python >/dev/null 2>&1 && py=python || py=python3

  `command -v python` only proves a file named `python` is on PATH - it does not prove that
  file behaves like an interpreter. Windows ships exactly such a file even on a machine with NO
  real Python installed: the stock "App Execution Alias" stub. Running it prints a Microsoft
  Store nag to stderr and exits 49; it never reads stdin, never imports anything, and is not
  Python.

  gate.py's hook `exec`s straight into whatever that resolves to, so exit 49 becomes the
  COMMIT's exit code - every single commit BLOCKED, which is the exact opposite of the
  FAIL-SAFE, NOT FAIL-SHUT invariant gate.py's own module docstring states two paragraphs above
  the old HOOK constant. install.py's hook fares no better in the opposite direction: its
  if-chain only handles rc 1 (block) and rc 3 (warn-and-allow); rc 49 matches neither, falls
  through the whole chain, and lands on the trailing `exit 0` - silently ALLOWED, nothing
  checked, and no message telling anyone that happened.

  These tests assert the STATIC, RENDERED hook text - not a live invocation - so they reproduce
  and pin the fix without needing an actual App Execution Alias stub on the test machine. That
  is also why they import gate.py/install.py directly from THIS checkout (PACKAGE_ROOT is put
  ahead of everything else on sys.path) rather than trusting a possibly pip-installed `kibsu`:
  the whole point is to examine the source under test, not whatever happens to be on site-packages.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
PACKAGE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PACKAGE_ROOT)

from kibsu import gate as gate_mod
from kibsu import install as install_mod

# The exact old, unvalidated one-liner both templates used to share - presence via `command -v`,
# nothing more. Its disappearance is itself part of what these tests pin: a stub that satisfies
# `command -v` must no longer be trusted just because it is found.
OLD_GATE_LINE = 'command -v python >/dev/null 2>&1 && py=python || py=python3'
OLD_INSTALL_LINE = 'command -v python >/dev/null 2>&1 && PY=python || PY=python3'


def _index_or_fail(text, needle, label):
    i = text.find(needle)
    if i == -1:
        raise AssertionError("expected %r to appear in the rendered hook (%s), it did not" % (needle, label))
    return i


class GateHookTemplateTests(unittest.TestCase):
    """kibsu/gate.py's HOOK constant, rendered exactly as install() renders it."""

    def setUp(self):
        self.hook = gate_mod.HOOK.format(v=gate_mod.VERSION, bin=".kibsu/bin")

    def test_old_naive_presence_check_is_gone(self):
        self.assertNotIn(OLD_GATE_LINE, self.hook)

    def test_each_candidate_is_validated_by_actually_running_it(self):
        # Presence (`command -v`) is not enough - each candidate must be invoked with
        # `-c "import sys"`, output discarded, before it is trusted.
        self.assertIn('-c "import sys"', self.hook)
        self.assertIn('>/dev/null 2>&1', self.hook)

    def test_candidates_tried_in_order_python3_then_python_then_py_dash_3(self):
        i3 = _index_or_fail(self.hook, "try_py python3;", "gate hook")
        ip = _index_or_fail(self.hook, "try_py python;", "gate hook")
        ipy = _index_or_fail(self.hook, "try_py py -3;", "gate hook")
        self.assertLess(i3, ip, "python3 must be tried before python")
        self.assertLess(ip, ipy, '"python" must be tried before "py -3"')

    def test_py_dash_3_is_not_split_into_an_array(self):
        # POSIX sh has no arrays; "py -3" must travel as a two-word command tried via a function,
        # never as a bracketed/array construct.
        self.assertNotIn("py[", self.hook)
        self.assertNotIn("${py[", self.hook)

    def test_no_working_python_warns_kibsu_branded_and_allows(self):
        self.assertIn("no working python found", self.hook)
        self.assertIn("commit ALLOWED", self.hook)
        self.assertIn("nothing was verified", self.hook)
        self.assertIn("this is not a pass", self.hook)
        self.assertIn("kibsu gate:", self.hook)

    def test_execution_alias_stub_named_as_the_reason(self):
        # A comment naming the actual failure mode this validation exists to survive.
        self.assertIn("App Execution Alias", self.hook)

    def test_still_execs_the_vendored_gate_tool_on_success(self):
        # The fix must not disturb the real dispatch once a working interpreter is found.
        self.assertIn('exec $py "$gate_tool" --check --repo "$root"', self.hook)

    def test_missing_gate_tool_check_still_present(self):
        # Pre-existing fail-safe behaviour (vendored gate.py gone) must survive untouched.
        self.assertIn("gate.py missing from", self.hook)


class InstallHookTemplateTests(unittest.TestCase):
    """kibsu/install.py's HOOK constant, rendered exactly as install() renders it."""

    def setUp(self):
        self.hook = install_mod.HOOK.format(
            v=install_mod.VERSION, index=".kibsu/index.json", baseline="",
        )

    def test_old_naive_presence_check_is_gone(self):
        self.assertNotIn(OLD_INSTALL_LINE, self.hook)

    def test_each_candidate_is_validated_by_actually_running_it(self):
        self.assertIn('-c "import sys"', self.hook)
        self.assertIn('>/dev/null 2>&1', self.hook)

    def test_candidates_tried_in_order_python3_then_python_then_py_dash_3(self):
        i3 = _index_or_fail(self.hook, "try_py python3;", "install hook")
        ip = _index_or_fail(self.hook, "try_py python;", "install hook")
        ipy = _index_or_fail(self.hook, "try_py py -3;", "install hook")
        self.assertLess(i3, ip, "python3 must be tried before python")
        self.assertLess(ip, ipy, '"python" must be tried before "py -3"')

    def test_no_working_python_warns_kibsu_branded_and_allows(self):
        self.assertIn("no working python found", self.hook)
        self.assertIn("commit ALLOWED", self.hook)
        self.assertIn("nothing was verified", self.hook)
        self.assertIn("this is not a pass", self.hook)
        self.assertIn("kibsu install:", self.hook)

    def test_execution_alias_stub_named_as_the_reason(self):
        self.assertIn("App Execution Alias", self.hook)

    # ---- the failure install.py had that gate.py did not: an rc that is neither 0, 1 nor 3 ----
    def test_unexpected_rc_branch_exists_and_is_kibsu_branded(self):
        # rc=49 (the stub's own exit code) used to match neither the exit-1 (block) nor exit-3
        # (warn-and-allow) branch and fall through, unannounced, to the trailing `exit 0`. Any rc
        # outside {0, 1, 3} must now be named and reported before the commit is allowed.
        self.assertIn("$rc", self.hook)
        self.assertIn("neither 0, 1, nor 3", self.hook)
        self.assertIn("commit ALLOWED", self.hook)
        self.assertIn("nothing was verified", self.hook)
        self.assertIn("kibsu install:", self.hook)

    def test_existing_block_and_warn_branches_still_present(self):
        # Pre-existing rc==1 (block) and rc==3 (warn-and-allow) handling must survive untouched.
        self.assertIn("commit blocked by ns_check", self.hook)
        self.assertIn("ns_check COULD NOT RUN (exit 3)", self.hook)

    def test_still_runs_the_vendored_checker_on_success(self):
        self.assertIn('$PY "$NS_TOOL" "$ROOT" --staged --index', self.hook)


if __name__ == "__main__":
    unittest.main()
