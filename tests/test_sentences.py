#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""What is counted is the sentence, not the line (scorer 0.11.0).

Through 0.10.0 the scorer judged physical lines. A sentence hard-wrapped over three lines was
scored once for every line that carried a directive word, and a line holding three sentences
was scored once. So the score depended on where an editor broke lines: re-wrapping the same
text at 60 or at 100 columns moved 468 of the 699 procedure files in the largest surveyed
collection, and one twelve-file collection read 7.4%, 3.8% and 5.6% at three wrap widths.

The property that replaces all of that, and the acceptance test of this round:

    RE-WRAPPING A DOCUMENT CHANGES NOTHING.

Not the instruction count, not the checkable count, not the genre, not the mandated files,
not the text of a single counted sentence. "Re-wrapping" means what a Markdown renderer
means by it: a soft line break moved, added or removed, such that the page renders the same.
A hard break is not one (it is a sentence boundary), and in two named places the scorer reads
the file as its reader does rather than as a renderer would - see BlockTests, the two tests
marked DELIBERATE.

HOW THIS FILE TESTS IT, AND WHY IT IS BUILT THIS WAY
The first draft of the reader passed a property test and was wrong. That test re-wrapped
documents with a helper that asked the SCORER which lines formed a block - so it could only
ever try the wraps the scorer already understood, and it never put a line break in front of
`<path>`, `[x]`, `2024.`, `#12` or `|`. An adversarial pass with a real CommonMark parser as
its oracle did, and found six places where the reader was looser than the renderer; each was
a re-wrap that changed a count.

So nothing here parses Markdown to decide how to wrap it. A fixture is DESCRIBED - "a
paragraph with this text", "a list item with this marker and this text" - and render() lays
it out at a width and a hanging indent. The only breaks it refuses are the ones CommonMark
itself says would start a new block (a continuation line opening with a bullet, `> `, `# `,
a fence, a list numbered 1, a block-level HTML tag - and on a LAZY line, written outside the
list item or quote it continues, a list of any number). Four columns past the text of its
container, a line can open nothing, so there nothing is refused. Every other token is fair
game, and test_the_wraps_really_put_awkward_tokens_at_line_starts proves the awkward ones do
land at the start of a line - otherwise a pass would mean only that the hard cases were never
tried.

Until scorer 0.12.0 the helper also refused any number at the start of a list item's
continuation line. CommonMark refuses only a lazy one, so the helper never tried the wraps
that broke the reader there (issue #113): "Always read step 2. Then decide." was read as an
item numbered 2. The refusal now matches CommonMark's, and nothing more.

Per CONTRIBUTING rule 4 the property has a control: the same fixtures, counted by a crude
line count, DO move between wraps."""
import os
import re
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from support import PACKAGE_ROOT

sys.path.insert(0, PACKAGE_ROOT)
from kibsu import audit  # noqa: E402 -- must follow the sys.path.insert above

# What CommonMark lets interrupt a paragraph when it opens a continuation line.
STARTS_BLOCK = re.compile(r"^(?:[-+*]$|>|#{1,6}$|```|~~~|1[.)]$|</?(?:div|p|pre|details|summary|table|ul|ol|li)\b)", re.I)
ANY_NUMBER_MARKER = re.compile(r"^\d+[.)]$")

RELEASE = [
    ("heading", "# Release"),
    ("blank",),
    ("para", "Do not start the release until the suite has actually been run and its exit "
             "code read. A plan is not approval. Never soften a checker to make an unclear "
             "phase pass. Pass the path as <path> and never as a relative name. Mark the item "
             "[x] when it is done and never before. Never reuse the schema from 2024. Then "
             "update the docs. Always list the codes (#REF!, #DIV/0!, #N/A) in the report. "
             "You must use a | b as the separator, e.g. Foo | Bar. You must copy the file "
             "to C:\\\\ and never delete the source file."),
    ("blank",),
    ("para", "| Never skip this step, and always read the log before you tag."),
    ("blank",),
    ("item", "- ", "Run `python -m unittest discover -s tests` and read the exit code, not "
                   "the text. Then write the result to `docs/release-notes.md`."),
    ("item", "- ", "Never reuse the schema from 2024. Then run the build + test steps and "
                   "never skip them."),
    ("blank",),
    ("listpara", "You must run the whole suite and never skip the slow tests, even when the "
                 "change looks small. Always read step 2. Then decide."),
    ("blank",),
    ("box", "- [ ] ", "Confirm the changelog entry names every change. It must also credit "
                      "contributors."),
    ("item", "1. ", "You must keep the team informed, e.g. by posting in the channel. "
                    "Always say what is left."),
    ("item", "2. ", "Never tag before the merge commit exists. Choose option A. Then push."),
    ("blank",),
    ("quote", "Always check the published artifact, not the workflow that built it. The "
              "workflow can be green while the artifact is wrong. Read step 3. Then decide."),
    ("blank",),
    ("rows", ["| step | rule |", "|---|---|", "| Tag | Never tag before the merge commit |"]),
    ("blank",),
    ("fence", ["```bash", "git tag -a v1.0.0 -m release. Then push it. Never do this by hand.",
               "```"]),
    ("blank",),
    ("para", "Open `README.md. Then` is a file name, not two sentences. See docs/a.md for "
             "more detail. You should never trust a tick."),
]

THINKING = [
    ("heading", "# How we think here"),
    ("blank",),
    ("para", "Name the hidden assumption before you build anything. When the premise "
             "conflicts with the evidence, say so plainly and show the evidence. Prefer the "
             "simpler reading unless the difference is material."),
    ("blank",),
    ("item", "1. ", "First restate what was asked in your own words, in one or two lines."),
    ("item", "2. ", "Then name the assumption you are making where the request was open."),
    ("item", "3. ", "Finally say what you will do first, and do it without waiting."),
    ("blank",),
    ("para", "You should always land on a recommendation. Options are a fact; a "
             "recommendation with its reason and its trade-off is thinking. Never present a "
             "menu and make the reader choose blind, and do not ask a question the documents "
             "already answer. You must check a claim against the source before you build on "
             "it."),
]

FIXTURES = {"release": (["---", "genre: procedure", "---"], RELEASE),
            "thinking": ([], THINKING)}
WIDTHS = list(range(14, 96, 3)) + [10 ** 6]
HANGS = (0, 2, 4, 7)


def wrap(text, width, first, rest, deep=False, lazy=False):
    """Greedy wrap of one block's text. `first` prefixes the first line, `rest` every
    continuation line. A break is refused only where CommonMark would read the continuation
    line as the start of a new block.

    deep    the continuation lines sit four or more columns past the text of their container,
            where nothing can open: every break is allowed.
    lazy    they sit outside their container (a list item's or a quote's line written flush
            left). The paragraph is not what the line is tested against there, so ANY number
            opens a list: flush under "- schema from", "2024. Then" is an item numbered 2024."""
    lines, cur = [], first
    words = text.split()
    for n, word in enumerate(words):
        if n == 0:
            cur += word
            continue
        opens = STARTS_BLOCK.match(word) or (lazy and ANY_NUMBER_MARKER.match(word))
        if deep:
            opens = None
        if len(cur) + 1 + len(word) > width and not opens:
            lines.append(cur)
            cur = rest + word
        else:
            cur += " " + word
    lines.append(cur)
    return lines


def render(frontmatter, blocks, width, hang):
    out = list(frontmatter)
    for block in blocks:
        kind = block[0]
        if kind == "blank":
            out.append("")
        elif kind == "heading":
            out.append(block[1])
        elif kind == "para":
            out.extend(wrap(block[1], width, "", " " * hang, deep=hang >= 4))
        elif kind in ("item", "box"):
            marker, text = block[1], block[2]
            # Lazy at hang 0; aligned with the text at 2; two and five columns past it at 4
            # and 7. The item's text starts after the list marker - for "- [ ] " that is
            # column 2, so an aligned tick-box line is already four columns past it.
            content = len(re.match(r"\s*(?:[-+*]|\d+[.)])\s+", marker).group(0))
            rest = " " * (len(marker) + hang - 2) if hang else ""
            out.extend(wrap(text, width, marker, rest,
                            deep=bool(hang) and len(rest) - content >= 4, lazy=not hang))
        elif kind == "listpara":                                # under "- ": two columns in
            out.extend(wrap(block[1], width, "    ", "    "))
        elif kind == "quote":
            out.extend(wrap(block[1], width, "> ", "> " if hang else "", lazy=not hang))
        else:                                                    # rows, fence: never wrapped
            out.extend(block[1])
    return "\n".join(out) + "\n"


def signature(text):
    """Everything about a document that re-wrapping must not be able to change."""
    r = audit.analyse(text, keep_lines=True)
    return {"instructions": r["instructions"], "checkable": r["checkable"],
            "claimable": r["claimable"], "genre": r["genre"],
            "genre_scores": r["genre_scores"], "logical_lines": r["logical_lines"],
            "steps": r["steps"], "seq": r["seq"], "checkboxes": r["checkboxes"],
            "tables": r["tables"], "fences": r["fences"],
            "mandated": sorted(m["tok"] for m in r["mandated"]),
            "sentences": [(rec["text"], rec["verdict"], rec["why"]) for rec in r["line_records"]]}


def directive_lines(text):
    """A crude LINE count: physical lines carrying a directive word. The control."""
    return len([ln for ln in text.split("\n") if audit.MODALS.search(ln)])


class RewrapInvarianceTests(unittest.TestCase):
    def test_rewrapping_a_document_changes_nothing(self):
        for name, (front, blocks) in FIXTURES.items():
            base = signature(render(front, blocks, 10 ** 6, 0))
            self.assertGreaterEqual(base["instructions"], 5,
                                    "fixture %r measures too little" % name)
            for width in WIDTHS:
                for hang in HANGS:
                    doc = render(front, blocks, width, hang)
                    self.assertEqual(signature(doc), base,
                                     "%s at width %d, hang %d:\n%s" % (name, width, hang, doc))

    def test_the_wraps_really_put_awkward_tokens_at_line_starts(self):
        """Each of these, opening a continuation line, was read as a new block by the first
        draft. If no wrap here ever placed one there, the property test tried nothing hard."""
        front, blocks = FIXTURES["release"]
        seen = set()
        for width in WIDTHS:
            for hang in HANGS:
                for line in render(front, blocks, width, hang).split("\n"):
                    first = line.strip().split(" ")[0] if line.strip() else ""
                    for token in ("<path>", "[x]", "2024.", "(#REF!,", "#DIV/0!,", "|", "2."):
                        if first == token:
                            seen.add(token)
        self.assertEqual(seen, {"<path>", "[x]", "2024.", "(#REF!,", "#DIV/0!,", "|", "2."})

    def test_the_wraps_really_reach_the_shapes_of_issue_113(self):
        """The five places scorer 0.11.0 still moved a count. Each is a line the old helper
        never produced, or a line end it never produced. If none of them appears, the
        property test above passes for want of trying."""
        front, blocks = FIXTURES["release"]
        reached = set()
        for width in WIDTHS:
            for hang in HANGS:
                lines = render(front, blocks, width, hang).split("\n")
                for n, line in enumerate(lines):
                    nxt = lines[n + 1] if n + 1 < len(lines) else ""
                    if line.startswith("  ") and line.lstrip().startswith("2024. "):
                        reached.add("a number inside a list item")
                    if line.startswith("    ") and line.lstrip().startswith("2. "):
                        reached.add("a number inside a list paragraph")
                    if line.endswith("C:\\\\"):
                        reached.add("an escaped backslash at a line end")
                    if line.startswith("      ") and line.lstrip().startswith("+ "):
                        reached.add("a bullet four columns past an item's text")
                    if line.startswith("| Never") and nxt and not nxt.startswith("|"):
                        reached.add("a pipe-led line with prose under it")
        self.assertEqual(reached, {"a number inside a list item",
                                   "a number inside a list paragraph",
                                   "an escaped backslash at a line end",
                                   "a bullet four columns past an item's text",
                                   "a pipe-led line with prose under it"})

    def test_negative_control_a_line_count_does_move_on_these_fixtures(self):
        """If the fixtures could not expose a line count, the test above would prove nothing."""
        for name, (front, blocks) in FIXTURES.items():
            counts = {directive_lines(render(front, blocks, width, 0)) for width in WIDTHS}
            self.assertGreater(len(counts), 2, "%s: a line count reads the same at every "
                                               "width, so this fixture cannot fail" % name)

    def test_a_document_already_in_normal_form_is_its_own_normal_form(self):
        """Blocks of one line each: joining has nothing to join, and the logical line count
        is the physical one - the reading is the line-by-line reading it always was."""
        doc = "# T\n\n- Run `python build.py`.\n- You must tell the team.\n\nAlways check.\n"
        r = audit.analyse(doc)
        self.assertEqual(r["logical_lines"], r["lines"])
        self.assertEqual((r["instructions"], r["checkable"]), (3, 1))

    def test_a_wrapped_frontmatter_scalar_reads_as_yaml_reads_it(self):
        """YAML folds a continuation line into the value. The persona test has to as well."""
        body = "\n# T\n\nYou must run it.\n"
        one = "---\nname: x\ndescription: A senior engineer with ten years of experience.\n---\n"
        two = "---\nname: x\ndescription: A senior engineer with ten years of\n  experience.\n---\n"
        a, b = audit.analyse(one + body), audit.analyse(two + body)
        self.assertGreater(a["persona_hits"], 0)
        self.assertEqual((a["persona_hits"], a["genre"]), (b["persona_hits"], b["genre"]))


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
            "He said \u201cstop.\u201d Then he left.": ["He said \u201cstop.\u201d", "Then he left."],
            "Do X (see the guide). Then do Z.": ["Do X (see the guide).", "Then do Z."],
            # A lone capital is a label, not an initial; a chain of them ("J. K.") is a name.
            "Choose option A. Then run it.": ["Choose option A.", "Then run it."],
            # "etc." was on the abbreviation list and swallowed real sentence ends.
            "Install Slack, Teams, etc. Run the setup script.":
                ["Install Slack, Teams, etc.", "Run the setup script."],
            # The tail of "47ms" is not the title "Ms."
            "Latency fell to 47ms. Increase the cache next.":
                ["Latency fell to 47ms.", "Increase the cache next."],
            "Answer yes or no. Then run it.": ["Answer yes or no.", "Then run it."],
            "Check it\u2026 Then run it.": ["Check it\u2026", "Then run it."],
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
            "Ask J. K. Rowling about it.",                   # a chain of initials
            "Huang, N. E., et al. (1998) describe it.",      # initials and "et al."
            "Use the U.S. Army spec for this.",              # a dotted abbreviation
            "Ask Prof. Smith before you change it.",
            "Wait... then continue.",                        # lowercase follows
            "1. Run the tests first",                        # a list number is not a sentence
            "**3. Identify value thresholds**",              # nor is a bold one
            "- 10. Always check the result",
        )
        for text in whole:
            self.assertEqual(self._sentences(text), [text], text)

    def test_a_code_span_closes_at_a_run_of_the_same_length(self):
        self.assertEqual(audit.mask_code_spans("a `b. C` d ``e ` f. G`` h"),
                         "a " + "\x00" * 6 + " d " + "\x00" * 12 + " h")
        self.assertEqual(audit.mask_code_spans("no ` closing tick"), "no ` closing tick")


class BlockTests(unittest.TestCase):
    def _counted(self, body):
        r = audit.analyse(body, keep_lines=True)
        return [(rec["line"], rec["end_line"], rec["text"]) for rec in r["line_records"]]

    def _texts(self, body):
        return [u[2] for u in self._counted(body)]

    def test_a_wrapped_sentence_is_counted_once_at_the_line_it_starts_on(self):
        doc = ("---\ngenre: procedure\n---\n# T\n\n"
               "Do not leave the index stale after an\n"
               "edit. You must rebuild it\n"
               "yourself, every time.\n")
        self.assertEqual(self._counted(doc), [
            (6, 7, "Do not leave the index stale after an edit."),
            (7, 8, "You must rebuild it yourself, every time."),
        ])

    def test_a_list_item_takes_its_continuation_lines_and_the_next_item_starts_a_new_one(self):
        doc = ("# T\n\n"
               "- You must run the\n  whole suite.\n"
               "- Never pipe a\ngate command.\n")
        self.assertEqual(self._counted(doc), [
            (3, 4, "- You must run the whole suite."),
            (5, 6, "- Never pipe a gate command."),
        ])

    def test_a_second_paragraph_of_a_list_item_is_a_paragraph_not_code(self):
        """Indented four columns after a blank line, inside a list: the first draft (and
        0.10.0) read each line as indented code, each line counted on its own."""
        doc = "# T\n\n- Step one\n\n    You must run the tests\n    and never skip them.\n"
        self.assertEqual(self._counted(doc), [(5, 6, "You must run the tests and never skip them.")])

    def test_four_columns_of_indent_with_no_list_open_is_still_code(self):
        doc = "# T\n\nIntro.\n\n    You must run the tests\n    and never skip them.\n"
        self.assertEqual(self._texts(doc), ["You must run the tests", "and never skip them."])

    def test_a_tick_box_item_is_counted_once_however_many_sentences_it_holds(self):
        doc = "# T\n\n- [ ] Confirm the build. It must\n  be ready. Never skip this.\n"
        r = audit.analyse(doc, keep_lines=True)
        self.assertEqual([(rec["line"], rec["end_line"], rec["why"]) for rec in r["line_records"]],
                         [(3, 4, ["tick-box"])])
        self.assertEqual((r["instructions"], r["checkable"]), (1, 1))

    def test_negative_control_a_link_named_x_is_not_a_ticked_box(self):
        doc = "# T\n\n[X](https://x.com/a) is where you must post the news.\n"
        r = audit.analyse(doc, keep_lines=True)
        self.assertEqual(r["checkboxes"], 0)
        self.assertEqual([rec["why"] for rec in r["line_records"]], [[]])

    def test_a_tick_box_mentioned_mid_paragraph_is_a_mention(self):
        doc = "# T\n\nYou must mark the item\n[x] when it is done.\n"
        r = audit.analyse(doc, keep_lines=True)
        self.assertEqual(r["checkboxes"], 0)
        self.assertEqual(self._texts(doc), ["You must mark the item [x] when it is done."])

    def test_table_rows_stand_alone_and_are_never_joined(self):
        doc = "# T\n\n| a | b |\n|---|---|\n| Never tag early | x |\n| Always verify | y |\n"
        self.assertEqual(self._texts(doc), ["| Never tag early | x |", "| Always verify | y |"])

    def test_negative_control_a_pipe_under_a_paragraph_is_not_a_table(self):
        """A table needs its delimiter row. A wrapped line that merely opens with `|` is prose."""
        doc = "# T\n\nYou must use a\n| b as the separator.\n"
        self.assertEqual(self._texts(doc), ["You must use a | b as the separator."])

    def test_a_blockquote_is_read_like_the_text_it_quotes(self):
        doc = "# T\n\n> Always check the artifact,\n> not the workflow. Never\n> trust a tick.\n"
        self.assertEqual(self._counted(doc), [
            (3, 4, "Always check the artifact, not the workflow."),
            (4, 5, "Never trust a tick."),
        ])

    def test_a_fence_inside_a_blockquote_is_a_fence(self):
        doc = "# T\n\n> You must run:\n> ```bash\n> npm install -g x. Never skip it.\n> ```\n"
        r = audit.analyse(doc, keep_lines=True)
        self.assertEqual((r["fences"], r["runnable_fences"]), (1, 1))
        self.assertEqual(self._texts(doc), ["You must run:"])

    def test_a_tick_box_inside_a_blockquote_is_a_tick_box(self):
        doc = "# T\n\n> - [ ] Confirm the build. It must pass.\n> - [x] Run `make test`.\n"
        r = audit.analyse(doc, keep_lines=True)
        self.assertEqual(r["checkboxes"], 2)
        self.assertEqual([rec["why"][0] for rec in r["line_records"]], ["tick-box", "tick-box"])

    def test_fenced_text_is_never_counted(self):
        doc = "# T\n\n```\nNever do this. Always do that.\n```\n\nYou must read it.\n"
        self.assertEqual(self._texts(doc), ["You must read it."])

    def test_negative_control_three_backticks_around_a_word_are_a_code_span_not_a_fence(self):
        """The old reading opened a fence here and swallowed the rest of the document."""
        doc = "# T\n\n```foo``` is the name. You must keep it.\n\nNever rename it.\n"
        r = audit.analyse(doc, keep_lines=True)
        self.assertEqual(r["fences"], 0)
        self.assertEqual(self._texts(doc), ["You must keep it.", "Never rename it."])

    def test_a_heading_needs_its_space(self):
        """`#12` and `#REF!` are prose. Only `# ` opens a heading, as in CommonMark."""
        doc = "# T\n\nYou must cite issue\n#42 in the message. Never omit it.\n"
        self.assertEqual(self._texts(doc), ["You must cite issue #42 in the message.",
                                            "Never omit it."])

    def test_an_inline_tag_is_text_and_a_tag_alone_on_its_line_is_a_block(self):
        inline = "# T\n\nYou must pass the path as\n<path> and never as a relative name.\n"
        self.assertEqual(self._texts(inline),
                         ["You must pass the path as <path> and never as a relative name."])
        alone = "# T\n\n<important>\nYou must run the tests.\n</important>\n"
        self.assertEqual(self._texts(alone)[0], "You must run the tests. </important>")

    def test_only_a_list_numbered_one_interrupts_a_paragraph(self):
        para = "# T\n\nNever reuse the schema from\n2024. Then update the docs.\n"
        self.assertEqual(self._texts(para), ["Never reuse the schema from 2024."])
        listed = "# T\n\n1. You must run it.\n2. Never skip it.\n"
        self.assertEqual(self._texts(listed), ["1. You must run it.", "2. Never skip it."])

    def test_an_explicit_hard_break_is_a_boundary(self):
        doc = "# T\n\nYou must run the tests  \nNever commit on red\\\nAlways read the exit code\n"
        self.assertEqual(self._texts(doc), ["You must run the tests", "Never commit on red\\",
                                            "Always read the exit code"])

    def test_negative_control_a_soft_break_between_unpunctuated_lines_is_not(self):
        """Disclosed, not hidden: with no blank line, list marker, hard break or sentence
        punctuation between them, two lines are one block - exactly as Markdown renders
        them. Telling them apart would need the line break, and the line break is what must
        not matter."""
        doc = "# T\n\nYou must run the tests\nNever commit on red\n"
        self.assertEqual(self._texts(doc), ["You must run the tests Never commit on red"])

    def test_a_heading_or_a_blank_line_ends_the_block(self):
        doc = "# T\n\nYou must do the first thing\n## Next\nyou must do the second thing\n"
        self.assertEqual(self._texts(doc),
                         ["You must do the first thing", "you must do the second thing"])

    def test_a_long_frontmatter_closer_does_not_leak_a_dash_into_the_body(self):
        doc = "---\nname: x\n----\nYou must keep\nthis.\n"
        self.assertEqual(self._counted(doc), [(4, 5, "You must keep this.")])

    def test_a_deep_indented_line_that_leaves_a_quote_is_a_continuation(self):
        """Four columns in, a line cannot start a list, so it continues the quoted item above
        it - the last re-wrap the adversarial pass found that still moved a count."""
        lazy = "# T\n\n> - You must cite the paper\n    - never the preprint.\n"
        self.assertEqual(self._texts(lazy), ["- You must cite the paper - never the preprint."])
        flush = "# T\n\n> - You must cite the paper\n- never the preprint.\n"
        self.assertEqual(self._texts(flush), ["- You must cite the paper", "- never the preprint."])

    def test_a_quote_that_opens_under_a_paragraph_reads_as_it_would_alone(self):
        """A quote interrupts the paragraph above it, so what is quoted reads the same with or
        without that paragraph. Under scorer 0.11.0 (package 0.10.0), a quoted line four columns
        in was appended to the paragraph the quote had just closed: TypeError, and `audit`,
        `report` and `explain` lost the whole repository to one file."""
        quote = ">     make build\n> Never skip the build.\n"
        alone = self._texts("# T\n\n" + quote)
        self.assertEqual(alone, ["make build", "Never skip the build."])
        self.assertEqual(self._texts("# T\n\nYou must read the guide.\n" + quote),
                         ["You must read the guide."] + alone)

    def test_no_change_of_container_can_crash_the_reader(self):
        """Every opener x every quote depth x indents 0-6 x every kind of next line. The crash
        above was one cell of this grid; a reader that keeps a stale answer about which block
        is open fails here, not in a user's repository."""
        openers = ["Intro line", "- item", "1. item", "> quoted", ">> deep", "| a | b |", "    code"]
        prefixes = ["", ">", "> ", ">>", "> > "]
        bodies = ["x", "- x", "2. x", "```", "| a |", "[ ] x"]
        for opener in openers:
            for prefix in prefixes:
                for indent in range(7):
                    for body in bodies:
                        doc = "%s\n%s%s%s\n" % (opener, prefix, " " * indent, body)
                        with self.subTest(doc=doc):
                            audit.analyse(doc, keep_lines=True)

    # Issue #113: five places where a soft line break still moved a count under scorer
    # 0.11.0. In each pair the two documents are one document to CommonMark (markdown-it-py,
    # cmark-gfm and commonmark.py agree on every pair), so they must be one to the scorer.
    def _same(self, one_line, wrapped):
        a, b = audit.analyse(one_line, keep_lines=True), audit.analyse(wrapped, keep_lines=True)
        self.assertEqual([rec["text"] for rec in a["line_records"]],
                         [rec["text"] for rec in b["line_records"]])
        for key in ("instructions", "checkable", "steps", "seq", "tables", "logical_lines"):
            self.assertEqual(a[key], b[key], key)
        return a

    def test_a_number_inside_a_list_item_continues_it(self):
        """Only a list numbered 1 may interrupt a paragraph, and a list item's paragraph is a
        paragraph. Scorer 0.11.0 opened an item on any number under an item."""
        r = self._same("- Never reuse the schema from 2024. Then update the docs.\n",
                       "- Never reuse the schema from\n  2024. Then update the docs.\n")
        self.assertEqual((r["instructions"], r["steps"]), (1, 0))
        self._same("1. You must read step 2. Then decide.\n",
                   "1. You must read step\n   2. Then decide.\n")
        self._same("- Run it.\n\n    You must read step 2. Then decide.\n",
                   "- Run it.\n\n    You must read step\n    2. Then decide.\n")

    def test_negative_control_a_lazy_number_line_does_start_a_list(self):
        """Written flush left, the same line is outside the item, and there CommonMark lets
        any number start a list - so these are NOT re-wraps, and the counts differ."""
        one = audit.analyse("- Never reuse the schema from 2024. Then update the docs.\n")
        lazy = audit.analyse("- Never reuse the schema from\n2024. Then update the docs.\n")
        self.assertEqual((one["steps"], lazy["steps"]), (0, 1))
        quoted = audit.analyse("> Never reuse the schema from\n2024. Then update the docs.\n")
        self.assertEqual(quoted["steps"], 1)
        # And `1.`, the one number that may interrupt anything: ignoring it on a line that
        # leaves a quote survived the whole 0.11.0 suite (issue #113).
        quoted_one = audit.analyse("> Note the schema.\n1. Then update the docs.\n")
        self.assertEqual(quoted_one["steps"], 1)
        listed = "# T\n\n1. You must run it.\n2. Never skip it.\n"
        self.assertEqual(self._texts(listed), ["1. You must run it.", "2. Never skip it."])

    def test_an_escaped_backslash_at_a_line_end_is_not_a_hard_break(self):
        """`\\\\` is one backslash, escaped. Only an odd run of them ends in a hard break."""
        r = self._same("You must copy the file to C:\\\\ and then never delete the source.\n",
                       "You must copy the file to C:\\\\\nand then never delete the source.\n")
        self.assertEqual(r["instructions"], 1)
        odd = self._texts("# T\n\nYou must copy it to C:\\\\\\\nand never delete it.\n")
        self.assertEqual(len(odd), 2, "three backslashes: an escaped one, then a hard break")

    def test_a_bullet_four_columns_past_an_items_text_continues_it(self):
        """Four columns past the text of its item, a line is indented code to CommonMark,
        and indented code cannot interrupt a paragraph."""
        r = self._same("- You must run the build + test steps. Never skip them.\n",
                       "- You must run the build\n      + test steps. Never skip them.\n")
        self.assertEqual(r["instructions"], 2)
        self._same("- You must run the build ``` and the tests.\n",
                   "- You must run the build\n      ``` and the tests.\n")

    def test_negative_control_three_columns_past_an_items_text_is_a_sub_item(self):
        r = audit.analyse("- You must run the build\n     + test steps. Never skip them.\n",
                          keep_lines=True)
        self.assertEqual([rec["text"] for rec in r["line_records"]],
                         ["- You must run the build", "+ test steps.", "Never skip them."])

    def test_a_pipe_led_line_with_no_delimiter_row_is_prose(self):
        """A table needs its delimiter row - under a paragraph (the negative control above)
        and with nothing open alike. Scorer 0.11.0 read a lone `|`-led line as a table row
        and the line under it as a new paragraph."""
        r = self._same("| Never skip this step, and always read the log.\n",
                       "| Never skip this step,\nand always read the log.\n")
        self.assertEqual(r["instructions"], 1)

    def test_a_quote_inside_an_item_does_not_swallow_the_items_after_it(self):
        """A line that leaves a quote continues it lazily only if it would not open a block
        there, and outside a paragraph's own container any number opens a list. Scorer
        0.11.0 knew only `1.`, and swallowed every later step into the quote."""
        with_quote = audit.analyse("1. If:\n   > Note the version.\n2. Run `x --version`.\n"
                                   "3. Run `x init`.\n", keep_lines=True)
        without = audit.analyse("1. If:\n2. Run `x --version`.\n3. Run `x init`.\n")
        self.assertEqual((with_quote["steps"], without["steps"]), (3, 3))
        self.assertEqual([rec["text"] for rec in with_quote["line_records"]],
                         ["Note the version.", "2. Run `x --version`.", "3. Run `x init`."])

    def test_negative_control_prose_after_a_quote_still_continues_it(self):
        self.assertEqual(self._texts("# T\n\n> You must note the\nversion first.\n"),
                         ["You must note the version first."])

    def test_a_fence_under_a_tag_line_is_a_fence(self):
        """DELIBERATE, and not CommonMark: there, `<Good>` opens an HTML block that swallows
        the fence line, and the code after the first blank line turns into paragraphs. The
        agent reading the file sees a fence, so the scorer does too."""
        doc = ("# T\n\n<Good>\n```bash\nnpm test\n\nNever do this. Always do that.\n```\n</Good>\n\n"
               "You must read it.\n")
        r = audit.analyse(doc, keep_lines=True)
        self.assertEqual((r["fences"], r["runnable_fences"]), (1, 1))
        self.assertEqual(self._texts(doc), ["You must read it."])

    def test_a_table_with_a_ragged_delimiter_row_is_still_rows(self):
        """DELIBERATE, and not GFM: a delimiter row with more cells than the header makes the
        whole table a paragraph there. One table in 1,241 across the survey is written that
        way, and to its reader it is a table."""
        doc = "# T\n\n| a | b |\n|---|---|---|\n| Never tag early | x |\n| Always verify | y |\n"
        self.assertEqual(self._texts(doc), ["| Never tag early | x |", "| Always verify | y |"])

    def test_spacing_inside_a_block_does_not_change_what_matches(self):
        """"do  not" on one line and "do" / "not" on two are the same words."""
        a = audit.analyse("# T\n\nPlease do  not delete files.\n")
        b = audit.analyse("# T\n\nPlease do\nnot delete files.\n")
        self.assertEqual((a["instructions"], b["instructions"]), (1, 1))
        # The genre signals read the same joined text, and want one space too.
        c = audit.analyse("# T\n\nStop and ask the owner when in  doubt.\n")
        d = audit.analyse("# T\n\nStop and ask the owner when in\ndoubt.\n")
        self.assertEqual((c["doctrine_hits"], d["doctrine_hits"]), (1, 1))


class MandateSentenceTests(unittest.TestCase):
    def _mandated(self, doc):
        return sorted(m["tok"] for m in audit.analyse(doc)["mandated"])

    def test_a_mandate_wrapped_across_two_lines_is_found(self):
        """Verb on one line, file on the next: invisible to a line-by-line reading."""
        doc = "# T\n\n- You must write the summary to\n  `docs/summary.md` before you stop.\n"
        self.assertEqual(self._mandated(doc), ["docs/summary.md"])

    def test_negative_control_a_verb_and_a_file_in_different_sentences_are_not_a_mandate(self):
        """One physical line used to be enough for the two to count as one promise. A scraped
        page pasted on a single line "mandated" a file named a hundred kilobytes after the
        verb."""
        doc = "# T\n\nCreate a plan first. Nobody has ever read `docs/old-notes.md` since.\n"
        self.assertEqual(self._mandated(doc), [])


class LinearTimeTests(unittest.TestCase):
    """The first draft had three super-linear paths. No file in the survey triggered them -
    the slowest took a sixth of a second - but kibsu reads repositories it did not write, up
    to a 5 MB ceiling per file. Each input below took between forty seconds and a minute and
    a half; the bound is generous on purpose, so this fails on the old behaviour and not on a
    slow runner."""
    BOUND = 10.0

    def _timed(self, doc):
        t0 = time.time()
        audit.analyse(doc)
        return time.time() - t0

    def test_a_long_unbroken_block(self):
        self.assertLess(self._timed("# T\n\n" + "A" * 40000 + " x. Y\n"), self.BOUND)

    def test_many_candidate_boundaries_that_are_not_boundaries(self):
        self.assertLess(self._timed("# T\n\n" + "Run J. K. R. " * 3000 + "\n"), self.BOUND)

    def test_a_run_of_backticks(self):
        self.assertLess(self._timed("# T\n\nYou must run it. " + "`" * 1280 + " Then stop.\n"),
                        self.BOUND)

    def test_one_block_of_many_lines(self):
        doc = "# T\n\n" + "".join("Run it %d. Then stop.\n" % i for i in range(16000))
        self.assertLess(self._timed(doc), self.BOUND)


if __name__ == "__main__":
    unittest.main()
