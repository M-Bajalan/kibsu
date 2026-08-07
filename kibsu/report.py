#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ns_report.py  v1.0.0  -  the read-only readiness report. The first thing a stranger runs.

WHAT THIS IS FOR
  Not a documentation hygiene score. A statement of what an agent CANNOT DO in this repo yet.
  Same measurements underneath - the difference is that a percentage tells you about your
  files, and this tells you about your agents.

WHY READ-ONLY IS THE WHOLE POINT
  "Let me restructure your docs and install a commit hook" is a very large ask from software
  a stranger has never heard of. This asks for nothing. It writes nothing, changes no config,
  and touches no git state. It runs, it tells you something uncomfortable and specific about
  your own repo, and it stops. Whether anything is installed afterwards is a separate decision
  taken later, by you, with evidence in hand.

  Verify that claim rather than trusting it: run it, then `git status`. Nothing.

WHAT IT MEASURES
  1. NAVIGATION   can an agent find your docs without grepping the whole tree?
  2. CONVENTION   is there a consistent shape to enforce, or does every doc differ?
  3. VERIFIABILITY  how much of what you tell agents could anyone check afterwards?
  4. CONTINUITY   do the artifacts your instructions promise actually get produced?
  5. HISTORY      how often have your own commits broken your own written rule?

Dependency-free. Python 3.8+. Reads only.

  python -m kibsu report [repo] [--skills DIR] [--json] [--peer-median 11.1]

EXIT CODES
  0  the report is complete - every check ran.
  3  the report ran but is INCOMPLETE - at least one check could not run, so the output is
     not trustworthy. Matches ns_check.py's CANNOT_RUN, so one number means one thing here.
  Findings NEVER make this non-zero. "2 of 5 ready" is a measurement against a peer median,
  and the threshold for acting on it belongs to whoever runs this, not to us. A check that
  could not run is different in kind: that is the tool declaring its own output unreliable,
  which IS ours to signal.
"""
import argparse
import io
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from . import config

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

VERSION = "1.1.0"
PEER_MEDIAN = 9.4           # procedure-only checkability, 8 public collections, SHA-pinned,
                            # scorer 0.6.0 (was 11.1 under 0.5.0 - CORRECTIONS.md, 2026-08-07)
BAD, WARN, OK, SKIP = "x", "!", "+", "?"
CANNOT_RUN = 3              # exit code, same value and same meaning as in ns_check.py
# SKIP is not a pass. A check that could not run must say so on its own line - printing one
# line fewer makes "2 of 4" and "2 of 5" indistinguishable, and the missing check is always
# the uncomfortable one. This report fails loudly or it is not worth running.
#
# WARN vs SKIP is a real distinction, not a shade of the same thing:
#   SKIP (?) the check could NOT run. The output is incomplete and says so.
#   WARN (!) the check RAN and found nothing worth judging (no markdown at all; too few
#            instructions to make a percentage mean anything).
# Two sites used to mark a could-not-run condition as WARN, which kept it out of the skipped
# count - so a repo with no agent-instruction directory truthfully could not run two checks
# and reported "1 could NOT be checked". The honesty mechanism was undercounting itself.


def run(args, cwd=None, any_rc=False):
    """any_rc=True keeps stdout regardless of exit code. ns_check exits 1 when it FINDS
    violations - that is success for our purposes, and discarding it silently dropped the
    entire history finding from this report without any error appearing."""
    try:
        p = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        return p.stdout if (any_rc or p.returncode == 0) else None
    except Exception:
        return None


def tool(name):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), name)


def audit_json(path, extra=None):
    out = run([sys.executable, tool("audit.py"), path, "--json"] + (extra or []))
    try:
        return json.loads(out) if out else None
    except Exception:
        return None


def index_json(root):
    from . import index as ns_index
    try:
        return ns_index.build(root)
    except Exception:
        return None


def find_skills_dir(root, cfg=None):
    """Where does this repo keep agent instructions? Do not assume our layout.

    cfg["skills_dir"] is checked FIRST, but only when it has been explicitly set away from
    kibsu's own built-in default - an unset key must not silently reorder auto-detection and
    change what a repo that has never heard of kibsu gets by default."""
    if cfg and cfg.get("skills_dir") and cfg["skills_dir"] != config.DEFAULTS["skills_dir"]:
        p = os.path.join(root, cfg["skills_dir"].replace("/", os.sep))
        if os.path.isdir(p):
            return p
    for c in (".agents/skills", ".claude/skills", ".cursor/skills", "skills",
              "agents", ".github/skills"):
        p = os.path.join(root, c.replace("/", os.sep))
        if os.path.isdir(p):
            return p
    return None


def q(p):
    """Quote a path only when it needs it. These lines are meant to be pasted, and an
    unquoted C:\\My Repos\\x silently becomes two arguments."""
    return '"%s"' % p if " " in p else p


def line(mark, title, detail, see=None):
    """`see` is attached ONLY to a check that could not run, and it is always read-only.

    A finding that RAN needs no instruction - "47 of your last 200 commits changed a doc
    without updating the index" is already actionable in the reader's own repo with the
    reader's own tools, and printing a command there turns a diagnosis into a funnel. A check
    that could NOT run is different in kind: it is an accusation the reader cannot inspect,
    and refusing to say how to inspect it is just withholding. ns_check.py already reached
    this conclusion (see its 'Build one first:' line); this file had not.

    No mutating command is ever printed here. ns_index's -o overwrites an existing untracked
    index with no backup and no prompt, so it is not offered - only --stdout is."""
    print("  %s  %-26s %s" % (mark, title, detail))
    if see:
        print("  %s  %-26s reads only, writes nothing:  %s" % (" ", "", see))


def main():
    ap = argparse.ArgumentParser(prog="python -m kibsu report", description="What can an agent not do in this repo yet?")
    ap.add_argument("repo", nargs="?", default=".")
    ap.add_argument("--skills", default=None, help="agent-instruction dir (auto-detected)")
    ap.add_argument("--peer-median", type=float, default=PEER_MEDIAN)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    root = os.path.abspath(a.repo)
    cfg = config.load(root)

    idx = index_json(root)
    skills = a.skills or find_skills_dir(root, cfg)
    sk = audit_json(skills, ["--artifacts"]) if skills else None

    findings, score = [], 0

    # 1 NAVIGATION -----------------------------------------------------------------------
    docs = idx["doc_count"] if idx else 0
    has_index = any(os.path.isfile(os.path.join(root, f)) for f in
                    (cfg["index_path"], os.path.join(cfg["docs_root"], "index.json"),
                     "docs/index.json"))
    if docs and not has_index:
        findings.append((BAD, "Find your docs",
                         "%d markdown files, no index. An agent must grep the tree." % docs))
    elif docs:
        findings.append((OK, "Find your docs", "%d docs, index present." % docs))
        score += 1
    else:
        findings.append((WARN, "Find your docs", "no markdown found - nothing to navigate."))

    # 2 CONVENTION -----------------------------------------------------------------------
    if idx:
        t = idx["taxonomy"]
        if t["enforceable"]:
            keys = ", ".join(k["key"] for k in t["required"])
            findings.append((OK, "Know your conventions",
                             "consistent frontmatter (%s) - enforceable." % keys))
            score += 1
        else:
            findings.append((BAD, "Know your conventions",
                             "%d of %d docs carry frontmatter, no key is consistent enough "
                             "to enforce." % (t["docs_with_frontmatter"], t["docs_total"])))

    else:
        findings.append((SKIP, "Know your conventions",
                         "COULD NOT CHECK - no readable markdown index could be built here.",
                         "%s %s %s --stdout" % (q(sys.executable),
                                                q(tool("index.py")), q(root))))

    # 3 VERIFIABILITY --------------------------------------------------------------------
    if sk:
        p = sk["procedure_only"]
        if p["instructions"] >= 20:
            pct = p["pct"]
            cmp_ = "above" if pct > a.peer_median else "below"
            mark = OK if pct > a.peer_median else BAD
            findings.append((mark, "Prove they followed",
                             "%.1f%% of your procedural instructions are verifiable "
                             "(%s the %.1f%% public median)." % (pct, cmp_, a.peer_median)))
            if pct > a.peer_median:
                score += 1
        else:
            findings.append((WARN, "Prove they followed",
                             "only %d procedural instructions found - too few to judge."
                             % p["instructions"]))
    else:
        # SKIP, not WARN. Identical root cause to the SKIP under "Resume after a break" below,
        # and marking the same condition two different ways is how the tail lost a count.
        # The remediation is printed once, there - saying it twice is noise.
        findings.append((SKIP, "Prove they followed",
                         "COULD NOT CHECK - no agent-instruction directory found. Nothing here "
                         "tells agents how to work, so there is nothing to measure."))

    # 4 CONTINUITY -----------------------------------------------------------------------
    if sk:
        arts = [x for x in sk.get("artifacts", []) if x.get("in_scope")]
        # unverifiable_pattern mandates ({name}.md, *.md, ...) prove nothing either way - no
        # hit or miss on a pattern like that was ever actually checked (see audit.py's own
        # --definitions). `phantom` is structurally always False on one of these, so treating
        # `ph` alone as the gate would let a skill whose ONLY mandated artifact is
        # unverifiable-pattern read as a clean OK - a braced path flipping unproven evidence
        # into a passing finding. Split them out so that case reads WARN, never OK.
        unver = [x for x in arts if x.get("unverifiable_pattern")]
        ver = [x for x in arts if not x.get("unverifiable_pattern")]
        ph = [x for x in ver if x.get("phantom")]
        if not arts:
            findings.append((BAD, "Resume after a break",
                             "your instructions promise no artifacts at all - nothing survives "
                             "the session, and nothing can be checked."))
        elif sk.get("history_shallow"):
            findings.append((WARN, "Resume after a break",
                             "shallow clone - cannot tell whether promised artifacts exist."))
        elif ph:
            findings.append((BAD, "Resume after a break",
                             "%d of %d artifacts your instructions promise have never existed "
                             "in any commit." % (len(ph), len(ver))))
        elif unver:
            findings.append((WARN, "Resume after a break",
                             "%d of %d promised artifacts use pattern-only names (e.g. "
                             "{name}.md) that cannot be verified either way%s."
                             % (len(unver), len(arts),
                                "" if not ver else " - the rest exist")))
        else:
            findings.append((OK, "Resume after a break",
                             "all %d promised artifacts exist." % len(arts)))
            score += 1

    else:
        findings.append((SKIP, "Resume after a break",
                         "COULD NOT CHECK - no agent-instruction directory found, so there is "
                         "nothing promising artifacts to verify.",
                         "%s %s %s --skills <your agent-instruction dir>"
                         % (q(sys.executable), q(os.path.abspath(__file__)), q(root))))

    # 5 HISTORY --------------------------------------------------------------------------
    cat = None
    catalog_candidate = os.path.join(cfg["docs_root"], "index.json")
    for c in (catalog_candidate, cfg["index_path"], "docs/index.json"):
        if os.path.isfile(os.path.join(root, c.replace("/", os.sep))):
            cat = c
            break
    if cat:
        # ns_check needs an index in ITS format; the repo's own catalog is a different
        # shape, and passing it made ns_check exit 3 (cannot run) so the backtest never ran
        # and this whole finding vanished without an error. Build ours into a SYSTEM temp
        # file - never the user's repo, which is what "writes nothing" has to keep meaning.
        import tempfile
        out = None
        if idx:
            fd, tmp = tempfile.mkstemp(suffix=".json", prefix="nsreport_")
            os.close(fd)
            try:
                from . import index as _ni
                with io.open(tmp, "w", encoding="utf-8", newline="") as fh:
                    fh.write(_ni.dumps(idx))
                out = run([sys.executable, tool("check.py"), root, "--all", "--quiet",
                           "--index", tmp, "--backtest", "200", "--backtest-index", cat,
                           "--backtest-mode", "existence"], root, any_rc=True)
            finally:
                try:
                    os.remove(tmp)
                except OSError:
                    pass
        n = None
        for ln in (out or "").split("\n"):
            if "would have exited 1" in ln:
                try:
                    n = int(ln.strip().split()[1])
                except Exception:
                    pass
        if n is not None:
            mark = OK if n == 0 else BAD
            findings.append((mark, "Follow your own rules",
                             "%d of your last 200 commits changed a doc without updating "
                             "the index they claim to keep." % n))
            if n == 0:
                score += 1
        else:
            # Split the "or". The tool took exactly ONE of these branches and used to throw
            # away which - npm doctor's failure mode, where an unreachable registry and a
            # misconfigured one both render as "Not ok" and the reader cannot tell them apart.
            if not idx:
                findings.append((SKIP, "Follow your own rules",
                                 "COULD NOT CHECK - the index could not be built here, so the "
                                 "history replay never ran.",
                                 "%s %s %s --stdout" % (q(sys.executable),
                                                        q(tool("index.py")), q(root))))
            else:
                findings.append((SKIP, "Follow your own rules",
                                 "COULD NOT CHECK - the history replay returned no verdict "
                                 "(no git history here, or a shallow clone)."))
    else:
        # SKIP, not WARN - this check genuinely could not run. Name what was looked for, so the
        # reader can tell "you have no index" from "your index is somewhere I do not know about".
        findings.append((SKIP, "Follow your own rules",
                         "COULD NOT CHECK - no index file to check history against (looked for "
                         "%s, %s, docs/index.json)." % (catalog_candidate, cfg["index_path"])))

    # Computed BEFORE the --json branch. It used to be counted only on the human path, which is
    # why the machine-readable output had no way to say "this report is incomplete" at all.
    skipped = len([f for f in findings if f[0] == SKIP])

    if a.json:
        print(json.dumps({"version": VERSION, "repo": root, "score": score,
                          "of": len(findings), "skipped": skipped,
                          "complete": skipped == 0,
                          "findings": [{"mark": f[0], "title": f[1], "detail": f[2]}
                                       for f in findings]}, indent=2))
        return CANNOT_RUN if skipped else 0

    print("\n  WHAT YOUR AGENTS CANNOT DO HERE YET")
    print("  %s" % root)
    print("  " + "-" * 74)
    for f in findings:
        line(f[0], f[1], f[2], f[3] if len(f) > 3 else None)
    print("  " + "-" * 74)
    tail = "" if not skipped else "  %d could NOT be checked - that is not a pass." % skipped
    print("  %d of %d ready.%s" % (score, len(findings), tail))
    # The no-write assurance stays the LAST thing on screen. Nothing is appended after it, so it
    # remains a guarantee rather than a softener for a request that follows.
    print("  Nothing was written to this repo - run `git status` to confirm.\n")
    return CANNOT_RUN if skipped else 0


if __name__ == "__main__":
    sys.exit(main())
