# Corrections

Every published number this project has had to correct, in one place, newest first. Each
entry names what was wrong, which direction the error biased the published figure, the old
and new values, and how to reproduce both sides. This file exists because the project
expects to keep finding errors in its own instrument; the alternative is not finding them.

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
