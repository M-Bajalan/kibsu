# Contributing

This project reports on whether other people's instructions can be verified. Its
own contribution rules are therefore written to be checkable: every rule below is
either a tick-box, a command you can run, or an exit code you can compare. If you
find a rule here that can only be confirmed by someone's word, that is a bug in
this file and worth an issue on its own.

Before anything else, the short version: **the four hard rules are non-negotiable,
the pre-PR checklist is copy-pasteable, and a check that has never failed will be
sent back.**

---

## The four hard rules

### 1. Zero runtime dependencies

`pyproject.toml` declares `dependencies = []`. It stays that way.

A pull request that adds a runtime dependency will be closed, however good the
library is. The reason is not minimalism for its own sake: this tool's entire
proposition is that you can audit it before pointing it at your own repository,
and "audit it" has to mean something a person can finish in an evening. Every
dependency added is a package the reader now has to trust instead of read.

Verify:

```bash
python -c "import pathlib,sys; sys.exit(0 if 'dependencies = []' in pathlib.Path('pyproject.toml').read_text() else 1)"
echo $?                  # must print 0   (bash / zsh)
echo $LASTEXITCODE       # must print 0   (PowerShell)
```

One line, not a heredoc, so it runs in PowerShell as well as bash — contributors are not
all on Unix and a check that only runs on one platform is a check half the reviewers
cannot repeat. This one has a working negative control too: point it at a
`pyproject.toml` carrying a real dependency and it exits 1. Per rule 4, that is the half
that matters.

Standard library only, in the package and in the tests. There is no dev-dependency
escape hatch either — `tests/` imports nothing outside the stdlib.

### 2. Tests are stdlib `unittest`

```bash
python -m unittest discover -s tests
echo $?    # must print 0
```

No pytest, no tox, no nox, no plugins, no conftest. `unittest` ships with the
interpreter, which means rule 1 and rule 3 stay true for the test suite as well as
the package. If a test needs a fixture framework to be readable, the test is doing
too much.

Python 3.8 is the declared floor (`requires-python = ">=3.8"`) and CI runs it. Do
not use syntax or stdlib APIs newer than 3.8 — the walrus operator is fine, `match`
statements and `dict | dict` are not.

### 3. Clone-and-run must survive

Someone must be able to do this, on a machine with nothing installed but Python,
and get output:

```bash
git clone https://github.com/M-Bajalan/kibsu && cd kibsu
python -m kibsu report .
echo $?    # 3 here, and 3 is fine — see below
```

`report` exits **0** when every question is ready and **3** when something is not ready
or could not be checked. Against this repository it returns **3**, for the reason given
in the README's Honest Limits. Treat 0 and 3 as "it ran"; anything else is the bug.

No `pip install`, no build step, no config file, no network access, no environment
variables, no first-run setup. If your change means that sequence no longer works,
the change is wrong even if every test passes.

There is a second half to this rule, and it is the one most easily broken by
accident: **kibsu writes nothing to the repository it is pointed at.** Any new
feature that wants to persist something writes it outside the target tree, or it
does not ship. The proof is two commands and it is in the README for a reason:

```bash
python -m kibsu report /path/to/some/repo
git -C /path/to/some/repo status --porcelain    # must print nothing
```

Not chained on `&&`: `report` returns 3 on most real repositories, so `&&` would skip
the proof in exactly the case you wanted proven. That is a small thing and it hid a
real defect in this README once.

### 4. Every checker must be able to fail

This is the rule the project has had to learn twice, so it is now law.

If you add a check, a gate, a test, or a report question, you must also
demonstrate the case where it **fails**. A green check that has never once gone
red is not evidence of anything — it is an untested branch wearing a tick.

Concretely, a pull request that adds a check includes:

- [ ] the check itself
- [ ] a test that drives it to a passing result
- [ ] a **negative control**: a test that drives it to a failing result, asserting
      the non-zero exit code or the specific finding
- [ ] the failing case named in the PR description, in one line, so a reviewer can
      re-run it by hand

`tests/` already contains negative controls for the existing checks. Copy the
shape from the nearest one rather than inventing a new convention.

---

## The pre-PR checklist

Run all of it. Paste the exit codes into the pull request. Bare commands, not
piped — a pipe replaces the exit code you are trying to report with the exit code
of whatever it was piped into, which is how an untested change passes review.

- [ ] `python -m unittest discover -s tests` → exit **0** (144 tests at time of writing;
      the command prints the count, so do not trust this number, read that one)
- [ ] `python tools/refresh_readme_counts.py` → exit **0**, and commit the README if it
      changed. The paragraph publishes this repo's own line and test counts, so ANY change
      under `kibsu/` or `tests/` moves them and the suite fails while the prose disagrees
      (#29). Do not edit those four numbers by hand — this produces them from the guard's own
      measurement, touching nothing else in the file. `--check` reports without writing.
- [ ] `python -m kibsu report .` → exit **3** on this repo, and `git status --porcelain`
      afterwards shows only your own changes
- [ ] `python -m kibsu audit . --definitions` → exit **0**, still prints the full ruleset,
      and it still matches what the code does (if you changed the ruleset, this is the
      output that has to change with it)
- [ ] zero-dependency check above → exit **0**
- [ ] on a Python 3.8 interpreter if you have one; CI will tell you if you do not
- [ ] negative control named, if you added a check (rule 4)

## What you cannot run, and what that means for you

The provenance scrub — the script that enforces the claims in
[PROVENANCE.md](PROVENANCE.md) — is **not in this repository and will not be
added.** It scans for a denylist of private identifiers, and that denylist is
itself the sensitive artifact; shipping the checker would publish exactly what it
exists to keep out. The reasoning is written out in full in `PROVENANCE.md`,
including the revision where it *was* shipped and was the only remaining leak in
the tree while reporting `PASS — 0 hits`.

So: you cannot run it, and you are not expected to. What this means in practice is
that a maintainer runs it before any release, and that **pull requests should not
introduce example data, fixtures, or documentation drawn from a real company,
market, customer, or internal system.** Invent your fixtures. If you need a
realistic dataset to test against, generate one.

## If you are quoting a number

Any figure this project publishes — coverage percentages, checkability ratios,
medians — is measured against a **named public repository at a pinned commit SHA**,
and the raw per-repo JSON lives in [`evidence/`](evidence/). A number without a SHA
is not reproducible, and this repository has already published one of those once
and had to explain it.

If your change moves a published figure:

- [ ] re-run `python -m kibsu survey` rather than editing the table by hand
- [ ] commit the regenerated `evidence/*.json`
- [ ] state in the PR which figures moved and which stayed identical

## Reporting a bug

Issues are welcome and a reproduction is worth more than a description. Useful
issues carry: the command you ran, the exit code, the output, the repository you
pointed it at (a public one if possible, with the SHA), and your Python version.

If kibsu reported something about your repository that you believe is wrong, that
is the most valuable class of issue there is — the metric is a documented heuristic
and `--definitions` exists so you can argue with it. Say which rule you think
misfired.

## Commit trailers

If an AI assistant drafted part of your change, record it in a commit trailer. The
existing history does this, and `PROVENANCE.md` explains why: a project about
verifiable claims should not carry an unverifiable author line. Nobody is going to
think less of a patch for it.

## What is likely to be declined

Stated up front so nobody wastes an afternoon:

- anything adding a runtime dependency (rule 1)
- a test framework change (rule 2)
- a feature requiring install or build before first run (rule 3)
- a check without a negative control (rule 4)
- a feature that writes into the analysed repository
- broadening a reported claim beyond what the code measures — the README's
  Honest Limits section is load-bearing, not a disclaimer, and a PR that makes a
  stronger claim than the evidence supports will be asked for the evidence

## Licence

Contributions are accepted under the MIT licence in [LICENSE](LICENSE).
