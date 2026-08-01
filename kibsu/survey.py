#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Clone public agent-instruction repos, audit each, print the distribution.

FULL clones (not shallow) so the phantom-artifact check has real history to search.
Read-only: reads markdown, executes nothing from the cloned repos.
Failures are reported, never silently dropped.
"""
import json
import os
import subprocess
import sys

from . import __version__

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
# NEVER clone into the repo this file lives in. When a tool like this one moved into a larger
# repo, its (relative) clone dir moved with it and dropped ten full repo clones into a tracked
# directory - untracked, not gitignored, and a nightly job running `git add -A` would have swept
# them in. Default outside the tree.
REPOS_DIR = os.environ.get("SKILL_AUDIT_CLONES") or os.path.join(
    os.path.expanduser("~"), ".skill-audit-clones")
AUDIT = os.path.join(HERE, "audit.py")

EVIDENCE = os.environ.get("SKILL_AUDIT_EVIDENCE")

REPOS = [
    "anthropics/skills",
    "obra/superpowers",
    "wshobson/agents",
    "VoltAgent/awesome-claude-code-subagents",
    "0xfurai/claude-code-subagents",
    "contains-studio/agents",
    "iannuttall/claude-agents",
    "vijaythecoder/awesome-claude-agents",
    "davila7/claude-code-templates",
    "sanjeed5/awesome-cursor-rules-mdc",
]


def clone(slug):
    dest = os.path.join(REPOS_DIR, slug.replace("/", "__"))
    if os.path.isdir(os.path.join(dest, ".git")):
        return dest, None
    os.makedirs(REPOS_DIR, exist_ok=True)
    p = subprocess.run(["git", "-c", "core.longpaths=true", "clone", "--quiet",
                        "https://github.com/%s.git" % slug, dest], capture_output=True, text=True)
    if p.returncode != 0:
        tail = (p.stderr or "clone failed").strip().splitlines()
        return None, (tail[0] if tail else "clone failed")[:88]
    return dest, None


def head_sha(path):
    """The commit the measurement was taken at. A number without a SHA is not reproducible -
    the repo moves and the reader cannot get back to what was measured."""
    p = subprocess.run(["git", "rev-parse", "HEAD"], cwd=path, capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 else None


def audit(path, artifacts=True):
    cmd = [sys.executable, AUDIT, path, "--json"] + (["--artifacts"] if artifacts else [])
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if p.returncode != 0:
        return None, (p.stderr or "audit failed").strip()[:88]
    try:
        return json.loads(p.stdout), None
    except Exception as e:
        return None, str(e)[:88]


def _version_banner():
    """The banner's tool-name-and-version stamp, sourced from the real constants - not a
    hand-frozen string. Mirrors __main__.py's _cmd_version()/_scorer_version(): the package
    version says which CLI is printing this, audit.py's VERSION says which ruleset the numbers
    below were measured with. This used to read "(skill-audit v0.2.1)" - a tool name and a
    version that never existed anywhere in this repo, wired to nothing - long after --version
    had already been printing the real pair (see CORRECTIONS.md)."""
    from . import audit
    return "kibsu %s (scorer %s)" % (__version__, audit.VERSION)


# A procedure-only percentage computed from a handful of instructions is noise wearing a number.
MIN_UNITS, MIN_INSTR = 5, 50


def _artifact_population(arts, include_out_of_scope):
    """The population taxonomy every count-printing site in survey.py's main() must speak - named
    ONCE, here, so "distinct" and "record" never again mean two different things a few lines
    apart. Three appearances of exactly that ambiguity (a verifier catching it three separate
    times, in three separate rounds) is what this taxonomy exists to retire:

      (1) REFERENCE RECORDS   one row per mandate LINE - duplicates are real: the same artifact
                               string mandated by two skills is two records. This is `arts`
                               itself, and what the exclusion ledger's per-class breakdown
                               counts (audit.py's own build_exclusion_ledger() is record-based
                               too - see its docstring).

      (2) DISTINCT ARTIFACTS  reference records (1) deduped to distinct artifact STRINGS per
                               repo, unverifiable_pattern excluded (a hit or miss on `{name}.md`
                               proves nothing either way). Computed here with
                               include_out_of_scope=True: every artifact this repo produced, in
                               scope and out, that carries literal content to search for. This
                               is `cf_all_n` in row_from() below.

      (3) IN-SCOPE DISTINCT   population (2) restricted to strings with at least one IN-SCOPE
                               mandate. Computed here with include_out_of_scope=False. This is
                               `mand`/`phantom` in row_from() below - the headline rate this
                               tool has always reported. IN-SCOPE DISTINCT is always a SUBSET of
                               DISTINCT ARTIFACTS (any record that qualifies for (3) also
                               qualifies for (2), since the scope check is the only difference
                               between the two calls below), so "excluded outright" - the
                               bracket's own `out` field in row_from() - is exactly population
                               (2) minus population (3), a plain set difference.

    A fourth quantity - EXCLUDED-RECORD DISTINCT, `excluded_distinct` in row_from() below - is
    NOT one of these three, and main()'s exclusion-ledger reconciliation needs it: it is
    reference records (1) restricted to OUT-of-scope rows, deduped to strings. It is not
    reducible to (2), (3), or `out` alone, because a string can carry an exclusion record from
    one skill AND a genuine in-scope mandate from another - verified against real evidence:
    davila7's `.mcp.json` is in scope under two skills and excluded under a third. Such a
    string sits in BOTH population (3) and this fourth set at once, and `out` (population 2
    minus 3) does not see it, because it IS mandated, correctly, somewhere. See main()'s ledger
    print for where this fourth quantity is needed and why populations (2)/(3) alone cannot
    state it.

    Historical note: an independent verifier BLOCKED the first version of this function's call
    sites - mand/phantom (population 3, deduped) were paired against cf_all_n/cf_all_phantom
    computed as len(arts) (population 1, raw records) - three axes differed (dedup,
    unverifiable_pattern, scope) where the printed line claimed only one (scope), understating
    the true "if all exclusions are counted" rate. Routing both call sites through this single
    function is what makes "only scope differs" true rather than asserted:
    include_out_of_scope=False reproduces mand/phantom exactly (pinned in
    ArtifactPopulationTests, tests/test_survey.py) because row_from() calls this exact function
    for that population too - not a parallel computation that happens to agree today.

    match_count == 0 (not the `phantom` boolean, which audit.py only ever sets for an in-scope,
    verifiable artifact - see check_artifacts()) is what lets ONE formula serve both scope
    settings: for an in-scope, verifiable artifact the two are equivalent by audit.py's own
    definition (phantom = in_scope and not unverifiable and match_count == 0), so nothing about
    the in-scope numbers changes by using it here instead.
    """
    pool = [x for x in arts if not x.get("unverifiable_pattern")
            and (include_out_of_scope or x["in_scope"])]
    names = {x["artifact"] for x in pool}
    zero_match = {x["artifact"] for x in pool if x.get("match_count") == 0}
    return names, zero_match


def row_from(slug, d):
    A, P = d["all"], d["procedure_only"]
    arts = d.get("artifacts", [])
    usable_hist = d.get("has_git") and not d.get("history_shallow")
    inscope_all = {x["artifact"] for x in arts if x["in_scope"]}
    # unverifiable_pattern artifacts are in-scope but carry no literal content to check - a hit
    # or miss on `{name}.md` proves nothing either way (audit.py's own `ver` set excludes them
    # from BOTH the phantom numerator and denominator for exactly this reason - see its
    # check_artifacts()/main()). `mand`/`phantom` here must agree with that, or this survey's
    # printed rate and a single-repo `audit --artifacts` run on the same data would silently
    # disagree on what "mandated, checkable" means.
    in_scope_names, in_scope_zero = _artifact_population(arts, include_out_of_scope=False)
    unverifiable = len(inscope_all) - len(in_scope_names)
    # Every OUT-OF-SCOPE reason class this repo's audit produced, summed here so main() can add
    # them across every ranked repo into one disclosure-ledger total (audit.py's own
    # `exclusion_ledger` is the single-repo version of the same idea - see its
    # build_exclusion_ledger()). REFERENCE RECORDS (population 1, see _artifact_population()'s
    # taxonomy) - one row per excluded mandate LINE, duplicates real.
    exclusions = {}
    for x in arts:
        if not x["in_scope"]:
            cls = x.get("out_of_scope_class") or "unspecified"
            exclusions[cls] = exclusions.get(cls, 0) + 1
    # EXCLUDED-RECORD DISTINCT (a fourth population, not one of the three canonical ones - see
    # _artifact_population()'s taxonomy docstring for why): the SAME excluded reference records
    # (1) as `exclusions` above, deduped to distinct strings instead of counted by class. Needed
    # because `out` (population 2 minus 3, "excluded outright") misses a string that carries an
    # exclusion record from one skill while ALSO being genuinely mandated, in-scope, by another
    # - `not x.get("unverifiable_pattern")` is structurally a no-op here (an out-of-scope record
    # is never unverifiable_pattern - audit.py's check_artifacts() sets `unverifiable` only when
    # `in_scope` already is), kept for consistency with the other three populations regardless.
    excluded_names = {x["artifact"] for x in arts
                       if not x["in_scope"] and not x.get("unverifiable_pattern")}
    # PHANTOM COUNTERFACTUAL (council ruling #3): mirrors audit.py's own phantom_counterfactual()
    # (audit.py:667) at the per-repo level, so main() can sum these SAME numerator/denominator
    # quantities across every ranked repo instead of re-deriving the rate by a different formula.
    # cf_all_n/cf_all_phantom are the SAME _artifact_population() call as mand/phantom above,
    # with only the scope filter toggled - gated to None on unusable history exactly like
    # `phantom` below, since match_count==0 is unreliable evidence when history is shallow or
    # absent (a "never matched" cannot be told apart from "matched somewhere history can't
    # reach").
    all_names, all_zero = _artifact_population(arts, include_out_of_scope=True)
    cf_all_n = len(all_names)
    cf_all_phantom = len(all_zero) if usable_hist else None
    # `out` = DISTINCT ARTIFACTS (2) minus IN-SCOPE DISTINCT (3), "excluded outright" - derived
    # from the exact same all_names/in_scope_names sets mand and cf_all_n already use, not a
    # separately re-derived distinct count - see _artifact_population()'s taxonomy docstring.
    # This also fixed a real divergence: the old formula (distinct-all minus distinct-in-scope,
    # neither side excluding unverifiable_pattern) let an in-scope-but-unverifiable mandate's
    # mere presence hide that same string's separate out-of-scope mandate from `out` entirely.
    return dict(slug=slug, units=A["units"], instr=A["instructions"], pct_all=A["pct"],
                p_units=P["units"], p_instr=P["instructions"], pct_proc=P["pct"],
                zero=A["zero"], mand=len(in_scope_names),
                out=len(all_names) - len(in_scope_names),
                unverifiable=unverifiable, exclusions=exclusions,
                excluded_distinct=len(excluded_names),
                phantom=(len(in_scope_zero) if usable_hist else None),
                cf_all_n=cf_all_n, cf_all_phantom=cf_all_phantom,
                enough=(P["units"] >= MIN_UNITS and P["instructions"] >= MIN_INSTR),
                genres={g: v["units"] for g, v in d.get("by_genre", {}).items()})


def main():
    rows, failures = [], []
    for slug in REPOS:
        sys.stderr.write("  ... %s\n" % slug)
        dest, err = clone(slug)
        if err:
            failures.append((slug, "clone: " + err))
            continue
        d, err = audit(dest)
        if err:
            failures.append((slug, "audit: " + err))
            continue
        if d["all"]["instructions"] < 20:
            failures.append((slug, "only %d instructions (mode=%s) - unmeasurable"
                             % (d["all"]["instructions"], d["mode"])))
            continue
        r = row_from(slug, d)
        r["sha"] = head_sha(dest)
        rows.append(r)
        if EVIDENCE:
            os.makedirs(EVIDENCE, exist_ok=True)
            fn = os.path.join(EVIDENCE, slug.replace("/", "__") + ".json")
            # Strip the local clone path. Published evidence must not reveal the machine it
            # was measured on - "root" carried a full absolute path including the username.
            clean = dict(d)
            clean["root"] = "<clone of %s at %s>" % (slug, (r["sha"] or "?")[:12])
            with open(fn, "w", encoding="utf-8") as fh:
                json.dump({"repo": slug, "sha": r["sha"], "measured_by": "skill_audit",
                           "result": clean}, fh, indent=2)

    # Optional local comparison set. Nothing about this file should assume whose machine it
    # is running on - it is the file a reader would open to check the claim that this tool is
    # generic, so a hardcoded path here would refute the claim on sight.
    local = os.environ.get("SKILL_AUDIT_LOCAL") or (sys.argv[1] if len(sys.argv) > 1 else None)
    label = os.environ.get("SKILL_AUDIT_LABEL", "** local (not published) **")
    if local:
        d, err = audit(os.path.abspath(local))
        if err:
            failures.append((local, "audit: " + err))
        else:
            rows.append(row_from(label, d))

    ranked = sorted([r for r in rows if r["enough"]], key=lambda r: -r["pct_proc"])
    thin = [r for r in rows if not r["enough"]]
    W = 112
    print("\n" + "=" * W)
    print("CHECKABLE-INSTRUCTION SURVEY - public agent instruction sets   %s" % _version_banner())
    print("min sample to rank: >=%d procedure units AND >=%d procedure instructions" % (MIN_UNITS, MIN_INSTR))
    print("=" * W)
    print("%-40s %6s %7s %7s | %6s %7s %7s | %6s %7s"
          % ("repo", "units", "instr", "all%", "proc-u", "p-instr", "PROC%", "in-scp", "phantom")
          + " | commit")
    print("-" * W)
    # Per-repo "in-scp"/"phantom" columns: the SAME IN-SCOPE DISTINCT (population 3) numbers
    # the aggregate headline below sums across every ranked repo - see
    # _artifact_population()'s taxonomy.
    for r in ranked:
        ph = "n/a" if r["phantom"] is None else "%d (%.0f%%)" % (
            r["phantom"], 100.0 * r["phantom"] / max(1, r["mand"]))
        print("%-40s %6d %7s %6.1f%% | %6d %7s %6.1f%% | %6d %8s | %s"
              % (r["slug"][:40], r["units"], format(r["instr"], ","), r["pct_all"],
                 r["p_units"], format(r["p_instr"], ","), r["pct_proc"], r["mand"], ph,
                 (r.get("sha") or "?")[:10]))
    print("-" * W)

    pub = [r for r in ranked if not r["slug"].startswith("**")]
    if pub:
        for key, lbl in (("pct_all", "all units"), ("pct_proc", "procedure units only")):
            ps = sorted(r[key] for r in pub)
            n = len(ps)
            med = ps[n // 2] if n % 2 else (ps[n // 2 - 1] + ps[n // 2]) / 2
            print("ranked public n=%d  %-22s median %5.1f%%   min %4.1f%%   max %5.1f%%"
                  % (n, lbl, med, ps[0], ps[-1]))
        tm = sum(r["mand"] for r in pub)
        tp = sum(r["phantom"] for r in pub if r["phantom"] is not None)
        to = sum(r["out"] for r in pub)
        tu = sum(r.get("unverifiable", 0) for r in pub)
        # HEADLINE: tm/tp are IN-SCOPE DISTINCT (population 3, _artifact_population()'s
        # taxonomy) - the phantom rate this tool has always reported. BRACKET (`to`): DISTINCT
        # ARTIFACTS (2) minus IN-SCOPE DISTINCT (3) - "excluded outright", artifacts with no
        # in-scope mandate anywhere (see row_from()'s `out`). `tu` (unverifiable-pattern):
        # in-scope distinct strings INCLUDING unverifiable_pattern ones, minus population 3 - a
        # related but separate exclusion (row_from()'s `unverifiable`), not itself one of the
        # three named populations.
        print("in-scope mandated artifacts: %d distinct, %d PHANTOM (%.0f%%)   "
              "[%d excluded from the phantom check (all classes), %d unverifiable-pattern]"
              % (tm, tp, (100.0 * tp / tm) if tm else 0, to, tu))
        # Disclosure ledger, summed across every ranked public repo (audit.py's own
        # exclusion_ledger is the single-repo version - see build_exclusion_ledger() there).
        # Printed right where the phantom evidence above already is, per the council's ruling
        # that this must never be a separate, easy-to-miss section.
        ledger = {}
        for r in pub:
            for cls, n in r.get("exclusions", {}).items():
                ledger[cls] = ledger.get(cls, 0) + n
        if ledger:
            # LEDGER (per-class breakdown): REFERENCE RECORDS (population 1) - one row per
            # excluded mandate line, duplicates real, grouped by reason (audit.py's own
            # build_exclusion_ledger() is record-based too - see its docstring). A reader sums
            # these per-class counts and compares against the bracket's "[N excluded from the
            # phantom check]" a few lines up - they must reconcile from the printed output
            # alone. They do NOT reconcile to the SAME number, though: `te` (EXCLUDED-RECORD
            # DISTINCT, row_from()'s `excluded_distinct` - see _artifact_population()'s taxonomy
            # for why this is a fourth population, not (2)/(3)/`out`) can exceed `to` ("excluded
            # outright") by exactly the count of strings that carry an exclusion record from one
            # skill while ALSO being genuinely mandated, in-scope, by another (verified against
            # real evidence: davila7's `.mcp.json`) - that gap is stated explicitly, not left for
            # a reader to notice as an unexplained mismatch. Every number below is reused, not
            # re-derived: `ledger_records` sums the exact dict just printed per-class, `te` sums
            # row_from()'s own excluded_distinct, and `to` is the exact value the bracket line
            # above already printed - so the two lines can never drift apart by construction.
            ledger_records = sum(ledger.values())
            te = sum(r["excluded_distinct"] for r in pub)
            print("exclusion ledger (full counts, all ranked repos): "
                  + ", ".join("%s=%d" % (k, ledger[k]) for k in sorted(ledger))
                  + " - %d reason records across %d distinct artifacts: %d excluded outright "
                    "(the bracket), %d also mandated in-scope by another skill and counted "
                    "there" % (ledger_records, te, to, te - to))
        # COUNTERFACTUAL, summed across every ranked public repo (audit.py's own
        # phantom_counterfactual() is the single-repo version this mirrors - see audit.py:667
        # and row_from()'s cf_all_n/cf_all_phantom above). The in-scope side reuses tm/tp -
        # IN-SCOPE DISTINCT (population 3), the SAME numbers the headline above already
        # printed. The 'all' side (ta/tap) is DISTINCT ARTIFACTS (population 2) -
        # cf_all_n/cf_all_phantom, scope exclusions counted back in. Council ruling #3 kept the
        # path-prefix scope filter explicitly IN EXCHANGE for this reaching readers HERE, not
        # just a single `audit --artifacts` run: the first number is the in-scope-only rate the
        # PHANTOM line above has always reported; the second is what it would read if every
        # excluded artifact (out-of-scope, all classes) were simply counted too, using each
        # artifact's own already-computed match_count==0 - no new evidence gathered, the
        # exclusions just undone. Numerators and denominators are summed across repos first and
        # divided once - never averaged as per-repo percentages, and never re-derived by a
        # formula of its own. The denominator is restricted to the SAME repos the numerator can
        # even be computed for (cf_all_phantom is not None) - a shallow-history repo's cf_all_n
        # must not pad the denominator while contributing nothing to the numerator, which would
        # silently deflate the printed rate.
        cf_repos = [r for r in pub if r["cf_all_phantom"] is not None]
        ta = sum(r["cf_all_n"] for r in cf_repos)
        tap = sum(r["cf_all_phantom"] for r in cf_repos)
        print("phantom rate (all ranked repos, summed): %.1f%% in-scope-only (%d artifacts) / "
              "%.1f%% if all exclusions are counted (%d artifacts)"
              % ((100.0 * tp / tm) if tm else 0.0, tm, (100.0 * tap / ta) if ta else 0.0, ta))
        print("genre mix:", {g: sum(r["genres"].get(g, 0) for r in pub)
                             for g in ("procedure", "persona", "reference", "mixed")})
    if thin:
        print("\nBELOW SAMPLE FLOOR - measured, not ranked (a %% from <%d instructions is noise):" % MIN_INSTR)
        for r in thin:
            print("  %-40s %d procedure units / %d instructions  (would read %.1f%%)"
                  % (r["slug"][:40], r["p_units"], r["p_instr"], r["pct_proc"]))
    if failures:
        print("\nEXCLUDED (%d) - reported, not hidden:" % len(failures))
        for s, why in failures:
            print("  %-40s %s" % (s, why))
    print()


if __name__ == "__main__":
    main()
