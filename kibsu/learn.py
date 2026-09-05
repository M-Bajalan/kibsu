#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ns_learn.py  v1.0.0  -  does the knowledge base still tell the truth?

WHAT THIS IS FOR
  docs/memory/ is the repo's cross-agent knowledge base: 26 learnings, written to
  be read by Claude Code, Desktop, Cowork, Cursor and Cline alike. Nothing checks it. A learning
  is prose, and prose rots quietly - the file it cites gets renamed, the sibling it links to was
  never written, the whole note is reachable from nowhere.

  This applies the same test to knowledge that skill_audit applies to instructions: not "is it
  well written" but "can any of it still be verified from the repo".

THE FIVE CHECKS
  CROSS-STORE  a link that resolves ONLY inside one agent's private memory. The file looks
               shared - it is git-tracked, in the shared folder, read by every agent - and the
               link is dead for all of them but one. This is the check that motivated the tool.
  DANGLING     a link that resolves nowhere at all.
  ROTTED       a cited source file that no longer exists. Phantom artifacts, pointed at
               knowledge instead of instructions.
  ORPHAN       a learning nothing links to. Not wrong, just unreachable - it will be rediscovered
               the hard way and written a second time.
  UNANCHORED   a learning with no date, no cited file, and no number in it. Nothing ties it to
               anything checkable, so it can only ever be taken on faith.

WHAT IT DOES NOT DO
  It does not judge whether a lesson is TRUE or still relevant. No tool can. It only reports
  whether the things a lesson points AT are still there.

Read-only. Dependency-free. Python 3.8+.

  python -m kibsu learn [repo] [--private-store DIR] [--json] [--quiet]

EXIT CODES  (same meanings as ns_check.py and ns_report.py)
  0  clean            1  findings            3  cannot run
"""
import argparse
import io
import json
import os
import re
import sys

from . import config

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

VERSION = "1.0.0"

# Issue #39: kibsu scans arbitrary third-party repositories, and nothing stops one from
# git-tracking a multi-gigabyte markdown file. A whole-file .read() of that is an unbounded
# allocation the kernel OOM-killer ends with a SIGKILL no `except` clause sees. 5 MB is
# generous for instruction markdown; over-ceiling files are SKIPPED WITH A PRINTED REASON
# on stderr (stdout stays clean for --json), never silently.
MAX_READ_BYTES = 5 * 1024 * 1024
OK, FINDINGS, CANNOT_RUN = 0, 1, 3

# Extracting a cited path is where the FIRST version of this file was badly wrong, and the way it
# was wrong is worth keeping written down. It matched the whole backtick block against the repo
# root only, and reported 28 false ROTTED findings in one run - `guides/runbooks/setup.md` is
# written relative to docs/, `python scripts/build_catalog.py` is a command with a
# path inside it, and `%APPDATA%\...` is not this machine's business at all. A checker that cries
# wolf 28 times gets switched off on day one, which is worse than never having built it.
#
# So: pull path-shaped TOKENS out of a backtick block, then resolve each against every base the
# vault actually uses. Same lesson as memory/learnings/normalized-read-hides-crlf-false-pass.md -
# the instrument agreed with itself and was measuring the wrong thing.
BACKTICK_RE = re.compile(r"`([^`\n]+)`")
PATH_TOKEN_RE = re.compile(r"[\w.\-/\\]+\.(?:py|sql|ps1|bat|cmd|json|ya?ml|md)")


def cited_paths(text):
    """Path-shaped tokens inside backticks, skipping what is not a repo-relative file."""
    out = set()
    for block in BACKTICK_RE.findall(text):
        if "%" in block or "$" in block or "{" in block:
            continue                    # env vars and {C}-style templates are not literal paths
        for tok in PATH_TOKEN_RE.findall(block):
            if "/" not in tok and "\\" not in tok:
                continue                # a bare filename is too ambiguous to resolve
            if re.match(r"^[A-Za-z]:", tok) or tok.startswith(("/", "\\")):
                continue                # absolute - someone else's machine
            out.add(tok)
    return out


def repo_index(root):
    """basename -> [full repo-relative paths]. Built once.

    Guessing which BASE a citation is relative to was attempt two, and it was still wrong twice:
    `.lstrip("./")` strips a character SET, so `.agents/skills/x.ps1` silently became
    `agents/skills/x.ps1`; and `My Tools/api/client.py` contains a space, so the tokenizer only
    ever saw `Tools/api/client.py`. Both were reported as rotted knowledge. Neither was.

    So stop guessing bases. Index every file once and ask whether any of them ENDS WITH the cited
    path. That is base-agnostic, space-agnostic, and cannot regress the same way."""
    idx = {}
    files = []
    try:
        import subprocess
        # Tracked AND untracked-but-present. Tracked-only reported a brand-new, uncommitted file
        # as rotted knowledge the first time this ran - the citation was correct and the index
        # was incomplete. "Not in git yet" is not the same as "does not exist".
        for args in (["ls-files"], ["ls-files", "--others", "--exclude-standard"]):
            out = subprocess.run(["git", "-C", root] + args, capture_output=True, text=True,
                                 encoding="utf-8", errors="replace")
            if out.returncode == 0:
                files += out.stdout.split("\n")
    except Exception:
        files = []
    if not files:
        files = []
        for base, dirs, fs in os.walk(root):
            dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "node_modules", ".venv")]
            for f in fs:
                files.append(os.path.relpath(os.path.join(base, f), root))
    for f in files:
        f = f.strip().replace("\\", "/")
        if f:
            idx.setdefault(os.path.basename(f), []).append(f)
    return idx


def resolves(idx, cited):
    c = cited.replace("\\", "/")
    while c.startswith("./"):
        c = c[2:]
    for full in idx.get(os.path.basename(c), ()):
        # Plain endswith, NOT endswith("/" + c). A path containing a space - "My Tools/api/client.py"
        # - reaches here truncated to "Tools/api/client.py", because a token regex that allowed
        # spaces would swallow the prose in front of the path. Matching without requiring a
        # separator boundary recovers those, at the cost of a theoretical false NEGATIVE
        # ("Old/x.py" would resolve against "New/Old/x.py").
        #
        # That bias is deliberate and it is the same one skill_audit takes: be generous, so the
        # number reported is a CEILING on health rather than a pile of false alarms. A rot
        # detector nobody leaves switched on detects nothing.
        if full == c or full.endswith(c):
            return True
    return False
LINK_RE = re.compile(r"\[\[([^\]|#]+)")
DATE_RE = re.compile(r"\b20\d\d-\d\d-\d\d\b")
NUM_RE = re.compile(r"\b\d[\d,]{2,}\b|\b\d+(?:\.\d+)?\s*(?:%|x|s|ms|min|MB|GB)\b")

# Where an agent's PRIVATE memory lives. Claude Code namespaces by mangled project path, so this
# is a glob over the whole projects tree rather than one directory.
PRIVATE_HINTS = [
    os.path.join(os.path.expanduser("~"), ".claude", "projects"),
]


COMMENT_RE = re.compile(r"<!--.*?-->", re.S)


def read(p):
    # Guarded (issue #39): this was the one read in the package with no try/except at all -
    # an unreadable or over-ceiling file propagated an uncaught exception straight up.
    try:
        if os.path.getsize(p) > MAX_READ_BYTES:
            sys.stderr.write("kibsu learn: skipping %s (over the %d byte ceiling)\n"
                             % (p, MAX_READ_BYTES))
            return ""
        with io.open(p, encoding="utf-8", errors="replace") as f:
            text = f.read().lstrip("﻿")  # a BOM defeats every startswith() you will write
    except OSError:
        return ""
    # An HTML comment is not a live link or a live citation. Without this, a note that documents
    # a broken link in order to explain the fix gets reported for containing the broken link -
    # which happened the first time this file was used to fix something it found.
    return COMMENT_RE.sub("", text)


def md_files(root):
    out = []
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "node_modules")]
        for f in files:
            if f.lower().endswith(".md"):
                out.append(os.path.join(base, f))
    return out


def stem(p):
    return os.path.splitext(os.path.basename(p))[0]


def private_stems(explicit):
    """Every note name that exists in an agent-private store. Returns None when no store could be
    located - which is NOT the same as 'no private notes exist', and is reported as such."""
    roots = [explicit] if explicit else PRIVATE_HINTS
    found, any_root = {}, False
    for r in roots:
        if not r or not os.path.isdir(r):
            continue
        any_root = True
        for p in md_files(r):
            if stem(p).lower() != "memory":            # MEMORY.md is an index, not a note
                found.setdefault(stem(p), p)
    return found if any_root else None


def main():
    ap = argparse.ArgumentParser(prog="python -m kibsu learn",
                                 description="Does the knowledge base still tell the truth?")
    ap.add_argument("repo", nargs="?", default=".")
    ap.add_argument("--private-store", default=None,
                    help="an agent's private memory dir (auto-detected; SKIPs if not found)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    root = os.path.abspath(a.repo)
    mem_rel = config.load(root)["memory_root"]
    mem = os.path.join(root, mem_rel)

    if not os.path.isdir(mem):
        print("CANNOT RUN: no %s in %s" % (mem_rel, root))
        return CANNOT_RUN

    notes = md_files(mem)
    if not notes:
        print("CANNOT RUN: %s has no markdown notes" % mem_rel)
        return CANNOT_RUN

    shared = {stem(p): p for p in notes}
    priv = private_stems(a.private_store)

    # Inbound links are counted from the WHOLE vault, not just memory/. A learning referenced
    # from a runbook is reachable; scoping the scan to memory/ would invent orphans.
    vault_docs = md_files(os.path.join(root, "documentation")) if \
        os.path.isdir(os.path.join(root, "documentation")) else notes
    linked_to = set()
    for p in vault_docs:
        for t in LINK_RE.findall(read(p)):
            linked_to.add(t.strip())

    idx = repo_index(root)
    findings, orphans, exempt = [], [], []
    for p in notes:
        rel = os.path.relpath(p, root).replace("\\", "/")
        if stem(p).lower() == "readme":
            continue
        text = read(p)

        # A note that TEACHES about broken references necessarily contains broken references.
        # That is a real category, not an excuse, so it gets a declared opt-out rather than a
        # heuristic - declaration beats detection, the same call skill_audit makes about genre.
        # Exempt notes are COUNTED and printed: an exemption nobody can see is a loophole, and
        # this whole toolchain exists to stop rules being enforced by nobody looking.
        if re.search(r"^ns_learn:\s*examples-only\b", text, re.M):
            exempt.append(rel)
            continue

        for target in sorted(set(t.strip() for t in LINK_RE.findall(text))):
            if target in shared:
                continue
            if priv is None:
                findings.append(("SKIP", rel, "link [[%s]] unresolved, and no private store was "
                                              "found to rule out - NOT checked" % target))
            elif target in priv:
                findings.append(("CROSS-STORE", rel,
                                 "[[%s]] exists ONLY in an agent's private memory. This file is "
                                 "git-tracked and shared - the link is dead for every agent but "
                                 "one." % target))
            else:
                findings.append(("DANGLING", rel, "[[%s]] resolves nowhere" % target))

        cites = cited_paths(text)
        for cited in sorted(cites):
            if not resolves(idx, cited):
                findings.append(("ROTTED", rel,
                                 "cites `%s`, and no file in the repo has that path" % cited))

        if stem(p) not in linked_to:
            # Counted, NOT reported as a finding. Measurement said 20 of 31 - and this vault
            # navigates by catalog tags, not by wikilink, so an unlinked note is perfectly
            # reachable. Twenty findings that are not defects would have buried the one that is.
            orphans.append(rel)

        # UNANCHORED applies to LEARNINGS only. A note recording a preference ("Mohammed wants
        # the assumption named first") has nothing to anchor to and is not defective for it -
        # that is skill_audit's genre lesson, where scoring doctrine on checkability was the
        # first mistake that tool made. Judge a genre by what its genre is for.
        if re.search(r"^kind:\s*learning\b", text, re.M):
            if not DATE_RE.search(text) and not cites and not NUM_RE.search(text):
                findings.append(("UNANCHORED", rel, "a learning with no date, no cited file and "
                                                    "no measured number - nothing here can be "
                                                    "checked against anything"))

    order = ["CROSS-STORE", "DANGLING", "ROTTED", "UNANCHORED", "ORPHAN", "SKIP"]
    findings.sort(key=lambda f: (order.index(f[0]) if f[0] in order else 9, f[1]))
    skipped = sum(1 for f in findings if f[0] == "SKIP")
    real = len(findings) - skipped

    if a.json:
        print(json.dumps({"version": VERSION, "repo": root, "notes": len(notes),
                          "findings": [{"kind": k, "file": f, "detail": d}
                                       for k, f, d in findings],
                          "checked_private_store": priv is not None}, indent=2))
        return CANNOT_RUN if (skipped and not real) else (FINDINGS if real else OK)

    print("\n  KNOWLEDGE BASE - what no longer resolves")
    print("  %s  (%d notes)" % (os.path.join(root, mem_rel), len(notes)))
    print("  " + "-" * 74)
    if not findings:
        print("  +  every link, citation and note resolves.")
    for k, f, d in findings:
        if a.quiet and k in ("ORPHAN", "SKIP"):
            continue
        print("  %-11s %s" % (k, f))
        print("  %-11s   %s" % ("", d))
    print("  " + "-" * 74)
    print("  %d finding(s) across %d notes." % (real, len(notes)))
    if exempt:
        print("  !  %d note(s) declared `ns_learn: examples-only` and were NOT checked for broken"
              % len(exempt))
        print("     links or citations. That is an exemption, not a pass:")
        for e in exempt:
            print("       %s" % e)
    if orphans:
        print("  i  %d of %d notes have no inbound wikilink. Not a defect here - this vault"
              % (len(orphans), len(notes)))
        print("     navigates by catalog tag - but cross-links are how a sibling lesson gets")
        print("     found, and %d notes currently cannot be reached that way." % len(orphans))
    if priv is None:
        print("  ?  No private memory store was found, so CROSS-STORE could not be checked.")
        print("     Unresolved links are reported as unchecked, not as clean.")
    print("")
    return CANNOT_RUN if (skipped and not real) else (FINDINGS if real else OK)


if __name__ == "__main__":
    sys.exit(main())
