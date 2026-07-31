#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ns_check.py  v1.0.0  -  the commit-time index check.

The check that gets wired to `git commit`. It answers one question mechanically:
**does the repo still match the index it claims to keep?**

TWO CHECKS, AND ONLY TWO. Both derived, neither invented.

  STALE   a tracked .md changed, was added, or was deleted, and `.kibsu/index.json` was not
          regenerated in the same commit. This is the generic form of the rule this repo
          already writes down and does not enforce: "before commit -> run the checker, don't
          commit red". Replaying the last 200 commits here, 29 of 61 eligible commits would
          have failed this. That gap is the entire product.

  TAXONOMY  a doc under a root WITH an enforceable taxonomy is missing a required key.
          "Enforceable" is decided by ns_index's promotion rule (>=80% of frontmattered docs,
          >=10 docs) - imported, never restated, so the two cannot drift.

PER DOC ROOT, NOT PER REPO. Running E1 on this monorepo returned zero required keys across
1,834 docs, because `docs/` uses tags+summary while the vendored skills use
`description`. A repo-wide taxonomy would be wrong. Each top-level root gets its own, or none.

WHAT IT WILL NOT DO. It never edits a file, never runs git-write, never blocks on prose. A rule
that cannot produce a path and a reason is not a rule this tool will enforce.

EXIT CODES   0 clean · 1 violations (BLOCK) · 2 warnings only · 3 cannot run

  python -m kibsu check [repo] [--staged|--all] [--index .kibsu/index.json] [--quiet] [--warn-only]
"""
import argparse, hashlib, io, json, os, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from index import derive_taxonomy, parse_frontmatter   # single source of the rule
# config.py is a normal package file, always present next to this one when check.py runs as
# part of kibsu - but this file is also VENDORED on its own (see install.py's HOOK, which
# copies check.py + index.py, and only those two, into a target repo's .kibsu/bin/). A vendored
# copy has no config.py beside it, so the import is optional: fall back to kibsu's own default
# rather than crash a git hook over a missing convenience file. A checker that cannot resolve
# its own default must not become a checker that blocks every commit.
try:
    import config as _kibsu_config
except ImportError:
    _kibsu_config = None

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

VERSION = "1.0.0"
OK, VIOLATIONS, WARNINGS_ONLY, CANNOT_RUN = 0, 1, 2, 3
DEFAULT_INDEX_REL = ".kibsu/index.json"   # byte-identical to config.DEFAULTS["index_path"]


def _index_default(root):
    """The --index default, from .kibsu.json when this file can read one, else kibsu's own
    built-in default (never the pre-port .ns/ path - that name is retired, not just moved)."""
    if _kibsu_config is not None:
        return _kibsu_config.load(root)["index_path"]
    return DEFAULT_INDEX_REL


def run(args, cwd):
    try:
        p = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        return p.stdout if p.returncode == 0 else None
    except Exception:
        return None


def staged_md(root):
    out = run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACMRD"], root)
    if out is None:
        return None
    return sorted(p.strip() for p in out.split("\n") if p.strip().endswith(".md"))


def tracked_md(root):
    out = run(["git", "ls-files", "-z"], root)
    if out is None:
        return None
    return sorted(p for p in out.split("\0") if p.endswith(".md"))


def sha16(path):
    try:
        return hashlib.sha256(io.open(path, encoding="utf-8", errors="replace")
                              .read().encode("utf-8", "replace")).hexdigest()[:16]
    except Exception:
        return None


def doc_root(rel):
    """Top-level directory, or '.' for repo-root files. The unit a taxonomy belongs to."""
    parts = rel.split("/")
    return parts[0] if len(parts) > 1 else "."


def duplicate_roots(root):
    """Find top-level trees that are byte-identical, and keep only one.

    Derived, not configured: git content-addresses trees, so a directory junction or symlink
    that got committed twice appears as two names sharing ONE tree OID. A real repo hit
    exactly that - `docs/` and `vendor/wiki/docs-mirror/` were the same physical
    files - and without this every violation is reported twice. Returns {skip_name: kept_name}.
    """
    out = run(["git", "ls-tree", "-r", "-d", "--full-tree", "HEAD"], root)
    if out is None:
        return {}
    by_oid = {}
    for line in out.split("\n"):
        f = line.split(None, 3)
        if len(f) >= 4 and f[1] == "tree":
            by_oid.setdefault(f[2], []).append(f[3].strip())
    # Match PATHS, never roots. An earlier version compared the top-level component of any
    # matching subtree and concluded whole roots were duplicates - `.agents/skills/x` really does
    # equal `.cursor/skills/x`, but that says nothing about `.agents` vs `.cursor`. It silently
    # dropped 775 files and printed PASS. Compare the exact directory, keep the shortest path.
    dupes = {}
    for paths in by_oid.values():
        if len(paths) < 2:
            continue
        keep = sorted(paths, key=lambda s: (len(s), s))[0]
        for p in paths:
            if p != keep:
                dupes[p] = keep
    # drop children whose parent is already covered - one line per real duplication
    return {p: k for p, k in dupes.items()
            if not any(p != q and p.startswith(q + "/") for q in dupes)}


def under_duplicate(rel, dupes):
    for p in dupes:
        if rel == p or rel.startswith(p + "/"):
            return p
    return None


def load_baseline(root, override=None, default_dir=".kibsu"):
    """`.kibsu/baseline.json` - the acknowledgement file. 'This looks like a gap, it is deliberate.'

    Without one, a deriving checker re-proposes the same intentional choice forever and gets
    uninstalled. Shape: {"exclude": ["docs/archive/**", ...], "why": {"glob": "reason"}}
    Whatever it skips is COUNTED and PRINTED - an exclusion may be silent to the exit code but
    never silent to the reader.

    default_dir is resolved by the caller from the (possibly config-driven) --index directory,
    so the fallback below only fires if a caller ever invokes this without doing that.
    """
    p = override or os.path.join(root, default_dir, "baseline.json")
    if not os.path.isfile(p):
        return {"exclude": [], "why": {}}
    try:
        b = json.load(io.open(p, encoding="utf-8"))
        return {"exclude": list(b.get("exclude", [])), "why": dict(b.get("why", {}))}
    except Exception:
        return {"exclude": [], "why": {}}


def excluded_by(rel, patterns):
    import fnmatch
    # fnmatchcase, never fnmatch: fnmatch.fnmatch() runs os.path.normcase() on both operands,
    # which lowercases on Windows and is a no-op on POSIX - so the SAME baseline.json would
    # exclude a different file set depending on which OS ran the check (docs/archive/** would
    # also swallow Docs/Archive/ and docs/ARCHIVE/, but only on Windows). rel comes from
    # `git ls-files`, which is already the canonical, case-exact path git tracks on every OS -
    # matching it case-sensitively is what keeps this check's exclusions identical across the
    # project's own 3-OS CI matrix.
    for pat in patterns:
        if fnmatch.fnmatchcase(rel, pat) or fnmatch.fnmatchcase(rel, pat.rstrip("/") + "/*"):
            return pat
    return None


def roots_taxonomy(index):
    """Group the indexed docs by root and derive each root's taxonomy independently."""
    by = {}
    for d in index["docs"]:
        by.setdefault(doc_root(d["path"]), []).append(d)
    return {r: derive_taxonomy(docs) for r, docs in sorted(by.items())}


# ---- backtest ------------------------------------------------------------------------------
def backtest(root, n, index_rel, mode="content", cfg=None):
    """mode decides WHICH commits are eligible, and it must match what the index records.

      content  - the index stores a per-doc hash (ns_index.json does), so ANY edit stales it.
      existence- the index stores only paths/metadata (docs/catalog.json does), so
                 only Add / Delete / Rename stales it. Editing a doc body does not.

    Getting this wrong inflates the result. Backtesting docs/catalog.json in 'content' mode scored
    commits that appended to a session log as failures, which they were not - the catalog was
    correctly untouched. Choose the mode from the index, never from the number you want."""
    """Replay the last N commits and count how many WOULD have been blocked.

    The rule under test: if a commit changed a watched .md, it must also have updated the index
    in the SAME commit. Watched = every .md under the directory that holds the index file.

    Why not replay against .kibsu/index.json: it has no history, so every commit would trivially
    'fail' and the number would mean nothing. Replaying against the index the repo ALREADY
    claims to maintain measures the discipline that is actually being asserted today.

    Honest limit, printed with the result: this measures state AT COMMIT TIME. A commit that
    left the index stale and was fixed in the next commit still counts - these are moments of
    red, not permanent breakage.
    """
    watch_dir = os.path.dirname(index_rel.replace("\\", "/")) or "."

    # existence mode's index conventionally lives APART from the docs it tracks - kibsu's own
    # DEFAULTS put it at .kibsu/index.json while docs_root is "docs" - so replaying "touched"
    # against dirname(index_path) watches the wrong directory on every default-config repo
    # (issue #2: 0 eligible commits, always). Scope existence mode to the same file set `index`
    # itself is meant to cover instead: docs_root, skills_dir, and instruction_files. content
    # mode is untouched - its index conventionally sits beside the docs it hashes (e.g.
    # docs/catalog.json), where dirname(index_path) is already correct.
    if mode == "existence":
        cfg = cfg or {}
        scope_dirs = [d for d in (cfg.get("docs_root", "docs"),
                                   cfg.get("skills_dir", ".claude/skills")) if d]
        scope_files = set(cfg.get("instruction_files",
                                   ["AGENTS.md", "CLAUDE.md", ".cursorrules"]))
        report_scope = " + ".join(d.replace("\\", "/").rstrip("/") or "." for d in scope_dirs) or "."
    else:
        scope_dirs = [watch_dir]
        scope_files = set()
        report_scope = watch_dir

    def _in_scope(p):
        if p in scope_files:
            return True
        for d in scope_dirs:
            d = d.replace("\\", "/").rstrip("/")
            if d in ("", "."):
                return True
            if p == d or p.startswith(d + "/"):
                return True
        return False

    # --name-status, never --diff-filter. A diff-filter also filters the FILE LISTING, which
    # hides the index file itself (it is always 'M'), making "index not updated" trivially true
    # for every commit. That produced a 100.0% result - the tell that it was a bug, not a finding.
    out = run(["git", "log", "-n", str(n), "--format=@%H|%cI|%s", "--name-status", "--no-renames"], root)
    if out is None:
        return None
    commits, cur = [], None
    for line in out.split("\n"):
        if line.startswith("@"):
            if cur:
                commits.append(cur)
            h, ci, subj = (line[1:].split("|", 2) + ["", ""])[:3]
            cur = {"sha": h[:8], "date": ci[:10], "subj": subj[:70], "files": []}
        elif line.strip() and cur:
            parts = line.split("\t")
            if len(parts) >= 2:
                cur["files"].append((parts[0].strip()[:1], parts[-1].strip()))
    if cur:
        commits.append(cur)

    idx = index_rel.replace("\\", "/")
    trigger = ("A", "D", "R") if mode == "existence" else ("A", "D", "R", "M")
    eligible, failed = [], []
    for c in commits:
        paths = [p for _, p in c["files"]]
        watched = [p for st, p in c["files"]
                   if p.endswith(".md") and st in trigger and _in_scope(p)]
        if not watched:
            continue
        eligible.append(c)
        if idx not in paths:                    # any status counts as "the index was updated"
            c["watched_n"] = len(watched)
            failed.append(c)
    return {"scanned": len(commits), "watch_dir": report_scope, "index": index_rel,
            "mode": mode, "eligible": eligible, "failed": failed}


def write_receipt(root, index, scope_n, viol, warn, enforce, bt, arts, shallow, path):
    L = []
    L.append("# NERVOUS SYSTEM - RECEIPT")
    L.append("")
    L.append("repo: `%s`  ·  index head: `%s`  ·  generator: ns_check v%s"
             % (root, (index.get("head") or "?")[:8], VERSION))
    L.append("")
    L.append("Every number below is computed. Nothing here is asserted.")
    L.append("")
    L.append("## 1  INDEX")
    L.append("")
    L.append("- **%s** markdown units indexed, **%s** carry frontmatter, **%s** in scope this run"
             % (format(index.get("doc_count", 0), ","),
                format(index["taxonomy"]["docs_with_frontmatter"], ","), format(scope_n, ",")))
    if enforce:
        for r, t in sorted(enforce.items()):
            L.append("- root `%s/` enforces **%s** (derived, not configured)"
                     % (r, ", ".join("%s %.0f%%" % (k["key"], k["share"] * 100) for k in t["required"])))
    else:
        L.append("- **no root clears the promotion floor** - taxonomy observed only, nothing enforced.")
        L.append("  That is an abstention, not a pass.")
    L.append("- violations now: **%d** · warnings: **%d**" % (viol, warn))
    L.append("")
    L.append("## 2  BACKTEST - would this have caught anything?")
    L.append("")
    if not bt:
        L.append("- unavailable (no git history)")
    elif not bt["eligible"]:
        L.append("- %d commits scanned, **0 touched a watched `.md`** - nothing to test against."
                 % bt["scanned"])
    else:
        pct = 100.0 * len(bt["failed"]) / len(bt["eligible"])
        L.append("- eligibility mode: **%s** (%s)" % (bt["mode"],
                 "any .md edit stales a hash-recording index" if bt["mode"] == "content"
                 else "only add/delete/rename stales a path+tag index"))
        L.append("- commits scanned: **%d**" % bt["scanned"])
        L.append("- of those, **%d** changed a `.md` under `%s/`" % (len(bt["eligible"]), bt["watch_dir"]))
        L.append("- of those, **%d (%.1f%%)** did NOT update `%s` in the same commit"
                 % (len(bt["failed"]), pct, bt["index"]))
        L.append("")
        L.append("> **%d commits would have exited 1 at the moment they were made.**" % len(bt["failed"]))
        L.append("")
        L.append("Most recent examples:")
        L.append("")
        L.append("| commit | date | files | subject |")
        L.append("|---|---|---:|---|")
        for c in bt["failed"][:8]:
            L.append("| `%s` | %s | %d | %s |" % (c["sha"], c["date"], c.get("watched_n", 0), c["subj"].replace("|", "/")))
        L.append("")
        L.append("*Measured at commit time. A commit that left the index stale and was fixed in a")
        L.append("later commit still counts - this counts moments of red, not permanent breakage.*")
        if pct > 60:
            L.append("")
            L.append("> ⚠ **%.0f%% would block.** A gate that stops most commits gets bypassed, and a" % pct)
            L.append("> bypassed gate measures nothing. Demote these to WARN before enforcing.")
    L.append("")
    L.append("## 3  MANDATED ARTIFACTS")
    L.append("")
    if not arts:
        L.append("- **not measured by this tool.** Artifact/phantom analysis lives in")
        L.append("  `python -m kibsu audit <dir> --artifacts`. Reporting zero here would be a")
        L.append("  number this run did not compute.")
    elif shallow:
        L.append("- **SHALLOW CLONE** - history unavailable, phantom status is UNKNOWN, not zero.")
    else:
        ins = [a for a in arts if a["in_scope"]]
        ph = [a for a in ins if a["phantom"]]
        L.append("- %d in-scope artifacts the skills mandate; **%d have never existed** in the tree or "
                 "in any commit (%.0f%%)" % (len(ins), len(ph), 100.0 * len(ph) / max(1, len(ins))))
        for a in ph[:6]:
            L.append("  - `%s` - mandated by `%s`" % (a["artifact"], a["skill"]))
    L.append("")
    L.append("## 4  NOT BUILT YET")
    L.append("")
    L.append("Stated so this receipt is not mistaken for a full one:")
    L.append("")
    L.append("- **rule extraction** (how many written rules are machine-checkable) - needs W1")
    L.append("- **architecture-gap findings** - needs the detector set")
    L.append("- **memory / lessons layer** - starts empty by design and stays empty until you fill it")
    L.append("")
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")
    return len(L)


def main():
    ap = argparse.ArgumentParser(prog="python -m kibsu check", description="Check the repo against its own index.")
    ap.add_argument("repo", nargs="?", default=".")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--staged", action="store_true", help="only files in the git index (pre-commit)")
    g.add_argument("--all", action="store_true", help="every tracked .md (default)")
    ap.add_argument("--index", default=None,
                    help="default: config['index_path'] from .kibsu.json, else .kibsu/index.json")
    ap.add_argument("--baseline", default=None,
                    help="acknowledgement file (default: <index dir>/baseline.json)")
    ap.add_argument("--backtest", type=int, metavar="N",
                    help="replay the last N commits and count how many would have been blocked")
    ap.add_argument("--backtest-mode", choices=["content", "existence"], default="content",
                    help="content = index stores per-doc hashes, any edit stales it (ns_index.json). "
                         "existence = index stores only paths/tags, only add/delete/rename stales "
                         "it (docs/catalog.json). Must match what the index records.")
    ap.add_argument("--backtest-index", default=None, metavar="PATH",
                    help="the index/catalog a commit must update (default: the --index path). "
                         "Use the file the repo ALREADY maintains, e.g. docs/catalog.json")
    ap.add_argument("--receipt", nargs="?", const="", default=None,
                    metavar="PATH", help="write RECEIPT.md with the computed numbers "
                                          "(default path: <index dir>/RECEIPT.md)")
    ap.add_argument("--warn-only", action="store_true", help="never exit 1; report and exit 0/2")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    root = os.path.abspath(a.repo)

    # --index has no static default (its real default is config-dependent, and config is keyed
    # on `root`, which argparse does not know until AFTER parsing) - resolve it here instead.
    index_arg = a.index if a.index is not None else _index_default(root)
    idx_path = index_arg if os.path.isabs(index_arg) else os.path.join(root, index_arg)

    say = (lambda *x: None) if a.quiet else print
    say("ns_check v%s   %s" % (VERSION, root))

    if run(["git", "rev-parse", "--is-inside-work-tree"], root) is None:
        print("  CANNOT RUN: not a git repository (or git unavailable).")
        print("  This check compares committed state against an index; without git there is")
        print("  nothing to compare. Reporting SKIPPED, not OK.")
        return CANNOT_RUN

    if not os.path.isfile(idx_path):
        print("  CANNOT RUN: no index at %s" % idx_path)
        print("  Build one first:  python -m kibsu index . -o %s" % index_arg)
        return CANNOT_RUN
    try:
        index = json.load(io.open(idx_path, encoding="utf-8"))
    except Exception as e:
        print("  CANNOT RUN: index is not readable JSON (%s)" % e)
        return CANNOT_RUN

    indexed = {d["path"]: d for d in index.get("docs", [])}
    tracked = tracked_md(root)
    if tracked is None:
        print("  CANNOT RUN: git ls-files failed.")
        return CANNOT_RUN

    if a.staged:
        scope = staged_md(root)
        if scope is None:
            print("  CANNOT RUN: git diff --cached failed.")
            return CANNOT_RUN
        scope_label = "staged"
    else:
        scope = tracked
        scope_label = "all tracked"

    # ---- scope reductions, both reported so nothing is silently skipped -------------------
    dupes = duplicate_roots(root)
    baseline_dir = os.path.dirname(index_arg) or "."
    base = load_baseline(root, a.baseline, baseline_dir)
    skipped_dupe, skipped_base = 0, {}
    kept = []
    for rel in scope:
        if under_duplicate(rel, dupes):
            skipped_dupe += 1
            continue
        pat = excluded_by(rel, base["exclude"])
        if pat:
            skipped_base[pat] = skipped_base.get(pat, 0) + 1
            continue
        kept.append(rel)
    scope = kept

    violations, warnings = [], []

    # ---- CHECK 1: STALE -------------------------------------------------------------------
    tracked_set = set(tracked)
    for rel in scope:
        full = os.path.join(root, rel.replace("/", os.sep))
        present = os.path.isfile(full)
        rec = indexed.get(rel)
        if present and rec is None:
            violations.append(("STALE", rel, "tracked but absent from the index - regenerate"))
        elif not present and rec is not None:
            violations.append(("STALE", rel, "in the index but deleted - regenerate"))
        elif present and rec is not None:
            cur = sha16(full)
            if cur and rec.get("sha256_16") and cur != rec["sha256_16"]:
                violations.append(("STALE", rel, "content changed since the index was built "
                                                 "(%s -> %s)" % (rec["sha256_16"][:8], cur[:8])))
    # docs in the index that no longer exist anywhere (only meaningful in --all)
    if not a.staged:
        for rel in sorted(set(indexed) - tracked_set):
            violations.append(("STALE", rel, "in the index but no longer tracked - regenerate"))

    # ---- CHECK 2: TAXONOMY ----------------------------------------------------------------
    tax = roots_taxonomy(index)
    enforce = {r: t for r, t in tax.items() if t["enforceable"]}
    for rel in scope:
        full = os.path.join(root, rel.replace("/", os.sep))
        if not os.path.isfile(full):
            continue
        r = doc_root(rel)
        t = enforce.get(r)
        if not t:
            continue
        try:
            fm = parse_frontmatter(io.open(full, encoding="utf-8", errors="replace").read())
        except Exception:
            continue
        req = [k["key"] for k in t["required"]]
        if not fm:
            warnings.append(("NO-FRONTMATTER", rel,
                             "root '%s' enforces %s; this doc has none" % (r, "+".join(req))))
            continue
        missing = [k for k in req if k not in fm or fm[k] in ("", [], None)]
        if missing:
            violations.append(("TAXONOMY", rel, "missing required %s (root '%s')"
                               % ("+".join(missing), r)))

    # ---- report ---------------------------------------------------------------------------
    say("  scope         %s (%d markdown files)" % (scope_label, len(scope)))
    say("  index         %s docs, head %s" % (format(index.get("doc_count", 0), ","),
                                              (index.get("head") or "?")[:8]))
    if dupes:
        say("  duplicate     %d identical tree(s), %d files counted once:" % (len(dupes), skipped_dupe))
        for p, k in sorted(dupes.items())[:4]:
            say("                %s/  ==  %s/" % (p, k))
        if len(dupes) > 4:
            say("                ... and %d more" % (len(dupes) - 4))
    for pat, n in sorted(skipped_base.items()):
        say("  baseline      %-28s %d skipped%s" % (pat, n,
            ("  - " + base["why"][pat]) if pat in base["why"] else ""))
    if enforce:
        for r, t in sorted(enforce.items()):
            say("  enforcing     %-22s %s" % (r + "/", ", ".join(
                "%s(%.0f%%)" % (k["key"], k["share"] * 100) for k in t["required"])))
    else:
        say("  enforcing     nothing - no doc root clears the promotion floor")
        say("                (taxonomy observed only; this is not a pass, it is an abstention)")

    for tag, rel, msg in violations[:40]:
        print("  X  %-14s %s" % (tag, rel))
        print("     %s" % msg)
    if len(violations) > 40:
        print("  ... and %d more violations" % (len(violations) - 40))
    for tag, rel, msg in warnings[:10]:
        say("  !  %-14s %s  (%s)" % (tag, rel, msg))
    if len(warnings) > 10:
        say("  ... and %d more warnings" % (len(warnings) - 10))

    bt = None
    if a.backtest:
        bt_cfg = _kibsu_config.load(root) if _kibsu_config is not None else None
        bt = backtest(root, a.backtest, a.backtest_index or index_arg, a.backtest_mode, bt_cfg)
        say("\n  --- backtest: last %d commits ---" % a.backtest)
        if not bt:
            say("    unavailable (no git history)")
        elif not bt["eligible"]:
            say("    0 of %d commits touched a .md under %s/ - nothing to test"
                % (bt["scanned"], bt["watch_dir"]))
        else:
            pct = 100.0 * len(bt["failed"]) / len(bt["eligible"])
            say("    %d commits scanned" % bt["scanned"])
            say("    %d changed a .md under %s/" % (len(bt["eligible"]), bt["watch_dir"]))
            say("    %d (%.1f%%) did NOT update %s in the same commit"
                % (len(bt["failed"]), pct, bt["index"]))
            print("    >> %d commits would have exited 1 when they were made" % len(bt["failed"]))
            if pct > 60:
                say("    !! >60% would block - demote to WARN before enforcing, or it gets bypassed")

    if a.receipt is not None:
        receipt_arg = a.receipt if a.receipt else os.path.join(baseline_dir, "RECEIPT.md")
        rp = receipt_arg if os.path.isabs(receipt_arg) else os.path.join(root, receipt_arg)
        d = os.path.dirname(rp)
        if d:
            os.makedirs(d, exist_ok=True)
        # artifact/phantom analysis lives in `python -m kibsu audit --artifacts`, not here - the
        # receipt says so rather than silently printing a zero it did not measure.
        nl = write_receipt(root, index, len(scope), len(violations), len(warnings),
                           enforce, bt, [], False, rp)
        say("\n  receipt written: %s (%d lines)" % (receipt_arg, nl))

    say("")
    if violations:
        print("  FAIL  %d violation(s), %d warning(s)" % (len(violations), len(warnings)))
        if not a.warn_only:
            print("  Fix:  python -m kibsu index . -o %s     then re-stage" % index_arg)
            return VIOLATIONS
        print("  (--warn-only: not blocking)")
        return WARNINGS_ONLY
    if warnings:
        say("  PASS with %d warning(s)" % len(warnings))
        return WARNINGS_ONLY
    say("  PASS  0 violations, 0 warnings")
    return OK


if __name__ == "__main__":
    sys.exit(main())
