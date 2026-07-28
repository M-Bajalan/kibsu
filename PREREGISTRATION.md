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
