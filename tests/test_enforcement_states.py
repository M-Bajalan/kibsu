#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The discover -> guide enforcement-state contract (issues #32 and #35).

Issue #32's shape: discover.py COMPUTES which mandated scripts are unenforced, monitored, or
live - then reported it only as prose, and guide.py's buckets() regexed that prose. The
schedule-only branch emitted no evidence and a detail string the regexes never matched, so
every merely-MONITORED script fell through buckets()'s else-branch to ENFORCED - "you do not
need to remember these" - the exact inversion guide.py's own docstring forbids (discovering
red on Sunday is not preventing it). The fix: discover attaches a machine-readable `scripts`
map to the Mandated-gates capability and guide consumes it; the prose stays for humans, and
the regex parse stays only as a fallback for older discover JSON.

Issue #35's shape: discover's one-level hook indirection collapsed any `$`-containing path to
its bare basename probed at repo root, so kibsu's OWN installed hook (`$ROOT/.kibsu/bin/
check.py`) was invisible and a genuinely-enforced gate read INERT. The fix probes the
variable-stripped, root-relative remainder first.

discover.main() is run IN-PROCESS with `os_scheduler_text` patched (subprocess would put it
out of reach and make the verdict depend on whatever the host machine's real scheduler
happens to run - the same dependency-injection-at-the-test-boundary reasoning as
tests/test_survey.py's _SurveyRun). Per CONTRIBUTING rule 4, the two defect tests here were
run RED against the pre-fix code first; the red outputs are quoted in the fixing PR.
"""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
import unittest.mock as mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from support import make_repo
from kibsu import discover, guide


def _discover_json(repo, sched_text):
    out = io.StringIO()
    with mock.patch.object(discover, "os_scheduler_text", return_value=sched_text), \
         mock.patch.object(sys, "argv", ["discover", repo, "--json"]):
        with contextlib.redirect_stdout(out):
            rc = discover.main()
    return rc, json.loads(out.getvalue())


def _gates_cap(disc):
    return next(c for c in disc["capabilities"] if c["capability"] == "Mandated gates")


class ScheduleOnlyGateStateTests(unittest.TestCase):
    """Issue #32: the Weekly_Lint_Job scenario from discover.py's own module docstring."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="kibsu_test_states_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _repo(self):
        return make_repo(self.tmpdir, {
            "fake_gate.py": "print('checking')\n",
            "CLAUDE.md": "Before commit, run `python fake_gate.py` to check everything.\n",
        })

    def test_schedule_only_script_is_machine_readable_monitored_not_enforced(self):
        """Pre-fix: the schedule-only INERT branch carried no `scripts` map (KeyError here)
        and buckets() classified fake_gate.py as ENFORCED - the harmful inversion."""
        repo = self._repo()
        rc, disc = _discover_json(repo, sched_text="daily task: python fake_gate.py")
        gates = _gates_cap(disc)

        self.assertEqual(gates["state"], "INERT", gates)
        self.assertEqual(gates.get("scripts"), {"fake_gate.py": "monitored"}, gates)

        table = guide.buckets(repo, disc)
        self.assertEqual(table["fake_gate.py"][0], "MONITORED",
                         "a weekly schedule discovers red, it does not prevent it - this "
                         "must never read as ENFORCED")

    def test_live_script_maps_to_enforced_through_the_same_field(self):
        """The guard in the other direction: a genuinely CI-run script still lands ENFORCED
        via the structured field, not by falling through a broken parse."""
        repo = make_repo(self.tmpdir, {
            "fake_gate.py": "print('checking')\n",
            "CLAUDE.md": "Before commit, run `python fake_gate.py` to check everything.\n",
            ".github/workflows/ci.yml": (
                "name: CI\non: [push]\njobs:\n  check:\n    runs-on: ubuntu-latest\n"
                "    steps:\n      - run: python fake_gate.py\n"
            ),
        })
        rc, disc = _discover_json(repo, sched_text="")
        gates = _gates_cap(disc)

        self.assertEqual(gates["state"], "live", gates)  # LIVE constant is lowercase
        self.assertEqual(gates.get("scripts"), {"fake_gate.py": "live"}, gates)
        table = guide.buckets(repo, disc)
        self.assertEqual(table["fake_gate.py"][0], "ENFORCED")

    def test_buckets_regex_fallback_still_reads_older_discover_json(self):
        """Older discover output (no `scripts` field) must keep working through the prose
        parse - the mixed unenforced+monitored detail phrase is the one shape the old
        regexes did handle, pinned here so the fallback cannot rot silently."""
        repo = self._repo()
        disc = {"capabilities": [{
            "capability": "Mandated gates", "state": "INERT",
            "detail": "1 of 2 script(s)... (1 more run on a schedule, which MONITORS but "
                      "cannot block a commit: fake_gate.py)",
            "evidence": "other.py (named in CLAUDE.md)",
        }]}
        table = guide.buckets(repo, disc)
        self.assertEqual(table["fake_gate.py"][0], "MONITORED")


class HookIndirectionTests(unittest.TestCase):
    """Issue #35: a live hook delegating through a `$VAR/nested/path` wrapper."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="kibsu_test_hookvar_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_dollar_var_nested_wrapper_is_followed_and_gate_reads_live(self):
        """The hook names only `$ROOT/.kibsu/bin/check.py` - kibsu's OWN installed-hook
        idiom. The wrapper, not the hook, names the mandated script. Pre-fix the resolver
        probed a bare `check.py` at repo root, never found the wrapper, and reported the
        gate INERT ('invoked by no automation at all') - a false verdict on the tool's own
        primary layout."""
        repo = make_repo(self.tmpdir, {
            "scripts/ruff_check.py": "print('lint')\n",
            "CLAUDE.md": "Before commit, run `python scripts/ruff_check.py` first.\n",
            ".kibsu/bin/check.py": "# wrapper\n# runs scripts/ruff_check.py for the gate\n",
        })
        hook_dir = os.path.join(repo, ".git", "hooks")
        if not os.path.isdir(hook_dir):
            os.makedirs(hook_dir)
        with open(os.path.join(hook_dir, "pre-commit"), "w", encoding="utf-8",
                  newline="\n") as fh:
            fh.write('#!/bin/sh\nROOT="$(git rev-parse --show-toplevel)"\n'
                     'NS_TOOL="$ROOT/.kibsu/bin/check.py"\nexec python "$NS_TOOL"\n')

        rc, disc = _discover_json(repo, sched_text="")
        gates = _gates_cap(disc)
        self.assertEqual(gates["state"], "live",  # LIVE constant is lowercase
                         "the gate IS invoked - through the $VAR wrapper the live hook "
                         "execs; got: %r" % gates)

    def test_truly_absent_wrapper_still_reads_inert(self):
        """The negative control: the same $VAR hook shape pointing at a wrapper that does
        not exist anywhere must stay INERT - following indirection must not invent
        enforcement."""
        repo = make_repo(self.tmpdir, {
            "scripts/ruff_check.py": "print('lint')\n",
            "CLAUDE.md": "Before commit, run `python scripts/ruff_check.py` first.\n",
        })
        hook_dir = os.path.join(repo, ".git", "hooks")
        if not os.path.isdir(hook_dir):
            os.makedirs(hook_dir)
        with open(os.path.join(hook_dir, "pre-commit"), "w", encoding="utf-8",
                  newline="\n") as fh:
            fh.write('#!/bin/sh\nNS_TOOL="$ROOT/.kibsu/bin/check.py"\nexec python "$NS_TOOL"\n')

        rc, disc = _discover_json(repo, sched_text="")
        self.assertEqual(_gates_cap(disc)["state"], "INERT")


if __name__ == "__main__":
    unittest.main()
