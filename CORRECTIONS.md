# Corrections

Every published number this project has had to correct, in one place, newest first. Each
entry names what was wrong, which direction the error biased the published figure, the old
and new values, and how to reproduce both sides. This file exists because the project
expects to keep finding errors in its own instrument; the alternative is not finding them.

---

## 2026-10-14 — five places a soft line break still moved a count (scorer 0.12.0)

Scorer **0.12.0**. The 2026-10-11 round's acceptance property - where a soft line break falls
inside a block changes no number - was published without qualification, and it was not
true. [Issue #113](https://github.com/M-Bajalan/kibsu/issues/113) found five places where
the reader took a continuation line for the start of a block, where CommonMark reads it as
more text of the block above. markdown-it-py, cmark-gfm and commonmark.py agree on every
case below.

| shape | one line | re-wrapped | what 0.11.0 read in the re-wrap |
|---|---|---|---|
| a number inside a list item | `- Never reuse the schema from 2024. Then...` | `...from` / `  2024. Then...` | a second item, numbered 2024, and a step |
| an escaped backslash at a line end | `...copy the file to C:\\ and then...` | `...to C:\\` / `and then...` | a hard break: two sentences |
| a bullet four columns past an item's text | `- You must run the build + test steps.` | `...the build` / `      + test steps.` | a sub-item: two sentences |
| a `\|`-led line with no delimiter row | `\| Never skip this step, and always...` | `\| Never skip this step,` / `and always...` | a table row, then a new paragraph |

The fifth is the same misreading from the other side. On a line that leaves a quote, the
reader let only `1.` open a list, so in `1. If:` / `   > Note the version.` / `2. Run...` /
`3. Run...` every later step was read as a lazy continuation of the quote: one step where
the list has three. The rule is CommonMark's: only a list that would interrupt a paragraph
must start at 1, and a line that has left the quote is not tested against the quote's
paragraph. The same rule decides shape 1 from the other side. Written flush left, outside
the item, `2024. Then...` does start a list, and it still does.

**Why the property test passed.** Its wrap helper refused to break before any number at the
start of a list item's continuation line. CommonMark refuses only a lazy one, written
outside the item, so the helper never tried the wraps that broke shape 1. With the refusal
matched to CommonMark's, the suite went red at widths 14, 20 and 62, on the shipped fixture:
"Always read step 2. Then decide." was read as an item numbered 2. The helper now refuses
exactly what CommonMark refuses. It also wraps items two and five columns past their text.
The fixture carries every shape, and a new control fails unless each shape is really reached
by some wrap. Each pair above has its own test, with a negative control on the side where
CommonMark says the two documents differ. One mutant the issue named survived the whole
0.11.0 suite: `_interrupts()` ignoring list numbers. It no longer survives.

**What changed in the reader.**

- A backslash hard break needs an odd run of trailing backslashes. Two trailing spaces
  still make one.
- A table row needs a delimiter row under it, or a table already open. Before, any `|`-led
  line with nothing open was a row.
- The reader tracks the text column of each open list item. A line four or more columns past
  the text of the block's container continues the block, whatever it opens with: indented
  code cannot interrupt a paragraph. That covers a bullet, a fence or a number.
- A list number opens an item only where nothing is open, on a line outside the open block's
  container (`2.` at the margin under `1. ...` is the next item), or when it is 1 - and only
  where the reader knows a paragraph is open. An item can open with a quote, a heading,
  another list or indented code instead, and the reader's patterns, which count columns from
  the page, do not see those inside an item. After such an item any number opens one, as
  before.
- A tab is as wide as the column it starts at (`-\tx` puts `x` at column 4, not 5).
- On a line leaving a quote, any list number opens a list.
- #107's crash fix is carried. A quote opening under a paragraph had closed it, and the
  reader then appended to it. The reader re-tests its answer, so that crash cannot come back
  in a merged history.

**How the new reader was attacked before it was trusted.** An adversarial review ran the
first draft against the three parsers on about 1.5 million generated documents, and on
mutants of the reader against the suite.

- **Crashes:** none.
- **Performance:** linear.
- **A regression of the draft's own.** Its item rule assumed the open block was a paragraph.
  Where an item opened with a quote, a heading or code, it swallowed the next numbered item,
  which 0.11.0 had read right by accident. That was 7 documents in 800,000, and 0 of 4,806
  real files. A tab after a quote marker did the same in 41.
- **A wide marker.** `100.` and `-` followed by four spaces put the item's text past column
  4. A line four columns in is text there, and neither reader saw that.
- **19 of 41 mutants lived.**

All of it is fixed above. `ContainerTests` in `tests/test_sentences.py` is the review's tests
plus one for each regression. They fail on the draft and on 0.11.0 where each was wrong, and
every behaviour-changing mutant now dies. One mutant lives: dropping the quote-depth guard on
the four-column rule. It is closer to the parsers on some documents and farther on others,
and is left as it was.

One fix of the review's own was wrong on real files, and the corpus caught it. Measuring
every line against the page folded each bullet of a file indented four columns throughout
into the one before. One surveyed agent file went from 19 instructions to 2. The next bullet
beside an item is the next item now, and a test holds it.

Across the 6,490 corpus files, the reviewed reader and the first draft give identical
results, record for record. The figures below are the reviewed reader's.

**The re-wrap property, measured across the corpus.** Every paragraph of the 6,573
Markdown files in the ten pinned repositories was re-wrapped 48 ways. Widths and hanging
indents were varied, and breaks were added, removed and moved, never at a hard break. Only
re-wraps that markdown-it and cmark-gfm render as the same document were kept: 201,651 of
them.

| result changes on a kept re-wrap | scorer 0.11.0 | scorer 0.12.0 |
|---|---|---|
| any field `analyse` returns | 11,259 | **606**, in 35 files |
| ...of those, in the two declared places | | 227 |
| ...of those, an instruction count | | 51, in 6 files |
| ...where 0.11.0 reads it right and 0.12.0 does not | | **0** |

The 606 come from causes that predate this round, listed below. A second check compared
where each reader starts a list item with where markdown-it does. Items only the reader
starts fall from 295 in 33 files to 274 in 20, and the 132 it misses are unchanged. 0.12.0
starts or misses none that 0.11.0 did not.

This corrects a sentence of the 2026-10-11 entry and the README. That round's fuzz kept 973
re-wraps and found no instruction count, checkable count or sentence that moved. It was true
of the re-wraps it tried, not of re-wrapping: the wider fuzz finds the 51 above, and 0.11.0
moves on every one of them.

**Direction of the bias: none that a published figure shows.** Re-measured at the same
pinned SHAs, every `evidence/` file changes in one field, the scorer version. The survey
table, the median, the phantom line and every row are unmoved, and so is `report`'s public
median: 7.6, now labelled scorer 0.12.0.

Underneath, 14 of the 6,490 Markdown files in the ten pinned repositories read differently.
None of them is a surveyed unit, and none changes an instruction or checkable count:

- **11 rule files** in sanjeed5's `rules-v0-deprecated/` folder are YAML dumps. A bullet
  `- |-` is followed by `  5. Testing:`, two columns in, inside the item. CommonMark reads it
  as text of the item, and so does 0.12.0. Each loses a step, and the detected genre
  changes from procedure to mixed.
- **1 more rule file** of the same kind loses its step without a genre change.
- **1 davila7 reference file** loses 3 steps. Its `1.` lines sit twenty columns into a list
  item's text, which CommonMark reads as continuation.
- **1 davila7 template** has bullets inside an HTML comment, six columns into a list item.
  They now continue the item, as markdown-it reads them. The logical line count and the
  genre scores move; the genre does not.

In every one of the 14, the new reading is markdown-it's.

The issue also quoted a block-start comparison from an earlier review pass: 67 list items
lost in 22 of about 2,300 files. That pass did not keep its file list, and this round could
not reproduce the figure on the pinned corpus, where no file shows shape 5 at all. It is
not repeated here as a measurement.

**The pre-registration.** The public workspace kibsu-lab reads the same under 0.12.0 at both
pinned commits:

- `8bec5ee`: 58.1%, 18 of 31, 3 units; doctrine 0 of 6.
- `2d49abf`: 57.8%, 26 of 45.

The old instrument reproduced each before the new one was run. The private origin workspace
was not reachable from where this round was run, and is not re-measured here; see the
appended note in [PREREGISTRATION.md](PREREGISTRATION.md).

**What this round knows it leaves behind:**

- After a blank line, a paragraph under a list item but indented less than the item's text
  (`1. foo`, blank, `  bar`) is still read as part of the list. CommonMark closes the list
  there, so a `2.` under it continues the paragraph instead of opening an item. Unchanged
  from 0.11.0. No re-wrap reaches it, and changing it would change what counts as a step.
- An empty list item (a bullet with nothing after it) is not read as an item. Unchanged.
- An item whose text is itself a list marker (`- 1. foo`) is one item to the reader, not two.
  The next number still opens an item, as before.
- A `|`-led line at the margin under a list item, over a delimiter row, is read as a table.
  CommonMark reads it as more of the item. Inside a quote, the delimiter row is looked for
  without its quote marker. Both are unchanged.
- Fences:
  - A closing fence indented four or more columns closes the fence. CommonMark leaves it
    open.
  - A fence opener indented four or more columns opens one. CommonMark reads it as code.
  - A fence left open inside a list item runs to the end of the file. CommonMark ends it
    with the item.
  All three are unchanged.
- A blockquote inside a list item (`- > Note...`) is read as the item's text, so its lines
  are not joined the way the quote's are. Unchanged.
- A line that is one tag (`<ROLE_RULES>`) is read as an HTML line even where CommonMark,
  which allows no underscore in a tag name, reads text. Unchanged.
- Smaller cases, each unchanged:
  - two quote markers with four spaces between them;
  - a lazy `===` under a quote, read as a rule;
  - a tick-box `[ ]` split across two lines.
- The two deliberate places from the 2026-10-11 entry stand. A fence on the line under a tag
  is a fence, and a pipe table with a ragged delimiter row is a table. Shape 4 is not a
  third: a `|`-led line with no delimiter row is prose, as GFM reads it.

Reproduce both sides. kibsu 0.10.0 from PyPI (scorer 0.11.0) prints the left column of every
pair; this commit prints the right. The pairs are `tests/test_sentences.py`, in BlockTests
under the issue number. For the survey, check out the SHA in each `evidence/` file and run
`SKILL_AUDIT_CLONES=<dir> python -m kibsu survey`. The old instrument reproduced all ten
committed evidence files byte for byte before the new one was believed.

---

## 2026-10-11 — the scorer counted lines, and a line is not an instruction

Scorer **0.11.0**. Every scorer through 0.10.0 judged the physical line. `kibsu explain`,
merged earlier the same day, printed those lines for the first time, and its first listing showed
the fault in five entries: three of them were halves of sentences. A sentence hard-wrapped
over three lines was scored once for every line that carried a directive word; a line
holding three sentences was scored once.

So a file's score depended on where its editor broke lines. Measured before anything was
changed, by re-wrapping the same text: the largest surveyed collection read 16.6% as
written, 13.7% wrapped at 60 columns and 15.6% at 100, with 468 of its 699 procedure files
moving; `anthropics/skills` read 7.4%, 3.8% and 5.6%.

**Direction of the bias: both, and that is why a percentage hid it.**

- *Hard-wrapped prose was scored too LOW.* One instruction became two or three, and the
  fragments are nearly always claimable, because a continuation line rarely carries the
  command. kibsu-lab, which hard-wraps its prose, reads 57.8% where it read 47.8%.
- *Long lines were scored too HIGH.* A paragraph written as one line counted as one
  instruction, and counted checkable if any sentence in it named a command or a file.
  `anthropics/skills` across all genres reads 8.0% where it read 14.1%: 672 instructions
  where the line count saw 498. The private origin workspace of the pre-registration, which
  writes long lines, falls from 24.0% to 18.3%.

Across the eight ranked collections the two errors nearly cancel - the median moves a tenth
of a point - which is the least reassuring thing in this entry. A number that does not move
when its instrument is rebuilt was not measuring what moved underneath it.

**What changed in the instrument.** The document is normalised first: the lines of a
paragraph, list item or blockquote are joined the way CommonMark joins them, and every
signal - the genre signals as much as the instruction count - is computed from that. Each
block is then cut into sentences (sentence punctuation, then a capital letter or a code
span; an explicit hard break is a boundary too), and the sentence is what is judged. A
mandated file is read from one sentence, not one line. A tick-box item counts once.

**What moved** (same pinned SHAs, full history for the artifact column):

| collection | instr | all% | proc% | never existed / mandated |
|---|---|---|---|---|
| davila7/claude-code-templates | 18,823 -> **20,099** | 15.7 -> **14.6** | 16.6 -> **15.6** | 73/172 -> **56/129** |
| obra/superpowers | 418 -> **459** | 12.2 -> **11.8** | 13.1 -> **13.1** | 1/1 -> **1/1** |
| contains-studio/agents | 737 -> **734** | 9.5 -> **9.5** | 9.7 -> **9.7** | 0/0 -> **0/0** |
| sanjeed5/awesome-cursor-rules-mdc | 210 -> **230** | 6.2 -> **7.8** | 6.2 -> **7.8** | 1/2 -> **2/3** |
| wshobson/agents | 1,918 -> **2,080** | 6.2 -> **6.2** | 7.7 -> **7.4** | 8/14 -> **8/18** |
| vijaythecoder/awesome-claude-agents | 290 -> **293** | 8.6 -> **8.2** | 6.8 -> **6.7** | 0/1 -> **1/4** |
| anthropics/skills | 498 -> **672** | 14.1 -> **8.0** | 7.4 -> **6.2** | 12/38 -> **6/16** |
| VoltAgent/awesome-claude-code-subagents | 3,729 -> **3,742** | 1.7 -> **1.7** | 1.8 -> **1.7** | 1/1 -> **1/1** |

| figure | published (0.10.0) | corrected (0.11.0) |
|---|---|---|
| median, procedure-only, 8 ranked | 7.5% | **7.6%** |
| min / max | 1.8% / 16.6% | **1.7% / 15.6%** |
| in-scope mandated artifacts, distinct | 229 | **172** |
| ...of which never existed in any commit | 96 (42%) | **75 (44%)** |
| units whose detected genre changed | — | **5 of 1,477** (davila7 2, obra 1, wshobson 2) |
| below the floor, not ranked: 0xfurai / iannuttall | 62.5% of 16 / 14.5% of 76 | **62.5% of 16 / 14.1% of 78** |
| `report`'s public median constant | 7.5 (scorer 0.10.0) | **7.6 (scorer 0.11.0)** |
| kibsu-lab at `2d49abf`, procedure-only | 47.8% (22 of 46) | **57.8% (26 of 45)** |

**The artifact column moved most, so it was classified by hand, mention by mention.** The
mandate rule did not change: a file is mandated when an instruction carries an
artifact verb (create, write, save, update...) and names it. What changed is that the
instruction, the verb and the file must now share a sentence. Under the line count, a
`never` in the fourth sentence of a long line made the whole line an instruction, and a
`create` in the first made every file named anywhere on it a promise.

*78 mentions left. 70 were false pairings.* Reading lists (`Start with
shared/managed-agents-overview.md, then...`), detection patterns (`filenames like
agent-openai.py or *-generic.py`), and example names (`e.g. a.py, b.py, app.py`) were all
being reported as files the repository promised and never produced. 21 of the 27 phantoms
that left the table were of this kind - they were never promises.

*8 were real, and the stricter reading no longer sees them.* Named, because a count would
hide which rule lost them:

| lost mention | why the sentence is not read as an instruction, or not as a mandate |
|---|---|
| `<planning_dir>/claude-research.md` — "After collecting results..., combine them and write to..." | does not open with its verb, carries no modal |
| `.mcp.json` — "To use Xquik as an MCP server..., add to `.mcp.json`" | same (still in scope through three other units) |
| `02-pipelines.md` — "`02-pipelines.md` - For every flow..., write the end-to-end sequence" | opens with the file name |
| `setup.ps1` — "**Pro Tip:** Create a `setup.sh` or `setup.ps1` script" | the imperative stands behind a label |
| `SESSION.md`, `NEXT.md` — "**Rewrite `SESSION.md`**" | `rewrite` is not in the artifact-verb list; `appended` in the next sentence used to carry it |
| `swarmvault.config.json` — "Set `profile.deepLintDefault: true` in..." | `set ... in` is not an artifact verb |
| `dietary.json` — "Read `dietary.json`. Missing -> offer to create it" | the verb's object is a pronoun in the next sentence |

Each of the eight was caught before by accident - a modal or a verb elsewhere on the same
line - and each names a real gap in the instruction test or the verb list, now visible
because the accident is gone. None is fixed here: they are vocabulary and grammar rounds,
with a census each, not riders on a change of what is counted.

*20 mentions arrived. 10 are real* - `Save this data immediately to timing.json` (four
copies of one skill), two `Save to .seoagent/...` lines, a wrapped `Create or update
README.md, docs/api.md, docs/architecture.md`, and one declared `Output format:` file. They
were invisible because the sentence that carries them shared a line with one that is not an
instruction, or was wrapped across two.

*10 are false. Three of those mentions are two files that sit in the table above as never
existed:*

- `AGENTS.md` in sanjeed5, in two files (its row moves 1/2 -> 2/3 on this alone). The source
  is an MDX page; its `export const meta = { ... description: "...plus AGENTS.md."` is four lines
  that Markdown joins into one paragraph, and `export` is both an imperative and an
  artifact verb. A JavaScript statement is being read as an instruction to export a file.
- `reference/task-creation-template.md` in davila7: the artifact verb that matched is the
  word `creation` inside the file's own name.
- The other seven are files that exist: three `references/*.md` under a wrapped `**Output
  format:**` label, a script named in `the CSV output format assets/thermal-sample.sh
  writes`, `Read references/knowledge-base-pattern.md before creating the workspace`, a
  `package.json` beside the path `scripts/generators/commands`, and `SKILL.md` in six
  `✅`-led lines that Markdown runs together. They inflate the mandated count, not the
  phantom count.

Net, for the phantom line: of the 96 published, 21 were never promises; of the 75 now
published, 2 are this round's own false positives, and 6 real ones are no longer counted.

**A sentence on this page that its own evidence had stopped supporting.** The README said
"Three of the eight mandate zero artifacts." Under scorer 0.10.0's committed `evidence/`
that was already one of eight - a second collection mandated a single file, which exists,
and its table cell read `—` where it should have read `0/1`. It reads one of eight now, and
the table says what `—` means.

**How the new reader was attacked before it was trusted.** The first draft shipped with a
property test - re-wrap a document, nothing may change - and the test passed. Four review
agents were then given the draft and one question each: the sentence splitter, the block
reader, re-wrapping, and whether the units still meant anything. The re-wrap reviewer used
a real CommonMark parser as an oracle and found the property false in six ways: a
continuation line opening with `<path>`, `[x]`, `2024.`, `#12`, `|`, or four columns of
indent was read as a new block. The property test had missed all six because its re-wrap
helper asked the scorer which lines formed a block, so it could only try wraps the scorer
already understood. Other passes found a sentence scan that went quadratic and a code-span
pattern that went cubic (one hostile line could hold a scan for minutes), `"etc."` swallowing
ninety-one real sentence ends, and a list number read as the end of a sentence.

The reader was rewritten to CommonMark's interruption rules and the test rebuilt so that
nothing in it parses Markdown: fixtures are described, laid out at 29 widths and four
hanging indents, and a control proves the awkward tokens really land at line starts. A fuzz
then re-wrapped all 1,477 surveyed files in 15 families, keeping only re-wraps the
independent parser called the same document (973 file-by-family cases): **no instruction
count, no checkable count and no sentence moved.** Nine cases in four files still move a
genre signal, one of them far enough to change a genre, and all nine are in two places
where the reader deliberately sides with the file's reader against the renderer - a fence
on the line under a tag such as `<Good>` (CommonMark opens an HTML block there and turns
the code into paragraphs), and a pipe table whose delimiter row has the wrong number of
cells (1 table in 1,241; GFM calls it a paragraph).

**What this round knows it leaves behind:**

- Lines with no blank line, list marker or sentence punctuation between them are one
  sentence, as a renderer would run them together.
- An imperative behind a label (`**Pro tip:** Create...`) is seen only by its modal. Reading
  the colon as a boundary was measured on a draft: about 2,000 more instructions in the
  largest collection, nearly all claimable, and a median near 5.6%. It changes what an
  instruction is, so it is a round of its own.
- The boundary rule is conservative and knows English capitals only: a missed boundary
  merges two sentences, which costs less than inventing an instruction.
- The eight lost mandates and the two false phantoms above.

Reproduce both sides: `pip install kibsu==0.9.0` measures with scorer 0.10.0 and prints the
left columns; this commit prints the right. For the table, clone each collection in full,
check out the SHA in its `evidence/` file, and run `SKILL_AUDIT_CLONES=<dir> python -m
kibsu survey` - a shallow clone answers `UNKNOWN` for the artifact column, never a number.
The old instrument was made to reproduce every published 0.10.0 figure at these pins,
artifact column included, before the new column was believed. The property test is
`tests/test_sentences.py`; the pre-registration's re-measured column is in
[PREREGISTRATION.md](PREREGISTRATION.md), appended note of the same date.

---

## 2026-10-10 — the front door: `report` compared against a median three scorers old

Every earlier audit read this code against itself. This round did something else: it installed
the published 0.8.0 into an empty environment and followed the two READMEs as a stranger
would - `pip install kibsu`, the sample on this repository's front page, then kibsu-lab's
Quickstart from a fresh clone. Four things were wrong, none of them in the scorer, and none
of the survey table's figures move. One of them is a published number, which is why it is
indexed here.

**`report` judged every repository against the wrong median.** Question 3's mark is decided
by one comparison - the repository's procedure-only percentage against the public median -
and `report.py` carries that median as a constant, because the wheel does not ship
`evidence/`. It was set to 9.4 when scorer 0.6.0 measured 9.4, and never moved again. Scorer
0.7.0 re-measured the table to 7.7 and 0.10.0 to 7.5; four measurement rounds regenerated
`evidence/` and this file's tables, and not one touched the constant, because nothing
connected the two. Releases **0.6.0, 0.7.0 and 0.8.0** therefore measured with the strict
instrument and compared the answer to a median taken with the lenient one.

Direction of the bias: **against the repository being measured** - the one case in this file
where the tool was too harsh rather than too generous. Anything between 7.5% and 9.4% was
told it sat below a median it was above, lost the `+`, and lost a point of its "N of 5".
One of this project's own eight survey rows is in that band: `wshobson/agents` at its pinned
`c4b82b0` reads `x ... 7.7% (below the 9.4% public median)`, `1 of 5 ready` under the
published 0.8.0, and `+ ... 7.7% (above the 7.5% public median)`, `2 of 5 ready` from this
commit. The same staleness sat in this README's pasted sample, which had not been re-run
since scorer 0.6.0 and so printed 15.6% for `obra/superpowers` at `3dcbd5c` a few screens
above a table giving 13.1% for the same repository at the same commit.

**What moved** (no survey figure; the instrument's own comparison and one pasted sample):

| figure | published | corrected |
|---|---|---|
| `report`'s public median, the constant behind question 3's mark | 9.4% (scorer 0.6.0) | **7.5%** (scorer 0.10.0 - the table's own median) |
| README sample, `obra/superpowers` at `3dcbd5c`, question 3 | 15.6%, above the 9.4% median | **13.1%, above the 7.5% median** |
| `wshobson/agents` at `c4b82b0`, question 3 and score | `x` below the median, 1 of 5 | **`+` above the median, 2 of 5** |
| survey table: every percentage, the median, the phantom counts | — | **unmoved** |

Reproduce both sides: `pip install kibsu==0.8.0`, then `python -m kibsu report` against a
clone of either repository checked out at the SHA above, prints the left column; the same
command from this commit prints the right. The constant is now a pair - the median and the
scorer it was measured with - and `tests/test_peer_median.py` fails while either half
disagrees with the committed `evidence/`, computing the median through the survey's own
function rather than a copy of it. An instrument change still lands before its
re-measurement does, and in that window the two scorers honestly differ; `report` now says
so in the finding itself instead of comparing in silence.

**Three siblings from the same walk, no published figure involved:**

- **An index with no history was replayed, and convicted.** `kibsu index` writes
  `.kibsu/index.json`; a repository is free to gitignore it and build it on demand, as
  kibsu-lab does. Question 5 replayed the last commits against that file anyway, and since
  it had never been in a commit, every commit that added a doc "failed to update it" - 6 of
  6 eligible in the lab, the 100% that `check.py`'s own backtest docstring calls a number
  that "would mean nothing". Following this tool's quickstart turned `?` into an accusation
  - run at 0.1.1 and at 0.8.0, same line both times (0.1.0 abstained, but only because of
  the scoping bug in #2).
  It reads `COULD NOT CHECK - ... has never been committed` now, with the read-only command
  that shows it. A committed index left stale is still convicted; that is the negative control.
- **"Of your last 200 commits" on a repository with twenty.** The line printed the replay's
  cap as its denominator. It prints the commits actually walked.
- **An installed kibsu did not answer to its name.** No console script was declared, so
  `uvx kibsu` stopped at "does not provide any executables" (`pipx run` needs the same
  declaration) and `pip install kibsu` left no `kibsu` command. The package declares one
  now, bound to the same `main()` that `python -m kibsu` runs.
- **The tool that writes this README's counts wrote a wrong one, and exited 0.** Found while
  building this round, by the round's own tests. `tools/refresh_readme_counts.py` puts
  `tools/` on the import path and not the clone root, so the test modules it discovers
  imported whichever kibsu was pip-installed on the machine - here an older release. A new
  test module needed a name that release lacked, failed to import, and unittest counted the
  failure as one case: the tool reported 251 cases, wrote 251 into the README, and printed
  "refreshed". The suite ran 258 and failed on the paragraph the tool had just produced.
  Nothing was published - the guard caught its own companion - but a count is now refused,
  exit 2, when any test module fails to load, and the clone root is on the path before
  discovery. An unmeasurable count is "cannot tell", the same answer `?` gives.

Not fixed here, and named so it is not mistaken for fixed: **kibsu-lab's README and CI are
pinned to kibsu 0.1.0.** Its published baseline (53.7%, question 5 "could not check", a
citation of #2 as an open limitation) reproduces only under that one version; under 0.8.0 a
fresh clone following its Quickstart gets 47.8% and a different fifth line. The pin kept its
CI green through nine releases. It is refreshed in the lab's own repository against the release
that carries this round, so the block is re-captured once, not twice.

## 2026-09-01 — a pre-release audit of yesterday's three rounds (scorer 0.10.0)

Before cutting the release carrying scorer 0.9.0, main was audited the way the survey repos
are: two adversarial agents sent at the three scorer rounds shipped on 2026-08-31, refuters
defaulting to "refuted" when a claim could not be reproduced. Five findings survived. Three
touch the scorer and ship as 0.10.0 ([#PR1](https://github.com/M-Bajalan/kibsu/pull/89));
one was a stale ruleset disclosure, fixed in [#88](https://github.com/M-Bajalan/kibsu/pull/88);
one is packaging - the live 0.7.0 sdist could not run its own test suite. That fix arrived in
two commits, and the first one's message overstated it: [#90](https://github.com/M-Bajalan/kibsu/pull/90)
described MANIFEST.in plus two checker flags plus their CI wiring, and shipped MANIFEST.in
alone (the applying script stopped early; a `;` where `&&` belonged let the commit through).
The checks and wiring landed in [#91](https://github.com/M-Bajalan/kibsu/pull/91),
whose message owns the discrepancy - and whose first push CodeQL flagged for `py/tarslip`: the
checker written to guard the release unpacked the tarball with `extractall()`, the same
path-escape class #59 and #65 had closed elsewhere. It extracts member-by-member behind a
containment check now, with two negative controls. Recorded here because a commit message the
repository does not back is the exact class this project measures elsewhere. Survey re-run at
the **same pinned SHAs**, ref-scrubbed clones as always.

**Two of the three scorer refinements are measured nulls** - real defects, reproduced in a
temp repo, and affecting zero units at the pinned states:

- **The directory-prefix scope check went case-sensitive by accident.** 0.9.0 made `glob_re()`
  byte-exact for the file-existence question git answers; `check_artifacts()` reused the same
  function to decide whether a mandate's *ancestor directory* is this repo's business at all -
  a scope question, to which a directory that exists under different casing answers yes. A
  tracked `skills/` with a mandate for `Skills/foo.md` fell into the prefix-missing exclusion
  bucket and was never phantom-checked: not credited, not counted, and invisible to the 0.9.0
  ablation, because an excluded token never reaches `match_count`. Two questions, two matchers
  now. Zero pinned-corpus tokens were affected.
- **The mandate rule read the raw mandated list.** A doctrine unit whose only "mandate" was
  "save `{name}.md` into *your* project's notes" - a mention `check_artifacts()` excludes as
  user-scope - was demoted to mixed, and a declared doctrine earned a false conflict flag. The
  rule's own justification ("a unit promising files is making checkable promises") does not
  hold for a promise about someone else's tree. Gated on `any_clean`, a per-mention signal the
  scan already computed. Zero of the eight pinned-corpus demotions were affected.

**The third moves numbers.** Five entries in the verb vocabulary - `note`, `state`, `list`,
`record`, `track` - open ordinary prose at least as often as they command: `Note: ...`,
`Note that ...`, `List of ...`, `State of ...`. The 0.7.0 census had rejected `import`,
`order` and `format` on exactly this ground, and never re-examined the inherited list. When
one of the five is followed by a colon or by *that / of / the following / is / are / was*, the
line is a label or a description, not an instruction. On a 250-file public corpus 20 of 5,930
counted lines drop, every one a `Note:` callout or a wrapped continuation; `List the files`
still counts. Disclosed residual: a noun-noun opener (`Record types are ...`) is still counted
- the rule reaches the contexts the corpus produced, and one synthetic probe is not evidence
to widen it.

**What moved** (survey at the same pinned SHAs, scorer 0.9.0 → 0.10.0):

| figure | 0.9.0 published | 0.10.0 re-measured |
|---|---|---|
| median procedure-only checkability (8 ranked collections) | 7.7% | **7.5%** |
| total instructions, 8 ranked collections | 26,698 | **26,623** |
| phantom artifacts | 96 of 230 (42%) | **96 of 229 (42%)** |
| genre census, doctrine units | 15 | **15 (unmoved)** |
| origin workspace, every state | — | **two `Note:` lines fewer per state; see PREREGISTRATION** |
| kibsu-lab, every figure | — | **identical to the digit** |

The median moved DOWN, which the corpus ablation did not predict and the survey then
explained: a large share of the dropped `Note:` lines carried a backtick command
(`Note: run \`x.py\` first`) and had therefore been counted as CHECKABLE instructions, so
the numerator shrank with the denominator. A note about a command is not a command, and
the checkable ratio was borrowing credit from lines that instructed nobody to do anything.
One in-scope mandate left the denominator the same way: it sat on a `Note:` line in
anthropics/skills, and a mention on a non-instruction line has never been a mandate. The
genre census is untouched (doctrine 15) and the two null refinements are confirmed null at
the pinned states, as the ablation said.

The same audit found two cells in PREREGISTRATION.md's 2026-08-07 table that were copies of
the row above them (post-cycle-1 doctrine, both instrument columns); the file carries a dated
correction with the re-run values, per its own rule. Reproduce both sides of this entry:
`pip install kibsu==0.7.0` (which carries scorer 0.8.0 - the 0.9.0 instrument was never on
PyPI, only on `main` between #85 and this entry) versus this repository at `main`,
ref-scrubbed pinned clones per the 0.6.0 entry's caveat.

---

## 2026-08-31 — the existence check matched case-insensitively; git never did (scorer 0.9.0)

The case round ([#78](https://github.com/M-Bajalan/kibsu/issues/78), fixed in
[#85](https://github.com/M-Bajalan/kibsu/pull/85)). `glob_re()` compiled every artifact
matcher with `re.I`, so a mandate for `notes.md` was satisfied by a tracked `Notes.md` -
an answer git, which compares paths byte-exactly, would never give, and an instruction a
Linux `cat` fails. The check now answers the way git would. Detection of mandates stays
case-insensitive, deliberately: reading a mandate is a different question from checking
its existence, and the earlier "NOTES.MD is the same mandate as notes.md" ruling stands -
the two postures are now split on purpose rather than conflated by accident.

Ablated before shipping, per the issue's own bar: **367 distinct mandated tokens** across
the ten pinned repos and both experiment workspaces. Exactly **one** flips to phantom -
davila7's `summary.md` mandate, whose only six instances are `SUMMARY.md` benchmark
files - and seven lose surplus matches without changing verdict. Neither experiment
workspace is touched.

**What moved** (survey at the same pinned SHAs, scorer 0.8.0 → 0.9.0):

| figure | 0.8.0 published | 0.9.0 re-measured |
|---|---|---|
| median procedure-only checkability (8 ranked collections) | 7.7% | **7.7% (unmoved)** |
| phantom artifacts | 95 of 230 (41%) | **96 of 230 (42%)** |
| davila7/claude-code-templates phantoms | 72/172 | **73/172** |
| both preregistration workspaces, every figure | — | **identical to the digit** |

The direction is the honest one: the tool credits less, not more. Reproduce both sides:
`pip install kibsu==0.7.0` versus this repository at `main`, ref-scrubbed pinned clones
per the 0.6.0 entry's caveat.

---

## 2026-08-31 — a doctrine label could sit on a unit that mandates files (scorer 0.8.0)

The genre round, deferred out of 0.7.0 by design ([#77](https://github.com/M-Bajalan/kibsu/issues/77))
because genre is the backbone of the pre-registered experiment and a detector change
deserves a release where genre movement is the only variable. Fixed in
[#82](https://github.com/M-Bajalan/kibsu/pull/82); survey re-run at the **same pinned
SHAs**, ref-scrubbed clones as always.

The defect: `classify()` votes once for a whole file, and density on a short file lets a
four-sentence doctrine-flavoured preamble outvote a five-step procedure mandating four real
files (doctrine 147.7 vs procedure 19.2 in the audited repro) — the whole unit, checkable
steps included, left the headline procedure pool. The rule that closes it is derived from
this project's own v0.3.0 definition rather than invented: doctrine produces judgement, not
files, so **a unit that mandates artifacts or carries runnable fences cannot be DETECTED as
doctrine** — it is making checkable promises, and the 0%-by-construction exemption cannot
apply to it. Detection only; a declared genre still beats detection in both directions.

Three candidate designs were calibrated over 1,561 pinned-corpus units before one was
frozen; the two rejected ones (an executable-evidence floor, a region split) each failed to
fix the audited repro. The mandate rule flips **8 units, every one a visible
misclassification**, each demoting to the genre its own next-best score already indicated:

| unit | was | now |
|---|---|---|
| anthropics/skills · xlsx | doctrine | reference |
| davila7 · distributed-training-deepspeed | doctrine | procedure |
| davila7 · distributed-training-pytorch-fsdp | doctrine | procedure |
| davila7 · context-architecture | doctrine | reference |
| davila7 · swarmvault | doctrine | procedure |
| davila7 · sveltekit | doctrine | procedure |
| obra/superpowers · requesting-code-review | doctrine | procedure |
| wshobson/agents · grpo-rlvr-training | doctrine | reference |

**What moved** (survey at the same pinned SHAs, scorer 0.7.0 → 0.8.0):

| figure | 0.7.0 published | 0.8.0 re-measured |
|---|---|---|
| median procedure-only checkability (8 ranked collections) | 7.7% | **7.7% (unmoved)** |
| in-scope mandated artifacts / phantoms | 230 / 95 (41%) | **230 / 95 (unmoved)** |
| genre census, doctrine units | 23 | **15** |
| davila7 procedure-only | 16.5% | **16.6%** |
| obra/superpowers procedure-only | 13.5% | **13.1%** |
| both preregistration workspaces, every figure | — | **identical to the digit** |

A round that moves almost nothing is a result, not a disappointment: the misfiled units
were few, the bias direction was mixed (obra's pool gained a low-checkability procedure and
its figure went DOWN; davila7's went up), and the experiment's doctrine floor — hard 0.0%
at every stage — now stands on a pool that a mandating unit cannot quietly join, which
makes clause 3's disqualification test STRICTER, not looser. Reproduce both sides:
`pip install kibsu==0.6.0` versus this repository at `main`, ref-scrubbed pinned clones per
the 0.6.0 entry's caveat.

---

## 2026-08-31 — the scorer read past emphasis, half a vocabulary, and one delimiter style (scorer 0.7.0)

The 2026-08-28 audit of this repository (seven finder agents by dimension, adversarial
verifiers instructed to refute, two refuters attacking the fixes again before they shipped)
confirmed four more blind spots in the scorer, fixed in
[#79](https://github.com/M-Bajalan/kibsu/pull/79) as issues
[#56](https://github.com/M-Bajalan/kibsu/issues/56),
[#74](https://github.com/M-Bajalan/kibsu/issues/74),
[#75](https://github.com/M-Bajalan/kibsu/issues/75),
[#76](https://github.com/M-Bajalan/kibsu/issues/76). The survey was re-run at the **same
pinned SHAs** and `evidence/` regenerated. The headline moved again: **the published median
was 9.4%; the corrected instrument reads 7.7%.**

The four, each with the direction it biased the published numbers:

1. **The imperative anchor could not see markdown emphasis** (#56). `**Create** the gate
   file` — ordinary instruction style — was counted as no instruction at all, and a cycle
   of this project's own skill experiment moved its numbers by **de-bolding verbs**. The
   fix consumes the closing marker as a backreference to the opener with a marker-aware
   boundary: the issue's own fix sketch failed on the underscore variants it was written
   for (`_` is a word character), and a first draft here was defeated by regex backtracking
   (`**Test**ing` matched by giving the closer back) until the round's adversarial pass
   caught it. A backtick is deliberately not an emphasis marker — a code span names, it
   does not command.
2. **The verb vocabulary held 136 entries and missed ~112 ordinary imperatives** (#74),
   `gather` — the live specimen in #56 — included. 55 verbs were added, each earning its
   place in a per-verb census over these ten pinned repos plus a 1,660-file plugin corpus;
   the biggest candidates were **rejected on the same evidence** ("Import maps for
   JavaScript" is a noun phrase, and `import` alone would have added 1,625 false
   instructions).
3. **Artifact extraction required backticks while checkability never did** (#75). `Create
   config.yml` counted as checkable *because it names a file*, while that file could never
   be reported phantom. Delimiters unified — backtick, quote, or bare — with URLs and
   markdown links normalized first: the adversarial pass caught `[README.md](./README.md)`
   minting a bracket-corrupted phantom next to the real record, fifteen of which would
   have shipped into this very table. One residue is disclosed rather than guessed at: a
   bare token that is really a domain (`raycast.md` — .md is a live ccTLD) is
   indistinguishable from a file mandate by shape alone.
4. **Mandate dedup kept only the first-seen mention line** (#76), so document order — not
   the specification — decided an artifact's scope. Every mention now counts toward the
   scope verdict, computed **uncapped** after the adversarial pass showed a display cap
   quietly re-creating the bug at mention nine.

Together the four biased instruction counts **down** about 31% across every collection —
and 97% of what they hid is claimable, so every published percentage was biased **up**:
the truth about checkability is worse than every previous table said, this project's own
lab included (which is the one place the new instrument found nothing to correct — its
rewrites already carried their verbs unemphasized and their mandates backticked).

One procedural note that improved on the last round's caveat: the first re-measurement run
here used freshly cloned pins whose refs still reached **post-pin history**, and the
`git log --all` phantom walk saw the future — three of davila7's mandated files exist only
in commits newer than the pin, and phantoms read 92 instead of 95. The published numbers
come from ref-scrubbed clones per the 0.6.0 round's own caveat; the 3-artifact delta is
recorded here as the measured cost of skipping that step.

Deferred out of this round, with issues and reasons on the record:
[#77](https://github.com/M-Bajalan/kibsu/issues/77) (the whole-file genre vote — genre is
the backbone of PREREGISTRATION.md's experiment and deserves an isolated instrument round)
and [#78](https://github.com/M-Bajalan/kibsu/issues/78) (glob case posture).

**What moved** (survey at the same pinned SHAs, scorer 0.6.0 → 0.7.0):

| figure | 0.6.0 published | 0.7.0 re-measured |
|---|---|---|
| median procedure-only checkability (8 ranked collections) | 9.4% | **7.7%** |
| total instructions, 8 ranked collections | 20,286 | **26,698 (+31.6%)** |
| in-scope mandated artifacts | 159 distinct | **230 distinct** |
| phantom artifacts | 69 (43%) | **95 (41%)** |
| kibsu-lab baseline, procedure-only / doctrine | 42.4% / 0.0% | **42.4% / 0.0% (unmoved)** |
| origin workspace baseline, procedure-only / doctrine | 27.1% / 0.0% | **24.0% / 0.0%** |

Both PREREGISTRATION baselines — and, for the first time, the post-cycle-2 state — were
re-measured at their pinned states with the new instrument (its appended note carries the
full columns). Doctrine checkability is a hard 0.0% at every stage under every instrument
this project has shipped, so the pre-registered disqualification clause is untouched, and
both cycles' improvements survive re-instrumentation (24.0% → 25.9% → 26.7% under 0.7.0;
the 0.6.0 instrument read the same two moves as 27.1% → 29.3% → 29.9%).

Reproduce both sides: the old numbers with `pip install kibsu==0.5.0` at the pinned SHAs,
the new with this repository at `main` — ref-scrubbed pinned clones both times, per the
caveat above and in the 0.6.0 entry.

---

## 2026-08-07 — the scorer could not see Title-case directives (scorer 0.6.0)

A full review of this repository (six review agents by dimension, one adversarial verifier
per finding, both criticals re-reproduced by hand before being believed) confirmed three
defects in the scorer, fixed in
[#42](https://github.com/M-Bajalan/kibsu/pull/42) as issues
[#26](https://github.com/M-Bajalan/kibsu/issues/26),
[#27](https://github.com/M-Bajalan/kibsu/issues/27),
[#28](https://github.com/M-Bajalan/kibsu/issues/28). The survey was re-run at the **same
pinned SHAs** with scorer 0.6.0 and `evidence/` regenerated. Unlike the 0.5.0 round, this
time the headline moved: **the published median was 11.1%; the corrected instrument reads
9.4%.**

The three, each with the direction it biased the published numbers:

1. **`MODALS` was case-sensitive** (#26). `- Must run the tests before merging.` was
   counted as no instruction at all — Title-case matched neither the ALL-CAPS nor the
   lowercase alternation, and SHOULD/REQUIRED/MANDATORY had no lowercase branch to begin
   with. Instruction counts were biased **down** about 17% across every collection, which
   biased every published percentage **up** — the truth about checkability is worse than
   the table said. The extra mandate lines the fix extracts also grew the phantom
   population: in-scope mandates 134 → 159, phantoms 56 → 69. **Every number that moved in
   this round moved because of this one bug** — verified by ablation, not assumed: the
   survey was re-run twice more with each of the other two fixes individually reverted,
   and both runs reproduced the corrected evidence byte-for-byte.
2. **The path-prefix scope check could not see nested-only directories** (#27). A mandate
   under a directory holding only subdirectories (`skills/` in a `skills/<name>/SKILL.md`
   tree) was wrongly excluded as `prefix-missing`, silently shrinking the phantom
   population. Real — reproduced against a fixture repo end-to-end — and **zero effect at
   these pinned SHAs** (the ablation above): a bug with nothing to bite in this corpus,
   like 0.5.0's tilde-fence fix before it.
3. **A UTF-8 BOM defeated frontmatter detection in the scorer** (#28), so a declared
   `genre:`/`scope:` on a BOM'd file was silently ignored — the fix `index.py` already
   carried had never reached `audit.py`. Also **zero effect at these pinned SHAs**, by the
   same ablation.

Zero units changed genre under the new instrument (the genre classifier does not consume
the modal signal), and the identity of the two failure modes — three collections mandating
nothing, five collections whose mandates go unserved — is unchanged.

**What moved** (survey at the same pinned SHAs, scorer 0.5.0 → 0.6.0):

| figure | 0.5.0 published | 0.6.0 re-measured |
|---|---|---|
| median procedure-only checkability (8 ranked collections) | 11.1% | **9.4%** |
| total instructions, 8 ranked collections | 17,361 | **20,286 (+16.8%)** |
| in-scope mandated artifacts | 134 distinct | **159 distinct** |
| phantom artifacts | 56 (42%) | **69 (43%)** |
| kibsu-lab baseline, procedure-only / doctrine | 46.7% / 0.0% | **42.4% / 0.0%** |
| origin workspace baseline, procedure-only / doctrine | 28.7% / 0.0% | **27.1% / 0.0%** |

Both PREREGISTRATION baselines were re-measured at their pinned states with the new
instrument (its appended note carries the full columns); doctrine checkability is a hard
0.0% at every stage under both instruments, so the pre-registered disqualification clause
is untouched, and cycle 1's improvement survives re-instrumentation (27.1% → 29.3% under
0.6.0; the old instrument read the same move as 28.7% → 31.4%).

Reproduce both sides: the old numbers with `pip install kibsu==0.2.1` at the pinned SHAs,
the new with this repository at `main`. One procedural caveat that had not been written
down before: the phantom check walks `git log --all`, so a **fresh clone made today
contains commits newer than the pin** and would let the history walk see the future.
Check out the pinned SHA and point every local ref at it (delete other branches, tags,
and the remote) before measuring — that reproduces the state the original measurement ran
in, when the pin *was* the tip.

---

## 2026-07-31 — five scorer bugs (kibsu 0.2.0, scorer 0.5.0)

An audit of this project's own measurement core (three review agents, nine adversarial
verifiers, a thirteen-seat design council; every finding verified against source before
being believed) confirmed five defects in `audit.py`, the scorer behind every number this
repository publishes. All five are fixed in 0.2.0; the survey was re-run at the **same
pinned SHAs** with the corrected scorer, and `evidence/` was regenerated. The old numbers
stay reproducible: `pip install kibsu==0.1.1` and re-run at the pinned SHAs.

The five, each with the direction it biased the published numbers:

1. **Templated mandates always read phantom**
   ([#14](https://github.com/M-Bajalan/kibsu/issues/14)). `glob_re()` escaped
   `{placeholder}` segments literally, so `logs/report_{date}.md` could never match a real
   `logs/report_2026-07-30.md`. Biased the phantom rate **upward** — this error ran in the
   headline's favor. Phantom is now defined as zero instances anywhere (`match_count == 0`)
   for literal and templated mandates alike, and a pattern with no literal basename left
   (`{name}.md`) lands in its own `unverifiable_pattern` bucket, counted in neither
   direction and always reported.
2. **Fence tracking had no delimiter rule**
   ([#13](https://github.com/M-Bajalan/kibsu/issues/13)). Any ```-looking line toggled
   fence state, so fenced examples containing fences leaked display-only text into
   instruction counts and could flip a unit's genre. Direction: every ranked collection
   that moved, moved **down** in instruction count (one by −239); the only upward mover
   sits below the sample floor and was never in the published table. Five units changed
   genre; the ranked median did not move.
3. **`~~~` fences were not recognized at all.** CommonMark-valid tilde fences were scanned
   as prose. Zero occurrences in the surveyed corpus at the pinned SHAs — a real bug that
   happened to have nothing to bite; fixed by the same delimiter-tracking change as #13.
4. **Uppercase extensions were invisible.** `FILE_TOKEN`/`PATHY` lacked `re.IGNORECASE`, so
   a mandate naming `NOTES.MD` was never extracted, never counted checkable, never
   phantom-checked — mandates went missing from the denominator. Confirmed real on private
   corpora; moved **zero numbers** in this public sample, verified by a before/after
   checkpoint diff.
5. **The scaffold exclusion swept whole units on bare vocabulary.** One keyword like
   "template" anywhere near the top of a unit — including inside "do NOT scaffold" — removed
   every artifact that unit mandated from phantom-checking, silently. The published phantom
   denominator measured a keyword-filtered population. The filter now applies at the
   mandate's own line (keyword + user-scope language, negation-guarded), a frontmatter
   `scope:` declaration overrides it, and every exclusion class is published with full
   counts plus a with/without counterfactual rate. Related label fix: the old output's
   bracket "55 excluded as user-project scope" was summing **every** exclusion class under
   one class's name — the number was right, its English was wrong.

**What moved** (survey at the same pinned SHAs, scorer 0.3.0 → 0.5.0):

| figure | 0.1.1 published | 0.2.0 re-measured |
|---|---|---|
| median procedure-only checkability (8 ranked collections) | 11.1% | **11.1% — unmoved** |
| in-scope mandated artifacts | 103 distinct | **134 distinct** |
| phantom artifacts | 44 (43%) | **56 (42%)** |
| kibsu-lab baseline (procedure / doctrine) | 46.7% / 0.0% | **unmoved / unmoved** |

Both phantom counts rose — the corrected scorer *counts more mandates*, for three separable
reasons, each attributable per artifact via `out_of_scope_reason`/`templated` in the
evidence JSONs: the line-level scope rule returns artifacts the old scorer had extracted
and then excluded (the largest share), templated paths now match instead of always reading
phantom, and `.tsx`/`.jsx` joined the extension list — and the rate still fell a point,
because the denominator grew faster than the numerator. Three of the eight ranked collections are numerically
identical under both scorers on every published column, and the origin workspace's
pre-registered numbers reproduce digit-for-digit under both instruments (see
[PREREGISTRATION.md](PREREGISTRATION.md)'s appended note). Two disclosures the aggregate
line invites you to miss: **one collection dominates it** —
`davila7/claude-code-templates` supplies 101 of the 134 mandates and 44 of the 56 phantoms
— and "distinct" means distinct *within each collection, summed* (the same filename
mandated by two collections counts twice; globally distinct strings would read 119). Full
per-repo deltas: compare `evidence/` at tag `v0.1.1` against `v0.2.0` — every JSON carries
its scorer version and pinned repo SHA.

---

## 2026-07-29 — the phantom count could not be reproduced (README, pre-0.1.1)

An earlier revision of the survey table published **41 phantoms of 99 (41%)** with no
commit SHAs. Re-measuring produced **44 of 103 (43%)** — real growth in one surveyed repo,
not a scorer error, but the original number was unreproducible because nothing pinned what
it had measured. Every figure has carried its SHA since. (Restates the "One number moved"
note that has lived in the README since the fix.)

## 2026-07-29 — the line count was measured with a tool that skips blank lines (README)

The README published **3,679 lines** for the package, measured with PowerShell's
`Measure-Object -Line`, which silently skips empty lines. The correct figure at that commit
was **4,241**. (Restates the correction note that has lived in the README since; the stale
3,679 also survived unnoticed in a `codeql.yml` comment until 0.2.0.)
