#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared test helpers for kibsu's test suite.

Stdlib `unittest` only - no pytest, no third-party dependency of any kind. A test suite that
needed `pip install` to prove a dependency-free tool works would contradict the thing it is
testing.

Three helpers:

  make_repo(tmpdir, files)      write {relpath: content} under tmpdir, git-init it, commit
                                 everything with an inline identity (never touches global git
                                 config), return tmpdir.

  run_tool(subcommand, *args)   invoke `python -m kibsu <subcommand> <args...>` as a subprocess,
                                 cwd fixed to the kibsu package root so it runs straight from a
                                 clone with nothing installed. Returns (exit_code, stdout, stderr).

  assert_repo_untouched(path)   assert `git status --porcelain` is empty. This is the read-only
                                 tools' central claim, and it must be enforced by every test that
                                 exercises one of them - not assumed.

Every test module is expected to use tempfile.mkdtemp() for its fixtures and clean up in
tearDown(); nothing here is ever written under the kibsu working tree itself.
"""
import os
import subprocess
import sys

# The directory that contains the `kibsu` package (and this repo's pyproject.toml) - i.e. the
# directory `python -m kibsu` must be run from for a bare clone with nothing installed.
PACKAGE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _git(cwd, *args):
    """Run git in `cwd` and return stdout. Raises with the full stderr on failure.

    Never touches global or user git config - callers that need an identity pass it inline via
    `-c user.email=... -c user.name=...` on the specific command that needs it (commit).
    """
    result = subprocess.run(
        ["git"] + list(args),
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(
            "git %s (cwd=%s) failed with rc=%d:\n%s"
            % (" ".join(args), cwd, result.returncode, result.stderr)
        )
    return result.stdout


def make_repo(tmpdir, files):
    """Create fixture files under `tmpdir`, git-init it, and commit everything.

    `files` is {relpath: content}. Directories are created as needed. The identity used for the
    commit is passed inline on that one command (`-c user.email=... -c user.name=...`) - this
    never reads or writes the machine's global git config, per the project's hard rule against
    touching anything outside the fixture itself.

    core.autocrlf is turned off in the fixture repo's own (local, not global) config so the
    bytes kibsu reads back are exactly the bytes this function wrote, regardless of whatever the
    host machine's global autocrlf setting happens to be - line-ending churn on `git add` would
    otherwise make content hashes (ns_index's sha256_16) and byte-for-byte determinism
    comparisons depend on machine configuration instead of on the tool.

    Returns `tmpdir`, so call sites can write `repo = make_repo(tmpdir, {...})`.
    """
    for relpath, content in files.items():
        full = os.path.join(tmpdir, relpath.replace("/", os.sep))
        parent = os.path.dirname(full)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent)
        with open(full, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)

    _git(tmpdir, "init", "-q")
    _git(tmpdir, "config", "core.autocrlf", "false")
    _git(
        tmpdir,
        "-c", "user.email=kibsu-tests@example.com",
        "-c", "user.name=Kibsu Tests",
        "add", "-A",
    )
    _git(
        tmpdir,
        "-c", "user.email=kibsu-tests@example.com",
        "-c", "user.name=Kibsu Tests",
        "commit", "-q", "-m", "initial fixture commit",
    )
    return tmpdir


def run_tool(subcommand, *args, **kwargs):
    """Invoke `python -m kibsu <subcommand> <args...>` as a subprocess and return
    (exit_code, stdout, stderr).

    Runs with cwd=PACKAGE_ROOT by default (override with the `cwd=` keyword) precisely so the
    tool needs no installation - this is the exact command a user runs from a bare clone.
    Pass `input_text=` for the tools that read a JSON event on stdin (tokens --guard/--ledger).
    """
    cwd = kwargs.pop("cwd", None) or PACKAGE_ROOT
    input_text = kwargs.pop("input_text", None)
    if kwargs:
        raise TypeError("unexpected keyword arguments: %r" % (sorted(kwargs),))

    cmd = [sys.executable, "-m", "kibsu", subcommand] + list(args)
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        input=input_text,
    )
    return result.returncode, result.stdout, result.stderr


def run_git(cwd, *args):
    """Run git in `cwd` and return (returncode, stdout, stderr) WITHOUT raising.

    `_git` (above) is for fixture setup, where any git failure is a test-infrastructure bug and
    raising is correct. Tests for `install` and `gate` need the opposite: they deliberately run
    commits that are EXPECTED to fail (blocked by a hook) and must inspect the exit code and
    output, not treat non-zero as an error.
    """
    result = subprocess.run(
        ["git"] + list(args),
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.returncode, result.stdout, result.stderr


def assert_vendored_copy_matches_source(repo, *tool_names, source_root=None):
    """Assert that each of `tool_names` (e.g. "gate.py", "config.py") vendored under
    `repo/.kibsu/bin/` is byte-identical to the module of the same name under `source_root`
    (defaults to this checkout's own `kibsu/` package directory).

    This is what the `install`/`gate` hook tests actually need proved, and it replaces an earlier
    helper - assert_kibsu_not_importable() - that asserted `import kibsu` fails in a subprocess
    run from the fixture repo. That was only ever a PROXY, and a broken one: it is FALSE the
    moment kibsu is pip-installed anywhere on the machine (the maintainer's own machine, any
    dogfooding contributor's - not hypothetical, it is why this function exists now), at which
    point every hook test that called it failed for a reason that had nothing to do with the hook
    being wrong.

    The real property was never about importability at all. gate.py's and install.py's HOOK
    templates never run `python -m kibsu` - they exec a HARD-CODED path,
    "$root/{bin}/gate.py" / "$root/{bin}/check.py", vendored into the repo at install time (see
    gate.py's own HOOK comment and install.py's "PORTABLE AS OF v1.1.0" note). Python always runs
    exactly the file it is given by path; there is no ambiguity about "which copy ran" once that
    file's identity is pinned down. So the property worth asserting is that the file at that
    hard-coded path really is this checkout's vendored snapshot - not a stale copy from a prior
    install.py version, not a hand-edited stand-in, not simply absent - and that is checkable
    directly, by content, regardless of what else happens to be importable on this machine.

    Raises AssertionError, naming the file that failed, if a vendored copy is missing or its
    bytes diverge from source_root's copy of the same name. A guard that cannot fail proves
    nothing (see tests/test_support_helpers.py, which exercises exactly that: this function must
    fail on a tampered or absent vendored copy, not just pass on a good one).
    """
    source_root = source_root or os.path.join(PACKAGE_ROOT, "kibsu")
    for name in tool_names:
        vendored = os.path.join(repo, ".kibsu", "bin", name)
        source = os.path.join(source_root, name)
        assert os.path.isfile(vendored), (
            "expected a vendored copy of %r at %r - these hook tests only prove anything about "
            "the installed hook if it has a real vendored file at that path to exec"
            % (name, vendored)
        )
        assert os.path.isfile(source), (
            "no source module %r to compare the vendored copy against" % (source,)
        )
        with open(vendored, "rb") as fh:
            vendored_bytes = fh.read()
        with open(source, "rb") as fh:
            source_bytes = fh.read()
        assert vendored_bytes == source_bytes, (
            "%r does not match %r byte-for-byte - the installed hook would exec a stale or "
            "tampered copy, not the vendored snapshot this test assumes" % (vendored, source)
        )


def assert_repo_untouched(path):
    """Assert `git status --porcelain` is empty for the repo at `path`.

    This is the read-only tools' central claim ("nothing was written to this repo"), and every
    test exercising one of them must call this - the claim is enforced by the test suite, not
    taken on faith.
    """
    out = _git(path, "status", "--porcelain")
    assert out.strip() == "", (
        "expected %s to be untouched by a read-only tool, but `git status --porcelain` "
        "reported:\n%s" % (path, out)
    )
