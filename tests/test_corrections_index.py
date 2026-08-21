#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CORRECTIONS.md's index is now structural, because prose could not hold it.

The file opens by promising "every published number this project has had to correct, in one
place, newest first". For nine days it did not deliver one. Commit aef3b34 added the
2026-08-07 round by writing its heading OVER the previous round's heading instead of above
it - the diffstat reads +64/-1, and the single deletion was the line
`## 2026-07-31 - five scorer bugs (kibsu 0.2.0, scorer 0.5.0)`. The 0.2.0 round's body
survived byte-identical but became unindexed: it sat inside the 2026-08-07 section, so a
reader scanning the `## ` headings saw three rounds where there were four, and never saw the
round that moved published survey figures (in-scope mandated artifacts 103 -> 134, phantom
artifacts 44 -> 56). It was restored by hand in a035b11; this guard is why it cannot happen
a second time.

The invariant was already asserted in prose - audit.py's module docstring says a re-measure
"is indexed in CORRECTIONS.md like every round before it" - and nothing checked it. That is
precisely the failure this project measures in other people's instruction files, so the
claim gets a checker rather than another sentence.

THE LOAD-BEARING CHECK IS THE THIRD ONE. Heading shape and newest-first ordering would both
have passed the broken file: the surviving headings were well-formed and correctly ordered.
What gives a swallowed round away is that its section then carries TWO "**What moved**"
tables, because each re-measure round publishes exactly one. A round with no such table (the
two 2026-07-29 README notes) is fine; the rule is at most one per section, never at least
one, so a future round that moves no numbers is not forced to invent a table.

Per CONTRIBUTING rule 4 every check here has a negative control: each drives
`index_problems` to a finding, and the swallowed-round control reproduces aef3b34 exactly by
deleting that same heading line from the live text."""
import datetime
import io
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from support import PACKAGE_ROOT

EM_DASH = "—"
HEADING_RE = re.compile(r"^## (\d{4}-\d{2}-\d{2}) " + EM_DASH + r" \S")
MOVED_MARKER = "**What moved**"


def corrections_text():
    with io.open(os.path.join(PACKAGE_ROOT, "CORRECTIONS.md"), encoding="utf-8") as fh:
        return fh.read()


def index_problems(text):
    """Every structural promise CORRECTIONS.md's opening line makes, checked. Returns a list
    of human-readable findings - empty when the ledger keeps all of them."""
    problems = []
    lines = text.splitlines()
    headings = [(n, line) for n, line in enumerate(lines, 1) if line.startswith("## ")]

    if not headings:
        return ["no '## ' round headings at all - the ledger indexes nothing"]

    dated = []
    for n, line in headings:
        match = HEADING_RE.match(line)
        if not match:
            problems.append(
                "line %d: heading is not '## YYYY-MM-DD %s <description>': %r"
                % (n, EM_DASH, line))
            continue
        try:
            stamp = datetime.datetime.strptime(match.group(1), "%Y-%m-%d").date()
        except ValueError:
            problems.append("line %d: %r is not a real calendar date" % (n, match.group(1)))
            continue
        dated.append((n, stamp))

    for (first_n, first_date), (next_n, next_date) in zip(dated, dated[1:]):
        if first_date < next_date:
            problems.append(
                "lines %d/%d: %s is listed above %s, but the file promises newest first"
                % (first_n, next_n, first_date, next_date))

    starts = [n for n, _ in headings]
    bounds = starts[1:] + [len(lines) + 1]
    for (n, line), end in zip(headings, bounds):
        body = lines[n:end - 1]
        moved = [j for j, text_line in enumerate(body, n + 1)
                 if text_line.startswith(MOVED_MARKER)]
        if len(moved) > 1:
            problems.append(
                "the section at line %d (%s) carries %d %s tables (lines %s) - two "
                "re-measure rounds under one heading means a round lost its own heading, "
                "which is how aef3b34 unindexed the 0.2.0 round"
                % (n, line[3:].strip(), len(moved), MOVED_MARKER,
                   ", ".join(str(j) for j in moved)))

    return problems


def without_heading(text, prefix):
    """The live text with one round heading deleted - aef3b34's regression, reproduced."""
    lines = text.splitlines()
    kept = [line for line in lines if not line.startswith(prefix)]
    if len(kept) != len(lines) - 1:
        raise AssertionError("expected exactly one heading starting %r" % prefix)
    return "\n".join(kept)


class CorrectionsIndexTests(unittest.TestCase):
    def test_live_ledger_keeps_every_index_promise(self):
        self.assertEqual([], index_problems(corrections_text()))

    def test_every_round_body_is_reachable_from_a_heading(self):
        """No prose above the first heading except the file's own preamble - a round cannot
        hide before the index starts."""
        text = corrections_text()
        head, _, _ = text.partition("\n## ")
        self.assertNotIn(MOVED_MARKER, head,
                         "a '%s' table appears before the first '## ' heading" % MOVED_MARKER)

    # --- negative controls (CONTRIBUTING rule 4) --------------------------------------

    def test_negative_control_swallowed_round_is_caught(self):
        """aef3b34 itself: delete the 2026-07-31 heading and the guard must object."""
        broken = without_heading(corrections_text(), "## 2026-07-31 ")
        found = index_problems(broken)
        self.assertTrue(found, "deleting a round heading produced no finding")
        self.assertTrue(any(MOVED_MARKER in problem for problem in found),
                        "expected the two-tables-one-heading finding, got: %r" % found)

    def test_negative_control_out_of_order_is_caught(self):
        """Oldest-first is the other way the promise breaks."""
        text = corrections_text()
        reversed_dates = text.replace("## 2026-08-07 ", "## 2026-07-30 ", 1)
        found = index_problems(reversed_dates)
        self.assertTrue(any("newest first" in problem for problem in found),
                        "out-of-order headings were not caught: %r" % found)

    def test_negative_control_malformed_heading_is_caught(self):
        """A hyphen where the em dash belongs, and an undated heading."""
        text = corrections_text()
        hyphenated = text.replace("## 2026-08-07 " + EM_DASH + " ", "## 2026-08-07 - ", 1)
        self.assertTrue(any("is not '## YYYY-MM-DD" in p for p in index_problems(hyphenated)),
                        "a hyphenated heading was accepted")
        undated = text.replace("## 2026-08-07 " + EM_DASH + " ", "## the scorer round ", 1)
        self.assertTrue(any("is not '## YYYY-MM-DD" in p for p in index_problems(undated)),
                        "an undated heading was accepted")

    def test_negative_control_impossible_date_is_caught(self):
        """A well-shaped heading can still carry a date that does not exist."""
        text = corrections_text().replace("## 2026-08-07 ", "## 2026-02-30 ", 1)
        self.assertTrue(any("real calendar date" in problem for problem in index_problems(text)),
                        "2026-02-30 was accepted as a date")

    def test_negative_control_empty_ledger_is_caught(self):
        self.assertEqual(["no '## ' round headings at all - the ledger indexes nothing"],
                         index_problems("# Corrections\n\nnothing here yet.\n"))


if __name__ == "__main__":
    unittest.main()
