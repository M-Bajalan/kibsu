#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Refresh the README's "count it yourself" paragraph from the repository itself.

WHY THIS EXISTS
  Issue #29's guard (tests/test_readme_counts.py) made a stale paragraph impossible to ship,
  and that was the right fix - the numbers had drifted four times by then, and the class does
  not die by diligence, only by machine. But the guard measures the repo's OWN lines and test
  cases, so every change to kibsu/ or tests/ moves the measured truth. The paragraph therefore
  has to move with it, and until now that meant editing four numbers by hand in every code PR.

  Measured cost, 2026-08-28: a batch of seven concurrent PRs all touched that one paragraph.
  Each merge invalidated the other six, and each of the six then needed a re-sync whose only
  real conflict was those four numbers. Seven forced re-syncs to land seven fixes.

  A number that is DERIVED should be produced, not authored. This produces it.

ONE MEASUREMENT, NOT TWO
  This tool imports measure() and CLAIM_RE from the guard rather than reimplementing them.
  That is deliberate and is the whole point: a second copy of the measurement could disagree
  with the first, which is precisely the drift class #29 exists to kill. If the guard's logic
  changes, this tool changes with it, because it IS the guard's logic.

WHAT IT EDITS
  Only the four numbers, in place, by span - the surrounding prose, the line break inside the
  sentence, and every byte around them are left exactly as they were. It rewrites no sentence
  and reflows no paragraph.

USAGE
  python tools/refresh_readme_counts.py            # rewrite the paragraph if it is stale
  python tools/refresh_readme_counts.py --check    # report only; exit 1 if stale, 0 if fresh
  python tools/refresh_readme_counts.py <path>     # operate on some other file (tests use this)

  The optional path exists so this tool can be exercised against a fixture instead of the
  real README - a tool that can only be tested by mutating the repository it lives in is a
  tool whose tests nobody runs. The MEASUREMENT is always of this repository; only the file
  carrying the paragraph is redirectable.

EXIT CODES
  0  fresh (or successfully refreshed)
  1  --check found the paragraph stale
  2  the paragraph could not be found at all
"""
import argparse
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
# The guard is the single source of the measurement; import it rather than restate it.
sys.path.insert(0, os.path.join(ROOT, "tests"))
from test_readme_counts import CLAIM_RE, claims, measure  # noqa: E402

README = os.path.join(ROOT, "README.md")

# Which capture group in CLAIM_RE carries which measured key, and whether it is written with
# thousands separators. Keyed by group number so the rewrite below can work purely on spans.
GROUPS = (
    (1, "kibsu_lines", True),
    (2, "kibsu_files", False),
    (3, "tests_lines", True),
    (4, "cases", False),
)


def render(value, grouped):
    return "{:,}".format(value) if grouped else str(value)


def refresh(text, truth):
    """Return (new_text, changed). Only the four numbers move, and only by span."""
    m = CLAIM_RE.search(text)
    if not m:
        return text, False
    out, changed = text, False
    # Right to left, so replacing a later span cannot shift an earlier one's offsets.
    for group, key, grouped in reversed(GROUPS):
        start, end = m.span(group)
        new = render(truth[key], grouped)
        if out[start:end] != new:
            changed = True
        out = out[:start] + new + out[end:]
    return out, changed


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="python tools/refresh_readme_counts.py",
        description="Refresh (or check) the README's count-it-yourself paragraph.")
    ap.add_argument("--check", action="store_true",
                    help="report only; exit 1 if the paragraph is stale, 0 if it is fresh")
    ap.add_argument("path", nargs="?", default=README,
                    help="file carrying the paragraph (default: this repo's README.md)")
    args = ap.parse_args(argv)

    with io.open(args.path, encoding="utf-8") as fh:
        text = fh.read()

    claimed = claims(text)
    if claimed is None:
        sys.stderr.write(
            "refresh_readme_counts: the 'count it yourself' paragraph is missing or reworded.\n"
            "Update CLAIM_RE in tests/test_readme_counts.py with the new wording - never\n"
            "delete the guard to make this pass.\n")
        return 2

    truth = measure()
    if claimed == truth:
        print("README counts are already correct: "
              "{kibsu_lines:,} lines across {kibsu_files} files in kibsu/, plus "
              "{tests_lines:,} lines of tests running {cases} cases".format(**truth))
        return 0

    print("stale  : {kibsu_lines:,} / {kibsu_files} / {tests_lines:,} / {cases}".format(**claimed))
    print("actual : {kibsu_lines:,} / {kibsu_files} / {tests_lines:,} / {cases}".format(**truth))

    if args.check:
        sys.stderr.write("refresh_readme_counts: README is stale. "
                         "Run without --check to refresh it.\n")
        return 1

    new_text, changed = refresh(text, truth)
    if changed:
        # newline="" so the file's existing line endings survive the rewrite untouched.
        with io.open(args.path, "w", encoding="utf-8", newline="") as fh:
            fh.write(new_text)
        print("refreshed %s" % os.path.basename(args.path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
