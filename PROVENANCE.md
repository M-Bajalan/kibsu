# Provenance

Kibsu was built on personal time, on personally-owned hardware, paid for out of
the author's own pocket, on the author's own initiative.

It was not commissioned, requested, assigned, or required by any employer. It is
not a work product of any employment, and it does not relate to the business of
any employer the author has worked for. It was written by one person, working
alone, to make that person's own work easier.

## What this repository does not contain

No employer data. No employer code. No employer configuration. No employer
business logic. No customer, market, product, or commercial information of any
kind. Every file here was authored for this project.

## How that claim is enforced — and why you cannot run the check yourself

This project exists because instructions that cannot be verified tend not to be
followed, so it would be poor form to make an unverifiable claim in its own
provenance file. The claim above **is** enforced by a script — but that script is
deliberately **not** in this repository, and the reason is worth stating plainly.

The gate scans every tracked file against a denylist of identifiers, path shapes
and naming conventions belonging to the private system this tooling was
originally written inside. It matches on word boundaries rather than substrings,
and uses Python's `ast` module to classify each hit as a string literal, a
comment or an identifier — because a regular expression cannot tell code from
prose, and a scrub that raises false alarms is a scrub that gets bypassed. It
exits 0 only when it finds nothing, and no release is cut while it is red.

**That denylist is itself the sensitive artifact.** It is a written list of the
exact private identifiers the scan exists to keep out of this repository.
Shipping the checker would publish, in plain text, everything it was built to
conceal — so the checker stays in the private repository and scans this one from
the outside.

This was found the hard way. An earlier revision did ship it, exempting the file
from its own scan and printing that exemption on every run. The exemption was
disclosed, and disclosure was mistaken for protection: after this repository's
history was rebuilt to remove leaked commits, the single remaining leak in the
entire tree was the checker itself — reporting `PASS — 0 hits` while being the
only thing left to find.

What you can verify without it: the absence itself. Search this repository for
anything that looks like a company, a market, a customer or an internal system.
The claim is that you will find none. That is a falsifiable statement, and it
does not require the tool to test.

## Survey figures

Any coverage percentages, checkability ratios, or similar metrics this project
cites are measured against named, public, open-source repositories at pinned
commit SHAs — never against private, proprietary, or employer-owned material.
Each figure is reproducible from the pinned commit alone, and every repository
used is named in `README.md` rather than left implicit.
