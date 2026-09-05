#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for `python -m kibsu tokens` - the model-tier subagent guard.

tokens.py's module docstring now carries an "EXIT CODES" section (added as part of plan 6.1,
closing the gap with discover/report/guide/learn). It documents, per the source: both --guard
and --ledger are explicitly FAIL-SAFE, NOT FAIL-SHUT - "A broken guard must never wedge the
session. Every unexpected condition exits 0 (allow)". `guard()` returns 0 via `_allow()` on the
allow path AND via `_deny()` on the deny path (a deny still `return 0` at the end of `_deny`) -
so --guard's PROCESS EXIT CODE IS ALWAYS 0, allow or deny. The actual decision only ever shows up
in stdout, as `{"hookSpecificOutput": {..., "permissionDecision": "deny"|"allow", ...}}` for a
deny, or as EMPTY stdout for an allow (an allow "says nothing" - see `_allow`'s own docstring).
This is the behaviour verified below; a naive reader of this docstring block might otherwise
expect --guard to exit 1 on deny, and it never does. --ledger is documented the same way: always
0, best-effort recording.

--selftest is the one place a non-zero code is possible on its own: it returns 1 only if any of
its 9 built-in guard scenarios disagrees with its own expectation, 0 if "all cases pass".

The positive fixture here is exactly the task's own two-part spec: --selftest (which itself
covers deny-on-no-model as one of its 9 built-in cases) plus one explicit standalone
--guard call with a missing `model` field, asserting the JSON deny payload directly. The negative
fixture is a standalone --guard call with `model: sonnet`, asserting the JSON allow behaviour
(empty stdout, exit 0). A third test below exercises --ledger directly (untouched by the other
two), asserting its own documented "always 0" code on a non-spawning event - chosen specifically
because it never touches the real on-disk ledger file (`~/.claude/ns_token_ledger.jsonl`), which
a test suite must never write to as a side effect of merely proving an exit code.
"""
import contextlib
import io
import json
import os
import shutil
import tempfile
import time
import unittest
import unittest.mock as mock

from kibsu import tokens
from support import run_tool


class TokensTests(unittest.TestCase):
    def test_selftest_passes_and_guard_denies_a_missing_model(self):
        """--selftest must report all 9 of its own built-in cases passing (exit 0), and a
        standalone --guard call for a subagent spawn with no `model` field at all must DENY -
        the omission is the failure mode the whole guard exists to catch (an unstated tier
        silently inherits the main-loop model)."""
        exit_code, stdout, stderr = run_tool("tokens", "--selftest")
        self.assertEqual(exit_code, 0, "stderr=%r\nstdout=%r" % (stderr, stdout))
        self.assertIn("all cases pass", stdout)

        event = json.dumps({"tool_name": "Agent", "tool_input": {"prompt": "do something"}})
        exit_code, stdout, stderr = run_tool("tokens", "--guard", input_text=event)

        # The guard's own fail-safe design means the PROCESS exit code is 0 for both allow and
        # deny - the decision lives in stdout, never in the exit code. Assert both explicitly so
        # a future change that broke either one would be caught here.
        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)
        decision = json.loads(stdout)
        self.assertEqual(
            decision["hookSpecificOutput"]["permissionDecision"], "deny",
        )
        self.assertIn("no model", decision["hookSpecificOutput"]["permissionDecisionReason"])

    def test_guard_allows_model_sonnet(self):
        """A subagent spawn explicitly pinned to `model: sonnet` - inside the documented
        ALLOWED_TIERS ceiling - must be allowed: exit 0, and no output at all (an allow prints
        nothing; see `_allow`'s own comment: "a guard that narrates every permitted call is a
        guard nobody leaves switched on")."""
        event = json.dumps({"tool_name": "Agent", "tool_input": {"model": "sonnet"}})
        exit_code, stdout, stderr = run_tool("tokens", "--guard", input_text=event)

        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)
        self.assertEqual(stdout.strip(), "")

    def test_ledger_ignores_a_non_spawning_event_and_exits_zero(self):
        """--ledger is documented as "always 0" - best-effort recording that never fails a tool
        call. Piped a `tool_name` NOT in SPAWNING_TOOLS ("Bash"), `ledger()` returns immediately
        (see the source: `if not isinstance(ev, dict) or ev.get("tool_name") not in
        SPAWNING_TOOLS: return 0`) without ever opening the ledger file - which is exactly why
        this fixture is safe to run in a test suite: it asserts the documented exit code without
        writing to the real `~/.claude/ns_token_ledger.jsonl` on whatever machine runs it."""
        event = json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls"}})
        exit_code, stdout, stderr = run_tool("tokens", "--ledger", input_text=event)

        self.assertEqual(exit_code, 0, "stderr=%r" % stderr)


class ReportTests(unittest.TestCase):
    """Issue #37: `--report` - the ledger/bracket arithmetic half of tokens.py - had zero
    coverage, in the codebase whose own history (CORRECTIONS.md entry #5, survey.py's ledger
    regressions) says bracket arithmetic is the bug-prone class.

    Every test here patches `tokens.LEDGER` to a per-test temp file and calls `report()`
    in-process - this suite must NEVER read or write the real `~/.claude/ns_token_ledger.jsonl`
    (the same law the --ledger test above already observes). The documented 0-vs-3 exit
    contract is driven in BOTH directions, per CONTRIBUTING rule 4: the clean path to 0, and
    each unclean path (missing ledger, unknown-cost rows, unparseable lines) to 3."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="kibsu_test_tokens_report_")
        self.ledger = os.path.join(self.tmpdir, "ledger.jsonl")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @staticmethod
    def _row(tier="sonnet", tokens_n=100, known=True, requested_only=False, age_days=0):
        ts = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time.time() - age_days * 86400))
        row = {"ts": ts, "tokens_known": known, "total_tokens": tokens_n if known else None}
        if requested_only:
            row["requested_tier"] = tier
        else:
            row["resolved_tier"] = tier
        return row

    def _report(self, rows=None, raw_lines=None, days=7, budget=None, write_file=True):
        if write_file:
            with io.open(self.ledger, "w", encoding="utf-8", newline="\n") as fh:
                for r in rows or []:
                    fh.write(json.dumps(r) + "\n")
                for ln in raw_lines or []:
                    fh.write(ln + "\n")
        out = io.StringIO()
        with mock.patch.object(tokens, "LEDGER", self.ledger):
            with contextlib.redirect_stdout(out):
                rc = tokens.report(days, budget)
        return rc, out.getvalue()

    def test_clean_ledger_exits_zero_and_sums_by_tier(self):
        rc, out = self._report(rows=[
            self._row("sonnet", 1000), self._row("sonnet", 500), self._row("haiku", 200),
            self._row("sonnet", 9999, age_days=30),  # outside the window - must not count
        ])
        self.assertEqual(rc, 0, out)
        self.assertIn("3 runs, 1,700 tokens counted.", out)
        self.assertNotIn("ABOVE", out)

    def test_over_ceiling_tier_is_marked_and_summed(self):
        rc, out = self._report(rows=[self._row("sonnet", 100), self._row("opus", 500)])
        self.assertEqual(rc, 0, "over-ceiling spend is a finding, not an incomplete report")
        self.assertIn("x opus", out)
        self.assertIn("500 tokens ran ABOVE the sonnet/haiku ceiling.", out)

    def test_unknown_cost_rows_force_exit_three_and_the_higher_not_equal_note(self):
        rc, out = self._report(rows=[self._row("sonnet", 100), self._row("sonnet", known=False)])
        self.assertEqual(rc, 3, out)
        self.assertIn("1 of 2 runs recorded NO token count", out)
        self.assertIn("the real total is HIGHER, not equal", out)

    def test_unparseable_lines_force_exit_three_and_are_counted(self):
        rc, out = self._report(rows=[self._row("sonnet", 100)], raw_lines=["{not json"])
        self.assertEqual(rc, 3, out)
        self.assertIn("1 unparseable ledger lines skipped.", out)

    def test_missing_ledger_exits_three_not_zero(self):
        rc, out = self._report(write_file=False)
        self.assertEqual(rc, 3, out)
        self.assertIn("NOT the same as nothing was spent", out)

    def test_tier_falls_back_requested_then_undeclared(self):
        rc, out = self._report(rows=[
            self._row("haiku", 10, requested_only=True),
            {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "tokens_known": True, "total_tokens": 7},
        ])
        self.assertEqual(rc, 0, out)
        self.assertIn("haiku", out)
        self.assertIn("(undeclared)", out)

    def test_weekly_budget_prints_share_and_its_absence_says_cannot_evaluate(self):
        rc_with, out_with = self._report(rows=[self._row("sonnet", 150)], budget=1000)
        self.assertIn("15.0% of the 1,000 weekly budget.", out_with)
        rc_without, out_without = self._report(rows=[self._row("sonnet", 150)])
        self.assertIn("CANNOT be evaluated", out_without)
        self.assertEqual((rc_with, rc_without), (0, 0))


if __name__ == "__main__":
    unittest.main()
