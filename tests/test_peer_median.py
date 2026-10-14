#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`report` compares every repository to a published number, so that number gets a checker.

report.py carries the survey's procedure-only median as a constant - the wheel does not ship
`evidence/`, so it cannot be computed where the tool runs. Question 3's mark is decided by
that constant: above it reads `+`, at or below it reads `x`.

For three releases (0.6.0, 0.7.0, 0.8.0) the constant stayed at 9.4, the median under scorer
0.6.0, while the scorer moved through 0.7.0, 0.8.0, 0.9.0 and 0.10.0 and the published median
moved to 7.7 and then 7.5. Four measurement rounds regenerated `evidence/` and the README
table; none of them touched report.py, because nothing connected the two. So the flagship
command measured a stranger's repository with the strict instrument and compared the answer to
a median taken with the lenient one - and a repository between 7.5% and 9.4% was told it sat
below a median it was above. One of this project's own eight survey rows is in that band.

The guard is the same shape as test_readme_counts.py: the constant must equal what the
committed evidence gives, computed through the survey's own row_from() and median() - not a
second copy of either - and the scorer the constant is labelled with must be the scorer the
evidence records. A measurement round that regenerates `evidence/` now fails this suite until
report.py moves with it.

What it deliberately does NOT assert: that the running scorer equals the median's scorer. An
instrument change and its re-measurement are separate changes in this repository, and between
them that inequality is the truth. report.py discloses it in the finding instead
(median_note), and that disclosure has its own two tests below.

Per CONTRIBUTING rule 4 every check here has a negative control, and the match test ran RED
against the shipped constant (9.4 against 7.5) before it was corrected in the same change."""
import contextlib
import glob
import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from support import PACKAGE_ROOT, make_repo, run_tool

sys.path.insert(0, PACKAGE_ROOT)
from kibsu import report, survey  # noqa: E402 -- must follow the sys.path.insert above
from kibsu.survey import median  # noqa: E402 -- ditto; the survey's own, never a copy


def evidence_rows():
    """Every committed evidence file as (survey row, scorer version it records)."""
    out = []
    for path in sorted(glob.glob(os.path.join(PACKAGE_ROOT, "evidence", "*.json"))):
        with io.open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        out.append((survey.row_from(d["repo"], d["result"]), d["result"].get("version")))
    return out


def peer_median_problems(peer_median, peer_scorer, rows):
    """Every way report.py's constant can disagree with the evidence it summarises. Returns a
    list of human-readable findings - empty when the two agree."""
    problems = []
    ranked = [r for r, _ in rows if r["enough"]]
    if not ranked:
        return ["no ranked repository in evidence/ - there is no median to compare against"]
    measured = median(r["pct_proc"] for r in ranked)
    if "%.1f" % measured != "%.1f" % peer_median:
        problems.append("report.PEER_MEDIAN is %.1f, the committed evidence gives %.1f "
                        "(n=%d ranked)" % (peer_median, measured, len(ranked)))
    versions = sorted({str(v) for _, v in rows})
    if len(versions) != 1:
        problems.append("evidence/ mixes scorer versions (%s) - one median cannot describe it"
                        % ", ".join(versions))
    elif versions[0] != peer_scorer:
        problems.append("report.PEER_MEDIAN_SCORER is %s, the evidence was measured with %s"
                        % (peer_scorer, versions[0]))
    return problems


class PeerMedianTests(unittest.TestCase):
    def test_the_shipped_constant_is_what_the_committed_evidence_gives(self):
        self.assertEqual(
            peer_median_problems(report.PEER_MEDIAN, report.PEER_MEDIAN_SCORER,
                                 evidence_rows()), [])

    def test_negative_control_a_stale_median_is_caught(self):
        problems = peer_median_problems(9.4, report.PEER_MEDIAN_SCORER, evidence_rows())
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("9.4", problems[0])

    def test_negative_control_a_stale_scorer_label_is_caught(self):
        problems = peer_median_problems(report.PEER_MEDIAN, "0.6.0", evidence_rows())
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("0.6.0", problems[0])

    def test_negative_control_evidence_from_two_scorers_is_caught(self):
        rows = evidence_rows()
        rows[0] = (rows[0][0], "0.0.0")
        problems = peer_median_problems(report.PEER_MEDIAN, report.PEER_MEDIAN_SCORER, rows)
        self.assertTrue(any("mixes scorer versions" in p for p in problems), problems)


class SurveyMainTests(unittest.TestCase):
    """#111: the guard above used to end in `assertIs(median, survey.median)`, true by
    construction - both names came from one import - so it could not fail, and a survey.main()
    that computed the published median with its own arithmetic would have passed it. These run
    survey.main() itself, with its clones and audits replaced by the committed evidence, and
    read the median it prints."""

    def _run_main(self):
        evidence = {}
        for path in glob.glob(os.path.join(PACKAGE_ROOT, "evidence", "*.json")):
            with io.open(path, encoding="utf-8") as fh:
                d = json.load(fh)
            evidence[d["repo"]] = d
        saved = (survey.clone, survey.audit, survey.head_sha, survey.EVIDENCE, sys.argv,
                 os.environ.pop("SKILL_AUDIT_LOCAL", None))
        survey.clone = lambda slug: (slug, None) if slug in evidence else (None, "not in evidence/")
        survey.audit = lambda dest, artifacts=True: (evidence[dest]["result"], None)
        survey.head_sha = lambda dest: evidence[dest]["sha"]
        survey.EVIDENCE, sys.argv = None, ["survey"]       # write nothing; no local extra row
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                survey.main()
        finally:
            survey.clone, survey.audit, survey.head_sha, survey.EVIDENCE, sys.argv = saved[:5]
            if saved[5] is not None:
                os.environ["SKILL_AUDIT_LOCAL"] = saved[5]
        return out.getvalue()

    def _printed_median(self, out):
        m = re.search(r"procedure units only\s+median\s+([\d.]+)%", out)
        self.assertIsNotNone(m, "no procedure-only median line in:\n%s" % out)
        return float(m.group(1))

    def test_survey_main_prints_the_median_report_ships(self):
        self.assertEqual("%.1f" % self._printed_median(self._run_main()),
                         "%.1f" % report.PEER_MEDIAN)

    def test_negative_control_survey_main_computes_it_through_median(self):
        """Swap median() for a stand-in and the printed figure must follow it. A main() with
        its own arithmetic would print 7.6 here regardless."""
        real = survey.median
        survey.median = lambda values: 42.0
        try:
            out = self._run_main()
        finally:
            survey.median = real
        self.assertEqual(self._printed_median(out), 42.0)


# Thirty numbered procedure steps, one in five naming a command: enough for question 3 to judge.
PROCEDURE = "---\ngenre: procedure\n---\n# Release\n\n## Steps\n\n" + "".join(
    "%d. %s\n" % (i + 1, ("Run `make test` before step %d." % i) if i % 5 == 0 else
                   ("Always check the release notes for step %d." % i)) for i in range(30))


class ReportUsesThePublishedMedianTests(unittest.TestCase):
    """#111: the constant was guarded, its use was not. `--peer-median` defaulting back to the
    stale 9.4 - the exact drift #95 fixed - left all 316 tests green, and so did dropping the
    median_note() call from main(). These read what `report` prints."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="kibsu_test_peer_median_")
        self.repo = make_repo(os.path.join(self.tmpdir, "repo"),
                              {".claude/skills/release.md": PROCEDURE})

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _prove(self, *args, **kwargs):
        _, stdout, stderr = run_tool("report", self.repo, "--json", *args, **kwargs)
        return next(f for f in json.loads(stdout)["findings"]
                    if f["title"] == "Prove they followed")

    def test_report_compares_against_the_median_it_ships(self):
        prove = self._prove()
        self.assertIn(prove["mark"], ("+", "x"), prove)
        self.assertIn("the %.1f%% public median)" % report.PEER_MEDIAN, prove["detail"])
        self.assertNotIn("measured with scorer", prove["detail"], "like for like: no note")

    def test_a_median_the_reader_passes_replaces_ours_and_carries_no_note(self):
        prove = self._prove("--peer-median", "50")
        self.assertIn("the 50.0% public median)", prove["detail"])
        self.assertNotIn("measured with scorer", prove["detail"])

    def test_negative_control_a_run_on_another_scorer_says_so_in_the_finding(self):
        """report.main() must route the finding through median_note(). A copy of the package
        whose scorer reports another version is the run that should carry the note."""
        pkg = os.path.join(self.tmpdir, "pkg")
        shutil.copytree(os.path.join(PACKAGE_ROOT, "kibsu"), os.path.join(pkg, "kibsu"))
        audit_py = os.path.join(pkg, "kibsu", "audit.py")
        with io.open(audit_py, encoding="utf-8") as fh:
            src = fh.read()
        anchor = 'VERSION = "%s"' % report.PEER_MEDIAN_SCORER
        self.assertIn(anchor, src, "the scorer version line moved - update this test")
        with io.open(audit_py, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(src.replace(anchor, 'VERSION = "9.9.9"', 1))
        prove = self._prove(cwd=pkg)
        self.assertIn("measured with scorer %s and this run used 9.9.9"
                      % report.PEER_MEDIAN_SCORER, prove["detail"])


class TieTests(unittest.TestCase):
    """#111: nothing pinned which way an exact tie goes, and `>` -> `>=` stayed green.
    verifiability_verdict()'s rule is that a repository is ready when it BEATS the public
    median, so a tie is not a pass."""

    def test_a_repository_at_the_median_is_not_marked_ready(self):
        self.assertEqual(report.verifiability_verdict(report.PEER_MEDIAN, report.PEER_MEDIAN),
                         (report.BAD, "below"))

    def test_negative_control_just_above_the_median_is_ready(self):
        self.assertEqual(report.verifiability_verdict(report.PEER_MEDIAN + 0.05,
                                                      report.PEER_MEDIAN),
                         (report.OK, "above"))


class MedianNoteTests(unittest.TestCase):
    """The window the guard above leaves open on purpose is closed in the output instead."""

    def test_a_like_for_like_comparison_carries_no_note(self):
        self.assertEqual(report.median_note(report.PEER_MEDIAN_SCORER, report.PEER_MEDIAN), "")

    def test_negative_control_a_different_scorer_is_disclosed_in_the_finding(self):
        note = report.median_note("99.0.0", report.PEER_MEDIAN)
        self.assertIn("99.0.0", note)
        self.assertIn(report.PEER_MEDIAN_SCORER, note)

    def test_a_median_the_caller_supplied_is_theirs_to_vouch_for(self):
        """--peer-median replaces our number with the reader's; a note about OUR scorer on
        THEIR number would be a claim about a measurement we never saw."""
        self.assertEqual(report.median_note("99.0.0", report.PEER_MEDIAN + 1.0), "")


if __name__ == "__main__":
    unittest.main()
