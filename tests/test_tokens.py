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
import json
import unittest

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


if __name__ == "__main__":
    unittest.main()
