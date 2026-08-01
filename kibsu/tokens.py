#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ns_tokens.py  v1.0.0  -  make the model-tier rule CHECKABLE instead of claimable.

WHY THIS EXISTS
  This repo's model-tier ladder - Cline first, Sonnet executes, Opus plans - is written in CLAUDE.md,
  in a memory file, and re-read at the top of every session. On 2026-07-25 it was violated
  anyway: nine Opus subagents, 1,453,674 tokens, on work that was textbook executor work.
  The rule was fresh, the author was watching, and cost was explicitly under discussion. It
  still lost.

  That is the definition of a CLAIMABLE instruction: the only thing standing between the rule
  and the spend is an agent remembering. Writing it a fourth time, in bolder type, changes
  nothing. This file is the fourth statement of the rule expressed as a mechanism instead.

THREE MODES, ONE FILE
  --guard    PreToolUse.  Reads the tool call on stdin, DENIES a subagent that is not
             explicitly pinned to an allowed tier. Refusal, not reminder.
  --ledger   PostToolUse. Appends what the subagent actually cost to a JSONL ledger.
  --report   Reads the ledger and answers "how much did subagents cost this week" - a
             question neither the operator nor the agent could previously answer at all.

FAIL-SAFE, NOT FAIL-SHUT
  A broken guard must never wedge the session. Every unexpected condition exits 0 (allow)
  and complains on stderr. The one thing worse than an unenforced rule is a gate that blocks
  everything for a reason nobody can see. Same posture as ns_check's exit 3.

Dependency-free. Python 3.8+.

EXIT CODES
  --guard     always 0 - allow AND deny both exit 0. This is the fail-safe design stated above,
              not an oversight: the decision a hook consumer needs is carried in the JSON
              printed to stdout (`hookSpecificOutput.permissionDecision`: "deny" plus a reason
              - or empty stdout for an allow), never in the process exit code.
  --ledger    always 0. Recording is best-effort: a write failure is warned on stderr and
              swallowed, never surfaced as a non-zero exit.
  --selftest  0  every one of its 9 built-in guard scenarios matched its own expectation.
              1  at least one scenario disagreed with its expectation ("do not install" is
                 printed) - the only place this file returns 1.
  --report    0  the ledger file exists and every row read parsed cleanly with a known token
                 count.
              3  the ledger file does not exist yet, OR at least one row's token count is
                 unknown (a background subagent launch whose cost had not yet been reported) or
                 unparseable - the report still ran and printed, but its total is a floor, not
                 a fact.
  Any unhandled exception anywhere in main() is caught by the top-level `__main__` guard at the
  bottom of this file and forced to exit 0 ("never wedge the session") - the same fail-safe
  posture applies to the whole tool, not only to --guard.

  python -m kibsu tokens --guard              < hook JSON on stdin
  python -m kibsu tokens --ledger             < hook JSON on stdin
  python -m kibsu tokens --report [--weekly-budget N] [--days 7]
"""
import argparse
import io
import json
import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

VERSION = "1.0.0"

# The ceiling, not the floor. Set 2026-07-25: "not more than sonnet".
ALLOWED_TIERS = ("sonnet", "haiku")

# Tools that spawn a subagent and therefore spend on a tier we care about. Workflow is listed
# speculatively - it is NOT in the documented PreToolUse matcher list, so the guard may simply
# never be invoked for it. --selftest reports that honestly rather than implying coverage.
SPAWNING_TOOLS = ("Agent", "Workflow")

LEDGER = os.path.join(os.path.expanduser("~"), ".claude", "ns_token_ledger.jsonl")


def _warn(msg):
    sys.stderr.write("ns_tokens: %s\n" % msg)


def _read_stdin_json():
    raw = sys.stdin.read()
    if not raw.strip():
        return None
    return json.loads(raw)


def _allow():
    """Say nothing, exit 0. The overwhelmingly common path - a guard that narrates every
    permitted call is a guard nobody leaves switched on."""
    return 0


def _deny(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        # Shown to Claude, not the user. So it is written AT the model: state the rule, the
        # exact fix, and why - a bare "denied" just produces a retry of the same call.
        "permissionDecisionReason": reason,
    }}))
    return 0


def _tier_of(model):
    """Normalise 'claude-sonnet-5', 'sonnet', 'claude-haiku-4-5-20251001' -> 'sonnet'/'haiku'."""
    if not model:
        return None
    m = str(model).lower()
    for known in ("haiku", "sonnet", "opus", "fable"):
        if known in m:
            return known
    return m


# ----------------------------------------------------------------------------- guard --------
def guard():
    try:
        ev = _read_stdin_json()
    except Exception as e:
        _warn("stdin was not JSON (%s) - allowing" % e)
        return _allow()
    if not isinstance(ev, dict):
        return _allow()

    tool = ev.get("tool_name")
    if tool not in SPAWNING_TOOLS:
        return _allow()

    inp = ev.get("tool_input") or {}
    model = inp.get("model")
    tier = _tier_of(model)

    if tier in ALLOWED_TIERS:
        return _allow()

    allowed = " or ".join("model: '%s'" % t for t in ALLOWED_TIERS)

    if tier is None:
        # Omission is the actual failure mode, not a wrong value. The parameter is silent when
        # absent - it inherits the main loop, which is Opus - and nothing warns. Requiring it
        # explicitly is the whole point: an explicit tier at every call site is greppable, so
        # the rule becomes checkable from the repo instead of asserted in a document.
        #
        # NOTE this also fires when a custom agent definition sets its own model in frontmatter.
        # That is deliberate. The hook cannot see that frontmatter, and a rule that trusts an
        # invisible declaration is back to being claimable. Pass it explicitly anyway.
        return _deny(
            "BLOCKED by this repo's subagent model policy: this %s call declares no model, so it "
            "would silently inherit the main-loop model (Opus). Re-issue with %s.\n"
            "Sonnet is the CEILING for subagents, not the floor - including synthesis and "
            "judgment agents. If a custom agent definition already sets its tier, pass it "
            "explicitly anyway: the hook cannot read that frontmatter, and an unstated tier is "
            "how 1,453,674 Opus tokens were spent on executor work on 2026-07-25."
            % (tool, allowed))

    return _deny(
        "BLOCKED by this repo's subagent model policy: this %s call requests '%s', which is above "
        "the subagent ceiling. Re-issue with %s.\n"
        "Opus is the main loop only. If this task genuinely cannot be done at or below Sonnet, "
        "say so to the user and let them lift the ceiling - do not lift it yourself."
        % (tool, model, allowed))


# ---------------------------------------------------------------------------- ledger --------
def ledger():
    """Record what a subagent ACTUALLY cost. Never blocks, never fails a tool call."""
    try:
        ev = _read_stdin_json()
        if not isinstance(ev, dict) or ev.get("tool_name") not in SPAWNING_TOOLS:
            return 0
        resp = ev.get("tool_response") or {}
        if not isinstance(resp, dict):
            resp = {}

        requested = (ev.get("tool_input") or {}).get("model")
        # totalTokens is absent for a background launch (status "async_launched"), and subagents
        # run in the background BY DEFAULT. So most rows will land here with tokens unknown.
        # Record None, never 0. A missing cost silently counted as zero is precisely the lie
        # this whole toolchain exists to catch.
        tokens = resp.get("totalTokens")

        row = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "tool": ev.get("tool_name"),
            "session": ev.get("session_id"),
            "agent_id": resp.get("agentId"),
            "status": resp.get("status"),
            "requested_model": requested,
            "requested_tier": _tier_of(requested),
            "resolved_model": resp.get("resolvedModel"),
            "resolved_tier": _tier_of(resp.get("resolvedModel")),
            "models_used": resp.get("modelsUsed"),
            "total_tokens": tokens,
            "tokens_known": tokens is not None,
            "usage": resp.get("usage"),
            "duration_ms": resp.get("totalDurationMs"),
            "tool_uses": resp.get("totalToolUseCount"),
        }
        d = os.path.dirname(LEDGER)
        if d and not os.path.isdir(d):
            os.makedirs(d)
        with io.open(LEDGER, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception as e:
        _warn("ledger write failed (%s) - continuing" % e)
    return 0


# ---------------------------------------------------------------------------- report --------
def report(days, weekly_budget):
    if not os.path.isfile(LEDGER):
        print("\n  no ledger yet at %s" % LEDGER)
        print("  Nothing has been recorded, which is NOT the same as nothing was spent.\n")
        return 3

    cutoff = time.time() - days * 86400
    rows, bad = [], 0
    with io.open(LEDGER, encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.strip()
            if not ln:
                continue
            try:
                r = json.loads(ln)
                t = time.mktime(time.strptime(r["ts"], "%Y-%m-%dT%H:%M:%S"))
                if t >= cutoff:
                    rows.append(r)
            except Exception:
                bad += 1

    by_tier, unknown = {}, 0
    for r in rows:
        tier = r.get("resolved_tier") or r.get("requested_tier") or "(undeclared)"
        slot = by_tier.setdefault(tier, {"runs": 0, "tokens": 0, "unknown": 0})
        slot["runs"] += 1
        if r.get("tokens_known"):
            slot["tokens"] += r.get("total_tokens") or 0
        else:
            slot["unknown"] += 1
            unknown += 1

    total = sum(v["tokens"] for v in by_tier.values())
    over = sum(v["tokens"] for k, v in by_tier.items() if k not in ALLOWED_TIERS)

    print("\n  SUBAGENT SPEND - last %d days" % days)
    print("  %s" % LEDGER)
    print("  " + "-" * 74)
    print("  %-16s %7s %14s %12s" % ("tier", "runs", "tokens", "cost unknown"))
    for tier in sorted(by_tier, key=lambda k: -by_tier[k]["tokens"]):
        v = by_tier[tier]
        mark = " " if tier in ALLOWED_TIERS else "x"
        print("  %s %-14s %7d %14s %12s"
              % (mark, tier, v["runs"], "{:,}".format(v["tokens"]),
                 v["unknown"] or "-"))
    print("  " + "-" * 74)
    print("  %d runs, %s tokens counted." % (len(rows), "{:,}".format(total)))

    if over:
        print("  x  %s tokens ran ABOVE the %s ceiling."
              % ("{:,}".format(over), "/".join(ALLOWED_TIERS)))
    if weekly_budget:
        print("     %.1f%% of the %s weekly budget."
              % (100.0 * total / weekly_budget, "{:,}".format(weekly_budget)))
    else:
        # Say what cannot be computed rather than printing a percentage of an invented total.
        print("     No --weekly-budget given, so the 15% rule CANNOT be evaluated - this is an")
        print("     absolute count, not a share.")

    if unknown:
        print("  ?  %d of %d runs recorded NO token count (background launches report cost"
              % (unknown, len(rows)))
        print("     asynchronously, and the hook fires before it is known). Those are missing")
        print("     from every number above - the real total is HIGHER, not equal.")
    if bad:
        print("  ?  %d unparseable ledger lines skipped." % bad)
    print("")
    return 3 if (unknown or bad) else 0


# -------------------------------------------------------------------------- selftest ---------
def selftest():
    """Prove the guard's decisions without installing it anywhere."""
    cases = [
        ("Agent, no model",       {"tool_name": "Agent", "tool_input": {"prompt": "x"}}, "deny"),
        ("Agent, opus",           {"tool_name": "Agent", "tool_input": {"model": "opus"}}, "deny"),
        ("Agent, claude-opus-5",  {"tool_name": "Agent", "tool_input": {"model": "claude-opus-5"}}, "deny"),
        ("Agent, fable",          {"tool_name": "Agent", "tool_input": {"model": "fable"}}, "deny"),
        ("Agent, sonnet",         {"tool_name": "Agent", "tool_input": {"model": "sonnet"}}, "allow"),
        ("Agent, haiku pinned",   {"tool_name": "Agent", "tool_input": {"model": "claude-haiku-4-5-20251001"}}, "allow"),
        ("Workflow, no model",    {"tool_name": "Workflow", "tool_input": {"script": "x"}}, "deny"),
        ("Bash (not a spawner)",  {"tool_name": "Bash", "tool_input": {"command": "ls"}}, "allow"),
        ("garbage input",         {"nonsense": True}, "allow"),
    ]
    import subprocess
    me = os.path.abspath(__file__)
    ok = True
    print("\n  ns_tokens --guard selftest")
    print("  " + "-" * 62)
    for name, payload, expect in cases:
        p = subprocess.run([sys.executable, me, "--guard"], input=json.dumps(payload),
                           capture_output=True, text=True, encoding="utf-8")
        got = "allow"
        if p.stdout.strip():
            try:
                got = json.loads(p.stdout)["hookSpecificOutput"]["permissionDecision"]
            except Exception:
                got = "MALFORMED"
        good = (got == expect) and p.returncode == 0
        ok = ok and good
        print("  %s  %-24s expect %-5s got %-9s rc=%d"
              % ("+" if good else "x", name, expect, got, p.returncode))
    print("  " + "-" * 62)
    print("  %s\n" % ("all cases pass" if ok else "FAILURES ABOVE - do not install"))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(prog="python -m kibsu tokens", description="Model-tier guard, cost ledger, and spend report.")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--guard", action="store_true", help="PreToolUse: refuse an unpinned subagent")
    g.add_argument("--ledger", action="store_true", help="PostToolUse: record what it cost")
    g.add_argument("--report", action="store_true", help="what have subagents cost lately")
    g.add_argument("--selftest", action="store_true", help="prove the guard without installing")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--weekly-budget", type=int, default=0,
                    help="token budget the 15%% rule is a share OF; without it, no share is printed")
    a = ap.parse_args()

    if a.guard:
        return guard()
    if a.ledger:
        return ledger()
    if a.selftest:
        return selftest()
    return report(a.days, a.weekly_budget)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:                                   # never wedge the session
        _warn("unexpected failure (%s) - allowing the tool call" % e)
        sys.exit(0)
