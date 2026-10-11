#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The unit is the sentence, not the line (scorer 0.11.0).

Through 0.10.0 the scorer judged physical lines. A sentence hard-wrapped over three lines was
scored once for every line that carried a directive word, and a line holding three sentences
was scored once. So the score depended on where an editor broke lines: re-wrapping the same
text at 60 or at 100 columns moved 468 of the 699 procedure files in the largest surveyed
collection, and one twelve-file collection read 7.4%, 3.8% and 5.6% at three wrap widths.

The property that replaces all of that, and the acceptance test of this round:

    RE-WRAPPING A DOCUMENT CHANGES NOTHING.

Not the instruction count, not the checkable count, not the genre, not the text of a single
unit. It is tested here on fixtures at four widths, and it was run over every file of the
ten pinned survey repositories before the round was frozen.

How it is achieved - normalise first: the wrapped lines of a paragraph, list item or
blockquote are joined (a line break inside a block is whitespace, which is what Markdown
says), and everything is computed from that. Then a block is cut into sentences. A
tick-box item is not cut: one box is one promise.

Per CONTRIBUTING rule 4 the property test has a control: the same fixtures, counted by a
crude line unit, DO move between wraps - so a pass here is not a fixture that could not have
failed."""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from support import PACKAGE_ROOT

sys.path.insert(0, PACKAGE_ROOT)
from kibsu import audit  # noqa: E402 -- must follow the sys.path.insert above

OPENS_BLOCK = re.compile(r"^(?:[-*+]\s|\d+[.)]\s|#|\||>|<[/!a-zA-Z]|```|~~~|\[[ xX]?\]?)")
# A line that so far holds only a list / quote / tick-box marker. Breaking there would leave
# the marker alone on its line, which Markdown reads as an empty item followed by a paragraph.
MARKER_ONLY = re.compile(r"^\s*(?:(?:[-*+]|\d+[.)]|>)\s*)?(?:\[(?:[ xX]\]?)?)?\s*$")

PROCEDURE_DOC = (
    "---\n"
    "genre: procedure\n"
    "---\n"
    "# Release\n"
    "\n"
    "Do not start the release until the suite has actually been run and its exit code read. "
    "A plan is not approval. Never soften a checker to make an unclear phase pass.\n"
    "\n"
    "- Run `python -m unittest discover -s tests` and read the exit code, not the text. "
    "Then write the result to `docs/release-notes.md`.\n"
    "- [ ] Confirm the changelog entry names every change. It must also credit contributors.\n"
    "- You must keep the team informed, e.g. by posting in the channel. Always say what is left.\n"
    "\n"
    "> Always check the published artifact, not the workflow that built it. "
    "The workflow can be green while the artifact is wrong.\n"
    "\n"
    "| step | rule |\n"
    "|---|---|\n"
    "| Tag | Never tag before the merge commit exists |\n"
    "\n"
    "```bash\n"
    "git tag -a v1.0.0 -m release. Then push it. Never do this by hand.\n"
    "```\n"
    "\n"
    "Open `README.md. Then` is a file name, not two sentences. See docs/a.md for more detail.\n"
)

UNDECLARED_DOC = (
    "# How we think here\n"
    "\n"
    "Name the hidden assumption before you build anything. When the premise conflicts with the "
    "evidence, say so plainly and show the evidence. Prefer the simpler reading unless the "
    "difference is material.\n"
    "\n"
    "1. First restate what was asked in your own words, in one or two lines at most.\n"
    "2. Then name the assumption you are making where the request was open.\n"
    "3. Finally say what you will do first, and do it without waiting.\n"
    "\n"
    "You should always land on a recommendation. Options are a fact; a recommendation with its "
    "reason and its trade-off is thinking. Never present a menu and make the reader choose "
    "blind, and do not ask a question the documents already answer. You must check a claim "
    "against the source before you build on it.\n"
)

DOCS = {"procedure": PROCEDURE_DOC, "undeclared": UNDECLARED_DOC}
WIDTHS = (24, 40, 72, 100000)


def rewrap(text, width):
    """Hard-wrap every paragraph, list item and quote at `width`. A break that would make the
    continuation line open a new Markdown block (it would start with '- ', '1. ', '#', '|',
    '>') is refused - that is the one wrap Markdown itself does not survive."""
    body, _fm = audit.strip_frontmatter(text)
    stripped = text.lstrip("﻿")
    prefix = stripped[:len(stripped) - len(body)]
    out, run = [], []
    in_fence, fence_char, fence_len = False, "", 0

    def flush():
        for kind, pieces in audit.iter_blocks(run):
            if kind in ("single", "rule"):
                out.append(pieces[0][1])
                continue
            lines, cur = [], ""
            for word in audit.block_text(pieces).split():
                opens = (OPENS_BLOCK.match(word + " ") or word in "-*+"
                         or re.match(r"^\d+[.)]$", word))
                if (cur and len(cur) + 1 + len(word) > width and not opens
                        and not MARKER_ONLY.match(cur)):
                    lines.append(cur)
                    cur = word
                else:
                    cur = word if not cur else cur + " " + word
            lines.append(cur)
            out.extend(lines)
        del run[:]

    for number, line in enumerate(body.split("\n"), 1):
        fence = audit.FENCE_RE.match(line)
        if fence:
            marks, rest = fence.group(1), fence.group(2)
            if in_fence:
                if marks[0] == fence_char and len(marks) >= fence_len and not rest.strip():
                    in_fence = False
            else:
                in_fence, fence_char, fence_len = True, marks[0], len(marks)
            flush()
            out.append(line)
        elif in_fence:
            out.append(line)
        elif line.lstrip().startswith("#") or not line.strip():
            flush()
            out.append(line)
        else:
            run.append((number, line))
    flush()
    return prefix + "\n".join(out)


def signature(text):
    """Everything about a document that re-wrapping must not be able to change."""
    r = audit.analyse(text, keep_lines=True)
    return {"instructions": r["instructions"], "checkable": r["checkable"],
            "claimable": r["claimable"], "genre": r["genre"],
            "genre_scores": r["genre_scores"], "logical_lines": r["logical_lines"],
            "mandated": sorted(m["tok"] for m in r["mandated"]),
            # Text compared with its spacing collapsed: a run of two spaces that lands on a
            # line break is one space after the join, and that is the wrapper, not the scorer.
            "units": [(" ".join(rec["text"].split()), rec["verdict"], rec["why"])
                      for rec in r["line_records"]]}


def directive_lines(text):
    """A crude LINE unit: physical lines carrying a directive word. The control."""
    return len([ln for ln in text.split("\n") if audit.MODALS.search(ln)])


class RewrapInvarianceTests(unittest.TestCase):
    def test_rewrapping_a_document_changes_nothing(self):
        for name, doc in DOCS.items():
            base = signature(doc)
            self.assertGreater(base["instructions"], 3, "fixture %r measures too little" % name)
            for width in WIDTHS:
                self.assertEqual(signature(rewrap(doc, width)), base,
                                 "%s re-wrapped at %d" % (name, width))

    def test_negative_control_a_line_unit_does_move_on_these_fixtures(self):
        """If the fixtures could not expose a line unit, the test above would prove nothing."""
        for name, doc in DOCS.items():
            counts = {directive_lines(rewrap(doc, width)) for width in WIDTHS}
            self.assertGreater(len(counts), 1, "%s: a line unit reads the same at every "
                                               "width, so this fixture cannot fail" % name)

    def test_the_rewrapper_really_changes_the_line_structure(self):
        for doc in DOCS.values():
            lengths = {len(rewrap(doc, width).split("\n")) for width in WIDTHS}
            self.assertGreater(len(lengths), 2)

    def test_a_document_already_in_normal_form_is_its_own_normal_form(self):
        """Blocks of one line each: joining has nothing to join, and the logical line count
        is the physical one - the reading is the line-by-line reading it always was."""
        doc = "# T\n\n- Run `python build.py`.\n- You must tell the team.\n\nAlways check.\n"
        r = audit.analyse(doc)
        self.assertEqual(r["logical_lines"], r["lines"])
        self.assertEqual((r["instructions"], r["checkable"]), (3, 1))


class SentenceTests(unittest.TestCase):
    def _sentences(self, text):
        return [text[a:b].strip() for a, b in audit.split_sentences(text)]

    def test_boundaries(self):
        cases = {
            "Do this. Then do that.": ["Do this.", "Then do that."],
            "Never skip it! Run the tests. Is it green? Check.":
                ["Never skip it!", "Run the tests.", "Is it green?", "Check."],
            "**Note:** Always do X. **Warning:** Never do Y.":
                ["**Note:** Always do X.", "**Warning:** Never do Y."],
            "Run it first. `git status` shows the result.":
                ["Run it first.", "`git status` shows the result."],
            'He said "stop." Then he left.': ['He said "stop."', "Then he left."],
            "Do X (see the guide). Then do Z.": ["Do X (see the guide).", "Then do Z."],
            # A lone capital is a label, not an initial; a chain of them ("J. K.") is a name.
            "Choose option A. Then run it.": ["Choose option A.", "Then run it."],
        }
        for text, expected in cases.items():
            self.assertEqual(self._sentences(text), expected, text)

    def test_negative_control_what_is_not_a_boundary(self):
        """Each of these has a full stop that a naive splitter would cut at."""
        whole = (
            "Open `README.md. Then` carefully.",            # inside a code span
            "See docs/a.md for more detail.",                # a file name, lowercase follows
            "Use a flag, e.g. Verbose mode, when stuck.",    # abbreviation
            "Compare A vs. B before choosing.",              # abbreviation
            "Version 0.9.0 is the first with the command.",  # a number, lowercase follows
            "Ask J. K. Rowling about it.",                   # initials
            "Wait... then continue.",                        # lowercase follows
        )
        for text in whole:
            self.assertEqual(self._sentences(text), [text], text)


class BlockTests(unittest.TestCase):
    def _units(self, body):
        r = audit.analyse(body, keep_lines=True)
        return [(rec["line"], rec["end_line"], rec["text"]) for rec in r["line_records"]]

    def test_a_wrapped_sentence_is_one_unit_at_the_line_it_starts_on(self):
        doc = ("---\ngenre: procedure\n---\n# T\n\n"
               "Do not leave the index stale after an\n"
               "edit. You must rebuild it\n"
               "yourself, every time.\n")
        self.assertEqual(self._units(doc), [
            (6, 7, "Do not leave the index stale after an edit."),
            (7, 8, "You must rebuild it yourself, every time."),
        ])

    def test_a_list_item_takes_its_continuation_lines_and_the_next_item_starts_a_new_one(self):
        doc = ("# T\n\n"
               "- You must run the\n  whole suite.\n"
               "- Never pipe a\ngate command.\n")
        self.assertEqual(self._units(doc), [
            (3, 4, "- You must run the whole suite."),
            (5, 6, "- Never pipe a gate command."),
        ])

    def test_a_tick_box_item_is_one_unit_however_many_sentences_it_holds(self):
        doc = "# T\n\n- [ ] Confirm the build. It must\n  be ready. Never skip this.\n"
        r = audit.analyse(doc, keep_lines=True)
        self.assertEqual([(rec["line"], rec["end_line"], rec["why"]) for rec in r["line_records"]],
                         [(3, 4, ["tick-box"])])
        self.assertEqual((r["instructions"], r["checkable"]), (1, 1))

    def test_table_rows_stand_alone_and_are_never_joined(self):
        doc = "# T\n\n| a | b |\n|---|---|\n| Never tag early | x |\n| Always verify | y |\n"
        self.assertEqual([u[2] for u in self._units(doc)],
                         ["| Never tag early | x |", "| Always verify | y |"])

    def test_a_blockquote_joins_like_a_paragraph(self):
        doc = "# T\n\n> Always check the artifact,\n> not the workflow. Never\n> trust a tick.\n"
        self.assertEqual(self._units(doc), [
            (3, 4, "> Always check the artifact, not the workflow."),
            (4, 5, "Never trust a tick."),
        ])

    def test_fenced_text_is_never_a_unit(self):
        doc = "# T\n\n```\nNever do this. Always do that.\n```\n\nYou must read it.\n"
        self.assertEqual([u[2] for u in self._units(doc)], ["You must read it."])

    def test_a_heading_or_a_blank_line_ends_the_block(self):
        doc = "# T\n\nYou must do the first thing\n## Next\nyou must do the second thing\n"
        self.assertEqual([u[2] for u in self._units(doc)],
                         ["You must do the first thing", "you must do the second thing"])

    def test_negative_control_unpunctuated_lines_in_one_block_are_one_unit(self):
        """Disclosed, not hidden: with no blank line, list marker or sentence punctuation
        between them, two lines are one block - exactly as Markdown renders them. Telling
        them apart would need the line break, and the line break is what must not matter."""
        doc = "# T\n\nYou must run the tests\nNever commit on red\n"
        self.assertEqual([u[2] for u in self._units(doc)],
                         ["You must run the tests Never commit on red"])


class MandateUnitTests(unittest.TestCase):
    def _mandated(self, doc):
        return sorted(m["tok"] for m in audit.analyse(doc)["mandated"])

    def test_a_mandate_wrapped_across_two_lines_is_found(self):
        """Verb on one line, file on the next: invisible to a line unit."""
        doc = "# T\n\n- You must write the summary to\n  `docs/summary.md` before you stop.\n"
        self.assertEqual(self._mandated(doc), ["docs/summary.md"])

    def test_negative_control_a_verb_and_a_file_in_different_sentences_are_not_a_mandate(self):
        """One physical line used to be enough for the two to count as one promise. A scraped
        page pasted on a single line "mandated" a file named a hundred kilobytes after the
        verb."""
        doc = "# T\n\nCreate a plan first. Nobody has ever read `docs/old-notes.md` since.\n"
        self.assertEqual(self._mandated(doc), [])


if __name__ == "__main__":
    unittest.main()
