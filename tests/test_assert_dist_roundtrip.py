#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for `tools/assert_dist_roundtrip.py` - the checker that guards the publish path.

`release.yml` fires only on a `v*` tag, so the upload/download pair feeding
`pypa/gh-action-pypi-publish` is the one path in this repository that no pull request can
exercise. `.github/workflows/roundtrip.yml` tests it, and `tools/assert_dist_roundtrip.py` is
the assertion that workflow runs.

The assertion used to live inline in the workflow YAML, in two copies, where `python -m
unittest` could not reach it: a check nobody could check. This module is the other half of
moving it out. Per CONTRIBUTING.md rule 4, every branch below that can fail is DRIVEN to fail
here - the negative cases are the point of the file, not decoration. They are the same six
cases the checker was validated against by hand before it first shipped, plus the branches that
hand-run did not cover.

Fixtures are genuine formats, never stand-ins: `_make_sdist` writes a real gzip tarball and
`_make_wheel` writes a real zip archive. A file merely NAMED `.whl` would pass a naive check
and prove nothing about `download-artifact` v8's "no longer attempt to unzip" behaviour, which
is the whole reason the checker exists.
"""
import contextlib
import io
import os
import re
import shutil
import sys
import tarfile
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import assert_dist_roundtrip as adr


def _make_sdist(path):
    """Write a real gzip tarball at `path` and return its sha256."""
    with tarfile.open(str(path), "w:gz") as tar:
        data = b"Metadata-Version: 2.1\nName: kibsu\nVersion: 0.1.0\n"
        info = tarfile.TarInfo("kibsu-0.1.0/PKG-INFO")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    return adr.sha256(path)


def _make_wheel(path):
    """Write a real zip archive at `path` and return its sha256."""
    with zipfile.ZipFile(str(path), "w") as zf:
        zf.writestr("kibsu/__init__.py", "__version__ = '0.1.0'\n")
        zf.writestr("kibsu-0.1.0.dist-info/METADATA",
                    "Metadata-Version: 2.1\nName: kibsu\nVersion: 0.1.0\n")
    return adr.sha256(path)


class AssertDistRoundtripTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.dist = os.path.join(self.tmpdir, "dist")
        os.makedirs(self.dist)
        self.sdist = os.path.join(self.dist, "kibsu-0.1.0.tar.gz")
        self.wheel = os.path.join(self.dist, "kibsu-0.1.0-py3-none-any.whl")
        self.sha_sdist = _make_sdist(self.sdist)
        self.sha_wheel = _make_wheel(self.wheel)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _check(self):
        return adr.check(self.dist, self.sha_sdist, self.sha_wheel)

    # ---- the contract holds ------------------------------------------------

    def test_intact_dist_passes(self):
        self.assertEqual([], self._check())

    def test_digests_are_optional_shape_still_checked(self):
        """Omitting the expected digests skips the hash comparison, not the rest."""
        self.assertEqual([], adr.check(self.dist))
        os.remove(self.wheel)
        self.assertTrue(adr.check(self.dist))

    # ---- negative controls: each of these MUST fail ------------------------

    def test_wrapped_in_a_single_zip_fails(self):
        """The exact failure this checker exists to catch: files arrive archived."""
        wrapped = os.path.join(self.tmpdir, "wrapped")
        os.makedirs(wrapped)
        with zipfile.ZipFile(os.path.join(wrapped, "dist.zip"), "w") as zf:
            zf.write(self.sdist, os.path.basename(self.sdist))
            zf.write(self.wheel, os.path.basename(self.wheel))
        failures = adr.check(wrapped, self.sha_sdist, self.sha_wheel)
        self.assertTrue(any("arrived archived" in f for f in failures), failures)

    def test_flipped_byte_in_wheel_fails_on_hash(self):
        with open(self.wheel, "r+b") as handle:
            handle.seek(-1, os.SEEK_END)
            last = handle.read(1)
            handle.seek(-1, os.SEEK_END)
            handle.write(bytes([last[0] ^ 0xFF]))
        failures = self._check()
        self.assertTrue(any("sha256 changed" in f for f in failures), failures)

    def test_wheel_that_is_not_a_zip_fails(self):
        """A file named .whl is not a wheel. This is the branch fixtures would have hidden."""
        with open(self.wheel, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("not really a wheel")
        failures = self._check()
        self.assertTrue(any("not a valid zip" in f for f in failures), failures)

    def test_sdist_that_is_not_a_tar_fails(self):
        with open(self.sdist, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("not really a tarball")
        failures = self._check()
        self.assertTrue(any("not a valid tar" in f for f in failures), failures)

    def test_empty_file_fails(self):
        open(self.wheel, "wb").close()
        failures = self._check()
        self.assertTrue(any("is empty" in f for f in failures), failures)

    def test_directory_instead_of_file_fails(self):
        os.remove(self.wheel)
        os.makedirs(self.wheel)
        failures = self._check()
        self.assertTrue(any("not a plain file" in f for f in failures), failures)

    def test_extra_entry_fails(self):
        with open(os.path.join(self.dist, "stray.txt"), "w", encoding="utf-8") as handle:
            handle.write("unexpected")
        failures = self._check()
        self.assertTrue(any("expected exactly 2 entries" in f for f in failures), failures)

    def test_empty_directory_fails(self):
        os.remove(self.sdist)
        os.remove(self.wheel)
        failures = self._check()
        self.assertTrue(any("expected exactly 2 entries" in f for f in failures), failures)

    def test_missing_directory_fails(self):
        failures = adr.check(os.path.join(self.tmpdir, "nope"))
        self.assertEqual(1, len(failures))
        self.assertIn("does not exist", failures[0])

    def test_every_failure_is_reported_not_just_the_first(self):
        """The reviewer gets the whole shape of the breakage in one log."""
        os.remove(self.sdist)
        with open(self.wheel, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("not really a wheel")
        self.assertGreater(len(self._check()), 1)

    # ---- the CLI wrapper, exit codes included ------------------------------
    #
    # main() prints; these helpers capture it rather than letting it litter the suite's
    # output, and then assert on what was printed - a checker that exits 1 while printing
    # nothing useful would still be a bad checker.

    def _run_main(self, argv, env):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = adr.main(argv, env)
        return code, buffer.getvalue()

    def test_main_returns_zero_and_says_pass_when_contract_holds(self):
        env = {"EXPECT_SDIST": self.sha_sdist, "EXPECT_WHEEL": self.sha_wheel}
        code, output = self._run_main([self.dist], env)
        self.assertEqual(0, code)
        self.assertIn("PASS", output)

    def test_main_returns_one_and_names_the_failure(self):
        os.remove(self.wheel)
        env = {"EXPECT_SDIST": self.sha_sdist, "EXPECT_WHEEL": self.sha_wheel}
        code, output = self._run_main([self.dist], env)
        self.assertEqual(1, code)
        self.assertIn("ASSERTION FAILED", output)
        self.assertIn("*.whl", output)

    def test_main_returns_two_on_wrong_usage(self):
        self.assertEqual(2, self._run_main([], {})[0])
        self.assertEqual(2, self._run_main([self.dist, "extra"], {})[0])

    def test_main_tolerates_absent_expected_digests(self):
        """The workflow always supplies them; a human running it by hand may not."""
        self.assertEqual(0, self._run_main([self.dist], {})[0])


class MustMatchInvariantTests(unittest.TestCase):
    """The MUST-MATCH rule between release.yml and roundtrip.yml, enforced instead of asserted.

    Both workflows carry a comment saying their upload-artifact and download-artifact pins must
    be identical - that is what makes the roundtrip checker actually guard the publish path.
    A rule that lives only in a comment is a rule Dependabot cannot read and a reviewer can
    miss, which is the precise failure mode this repository exists to report. So it is checked
    here, by machine, on every test run.

    Regex rather than a YAML parser on purpose: the test suite imports nothing outside the
    standard library (CONTRIBUTING.md, rule 2), and matching a pinned `uses:` line needs no
    more than that.
    """

    WORKFLOWS = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".github", "workflows")

    def _pins(self, filename, action):
        path = os.path.join(self.WORKFLOWS, filename)
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        return re.findall(r"uses:\s*actions/%s@([0-9a-f]{40})" % re.escape(action), text)

    def test_upload_artifact_pins_match(self):
        release = self._pins("release.yml", "upload-artifact")
        roundtrip = self._pins("roundtrip.yml", "upload-artifact")
        self.assertEqual(1, len(release), "release.yml should pin upload-artifact exactly once")
        self.assertEqual(1, len(roundtrip), "roundtrip.yml should pin upload-artifact exactly once")
        self.assertEqual(
            release[0], roundtrip[0],
            "release.yml and roundtrip.yml pin different upload-artifact SHAs - the roundtrip "
            "checker is no longer testing the versions the publish path actually uses")

    def test_download_artifact_pins_match(self):
        release = self._pins("release.yml", "download-artifact")
        roundtrip = self._pins("roundtrip.yml", "download-artifact")
        # Two jobs legitimately download the dist artifact (publish and github-release).
        # The invariant was never the count - it is that every download in the publish
        # path runs the SAME pinned version the roundtrip checker actually tests.
        self.assertGreaterEqual(
            len(release), 1, "release.yml should pin download-artifact at least once")
        self.assertEqual(1, len(roundtrip), "roundtrip.yml should pin download-artifact exactly once")
        self.assertEqual(
            1, len(set(release)),
            "release.yml pins download-artifact at more than one SHA - the roundtrip checker "
            "cannot be testing all of them")
        self.assertEqual(
            release[0], roundtrip[0],
            "release.yml and roundtrip.yml pin different download-artifact SHAs - the roundtrip "
            "checker is no longer testing the versions the publish path actually uses")

    def test_no_floating_action_refs_anywhere(self):
        """Every `uses:` in every workflow is a 40-hex SHA. Scorecard's Pinned-Dependencies,
        enforced locally so it is caught before a reviewer or a rating service has to."""
        floating = []
        for name in sorted(os.listdir(self.WORKFLOWS)):
            if not name.endswith((".yml", ".yaml")):
                continue
            with open(os.path.join(self.WORKFLOWS, name), encoding="utf-8") as handle:
                for line in handle:
                    if re.search(r"^\s*-?\s*uses:", line) and not re.search(r"@[0-9a-f]{40}\b", line):
                        floating.append("%s: %s" % (name, line.strip()))
        self.assertEqual([], floating, "unpinned action references found")


if __name__ == "__main__":
    unittest.main()
