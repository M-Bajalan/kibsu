#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ns_index.py  v1.0.0  -  kibsu's deterministic markdown index.

Builds a DETERMINISTIC index of a repository's markdown, and derives that repo's own frontmatter
taxonomy instead of assuming one. Everything downstream (ns_check, the receipt, the backtest)
reads this file and nothing else.

WHY DETERMINISTIC IS A FEATURE, NOT A DETAIL
  Two runs on an unchanged tree must produce byte-identical output. If they do not, every check
  built on top inherits the noise and "it changed" stops meaning anything. So: git commit dates
  (never mtime - mtime changes on checkout), sorted keys, sorted paths, no wall-clock stamp in the
  payload. `--verify-determinism` builds it twice in memory and diffs.

WHY THE TAXONOMY IS DERIVED
  This repo tags docs `type/ domain/ topic/ status/`. anthropics/skills uses `name/ description/
  license`. Neither is "correct". A key is promoted to REQUIRED only if it appears on >=80% of docs
  that carry any frontmatter at all, and only if there are >=10 such docs. Below that the taxonomy
  is recorded as `observed` and never enforced - inventing a schema for a repo that has none is how
  you manufacture rules nobody follows.

Stdlib only. Python 3.8+. Reads only; writes exactly one file.

  python -m kibsu index [repo] [-o .kibsu/index.json] [--verify-determinism] [--stdout]
"""
import argparse
import hashlib
import io
import json
import os
import re
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

VERSION = "1.0.0"

# Issue #39: kibsu scans arbitrary third-party repositories, and nothing stops one from
# git-tracking a multi-gigabyte markdown file. A whole-file .read() of that is an unbounded
# allocation the kernel OOM-killer ends with a SIGKILL no `except` clause sees. 5 MB is
# generous for instruction markdown; over-ceiling files are SKIPPED WITH A PRINTED REASON
# on stderr (stdout stays clean for --json), never silently.
MAX_READ_BYTES = 5 * 1024 * 1024
SCHEMA = 1
VENDOR = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
          ".next", ".nuxt", "vendor", ".tox", ".mypy_cache", ".pytest_cache"}
PROMOTE_MIN_DOCS = 10
PROMOTE_MIN_SHARE = 0.80


def run(args, cwd):
    try:
        p = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        return p.stdout if p.returncode == 0 else None
    except Exception:
        return None


def git_tracked(root):
    """Tracked files only - respects .gitignore for free and avoids indexing junk."""
    out = run(["git", "ls-files", "-z"], root)
    if out is None:
        return None
    return [p for p in out.split("\0") if p.endswith(".md")]


def walk_md(root):
    hits = []
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in VENDOR]
        for f in fn:
            if f.lower().endswith(".md"):
                rel = os.path.relpath(os.path.join(dp, f), root).replace("\\", "/")
                hits.append(rel)
    return hits


def git_dates(root, paths):
    """Last commit date per path. One process, not one per file."""
    out = run(["git", "log", "--format=%x00%cI", "--name-only", "--no-renames"], root)
    if out is None:
        return {}
    dates, cur = {}, None
    for line in out.split("\n"):
        if line.startswith("\0"):
            cur = line[1:].strip()
        elif line.strip() and cur and line.strip() not in dates:
            dates[line.strip()] = cur
    return {p: dates.get(p) for p in paths}


FM_LINE = re.compile(r"^([A-Za-z_][\w.-]*)\s*:\s*(.*)$")


def parse_frontmatter(text):
    """Minimal YAML-subset frontmatter: scalars and '- ' lists. No dependency, no eval.
    Unparseable frontmatter yields {} rather than a guess."""
    # A UTF-8 BOM defeats startswith("---"). Real repos have them - this repo has several
    # written by PowerShell, whose frontmatter was being read as absent. Strip it, do not guess.
    text = text.lstrip("﻿")
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    block = text[3:end].strip("\n")
    data, key = {}, None
    for raw in block.split("\n"):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.lstrip().startswith("- ") and key:
            data.setdefault(key, [])
            if isinstance(data[key], list):
                data[key].append(raw.lstrip()[2:].strip().strip("'\""))
            continue
        m = FM_LINE.match(raw)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if val == "":
            data[key] = []
        else:
            data[key] = val.strip("'\"")
    return data


def derive_taxonomy(docs):
    """The repo's own vocabulary, measured. Never assumed."""
    withfm = [d for d in docs if d["frontmatter"]]
    n = len(withfm)
    keys = {}
    for d in withfm:
        for k in d["frontmatter"]:
            keys.setdefault(k, 0)
            keys[k] += 1
    required, observed = [], []
    for k in sorted(keys):
        share = keys[k] / n if n else 0.0
        entry = {"key": k, "docs": keys[k], "share": round(share, 4)}
        if n >= PROMOTE_MIN_DOCS and share >= PROMOTE_MIN_SHARE:
            required.append(entry)
        else:
            observed.append(entry)
    vocab = {}
    for k in sorted(keys):
        vals = {}
        for d in withfm:
            v = d["frontmatter"].get(k)
            for item in (v if isinstance(v, list) else [v] if isinstance(v, str) else []):
                if item and len(item) < 60:
                    vals[item] = vals.get(item, 0) + 1
        if vals and len(vals) <= 60:
            vocab[k] = dict(sorted(vals.items()))
    return {"docs_with_frontmatter": n, "docs_total": len(docs),
            "promotion_rule": {"min_docs": PROMOTE_MIN_DOCS, "min_share": PROMOTE_MIN_SHARE},
            "required": required, "observed": observed, "vocabulary": vocab,
            "enforceable": bool(required)}


def build(root):
    tracked = git_tracked(root)
    src = "git ls-files" if tracked is not None else "filesystem walk (not a git repo)"
    paths = sorted(tracked if tracked is not None else walk_md(root))
    dates = git_dates(root, paths) if tracked is not None else {}
    docs = []
    for rel in paths:
        full = os.path.join(root, rel.replace("/", os.sep))
        try:
            if os.path.getsize(full) > MAX_READ_BYTES:
                sys.stderr.write("kibsu index: skipping %s (%d bytes > %d byte ceiling)\n"
                                 % (rel, os.path.getsize(full), MAX_READ_BYTES))
                continue
            text = io.open(full, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        fm = parse_frontmatter(text)
        body = text.split("\n")
        h = hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:16]
        docs.append({"path": rel, "lines": len(body), "sha256_16": h,
                     "last_commit": dates.get(rel), "has_frontmatter": bool(fm),
                     "frontmatter": {k: fm[k] for k in sorted(fm)}})
    docs.sort(key=lambda d: d["path"])
    head = (run(["git", "rev-parse", "HEAD"], root) or "").strip() or None
    return {"schema": SCHEMA, "generator": "ns_index.py v" + VERSION,
            "source": src, "head": head, "doc_count": len(docs),
            "taxonomy": derive_taxonomy(docs), "docs": docs}


def dumps(idx):
    return json.dumps(idx, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main():
    ap = argparse.ArgumentParser(prog="python -m kibsu index", description="Deterministic markdown index with a derived taxonomy.")
    ap.add_argument("repo", nargs="?", default=".")
    ap.add_argument("-o", "--out", default=os.path.join(".kibsu", "index.json"))
    ap.add_argument("--verify-determinism", action="store_true",
                    help="build twice and byte-compare; exit 3 on mismatch")
    ap.add_argument("--stdout", action="store_true", help="print instead of writing")
    a = ap.parse_args()
    root = os.path.abspath(a.repo)

    # Validate the target BEFORE build()/write. Without this, a typo'd path
    # (`python -m kibsu index <typo>`) is not caught anywhere downstream: git commands fail
    # against the missing cwd (caught in run(), read as "not a git repo"), walk_md() over a
    # missing path just yields zero files, and the os.makedirs(dirname(out), exist_ok=True)
    # below - meant only to create .kibsu/ inside an EXISTING repo - ends up creating the
    # typo'd path itself as a side effect. The result is a fabricated clean success: exit 0,
    # .kibsu/index.json written into a brand-new directory that did not exist a moment ago.
    # discover.py already guards the identical input this same way - mirrored here.
    if not os.path.isdir(root):
        print("CANNOT RUN: %s is not a directory" % root)
        return 3

    idx = build(root)
    text = dumps(idx)

    if a.verify_determinism:
        second = dumps(build(root))
        if second != text:
            import difflib
            d = list(difflib.unified_diff(text.split("\n"), second.split("\n"),
                                          "run1", "run2", n=1, lineterm=""))[:20]
            print("DETERMINISM FAIL - two runs differ:")
            print("\n".join(d))
            return 3
        print("  [ok] determinism: two builds byte-identical (sha256 %s)"
              % hashlib.sha256(text.encode()).hexdigest()[:16])

    t = idx["taxonomy"]
    print("ns_index v%s   %s" % (VERSION, root))
    print("  source        %s" % idx["source"])
    print("  docs          %d  (%d with frontmatter)" % (idx["doc_count"], t["docs_with_frontmatter"]))
    if t["required"]:
        print("  REQUIRED keys (>=%.0f%% of frontmattered docs): %s"
              % (PROMOTE_MIN_SHARE * 100, ", ".join("%s(%.0f%%)" % (r["key"], r["share"] * 100)
                                                    for r in t["required"])))
    else:
        print("  REQUIRED keys: none - taxonomy recorded as OBSERVED ONLY, nothing will be enforced")
        print("                 (needs >=%d frontmattered docs; found %d)"
              % (PROMOTE_MIN_DOCS, t["docs_with_frontmatter"]))
    if t["observed"]:
        print("  observed      %s" % ", ".join("%s(%d)" % (o["key"], o["docs"]) for o in t["observed"][:8]))

    if a.stdout:
        sys.stdout.write(text)
        return 0
    out = a.out if os.path.isabs(a.out) else os.path.join(root, a.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with io.open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    try:
        shown = os.path.relpath(out, root)
    except ValueError:          # different drive on Windows - relpath is undefined, not an error
        shown = out
    print("  written       %s  (%s bytes)" % (shown, format(len(text), ",")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
