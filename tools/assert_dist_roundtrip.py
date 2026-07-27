#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Assert that a built `dist/` survived a GitHub Actions artifact round trip intact.

`release.yml` builds distributions in one job, uploads them, downloads them in another job,
and hands the result to `pypa/gh-action-pypi-publish`. That workflow fires only on a `v*` tag,
so no pull request has ever exercised it: a bump to `upload-artifact` or `download-artifact`
lands with green CI and is first tested by an actual release. `.github/workflows/roundtrip.yml`
closes that gap, and this module is the assertion it runs.

WHAT THE CONTRACT ACTUALLY IS - what `gh-action-pypi-publish` needs to find:

  - exactly two entries in the directory,
  - both PLAIN FILES, not directories and not an archive wrapping them,
  - one `*.tar.gz` and one `*.whl`, both non-empty,
  - byte-identical to what was uploaded (sha256, when the expected digests are supplied),
  - and still structurally valid: the sdist a readable tar, the wheel a readable zip.

THE WHEEL IS A ZIP, and that is the load-bearing detail rather than trivia. The headline change
in `download-artifact` v8 is that it "will no longer attempt to unzip all downloaded files", so
a fixture file merely NAMED `.whl` would pass a naive check and prove nothing about the actual
behaviour under test. The workflow therefore builds real distributions with `python -m build`,
and this module verifies the wheel is still a valid zip after the trip.

WHY THIS IS A FILE AND NOT A HEREDOC. It previously lived inline inside the workflow YAML, in
two copies. That made it the one checker in this repository that `python -m unittest` could not
reach - a check nobody could check, which is the exact defect class this project reports in
other people's repositories. `tests/test_assert_dist_roundtrip.py` now drives every branch
below, including the failing ones. Per CONTRIBUTING.md rule 4, a checker that has never failed
proves nothing; these failures are exercised on every test run.

Standard library only, and 3.8-compatible, because the test suite that imports it runs on the
floor declared in `pyproject.toml`.

USAGE
    python tools/assert_dist_roundtrip.py <dist-dir>

    Reads the expected digests from the environment when present:
        EXPECT_SDIST   sha256 of the sdist as it was uploaded
        EXPECT_WHEEL   sha256 of the wheel as it was uploaded
    Omit either to skip that comparison (shape and format are still checked).

EXIT CODES
    0  the contract holds
    1  at least one assertion failed; every failure is printed, not just the first
"""
import hashlib
import os
import pathlib
import sys
import tarfile
import zipfile


def sha256(path):
    """Hex sha256 of a file, read in chunks so a large sdist is never held in memory."""
    digest = hashlib.sha256()
    with open(str(path), "rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def check(dist_dir, expect_sdist=None, expect_wheel=None):
    """Return a list of failure strings. An empty list means the contract holds.

    Returning every failure instead of raising on the first one is deliberate: when this goes
    red on a Dependabot pull request, the reviewer wants the whole shape of the breakage in one
    log, not one symptom at a time across three re-runs.
    """
    failures = []
    directory = pathlib.Path(dist_dir)

    if not directory.is_dir():
        return ["%s does not exist or is not a directory" % directory]

    entries = sorted(directory.iterdir())
    if len(entries) != 2:
        failures.append("expected exactly 2 entries, found %d: %s"
                        % (len(entries), [e.name for e in entries]))

    for entry in entries:
        if not entry.is_file():
            failures.append("%s is not a plain file" % entry.name)
        if entry.name.endswith(".zip"):
            failures.append("%s is a .zip - the artifact arrived archived, not extracted"
                            % entry.name)

    sdists = [e for e in entries if e.name.endswith(".tar.gz")]
    wheels = [e for e in entries if e.name.endswith(".whl")]
    if len(sdists) != 1:
        failures.append("expected exactly one *.tar.gz, found %d" % len(sdists))
    if len(wheels) != 1:
        failures.append("expected exactly one *.whl, found %d" % len(wheels))

    if sdists:
        sdist = sdists[0]
        if sdist.is_file():
            if sdist.stat().st_size == 0:
                failures.append("%s is empty" % sdist.name)
            if not tarfile.is_tarfile(str(sdist)):
                failures.append("%s is not a valid tar archive after the round trip"
                                % sdist.name)
            if expect_sdist:
                got = sha256(sdist)
                if got != expect_sdist:
                    failures.append("%s sha256 changed: %s -> %s"
                                    % (sdist.name, expect_sdist, got))

    if wheels:
        wheel = wheels[0]
        if wheel.is_file():
            if wheel.stat().st_size == 0:
                failures.append("%s is empty" % wheel.name)
            # A wheel IS a zip. This is precisely the property that download-artifact v8's
            # "no longer attempt to unzip all downloaded files" change could plausibly break,
            # and the reason a fabricated fixture would not do.
            if not zipfile.is_zipfile(str(wheel)):
                failures.append("%s is not a valid zip after the round trip" % wheel.name)
            if expect_wheel:
                got = sha256(wheel)
                if got != expect_wheel:
                    failures.append("%s sha256 changed: %s -> %s"
                                    % (wheel.name, expect_wheel, got))

    return failures


def main(argv=None, env=None):
    """CLI entry point. Returns an exit code rather than calling sys.exit, so tests can drive it."""
    argv = list(sys.argv[1:] if argv is None else argv)
    env = os.environ if env is None else env

    if len(argv) != 1:
        print("usage: assert_dist_roundtrip.py <dist-dir>")
        return 2

    target = argv[0]
    failures = check(target, env.get("EXPECT_SDIST"), env.get("EXPECT_WHEEL"))

    directory = pathlib.Path(target)
    if directory.is_dir():
        print("contents of %s: %s" % (target, [e.name for e in sorted(directory.iterdir())]))

    if failures:
        print("ASSERTION FAILED:")
        for failure in failures:
            print("  - %s" % failure)
        return 1

    print("PASS: two plain distributions, byte-identical, formats intact")
    return 0


if __name__ == "__main__":
    sys.exit(main())
