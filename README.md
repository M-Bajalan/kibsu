# Kibsu

[![CI](https://github.com/M-Bajalan/kibsu/actions/workflows/ci.yml/badge.svg)](https://github.com/M-Bajalan/kibsu/actions/workflows/ci.yml)
[![CodeQL](https://github.com/M-Bajalan/kibsu/actions/workflows/codeql.yml/badge.svg)](https://github.com/M-Bajalan/kibsu/actions/workflows/codeql.yml)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/M-Bajalan/kibsu/badge)](https://scorecard.dev/viewer/?uri=github.com/M-Bajalan/kibsu)
[![PyPI](https://img.shields.io/pypi/v/kibsu)](https://pypi.org/project/kibsu/)
[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue)](https://github.com/M-Bajalan/kibsu/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Dependencies: none](https://img.shields.io/badge/dependencies-none-brightgreen)](pyproject.toml)
[![OS](https://img.shields.io/badge/OS-linux%20%7C%20macOS%20%7C%20windows-blue)](https://github.com/M-Bajalan/kibsu/actions/workflows/ci.yml)

**What can your agents not do in this repository yet?**

You have written instructions for coding agents — `AGENTS.md`, `CLAUDE.md`, a `skills/` directory,
`.cursorrules`. Kibsu reads them alongside your git history and reports which of those instructions
anyone could actually verify were followed, and which ones only work when a human remembers.

The read-only commands write nothing — run one, then run `git status`. Four commands write
on purpose and say so before they do: `index` (the index file), `install` and
`gate --install` (vendored tools plus hook wiring, reversible), `check --receipt` (a
receipt file). Everything else — `report`, `explain`, `audit`, `discover`, `survey`, `guide`,
`learn`, `tokens` — reads only.

---

## Run it

No dependencies. Python 3.8+.

```bash
pip install kibsu
python -m kibsu report /path/to/any/repo
```

Or try it without installing anything into your environment: `uvx kibsu report /path/to/any/repo`
(`pipx run kibsu report ...` is the same idea). `kibsu ...` and `python -m kibsu ...` are the
same program; this page writes the long form because it is the one that also works from a
bare clone, with no install at all. One honesty note: the short `kibsu` command ships from
0.9.0 — through 0.8.0 the package declared no command, and `uvx kibsu` answered "does not
provide any executables" (see [CORRECTIONS.md](CORRECTIONS.md), 2026-10-10).

`report` is one of thirteen subcommands — `python -m kibsu --help` lists them all. It is
the one to start with, and the only one you need to read this page.

Real output, against a public repository at commit `3dcbd5c`:

```
  WHAT YOUR AGENTS CANNOT DO HERE YET
  /tmp/superpowers
  --------------------------------------------------------------------------
  x  Find your docs             89 markdown files, no index. An agent must grep the tree.
  +  Know your conventions      consistent frontmatter (description, name) - enforceable.
  +  Prove they followed        13.1% of your procedural instructions are verifiable (above the 7.6% public median).
  x  Resume after a break       1 of 1 artifacts your instructions promise have never existed in any commit.
  ?  Follow your own rules      COULD NOT CHECK - no index file to check history against (looked for docs/index.json, .kibsu/index.json, docs/index.json).
  --------------------------------------------------------------------------
  2 of 5 ready.  1 could NOT be checked - that is not a pass.
  Nothing was written to this repo - run `git status` to confirm.
```

> That block was last re-run against `3dcbd5c` on 2026-10-14, with scorer 0.12.0, and every
> line reproduced, so it was not re-pasted. It was last re-pasted on 2026-10-11, with scorer
> 0.11.0 — the fifth re-paste it has needed, each one recorded. One figure moved that time:
> the median it is compared against, 7.5% to 7.6%, when the survey was re-measured in sentences instead of
> lines (see [CORRECTIONS.md](CORRECTIONS.md), 2026-10-11). The repository's own 13.1% did
> not move, though what stands under it did: 46 of 352 sentences in 9 procedure units, where
> the line count had 50 of 381 in 10. The re-paste before it (2026-10-10, scorer 0.10.0)
> moved one line, and both numbers on it
> were stale for different reasons. 15.6% became 13.1%: the block had not been re-run since
> scorer 0.6.0, while the survey table further down was re-measured three times — so this
> page showed two different figures for the same repository at the same commit. And 9.4%
> became 7.5%: that one was stale *inside the tool*. `report` carries the survey median as a
> constant, and it sat at the scorer-0.6.0 value through three releases while the scorer and
> this page's own table moved on (see [CORRECTIONS.md](CORRECTIONS.md), 2026-10-10 — a
> test now fails while the constant and `evidence/` disagree). Both runs were on Windows; every
> other line matched the earlier Linux paste except for path separators, so those lines are
> kept as pasted. The three earlier re-pastes (Title-case directives under scorer 0.6.0, the
> scaffold-scope change under 0.5.0, the pre-`?`-mark build before that) are narrated in
> this file's git history. A pasted sample a reader could reproduce and get something
> *else* from is the same reproducibility defect as the SHA-less survey table further down,
> and it is recorded rather than quietly corrected for the same reason.

Reproduce it:

```bash
git clone https://github.com/obra/superpowers /tmp/superpowers && cd /tmp/superpowers && git checkout 3dcbd5c
python -m kibsu report /tmp/superpowers
git -C /tmp/superpowers status --porcelain
```

The last command prints nothing. That is the point.

(`report` exits **3** here, not 0 — two questions came back not-ready and one could not
be checked, which is the finding, not a failure to run. The commands are deliberately
*not* chained on `&&` for that reason: `&&` would swallow the `git status` proof in
exactly the case worth proving.)

`+` ready · `x` not ready · `!` not applicable here · `?` **could not be checked**

A check that could not run gets its own line and its own mark, and the summary says so out loud.
Printing one line fewer would make "2 of 4" and "2 of 5" indistinguishable, and the check that
cannot run is reliably the uncomfortable one.

## See a repo that passes

Want to know what a governed workspace looks like — or test kibsu against one built to be
read? Clone **[kibsu-lab](https://github.com/M-Bajalan/kibsu-lab)**: a complete fictional
company (Tuppi Trading Co.) with a seeded deterministic data generator, an armed commit gate,
a skills team for agents, and three machine-checkable tasks — including one that ships
half-finished on a branch, so you can watch an agent *resume* work it never started. Point
any coding agent at its `AGENTS.md`; check its work with one command. The lab scores
**4 of 5** on the report above — and its README shows the exact command trail that proves it.

---

## The five questions

| | question | what it actually tests |
|---|---|---|
| 1 | **Find your docs** | is there an index, or must an agent grep the whole tree on every task? |
| 2 | **Know your conventions** | is there a consistent document shape to enforce, or does every file differ? |
| 3 | **Prove they followed** | what fraction of your instructions could a reviewer verify afterwards? |
| 4 | **Resume after a break** | do the files your instructions promise actually get produced? |
| 5 | **Follow your own rules** | how often have your own commits broken your own written rule? |

Question 5 is a **replay**, not an opinion. It walks your last N commits and asks, for each one,
whether the index you claim to maintain would have gone stale. The answer is a count of your own
commits, which is considerably harder to argue with than a score.

---

## What "verifiable" means

An instruction is **CHECKABLE** if a reviewer could tell, from the repository alone, whether it
happened:

- it is a tick-box, **or**
- it contains a runnable command, **or**
- it names a concrete file artifact, **or**
- it refers to an exit code, a diff, or an assertion

Everything else is **CLAIMABLE**: the only evidence it happened is the agent saying that it did.

**The metric is deliberately biased toward CHECKABLE.** Every ambiguous instruction is counted as
checkable — a bare path mention counts, a bare command word counts. Reported figures are therefore
**ceilings**. The true numbers are lower. `python -m kibsu audit <dir> --definitions` prints the
whole ruleset so you can argue with it (exit 0).

### Which lines

A percentage tells you there is a gap. It does not tell you where to look. `explain` lists the
instructions behind `report`'s number as `path:line  text` — the shape an editor or a terminal
turns into a link. (`explain` ships from package 0.10.0, which is also the first to carry scorer
0.11.0 and count sentences. The two numbering lines are easy to cross: scorer 0.10.0 shipped in
package 0.9.0, so `pip install kibsu==0.9.0` still measures in lines and prints the older
figures.)

```bash
python -m kibsu explain /path/to/any/repo
python -m kibsu explain /path/to/any/repo --unit planner    # one file at a time
```

Real output, for one unit of [kibsu-lab](https://github.com/M-Bajalan/kibsu-lab) at commit
`2d49abf`:

```
  THE LINES BEHIND THE NUMBER
  /tmp/kibsu-lab
  --------------------------------------------------------------------------
  57.8% of your procedural instructions are verifiable: 26 of 45.
  3 instruction(s) can only be confirmed by the agent saying so:

  skills/planner/SKILL.md   3 of 8 cannot be checked
    skills/planner/SKILL.md:21  Create `docs/plans/<YYYY-MM-DD>-<slug>.md` with this shape:
    skills/planner/SKILL.md:46  Check off each task box (`- [ ]` -> `- [x]`) only after its own verify step passed, not when you...
    skills/planner/SKILL.md:54  Never soften a checker to make an unclear phase pass.
  --------------------------------------------------------------------------
  An instruction is CHECKABLE when a reviewer could confirm it from the repository
  alone: it is a tick-box, names a command to run, names a file, or names an exit
  code, a diff or an assertion. `python -m kibsu audit <dir> --definitions` prints the
  whole rule.
  Not every one should be. Judgement has nothing to check, and rewriting it as
  ceremony improves the number and worsens the instruction.
  What is counted is the SENTENCE, not the line: one wrapped over three lines is one
  entry, shown whole at the line it starts on. Where a paragraph's lines break
  changes neither this list nor the number.
  2 doctrine unit(s) not listed - checkability is not a fair test of them (--all-genres lists them).
  Nothing was written to this repo - run `git status` to confirm.
```

Reproduce it — the second line of the block is your clone's path; this one was run on Windows
and is written here as the path the commands below use:

```bash
git clone https://github.com/M-Bajalan/kibsu-lab /tmp/kibsu-lab && cd /tmp/kibsu-lab && git checkout 2d49abf
python -m kibsu explain /tmp/kibsu-lab --unit planner
```

The verdict on every entry is the scorer's own, read back: one function decides both the
percentage and the list, so the two cannot disagree. The number of entries listed is exactly
the gap in the headline — 19 for this repository's `26 of 45` — and a test compares the two
against a separate `audit` run rather than against `explain`'s own arithmetic.

**This sample is the reason the scorer counts sentences.** Its first printing, under scorer
0.10.0, listed five entries for the same file at the same commit, and three of them were
halves of sentences: `verify step passed, not when you believe it should pass.` was one. The
scorer counted physical lines then, so a sentence wrapped over three lines was scored as each
line that carried a directive word. A percentage had hidden that since the first scorer;
printing the lines showed it on the first run, and 47.8% (22 of 46) is 57.8% (26 of 45) now
that the same text is read as its author wrote it (see [CORRECTIONS.md](CORRECTIONS.md),
2026-10-11). One thing the sample still gets wrong is the instrument's, not the repository's:
line 21 names a file and is listed anyway, because `docs/plans/<YYYY-MM-DD>-<slug>.md` is a
path shape the scorer does not recognise. That one is in [Honest limits](#honest-limits).

Only **procedure** units are listed by default. A doctrine unit's 0% is the genre working,
and a list of its lines would read as a to-do list for the one change that makes things worse.
The output says how many units were held back; `--all-genres` lists them, `--full` lifts the
display caps, and `--json` carries every instruction with both verdicts, the reason for each,
and the lines it starts and ends on.

### Genres, and why they matter

Scoring every document on checkability is the obvious way to get this wrong, so units are split
first and procedure-only figures are reported separately:

| genre | describes | is checkability a fair test? |
|---|---|---|
| **procedure** | what to do, in order | yes — this is the headline |
| **doctrine** | how to *think* ("name the assumption before building") | **no.** Produces judgement, not files. 0% here is the genre working, not a defect |
| **persona** | who the agent is ("You are a senior Rust engineer…") | no — it promises nothing |
| **reference** | lookup material: tables, options, definitions | partially |

**Genre is declared in frontmatter** (`genre: doctrine`), not guessed. Auto-detection still runs as
a fallback, and **any disagreement between declaration and detection is printed** — a declaration
cannot quietly buy a better score.

That design exists because auto-detection failed. Ten numbered *principles* are structurally
identical to ten numbered *steps*, and every heuristic tried turned out to be a prior belief
expressed as a regular expression.

### Phantom artifacts

Some instructions mandate an output file. Kibsu extracts those filenames and searches the working
tree **and the full git history** for them. An artifact that has never existed, in any commit, is a
**phantom** — an instruction no model has ever been caught skipping, because nothing was ever
looking.

Scoped to artifacts a document claims are produced *inside its own repository*. Scaffolding
instructions that generate files in the **user's** project are excluded, with the reason printed.
On a shallow clone the result is `UNKNOWN`, never zero.

---

## The survey

Eight public instruction collections, measured at pinned commits. Raw per-repo JSON, each carrying
the SHA it was measured at, is in [`evidence/`](evidence/).

Regenerate the whole table yourself — one honesty note first: `python -m kibsu survey`
clones each collection at its **current HEAD**, so on any day after the pinned date it
measures newer commits and will legitimately print different numbers (that is how the
first correction in [CORRECTIONS.md](CORRECTIONS.md) was discovered). To reproduce *this
table's* figures, check each clone out at the SHA recorded in its
[`evidence/`](evidence/) JSON and point the survey at those clones:

```bash
python -m kibsu survey                    # today's HEADs - comparable method, newer data
```

```bash
# this table exactly: clone each repo, check out the sha from evidence/<slug>.json,
# then audit the pinned clones (SKILL_AUDIT_CLONES reuses them instead of re-cloning).
# Clone dirs MUST be named <owner>__<repo> (e.g. obra__superpowers) - any other name
# silently falls through to a fresh HEAD clone, the exact drift this note warns about:
SKILL_AUDIT_CLONES=/path/to/pinned-clones python -m kibsu survey
```

> **This section previously linked to an `evidence/` directory that had never existed in any
> commit** — a phantom artifact, in the README of a tool built to detect phantom artifacts. It was
> found by an outside reviewer, not by me, and not by four of my own review agents that had passed
> the same file. The directory now exists because the survey was actually re-run; see below for the
> one number that changed when it was.

| repo | sha | units | instr | all% | **proc%** | phantom |
|---|---|---:|---:|---:|---:|---:|
| davila7/claude-code-templates | `91d14a7` | 891 | 20,099 | 14.6% | **15.6%** | 56/129 (43%) |
| obra/superpowers | `3dcbd5c` | 14 | 459 | 11.8% | **13.1%** | 1/1 |
| contains-studio/agents | `a5a480c` | 37 | 734 | 9.5% | **9.7%** | — |
| sanjeed5/awesome-cursor-rules-mdc | `8fbf269` | 5 | 230 | 7.8% | **7.8%** | 2/3 (67%) |
| wshobson/agents | `c4b82b0` | 180 | 2,080 | 6.2% | **7.4%** | 8/18 (44%) |
| vijaythecoder/awesome-claude-agents | `2050f3c` | 33 | 293 | 8.2% | **6.7%** | 1/4 (25%) |
| anthropics/skills | `b29e7cf` | 18 | 672 | 8.0% | **6.2%** | 6/16 (38%) |
| VoltAgent/awesome-claude-code-subagents | `947b44c` | 154 | 3,742 | 1.7% | **1.7%** | 1/1 |

**median procedure-only: 7.6%** · min 1.7% · max 15.6%
**in-scope mandated artifacts: 172 distinct, 75 never existed in any commit (44%)**

`instr` counts sentences, not lines, as of scorer 0.11.0. The phantom column is
*never existed / mandated in scope*; `—` means the collection mandates nothing in scope.

> **These figures were re-measured 2026-10-14 with scorer 0.12.0, at the same pinned SHAs,
> and none of them moved.** The 0.12.0 round closed five places where a soft line break still
> moved a count (issue #113). Across the 6,490 Markdown files of the ten pinned repositories,
> 14 now read differently, none of them a surveyed unit and none in an instruction count
> ([CORRECTIONS.md](CORRECTIONS.md), 2026-10-14). Before it,
> the 0.11.0 round (2026-10-11) changed what is counted: the sentence, not the physical line. The
> median barely moved (7.5 -> 7.6) and that is not the result. Underneath it, individual
> collections moved by up to 1.6 points in both directions, and the mandated-artifact
> column moved most of all (229 -> 172 in scope, 96 -> 75 never existed): under the line
> count, a directive word in one sentence of a long line made every file named anywhere
> on that line a promise. 70 of the 78 mentions that left were pairings of that kind,
> classified by hand; 8 were real promises the stricter reading no longer sees, and 10 of
> the 20 that arrived are real. All of it, with the ones this round got wrong, is in
> [CORRECTIONS.md](CORRECTIONS.md). Before it,
> the 0.10.0 round (2026-09-01) came out of a pre-release audit of the three rounds before it: five
> verb/noun-ambiguous vocabulary entries stopped counting `Note: ...` callouts as
> instructions, and the median moved DOWN (7.7 -> 7.5) - many of those callouts carried
> a backtick command and had been counted checkable. Notes about commands are not
> commands. Before it,
> The 0.9.0 case round moved exactly one number: the existence check is byte-exact now
> - the answer git itself would give - and one mandate whose only instances differ by
> case became the phantom a Linux `cat` always said it was (95 -> 96). Before it,
> The 0.8.0 genre round moved almost nothing, and that is a published result, not a
> disappointment: the mandate rule reclassified 8 of 1,561 units (a doctrine label
> cannot sit on a unit that mandates files), two cells above shifted by a tenth of a
> point, and the median, the phantom counts and both preregistration workspaces are
> unmoved to the digit. The 0.7.0 round before it moved everything:
> The median moved again (9.4% → 7.7%) and every collection's percentage came down: four
> blind spots closed at once — the anchor now reads through markdown emphasis, the verb
> vocabulary grew by 55 census-approved entries, artifact extraction accepts the same
> optional delimiters checkability always did, and every mention of a mandate now counts
> toward its scope. Of the ~6,700 newly visible instructions, **97% are claimable** — the
> blind spots overwhelmingly hid unverifiable instructions, so the older tables flattered
> every repo they measured, this project's own included. Every correction round, with its
> bias direction and the commands to reproduce both sides, is indexed in
> [CORRECTIONS.md](CORRECTIONS.md).

### One number moved, and that is the point of the SHA column

*(This section describes the first correction, 2026-07-29, kept as written. All corrections
since — including the 2026-07-31 scorer fixes — are indexed in
[CORRECTIONS.md](CORRECTIONS.md).)*

An earlier revision of this table published **41 phantoms of 99 (41%)** and carried **no commit
SHAs**. Re-measuring produced **44 of 103 (43%)**.

Every checkable figure — units, instructions, all%, proc%, the median, min and max — matched
exactly. The entire difference is the phantom-artifact count for
`davila7/claude-code-templates`, the most actively maintained collection of the eight: `31/70`
became `34/74` as the repository grew.

Nothing was wrong with the original measurement. It simply **could not be reproduced**, because it
recorded no commit to reproduce it against — the same defect this tool reports as `?  COULD NOT
CHECK` in other people's repositories. Both figures were probably right about different commits,
and there was no way to tell.

Every row now carries the SHA it was measured at, and the raw per-repo JSON is in
[`evidence/`](evidence/).

Two further repositories fell below the sample floor (≥5 procedure units **and** ≥50 procedure
instructions). They are reported but **not ranked**: a percentage from fifteen instructions is noise
wearing a number, and one of the two would otherwise have topped the table at 66.7% off a single
unit.

### The part that was not expected

**One of the eight mandates zero artifacts.** Not "promised and missing" — *never promised anything
at all*. The field splits into two distinct failure modes: collections that make no verifiable claim
in the first place, and collections whose claims fail — at rates from 25% to 100% per collection,
44% in aggregate. (This paragraph said *three* of the eight until 2026-10-11, and its own
`evidence/` had stopped agreeing with it before then: under scorer 0.10.0 one collection
mandated nothing and a second mandated a single file that exists. Corrected with the 0.11.0
re-measurement; see [CORRECTIONS.md](CORRECTIONS.md). An earlier revision still said *five*
of the eight — true under the old scorer. Two
collections moved off that list for two different reasons, both checkable in `evidence/`: obra's
one mandate was never missed — the old scorer extracted it, then the unit-level scaffold sweep
excluded it; the line-level rule returns it to scope. sanjeed5's was genuinely invisible until
`.tsx` joined the extension list. Both turned out phantom — two collections moved from the first
failure mode into the second.)

---

## Verify it yourself

You are about to point a tool at your own repository. Here is everything you can check
first, without taking anything here on trust.

**Nothing to install, nothing to audit.** `pyproject.toml` declares
`dependencies = []`, and the test suite imports nothing outside the standard library
either. There is no transitive dependency tree to review, because there is no
dependency tree.

```bash
python -c "import pathlib,sys; sys.exit(0 if 'dependencies = []' in pathlib.Path('pyproject.toml').read_text() else 1)"
echo $?                  # 0        (bash / zsh)
echo $LASTEXITCODE       # 0        (PowerShell)
```

One line rather than a heredoc, because a heredoc is a bash construct and this line has
to work in PowerShell too — a "verify it yourself" section that only verifies on Unix
is half a claim.

**It is small enough to actually read.** 6,745 lines across 15 files in `kibsu/`, plus
7,498 lines of tests running 342 cases. That is an evening, not a quarter. Count it
yourself rather than believing this paragraph — this is the third revision of these
numbers to ship after the code had already grown past them ([#29](https://github.com/M-Bajalan/kibsu/issues/29)
indexes the incident), so the commands below outrank the prose above them - and as of #29's fix the test
suite enforces that agreement (`tests/test_readme_counts.py` runs the same
measurements and fails while this paragraph is stale):

```bash
python -c "import pathlib,sys; f=sorted(pathlib.Path(sys.argv[1]).glob('*.py')); print(len(f),'files',sum(len(p.read_text(encoding='utf-8').splitlines()) for p in f),'lines')" kibsu
python -m unittest discover -s tests   # prints the case count
```

> An earlier revision published **3,679** here. That figure was not invented — it was
> measured, and then re-measured by a second reviewer who got the same answer. Both used
> PowerShell's `Measure-Object -Line`, which silently **skips empty lines**: 4,241 total
> minus 562 blank lines is exactly 3,679. Two counts agreed because they were not
> independent, which is the failure the second count existed to prevent. The commands above
> are printed so the next reader does not have to trust an instrument they cannot see.

```bash
git clone https://github.com/M-Bajalan/kibsu && cd kibsu
python -m unittest discover -s tests    # exit 0
python -m kibsu report .                # no install step, no config, no network
```

`report` exits **0** when every question came back ready and **3** when something is
not ready or could not be checked. Both are successful runs — 3 is a finding, not a
crash. (Pointed at this repository it returns 3, and the reason is stated in
[Honest limits](#honest-limits).)

**The diagnostic commands do not write to your repository.** This is the design constraint
everything else bends around — scoped honestly: `index`, `install`/`gate --install`, and
`check --receipt` write exactly the artifacts they exist to write, opt-in, named in their
own `--help`; every diagnostic (`report`, `explain`, `audit`, `discover`, `survey`, `guide`,
`learn`) writes nothing, and that claim is two commands to falsify:

```bash
python -m kibsu report /path/to/your/repo
git -C /path/to/your/repo status --porcelain
```

The second command prints nothing. If it ever prints something, that is a bug worth
an issue. Note the `;`-style separation rather than `&&`: chaining on `&&` would skip
the proof precisely when `report` returns 3, which is most of the time and is the
case you most want proven.

**The published package has verifiable provenance.** Releases go to PyPI through
GitHub's Trusted Publishing (OIDC), which generates [PEP 740](https://peps.python.org/pep-0740/)
attestations tying each artifact to the exact workflow run and commit that built it —
visible on the [PyPI project page](https://pypi.org/project/kibsu/). No API token
exists for this project, in CI settings or anywhere else; `release.yml` explains why.

**Two outside scanners look at this code, and their findings are public.**
[CodeQL](https://github.com/M-Bajalan/kibsu/security/code-scanning) scans the Python
*and* the workflow files on every push and weekly; results appear in the Security tab
whether they are flattering or not.
[OpenSSF Scorecard](https://scorecard.dev/viewer/?uri=github.com/M-Bajalan/kibsu)
rates the release path — branch protection, token permissions, pinned dependencies —
and publishes the number to a public dataset recomputed by someone else's
infrastructure. That is what makes the badge worth having; a badge served from this
repository would be decoration.

**What those two do not tell you:** Scorecard measures *process*, not correctness. A
good score means the release path is hard to tamper with. It says nothing about
whether the numbers this tool reports are right — that is what the SHAs in
[`evidence/`](evidence/) and the Honest Limits below are for. Confusing the two is
precisely the error this project was built to name.

**What you cannot verify from here:** the provenance scrub described in
[PROVENANCE.md](PROVENANCE.md) is not in this repository and will not be — the
denylist it scans for is itself the sensitive artifact. What you *can* check is the
absence it claims: search this tree for anything resembling a company, a market, a
customer or an internal system. Finding none is a falsifiable result, and it does not
require the tool.

The improvement experiment on the team skills is **pre-registered** — baseline, falsifiable
predictions, and the standing rule that a *rising* doctrine score is disqualifying:
[PREREGISTRATION.md](PREREGISTRATION.md), committed before any skill was rewritten.

Contribution rules — including the four that are non-negotiable — are in
[CONTRIBUTING.md](CONTRIBUTING.md).

---

## Honest limits

Read these before quoting anything above.

- **`obra/superpowers` ships a separate eval harness** that drives real agent CLIs and grades
  whether a skill was followed. Kibsu reads only *documents*, so it cannot see that. The real
  enforceability of that repo is higher than 13.1%. This is the strongest counter-example to the
  entire approach, and it belongs at the top of the limits rather than buried at the bottom.
- **The metric is a heuristic.** Biased generous by design. Ceilings, not measurements.
- **What is counted is the sentence, and the cut is conservative on purpose.** Through scorer
  0.10.0 it was the physical line, which scored a hard-wrapped sentence once per line that
  carried a directive word; 0.11.0 reads a paragraph, list item or blockquote the way Markdown
  renders it and cuts it into sentences. What that leaves, each one measured or tested rather
  than assumed:
  - **A missed boundary merges two sentences; it never invents one.** A boundary needs
    sentence punctuation followed by a capital letter or a code span, so a sentence that
    opens in lower case, `e.g. Foo`, and a run of initials are left whole. The rule knows
    English capitals only.
  - **Lines with no blank line, list marker or punctuation between them are one sentence**,
    exactly as a renderer would run them together. Six lines that each open with `✅` are one
    paragraph to Markdown and one sentence here.
  - **An imperative behind a label is seen only by its modal.** `**Pro tip:** Create a setup
    script` does not open with its verb, so it counts as an instruction only when the
    sentence also carries `must`, `never` or the like. Reading the colon as a boundary would
    find them, and was measured on a draft of this reader: about 2,000 more instructions in
    the largest collection, nearly all of them claimable, and a median near 5.6% instead of
    7.6%. Left out as a round of its own - it changes what an instruction is, not what is
    counted.
  - **A tick-box item counts once**, however many sentences it holds: one box, one promise.
  - **In two places the file is read as its reader sees it, not as a renderer would:** a
    fence on the line under a tag (`<Good>` then a fence) is a fence, and a pipe table is a
    table even when its delimiter row has the wrong number of cells (1 table in 1,241 here).
  - **A mandated file is read from a sentence that is itself an instruction.** Of the 78
    file mentions that stopped counting as promises in this page's survey, 70 were a verb in
    one sentence paired with a file in another, and 8 were real: `After collecting results
    from all subagents, combine them and write to <planning_dir>/claude-research.md` is not
    seen as an instruction, because it does not open with its verb. Named one by one in
    [CORRECTIONS.md](CORRECTIONS.md), 2026-10-11.
  - **Where a soft line break falls inside a block changes no number.** Held by a property
    test in the suite, after a fuzz that re-wrapped all 1,477 surveyed files against an
    independent CommonMark parser: no instruction count, checkable count or sentence moved;
    in the two reader-over-renderer places above, 4 files can still change a genre signal.
  A smaller sibling from `explain`'s first listing: a templated path written with angle
  brackets (`docs/plans/<date>-<slug>.md`) is not read as naming a file.
- **Persona collections are not badly written**, they are a different genre. Scoring them on
  checkability was the first mistake this tool made.
- **Low checkability has not been shown to produce worse outcomes.** Nobody has demonstrated that.
  The demonstrated finding is that *nobody can tell either way* — the weaker claim, the more
  defensible one, and the only one worth acting on.
- **N is small** for several repositories. Sample floors are enforced, not assumed.
- **Genre auto-detection is weak.** Declare it.
- **This repository scores 0 of 5 on its own report, and the number is honest.** Run
  `python -m kibsu report .` here and you get `0 of 5 ready. 3 could NOT be checked` —
  worse than every collection in the survey table. The reason is that kibsu is a tool, not
  an instruction collection: there is no `AGENTS.md`, no `skills/`, and no index, so three
  of the five questions have nothing to measure and say so rather than scoring zero. That
  is the `?` mark doing its job on its own author. It is also the strongest argument for
  the write-side work that is next on the roadmap — a tool that cannot yet furnish the
  artifacts it asks other repositories for. Anyone using this against the project is making
  a fair point, and it is written here first so they do not have to.
- **The Scorecard badge above says 4.8, and one of the points it deducts is for a genre
  mismatch — which is this project's own argument, arriving inside its own badge.**
  `Dependency-Update-Tool: 0`, because there is no Dependabot config for Python packages.
  There are no Python packages. `dependencies = []` is the first hard rule in
  [CONTRIBUTING.md](CONTRIBUTING.md), so the only possible score on a check for *keeping
  dependencies updated* is zero, permanently, by design. Scoring a repository on a dimension
  it deliberately does not have is exactly the mistake this tool made first and now reports
  in others: **the metric is measuring the wrong genre.** Adding a config block that can
  never fire, to move a number, would have been the Goodhart response.
  What made it interesting is that the check was also **right about something it did not
  say.** CI actions are dependencies too, and those were genuinely unwatched — so
  `.github/dependabot.yml` now exists for the `github-actions` ecosystem only, and every
  action in every workflow is pinned to an immutable commit SHA it keeps current. Wrong
  about the thing it named, right about a thing it pointed at. That is a better outcome than
  either obeying it or dismissing it, and it is the argument for reading a low score instead
  of chasing it.
  One more thing worth borrowing rather than criticising: two of Scorecard's checks return
  **`-1`, meaning *could not be checked*** — not zero. It reaches for the same three-state
  honesty this tool argues for with its `?` mark, on the same kind of question. A rating
  system that distinguishes *bad* from *unknown* is doing something most do not.

---

## The name

*kibsu* (𒆠𒍑, KI.UŠ) is Akkadian, derived from *kabāsu*, "to tread":

> **1.** "tread, imprint" of a foot — *kibsu redû*, "to follow a track"; *ša kibsi*, "tracker"
> **2.** "track, route"; transferred, "mode of life, behaviour, course of life"
> **3.** mathematical: "way of calculation"

— *A Concise Dictionary of Akkadian*, Black, George & Postgate, Harrassowitz ²2000

The trace left behind, the course of conduct, and the method of reckoning. The tool is all three.

## License

MIT. See [LICENSE](LICENSE) and [PROVENANCE.md](PROVENANCE.md).
