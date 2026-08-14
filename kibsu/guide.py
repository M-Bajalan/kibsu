#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ns_guide.py  v1.0.0  -  tell the agent what it actually has to REMEMBER.

THE PROBLEM
  Instruction sets only grow. A rule gets written when something goes wrong, and it stays
  written forever - including after the day a mechanism starts enforcing it. Nobody deletes an
  instruction for being redundant, because deleting a rule feels like lowering a standard.

  So an agent arrives holding a list of twenty things to remember, of which two are enforced by
  a hook, one by CI, and seventeen by nothing at all. All twenty are written in the same voice
  at the same volume. Attention is finite, and the seventeen that genuinely depend on memory are
  now diluted by three that do not.

  A repo made that concrete once: its instructions said "before commit -> run the doc check
  and the linter; don't commit red." Soon after, a pre-commit hook enforced exactly that.
  The sentence is now costing context in every session and buying nothing.

WHAT THIS DOES
  Splits the repo's own mandated commands into three honest buckets, derived from what
  ns_discover found actually invokes them:

    ENFORCED   a mechanism blocks you. The agent does not need to remember this, and saying so
               is not lowering the standard - the standard is now higher than a sentence.
    MONITORED  something runs it on a schedule and reports afterwards. Still on the agent
               before a commit, because discovering red on Sunday is not preventing it.
    ON YOU     nothing anywhere invokes it. These are the ones that need the emphasis, and
               today they are buried among the others.

  --check is the drift detector, and the point of the whole tool: it reports instructions that
  tell an agent to remember something a machine already guarantees. That drift only ever grows,
  and nothing else in the toolchain looks for it.

WHAT IT DOES NOT DO
  It does not edit your instruction files. Rewriting CLAUDE.md unattended is a bad trade for a
  tool this young, and the judgement about wording is the author's.

Read-only. Dependency-free. Python 3.8+.

  python -m kibsu guide [repo] [--check] [--json]

EXIT CODES
  0  no drift, or drift found but --check was not passed
  1  drift found AND --check was passed
  3  cannot run
  Exit 1 is gated on --check: without that flag this tool always exits 0, even on a run that
  prints (or --json-reports) drift findings. `kibsu guide .` with no flags in a CI job is
  therefore a green tick that can never go red - gating on this tool requires passing --check.
"""
import argparse
import io
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

VERSION = "1.0.0"
OK, DRIFT, CANNOT_RUN = 0, 1, 3

AGENT_DOCS = ["CLAUDE.md", "AGENTS.md", "GEMINI.md", ".cursorrules", "CONVENTIONS.md"]

# Language that puts the obligation on the reader's memory. Deliberately narrow - the finding is
# "you are told to REMEMBER an enforced thing", not "an enforced thing is mentioned". A doc may
# perfectly well describe what the gate does.
REMEMBER_RE = re.compile(
    r"\b(before\s+commit|don'?t\s+commit|do\s+not\s+commit|remember\s+to|make\s+sure\s+to|"
    r"always\s+run|must\s+run|be\s+sure\s+to|never\s+commit)\b", re.I)


def relpath(p):
    """Strip a leading './' - as a PREFIX, not a character set.

    `"./.agents/skills/x.ps1".lstrip("./")` returns 'agents/skills/x.ps1', because lstrip takes a
    SET of characters and happily eats the dot of '.agents'. The path then resolves nowhere and
    the entry is silently dropped from the report.

    memory/learnings/a-checker-that-guesses-the-base-path-cries-wolf.md rule 3 says exactly this,
    and was written three hours before this file repeated the bug twice. Which is the thesis of
    the whole toolchain, demonstrated on its own author: a written lesson is CLAIMABLE. Nothing
    checked it, so it did not bind."""
    p = p.replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p


def read(p):
    try:
        with io.open(p, encoding="utf-8", errors="replace") as f:
            return f.read().lstrip("﻿")
    except Exception:
        return ""


def enforcement_is_portable(root):
    """Does the enforcement survive a fresh clone, or only exist on this machine?

    This distinction was missed on the first version and produced actively harmful advice: it
    reported five instruction lines as redundant "because a hook enforces them", and recommended
    deleting them. But `core.hooksPath` lives in .git/config, which is NOT tracked - zero files
    under .git/ are in the index. A fresh clone, a second machine, another agent's checkout or a
    CI runner gets NO hook, and those five sentences were the only thing standing there.

    CI config is committed, so it travels. A git hook wired through core.hooksPath does not.
    Never fold the two into one word."""
    ci = []
    for g in (".github/workflows", ".gitlab-ci.yml", "azure-pipelines.yml", "Jenkinsfile",
              ".circleci/config.yml"):
        p = os.path.join(root, g.replace("/", os.sep))
        if os.path.exists(p):
            ci.append(g)
    try:
        p = subprocess.run(["git", "-C", root, "config", "--show-origin", "--get",
                            "core.hooksPath"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        hooks_local = p.returncode == 0 and ".git/config" in p.stdout.replace("\\", "/")
    except Exception:
        hooks_local = False
    return {"ci": ci, "hook_is_machine_local": hooks_local}


def discover(root):
    """Reuse ns_discover rather than re-deriving what runs. One source of that truth."""
    tool = os.path.join(os.path.dirname(os.path.abspath(__file__)), "discover.py")
    if not os.path.isfile(tool):
        return None
    try:
        p = subprocess.run([sys.executable, tool, root, "--json"], capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        return json.loads(p.stdout) if p.stdout.strip() else None
    except Exception:
        return None


def buckets(root, disc):
    """{script: state} for every command the instructions mandate.

    ns_discover already decided which are unenforced, which merely monitored, and which live;
    since issue #32 it says so in a machine-readable `scripts` map on the 'Mandated gates'
    capability, and THAT is what this consumes - one source of truth, no prose coupling. The
    regex parse survives only as a fallback for older discover JSON, because parsing prose is
    exactly how the schedule-only branch's wording (which matched neither pattern) sent every
    merely-MONITORED gate through the else-branch to ENFORCED - "you do not need to remember
    these" - the inversion this module's own docstring forbids."""
    gates = None
    for c in disc.get("capabilities", []):
        if c.get("capability") == "Mandated gates":
            gates = c
            break
    if gates is None:
        return None

    states_map = gates.get("scripts")
    on_you, monitored = set(), set()
    if not isinstance(states_map, dict):
        for m in re.findall(r"([\w./\\-]+\.(?:py|ps1|sh|js|bat|cmd))\s*\(named in", gates.get("evidence", "")):
            on_you.add(relpath(m))
        m = re.search(r"MONITORS but cannot block a commit:\s*([^)]*)", gates.get("detail", ""))
        if m:
            for name in m.group(1).split(","):
                name = name.strip()
                if name:
                    monitored.add(name)

    # Everything the docs mandate that ns_discover did NOT list as unenforced or monitored is,
    # by elimination, enforced. Derived from one source, not asserted twice.
    mandated = {}
    for d in AGENT_DOCS:
        p = os.path.join(root, d)
        if not os.path.isfile(p):
            continue
        for s in re.findall(r"`(?:python3?|py|pwsh|powershell|node|bash|sh)?\s*"
                            r"([\w./\\-]+\.(?:py|ps1|sh|js|bat|cmd))[^`]*`", read(p)):
            s = relpath(s)
            if os.path.exists(os.path.join(root, s.replace("/", os.sep))):
                mandated.setdefault(s, set()).add(d)

    out = {}
    if isinstance(states_map, dict):
        norm = {relpath(k): v for k, v in states_map.items()}
        label = {"unenforced": "ON YOU", "monitored": "MONITORED", "live": "ENFORCED"}
        for s, docs in mandated.items():
            st = norm.get(s) or norm.get(os.path.basename(s))
            # A script discover never classified defaults to the SAFE reading - still on
            # the agent - never to ENFORCED, the direction that deletes real protection.
            out[s] = (label.get(st, "ON YOU"), sorted(docs))
        return out
    for s, docs in mandated.items():
        base = os.path.basename(s)
        if s in on_you:
            state = "ON YOU"
        elif base in monitored or s in monitored:
            state = "MONITORED"
        else:
            state = "ENFORCED"
        out[s] = (state, sorted(docs))
    return out


def drift(root, table, portable):
    """Instructions that put an ENFORCED obligation back on the agent's memory.

    Reports NOTHING when the only enforcement is a machine-local hook. In that case the
    instruction is not redundant - it is the sole protection on every checkout but this one, and
    calling it drift would be advising the user to delete their last line of defence."""
    if portable["hook_is_machine_local"] and not portable["ci"]:
        return []
    hits = []
    for d in AGENT_DOCS:
        p = os.path.join(root, d)
        if not os.path.isfile(p):
            continue
        for n, ln in enumerate(read(p).split("\n"), 1):
            if not REMEMBER_RE.search(ln):
                continue
            for s, (state, _) in table.items():
                if state == "ENFORCED" and os.path.basename(s).split(".")[0] in ln:
                    hits.append((d, n, s, ln.strip()[:110]))
    return hits


def main():
    ap = argparse.ArgumentParser(prog="python -m kibsu guide", description="What must the agent actually remember?")
    ap.add_argument("repo", nargs="?", default=".")
    ap.add_argument("--check", action="store_true", help="exit 1 if instructions have drifted")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    root = os.path.abspath(a.repo)

    disc = discover(root)
    if disc is None:
        print("CANNOT RUN: ns_discover.py did not produce readable output.")
        return CANNOT_RUN
    table = buckets(root, disc)
    if not table:
        print("CANNOT RUN: no agent-instruction file mandates a runnable command here.")
        return CANNOT_RUN

    portable = enforcement_is_portable(root)
    d = drift(root, table, portable)

    if a.json:
        print(json.dumps({"version": VERSION, "repo": root,
                          "commands": {k: v[0] for k, v in table.items()},
                          "drift": [{"doc": x[0], "line": x[1], "command": x[2], "text": x[3]}
                                    for x in d]}, indent=2))
        return DRIFT if (a.check and d) else OK

    print("\n  WHAT THIS AGENT ACTUALLY HAS TO REMEMBER")
    print("  %s" % root)
    print("  " + "-" * 74)
    for state in ("ON YOU", "MONITORED", "ENFORCED"):
        rows = sorted((s for s, (st, _) in table.items() if st == state))
        if not rows:
            continue
        head = {"ON YOU": "ON YOU - nothing anywhere invokes these. Memory is the only mechanism.",
                "MONITORED": "MONITORED - run on a schedule, reported AFTER the fact. Still yours "
                             "before a commit.",
                "ENFORCED": ("ENFORCED HERE ONLY - a git hook blocks you on THIS checkout. "
                             "core.hooksPath\n           lives in .git/config, which is not "
                             "tracked, so a fresh clone has NOTHING."
                             if portable["hook_is_machine_local"] and not portable["ci"] else
                             "ENFORCED - a mechanism blocks you. You do not need to remember "
                             "these.")
                }[state]
        print("  %s" % head)
        for s in rows:
            print("      %s" % s)
        print("")
    print("  " + "-" * 74)
    if d:
        print("  x  %d instruction line(s) still ask an agent to REMEMBER something a machine" % len(d))
        print("     now guarantees. Every session pays context for these and gains nothing:")
        for doc, n, s, text in d:
            print("       %s:%d  (%s)" % (doc, n, os.path.basename(s)))
            print("         %s" % text)
        print("     Deleting a rule a mechanism enforces is not lowering the standard -")
        print("     the standard is now higher than a sentence could make it.")
    elif portable["hook_is_machine_local"] and not portable["ci"]:
        print("  !  Drift NOT reported, because the only enforcement here is a git hook wired")
        print("     through core.hooksPath in .git/config - which is NOT tracked. It protects")
        print("     this checkout and nothing else: not a fresh clone, not a second machine,")
        print("     not another agent's copy, not CI. The instructions that name these scripts")
        print("     are the ONLY protection everywhere else, so do not delete them.")
        print("     To make enforcement travel, add CI - or have the instructions tell a fresh")
        print("     clone to run:  ns_gate.py --install --apply")
    else:
        print("  +  no instruction asks an agent to remember something already enforced.")
    print("")
    return DRIFT if (a.check and d) else OK


if __name__ == "__main__":
    sys.exit(main())
