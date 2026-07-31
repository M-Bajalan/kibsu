# Corrections

Every published number this project has had to correct, in one place, newest first. Each
entry names what was wrong, which direction the error biased the published figure, the old
and new values, and how to reproduce both sides. This file exists because the project
expects to keep finding errors in its own instrument; the alternative is not finding them.

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

Both phantom counts rose — the corrected scorer *finds more mandates* (line-level scope,
templated paths, `.tsx`/`.jsx`) — and the rate still fell a point, because the denominator
grew faster than the numerator. Three of the eight ranked collections are numerically
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
