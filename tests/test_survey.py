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
import os
import re
import sys
import unittest
import unittest.mock as mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kibsu import survey


# ---------------------------------------------------------------------------------------
# Fixture builders - construct the exact JSON shape audit.py's `--json` output has (see
# kibsu/audit.py's `json.dumps(dict(version=..., root=..., mode=..., all=ALL,
# procedure_only=PROC, by_genre=..., artifacts=..., history_shallow=..., has_git=...,
# skills=...))`), which is what `audit()` in survey.py hands back to `row_from()` / `main()`.
# ---------------------------------------------------------------------------------------

def _agg(units, instructions, pct, zero=0):
    return {"units": units, "instructions": instructions, "pct": pct, "zero": zero}


def _artifact(name, in_scope=True, phantom=False, unverifiable_pattern=False,
              out_of_scope_class=None):
    return {"artifact": name, "in_scope": in_scope, "phantom": phantom,
            "unverifiable_pattern": unverifiable_pattern,
            "out_of_scope_class": out_of_scope_class}


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


if __name__ == "__main__":
    unittest.main()
