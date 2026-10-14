#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Issue #112: a failure is not an absence.

"Could not check" and "nothing there" are different answers, and five paths gave the second
for the first. report and explain ran the scorer and kept only its stdout, so a crash, a file
over the size ceiling and a link out of the repository all read as "no agent-instruction
directory found. Nothing here tells agents how to work"; a mistyped --skills read the same; a
UTF-16 file was decoded into NULs and presented as a genre decision; a malformed .kibsu.json
was a traceback.

Per CONTRIBUTING rule 4, every test here ran red against fc56083 first, and each case has its
control: a repository that IS readable must not gain any of these notes."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from support import PACKAGE_ROOT, assert_repo_untouched, make_repo, run_tool

sys.path.insert(0, PACKAGE_ROOT)
from kibsu import audit  # noqa: E402 -- must follow the sys.path.insert above

SKILL = ("# Deploy\n\n## Steps\n\n1. Run `make test` before you push.\n"
         "2. Always check the release notes.\n")
BIG = ("x" * 79 + "\n") * (6 * 1024 * 1024 // 80)      # ~6 MB, over the 5 MB ceiling


def _finding(stdout, title):
    return next(f for f in json.loads(stdout)["findings"] if f["title"] == title)


class ScorerFailureTests(unittest.TestCase):
    """A scorer that fails must be named as one. The scorer is broken on purpose in a COPY of
    the package - the shipped one has no known crash left to drive this with (#107)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="kibsu_test_failures_")
        self.pkg = os.path.join(self.tmpdir, "pkg")
        shutil.copytree(os.path.join(PACKAGE_ROOT, "kibsu"), os.path.join(self.pkg, "kibsu"))
        audit_py = os.path.join(self.pkg, "kibsu", "audit.py")
        with open(audit_py, encoding="utf-8") as fh:
            src = fh.read()
        anchor = "    a = ap.parse_args()\n    global INCLUDE_ARCHIVED"
        self.assertIn(anchor, src, "the sabotage anchor moved - update this test")
        with open(audit_py, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(src.replace(anchor, "    a = ap.parse_args()\n"
                                 "    raise RuntimeError('deliberate test failure')\n"
                                 "    global INCLUDE_ARCHIVED", 1))
        self.repo = make_repo(os.path.join(self.tmpdir, "repo"),
                              {".claude/skills/deploy.md": SKILL})

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_report_names_a_failed_scorer_instead_of_an_empty_repository(self):
        exit_code, stdout, stderr = run_tool("report", self.repo, "--json", cwd=self.pkg)
        prove = _finding(stdout, "Prove they followed")
        self.assertEqual(prove["mark"], "?", prove)
        self.assertIn("the scorer could not measure", prove["detail"])
        self.assertIn("deliberate test failure", prove["detail"])
        self.assertNotIn("no agent-instruction directory found", stdout)
        self.assertEqual(exit_code, 3)
        assert_repo_untouched(self.repo)

    def test_explain_names_a_failed_scorer_instead_of_an_empty_repository(self):
        exit_code, stdout, stderr = run_tool("explain", self.repo, cwd=self.pkg)
        self.assertIn("the scorer could not measure", stdout)
        self.assertIn("deliberate test failure", stdout)
        self.assertNotIn("Nothing here tells agents how to work", stdout)
        self.assertEqual(exit_code, 3)
        assert_repo_untouched(self.repo)

    def test_negative_control_the_unbroken_scorer_measures_the_same_repository(self):
        exit_code, stdout, _ = run_tool("report", self.repo, "--json")
        self.assertNotIn("could not measure", _finding(stdout, "Prove they followed")["detail"])
        exit_code, stdout, _ = run_tool("explain", self.repo)
        self.assertEqual(exit_code, 0)
        self.assertNotIn("could not measure", stdout)


class MistypedSkillsTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="kibsu_test_failures_")
        self.repo = make_repo(self.tmpdir, {".claude/skills/deploy.md": SKILL})
        self.typo = os.path.join(self.repo, ".claude", "skilz")
        self.right = os.path.join(self.repo, ".claude", "skills")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_report_says_the_named_directory_does_not_exist(self):
        exit_code, stdout, _ = run_tool("report", self.repo, "--skills", self.typo, "--json")
        prove = _finding(stdout, "Prove they followed")
        self.assertEqual(prove["mark"], "?", prove)
        self.assertIn("is not a directory", prove["detail"])
        self.assertNotIn("no agent-instruction directory found", stdout)
        self.assertEqual(exit_code, 3)
        # Control: the same flag, spelled right, measures.
        _, stdout, _ = run_tool("report", self.repo, "--skills", self.right, "--json")
        self.assertNotIn("is not a directory", _finding(stdout, "Prove they followed")["detail"])
        assert_repo_untouched(self.repo)

    def test_explain_says_the_named_directory_does_not_exist(self):
        exit_code, stdout, _ = run_tool("explain", self.repo, "--skills", self.typo)
        self.assertIn("is not a directory", stdout)
        self.assertNotIn("Nothing here tells agents how to work", stdout)
        self.assertEqual(exit_code, 3)
        exit_code, _, _ = run_tool("explain", self.repo, "--skills", self.right)
        self.assertEqual(exit_code, 0)
        assert_repo_untouched(self.repo)


class UnreadFileTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="kibsu_test_failures_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _repo_with(self, name, write):
        skills = os.path.join(self.tmpdir, ".claude", "skills")
        os.makedirs(skills)
        write(os.path.join(skills, name))
        return make_repo(self.tmpdir, {".claude/skills/deploy.md": SKILL})

    def test_an_oversized_file_is_named_by_report_and_explain(self):
        """audit already skipped it with a line on stderr; report and explain threw the line
        away, so the figures shrank with nothing on screen to say why."""
        def big(path):
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(BIG)
        repo = self._repo_with("huge.md", big)
        _, stdout, _ = run_tool("report", repo, "--json")
        unread = json.loads(stdout)["unread_files"]
        self.assertEqual(len(unread), 1, unread)
        self.assertTrue(unread[0].startswith(".claude/skills/huge.md ("), unread)
        self.assertTrue(unread[0].endswith("byte ceiling)"), unread)
        _, stdout, _ = run_tool("explain", repo)
        self.assertIn("The scorer did not read 1 file", stdout)
        self.assertIn("huge.md", stdout)
        assert_repo_untouched(repo)

    def test_a_utf16_file_is_named_as_unreadable_not_scored_as_a_genre(self):
        """What PowerShell's `>` writes. Decoded as UTF-8 it was every-other-byte NUL, scored as
        a `mixed` unit of zero instructions, and explain counted it among the units for which
        "checkability is not a fair test"."""
        def wide(path):
            with open(path, "w", encoding="utf-16") as fh:
                fh.write("Run `make test`.\nNever skip the build.\n")
        repo = self._repo_with("wide.md", wide)
        skills = os.path.join(repo, ".claude", "skills")
        _, stdout, stderr = run_tool("audit", skills, "--json")
        self.assertEqual([s["skill"] for s in json.loads(stdout)["skills"]], ["deploy.md"])
        self.assertIn("kibsu audit: skipping wide.md (not UTF-8 text: a UTF-16 byte-order mark)",
                      stderr)
        _, stdout, _ = run_tool("explain", repo, "--all-genres")
        self.assertIn("wide.md (not UTF-8 text", stdout)
        self.assertNotIn("mixed unit", stdout)
        assert_repo_untouched(repo)

    def test_negative_control_a_readable_repository_reports_no_unread_files(self):
        repo = make_repo(self.tmpdir, {".claude/skills/deploy.md": SKILL})
        _, stdout, _ = run_tool("report", repo, "--json")
        self.assertEqual(json.loads(stdout)["unread_files"], [])
        _, stdout, _ = run_tool("explain", repo)
        self.assertNotIn("did not read", stdout)
        assert_repo_untouched(repo)


class NotUtf8TextTests(unittest.TestCase):
    def test_wide_encodings_and_nul_bytes_are_refused(self):
        self.assertEqual(audit.not_utf8_text(b"\xff\xfe" + "x".encode("utf-16-le")),
                         "a UTF-16 byte-order mark")
        self.assertEqual(audit.not_utf8_text(b"\xfe\xff" + "x".encode("utf-16-be")),
                         "a UTF-16 byte-order mark")
        self.assertEqual(audit.not_utf8_text(b"\xff\xfe\x00\x00" + "x".encode("utf-32-le")),
                         "a UTF-32 byte-order mark")
        self.assertEqual(audit.not_utf8_text(b"\x00\x00\xfe\xff" + "x".encode("utf-32-be")),
                         "a UTF-32 byte-order mark")
        self.assertEqual(audit.not_utf8_text("Run make test.\n".encode("utf-16-le")),
                         "NUL bytes throughout - UTF-16 or UTF-32 with no byte-order mark")

    def test_negative_control_text_that_reads_today_still_reads(self):
        """Only bytes that were never text are refused. A UTF-8 byte-order mark, an accented
        Latin-1 byte (one replacement character, as before) and Arabic all still read."""
        self.assertIsNone(audit.not_utf8_text(b"\xef\xbb\xbfRun `make test`.\n"))
        self.assertIsNone(audit.not_utf8_text("Caf\xe9 rules.\n".encode("latin-1")))
        self.assertIsNone(audit.not_utf8_text("اقرأ الدليل أولاً.\n".encode("utf-8")))
        self.assertIsNone(audit.not_utf8_text(b""))

    def test_negative_control_a_stray_nul_in_a_text_file_does_not_refuse_it(self):
        """A file that scored before a stray NUL was appended still scores: refusing it would
        trade one silent change of the figures for another. One NUL in twenty bytes is where
        text stops being text."""
        body = SKILL.encode("utf-8") + b"\x00"
        self.assertIsNone(audit.not_utf8_text(body))
        self.assertIsNone(audit.not_utf8_text(b"x" * 20 + b"\x00"))       # 1 in 21: text
        self.assertIsNotNone(audit.not_utf8_text(b"x" * 19 + b"\x00"))    # 1 in 20: refused


class NothingReadableTests(unittest.TestCase):
    """The adversarial pass on this change: when EVERY instruction file is unreadable, the
    scorer returns an empty measurement, and an empty measurement read as an empty repository -
    "your instructions promise no artifacts at all", "Every instruction in scope can be
    checked". A run that read nothing is a failure to name, like a crash."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="kibsu_test_failures_")
        with open(os.path.join(self.tmpdir, "AGENTS.md"), "w", encoding="utf-16") as fh:
            fh.write("Run `make test` before pushing.\nAlways check the log.\n")
        self.repo = make_repo(self.tmpdir, {"README.md": "# Readme\n"})

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_report_names_the_unread_file_instead_of_judging_nothing(self):
        exit_code, stdout, _ = run_tool("report", self.repo, "--json")
        result = json.loads(stdout)
        for title in ("Prove they followed", "Resume after a break"):
            found = _finding(stdout, title)
            self.assertEqual(found["mark"], "?", found)
        self.assertIn("could read none", _finding(stdout, "Prove they followed")["detail"])
        self.assertEqual(len(result["unread_files"]), 1)
        self.assertTrue(result["unread_files"][0].startswith("AGENTS.md (not UTF-8 text"),
                        result["unread_files"])
        self.assertEqual(exit_code, 3)
        assert_repo_untouched(self.repo)

    def test_explain_names_the_unread_file_instead_of_listing_nothing(self):
        exit_code, stdout, _ = run_tool("explain", self.repo)
        self.assertEqual(exit_code, 3)
        self.assertIn("could read none", stdout)
        self.assertIn("AGENTS.md (not UTF-8 text", stdout)
        self.assertNotIn("Every instruction in scope can be checked", stdout)
        self.assertNotIn("figures above", stdout, "there are no figures on a failure")
        exit_code, stdout, _ = run_tool("explain", self.repo, "--json")
        result = json.loads(stdout)
        self.assertIs(result["complete"], False)
        self.assertEqual(len(result["unread_files"]), 1)
        assert_repo_untouched(self.repo)


class OutputShapeTests(unittest.TestCase):
    """Where the unread note sits, how its paths read, and what the reproduction hint runs."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="kibsu_test_failures_")
        skills = os.path.join(self.tmpdir, ".claude", "skills")
        os.makedirs(skills)
        with open(os.path.join(skills, "wide.md"), "w", encoding="utf-16") as fh:
            fh.write("Never skip the build.\n")
        self.repo = make_repo(self.tmpdir, {".claude/skills/deploy.md": SKILL})

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _last_line(self, stdout):
        return [ln for ln in stdout.splitlines() if ln.strip()][-1].strip()

    def test_the_no_write_guarantee_stays_last_and_the_unread_note_comes_before_it(self):
        for tool in ("report", "explain"):
            _, stdout, _ = run_tool(tool, self.repo)
            self.assertEqual(self._last_line(stdout),
                             "Nothing was written to this repo - run `git status` to confirm.",
                             tool)
            self.assertIn("The scorer did not read 1 file", stdout, tool)
            self.assertLess(stdout.index("did not read"), stdout.index("Nothing was written"))
        assert_repo_untouched(self.repo)

    def test_unread_paths_are_relative_to_the_repository_like_every_other_path(self):
        _, stdout, _ = run_tool("report", self.repo, "--json")
        self.assertEqual(json.loads(stdout)["unread_files"],
                         [".claude/skills/wide.md (not UTF-8 text: a UTF-16 byte-order mark)"])
        _, stdout, _ = run_tool("explain", self.repo, "--json")
        self.assertEqual(json.loads(stdout)["unread_files"],
                         [".claude/skills/wide.md (not UTF-8 text: a UTF-16 byte-order mark)"])

    def test_a_lone_cr_file_reads_as_its_lf_twin(self):
        """The bytes are read once and decoded as io.open decoded them, universal newlines
        included. A plain bytes.decode() would leave old-Mac line ends as one long line."""
        lf = "# Deploy\n\nRun `make test`.\n\nAlways check the log.\n"
        counts = []
        for name, body in (("lf.md", lf), ("cr.md", lf.replace("\n", "\r"))):
            d = os.path.join(self.tmpdir, "twin-" + name)
            os.makedirs(d)
            with open(os.path.join(d, name), "w", encoding="utf-8", newline="") as fh:
                fh.write(body)
            _, stdout, _ = run_tool("audit", d, "--json")
            r = json.loads(stdout)["all"]
            counts.append((r["lines"], r["instructions"], r["checkable"]))
        self.assertEqual(counts[0], counts[1])


class StderrEncodingTests(unittest.TestCase):
    """The scorer names skipped files on stderr, and report reads stderr back as UTF-8. On a
    Windows code page an unconfigured stderr wrote "caf\xe9.md" in cp1252, and it came back
    as "caf\ufffd.md". PYTHONIOENCODING=cp1252 stands in for that console here."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="kibsu_test_failures_")
        skills = os.path.join(self.tmpdir, ".claude", "skills")
        os.makedirs(skills)
        try:
            with open(os.path.join(skills, "caf\u00e9.md"), "w", encoding="utf-16") as fh:
                fh.write("Never skip the build.\n")
        except (OSError, UnicodeError) as exc:
            self.skipTest("this filesystem cannot hold the name: %s" % exc)
        self.repo = make_repo(self.tmpdir, {".claude/skills/deploy.md": SKILL})

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_a_non_ascii_file_name_survives_a_non_utf8_console(self):
        env = dict(os.environ, PYTHONIOENCODING="cp1252")
        p = subprocess.run([sys.executable, "-m", "kibsu", "report", self.repo, "--json"],
                           cwd=PACKAGE_ROOT, env=env, capture_output=True)
        unread = json.loads(p.stdout.decode("utf-8"))["unread_files"]
        names = [unicodedata.normalize("NFC", u.split(" (")[0]) for u in unread]
        self.assertEqual(names, [".claude/skills/caf\u00e9.md"], unread)


@unittest.skipUnless(hasattr(os, "symlink"), "no symlinks on this platform")
class SkipReasonTests(unittest.TestCase):
    """Every way the scorer leaves a file out is named, in one shape, relative to the repo."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="kibsu_test_failures_")
        self.outside = tempfile.mkdtemp(prefix="kibsu_test_outside_")
        self.repo = make_repo(self.tmpdir, {".claude/skills/deploy.md": SKILL})
        skills = os.path.join(self.repo, ".claude", "skills")
        with open(os.path.join(self.outside, "secret.md"), "w", encoding="utf-8") as fh:
            fh.write("Run `cat secret`.\n")
        try:
            os.symlink(os.path.join(self.outside, "secret.md"), os.path.join(skills, "out.md"))
            os.symlink(os.path.join(skills, "no-such-target.md"), os.path.join(skills, "ghost.md"))
        except (OSError, NotImplementedError) as exc:     # Windows without the privilege
            self.skipTest("cannot create symlinks here: %s" % exc)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        shutil.rmtree(self.outside, ignore_errors=True)

    def test_a_link_out_of_the_repo_and_an_unopenable_file_are_both_named(self):
        _, stdout, _ = run_tool("report", self.repo, "--json")
        unread = json.loads(stdout)["unread_files"]
        self.assertIn(".claude/skills/out.md (resolves outside the repo)", unread)
        self.assertTrue(any(u.startswith(".claude/skills/ghost.md (could not read:")
                            for u in unread), unread)


class ReproductionHintTests(unittest.TestCase):
    """report's read-only hint must re-run the run that failed. A scorer broken only in its
    artifact walk - the git-driven part, the likeliest real crash - succeeds without
    --artifacts, and a hint that succeeds says there was nothing wrong."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="kibsu_test_failures_")
        self.pkg = os.path.join(self.tmpdir, "pkg")
        shutil.copytree(os.path.join(PACKAGE_ROOT, "kibsu"), os.path.join(self.pkg, "kibsu"))
        audit_py = os.path.join(self.pkg, "kibsu", "audit.py")
        with open(audit_py, encoding="utf-8") as fh:
            src = fh.read()
        anchor = "    a = ap.parse_args()\n    global INCLUDE_ARCHIVED"
        self.assertIn(anchor, src, "the sabotage anchor moved - update this test")
        with open(audit_py, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(src.replace(anchor, "    a = ap.parse_args()\n"
                                 "    if a.artifacts:\n"
                                 "        raise RuntimeError('artifact walk exploded')\n"
                                 "    global INCLUDE_ARCHIVED", 1))
        self.repo = make_repo(os.path.join(self.tmpdir, "repo"),
                              {".claude/skills/deploy.md": SKILL})

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_the_hint_reruns_the_failing_run_and_fails_the_same_way(self):
        _, stdout, _ = run_tool("report", self.repo, cwd=self.pkg)
        self.assertIn("artifact walk exploded", stdout)
        hint = next(ln for ln in stdout.splitlines() if "reads only, writes nothing:" in ln)
        self.assertTrue(hint.rstrip().endswith("--json --artifacts"), hint)


class MalformedConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="kibsu_test_failures_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_a_wrongly_typed_key_is_a_warning_not_a_traceback(self):
        repo = make_repo(self.tmpdir, {".claude/skills/deploy.md": SKILL,
                                       ".kibsu.json": '{"skills_dir": 5}\n'})
        for tool in ("report", "explain"):
            exit_code, stdout, stderr = run_tool(tool, repo)
            self.assertNotIn("Traceback", stderr, tool)
            self.assertIn('"skills_dir" must be a string', stderr, tool)
            self.assertIn(exit_code, (0, 3), "%s exited %d: %s" % (tool, exit_code, stderr))
        assert_repo_untouched(repo)


if __name__ == "__main__":
    unittest.main()
