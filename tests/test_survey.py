#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for `python -m kibsu survey` - the AGGREGATION half, offline.

kibsu/survey.py unconditionally clones ten public GitHub repositories and shells out to
audit.py on every real invocation (see the module's own docstring, its REPOS list, and
__main__.py's `_cmd_survey` comment: it "still clones and audits public repos over the
network regardless" of any local-repo argument passed to it). There is no `--local-only` /
`--no-clone` switch. That makes the network I/O itself genuinely untestable offline -
SurveyNetworkTests below skips exactly that, with a reason, and nothing else.

The AGGREGATION - the part that turns per-repo audit JSON into the ranked table, the sample
floor, the median, and the failure list - is a different matter, and IS exercised here,
offline, with no mocking of anything except the two functions that reach the network:

  RowFromTests            `row_from()` is an ordinary importable module-level function - it
                           needs no mocking at all and is called directly.

  SurveyAggregationTests   The ranking / sample-floor split / median / genre-mix / failure
                           reporting is NOT separately importable: it lives inline in
                           `survey.main()`, interleaved with the network-calling `clone()`
                           and `audit()` (plus `head_sha()`). Rather than restructure
                           survey.py to pull that logic into its own function - a design
                           change that would be flagged here, not made unilaterally - these
                           tests run the REAL, unmodified `main()` with `clone`/`audit`/
                           `head_sha` substituted via `unittest.mock.patch.object`, keyed by
                           the actual slugs in `survey.REPOS`. That is dependency injection
                           at the test boundary: no line of survey.py is touched, and every
                           code path exercised below is the real shipped aggregation logic,
                           not a re-implementation of it.

This is also why this file imports `kibsu.survey` directly and runs in-process, instead of
the subprocess-based `run_tool()` helper every other module in this suite uses - subprocess
would put `clone`/`audit` out of reach and force a real network call to substitute them.
"""
import contextlib
import io
import json
import os
import re
import sys
import unittest
import unittest.mock as mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kibsu import survey
from support import PACKAGE_ROOT


# ---------------------------------------------------------------------------------------
# Fixture builders - construct the exact JSON shape audit.py's `--json` output has (see
# kibsu/audit.py's `json.dumps(dict(version=..., root=..., mode=..., all=ALL,
# procedure_only=PROC, by_genre=..., artifacts=..., history_shallow=..., has_git=...,
# skills=...))`), which is what `audit()` in survey.py hands back to `row_from()` / `main()`.
# ---------------------------------------------------------------------------------------

def _agg(units, instructions, pct, zero=0):
    return {"units": units, "instructions": instructions, "pct": pct, "zero": zero}


def _artifact(name, in_scope=True, phantom=False, unverifiable_pattern=False,
              out_of_scope_class=None, match_count=None):
    # match_count mirrors audit.py's own field (check_artifacts() -> phantom_counterfactual()):
    # phantom is defined there as in_scope and not unverifiable and match_count == 0, so an
    # in-scope phantom fixture defaults to match_count=0 and everything else to 1 - callers
    # building the counterfactual negative-control fixtures override it explicitly to give an
    # OUT-OF-SCOPE artifact a real match_count=0 (never found anywhere), independent of `phantom`
    # (which audit.py only ever sets True for in-scope artifacts).
    if match_count is None:
        match_count = 0 if phantom else 1
    return {"artifact": name, "in_scope": in_scope, "phantom": phantom,
            "unverifiable_pattern": unverifiable_pattern,
            "out_of_scope_class": out_of_scope_class, "match_count": match_count}


def _result(all_units, all_instr, all_pct, proc_units, proc_instr, proc_pct,
            artifacts=None, has_git=True, history_shallow=False, genres=None, mode="SKILL.md"):
    return {
        "version": "test", "root": "/fake", "mode": mode,
        "all": _agg(all_units, all_instr, all_pct),
        "procedure_only": _agg(proc_units, proc_instr, proc_pct),
        "by_genre": genres or {},
        "artifacts": artifacts or [],
        "history_shallow": history_shallow,
        "has_git": has_git,
        "skills": [],
    }


class HeaderVersionTests(unittest.TestCase):
    """The survey banner's tool-name-and-version stamp must be derived from the real package
    and scorer constants, not a hand-frozen string. It used to read "(skill-audit v0.2.1)" -
    a tool name and a version that never existed anywhere in this repo, wired to nothing (see
    CORRECTIONS.md) - while __main__.py's --version had already been printing the real
    "kibsu <pkg-version> (scorer <audit.VERSION>)" pair for the CLI itself."""

    def test_version_banner_names_the_real_versions_not_the_fake_tool(self):
        from kibsu import __version__ as pkg_version
        from kibsu.audit import VERSION as scorer_version
        banner = survey._version_banner()
        self.assertIn(pkg_version, banner)
        self.assertIn(scorer_version, banner)
        self.assertNotIn("skill-audit", banner)

    def test_printed_survey_title_line_carries_the_same_real_versions(self):
        """Not just that the helper computes the right string in isolation - that it is
        actually wired into the printed banner main() emits, the same way __main__.py's
        _cmd_version() is wired to _scorer_version()."""
        from kibsu import __version__ as pkg_version
        from kibsu.audit import VERSION as scorer_version
        out, _ = _SurveyRun(results={}).run()
        title_line = next(ln for ln in out.splitlines() if ln.startswith("CHECKABLE-INSTRUCTION SURVEY"))
        self.assertIn(pkg_version, title_line)
        self.assertIn(scorer_version, title_line)
        self.assertNotIn("skill-audit", title_line)


class ArtifactPopulationTests(unittest.TestCase):
    """An independent verifier BLOCKED the first version of the phantom counterfactual: the
    in-scope-only side (mand/phantom) is a DEDUPED SET with unverifiable_pattern excluded, but
    the 'all' side (cf_all_n/cf_all_phantom) summed len(arts) - the raw reference LIST,
    duplicates and unverifiable_pattern both included. Three axes differed (dedup,
    unverifiable_pattern, scope) where the printed sentence claimed only one (scope). This
    class pins survey._artifact_population() - the single population rule both sides must now
    share, toggling ONLY the scope filter - and proves the in-scope call reproduces row_from()'s
    own mand/phantom exactly, structurally (same function, same call), not by coincidence."""

    def test_in_scope_call_reproduces_row_froms_own_mand_and_phantom_exactly(self):
        arts = [
            _artifact("a.md", in_scope=True, phantom=True),
            _artifact("a.md", in_scope=True, phantom=True),   # duplicate mandate, same string
            _artifact("b.md", in_scope=True, phantom=False),
            _artifact("{name}.md", in_scope=True, phantom=False, unverifiable_pattern=True),
            _artifact("ex.md", in_scope=False, out_of_scope_class="scaffold-scope", match_count=0),
        ]
        names, zero = survey._artifact_population(arts, include_out_of_scope=False)
        d = _result(5, 60, 10.0, 5, 60, 10.0, artifacts=arts)
        r = survey.row_from("pop/repo", d)

        self.assertEqual(len(names), r["mand"], "not by coincidence: row_from() calls the "
                                                  "exact same function for this population")
        self.assertEqual(len(zero), r["phantom"])
        self.assertEqual(len(names), 2, "a.md deduped to one, b.md counted; {name}.md "
                                         "(unverifiable_pattern) and ex.md (out of scope) both "
                                         "excluded")
        self.assertEqual(len(zero), 1, "only a.md has zero matching instances")

    def test_all_scope_call_counts_exclusions_back_in_with_the_identical_dedup_rule(self):
        """Only the scope filter may differ between the two calls - dedup and the
        unverifiable_pattern exclusion must be IDENTICAL on both sides. Real audit.py data can
        never produce an out-of-scope unverifiable_pattern artifact (check_artifacts() sets
        `unverifiable` only when `in_scope` is already true - see audit.py's own `unverifiable =
        in_scope and literal_remainder == ""`), so this fixture keeps that same invariant."""
        arts = [
            _artifact("a.md", in_scope=True, phantom=True),
            _artifact("{name}.md", in_scope=True, phantom=False, unverifiable_pattern=True),
            _artifact("ex.md", in_scope=False, out_of_scope_class="scaffold-scope", match_count=0),
            _artifact("ex.md", in_scope=False, out_of_scope_class="scaffold-scope", match_count=0),
        ]
        names, zero = survey._artifact_population(arts, include_out_of_scope=True)
        self.assertEqual(len(names), 2, "a.md + ex.md, ex.md's duplicate mandate deduped away; "
                                         "{name}.md stays excluded as unverifiable_pattern even "
                                         "with scope exclusions counted back in")
        self.assertEqual(len(zero), 2, "both a.md and ex.md have zero matching instances")


class RowFromTests(unittest.TestCase):
    """`row_from()` is the pure, importable half of survey's aggregation - the function that
    turns one audit.py JSON result into the flat row `main()` later ranks and sums. Exercised
    directly: no mocking, no network, no subprocess."""

    def test_passes_through_unit_and_percentage_fields(self):
        d = _result(all_units=20, all_instr=300, all_pct=15.0,
                    proc_units=10, proc_instr=100, proc_pct=25.0)
        r = survey.row_from("some/repo", d)
        self.assertEqual(r["slug"], "some/repo")
        self.assertEqual(r["units"], 20)
        self.assertEqual(r["instr"], 300)
        self.assertEqual(r["pct_all"], 15.0)
        self.assertEqual(r["p_units"], 10)
        self.assertEqual(r["p_instr"], 100)
        self.assertEqual(r["pct_proc"], 25.0)

    def test_enough_true_at_exactly_the_sample_floor(self):
        d = _result(20, 300, 15.0, proc_units=survey.MIN_UNITS, proc_instr=survey.MIN_INSTR,
                    proc_pct=50.0)
        r = survey.row_from("ok/repo", d)
        self.assertTrue(r["enough"], "MIN_UNITS/MIN_INSTR are documented as the floor to RANK "
                                      "at, i.e. >=, not a strict > - exactly-at-floor must count")

    def test_enough_false_below_the_unit_floor_even_with_ample_instructions(self):
        d = _result(20, 300, 15.0, proc_units=survey.MIN_UNITS - 1, proc_instr=500, proc_pct=66.7)
        r = survey.row_from("thin-units/repo", d)
        self.assertFalse(r["enough"])

    def test_enough_false_below_the_instruction_floor_even_with_ample_units(self):
        d = _result(20, 300, 15.0, proc_units=50, proc_instr=survey.MIN_INSTR - 1, proc_pct=66.7)
        r = survey.row_from("thin-instr/repo", d)
        self.assertFalse(r["enough"])

    def test_phantom_count_only_reported_with_usable_git_history(self):
        arts = [_artifact("a.md", phantom=True), _artifact("b.md", phantom=False),
                _artifact("c.md", phantom=True)]
        d = _result(5, 60, 10.0, 5, 60, 10.0, artifacts=arts, has_git=True, history_shallow=False)
        r = survey.row_from("full-history/repo", d)
        self.assertEqual(r["mand"], 3)
        self.assertEqual(r["phantom"], 2)

    def test_phantom_is_none_on_a_shallow_clone_even_with_identical_artifacts(self):
        arts = [_artifact("a.md", phantom=True), _artifact("b.md", phantom=False)]
        d = _result(5, 60, 10.0, 5, 60, 10.0, artifacts=arts, has_git=True, history_shallow=True)
        r = survey.row_from("shallow/repo", d)
        self.assertIsNone(r["phantom"], "a shallow clone cannot prove an artifact never "
                                         "existed anywhere in history - phantom must read "
                                         "UNKNOWN (None), never a false 0")

    def test_phantom_is_none_without_git_at_all(self):
        arts = [_artifact("a.md", phantom=True)]
        d = _result(5, 60, 10.0, 5, 60, 10.0, artifacts=arts, has_git=False, history_shallow=False)
        r = survey.row_from("no-git/repo", d)
        self.assertIsNone(r["phantom"])

    def test_out_of_scope_artifacts_excluded_from_the_mandated_count(self):
        arts = [_artifact("in.md", in_scope=True), _artifact("scaffold.md", in_scope=False)]
        d = _result(5, 60, 10.0, 5, 60, 10.0, artifacts=arts)
        r = survey.row_from("mixed-scope/repo", d)
        self.assertEqual(r["mand"], 1)
        self.assertEqual(r["out"], 1)

    def test_name_collision_between_in_scope_and_out_of_scope_hides_from_the_out_count(self):
        """A genuine quirk of the shipped code, documented here rather than fixed (per the
        instruction to flag, not restructure): `out` is computed as (distinct artifact names
        total) minus (distinct IN-SCOPE names) - it is not a count of out-of-scope artifacts.
        If two different skills mandate the identical literal filename and one mandate is
        in-scope while the other is flagged out-of-scope, the name collapses into the
        in-scope set and the out-of-scope mandate of that same name becomes invisible to
        `out` entirely."""
        arts = [_artifact("shared.md", in_scope=True), _artifact("shared.md", in_scope=False)]
        d = _result(5, 60, 10.0, 5, 60, 10.0, artifacts=arts)
        r = survey.row_from("collision/repo", d)
        self.assertEqual(r["mand"], 1)
        self.assertEqual(r["out"], 0, "the out-of-scope mandate of 'shared.md' is invisible "
                                      "because the identical name is also in-scope elsewhere")

    def test_unverifiable_pattern_artifacts_excluded_from_mand_and_phantom_denominator(self):
        """audit.py's own `ver` set (see check_artifacts()/main()) excludes unverifiable_pattern
        mandates from BOTH the phantom numerator and denominator - a hit or miss on a pattern
        like `{name}.md` proves nothing either way. row_from()'s `mand`/`phantom` counts must
        agree with that, not silently count an in-scope-but-unverifiable artifact toward
        `mand` while it can structurally never contribute to `phantom` - that mismatch would
        deflate the printed phantom rate for no reason a reader could see."""
        arts = [
            _artifact("a.md", in_scope=True, phantom=True),
            _artifact("b.md", in_scope=True, phantom=False),
            _artifact("{name}.md", in_scope=True, phantom=False, unverifiable_pattern=True),
        ]
        d = _result(5, 60, 10.0, 5, 60, 10.0, artifacts=arts)
        r = survey.row_from("unverifiable/repo", d)
        self.assertEqual(r["mand"], 2, "the unverifiable_pattern artifact must not count "
                                        "toward the mandated (checkable) denominator")
        self.assertEqual(r["phantom"], 1)
        self.assertEqual(r["unverifiable"], 1)

    def test_exclusion_reason_classes_summed_per_repo(self):
        """row_from() surfaces the per-repo exclusion-class totals (audit.py's own
        out_of_scope_class on each artifact) so main() can sum them across repos into the
        disclosure ledger the printed evidence line reports - see
        SurveyAggregationTests.test_exclusion_ledger_totals_summed_across_repos_in_output."""
        arts = [
            _artifact("in.md", in_scope=True),
            _artifact("s1.md", in_scope=False, out_of_scope_class="scaffold-scope"),
            _artifact("s2.md", in_scope=False, out_of_scope_class="scaffold-scope"),
            _artifact("p1.md", in_scope=False, out_of_scope_class="prefix-missing"),
        ]
        d = _result(5, 60, 10.0, 5, 60, 10.0, artifacts=arts)
        r = survey.row_from("exclusions/repo", d)
        self.assertEqual(r["exclusions"], {"scaffold-scope": 2, "prefix-missing": 1})

    def test_genres_are_passed_through_verbatim(self):
        d = _result(5, 60, 10.0, 5, 60, 10.0,
                    genres={"procedure": {"units": 4}, "doctrine": {"units": 1}})
        r = survey.row_from("genre/repo", d)
        self.assertEqual(r["genres"], {"procedure": 4, "doctrine": 1})

    def test_counterfactual_all_rate_widens_when_excluded_artifacts_were_never_found(self):
        """Mirrors audit.py's own phantom_counterfactual() (audit.py:667) at the per-repo level:
        `cf_all_n` is every artifact reference this repo produced (in-scope and out, verifiable
        and not) and `cf_all_phantom` is how many of THOSE have zero matching instances anywhere
        (match_count == 0), regardless of scope. Negative control: two out-of-scope artifacts
        that were never found anywhere (match_count=0) must inflate the 'all' side without
        moving the in-scope side (mand/phantom) at all."""
        arts = [
            _artifact("in.md", in_scope=True, phantom=True),     # in-scope, phantom -> both sides
            _artifact("in2.md", in_scope=True, phantom=False),   # in-scope, found -> neither side
            _artifact("excluded1.md", in_scope=False, out_of_scope_class="scaffold-scope", match_count=0),
            _artifact("excluded2.md", in_scope=False, out_of_scope_class="prefix-missing", match_count=0),
        ]
        d = _result(5, 60, 10.0, 5, 60, 10.0, artifacts=arts)
        r = survey.row_from("cf/repo", d)
        self.assertEqual(r["mand"], 2, "in-scope side must be untouched by the exclusions")
        self.assertEqual(r["phantom"], 1)
        self.assertEqual(r["cf_all_n"], 4)
        self.assertEqual(r["cf_all_phantom"], 3, "the two excluded, never-found artifacts join "
                                                  "the single in-scope phantom on the 'all' side")

    def test_counterfactual_all_phantom_is_none_without_usable_history(self):
        """match_count == 0 is exactly as unreliable on a shallow clone as the existing
        `phantom` field is - same gate, same reason (a shallow clone cannot prove an artifact
        never existed anywhere in history)."""
        arts = [_artifact("a.md", in_scope=True, phantom=True, match_count=0)]
        d = _result(5, 60, 10.0, 5, 60, 10.0, artifacts=arts, has_git=True, history_shallow=True)
        r = survey.row_from("shallow/repo", d)
        self.assertEqual(r["cf_all_n"], 1, "the denominator (a pure count of references) needs "
                                            "no git history and stays a real number")
        self.assertIsNone(r["cf_all_phantom"])

    def test_counterfactual_all_side_dedupes_and_excludes_unverifiable_pattern_like_the_headline(self):
        """The bug an independent verifier caught: the old cf_all_n/cf_all_phantom summed
        len(arts) directly - the raw reference LIST - so a duplicate mandate inflated the
        denominator and an unverifiable_pattern artifact (which the headline's mand/phantom has
        always excluded) leaked into the 'all' side uncounted-for. Two skills mandating the
        identical 'dup.md', plus an in-scope unverifiable_pattern mandate, plus a duplicated
        out-of-scope mandate - the SAME dedup and unverifiable_pattern rules must govern both
        sides; only the scope filter may differ."""
        arts = [
            _artifact("dup.md", in_scope=True, phantom=True),
            _artifact("dup.md", in_scope=True, phantom=True),           # same mandate, 2 skills
            _artifact("{name}.md", in_scope=True, phantom=False, unverifiable_pattern=True),
            _artifact("out.md", in_scope=False, out_of_scope_class="scaffold-scope", match_count=0),
            _artifact("out.md", in_scope=False, out_of_scope_class="scaffold-scope", match_count=0),
        ]
        d = _result(5, 60, 10.0, 5, 60, 10.0, artifacts=arts)
        r = survey.row_from("dedup/repo", d)
        self.assertEqual(r["mand"], 1, "dup.md deduped; unverifiable_pattern excluded")
        self.assertEqual(r["phantom"], 1)
        self.assertEqual(r["cf_all_n"], 2, "dup.md + out.md, EACH deduped once - the old code "
                                            "would have read 5 (raw len(arts): duplicates and "
                                            "the unverifiable_pattern record all included)")
        self.assertEqual(r["cf_all_phantom"], 2)

    def test_out_count_is_pinned_to_the_same_population_function_as_mand_and_cf_all_n(self):
        """`out` (and therefore the aggregate bracket's "[N excluded from the phantom check]"
        distinct-artifact count) is now derived from the exact same _artifact_population() sets
        mand and cf_all_n already use - all_names minus in_scope_names - not a separately
        re-derived distinct count that could silently drift from the population discipline the
        rest of row_from() follows.

        '{name}.md' is mandated twice: once in-scope but unverifiable_pattern (no literal
        content to check - excluded from the in-scope population), once by a different skill,
        classified out-of-scope. The OLD `out` formula (distinct-all minus distinct-in-scope,
        neither side excluding unverifiable_pattern) let the in-scope mandate's mere presence
        hide the string from `out` entirely (0) - the population-based formula correctly counts
        its separate out-of-scope, verifiable instance (1), since an unverifiable in-scope
        mandate does not count as real in-scope membership under the shared discipline."""
        arts = [
            _artifact("{name}.md", in_scope=True, phantom=False, unverifiable_pattern=True),
            _artifact("{name}.md", in_scope=False, out_of_scope_class="prefix-missing", match_count=0),
        ]
        d = _result(5, 60, 10.0, 5, 60, 10.0, artifacts=arts)
        r = survey.row_from("outcount/repo", d)

        all_names, _ = survey._artifact_population(arts, include_out_of_scope=True)
        in_scope_names, _ = survey._artifact_population(arts, include_out_of_scope=False)
        self.assertEqual(r["out"], len(all_names) - len(in_scope_names),
                          "not by coincidence: row_from() computes `out` from these exact sets")
        self.assertEqual(r["out"], 1, "the OLD formula would have read 0 here - the unverifiable "
                                       "in-scope mandate hid the string's separate out-of-scope "
                                       "instance from `out` entirely")

    def test_excluded_distinct_counts_the_specimen_case_where_out_undercounts(self):
        """Round 4 DEFECT (verifier-specimen, verified against real evidence): `out` ("excluded
        outright" - DISTINCT ARTIFACTS minus IN-SCOPE DISTINCT) does NOT count a string that
        carries an exclusion record from one skill while ALSO being genuinely mandated,
        in-scope, by another - davila7's real `.mcp.json` is in scope under two skills and
        excluded under a third. `excluded_distinct` (reference records restricted to
        out-of-scope rows, deduped to strings) DOES count it, because it has at least one
        exclusion record regardless of what else is true of the string. The two numbers must
        genuinely differ for this specimen shape, not merely be printed near each other."""
        arts = [
            _artifact("shared.json", in_scope=True, phantom=False),           # skill A: in scope
            _artifact("shared.json", in_scope=False, out_of_scope_class="scaffold-scope",
                      match_count=0),                                         # skill B: excluded
            _artifact("only-excluded.md", in_scope=False,
                      out_of_scope_class="prefix-missing", match_count=0),
        ]
        d = _result(5, 60, 10.0, 5, 60, 10.0, artifacts=arts)
        r = survey.row_from("specimen/repo", d)

        self.assertEqual(r["out"], 1, "only-excluded.md is excluded outright; shared.json is "
                                       "mandated in-scope elsewhere, so `out` does not count it")
        self.assertEqual(r["excluded_distinct"], 2, "shared.json AND only-excluded.md both "
                                                      "carry at least one exclusion record")
        self.assertEqual(r["exclusions"], {"scaffold-scope": 1, "prefix-missing": 1})


def _median_line(output, label):
    """Parse one of main()'s `ranked public n=... <label> median ...% min ...% max ...%`
    lines out of captured stdout. Matched by regex rather than by exact column widths, so
    this stays robust to the print statement's own %-formatting spacing."""
    pat = re.compile(
        r"ranked public n=(\d+)\s+%s\s+median\s+([\d.]+)%%\s+min\s+([\d.]+)%%\s+max\s+([\d.]+)%%"
        % re.escape(label)
    )
    m = pat.search(output)
    assert m, "no %r median line found in:\n%s" % (label, output)
    return {"n": int(m.group(1)), "median": float(m.group(2)),
            "min": float(m.group(3)), "max": float(m.group(4))}


def _ledger_clause(output):
    """Parse the exclusion-ledger line's reconciliation clause - "<per-class breakdown> - N
    reason records across M distinct artifacts: X excluded outright (the bracket), Y also
    mandated in-scope by another skill and counted there" - out of captured stdout. Also checks
    that the per-class breakdown printed just before the clause sums to the stated record
    total, since that is exactly the reader arithmetic the clause exists to survive. Returns
    (outright, overlap, records, distinct) - X, Y, N, M, in that order, all ints."""
    pat = re.compile(
        r"exclusion ledger \(full counts, all ranked repos\): (.+?) - "
        r"(\d+) reason records across (\d+) distinct artifacts: "
        r"(\d+) excluded outright \(the bracket\), "
        r"(\d+) also mandated in-scope by another skill and counted there"
    )
    m = pat.search(output)
    assert m, "no reconciled ledger clause found in:\n%s" % output
    per_class_text, records, distinct, outright, overlap = m.groups()
    records, distinct, outright, overlap = (
        int(records), int(distinct), int(outright), int(overlap))
    per_class_sum = sum(int(v) for v in re.findall(r"=(\d+)", per_class_text))
    assert per_class_sum == records, (
        "per-class breakdown sums to %d but the clause states %d records:\n%s"
        % (per_class_sum, records, output))
    return outright, overlap, records, distinct


class _SurveyRun(object):
    """Runs the real, unmodified `survey.main()` with `clone()`, `audit()`, and `head_sha()`
    substituted for fixture data keyed by repo slug. `main()` still iterates its own real,
    hardcoded `survey.REPOS` list (ten actual GitHub slugs) - any slug not given a result or
    an explicit clone/audit error here defaults to a clone failure, so tests only need to
    describe the handful of slugs they actually care about.

    Passing the slug string itself through as `clone()`'s "dest" is deliberate: since
    `audit()` and `head_sha()` are mocked too, no real path is ever touched or needs to
    exist - this is fully offline, with no filesystem or network access of any kind.
    """

    def __init__(self, results=None, clone_errors=None, audit_errors=None):
        self.results = results or {}
        self.clone_errors = clone_errors or {}
        self.audit_errors = audit_errors or {}

    def _fake_clone(self, slug):
        if slug in self.clone_errors:
            return None, self.clone_errors[slug]
        if slug in self.results or slug in self.audit_errors:
            return slug, None  # "dest" == slug; never touched as a real path
        return None, "not used by this fixture"

    def _fake_audit(self, dest, artifacts=True):
        slug = dest
        if slug in self.audit_errors:
            return None, self.audit_errors[slug]
        return self.results[slug], None

    def run(self):
        out, err = io.StringIO(), io.StringIO()
        saved_env = {}
        for var in ("SKILL_AUDIT_LOCAL", "SKILL_AUDIT_EVIDENCE", "SKILL_AUDIT_LABEL"):
            saved_env[var] = os.environ.pop(var, None)
        try:
            with mock.patch.object(survey, "clone", side_effect=self._fake_clone), \
                 mock.patch.object(survey, "audit", side_effect=self._fake_audit), \
                 mock.patch.object(survey, "head_sha", return_value="f" * 40), \
                 mock.patch.object(sys, "argv", ["survey"]):
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    survey.main()  # must not raise - that IS part of what these tests assert
        finally:
            for var, val in saved_env.items():
                if val is not None:
                    os.environ[var] = val
        return out.getvalue(), err.getvalue()


class SurveyAggregationTests(unittest.TestCase):
    """Exercises the real `survey.main()` end to end - ranking, sample floor, median,
    genre mix, and failure reporting - with the network replaced by fixtures."""

    def test_median_and_range_computed_across_ranked_repos(self):
        slugs = survey.REPOS[:4]
        results = {}
        for slug, pp, pa in zip(slugs, [10.0, 20.0, 30.0, 40.0], [15.0, 25.0, 35.0, 45.0]):
            results[slug] = _result(all_units=10, all_instr=100, all_pct=pa,
                                     proc_units=10, proc_instr=100, proc_pct=pp)
        out, _ = _SurveyRun(results=results).run()

        proc = _median_line(out, "procedure units only")
        allu = _median_line(out, "all units")
        self.assertEqual(proc["n"], 4)
        self.assertAlmostEqual(proc["median"], 25.0)  # (20 + 30) / 2, the even-count branch
        self.assertAlmostEqual(proc["min"], 10.0)
        self.assertAlmostEqual(proc["max"], 40.0)
        self.assertAlmostEqual(allu["median"], 30.0)  # (25 + 35) / 2

    def test_below_sample_floor_repo_is_reported_but_excluded_from_ranking_and_median(self):
        thin_slug, a_slug, b_slug = survey.REPOS[0], survey.REPOS[1], survey.REPOS[2]
        results = {
            # Mirrors the README's own note: "one of the two would otherwise have topped
            # the table at 66.7% off a single unit" - a thin repo with the HIGHEST pct of
            # the run must still never enter the ranked table or the median. `all_instr`
            # must clear main()'s own "< 20 instructions" unmeasurable filter (a separate,
            # earlier check than the procedure-only sample floor this test targets) or the
            # repo is excluded before it ever reaches the floor check at all.
            thin_slug: _result(3, 30, 66.7, 1, 15, 66.7),
            a_slug: _result(10, 100, 20.0, 10, 100, 20.0),
            b_slug: _result(10, 100, 30.0, 10, 100, 30.0),
        }
        out, _ = _SurveyRun(results=results).run()

        self.assertIn("BELOW SAMPLE FLOOR", out)
        self.assertIn("1 procedure units / 15 instructions", out)
        self.assertIn("(would read 66.7%)", out)

        proc = _median_line(out, "procedure units only")
        self.assertEqual(proc["n"], 2, "the below-floor repo must not count toward n")
        self.assertAlmostEqual(proc["median"], 25.0, msg="(20 + 30) / 2, NOT influenced by 66.7")
        self.assertAlmostEqual(proc["max"], 30.0, msg="66.7% must never leak into the ranked max")

    def test_empty_result_set_does_not_crash_or_divide_by_zero(self):
        # No slug is given a result - every one of the real REPOS fails to "clone". Reaching
        # the assertions below without an exception IS the "no crash" proof.
        out, _ = _SurveyRun(results={}).run()

        self.assertIn("EXCLUDED (%d)" % len(survey.REPOS), out)
        self.assertNotIn("ranked public n=", out, "an empty result set must never print a "
                                                    "ranked/median line")
        self.assertNotIn("in-scope mandated artifacts:", out)

    def test_repo_with_fewer_than_20_total_instructions_is_excluded_as_unmeasurable(self):
        slug = survey.REPOS[0]
        results = {slug: _result(all_units=2, all_instr=10, all_pct=0.0,
                                  proc_units=2, proc_instr=10, proc_pct=0.0, mode="SKILL.md")}
        out, _ = _SurveyRun(results=results).run()

        self.assertIn("only 10 instructions (mode=SKILL.md) - unmeasurable", out)
        self.assertNotIn("BELOW SAMPLE FLOOR", out, "excluded before it ever reaches the "
                                                     "procedure sample-floor check")
        self.assertNotIn("ranked public n=", out)

    def test_clone_failure_is_reported_not_silently_dropped(self):
        slug = survey.REPOS[0]
        out, _ = _SurveyRun(clone_errors={slug: "repository not found"}).run()
        self.assertIn("clone: repository not found", out)

    def test_audit_failure_is_reported_not_silently_dropped(self):
        slug = survey.REPOS[0]
        out, _ = _SurveyRun(audit_errors={slug: "boom: traceback truncated"}).run()
        self.assertIn("audit: boom: traceback truncated", out)

    def test_exclusion_ledger_totals_summed_across_repos_in_output(self):
        """The printed "in-scope mandated artifacts" line is exactly where survey.py already
        prints phantom evidence - the disclosure ledger's totals (summed across every ranked
        public repo, not sampled) must surface right there, not in some separate, easy-to-miss
        section."""
        slug_a, slug_b = survey.REPOS[0], survey.REPOS[1]
        arts_a = [
            _artifact("in.md", in_scope=True, phantom=True),
            _artifact("s.md", in_scope=False, out_of_scope_class="scaffold-scope"),
        ]
        arts_b = [
            _artifact("p1.md", in_scope=False, out_of_scope_class="prefix-missing"),
            _artifact("p2.md", in_scope=False, out_of_scope_class="prefix-missing"),
        ]
        results = {
            slug_a: _result(10, 100, 20.0, 10, 100, 20.0, artifacts=arts_a),
            slug_b: _result(10, 100, 20.0, 10, 100, 20.0, artifacts=arts_b),
        }
        out, _ = _SurveyRun(results=results).run()

        self.assertIn("scaffold-scope=1", out)
        self.assertIn("prefix-missing=2", out)

    def test_exclusion_ledger_reconciles_with_the_bracket_distinct_count(self):
        """A verifier's reader test: sum the printed per-class ledger counts and compare against
        the bracket's "[N excluded from the phantom check]" a few lines up - they used to
        disagree with no explanation. The bracket (`to`, from `out`) is a DISTINCT-artifact
        count; the ledger is a REASON-RECORD count, and one artifact mandated by several skills
        with the same exclusion reason inflates the record count without moving the distinct
        count. The ledger line states three numbers: reason records, distinct artifacts across
        those records, and how that distinct total splits between "excluded outright" (the
        bracket) and "also mandated in-scope elsewhere" - see
        test_exclusion_ledger_clause_reconciles_the_specimen_case below for the case where that
        split is actually non-zero. Here, with no artifact both excluded AND in-scope elsewhere,
        the split's second half is 0 and distinct == bracket, by construction either way."""
        slug = survey.REPOS[0]
        arts = [
            _artifact("dup.md", in_scope=False, out_of_scope_class="prefix-missing", match_count=0),
            _artifact("dup.md", in_scope=False, out_of_scope_class="prefix-missing", match_count=0),
            _artifact("single.md", in_scope=False, out_of_scope_class="user-scope", match_count=0),
        ]
        results = {slug: _result(10, 100, 20.0, 10, 100, 20.0, artifacts=arts)}
        out, _ = _SurveyRun(results=results).run()

        bracket_m = re.search(r"\[(\d+) excluded from the phantom check", out)
        self.assertIsNotNone(bracket_m, "no bracket line found in:\n%s" % out)
        bracket_n = int(bracket_m.group(1))
        self.assertEqual(bracket_n, 2, "dup.md deduped to one, plus single.md")

        outright_n, overlap_n, records_n, distinct_n = _ledger_clause(out)
        self.assertEqual(records_n, 3, "prefix-missing=2 + user-scope=1")
        self.assertEqual(distinct_n, 2, "dup.md deduped to one, plus single.md")
        self.assertEqual(outright_n, bracket_n, "the clause's own bracket figure must equal "
                          "the bracket line's actual value")
        self.assertEqual(overlap_n, 0, "no artifact here is both excluded and in-scope "
                          "elsewhere")
        self.assertEqual(outright_n + overlap_n, distinct_n, "the clause's own three numbers "
                          "must sum correctly, not just be printed near each other")

    def test_exclusion_ledger_clause_reconciles_the_specimen_case(self):
        """Round 4 DEFECT: the reconciliation clause previously said "N reason records across M
        distinct artifacts" using `to` (excluded-outright) as M - wrong whenever a string
        carries BOTH an exclusion record and a genuine in-scope mandate elsewhere (the
        verifier's real specimen, verified against committed evidence: davila7's `.mcp.json`,
        in scope under two skills and excluded under a third). Reproduced here at the
        printed-line level: one artifact excluded by one skill while genuinely mandated,
        in-scope, by another skill."""
        slug = survey.REPOS[0]
        arts = [
            _artifact("shared.json", in_scope=True, phantom=False),
            _artifact("shared.json", in_scope=False, out_of_scope_class="scaffold-scope",
                      match_count=0),
            _artifact("only-excluded.md", in_scope=False,
                      out_of_scope_class="prefix-missing", match_count=0),
        ]
        results = {slug: _result(10, 100, 20.0, 10, 100, 20.0, artifacts=arts)}
        out, _ = _SurveyRun(results=results).run()

        bracket_m = re.search(r"\[(\d+) excluded from the phantom check", out)
        self.assertIsNotNone(bracket_m, "no bracket line found in:\n%s" % out)
        bracket_n = int(bracket_m.group(1))
        self.assertEqual(bracket_n, 1, "only-excluded.md is excluded outright; shared.json is "
                          "mandated in-scope elsewhere, so the bracket does not count it")

        outright_n, overlap_n, records_n, distinct_n = _ledger_clause(out)
        self.assertEqual(records_n, 2, "scaffold-scope=1 + prefix-missing=1")
        self.assertEqual(distinct_n, 2, "shared.json + only-excluded.md")
        self.assertEqual(outright_n, bracket_n, "the clause's own bracket figure must equal "
                          "the bracket line's actual value")
        self.assertEqual(overlap_n, 1, "shared.json alone - excluded by one skill, in-scope "
                          "via another")
        self.assertEqual(outright_n + overlap_n, distinct_n, "the clause's own three numbers "
                          "must sum correctly, not just be printed near each other")

    def test_phantom_counterfactual_line_prints_summed_in_scope_and_all_rates(self):
        """Council ruling #3 (IMP 3): the path-prefix scope filter stays IN EXCHANGE for this
        disclosure reaching every reader of the AGGREGATE table, not just a single-repo
        `audit --artifacts` run - see audit.py's phantom_counterfactual() docstring. Printed
        right where the phantom line and the exclusion ledger already are.

        Two repos: repo A mandates one real in-scope phantom plus one excluded artifact that
        was never found anywhere; repo B mandates one in-scope artifact that WAS found plus one
        excluded artifact that was never found anywhere. Summed across both:
          in-scope-only: 1 phantom / 2 mandated  = 50.0%
          all-exclusions-counted: 3 never-found / 4 total = 75.0%
        The two rates must genuinely differ - that gap IS the disclosure the council required."""
        slug_a, slug_b = survey.REPOS[0], survey.REPOS[1]
        arts_a = [
            _artifact("in.md", in_scope=True, phantom=True),
            _artifact("ex.md", in_scope=False, out_of_scope_class="scaffold-scope", match_count=0),
        ]
        arts_b = [
            _artifact("in2.md", in_scope=True, phantom=False),
            _artifact("ex2.md", in_scope=False, out_of_scope_class="prefix-missing", match_count=0),
        ]
        results = {
            slug_a: _result(10, 100, 20.0, 10, 100, 20.0, artifacts=arts_a),
            slug_b: _result(10, 100, 20.0, 10, 100, 20.0, artifacts=arts_b),
        }
        out, _ = _SurveyRun(results=results).run()

        pat = re.compile(
            r"phantom rate \(all ranked repos, summed\):\s+([\d.]+)%\s+in-scope-only\s+"
            r"\((\d+) artifacts\)\s+/\s+([\d.]+)%\s+if all exclusions are counted\s+"
            r"\((\d+) artifacts\)"
        )
        m = pat.search(out)
        self.assertTrue(m, "no aggregate phantom-counterfactual line found in:\n%s" % out)
        in_scope_pct, in_scope_n, all_pct, all_n = (float(m.group(1)), int(m.group(2)),
                                                      float(m.group(3)), int(m.group(4)))
        self.assertEqual(in_scope_n, 2)
        self.assertAlmostEqual(in_scope_pct, 50.0)
        self.assertEqual(all_n, 4)
        self.assertAlmostEqual(all_pct, 75.0)
        self.assertNotAlmostEqual(in_scope_pct, all_pct, msg="negative control: exclusions "
                                   "exist and must make the two rates genuinely differ")

        idx_phantom = out.index("in-scope mandated artifacts:")
        idx_cf = out.index("phantom rate (all ranked repos, summed):")
        self.assertGreater(idx_cf, idx_phantom, "the counterfactual disclosure must live in "
                            "the same block as the phantom headline, not float elsewhere")

    def test_aggregate_counterfactual_deduplicates_and_excludes_unverifiable_across_repos(self):
        """Requirement (c) of the verifier's finding: the live-shape aggregate on a two-repo
        fixture, by hand-computed expected values, with BOTH the duplicate-reference and
        unverifiable_pattern traps the finding named baked in. Repo A mandates 'in.md' via two
        skills (a duplicate reference), an in-scope unverifiable_pattern mandate, and one
        excluded, never-found artifact. Repo B mandates one in-scope artifact that WAS found and
        one excluded, never-found artifact mandated by two skills (another duplicate). Hand
        computed:
          in-scope-only: 1 phantom / 2 mandated = 50.0%   (in.md phantom, in2.md found)
          all-exclusions-counted: 3 never-found / 4 total = 75.0%
              (in.md, ex.md, ex2.md each deduped once and zero-match; in2.md found;
               {x}.md excluded as unverifiable_pattern on both sides)
        The buggy raw-list version this replaces summed len(arts) = 7 (both duplicates and the
        unverifiable_pattern record all counted) with 5 zero-match records, printing 71.4%
        instead of the correct 75.0% - a real, not hypothetical, gap."""
        slug_a, slug_b = survey.REPOS[0], survey.REPOS[1]
        arts_a = [
            _artifact("in.md", in_scope=True, phantom=True),
            _artifact("in.md", in_scope=True, phantom=True),               # duplicate mandate
            _artifact("{x}.md", in_scope=True, phantom=False, unverifiable_pattern=True),
            _artifact("ex.md", in_scope=False, out_of_scope_class="scaffold-scope", match_count=0),
        ]
        arts_b = [
            _artifact("in2.md", in_scope=True, phantom=False),
            _artifact("ex2.md", in_scope=False, out_of_scope_class="prefix-missing", match_count=0),
            _artifact("ex2.md", in_scope=False, out_of_scope_class="prefix-missing", match_count=0),
        ]
        results = {
            slug_a: _result(10, 100, 20.0, 10, 100, 20.0, artifacts=arts_a),
            slug_b: _result(10, 100, 20.0, 10, 100, 20.0, artifacts=arts_b),
        }
        out, _ = _SurveyRun(results=results).run()

        pat = re.compile(
            r"phantom rate \(all ranked repos, summed\):\s+([\d.]+)%\s+in-scope-only\s+"
            r"\((\d+) artifacts\)\s+/\s+([\d.]+)%\s+if all exclusions are counted\s+"
            r"\((\d+) artifacts\)"
        )
        m = pat.search(out)
        self.assertTrue(m, "no aggregate phantom-counterfactual line found in:\n%s" % out)
        in_scope_pct, in_scope_n, all_pct, all_n = (float(m.group(1)), int(m.group(2)),
                                                      float(m.group(3)), int(m.group(4)))
        self.assertEqual(in_scope_n, 2)
        self.assertAlmostEqual(in_scope_pct, 50.0)
        self.assertEqual(all_n, 4, "deduped and unverifiable-excluded, not the raw 7-record list")
        self.assertAlmostEqual(all_pct, 75.0, msg="not the buggy 71.4% (5 of 7) the raw-list "
                                                    "version of this line would have printed")

    def test_aggregate_all_side_denominator_skips_the_same_repos_the_numerator_skips(self):
        """FIX 2 (latent, same block): the 'all' denominator used to sum every ranked repo's
        cf_all_n regardless of whether that repo's cf_all_phantom was even usable, while the
        numerator already skipped repos with unusable history (cf_all_phantom is None on a
        shallow clone). A repo with a shallow clone would silently deflate the printed 'all'
        rate by padding the denominator with zero matching numerator contribution. Repo A has
        full history and both its artifacts are zero-match; repo B has a shallow clone and must
        be skipped by BOTH sides of the 'all' fraction, not just the numerator."""
        slug_a, slug_b = survey.REPOS[0], survey.REPOS[1]
        arts_a = [
            _artifact("in.md", in_scope=True, phantom=True),
            _artifact("ex.md", in_scope=False, out_of_scope_class="scaffold-scope", match_count=0),
        ]
        arts_b = [_artifact("z.md", in_scope=True, phantom=True)]  # would-be noise if summed in
        results = {
            slug_a: _result(10, 100, 20.0, 10, 100, 20.0, artifacts=arts_a,
                             has_git=True, history_shallow=False),
            slug_b: _result(10, 100, 20.0, 10, 100, 20.0, artifacts=arts_b,
                             has_git=True, history_shallow=True),
        }
        out, _ = _SurveyRun(results=results).run()

        pat = re.compile(
            r"phantom rate \(all ranked repos, summed\):\s+([\d.]+)%\s+in-scope-only\s+"
            r"\((\d+) artifacts\)\s+/\s+([\d.]+)%\s+if all exclusions are counted\s+"
            r"\((\d+) artifacts\)"
        )
        m = pat.search(out)
        self.assertTrue(m, "no aggregate phantom-counterfactual line found in:\n%s" % out)
        all_pct, all_n = float(m.group(3)), int(m.group(4))
        self.assertEqual(all_n, 2, "repo B's shallow-history artifact must not inflate the "
                                    "denominator when its numerator is unusable (None)")
        self.assertAlmostEqual(all_pct, 100.0, msg="both of repo A's artifacts are zero-match "
                                                     "and repo B contributes nothing to either side")

    def test_genre_mix_summary_silently_omits_doctrine_units(self):
        """A genuine finding surfaced BY writing this test, not asserted-then-fixed: the
        printed "genre mix" aggregate sums four of the five genres audit.py recognises -
        procedure, persona, reference, mixed - and OMITS doctrine, even though a row's
        `genres` dict can carry a doctrine count and the README's own genre table lists
        doctrine as one of four first-class genres. A collection that is mostly doctrine
        content still prints a genre mix with no doctrine key and no indication anything
        was left out of the total."""
        slug = survey.REPOS[0]
        results = {slug: _result(all_units=20, all_instr=300, all_pct=15.0,
                                  proc_units=10, proc_instr=100, proc_pct=25.0,
                                  genres={"procedure": {"units": 10}, "doctrine": {"units": 9}})}
        out, _ = _SurveyRun(results=results).run()

        genre_mix_line = next(ln for ln in out.splitlines() if ln.startswith("genre mix:"))
        self.assertIn("'procedure': 10", genre_mix_line)
        self.assertNotIn("doctrine", genre_mix_line, "doctrine units are silently excluded "
                                                       "from the printed genre mix total")


class SurveyNetworkTests(unittest.TestCase):
    """The one piece of survey.py that genuinely cannot run offline: the real `clone()` /
    `audit()` reaching github.com and shelling out to audit.py as a subprocess. Everything
    else in this file exercises the real aggregation logic without hitting the network -
    this is the only remaining skip, and it carries its own explicit reason rather than
    being a blanket, file-level skip."""

    @unittest.skip(
        "survey.py's clone()/audit() perform real network I/O (git clone over HTTPS) and "
        "spawn audit.py as a subprocess against each clone - reproducing that here would "
        "make this a live integration probe (network flake, GitHub rate limits, upstream "
        "repos moving) rather than a deterministic unit test. The aggregation those two "
        "functions feed - ranking, sample floor, median, genre mix, failure reporting - is "
        "fully covered offline above via RowFromTests and SurveyAggregationTests, which "
        "substitute clone()/audit()/head_sha() with fixtures instead of faking main()'s "
        "own logic."
    )
    def test_real_network_clone_and_audit_not_exercised_offline(self):
        pass  # pragma: no cover - intentionally never runs


class RealEvidenceReconciliationTests(unittest.TestCase):
    """Pin against the actual committed evidence/*.json - not a synthetic fixture. The Round 4
    verifier's finding was computed against the 0.5.0 evidence (26 distinct artifacts across
    exclusion records, 25 excluded outright, 1 overlap - davila7's `.mcp.json`); the 0.6.0
    re-measure (CORRECTIONS.md, 2026-08-07) moved the pins to 30/27/3 - the overlap grew to
    three davila7 artifacts (`.mcp.json`, `progress.md`, `task_plan.md`), each mandated
    in-scope by one skill and excluded under another. The trip-wire fired exactly as this
    docstring said it would, and these constants moved WITH the evidence in the same commit."""

    def test_ledger_reconciliation_on_committed_evidence(self):
        evidence_dir = os.path.join(PACKAGE_ROOT, "evidence")
        if not os.path.isdir(evidence_dir):
            self.skipTest("no evidence/ directory in this checkout")
        rows = []
        for slug in survey.REPOS:
            fn = os.path.join(evidence_dir, slug.replace("/", "__") + ".json")
            if not os.path.isfile(fn):
                continue
            with open(fn, encoding="utf-8") as fh:
                payload = json.load(fh)
            d = payload["result"]
            if d["all"]["instructions"] < 20:
                continue
            r = survey.row_from(slug, d)
            if r["enough"]:
                rows.append(r)
        self.assertTrue(rows, "no ranked repos found in evidence/ - fixture assumption broken")

        to = sum(r["out"] for r in rows)
        te = sum(r["excluded_distinct"] for r in rows)
        self.assertEqual(to, 27, "bracket (excluded outright) on committed evidence")
        self.assertEqual(te, 30, "distinct artifacts across exclusion records")
        self.assertEqual(te - to, 3, "davila7's .mcp.json, progress.md, task_plan.md - each "
                                      "in scope under one skill, excluded under another")


if __name__ == "__main__":
    unittest.main()
