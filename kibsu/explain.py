#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
explain  v1.0.0  -  the lines behind the percentage.

WHAT THIS IS FOR
  `report` says "47.8% of your procedural instructions are verifiable". `audit` breaks that
  down to units. Neither says WHICH lines, so a reader who accepts the number has nothing to
  do with it. This prints them, as `path:line  text` - the shape an editor or a terminal turns
  into a link, and the shape `grep -n` has always used.

WHAT IT IS NOT
  Not a second opinion. The verdict on every line is the scorer's own (audit.py's
  checkable_because), read back through `audit --json --lines`, so the list cannot be judged
  by a different rule than the percentage it explains. If a line here surprises you, the
  argument is with `audit --definitions`, and that is where it should be had.

  Not a to-do list for everything. Only PROCEDURE units are listed by default. A doctrine
  unit ("name the hidden assumption before building") produces judgement, not files; its 0%
  is the genre working. Listing its lines as defects would invite the one fix that makes
  things worse - rewriting judgement as ceremony so a number goes up. The units held back
  are counted in the output, and --all-genres lists them.

  Not advice on how to rewrite a line. It states the rule a line would have to meet. Whether
  a given instruction SHOULD meet it is the author's call, not a regular expression's.

Dependency-free. Python 3.8+. Reads only.

  python -m kibsu explain [repo] [--skills DIR] [--unit TEXT] [--all-genres] [--full] [--json]

EXIT CODES
  0  it ran. Lines found or not - a finding never makes this non-zero, same as `report`.
  3  it could not run: nothing here tells agents how to work, or the scorer returned nothing.
     Same value and same meaning as report's and check's CANNOT_RUN.
"""
import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from . import config
from .report import CANNOT_RUN, find_skills_dir, root_instruction_files

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

VERSION = "1.0.0"
UNITS_SHOWN = 12            # human output only; --full lifts both caps, --json never applies them
LINES_PER_UNIT = 10
TEXT_WIDTH = 100
NOT_FAIR_GENRES = ("doctrine", "persona", "reference", "mixed")


def audit_lines(path):
    """The scorer's own per-line verdicts for the instruction set at `path`, or None."""
    audit_py = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audit.py")
    try:
        p = subprocess.run([sys.executable, audit_py, path, "--json", "--lines"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        return json.loads(p.stdout) if p.returncode == 0 and p.stdout else None
    except Exception:
        return None


def build(root, skills, measured):
    """Shape the scorer's rows for a reader: one entry per unit, paths relative to the REPO
    (the scorer's are relative to the instruction directory it was pointed at)."""
    prefix = os.path.relpath(skills, root).replace("\\", "/")
    prefix = "" if prefix == "." else prefix + "/"
    units = []
    for row in measured["skills"]:
        units.append({
            "file": prefix + row["file"],
            "unit": row["skill"],
            "genre": row["genre"],
            "genre_source": row["genre_source"],
            "instructions": row["instructions"],
            "checkable": row["checkable"],
            "claimable": row["claimable"],
            "lines": row["line_records"],
        })
    return {"version": VERSION, "scorer": measured["version"], "repo": root,
            "instruction_dir": prefix.rstrip("/") or ".",
            "procedure_only": measured["procedure_only"], "units": units}


def unit_hint(path):
    """The shortest text that picks this file out for --unit: a SKILL.md is named by its
    directory, since every one of them shares the file name."""
    head, tail = os.path.split(path)
    if tail.lower() == "skill.md" and head:
        return os.path.basename(head)
    return os.path.splitext(tail)[0]


def shorten(text):
    text = " ".join(text.split())
    return text if len(text) <= TEXT_WIDTH else text[:TEXT_WIDTH - 3].rstrip() + "..."


def render(result, all_genres, full, unit_filter):
    rule = "  " + "-" * 74
    proc = result["procedure_only"]
    print("\n  THE LINES BEHIND THE NUMBER")
    print("  %s" % result["repo"])
    print(rule)
    if proc["instructions"]:
        print("  %.1f%% of your procedural instructions are verifiable: %d of %d."
              % (proc["pct"], proc["checkable"], proc["instructions"]))
    else:
        print("  No procedure-genre instructions were found here, so there is no percentage.")

    wanted = [u for u in result["units"]
              if (all_genres or u["genre"] == "procedure")
              and (not unit_filter or unit_filter.lower() in u["file"].lower())]
    listed = sorted([u for u in wanted if u["claimable"]],
                    key=lambda u: (-u["claimable"], u["file"]))
    total = sum(u["claimable"] for u in listed)

    shown_units = listed if full else listed[:UNITS_SHOWN]
    shown = sum(u["claimable"] if full else min(u["claimable"], LINES_PER_UNIT)
                for u in shown_units)
    if not listed:
        print("  Every instruction in scope can be checked - nothing to list.")
    elif shown == total:
        print("  %d line(s) can only be confirmed by the agent saying so:" % total)
    else:
        # Never let a capped listing read as the whole of it.
        print("  %d line(s) can only be confirmed by the agent saying so. Showing %d - "
              "--full lists all:" % (total, shown))
    for u in shown_units:
        tag = "" if u["genre"] == "procedure" else "   [%s]" % u["genre"]
        print("\n  %s   %d of %d cannot be checked%s"
              % (u["file"], u["claimable"], u["instructions"], tag))
        lines = [rec for rec in u["lines"] if rec["verdict"] == "claimable"]
        for rec in (lines if full else lines[:LINES_PER_UNIT]):
            print("    %s:%d  %s" % (u["file"], rec["line"], shorten(rec["text"])))
        if not full and len(lines) > LINES_PER_UNIT:
            print("    ... %d more in this file (--full, or --unit %s)"
                  % (len(lines) - LINES_PER_UNIT, unit_hint(u["file"])))
    if len(listed) > len(shown_units):
        rest = listed[len(shown_units):]
        print("\n  ... %d more file(s) holding %d line(s) (--full lists everything)"
              % (len(rest), sum(u["claimable"] for u in rest)))

    print(rule)
    print("  A line is CHECKABLE when a reviewer could confirm it from the repository alone: it")
    print("  is a tick-box, names a command to run, names a file, or names an exit code, a diff")
    print("  or an assertion. `python -m kibsu audit <dir> --definitions` prints the whole rule.")
    print("  Not every line should be. Judgement has nothing to check, and rewriting it as")
    print("  ceremony improves the number and worsens the instruction.")
    print("  The unit is the LINE as written: a sentence wrapped over three lines appears as each")
    print("  line that carries a directive word, fragments included. That is what the percentage")
    print("  counts too - if an entry reads like half a sentence, it was scored as one.")
    if not all_genres:
        held = {}
        for u in result["units"]:
            if u["genre"] != "procedure":
                held[u["genre"]] = held.get(u["genre"], 0) + 1
        for genre in NOT_FAIR_GENRES:
            if genre in held:
                print("  %d %s unit(s) not listed - checkability is not a fair test of them "
                      "(--all-genres lists them)." % (held[genre], genre))
    # Kept last, as in `report`: a guarantee, not a softener for something that follows.
    print("  Nothing was written to this repo - run `git status` to confirm.\n")


def main():
    ap = argparse.ArgumentParser(
        prog="python -m kibsu explain",
        description="Which instructions can nobody check? The lines behind report's percentage.")
    ap.add_argument("repo", nargs="?", default=".")
    ap.add_argument("--skills", default=None, help="agent-instruction dir (auto-detected, "
                                                   "the same way `report` detects it)")
    ap.add_argument("--unit", default=None, metavar="TEXT",
                    help="only files whose path contains TEXT")
    ap.add_argument("--all-genres", action="store_true",
                    help="also list doctrine / persona / reference / mixed units")
    ap.add_argument("--full", action="store_true", help="no cap on files or lines shown")
    ap.add_argument("--json", action="store_true",
                    help="every unit and every instruction line, both verdicts, uncapped")
    a = ap.parse_args()
    root = os.path.abspath(a.repo)
    cfg = config.load(root)

    skills = a.skills or find_skills_dir(root, cfg)
    if not skills and root_instruction_files(root, cfg):
        skills = root            # the root-file layout: same fallback, same order, as report
    measured = audit_lines(os.path.abspath(skills)) if skills else None
    if not measured:
        reason = ("the scorer returned nothing for %s" % skills if skills else
                  "no agent-instruction directory or root instruction file found")
        if a.json:
            print(json.dumps({"version": VERSION, "repo": root, "complete": False,
                              "reason": reason}, indent=2))
        else:
            print("\n  COULD NOT EXPLAIN - %s. Nothing here tells agents how to work, so there "
                  "is nothing to list.\n" % reason)
        return CANNOT_RUN

    result = build(root, os.path.abspath(skills), measured)
    if a.json:
        print(json.dumps(result, indent=2))
        return 0
    render(result, a.all_genres, a.full, a.unit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
