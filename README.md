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
receipt file). Everything else — `report`, `audit`, `discover`, `survey`, `guide`, `learn`,
`tokens` — reads only.

---

## Run it

No dependencies. Python 3.8+.

```bash
python -m kibsu report /path/to/any/repo
```

`report` is one of twelve subcommands — `python -m kibsu --help` lists them all. It is
the one to start with, and the only one you need to read this page.

Real output, against a public repository at commit `3dcbd5c`:

```
  WHAT YOUR AGENTS CANNOT DO HERE YET
  /tmp/superpowers
  --------------------------------------------------------------------------
  x  Find your docs             89 markdown files, no index. An agent must grep the tree.
  +  Know your conventions      consistent frontmatter (description, name) - enforceable.
  +  Prove they followed        15.6% of your procedural instructions are verifiable (above the 9.4% public median).
  x  Resume after a break       1 of 1 artifacts your instructions promise have never existed in any commit.
  ?  Follow your own rules      COULD NOT CHECK - no index file to check history against (looked for docs/index.json, .kibsu/index.json, docs/index.json).
  --------------------------------------------------------------------------
  2 of 5 ready.  1 could NOT be checked - that is not a pass.
  Nothing was written to this repo - run `git status` to confirm.
```

> That block was re-run against `3dcbd5c` with scorer 0.6.0 on 2026-08-07 before being
> pasted here — the third re-paste this block has needed, each one recorded. This round:
> 19.8% became 15.6% and the median it is compared against became 9.4%, because the scorer
> now counts Title-case directives ("- Must run the tests.") it used to skip entirely —
> obra's instruction denominator grew from 265 to 339 with the checkable count barely
> moving (see [CORRECTIONS.md](CORRECTIONS.md), 2026-08-07). Two smaller honesty notes on
> this paste: it was produced on Linux, the platform the repro commands below target, so
> the lookup-paths line now shows forward slashes — the previous paste's `docs\index.json`
> was quietly disclosing a Windows run; and the long lines are no longer re-wrapped for
> README width — the block now matches the tool's byte-for-byte line structure. The prior
> two re-pastes (the scaffold-scope change under 0.5.0, the pre-`?`-mark build before
> that) are narrated in this file's git history. A pasted sample a reader could reproduce
> and get something *else* from is the same reproducibility defect as the SHA-less survey
> table further down, and it is recorded rather than quietly corrected for the same
> reason.

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
| davila7/claude-code-templates | `91d14a7` | 891 | 18,888 | 15.7% | **16.6%** | 73/172 (42%) |
| obra/superpowers | `3dcbd5c` | 14 | 419 | 12.2% | **13.1%** | 1/1 |
| contains-studio/agents | `a5a480c` | 37 | 738 | 9.5% | **9.7%** | — |
| wshobson/agents | `c4b82b0` | 180 | 1,922 | 6.2% | **7.8%** | 8/14 (57%) |
| anthropics/skills | `b29e7cf` | 18 | 501 | 14.4% | **7.6%** | 12/39 (31%) |
| vijaythecoder/awesome-claude-agents | `2050f3c` | 33 | 290 | 8.6% | **6.8%** | — |
| sanjeed5/awesome-cursor-rules-mdc | `8fbf269` | 5 | 210 | 6.2% | **6.2%** | 1/2 (50%) |
| VoltAgent/awesome-claude-code-subagents | `947b44c` | 154 | 3,730 | 1.7% | **1.8%** | 1/1 |

**median procedure-only: 7.7%** · min 1.8% · max 16.6%
**in-scope mandated artifacts: 230 distinct, 96 never existed in any commit (42%)**

> **These figures were re-measured 2026-08-31 with scorer 0.9.0, at the same pinned SHAs.**
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

**Three of the eight mandate zero artifacts.** Not "promised and missing" — *never promised anything
at all*. The field splits into two distinct failure modes: collections that make no verifiable claim
in the first place, and collections whose claims fail — at rates from 33% to 100% per collection,
43% in aggregate. (An earlier revision said *five* of the eight — true under the old scorer. Two
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

**It is small enough to actually read.** 5,945 lines across 14 files in `kibsu/`, plus
5,928 lines of tests running 238 cases. That is an evening, not a quarter. Count it
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
own `--help`; every diagnostic (`report`, `audit`, `discover`, `survey`, `guide`, `learn`)
writes nothing, and that claim is two commands to falsify:

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
  enforceability of that repo is higher than 15.6%. This is the strongest counter-example to the
  entire approach, and it belongs at the top of the limits rather than buried at the bottom.
- **The metric is a heuristic.** Biased generous by design. Ceilings, not measurements.
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
