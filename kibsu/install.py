#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ns_install.py  v1.1.0  -  wires kibsu's check to `git commit`.

Wires ns_check to `git commit`, and makes that wiring reversible in one command.

WHY A HOOK AND NOT A README LINE
  This repo already writes "before commit -> run the checker, don't commit red" in CLAUDE.md,
  already ships the checker, and `git config core.hooksPath` is empty. 29 of the last 61
  documentation commits went in red anyway. The instruction is not the mechanism.

WHY core.hooksPath AND NOT .git/hooks/pre-commit
  `.git/hooks/` is not version-controlled and not visible in a diff. `core.hooksPath` points at
  a directory inside the repo, so the hook is reviewable, and the whole install is one config
  key plus one directory - which is also why it uninstalls cleanly.

  Cost, stated plainly: core.hooksPath REPLACES the default hooks directory. Any existing hook
  in .git/hooks is copied into the new directory at install time and its SHA recorded; a
  pre-existing pre-commit - the one name this installer also writes - is carried as
  `pre-commit.carried` and the generated hook execs it FIRST, so its logic keeps firing and
  its failure keeps blocking, exactly as before (issue #33: it used to be excluded from the
  carry list outright, which silently disabled it while this paragraph promised otherwise).
  Nothing is left behind and nothing is silently disabled - now checkably.

FAIL-SAFE, NOT FAIL-SHUT
  ns_check exit 1 (violations) blocks the commit.
  ns_check exit 3 (cannot run - no index, no git, no python) WARNS LOUDLY AND ALLOWS.
  A checker that cannot run must not become a checker that stops all work; that is how hooks get
  deleted at 2am. The distinction is why ns_check has four exit codes instead of two.

  `git commit --no-verify` bypasses it, as it does every hook. That is git's design, not a hole.

PORTABLE AS OF v1.1.0 - TOOLS ARE VENDORED
  v1.0.0 generated a hook containing ABSOLUTE paths to ns_check.py / ns_index.py on the
  installing machine, so anyone else's clone got a hook pointing at a path that did not exist.
  Now the tools are COPIED into `.kibsu/bin/` at install time and the hook resolves them from
  `git rev-parse --show-toplevel`. Nothing in the generated hook refers to the machine that
  installed it. If `.kibsu/bin/ns_check.py` is missing the hook says so and ALLOWS the commit -
  a missing checker must never masquerade as a passing one.

WHAT UNINSTALL DOES NOT DELETE
  `.kibsu/index.json` and `.kibsu/baseline.json` are YOUR data - an index you built and decisions
  you recorded. Uninstall removes only what it installed (the hook, install.json, the config key)
  and says what it kept. `--purge` removes those too.

EXIT CODES
  0  --status always (a read-only report, nothing to fail on); --install/--uninstall on
     success, including --dry-run (which reports what WOULD happen and changes nothing).
  3  REFUSED - the tool declined to act because doing so would not be safe or reversible:
       --install    not a git repository · already installed (.kibsu/install.json exists) and
                    --force not given · core.hooksPath already points elsewhere and --force not
                    given · check.py not found next to this script.
       --uninstall  .kibsu/install.json not found - nothing to uninstall.
     No other exit code is used intentionally.

  python -m kibsu install [repo] --install|--uninstall|--status [--dry-run] [--force] [--purge]
"""
import argparse
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import stat

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

VERSION = "1.1.0"
NS_DIR = ".kibsu"
HOOKS_DIR = os.path.join(NS_DIR, "hooks")
INSTALL_JSON = os.path.join(NS_DIR, "install.json")

HOOK = """#!/bin/sh
# kibsu - pre-commit  (installed by install.py v{v})
# Reversible:  python "$(git rev-parse --show-toplevel)/.kibsu/bin/install.py" . --uninstall
# Bypass once: git commit --no-verify
# Tools are vendored into .kibsu/bin at install time and resolved from the repo root, so this
# hook works in anyone's clone. Nothing here points at the machine that installed it.
ROOT="$(git rev-parse --show-toplevel)"
NS_TOOL="$ROOT/.kibsu/bin/check.py"

# A pre-commit that existed BEFORE this install is carried, not silently disabled: it runs
# first, and its failure blocks, exactly as it did before kibsu arrived (issue #33). Exec'd
# directly so its own shebang decides the interpreter - the same way git itself ran it.
CARRIED="$ROOT/{hooks}/pre-commit.carried"
if [ -f "$CARRIED" ]; then
  "$CARRIED" "$@"
  crc=$?
  if [ $crc -ne 0 ]; then
    echo "  commit blocked by the carried pre-existing pre-commit hook (exit $crc)."
    echo "  It lives at {hooks}/pre-commit.carried - it predates kibsu and still applies."
    exit $crc
  fi
fi

# Windows ships a "python"/"python3" App Execution Alias stub even on a machine with NO real
# interpreter installed: `command -v` finds it happily, but running it only prints a Microsoft
# Store nag to stderr and exits 49 - and rc=49 used to match neither of this hook's two handled
# cases (1 or 3) below, falling through the whole if-chain to a silent, unannounced `exit 0`:
# ALLOWED, nothing checked, nobody told. So presence is no longer trusted: each candidate is
# actually invoked and kept only if it behaves like a real interpreter. "py -3" is two words, so
# candidates are tried as validated command strings via a small sh function rather than an array
# - POSIX sh (which is what git runs this under, on all three OSes) has none.
try_py() {{
  command -v "$1" >/dev/null 2>&1 || return 1
  "$@" -c "import sys" >/dev/null 2>&1
}}
PY=
if try_py python3; then PY="python3"
elif try_py python; then PY="python"
elif try_py py -3; then PY="py -3"
fi
if [ -z "$PY" ]; then
  echo "  !! kibsu install: no working python found - commit ALLOWED, nothing was verified; this is not a pass."
  exit 0
fi

if [ ! -f "$NS_TOOL" ]; then
  echo "  !! check.py missing from .kibsu/bin - commit ALLOWED, nothing verified."
  echo "     Reinstall or uninstall; do not treat this as a pass."
  exit 0
fi
$PY "$NS_TOOL" "$ROOT" --staged --index "{index}" {baseline}
rc=$?
if [ $rc -eq 1 ]; then
  echo ""
  echo "  commit blocked by ns_check. Regenerate the index, then re-stage:"
  echo "    $PY \\"$ROOT/.kibsu/bin/index.py\\" \\"$ROOT\\" -o \\"{index}\\""
  echo "  Bypass once (recorded in the reflog):  git commit --no-verify"
  exit 1
fi
if [ $rc -eq 3 ]; then
  echo ""
  echo "  !! ns_check COULD NOT RUN (exit 3). Commit ALLOWED, but nothing was verified."
  echo "     This is not a pass. Fix the checker or uninstall it."
fi
if [ $rc -ne 0 ] && [ $rc -ne 1 ] && [ $rc -ne 3 ]; then
  echo ""
  echo "  !! kibsu install: ns_check exited $rc (neither 0, 1, nor 3). Commit ALLOWED, but"
  echo "     nothing was verified - this is not a pass. Fix the checker or uninstall it."
fi
exit 0
"""


def run(args, cwd, check=False):
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if check and p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout or "failed").strip())
    return p


def sha16(path):
    try:
        return hashlib.sha256(io.open(path, "rb").read()).hexdigest()[:16]
    except Exception:
        return None


def git_dir(root):
    p = run(["git", "rev-parse", "--git-dir"], root)
    if p.returncode != 0:
        return None
    d = p.stdout.strip()
    return d if os.path.isabs(d) else os.path.join(root, d)


def current_hookspath(root):
    p = run(["git", "config", "--get", "core.hooksPath"], root)
    return p.stdout.strip() if p.returncode == 0 and p.stdout.strip() else None


def status(root):
    gd = git_dir(root)
    rec = None
    ij = os.path.join(root, INSTALL_JSON)
    if os.path.isfile(ij):
        try:
            rec = json.load(io.open(ij, encoding="utf-8"))
        except Exception:
            rec = {"_error": "install.json unreadable"}
    hp = current_hookspath(root)
    print("ns_install v%s   %s" % (VERSION, root))
    print("  git dir            %s" % (gd or "NOT A GIT REPO"))
    print("  core.hooksPath     %s" % (hp or "(unset - default .git/hooks)"))
    print("  .kibsu/install.json   %s" % ("present" if rec else "absent"))
    if rec:
        print("    installed        %s by %s" % (rec.get("installed_at", "?"), rec.get("by", "?")))
        print("    previous hooks   %s" % (rec.get("previous_hookspath") or "(was unset)"))
        print("    files written    %s" % ", ".join(rec.get("files_written", [])) or "(none)")
        print("    carried hooks    %s" % (", ".join(rec.get("carried_hooks", [])) or "(none)"))
    default_hooks = os.path.join(gd, "hooks") if gd else None
    if default_hooks and os.path.isdir(default_hooks):
        live = [f for f in sorted(os.listdir(default_hooks)) if not f.endswith(".sample")]
        print("  .git/hooks (live)  %s" % (", ".join(live) or "(only .sample files)"))
    return 0


def _is_our_hookspath(value):
    """Is this core.hooksPath value pointing at the directory this installer writes?

    Compared on both separators: git stores whatever string it was given, and HOOKS_DIR is
    built with os.path.join, so the same directory reads as ".kibsu\\hooks" on Windows and
    ".kibsu/hooks" everywhere else - and either spelling can already be on disk from an
    install done on the other platform.
    """
    if not value:
        return False
    norm = value.replace("\\", "/").rstrip("/")
    return norm == HOOKS_DIR.replace("\\", "/").rstrip("/")


def _read_install_json(root):
    """The existing install record, or None when there isn't one we can read."""
    p = os.path.join(root, INSTALL_JSON)
    if not os.path.isfile(p):
        return None
    try:
        with io.open(p, encoding="utf-8") as fh:
            rec = json.load(fh)
        return rec if isinstance(rec, dict) else None
    except Exception:
        # A record we cannot parse tells us nothing about what preceded kibsu. Returning None
        # leaves previous_hookspath unset, which uninstall treats as "unset core.hooksPath" -
        # the safe end state, and never a claim that our own directory came first.
        return None


def install(root, dry, force, index_rel, baseline_rel):
    gd = git_dir(root)
    if not gd:
        print("  REFUSED: not a git repository.")
        return 3
    ij = os.path.join(root, INSTALL_JSON)
    if os.path.isfile(ij) and not force:
        print("  REFUSED: already installed (%s). Use --uninstall first, or --force." % INSTALL_JSON)
        return 3
    prev = current_hookspath(root)
    # A re-install over an ALREADY-installed kibsu must not record kibsu's own hooks dir as the
    # thing to restore. current_hookspath() answers "what is set right now", which after a first
    # install is `.kibsu/hooks` - so a second `--install --force` overwrote previous_hookspath
    # with our own path, and `--uninstall` then "restored" core.hooksPath to a directory whose
    # hook it had just deleted: the user's real setting gone, and NO hooks running at all.
    #
    # The prior record is the authority for what predates kibsu, but only when the current value
    # is in fact ours. If the user pointed core.hooksPath somewhere else since the last install,
    # that IS a genuine previous value and is recorded as one.
    if prev and _is_our_hookspath(prev):
        old_rec = _read_install_json(root)
        prev = old_rec.get("previous_hookspath") if old_rec else None
    if prev and not force:
        print("  REFUSED: core.hooksPath is already set to '%s'." % prev)
        print("  Overwriting it would silently disable those hooks. Re-run with --force to")
        print("  take it over (the previous value is recorded and restored on uninstall).")
        return 3

    here = os.path.dirname(os.path.abspath(__file__))
    checker = os.path.join(here, "check.py")
    if not os.path.isfile(checker):
        print("  REFUSED: check.py not found next to this script.")
        return 3

    hooks_abs = os.path.join(root, HOOKS_DIR)
    hook_path = os.path.join(hooks_abs, "pre-commit")
    default_hooks = os.path.join(gd, "hooks")
    carry = []
    carried_precommit = False
    if os.path.isdir(default_hooks):
        carry = [f for f in sorted(os.listdir(default_hooks))
                 if not f.endswith(".sample")
                 and os.path.isfile(os.path.join(default_hooks, f))]
        # The one name this installer also writes cannot keep it (issue #33) - it is carried
        # under a recorded rename and the generated hook execs it first, failure still blocking.
        if "pre-commit" in carry:
            carry.remove("pre-commit")
            carried_precommit = True

    bin_dir = os.path.join(root, NS_DIR, "bin")
    body = HOOK.format(v=VERSION,
                       hooks=HOOKS_DIR.replace("\\", "/"),
                       index=index_rel.replace("\\", "/"),
                       baseline=('--baseline "%s"' % baseline_rel.replace("\\", "/")) if baseline_rel else "")

    print("ns_install v%s   %s%s" % (VERSION, root, "   [DRY RUN]" if dry else ""))
    print("  will create   %s" % os.path.join(HOOKS_DIR, "pre-commit"))
    print("  will create   %s" % INSTALL_JSON)
    print("  will vendor   %s/bin/{check.py, index.py}  (hook resolves from repo root)" % NS_DIR)
    if carry:
        print("  will carry    existing hooks into the new dir: %s" % ", ".join(carry))
    if carried_precommit:
        print("  will carry    the existing pre-commit as pre-commit.carried - it runs FIRST "
              "on every commit and its failure still blocks")
    print("  will set      core.hooksPath = %s   (was: %s)" % (HOOKS_DIR, prev or "unset"))
    print("  behaviour     ns_check --staged on every commit;")
    print("                exit 1 blocks · exit 3 warns and ALLOWS · --no-verify bypasses")
    print("  reverse with  python ns_install.py . --uninstall")
    if dry:
        print("\n  --dry-run: nothing was written, no config was set.")
        return 0

    os.makedirs(hooks_abs, exist_ok=True)
    # Vendor the tools INTO the repo. Without this the generated hook points at an absolute
    # path on the installing machine and is dead in anyone else's clone - the blocker this
    # file documented against itself since v1.0.0.
    os.makedirs(bin_dir, exist_ok=True)
    vendored = []
    for tool in ("check.py", "index.py", "install.py"):
        src = os.path.join(here, tool)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(bin_dir, tool))
            vendored.append(NS_DIR + "/bin/" + tool)
    for f in carry:
        shutil.copy2(os.path.join(default_hooks, f), os.path.join(hooks_abs, f))
    if carried_precommit:
        dst = os.path.join(hooks_abs, "pre-commit.carried")
        shutil.copy2(os.path.join(default_hooks, "pre-commit"), dst)
        os.chmod(dst, os.stat(dst).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        carry = carry + ["pre-commit.carried"]
    with io.open(hook_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(body)
    os.chmod(hook_path, os.stat(hook_path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    run(["git", "config", "core.hooksPath", HOOKS_DIR], root, check=True)

    rec = {"schema": 1, "installer": "ns_install.py v" + VERSION,
           "installed_at": run(["git", "log", "-1", "--format=%cI"], root).stdout.strip() or None,
           "by": "ns_install", "previous_hookspath": prev,
           "files_written": [os.path.join(HOOKS_DIR, "pre-commit").replace("\\", "/"),
                             INSTALL_JSON.replace("\\", "/")],
           "carried_hooks": carry, "vendored": vendored,
           "hook_sha256_16": sha16(hook_path),
           "checker": checker.replace("\\", "/"), "index": index_rel.replace("\\", "/")}
    with io.open(ij, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(rec, indent=2, sort_keys=True) + "\n")
    print("\n  INSTALLED. hook sha %s" % rec["hook_sha256_16"])
    print("  Verify now:  git commit --allow-empty -m test   (then reset if it passes)")
    return 0


def uninstall(root, dry, purge=False):
    ij = os.path.join(root, INSTALL_JSON)
    if not os.path.isfile(ij):
        print("  nothing to uninstall: %s not found." % INSTALL_JSON)
        hp = current_hookspath(root)
        if hp:
            print("  NOTE: core.hooksPath is set to '%s' but was not set by this tool." % hp)
            print("  Leaving it alone - removing another tool's config is not ours to do.")
        return 3
    rec = json.load(io.open(ij, encoding="utf-8"))
    prev = rec.get("previous_hookspath")
    print("ns_install v%s   uninstall   %s%s" % (VERSION, root, "   [DRY RUN]" if dry else ""))
    print("  restore  core.hooksPath -> %s" % (prev or "(unset)"))
    for f in rec.get("files_written", []):
        print("  remove   %s" % f)
    for f in rec.get("vendored", []):
        print("  remove   %s   (vendored at install, not your data)" % f)
    if rec.get("carried_hooks"):
        print("  NOTE     carried hooks (%s) were copies; the originals in .git/hooks are untouched"
              % ", ".join(rec["carried_hooks"]))
    keep = [f for f in ("index.json", "baseline.json")
            if os.path.isfile(os.path.join(root, NS_DIR, f))]
    if keep and not purge:
        print("  KEEP     %s - your data, not install scaffolding. Remove with --purge."
              % ", ".join(NS_DIR + "/" + f for f in keep))
    elif keep:
        for f in keep:
            print("  remove   %s/%s   (--purge)" % (NS_DIR, f))
    print("  remove   %s/ (only if empty afterwards)" % NS_DIR)
    if dry:
        print("\n  --dry-run: nothing changed.")
        return 0
    if prev:
        run(["git", "config", "core.hooksPath", prev], root)
    else:
        run(["git", "config", "--unset", "core.hooksPath"], root)
    for f in list(rec.get("files_written", [])) + list(rec.get("vendored", [])):
        p = os.path.join(root, f.replace("/", os.sep))
        if os.path.isfile(p):
            os.remove(p)
    if purge:
        for f in ("index.json", "baseline.json"):
            p = os.path.join(root, NS_DIR, f)
            if os.path.isfile(p):
                os.remove(p)
    hooks_abs = os.path.join(root, HOOKS_DIR)
    # our own tools create __pycache__ in .kibsu/bin when they import each other; that residue
    # would leave .kibsu/ un-removable and make "uninstalled" untrue.
    pyc = os.path.join(root, NS_DIR, "bin", "__pycache__")
    if os.path.isdir(pyc):
        shutil.rmtree(pyc, ignore_errors=True)
    for d in (hooks_abs, os.path.join(root, NS_DIR, "bin"), os.path.join(root, NS_DIR)):
        try:
            if os.path.isdir(d) and not os.listdir(d):
                os.rmdir(d)
        except OSError:
            pass
    print("\n  UNINSTALLED. core.hooksPath is now: %s" % (current_hookspath(root) or "(unset)"))
    return 0


def main():
    ap = argparse.ArgumentParser(prog="python -m kibsu install", description="Wire ns_check to git commit, reversibly.")
    ap.add_argument("repo", nargs="?", default=".")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--install", action="store_true")
    g.add_argument("--uninstall", action="store_true")
    g.add_argument("--status", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--purge", action="store_true",
                    help="uninstall AND delete .kibsu/index.json + baseline.json (your data)")
    ap.add_argument("--index", default=os.path.join(NS_DIR, "index.json"))
    ap.add_argument("--baseline", default=None)
    a = ap.parse_args()
    root = os.path.abspath(a.repo)
    if a.status:
        return status(root)
    if a.install:
        return install(root, a.dry_run, a.force, a.index, a.baseline)
    return uninstall(root, a.dry_run, a.purge)


if __name__ == "__main__":
    sys.exit(main())
