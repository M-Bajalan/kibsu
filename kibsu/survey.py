#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Clone public agent-instruction repos, audit each, print the distribution.

FULL clones (not shallow) so the phantom-artifact check has real history to search.
Read-only: reads markdown, executes nothing from the cloned repos.
Failures are reported, never silently dropped.
"""
import json, os, subprocess, sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
# NEVER clone into the repo this file lives in. When a tool like this one moved into a larger
# repo, its (relative) clone dir moved with it and dropped ten full repo clones into a tracked
# directory - untracked, not gitignored, and a nightly job running `git add -A` would have swept
# them in. Default outside the tree.
REPOS_DIR = os.environ.get("SKILL_AUDIT_CLONES") or os.path.join(
    os.path.expanduser("~"), ".skill-audit-clones")
AUDIT = os.path.join(HERE, "audit.py")

EVIDENCE = os.environ.get("SKILL_AUDIT_EVIDENCE")

REPOS = [
    "anthropics/skills",
    "obra/superpowers",
    "wshobson/agents",
    "VoltAgent/awesome-claude-code-subagents",
    "0xfurai/claude-code-subagents",
    "contains-studio/agents",
    "iannuttall/claude-agents",
    "vijaythecoder/awesome-claude-agents",
    "davila7/claude-code-templates",
    "sanjeed5/awesome-cursor-rules-mdc",
]


def clone(slug):
    dest = os.path.join(REPOS_DIR, slug.replace("/", "__"))
    if os.path.isdir(os.path.join(dest, ".git")):
        return dest, None
    os.makedirs(REPOS_DIR, exist_ok=True)
    p = subprocess.run(["git", "-c", "core.longpaths=true", "clone", "--quiet",
                        "https://github.com/%s.git" % slug, dest], capture_output=True, text=True)
    if p.returncode != 0:
        tail = (p.stderr or "clone failed").strip().splitlines()
        return None, (tail[0] if tail else "clone failed")[:88]
    return dest, None


def head_sha(path):
    """The commit the measurement was taken at. A number without a SHA is not reproducible -
    the repo moves and the reader cannot get back to what was measured."""
    p = subprocess.run(["git", "rev-parse", "HEAD"], cwd=path, capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 else None


def audit(path, artifacts=True):
    cmd = [sys.executable, AUDIT, path, "--json"] + (["--artifacts"] if artifacts else [])
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if p.returncode != 0:
        return None, (p.stderr or "audit failed").strip()[:88]
    try:
        return json.loads(p.stdout), None
    except Exception as e:
        return None, str(e)[:88]


# A procedure-only percentage computed from a handful of instructions is noise wearing a number.
MIN_UNITS, MIN_INSTR = 5, 50


def row_from(slug, d):
    A, P = d["all"], d["procedure_only"]
    arts = d.get("artifacts", [])
    usable_hist = d.get("has_git") and not d.get("history_shallow")
    inscope = {x["artifact"] for x in arts if x["in_scope"]}
    phantom = {x["artifact"] for x in arts if x["in_scope"] and x["phantom"]}
    return dict(slug=slug, units=A["units"], instr=A["instructions"], pct_all=A["pct"],
                p_units=P["units"], p_instr=P["instructions"], pct_proc=P["pct"],
                zero=A["zero"], mand=len(inscope), out=len({x["artifact"] for x in arts}) - len(inscope),
                phantom=(len(phantom) if usable_hist else None),
                enough=(P["units"] >= MIN_UNITS and P["instructions"] >= MIN_INSTR),
                genres={g: v["units"] for g, v in d.get("by_genre", {}).items()})


def main():
    rows, failures = [], []
    for slug in REPOS:
        sys.stderr.write("  ... %s\n" % slug)
        dest, err = clone(slug)
        if err:
            failures.append((slug, "clone: " + err)); continue
        d, err = audit(dest)
        if err:
            failures.append((slug, "audit: " + err)); continue
        if d["all"]["instructions"] < 20:
            failures.append((slug, "only %d instructions (mode=%s) - unmeasurable"
                             % (d["all"]["instructions"], d["mode"]))); continue
        r = row_from(slug, d)
        r["sha"] = head_sha(dest)
        rows.append(r)
        if EVIDENCE:
            os.makedirs(EVIDENCE, exist_ok=True)
            fn = os.path.join(EVIDENCE, slug.replace("/", "__") + ".json")
            # Strip the local clone path. Published evidence must not reveal the machine it
            # was measured on - "root" carried a full absolute path including the username.
            clean = dict(d)
            clean["root"] = "<clone of %s at %s>" % (slug, (r["sha"] or "?")[:12])
            with open(fn, "w", encoding="utf-8") as fh:
                json.dump({"repo": slug, "sha": r["sha"], "measured_by": "skill_audit",
                           "result": clean}, fh, indent=2)

    # Optional local comparison set. Nothing about this file should assume whose machine it
    # is running on - it is the file a reader would open to check the claim that this tool is
    # generic, so a hardcoded path here would refute the claim on sight.
    local = os.environ.get("SKILL_AUDIT_LOCAL") or (sys.argv[1] if len(sys.argv) > 1 else None)
    label = os.environ.get("SKILL_AUDIT_LABEL", "** local (not published) **")
    if local:
        d, err = audit(os.path.abspath(local))
        if err:
            failures.append((local, "audit: " + err))
        else:
            rows.append(row_from(label, d))

    ranked = sorted([r for r in rows if r["enough"]], key=lambda r: -r["pct_proc"])
    thin = [r for r in rows if not r["enough"]]
    W = 112
    print("\n" + "=" * W)
    print("CHECKABLE-INSTRUCTION SURVEY - public agent instruction sets   (skill-audit v0.2.1)")
    print("min sample to rank: >=%d procedure units AND >=%d procedure instructions" % (MIN_UNITS, MIN_INSTR))
    print("=" * W)
    print("%-40s %6s %7s %7s | %6s %7s %7s | %6s %7s"
          % ("repo", "units", "instr", "all%", "proc-u", "p-instr", "PROC%", "in-scp", "phantom")
          + " | commit")
    print("-" * W)
    for r in ranked:
        ph = "n/a" if r["phantom"] is None else "%d (%.0f%%)" % (
            r["phantom"], 100.0 * r["phantom"] / max(1, r["mand"]))
        print("%-40s %6d %7s %6.1f%% | %6d %7s %6.1f%% | %6d %8s | %s"
              % (r["slug"][:40], r["units"], format(r["instr"], ","), r["pct_all"],
                 r["p_units"], format(r["p_instr"], ","), r["pct_proc"], r["mand"], ph,
                 (r.get("sha") or "?")[:10]))
    print("-" * W)

    pub = [r for r in ranked if not r["slug"].startswith("**")]
    if pub:
        for key, lbl in (("pct_all", "all units"), ("pct_proc", "procedure units only")):
            ps = sorted(r[key] for r in pub)
            n = len(ps)
            med = ps[n // 2] if n % 2 else (ps[n // 2 - 1] + ps[n // 2]) / 2
            print("ranked public n=%d  %-22s median %5.1f%%   min %4.1f%%   max %5.1f%%"
                  % (n, lbl, med, ps[0], ps[-1]))
        tm = sum(r["mand"] for r in pub)
        tp = sum(r["phantom"] for r in pub if r["phantom"] is not None)
        to = sum(r["out"] for r in pub)
        print("in-scope mandated artifacts: %d distinct, %d PHANTOM (%.0f%%)   [%d excluded as user-project scope]"
              % (tm, tp, (100.0 * tp / tm) if tm else 0, to))
        print("genre mix:", {g: sum(r["genres"].get(g, 0) for r in pub)
                             for g in ("procedure", "persona", "reference", "mixed")})
    if thin:
        print("\nBELOW SAMPLE FLOOR - measured, not ranked (a %% from <%d instructions is noise):" % MIN_INSTR)
        for r in thin:
            print("  %-40s %d procedure units / %d instructions  (would read %.1f%%)"
                  % (r["slug"][:40], r["p_units"], r["p_instr"], r["pct_proc"]))
    if failures:
        print("\nEXCLUDED (%d) - reported, not hidden:" % len(failures))
        for s, why in failures:
            print("  %-40s %s" % (s, why))
    print()


if __name__ == "__main__":
    main()
