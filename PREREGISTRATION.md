# Pre-registration

This project is about to use its own metric to improve the skill files that the metric
measures. That is a conflict of interest, and the only honest way to run it is to write down
the "before" and the prediction **first**, in public, where they cannot be quietly adjusted
afterwards to match whatever happened.

So: this file is committed before a single skill is rewritten. Everything below is a claim
made in advance. If the results come out differently, the results win and this file stays
exactly as it is — that is the whole point of it existing.

## Why this file is dated before the work

A before/after story is only worth reading if the "before" was recorded before the "after"
was known. Reconstructing a baseline from git history afterwards is the exact class of
after-the-fact evidence this project spends its entire argument against, and it would be the
easiest thing in the world to do by accident and in good faith.

The ordering is checkable, not asserted: the baseline commit predates every commit that edits
a team skill, and as of this writing **no skill has been edited since** — the skills tree is
byte-identical to its state at the baseline SHA. Improvement has not started.

---

## 1. The baseline

There are two baselines, they measure different things, and conflating them would be the
first dishonest move available. Each is labelled.

### 1a. The origin workspace — directional, and you cannot check it

| | |
|---|---|
| recorded | 2026-07-26 18:51:59 (+03), before any skill was touched |
| method | `kibsu audit <skills dir> --json --artifacts`, run at the pinned SHA |
| **procedure-genre only** | **28.65% checkable** — 208 of 726 instructions across 36 units |
| doctrine-genre | **0.0% checkable** — 0 of 34 instructions across 3 units |
| all genres | 24.71% — 295 of 1,194 instructions across 79 units |
| public median (procedure-only) | 11.1% across 8 surveyed public collections |

This is measured on a **private** workspace at a SHA in a **private** repository. You cannot
resolve that SHA, you cannot re-run the command, and you should therefore treat every number
in this sub-section as **directional only** — our word, offered as our word.

The raw audit JSON is not published and will not be. It is a per-unit map of a private
workspace: file paths, skill names, and the instruction text inside them. Publishing it to
prove a percentage would leak precisely what this project's scrub exists to keep out, in
order to win an argument about honesty. The number is kept; the evidence behind it stays
where it belongs, and this paragraph is the cost of that choice, stated rather than hidden.

### 1b. kibsu-lab — reproducible, and you should hold us to this one

The public workspace at [`kibsu-lab`](https://github.com/M-Bajalan/kibsu-lab), measured at
commit `8bec5ee`:

| | |
|---|---|
| **procedure-genre only** | **46.7% checkable** — 14 of 30 instructions across 3 units |
| doctrine-genre | **0.0% checkable** — 0 of 7 instructions across 1 unit |
| `kibsu report` exit code | 3 |

Reproduce it yourself — clone the lab at that commit and follow its Quickstart verbatim. If
your numbers differ from these, one of us is wrong and we would like to know which.

---

## 2. The prediction

Written before the work, in falsifiable form.

1. **Procedure-genre checkability will rise.** Procedure units mandate steps that produce
   artifacts, and an artifact can be looked for. Rewriting them to name the command and the
   exit code is a real improvement, and the metric should reward it.

2. **Doctrine-genre checkability will stay at ≈0%.** Doctrine produces judgment, not
   artifacts. There is nothing for a checker to find, and there should not be. The doctrine
   baseline is currently **exactly 0.0%** in both workspaces, which makes this prediction
   unusually sharp: *any* upward movement at all is the signal.

3. **A rising doctrine score means the metric was gamed — treat it as disqualifying.**
   Not as a mixed result, not as a bonus. If a later report shows doctrine climbing, the most
   probable explanation is that judgment-shaped guidance was rewritten into tick-boxes to make
   a number go up, which makes the guidance worse while making the score better. That is
   Goodhart's law, this project's own founding complaint, arriving in this project's own
   files. The reader is invited to check this and to say so loudly.

4. **The aggregate all-genre percentage is not the headline and will not be quoted as one.**
   It moves when the mix of unit genres moves, which is not the same as anything improving.
   Procedure-only is the fair comparison and the only one we will lead with.

### What "flat" would mean

If procedure-genre checkability does not move after the rewrites, that is a published result,
not a failed experiment to be re-run until it cooperates. It would mean one of: the units were
already as checkable as their content allows; the improvements were cosmetic; or the metric
does not detect the kind of improvement that was actually made. All three are worth knowing
and all three go in the write-up.

---

## 3. How the work will be published

- **Every rewrite ships as a text diff.** Not a summary of a diff, not a percentage: the diff.
  The reader judges each change on its merits and does not have to take the aggregate on
  trust. A rewrite that looks worse in the diff but better in the number is exactly the case
  this rule exists to expose.
- **Every published figure carries the SHA it was measured at**, per the rule already in
  [CONTRIBUTING.md](CONTRIBUTING.md).
- **Failed attempts stay in the write-up.** A lab notebook with no failed experiments is not a
  lab notebook.
- **This file is not edited to match the results.** Corrections to errors of fact get an
  appended, dated note; the original text stays legible.

---

## Honest limits of this pre-registration

- It pre-registers a **direction**, not a magnitude. No target percentage is named, because
  naming one would create the incentive this file exists to disarm.
- The genre taxonomy that makes clause 2 meaningful is a **declared hypothesis**, not a
  validated instrument. Auto-detection disagrees with declared genre on some units. If the
  taxonomy turns out not to carve reality at its joints, the doctrine prediction becomes
  untestable rather than false — and that outcome also gets published.
- The people running this experiment are the people who wrote the skills being measured and
  the tool doing the measuring. That is not a conflict this document can remove. It is a
  conflict this document is trying to make expensive to act on.

---

## Appended note — 2026-07-31: the instrument changed, so everything was re-measured

Per this file's own rule ("Corrections to errors of fact get an appended, dated note; the
original text stays legible"), nothing above this line has been edited.

**What happened.** After cycle 1 of the experiment ran (2026-07-28: a reclassification pass
and one rewrite, results published in the cycle record with diffs), an audit of the scorer
itself confirmed five measurement bugs in `audit.py` — see
[CORRECTIONS.md](CORRECTIONS.md), 2026-07-31 entry. They are fixed in scorer 0.5.0. An
instrument that changes mid-experiment invalidates before/after comparisons unless both
sides are re-measured with the corrected instrument, so both baselines in section 1, and
cycle 1's own endpoints, were re-measured at the same pinned states.

**Re-measurement, origin workspace (1a) — identical under both instruments:**

| pinned state | scorer 0.3.0 (published) | scorer 0.5.0 (re-measured) |
|---|---|---|
| baseline, procedure-only | 28.7% — 208/726, 36 units | 28.7% — 208/726, 36 units |
| baseline, doctrine | 0.0% — 0/34, 3 units | 0.0% — 0/34, 3 units |
| post-cycle-1, procedure-only | 31.4% — 251/800, 39 units | 31.4% — 251/800, 39 units |
| post-cycle-1, doctrine | 0.0% — 0/34, 3 units | 0.0% — 0/34, 3 units |

The five bugs' triggering shapes (nested fences, templated artifact mandates, scaffold
vocabulary on mandate lines, uppercase extensions) evidently do not occur in these files'
counted regions: the corrected scorer reproduces every published origin number
digit-for-digit, including cycle 1's result. Cycle 1 stands as published. (The directional
caveat of section 1a still applies — private repo, our word.)

**Re-measurement, kibsu-lab (1b) and the public survey — also unmoved:**

| | scorer 0.3.0 (published) | scorer 0.5.0 (re-measured) |
|---|---|---|
| 1b kibsu-lab @ `8bec5ee`, procedure-only | 46.7% (14/30, 3 units) | 46.7% (14/30, 3 units) |
| 1b kibsu-lab @ `8bec5ee`, doctrine | 0.0% (0/7, 1 unit) | 0.0% (0/7, 1 unit) |
| public median (procedure-only), 8 ranked collections | 11.1% | 11.1% |

The survey's aggregate phantom line did move (43% to 42%, with both counts rising — see
CORRECTIONS.md); the baselines this experiment is measured against did not. Future cycles
compare against the scorer-0.5.0 column: same instrument on both sides, or the comparison
is noise.

**A ruling this file must make in advance.** Clause 3 of section 2 declares a rising
doctrine score disqualifying evidence of gaming. That clause is about *documents being
rewritten* to chase the metric. A doctrine score that moves because the *scorer was
repaired* — for example, fence-tracking bugs that previously leaked example text into a
doctrine unit's counts — is a different event: the guidance text is byte-identical; only
the measurement changed. So the ruling: **doctrine movement attributable solely to an
instrument correction, measured on unedited files, does not trip clause 3; doctrine
movement after skill rewrites, measured with a stable instrument, still does.** This is the
project interpreting its own disqualification rule in its own favour, which is exactly why
the ruling is stated here, dated, in the same commit as the re-measurement — the reader who
finds the distinction self-serving is invited to say so now, not after. (As it happens, no
doctrine number moved at all this time; the ruling stands for future instrument changes
regardless.)

**A clause the original lacked, now standing:** any change to the scorer mid-experiment
requires a re-baseline of both workspaces and a dated note here, before any "after" numbers
are published. An instrument that changes silently between the before and the after is the
oldest trick in the book, and this file would rather name the trick than be suspected of it.

## Appended note — 2026-08-07: the instrument changed again, so everything was re-measured again

The clause directly above this note fired for the first time. Scorer 0.6.0 fixes three
defects found by a full review of the repository — chiefly that `MODALS` was
case-sensitive, so ordinary Title-case directives ("- Must run the tests.") were never
counted as instructions at all; see [CORRECTIONS.md](CORRECTIONS.md), 2026-08-07 entry.
This fix DOES bite these files' counted regions (unlike the 0.5.0 round's five), so this
time the numbers move — denominators grow everywhere, percentages come down, and the
comparison column for all future cycles is the 0.6.0 one below.

**Re-measurement, origin workspace (1a), same pinned states:**

| pinned state | scorer 0.5.0 (previous column) | scorer 0.6.0 (re-measured) |
|---|---|---|
| baseline, procedure-only | 28.7% — 208/726, 36 units | **27.1% — 240/887, 36 units** |
| baseline, doctrine | 0.0% — 0/34, 3 units | **0.0% — 0/37, 3 units** |
| post-cycle-1, procedure-only | 31.4% — 251/800, 39 units | **29.3% — 283/967, 39 units** |
| post-cycle-1, doctrine | 0.0% — 0/34, 3 units | **0.0% — 0/37, 3 units** |

**Re-measurement, kibsu-lab (1b) and the public survey:**

| | scorer 0.5.0 (previous column) | scorer 0.6.0 (re-measured) |
|---|---|---|
| 1b kibsu-lab @ `8bec5ee`, procedure-only | 46.7% (14/30, 3 units) | **42.4% (14/33, 3 units)** |
| 1b kibsu-lab @ `8bec5ee`, doctrine | 0.0% (0/7, 1 unit) | **0.0% (0/7, 1 unit)** |
| public median (procedure-only), 8 ranked collections | 11.1% | **9.4%** |

What survives re-instrumentation, which is the point of publishing both columns: cycle 1's
improvement is still there and still the same shape (27.1% → 29.3% under 0.6.0; the old
instrument read the same move as 28.7% → 31.4%) — the gain shrank with the growing
denominator but did not vanish, and no unit changed genre. Doctrine checkability is a hard
0.0% at every stage under both instruments, so clause 3's disqualification floor is
untouched, and the 2026-07-31 ruling on instrument-caused movement was not even needed —
the doctrine numerator stayed zero on its own. Per this file's own rule, nothing above the
2026-07-31 note has been edited; the checkable counts in both tables above were produced by
`kibsu audit <skills dir> --json` at the pinned states, with the private origin states
carrying the same directional-only caveat as section 1a.


## Appended note — 2026-08-31: the instrument changed a third time, so everything was re-measured a third time

The standing clause fired again. Scorer 0.7.0 closes four blind spots found by the
2026-08-28 audit — the imperative anchor reads through markdown emphasis, the verb
vocabulary grew by 55 census-approved entries, artifact extraction accepts the delimiters
checkability always did, and every mention of a mandate counts toward its scope — see
[CORRECTIONS.md](CORRECTIONS.md), 2026-08-31 entry. These fixes BITE these files' counted
regions harder than any round before them (cycle 2's own record documents working AROUND
the emphasis blindness by de-bolding verbs, movement it labelled "format visibility"), so
denominators grow everywhere, percentages come down, and the comparison column for all
future cycles is the 0.7.0 one below. The post-cycle-2 state, published since the last
note, is re-measured alongside the original two.

**Re-measurement, origin workspace (1a), same pinned states:**

| pinned state | scorer 0.6.0 (previous column) | scorer 0.7.0 (re-measured) |
|---|---|---|
| baseline, procedure-only | 27.1% — 240/887, 36 units | **24.0% — 249/1,036, 36 units** |
| baseline, doctrine | 0.0% — 0/37, 3 units | **0.0% — 0/45, 3 units** |
| post-cycle-1, procedure-only | 29.3% — 283/967, 39 units | **25.9% — 295/1,141, 39 units** |
| post-cycle-1, doctrine | 0.0% — 0/44, 3 units | **0.0% — 0/53, 3 units** |
| post-cycle-2, procedure-only | 29.9% — 294/982, 39 units | **26.7% — 306/1,147, 39 units** |
| post-cycle-2, doctrine | 0.0% — 0/44, 3 units | **0.0% — 0/53, 3 units** |

**Re-measurement, kibsu-lab (1b) and the public survey:**

| | scorer 0.6.0 (previous column) | scorer 0.7.0 (re-measured) |
|---|---|---|
| 1b kibsu-lab @ `8bec5ee`, procedure-only | 42.4% (14/33, 3 units) | **42.4% (14/33, 3 units) — unmoved** |
| 1b kibsu-lab @ `8bec5ee`, doctrine | 0.0% (0/7, 1 unit) | **0.0% (0/9, 1 unit)** |
| public median (procedure-only), 8 ranked collections | 9.4% | **7.7%** |

What survives re-instrumentation, which remains the point of publishing every column: both
cycles' improvements are still there and still the same shape — 24.0% → 25.9% → 26.7%
under 0.7.0, where 0.6.0 read the same two moves as 27.1% → 29.3% → 29.9%. The gains
shrink with the growing, truer denominators and do not vanish, and no unit changed genre.
The lab is the one place the new instrument found nothing to correct: its rewrites already
carried their verbs unemphasized and their mandates backticked, so its procedure figures
reproduce digit-for-digit. Doctrine checkability is a hard 0.0% at every stage under every
instrument this project has shipped — clause 3's floor is untouched, and the 2026-07-31
ruling on instrument-caused movement was again not needed. The pin authentication for
these tables was mechanical, not asserted: the 0.6.0 instrument was re-run first at every
pinned state and required to reproduce the previous column digit-for-digit before the
0.7.0 column was trusted. Per this file's own rule, nothing above the earlier notes has
been edited.
