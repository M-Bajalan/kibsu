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


# Files the sdist must carry for the documented "clone and run" promise to hold when the clone
# is the tarball. tests/support.py is imported by 18 of 21 test modules; tools/ holds the
# checkers the pre-PR checklist tells a contributor to run. The live 0.7.0 sdist shipped
# without any of them - setuptools' legacy finder takes only tests/test*.py - and
# `python -m unittest discover -s tests` inside it produced 18 ModuleNotFoundErrors. Found by
# the pre-release adversarial pass; the wheel was never affected. MANIFEST.in (#90) states the
# contents; these checks make sure the statement stays true.
SDIST_REQUIRED = (
    "tests/support.py",
    "tests/__init__.py",
    "tools/refresh_readme_counts.py",
    "tools/assert_dist_roundtrip.py",
)


def sdist_members(sdist):
    """Member paths inside the sdist with the leading `<name>-<version>/` directory stripped."""
    with tarfile.open(str(sdist)) as tf:
        out = set()
        for m in tf.getnames():
            parts = m.split("/", 1)
            out.add(parts[1] if len(parts) == 2 else parts[0])
        return out


def check_sdist_contents(sdist):
    """Return failure strings for every required file the sdist does not carry."""
    if not tarfile.is_tarfile(str(sdist)):
        return ["%s is not a tar archive; cannot check its contents" % pathlib.Path(sdist).name]
    have = sdist_members(sdist)
    return ["sdist is missing %s - its own test suite cannot run from source" % need
            for need in SDIST_REQUIRED if need not in have]


def check_sdist_suite(sdist):
    """Extract the sdist and run its test suite exactly as CONTRIBUTING tells a reader to.

    This is the check that would have caught the 0.7.0 sdist: a tarball that is a valid
    archive, byte-identical across the round trip, and still cannot pass its own tests. It
    takes as long as the suite does, so it sits behind its own flag and CI runs it on the real
    built artifact; the unit tests cover check_sdist_contents() with fixture tarballs and are
    deliberately not asked to run a suite inside a fake one - that is disclosed here rather
    than hidden behind a test that could not fail.
    """
    import shutil
    import subprocess
    import tempfile
    tmp = tempfile.mkdtemp(prefix="kibsu_sdist_suite_")
    try:
        with tarfile.open(str(sdist)) as tf:
            tf.extractall(tmp)
        roots = [d for d in pathlib.Path(tmp).iterdir() if d.is_dir()]
        if len(roots) != 1:
            return ["sdist did not extract to exactly one top-level directory: %s"
                    % [r.name for r in roots]]
        proc = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                              cwd=str(roots[0]), capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        if proc.returncode != 0:
            tail = "\n".join((proc.stderr or proc.stdout).splitlines()[-12:])
            return ["the sdist's own test suite FAILED (exit %d):\n%s" % (proc.returncode, tail)]
        return []
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None, env=None):
    """CLI entry point. Returns an exit code rather than calling sys.exit, so tests can drive it."""
    argv = list(sys.argv[1:] if argv is None else argv)
    env = os.environ if env is None else env

    # Two opt-in flags, stripped before the positional check so the usage contract stays the
    # same one-argument shape it has always had. Opt-in, because the unit tests drive check()
    # against deliberately fake fixture tarballs that must never trigger a suite run.
    want_contents = "--sdist-contents" in argv
    want_suite = "--sdist-suite" in argv
    argv = [a for a in argv if a not in ("--sdist-contents", "--sdist-suite")]

    if len(argv) != 1:
        print("usage: assert_dist_roundtrip.py <dist-dir> [--sdist-contents] [--sdist-suite]")
        return 2

    target = argv[0]
    failures = check(target, env.get("EXPECT_SDIST"), env.get("EXPECT_WHEEL"))

    if want_contents or want_suite:
        sdists = sorted(pathlib.Path(target).glob("*.tar.gz")) if pathlib.Path(target).is_dir() else []
        if len(sdists) != 1:
            failures.append("cannot check sdist contents: expected one *.tar.gz, found %d" % len(sdists))
        else:
            if want_contents:
                failures += check_sdist_contents(sdists[0])
            if want_suite and not failures:
                failures += check_sdist_suite(sdists[0])

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
