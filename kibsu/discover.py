#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ns_discover.py  v1.0.0  -  what is configured here, and what actually RUNS?

WHAT THIS IS FOR
  An agent arriving in an unfamiliar repository cannot tell infrastructure that EXISTS from
  infrastructure that RUNS. Those look identical from the inside, and the gap between them is
  where every "we have a process for that" story quietly dies.

THE THREE STATES, AND WHY THE MIDDLE ONE IS THE POINT
  ABSENT   the capability is not here. Honest, and easy to act on.
  LIVE     it is here AND something automatic invokes it.
  INERT    it is here and NOTHING invokes it. Declared but dead.

  Only INERT is dangerous, because it reads as coverage. A repo with a lint script nobody runs
  looks better than a repo with no lint script, and behaves worse - the second one knows.

  Real examples this tool was written from, all in one codebase:
    - a settings file with a "hooks" key containing {} - the surface existed, nothing was wired
    - an installer whose output directory appeared in 0 of 363 commits
    - 29 tracked test files and no runner of any kind
    - two gates named in the repo's own agent instructions ("before commit - do not commit red")
      that no CI job, git hook or scheduled task invokes anywhere

THE FLAGSHIP CHECK
  UNENFORCED GATE: a command the repo's own agent instructions tell you to run before committing,
  which appears in no CI workflow and no git hook. That is a rule enforced by whoever remembers -
  which, measured over enough commits, is nobody.

Read-only. Dependency-free. Python 3.8+.

  python -m kibsu discover [repo] [--json]

EXIT CODES  (same meanings as ns_check.py, ns_report.py, ns_learn.py)
  0  nothing inert        1  something is declared but dead        3  cannot run
"""
import argparse
import io
import json
import os
import re
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

VERSION = "1.1.0"

# Issue #39: kibsu scans arbitrary third-party repositories, and nothing stops one from
# git-tracking a multi-gigabyte markdown file. A whole-file .read() of that is an unbounded
# allocation the kernel OOM-killer ends with a SIGKILL no `except` clause sees. 5 MB is
# generous for instruction markdown; over-ceiling files are SKIPPED WITH A PRINTED REASON
# on stderr (stdout stays clean for --json), never silently.
MAX_READ_BYTES = 5 * 1024 * 1024
OK, INERT_FOUND, CANNOT_RUN = 0, 1, 3
ABSENT, INERT, LIVE, UNKNOWN = "absent", "INERT", "live", "unknown"

CI_GLOBS = [".github/workflows", ".gitlab-ci.yml", "azure-pipelines.yml",
            "Jenkinsfile", ".circleci/config.yml", ".travis.yml", "bitbucket-pipelines.yml"]
AGENT_DOCS = ["CLAUDE.md", "AGENTS.md", "GEMINI.md", ".cursorrules", "CONVENTIONS.md"]

# ---- K-1 / K-2 (issues #68 / #69) ---------------------------------------------------------
# K-1: gate-removing flags an instruction can hand to an agent. These exist so a HUMAN can
# push a known-good run through; in an agent's hands they delete exactly the gates that would
# catch a wrong invocation. Bare "-y" is deliberately absent: it collides with ordinary prose,
# and a check that flags a stranger's innocent text is a check that gets switched off - the
# same cry-wolf rule the gate classifier's name-boundary fix follows.
DANGEROUS_FLAG_RE = re.compile(r"--(?:auto-approve|skip-[\w-]+|force|yes|no-verify)\b")
# What counts as the flag being GATED, anywhere within ADJACENCY lines of the mention: an
# approval/confirmation rule, or a prohibition - "never run --force" is the opposite of a
# grant and must not be flagged. Both vocabularies disclosed in the capability detail.
APPROVAL_RE = re.compile(
    r"(?:approv|confirm|authoris|authoriz|permission|sign-?off|marker"
    r"|ask\s+(?:first|before|for|the\s+\w+|your\s+\w+)"
    r"|do\s+not\b|don'?t\b|never\b|forbidden|prohibit|refuse)", re.I)
ADJACENCY = 2  # lines before/after the mention searched for APPROVAL_RE

# K-2: a data-scope default that is a hardcoded date literal - true the day it was written,
# stale ever after, and the day an argument is omitted it silently scopes a destructive
# operation to a months-old window. Two signatures, both cheap and low-collision: a
# module-level assignment of a date/month string, and an argparse default= of one.
# Environment-name defaults ("prod") are out of scope v1: that string space collides with too
# much innocent code. Disclosed here, not silently skipped.
ASSIGN_DATE_RE = re.compile(r"^\s*[A-Za-z_]\w*\s*=\s*[\"']\d{4}-\d{2}(?:-\d{2})?[\"']\s*(?:#.*)?$")
DEFAULT_DATE_RE = re.compile(r"\bdefault\s*=\s*[\"']\d{4}-\d{2}(?:-\d{2})?[\"']")

# A command the instructions tell you to run. Narrow on purpose: a script path with an extension,
# optionally preceded by its interpreter. Prose like "run the tests" is not detectable and
# pretending otherwise would manufacture findings.
GATE_RE = re.compile(r"`(?:python3?|py|pwsh|powershell|node|bash|sh)?\s*"
                     r"([\w./\\-]+\.(?:py|ps1|sh|js|bat|cmd))[^`]*`")


def read(p):
    try:
        if os.path.getsize(p) > MAX_READ_BYTES:
            sys.stderr.write("kibsu discover: skipping %s (over the %d byte ceiling)\n"
                             % (p, MAX_READ_BYTES))
            return ""
        with io.open(p, encoding="utf-8", errors="replace") as f:
            return f.read().lstrip("﻿")
    except Exception:
        return ""


def walk_files(root, sub):
    d = os.path.join(root, sub)
    out = []
    if os.path.isdir(d):
        for base, _, fs in os.walk(d):
            out += [os.path.join(base, f) for f in fs]
    elif os.path.isfile(d):
        out.append(d)
    return out


def git(root, *args):
    try:
        p = subprocess.run(["git", "-C", root] + list(args), capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        return p.stdout.strip() if p.returncode == 0 else None
    except Exception:
        return None


NAME_BOUNDARY = (r"(?<![\w.\-])%s(?![\w\-])")


def names_script(text, name):
    """Does this runner/scheduler text actually invoke THIS script?

    It used to be a bare `name in text`, and substring containment is far too loose for a
    filename: "lint.py" is inside "pylint.py", "check.py" is inside "spellcheck.py", and a
    commented-out "# see also other_check.py" matched too. Any of those marked a script LIVE,
    so `discover` reported a gate as enforced when nothing ran it and `guide` passed that on
    as ENFORCED - the tool making exactly the kind of unbacked claim it exists to find.

    The name must appear as a whole path component. A path separator or quote or space before
    it is fine and expected (tools/lint.py, "lint.py"); a word character, dot or hyphen is not,
    because that is a DIFFERENT filename. Trailing word characters are rejected the same way,
    so "lint.pyc" no longer answers for "lint.py".
    """
    if not name:
        return False
    return re.search(NAME_BOUNDARY % re.escape(name), text) is not None


def capability(name, state, detail, evidence="", scripts=None):
    """`scripts`, when given, is {script: "live"|"monitored"|"unenforced"} - the
    machine-readable form of what detail/evidence say in prose. guide.py consumes THIS
    (issue #32): its buckets() used to regex the prose, and the schedule-only branch's
    wording matched none of its patterns, so merely-MONITORED gates fell through to
    ENFORCED - "you do not need to remember these" - the harmful inversion."""
    cap = {"capability": name, "state": state, "detail": detail, "evidence": evidence}
    if scripts is not None:
        cap["scripts"] = scripts
    return cap


def os_scheduler_text():
    """Every command the OS scheduler runs, as searchable text. Returns None where this cannot
    be checked, which is NOT the same as 'nothing is scheduled'.

    This function exists because leaving it out produced a false headline. The first version
    searched CI, git hooks and agent hooks only, and reported "10 of 10 mandated gates invoked by
    nothing" - while a scheduled task named Weekly_Lint_Job was running one of them every week.
    Literally true as worded, materially wrong, which is the worst kind of finding.

    Two traps here, both load-bearing:
      1. A scheduled task is a FOURTH runner, and on a Windows workstation it is often the ONLY
         one. Omitting it does not make the tool conservative, it makes it wrong.
      2. Task actions routinely hide the real command inside -EncodedCommand base64. A plain text
         scan sees none of those script names and cheerfully reports them as unenforced."""
    if not sys.platform.startswith("win"):
        return None
    try:
        p = subprocess.run(["schtasks", "/query", "/fo", "CSV", "/v"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if p.returncode != 0:
            return None
        text = p.stdout
    except Exception:
        return None
    import base64
    for b64 in re.findall(r"-Encoded[Cc]ommand\s+([A-Za-z0-9+/=]{16,})", text):
        try:
            text += "\n" + base64.b64decode(b64).decode("utf-16-le", "replace")
        except Exception:
            pass
    return text


def main():
    ap = argparse.ArgumentParser(prog="python -m kibsu discover", description="What is configured here, and what actually runs?")
    ap.add_argument("repo", nargs="?", default=".")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    root = os.path.abspath(a.repo)
    if not os.path.isdir(root):
        print("CANNOT RUN: %s is not a directory" % root)
        return CANNOT_RUN

    caps = []

    # ---- CI ------------------------------------------------------------------------------
    ci_files = []
    for g in CI_GLOBS:
        ci_files += walk_files(root, g)
    ci_text = "\n".join(read(f) for f in ci_files)
    if not ci_files:
        caps.append(capability("Continuous integration", ABSENT,
                               "no CI configuration found. Nothing runs on push."))
    else:
        caps.append(capability("Continuous integration", LIVE,
                               "%d CI file(s)." % len(ci_files),
                               ", ".join(os.path.relpath(f, root) for f in ci_files[:3])))

    # ---- git hooks -----------------------------------------------------------------------
    hp = git(root, "config", "--get", "core.hooksPath")
    hook_dir = os.path.join(root, hp) if hp else os.path.join(root, ".git", "hooks")
    live_hooks = []
    if os.path.isdir(hook_dir):
        live_hooks = [f for f in os.listdir(hook_dir) if not f.endswith(".sample")
                      and os.path.isfile(os.path.join(hook_dir, f))]
    hook_text = "\n".join(read(os.path.join(hook_dir, f)) for f in live_hooks)
    # Follow ONE level of indirection. A hook that delegates - "exec python .../ns_gate.py
    # --check" - contains none of the script names it ultimately runs, so a literal scan of the
    # hook body reports every one of them as unenforced. That produced a stale INERT verdict on
    # this very repo within a minute of a working gate being installed. One level only: enough
    # for the runner-script pattern, no cycle risk.
    for m in re.findall(r"[\w$./\\{}-]+\.(?:py|sh|ps1|js)", hook_text):
        # A `$`-containing path is a computed one - `$ROOT/.kibsu/bin/check.py`, kibsu's OWN
        # installed-hook idiom. Probe the variable-stripped, root-relative remainder FIRST
        # (issue #35: collapsing straight to the bare basename only ever found wrappers
        # sitting at repo root, so the tool's own layout read INERT), then the basename.
        # A second fallback probe here used to try a hardcoded, origin-specific subdirectory.
        # Removed: an origin's private layout belongs in config, never baked into published code.
        if "$" in m:
            parts = [p for p in m.replace("\\", "/").split("/") if p]
            keep = next((i for i, seg in enumerate(parts) if "$" not in seg), len(parts) - 1)
            probes = ("/".join(parts[keep:]), parts[-1])
        else:
            probes = (m.replace("\\", "/"),)
        for probe in probes:
            fp = os.path.join(root, probe.replace("/", os.sep))
            if os.path.isfile(fp):
                hook_text += "\n" + read(fp)
                break
    if live_hooks:
        caps.append(capability("Git hooks", LIVE, "%d active hook(s): %s"
                               % (len(live_hooks), ", ".join(sorted(live_hooks)[:4])),
                               hp or ".git/hooks"))
    elif hp:
        caps.append(capability("Git hooks", INERT,
                               "core.hooksPath is set to '%s' but that directory holds no "
                               "non-sample hooks. Configured, dead." % hp))
    else:
        caps.append(capability("Git hooks", ABSENT,
                               "no core.hooksPath and no non-sample hooks. Nothing runs on commit."))

    # ---- agent hooks ---------------------------------------------------------------------
    agent_hook_cmds, declared, broken = [], 0, []
    for s in (".claude/settings.json", ".claude/settings.local.json"):
        p = os.path.join(root, s.replace("/", os.sep))
        if not os.path.isfile(p):
            continue
        try:
            d = json.loads(read(p))
        except Exception:
            continue
        hooks = d.get("hooks")
        if hooks is None:
            continue
        if not hooks:
            broken.append("%s declares a 'hooks' key with nothing in it" % s)
            continue
        for _, groups in hooks.items():
            for grp in groups or []:
                for h in grp.get("hooks", []) or []:
                    declared += 1
                    agent_hook_cmds.append(h.get("command", ""))
    if declared:
        caps.append(capability("Agent hooks", LIVE, "%d hook command(s) declared." % declared))
    elif broken:
        caps.append(capability("Agent hooks", INERT, broken[0] + " - the surface exists, "
                                                     "nothing is wired to it."))
    else:
        caps.append(capability("Agent hooks", ABSENT, "no agent hook configuration."))

    # ---- tests ---------------------------------------------------------------------------
    tracked = (git(root, "ls-files") or "").split("\n")
    tests = [f for f in tracked if re.search(r"(^|/)(tests?/|test_[^/]*\.|[^/]*_test\.)", f, re.I)]
    sched_text = os_scheduler_text()
    runner_text = ci_text + "\n" + hook_text + "\n" + "\n".join(agent_hook_cmds)
    RUNNERS = r"\b(pytest|unittest|jest|vitest|go test|cargo test|npm t(est)?)\b"
    runs_tests = bool(re.search(RUNNERS, runner_text))
    # Search the OS scheduler here too. Leaving it out of the gate check produced one false
    # headline already; the same omission here would produce a second one.
    sched_tests = bool(sched_text and re.search(RUNNERS, sched_text))
    if not tests:
        caps.append(capability("Tests", ABSENT, "no test files found."))
    elif runs_tests:
        caps.append(capability("Tests", LIVE, "%d test file(s), invoked by automation." % len(tests)))
    elif sched_tests:
        caps.append(capability("Tests", INERT,
                               "%d test file(s), run only by a scheduled job. That reports a "
                               "break after it has been committed, not before." % len(tests)))
    else:
        unchecked = " The OS scheduler could not be searched here, so a scheduled runner cannot " \
                    "be ruled out." if sched_text is None else ""
        caps.append(capability("Tests", INERT,
                               "%d test file(s) tracked, and no CI job, git hook, agent hook or "
                               "scheduled task invokes any test runner. They pass only when "
                               "someone remembers to run them.%s" % (len(tests), unchecked)))

    # ---- the flagship: gates the instructions mandate but nothing invokes -----------------
    doc_hits, docs_found, doc_texts = {}, [], {}
    for d in AGENT_DOCS:
        p = os.path.join(root, d)
        if not os.path.isfile(p):
            continue
        docs_found.append(d)
        text = read(p)
        doc_texts[d] = text
        for m in GATE_RE.findall(text):
            script = m.replace("\\", "/")
            if not os.path.exists(os.path.join(root, script)):
                continue                       # cannot be a gate if the script is not here
            doc_hits.setdefault(script, set()).add(d)

    # A scheduled task RUNS a gate but cannot BLOCK a commit - it is monitoring, not enforcement.
    # The instructions say "before commit ... do not commit red"; a weekly job that appends to a
    # log satisfies neither half of that. Counted separately, never folded into "live".
    monitored = []
    unenforced = []
    script_states = {}
    for script, where in sorted(doc_hits.items()):
        base = os.path.basename(script)
        if names_script(runner_text, base) or names_script(runner_text, script):
            script_states[script] = "live"
            continue
        if sched_text and (names_script(sched_text, base)
                           or names_script(sched_text, script.replace("/", "\\"))):
            monitored.append((script, sorted(where)))
            script_states[script] = "monitored"
            continue
        unenforced.append((script, sorted(where)))
        script_states[script] = "unenforced"

    if not docs_found:
        caps.append(capability("Mandated gates", UNKNOWN,
                               "no agent-instruction file (%s) - nothing mandates anything, so "
                               "there is nothing to enforce." % "/".join(AGENT_DOCS[:2])))
    elif not doc_hits:
        caps.append(capability("Mandated gates", ABSENT,
                               "%s names no runnable script to gate on."
                               % ", ".join(docs_found)))
    elif unenforced:
        note = ""
        if monitored:
            note = " (%d more run on a schedule, which MONITORS but cannot block a commit: %s)" \
                   % (len(monitored), ", ".join(os.path.basename(s) for s, _ in monitored))
        if sched_text is None:
            note += " NOTE: the OS scheduler could not be searched on this platform, so some of " \
                    "these may in fact be scheduled."
        caps.append(capability("Mandated gates", INERT,
                               "%d of %d script(s) your own instructions tell agents to run are "
                               "invoked by no automation at all.%s"
                               % (len(unenforced), len(doc_hits), note),
                               "; ".join("%s (named in %s)" % (s, "+".join(w))
                                         for s, w in unenforced),
                               scripts=script_states))
    elif monitored:
        caps.append(capability("Mandated gates", INERT,
                               "every mandated script runs on a SCHEDULE, and none of them gates "
                               "a commit. Your instructions say 'before commit - do not commit "
                               "red'; a scheduled job discovers red afterwards.",
                               scripts=script_states))
    else:
        caps.append(capability("Mandated gates", LIVE,
                               "every script the instructions mandate is invoked by automation.",
                               scripts=script_states))

    # ---- K-1: dangerous flags handed out ungated (issue #68) ------------------------------
    # The mirror of the flagship check. Mandated-gates asks "which promised checks does
    # nothing run?"; this asks "which instructions hand an agent destructive capability with
    # no verification attached?". Same three states: a grant with an adjacent approval rule
    # (or a prohibition) is LIVE gating; a grant with nothing adjacent is INERT - it reads as
    # a priced convenience and is actually a standing free pass.
    flag_hits, gated_count = [], 0
    for d in docs_found:
        lines = doc_texts.get(d, "").split("\n")
        for i, ln in enumerate(lines):
            m = DANGEROUS_FLAG_RE.search(ln)
            if not m:
                continue
            lo, hi = max(0, i - ADJACENCY), min(len(lines), i + ADJACENCY + 1)
            # The flag tokens are struck from the window before the approval test, because
            # "--auto-approve" CONTAINS "approve" - without this, the most dangerous flag on
            # the list gated itself and could never be flagged at all.
            if any(APPROVAL_RE.search(DANGEROUS_FLAG_RE.sub("", lines[j])) for j in range(lo, hi)):
                gated_count += 1
            else:
                flag_hits.append("%s:%d %s" % (d, i + 1, m.group(0)))
    if docs_found:
        if flag_hits:
            caps.append(capability("Dangerous flags", INERT,
                                   "%d instruction line(s) hand out a gate-removing flag with no "
                                   "approval or prohibition rule within %d line(s). These flags "
                                   "exist so a HUMAN can push a known-good run through; ungated, "
                                   "they are a standing grant of exactly the checks they disable."
                                   % (len(flag_hits), ADJACENCY),
                                   "; ".join(flag_hits)))
        elif gated_count:
            caps.append(capability("Dangerous flags", LIVE,
                                   "%d gate-removing flag mention(s), every one adjacent to an "
                                   "approval or prohibition rule." % gated_count))
        else:
            caps.append(capability("Dangerous flags", ABSENT,
                                   "the instruction docs mention no gate-removing flags "
                                   "(--auto-approve / --skip-* / --force / --yes / --no-verify)."))

    # ---- K-2: stale literal scope defaults in mandated entry points (issue #69) ------------
    # Universe = the scripts the repo's own instructions mandate - the set doc_hits already
    # built - NOT the whole tree. That keeps test fixtures and vendored code out by
    # construction and this tool out of the repo-wide-linter business.
    scope_hits, py_examined = [], 0
    for script in sorted(doc_hits):
        if not script.lower().endswith(".py"):
            continue
        py_examined += 1
        for i, ln in enumerate(read(os.path.join(root, script)).split("\n")):
            if ASSIGN_DATE_RE.match(ln) or DEFAULT_DATE_RE.search(ln):
                scope_hits.append("%s:%d %s" % (script, i + 1, ln.strip()[:60]))
    if py_examined:
        if scope_hits:
            caps.append(capability("Scope defaults", INERT,
                                   "%d hardcoded date-literal scope default(s) in the %d python "
                                   "entry point(s) your instructions mandate. A literal scope was "
                                   "true the day it was written; the day an argument is omitted "
                                   "it silently scopes the run to a stale window."
                                   % (len(scope_hits), py_examined),
                                   "; ".join(scope_hits)))
        else:
            caps.append(capability("Scope defaults", LIVE,
                                   "no date-literal scope defaults in the %d mandated python "
                                   "entry point(s) (module assignments and argparse defaults "
                                   "checked; environment-name defaults are out of scope v1)."
                                   % py_examined))

    inert = [c for c in caps if c["state"] == INERT]

    if a.json:
        print(json.dumps({"version": VERSION, "repo": root,
                          "capabilities": caps, "inert": len(inert)}, indent=2))
        return INERT_FOUND if inert else OK

    print("\n  CONFIGURED vs ACTUALLY RUNNING")
    print("  %s" % root)
    print("  " + "-" * 74)
    for c in caps:
        mark = {LIVE: "+", ABSENT: "-", INERT: "x", UNKNOWN: "?"}[c["state"]]
        print("  %s  %-24s %-7s %s" % (mark, c["capability"], c["state"], c["detail"]))
        if c["evidence"]:
            print("     %-24s %-7s %s" % ("", "", c["evidence"]))
    print("  " + "-" * 74)
    if inert:
        print("  %d capability(ies) DECLARED BUT DEAD. That is worse than absent: it reads as"
              % len(inert))
        print("  coverage from the outside, and a repo with no gate at least knows it has none.")
    else:
        print("  Nothing here is merely declared - what exists, runs.")
    print("  Nothing was written to this repo - run `git status` to confirm.\n")
    return INERT_FOUND if inert else OK


if __name__ == "__main__":
    sys.exit(main())
