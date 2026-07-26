# Kibsu

**What can your agents not do in this repository yet?**

You have written instructions for coding agents — `AGENTS.md`, `CLAUDE.md`, a `skills/` directory,
`.cursorrules`. Kibsu reads them alongside your git history and reports which of those instructions
anyone could actually verify were followed, and which ones only work when a human remembers.

It writes nothing. Run it, then run `git status`.

---

## Run it

No dependencies. Python 3.8+.

```bash
python -m kibsu /path/to/any/repo
```

Real output, against a public repository at commit `3dcbd5c`:

```
  WHAT YOUR AGENTS CANNOT DO HERE YET
  /tmp/superpowers
  --------------------------------------------------------------------------
  x  Find your docs             89 markdown files, no index. An agent must grep the tree.
  +  Know your conventions      consistent frontmatter (description, name) - enforceable.
  +  Prove they followed        19.8% of your procedural instructions are verifiable
                                (above the 11.1% public median).
  x  Resume after a break       your instructions promise no artifacts at all - nothing
                                survives the session, and nothing can be checked.
  !  Follow your own rules      no index to check history against.
  --------------------------------------------------------------------------
  2 of 5 ready.
  Nothing was written to this repo - run `git status` to confirm.
```

Reproduce it:

```bash
git clone https://github.com/obra/superpowers /tmp/superpowers && cd /tmp/superpowers && git checkout 3dcbd5c
python -m kibsu /tmp/superpowers && git -C /tmp/superpowers status --porcelain
```

The second command prints nothing. That is the point.

`+` ready · `x` not ready · `!` not applicable here · `?` **could not be checked**

A check that could not run gets its own line and its own mark, and the summary says so out loud.
Printing one line fewer would make "2 of 4" and "2 of 5" indistinguishable, and the check that
cannot run is reliably the uncomfortable one.

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
**ceilings**. The true numbers are lower. `--definitions` prints the whole ruleset so you can argue
with it.

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

Regenerate the whole table yourself:

```bash
python -m kibsu survey
```

> **This section previously linked to an `evidence/` directory that had never existed in any
> commit** — a phantom artifact, in the README of a tool built to detect phantom artifacts. It was
> found by an outside reviewer, not by me, and not by four of my own review agents that had passed
> the same file. The directory now exists because the survey was actually re-run; see below for the
> one number that changed when it was.

| repo | sha | units | instr | all% | **proc%** | phantom |
|---|---|---:|---:|---:|---:|---:|
| davila7/claude-code-templates | `91d14a7` | 891 | 12,578 | 21.3% | **22.9%** | 34/74 (46%) |
| obra/superpowers | `3dcbd5c` | 14 | 267 | 18.0% | **19.8%** | — |
| wshobson/agents | `c4b82b0` | 180 | 807 | 10.8% | **12.8%** | 4/7 (57%) |
| contains-studio/agents | `a5a480c` | 37 | 564 | 12.4% | **12.7%** | — |
| anthropics/skills | `b29e7cf` | 18 | 310 | 15.8% | **9.4%** | 6/22 (27%) |
| sanjeed5/awesome-cursor-rules-mdc | `8fbf269` | 5 | 124 | 8.9% | **8.9%** | — |
| vijaythecoder/awesome-claude-agents | `2050f3c` | 33 | 186 | 7.5% | **6.2%** | — |
| VoltAgent/awesome-claude-code-subagents | `947b44c` | 154 | 2,775 | 2.1% | **2.2%** | — |

**median procedure-only: 11.1%** · min 2.2% · max 22.9%
**in-scope mandated artifacts: 103 distinct, 44 never existed in any commit (43%)**

### One number moved, and that is the point of the SHA column

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

**Five of the eight mandate zero artifacts.** Not "promised and missing" — *never promised anything
at all*. The field splits into two distinct failure modes: collections that make no verifiable claim
in the first place, and collections whose claims fail roughly 40% of the time.

---

## Honest limits

Read these before quoting anything above.

- **`obra/superpowers` ships a separate eval harness** that drives real agent CLIs and grades
  whether a skill was followed. Kibsu reads only *documents*, so it cannot see that. The real
  enforceability of that repo is higher than 19.8%. This is the strongest counter-example to the
  entire approach, and it belongs at the top of the limits rather than buried at the bottom.
- **The metric is a heuristic.** Biased generous by design. Ceilings, not measurements.
- **Persona collections are not badly written**, they are a different genre. Scoring them on
  checkability was the first mistake this tool made.
- **Low checkability has not been shown to produce worse outcomes.** Nobody has demonstrated that.
  The demonstrated finding is that *nobody can tell either way* — the weaker claim, the more
  defensible one, and the only one worth acting on.
- **N is small** for several repositories. Sample floors are enforced, not assumed.
- **Genre auto-detection is weak.** Declare it.

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
