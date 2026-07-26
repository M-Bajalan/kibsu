#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ns_gate.py  v1.0.0  -  the commit gate your instructions may already claim to have.

WHY
  A repo's own agent instructions often say something like: "before commit -> run the checks;
  don't commit red." A discovery pass (kibsu's own `discover` subcommand does exactly this) can
  measure what actually INVOKES that claim: often nothing. A checker that only a CI job runs
  weekly MONITORS, but cannot block anything - "do not commit red" is not satisfied by
  discovering red the following Sunday.

  So the rule ends up enforced, for its entire life, by whoever remembers. That makes it a
  mechanism, not a mandate, and mechanisms are what this file is.

WHY A BASELINE, AND WHY IDENTITY AND NOT A COUNT
  A repo's checks can easily start out already failing - pre-existing violations awaiting
  cleanup that nobody has gotten to yet. A gate that blocks on "the check exited non-zero" would
  block EVERY commit from the moment it is installed, and get ripped out within the hour. That is
  how gates die - not by being wrong, but by being unusable.

  So the gate blocks on NEW violations only. And it stores the IDENTITY of each accepted
  violation, not the count: a baseline of "42" passes happily when you fix one violation and
  introduce another, which is precisely the case a gate exists to catch.

DRIVEN BY CONFIG, NOT TWO HARDCODED SCRIPTS
  What used to be exactly two constants pointing at two specific scripts is now a list read from
  .kibsu.json's "gates" key:

      "gates": [ {"name": "lint", "cmd": ["python", "lint.py"], "cannot_run_exit": 2} ]

  Every configured command runs from the repo root with its stdout+stderr captured. Exit 0 is
  clean. Exit equal to that gate's own "cannot_run_exit" (if set) means the gate could not run at
  all - it is SKIPPED with a warning and every OTHER configured gate still enforces. Any other
  non-zero means the gate found something: its output is parsed for the shared [RULE] Title (N):
  / "    - item" shape every gate command is expected to speak, and judged against that gate's
  own baseline entry by the identity+count rule below. A configured command that emits a
  different shape is a known limitation to document, not a reason to hardcode a second parser.

  With no gates configured at all, --check exits 0 and says so plainly. That is an abstention,
  not a pass, and this file does not pretend otherwise.

FAIL-SAFE, NOT FAIL-SHUT
  If the gate cannot run - python missing, a configured command gone, output it cannot parse - it
  ALLOWS the commit and says so loudly on stderr. A gate that blocks for a reason nobody can see
  gets disabled, and then nothing is gated. Same posture as ns_check's exit 3 and ns_tokens.

Dependency-free. Python 3.8+. --check writes nothing.

  python -m kibsu gate --check                run the gates (this is what the hook calls)
  python -m kibsu gate --baseline             accept today's violations as the known-good set
  python -m kibsu gate --status               what is wired right now
  python -m kibsu gate --install [--apply]    wire the pre-commit hook (dry-run unless --apply)
  python -m kibsu gate --uninstall [--apply]  put it back exactly as it was

EXIT CODES
  0  pass, or could-not-run (fail-safe)      1  BLOCKED - a new violation
"""
import argparse, io, json, os, re, shutil, subprocess, sys, time

# This file is also VENDORED on its own (see install(), below, which copies gate.py + config.py,
# and only those two, into a target repo's .kibsu/bin/ so the hook never depends on kibsu being
# importable). A vendored copy has no package around it, so "from . import config" would raise
# ImportError: attempted relative import with no known parent package - exactly the failure
# check.py already documents for its own sibling import of index.py. Mirror that fix: resolve
# config.py next to THIS file on disk and import it as a plain top-level module, which works
# identically whether gate.py is running as part of the kibsu package or as a loose vendored file.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

VERSION = "1.0.0"
NS_DIR = ".kibsu"
HOOKS_REL = os.path.join(NS_DIR, "hooks")
BIN_REL = os.path.join(NS_DIR, "bin")
BASELINE_REL = os.path.join(NS_DIR, "gate_baseline.json")

# Vendored at install time, resolved by the hook from the repo root - see install()/HOOK. Only
# these two: gate.py needs config.py to read the "gates" list, and nothing else.
VENDOR_FILES = ("gate.py", "config.py")

# Each configured gate command is expected to print:  [RULE] heading (N):  then
# "    - <violation>" lines. This is the one shared contract every gate command must speak for
# baselining to work at all; a checker with a different output shape is a known limitation (see
# check(), below) - not a reason to hardcode a second parser for it.
RULE_RE = re.compile(r"^\[([A-Za-z0-9_]+)\]")
HEAD_RE = re.compile(r"^\[([A-Za-z0-9_]+)\].*?\((\d+)\):")
ITEM_RE = re.compile(r"^\s+-\s+(.*\S)\s*$")

HOOK = """#!/bin/sh
# kibsu gate - pre-commit gate  (installed by kibsu gate v{v})
#
# Runs every command configured under .kibsu.json's "gates" key before a commit. Blocks only on
# a NEW violation, never on the accepted baseline. Remove with:
#     python -m kibsu gate --uninstall --apply
#
# gate.py and config.py are vendored into {bin}/ at install time and this hook execs the
# vendored gate.py directly - it never shells back into "python -m kibsu", so it never depends
# on kibsu being pip-installed or importable in this clone. If the vendored file is gone (moved,
# deleted, a broken reinstall) that is NOT a violation: warn on stderr and ALLOW the commit,
# same fail-safe posture gate.py's own --check documents for python/module trouble.
root=$(git rev-parse --show-toplevel) || exit 0
gate_tool="$root/{bin}/gate.py"
command -v python >/dev/null 2>&1 && py=python || py=python3
if [ ! -f "$gate_tool" ]; then
  echo "kibsu gate: !! gate.py missing from {bin} - commit ALLOWED, nothing was verified." 1>&2
  echo "kibsu gate: reinstall (gate --install --apply) or uninstall; this is not a pass." 1>&2
  exit 0
fi
exec "$py" "$gate_tool" --check --repo "$root"
"""


def run(args, cwd=None):
    try:
        p = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as e:
        return None, str(e)


def git(root, *args):
    rc, out = run(["git", "-C", root] + list(args))
    return out.strip() if rc == 0 else None


def norm(s):
    """Fold a violation string to ASCII so its identity cannot depend on the environment.

    A checker can emit an em dash. Captured under one console code page it decodes to U+FFFD,
    under another to the real character - and the git hook runs in a DIFFERENT environment than
    an interactive shell. So the same violation had two spellings, and the gate blocked its own
    installation commit as four "new" violations that were in the baseline all along.

    That is the CRLF lesson again (memory/learnings/normalized-read-hides-crlf-false-pass.md):
    an encoding difference producing a confident, wrong verdict. Anything used as an IDENTITY
    must be canonical first.

    Digits are folded for the same reason. Several rules embed a live COUNT or a line number in
    their message - "reports/nightly/ has 29 active artifacts", "file.py:169 .lstrip(...)". Those
    move constantly: a fresh clone saw 23 where this working copy saw 29, because the working copy
    has untracked artifacts the clone does not. Left raw, the gate would have started
    false-blocking within days, as soon as any count shifted by one - and it would have blamed the
    developer for breakage that never happened.

    Growth is still caught: the per-rule declared COUNT is baselined separately, so a rule firing
    on MORE things blocks. What no longer blocks is the same violation reporting a different
    number, which is not new breakage and must not read as it."""
    s = s.encode("ascii", "replace").decode("ascii").strip()
    return re.sub(r"\d+", "#", s)


def parse_violations(text):
    """(items, declared) where items = [(rule, text)] and declared = {rule: count-in-header}.

    Both are needed because a configured gate's own checker can TRUNCATE its output:
    '[R4] Logs in repo (21):' followed by eight items and '... and 13 more'. Identity-only
    baselining is therefore not merely incomplete here, it is actively broken - R4's contents are
    nightly build logs, so the eight that get listed are DIFFERENT eight tomorrow. Every one would
    read as new and the gate would block every commit by morning. A gate that breaks overnight is
    worse than no gate, because you disable it and never come back.

    Returns (items, declared, raws). `raws` is the SAME violations with their text untouched,
    positionally aligned with `items`. Both are needed and conflating them was a bug: identity
    must be normalised (digits folded), but asking git whether a path is ignored requires the
    REAL path - `run_########_####.log` is ignored by nothing because it exists nowhere."""
    items, raws, declared, rule = [], [], {}, "?"
    for ln in text.split("\n"):
        m = HEAD_RE.match(ln)
        if m:
            rule = m.group(1)
            declared[rule] = declared.get(rule, 0) + int(m.group(2))
            continue
        m = RULE_RE.match(ln)
        if m:
            rule = m.group(1)
            declared.setdefault(rule, 0)
            continue
        m = ITEM_RE.match(ln)
        if m and not m.group(1).startswith("..."):
            items.append((rule, norm(m.group(1))))
            raws.append((rule, m.group(1)))
    return items, declared, raws


def split_rules(items, declared):
    """Which rules can be trusted by IDENTITY, and which only by COUNT."""
    listed = {}
    for r, _ in items:
        listed[r] = listed.get(r, 0) + 1
    complete = set(r for r, n in declared.items() if listed.get(r, 0) >= n)
    truncated = set(declared) - complete
    return complete, truncated


PATHISH_RE = re.compile(r"[\w.\-/\\]+/[\w.\-/\\]+")


def ignored(root, texts):
    """Of the paths mentioned in these violations, which does git IGNORE?

    A pre-commit gate must judge what is being COMMITTED. A repo-hygiene checker rightly reports
    on everything on disk, including untracked machine output - but using that unfiltered as a
    commit gate is a category error.

    Found the hard way, live: at 01:00 a scheduled nightly build wrote
    build/logs/run_20260726_0100.log, R4 went 21 -> 22, and the gate blocked a commit. All 22 of
    those logs are gitignored and NONE is tracked. So the gate was refusing a commit over files
    that can never be part of one, on a schedule, forever - roughly four times a day. That is
    precisely how a gate earns its own removal."""
    cands = []
    for t in texts:
        for m in PATHISH_RE.findall(t):
            cands.append(m.replace("\\", "/"))
    if not cands:
        return set()
    # -z and BINARY pipes, deliberately. In text mode on Windows Python translates the "\n"
    # separators to "\r\n", git takes the trailing "\r" as part of the FILENAME, finds it
    # "special", and quotes the whole path back:
    #     "build/logs/run_20260722_1600.log\r"
    # which then matches nothing. -z is NUL-separated in both directions and never quotes, so
    # there is no newline translation and no unescaping to get wrong.
    try:
        p = subprocess.run(["git", "-C", root, "check-ignore", "-z", "--stdin"],
                           input="\0".join(cands).encode("utf-8"), capture_output=True)
    except Exception:
        return set()          # cannot tell -> ignore nothing, i.e. stay strict
    out = p.stdout.decode("utf-8", "replace")
    return set(x.replace("\\", "/") for x in out.split("\0") if x)


def is_ignored_violation(text, ign):
    return any(m.replace("\\", "/") in ign for m in PATHISH_RE.findall(text))


def _empty_gate_baseline():
    return {"accepted": set(), "counts": {}, "truncated": set()}


def load_baseline_raw(root):
    """The baseline file exactly as written - JSON-native types, no set conversion. Used by
    baseline() so a gate that fails to run THIS time does not lose a PRIOR run's acceptance."""
    p = os.path.join(root, BASELINE_REL)
    if not os.path.isfile(p):
        return None
    try:
        with io.open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def load_baseline(root):
    """The baseline file, converted for check(): per-gate accepted/counts/truncated, with
    accepted upgraded to a set of tuples and truncated to a set. None means "no baseline file at
    all" (or unreadable), which is the fail-safe trigger - never confuse that with "a baseline
    exists but doesn't cover this particular gate yet", which is a normal, per-gate state."""
    raw = load_baseline_raw(root)
    if raw is None:
        return None
    gates = {}
    for name, g in (raw.get("gates") or {}).items():
        gates[name] = {
            "accepted": set(tuple(x) for x in g.get("accepted", [])),
            "counts": g.get("counts", {}),
            "truncated": set(g.get("truncated_rules", [])),
        }
    return {"gates": gates}


def load_gate_config(root):
    """Read config["gates"] from .kibsu.json and normalise each entry: a name (defaulted from the
    command itself), a cmd list, and an optional cannot_run_exit. An entry that is not shaped like
    a runnable command is dropped with a stderr warning rather than crashing a git hook over a
    config typo - the same fail-safe posture as everything else in this file."""
    raw = config.load(root).get("gates") or []
    out = []
    for i, g in enumerate(raw):
        if not isinstance(g, dict) or not g.get("cmd"):
            sys.stderr.write("kibsu gate: gates[%d] in .kibsu.json has no \"cmd\" - ignoring it.\n" % i)
            continue
        cmd = g["cmd"]
        if not isinstance(cmd, list) or not all(isinstance(c, str) for c in cmd):
            sys.stderr.write("kibsu gate: gates[%d].cmd must be a list of strings - ignoring it.\n" % i)
            continue
        out.append({
            "name": g.get("name") or " ".join(cmd),
            "cmd": cmd,
            "cannot_run_exit": g.get("cannot_run_exit"),
        })
    return out


# ------------------------------------------------------------------------------- check -------
def _run_one_gate(root, g, gate_base):
    """Run a single configured gate and judge it against ITS OWN baseline entry.

    Returns a dict describing what happened. status is one of:
      SKIPPED   the command could not be run at all, or exited its own cannot_run_exit
      PASS      ran, and (after baseline + gitignore filtering) nothing NEW showed up
      BLOCKED   ran, and something NEW (or a truncated rule's count growing) showed up

    Exactly one gate's worth of the hybrid identity+count logic lives here - preserved from the
    single-linter original, just scoped per gate instead of assumed global."""
    name, cmd, cannot_run_exit = g["name"], g["cmd"], g["cannot_run_exit"]
    rc, out = run(cmd, root)
    if rc is None:
        return {"name": name, "cmd": cmd, "status": "SKIPPED",
                "detail": "could not be executed (%s)" % out[:120]}
    if cannot_run_exit is not None and rc == cannot_run_exit:
        # Degrade, do not abandon: THIS gate is skipped with a warning while every OTHER
        # configured gate still runs and still enforces. Partial coverage beats none, and a gate
        # that silently allows everything because one checker is unavailable is the failure mode
        # this whole file exists to prevent.
        first = next((l.strip() for l in out.split("\n") if l.strip()), "no detail")
        return {"name": name, "cmd": cmd, "status": "SKIPPED",
                "detail": "exit %d (%s)" % (rc, first)}

    items, declared, raws = parse_violations(out)

    # Rules whose list this gate's checker TRUNCATES are judged on count only - their listed
    # members churn (R4 is nightly build logs) and identity would false-positive every morning.
    trunc = gate_base["truncated"]
    # RAW text here, never the normalised form - see parse_violations.
    ign = ignored(root, [t for _, t in raws])
    ign_flag = [is_ignored_violation(t, ign) for _, t in raws]
    hygiene = set()
    for rule in trunc:
        sample = [f for (r, _), f in zip(raws, ign_flag) if r == rule]
        # Every sampled member of this rule points at a gitignored path, so the rule tracks
        # machine output rather than anything a commit can contain. Report it, never block on it.
        if sample and all(sample):
            hygiene.add(rule)

    skipped_ignored = [t for (_, t), f in zip(raws, ign_flag) if f]
    now_ids = set(i for i, f in zip(items, ign_flag) if i[0] not in trunc and not f)
    new = sorted(now_ids - gate_base["accepted"])
    fixed = len(gate_base["accepted"] - now_ids)

    grew = []
    for rule in sorted(trunc - hygiene):
        was = int(gate_base["counts"].get(rule, 0))
        isnow = int(declared.get(rule, 0))
        if isnow > was:
            grew.append((rule, was, isnow))

    blocked = bool(new) or bool(grew)
    return {"name": name, "cmd": cmd, "rc": rc, "status": "BLOCKED" if blocked else "PASS",
            "new": new, "fixed": fixed, "grew": grew, "hygiene": hygiene,
            "skipped_ignored": skipped_ignored,
            "accepted_n": len(gate_base["accepted"]), "trunc_n": len(trunc)}


def check(root):
    def allow(why):
        sys.stderr.write("kibsu gate: CANNOT RUN - %s. Commit ALLOWED.\n" % why)
        return 0

    all_cfg = config.load(root).get("gates") or []
    cfg = load_gate_config(root)
    if not all_cfg:
        print("kibsu gate: no gates configured (.kibsu.json has \"gates\": []) - nothing was "
              "checked.")
        print("This is an abstention, not a pass. Add at least one command under \"gates\" to "
              "enable enforcement.")
        return 0
    if not cfg:
        return allow("%d configured gate(s), but none had a valid \"cmd\" - see stderr above"
                     % len(all_cfg))

    base = load_baseline(root)
    if base is None:
        return allow("no baseline at %s - run `python -m kibsu gate --baseline` once to accept "
                     "the current violations" % BASELINE_REL)

    results = []
    for g in cfg:
        gate_base = base["gates"].get(g["name"]) or _empty_gate_baseline()
        results.append(_run_one_gate(root, g, gate_base))

    for r in results:
        if r["status"] == "SKIPPED":
            sys.stderr.write("kibsu gate: gate '%s' CANNOT RUN (%s) - skipping it, other gates "
                             "still enforced.\n" % (r["name"], r["detail"]))

    ran = [r for r in results if r["status"] != "SKIPPED"]
    if not ran:
        sys.stderr.write("kibsu gate: every configured gate CANNOT RUN. Commit ALLOWED, nothing "
                         "was verified.\n")
        print("kibsu gate: PASS (fail-safe) - every configured gate could not run; nothing was "
              "verified.")
        return 0

    blocked = [r for r in ran if r["status"] == "BLOCKED"]

    if not blocked:
        parts = []
        for r in results:
            if r["status"] == "SKIPPED":
                parts.append("%s SKIPPED (%s)" % (r["name"], r["detail"]))
            else:
                parts.append("%s clean (%d accepted by identity, %d rule(s) by count)"
                             % (r["name"], r["accepted_n"], r["trunc_n"]))
        line = ("kibsu gate: PASS - no new violations across %d configured gate(s): %s"
               % (len(cfg), "; ".join(parts)))
        total_fixed = sum(r.get("fixed", 0) for r in ran)
        if total_fixed:
            line += ("; %d baseline violation(s) FIXED - re-baseline to lock the gain in"
                    % total_fixed)
        hygiene_all = set()
        skipped_ignored_all = []
        for r in ran:
            hygiene_all |= r.get("hygiene", set())
            skipped_ignored_all += r.get("skipped_ignored", [])
        if hygiene_all or skipped_ignored_all:
            line += ("\nkibsu gate: not gated (gitignored, cannot reach a commit): %s"
                     % (", ".join("rule %s" % r for r in sorted(hygiene_all))
                        or "%d violation(s)" % len(skipped_ignored_all)))
        print(line)
        return 0

    print("")
    print("  COMMIT BLOCKED by kibsu gate v%s" % VERSION)
    print("  " + "-" * 70)
    for r in results:
        if r["status"] == "SKIPPED":
            print("  ~  gate '%s' CANNOT RUN (%s) - skipped, not held against you."
                  % (r["name"], r["detail"]))
    for r in blocked:
        print("  x  gate '%s'  (%s)" % (r["name"], " ".join(r["cmd"])))
        if r["new"]:
            print("       %d NEW violation(s) not in the accepted baseline:" % len(r["new"]))
            for rule, item in r["new"][:10]:
                print("         [%s] %s" % (rule, item))
            if len(r["new"]) > 10:
                print("         ... and %d more" % (len(r["new"]) - 10))
        if r["grew"]:
            print("       %d rule(s) whose violation COUNT rose above the baseline:" % len(r["grew"]))
            for rule, was, isnow in r["grew"]:
                print("         [%s]  %d -> %d   (+%d)" % (rule, was, isnow, isnow - was))
            print("       these rules are judged by count because this gate's checker truncates "
                  "their list.")
    print("  " + "-" * 70)
    total_accepted = sum(r.get("accepted_n", 0) for r in ran)
    print("  This gate blocks NEW breakage only - %d pre-existing violation(s) are accepted."
          % total_accepted)
    print("     if this is intentional and you accept it:")
    print("              python -m kibsu gate --baseline")
    print("  Bypass once (it is recorded in the reflog either way):  git commit --no-verify")
    print("")
    return 1


# ---------------------------------------------------------------------------- baseline -------
def baseline(root):
    all_cfg = config.load(root).get("gates") or []
    if not all_cfg:
        print("kibsu gate: no gates configured (.kibsu.json has \"gates\": []) - nothing to "
              "baseline.")
        return 0
    cfg = load_gate_config(root)
    if not cfg:
        print("CANNOT RUN: %d configured gate(s), but none had a valid \"cmd\"." % len(all_cfg))
        return 0

    prev_raw = load_baseline_raw(root)
    # Start from what is already on disk so a gate that fails to run THIS time keeps its PRIOR
    # acceptance instead of being silently dropped; only gates that ran successfully (or are no
    # longer configured) change below. Gates no longer present in config are pruned - the file
    # stays scoped to what is actually configured.
    gates_payload = {}
    if prev_raw:
        for name, g in (prev_raw.get("gates") or {}).items():
            if any(gg["name"] == name for gg in cfg):
                gates_payload[name] = g

    any_ok = False
    for g in cfg:
        name, cmd, cannot_run_exit = g["name"], g["cmd"], g["cannot_run_exit"]
        rc, out = run(cmd, root)
        if rc is None:
            print("  gate '%s': CANNOT RUN (%s) - not (re)baselined; other gates continue."
                  % (name, out[:120]))
            continue
        if cannot_run_exit is not None and rc == cannot_run_exit:
            first = next((l.strip() for l in out.split("\n") if l.strip()), "no detail")
            print("  gate '%s': CANNOT RUN (exit %d, %s) - not (re)baselined; other gates "
                  "continue." % (name, rc, first))
            continue
        any_ok = True
        items, declared, _raws = parse_violations(out)
        complete, truncated = split_rules(items, declared)
        accepted = [list(x) for x in items if x[0] in complete]
        gates_payload[name] = {
            "accepted": accepted,
            "counts": {r: int(declared[r]) for r in sorted(declared)},
            "truncated_rules": sorted(truncated),
        }
        total = sum(declared.values())
        print("  gate '%s': accepted %d violation(s) total" % (name, total))
        print("    %d matched by IDENTITY across %d rule(s) - strict"
              % (len(accepted), len(complete)))
        if truncated:
            print("    %d matched by COUNT ONLY, because this gate's checker truncates these "
                  "rules:" % (total - len(accepted)))
            for r in sorted(truncated):
                print("      [%s] declares %d, lists %d" % (r, declared[r],
                                                            sum(1 for i in items if i[0] == r)))

    if not any_ok and not gates_payload:
        print("  CANNOT RUN: no configured gate could be executed. Nothing was baselined.")
        return 0

    d = os.path.join(root, NS_DIR)
    if not os.path.isdir(d):
        os.makedirs(d)
    payload = {
        "version": VERSION,
        "written": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "note": "Violations accepted as pre-existing, per configured gate. The gate blocks only "
                "on what is NOT here. Rules with a COMPLETE list are matched by identity, so "
                "fixing one violation and introducing another is still caught. Rules a gate's "
                "checker TRUNCATES are matched by count only - a weaker guarantee, listed under "
                "truncated_rules so it is visible rather than assumed.",
        "gates": gates_payload,
    }
    with io.open(os.path.join(root, BASELINE_REL), "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print("  baseline written: %s" % BASELINE_REL)
    print("  Track this file in git - it is the record of what you agreed to live with.")
    return 0


# ----------------------------------------------------------------------------- status --------
def status(root):
    hp = git(root, "config", "--get", "core.hooksPath")
    hook = os.path.join(root, HOOKS_REL, "pre-commit")
    cfg = load_gate_config(root)
    base = load_baseline(root)
    print("\n  kibsu gate status")
    print("  " + "-" * 70)
    print("  core.hooksPath     %s" % (hp or "(unset - default .git/hooks)"))
    print("  gate hook          %s" % ("present" if os.path.isfile(hook) else "ABSENT"))
    if not cfg:
        print("  gates configured   NONE - add entries under \"gates\" in .kibsu.json to enable")
    else:
        print("  gates configured   %d: %s" % (len(cfg), ", ".join(g["name"] for g in cfg)))
        if base is None:
            print("  baseline           ABSENT - gate would fail-safe (allow everything)")
        else:
            for g in cfg:
                gb = base["gates"].get(g["name"])
                if gb is None:
                    print("    %-20s not yet baselined" % g["name"])
                else:
                    total = sum(int(v) for v in gb["counts"].values()) or len(gb["accepted"])
                    print("    %-20s %d accepted (%d by identity, %d rule(s) by count: %s)"
                          % (g["name"], total, len(gb["accepted"]), len(gb["truncated"]),
                             ", ".join(sorted(gb["truncated"])) or "none"))
    wired = (hp == HOOKS_REL.replace("\\", "/") or hp == HOOKS_REL) and os.path.isfile(hook)
    print("  " + "-" * 70)
    print("  %s\n" % ("GATE IS LIVE - commits are checked."
                      if wired else "GATE IS NOT WIRED - commits are not checked."))
    return 0


# ---------------------------------------------------------------------------- install --------
def install(root, apply_):
    hp = git(root, "config", "--get", "core.hooksPath")
    hooks_abs = os.path.join(root, HOOKS_REL)
    hook_path = os.path.join(hooks_abs, "pre-commit")
    bin_abs = os.path.join(root, BIN_REL)

    if not (config.load(root).get("gates") or []):
        print("  REFUSED: no gates configured. Add at least one command under \"gates\" in "
              ".kibsu.json before installing.")
        return 1
    if hp and hp not in (HOOKS_REL, HOOKS_REL.replace("\\", "/")):
        print("  REFUSED: core.hooksPath is already set to '%s'." % hp)
        print("  Overwriting it would silently disable whatever installed that. Resolve by hand.")
        return 1
    existing = []
    d = os.path.join(root, ".git", "hooks")
    if os.path.isdir(d):
        existing = [f for f in os.listdir(d) if not f.endswith(".sample")]
    if load_baseline(root) is None:
        print("  REFUSED: no baseline yet. Run this first, and read what it accepts:")
        print("      python -m kibsu gate --baseline")
        print("  Installing without one would give you a gate that fail-safes on every commit,")
        print("  which looks like a working gate and checks nothing.")
        return 1

    # here = the directory THIS install() is actually running from (kibsu's package dir, or
    # .kibsu/bin/ if this very copy is itself a vendored one being re-installed elsewhere). Vendor
    # from there so the hook never has to import kibsu - see HOOK's comment for why.
    here = os.path.dirname(os.path.abspath(__file__))
    missing_src = [f for f in VENDOR_FILES if not os.path.isfile(os.path.join(here, f))]
    if missing_src:
        print("  REFUSED: %s not found next to this script - nothing to vendor."
              % ", ".join(missing_src))
        return 1

    print("\n  kibsu gate install plan")
    print("  " + "-" * 70)
    print("  create   %s" % os.path.join(HOOKS_REL, "pre-commit"))
    print("  vendor   %s/{%s}  (hook execs the vendored gate.py; kibsu need not be importable)"
          % (BIN_REL, ", ".join(VENDOR_FILES)))
    print("  set      core.hooksPath = %s   (currently: %s)" % (HOOKS_REL, hp or "unset"))
    if existing:
        print("  WARNING  core.hooksPath REPLACES .git/hooks. These stop running: %s"
              % ", ".join(existing))
    print("  reverse  python -m kibsu gate --uninstall --apply")
    print("  " + "-" * 70)
    if not apply_:
        print("  DRY RUN - nothing written. Re-run with --apply.\n")
        return 0

    if not os.path.isdir(hooks_abs):
        os.makedirs(hooks_abs)
    if not os.path.isdir(bin_abs):
        os.makedirs(bin_abs)
    for f in VENDOR_FILES:
        shutil.copy2(os.path.join(here, f), os.path.join(bin_abs, f))
    with io.open(hook_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(HOOK.format(v=VERSION, bin=BIN_REL.replace("\\", "/")))
    try:
        os.chmod(hook_path, 0o755)
    except Exception:
        pass
    run(["git", "-C", root, "config", "core.hooksPath", HOOKS_REL.replace("\\", "/")])
    print("  INSTALLED. The gate now runs on every commit.\n")
    return 0


def uninstall(root, apply_):
    hp = git(root, "config", "--get", "core.hooksPath")
    hook_path = os.path.join(root, HOOKS_REL, "pre-commit")
    bin_abs = os.path.join(root, BIN_REL)
    vendored_present = [f for f in VENDOR_FILES if os.path.isfile(os.path.join(bin_abs, f))]
    print("\n  kibsu gate uninstall plan")
    print("  " + "-" * 70)
    if hp and hp not in (HOOKS_REL, HOOKS_REL.replace("\\", "/")):
        print("  NOTE: core.hooksPath is '%s', which this tool did not set. Leaving it." % hp)
    else:
        print("  unset    core.hooksPath   (was: %s)" % (hp or "unset"))
    print("  remove   %s" % os.path.join(HOOKS_REL, "pre-commit"))
    if vendored_present:
        print("  remove   %s   (vendored at install, not your data)"
              % ", ".join(BIN_REL + "/" + f for f in vendored_present))
    print("  keep     %s  (your accepted violations - delete by hand if you want them gone)"
          % BASELINE_REL)
    print("  " + "-" * 70)
    if not apply_:
        print("  DRY RUN - nothing changed. Re-run with --apply.\n")
        return 0
    if hp in (HOOKS_REL, HOOKS_REL.replace("\\", "/")):
        run(["git", "-C", root, "config", "--unset", "core.hooksPath"])
    if os.path.isfile(hook_path):
        os.remove(hook_path)
    for f in VENDOR_FILES:
        p = os.path.join(bin_abs, f)
        if os.path.isfile(p):
            os.remove(p)
    # our own vendored gate.py creates __pycache__ in .kibsu/bin when it imports config.py; that
    # residue would leave .kibsu/bin/ (and so .kibsu/hooks/, .kibsu/) un-removable below and make
    # "uninstalled" untrue - same cleanup install.py already does for its own vendored tools.
    pyc = os.path.join(bin_abs, "__pycache__")
    if os.path.isdir(pyc):
        shutil.rmtree(pyc, ignore_errors=True)
    for d in (os.path.join(root, HOOKS_REL), bin_abs):
        try:
            if os.path.isdir(d) and not os.listdir(d):
                os.rmdir(d)
        except OSError:
            pass
    print("  REMOVED. Commits are no longer checked.\n")
    return 0


def main():
    ap = argparse.ArgumentParser(prog="python -m kibsu gate",
                                 description="The commit gate your instructions may already "
                                             "claim to have.")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--baseline", action="store_true")
    g.add_argument("--status", action="store_true")
    g.add_argument("--install", action="store_true")
    g.add_argument("--uninstall", action="store_true")
    ap.add_argument("--repo", default=None)
    ap.add_argument("--apply", action="store_true", help="actually write (install/uninstall)")
    a = ap.parse_args()
    root = os.path.abspath(a.repo) if a.repo else \
        (git(os.getcwd(), "rev-parse", "--show-toplevel") or os.getcwd())
    root = os.path.abspath(root)

    if a.check:
        return check(root)
    if a.baseline:
        return baseline(root)
    if a.status:
        return status(root)
    if a.install:
        return install(root, a.apply)
    return uninstall(root, a.apply)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:                                # never wedge a commit
        sys.stderr.write("kibsu gate: unexpected failure (%s) - commit ALLOWED.\n" % e)
        sys.exit(0)
