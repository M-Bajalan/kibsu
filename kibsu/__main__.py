"""Command-line entry point for kibsu.

Run as `python -m kibsu <command> ...`. Tier A tools (discover, index, install, tokens,
survey) and Tier B tools (check, report, guide, audit) are ported and registered below;
Tier C (learn, gate) is now fully ported too.
"""

import argparse
import importlib
import sys

from . import __version__


def _cmd_version(args):
    print("kibsu %s (scorer %s)" % (__version__, _scorer_version()))
    return 0


def _scorer_version():
    # The package version says which CLI shipped; the scorer version (audit.py's VERSION,
    # stamped into every evidence JSON) says which RULESET measured. They move independently -
    # a reader checking "was this measured with the instrument that had the bugs" needs the
    # second number, so --version prints both.
    from . import audit
    return audit.VERSION


# Tools that carry their own argparse.ArgumentParser and handle their own -h/--help. Their
# argv is forwarded untouched (see _forward below) rather than re-parsed by argparse
# subparsers here: argparse.REMAINDER does not reliably swallow a bare "--help" as the very
# first token of a subparser with no other options defined, so dispatch for these is
# done by slicing sys.argv directly, before kibsu's own top-level parser ever runs.
_FORWARDED = ("discover", "index", "install", "tokens", "check", "report", "guide", "audit", "learn", "gate")


def _forward(subcommand, extra_args):
    """Hand off to a ported tool's own main(), unmodified.

    discover.py / index.py / install.py / tokens.py each carry their own
    argparse.ArgumentParser and call parse_args() with no explicit argv, so it reads
    sys.argv[1:]. To reuse that logic exactly as ported, sys.argv is swapped for the
    duration of the call to `[subcommand] + extra_args`; each tool's own ArgumentParser has
    prog= set to "python -m kibsu <subcommand>", so its own --help / usage / error output is
    correct regardless of what sys.argv[0] happens to be under `python -m kibsu`.
    """
    module = importlib.import_module("." + subcommand, __package__)
    old_argv = sys.argv
    try:
        sys.argv = [subcommand] + list(extra_args)
        return module.main()
    finally:
        sys.argv = old_argv


def _cmd_survey(args):
    # survey.py has no argparse of its own (see that file) - it reads sys.argv[1] directly
    # as an optional local-repo path, and unconditionally clones + audits ten public repos
    # on every real run regardless of that argument. So --help is handled entirely by THIS
    # subparser (add_help defaults to True below) and never reaches survey.main() at all;
    # that is deliberate, not an oversight, and keeps `--help` free of network side effects.
    from . import survey
    old_argv = sys.argv
    try:
        sys.argv = ["survey", args.local] if args.local else ["survey"]
        survey.main()
    finally:
        sys.argv = old_argv
    return 0


# Subcommand registry: name -> (help text, handler(args) -> exit code). Only used for
# commands NOT in _FORWARDED - those are dispatched earlier, in main(), by slicing argv.
_SUBCOMMANDS = {
    "version": ("print the installed kibsu version", _cmd_version),
    "discover": ("what is configured in a repo, and what actually runs", None),
    "index": ("build a deterministic markdown index with a derived taxonomy", None),
    "install": ("wire the check gate to git commit, reversibly (needs the check tool - "
                "see its own --help)", None),
    "tokens": ("model-tier subagent guard, cost ledger, and spend report", None),
    "survey": ("clone public agent-instruction repos, audit each, print the distribution",
               _cmd_survey),
    "check": ("check the repo against its own index - the pre-commit gate (needs an index - "
              "see the index tool)", None),
    "report": ("read-only readiness report: what an agent cannot do here yet", None),
    "guide": ("what an agent actually has to remember, vs. what a mechanism enforces", None),
    "audit": ("measure the checkable:claimable ratio of an agent skill set", None),
    "learn": ("does the shared knowledge base still tell the truth - dangling links, rotted "
              "citations, orphans", None),
    "gate": ("the commit gate: runs the commands configured under \"gates\" in .kibsu.json and "
             "blocks only on a NEW finding (needs a baseline - see its own --help)", None),
}


def build_parser():
    parser = argparse.ArgumentParser(
        prog="kibsu",
        description=(
            "Kibsu reads your coding-agent instructions (AGENTS.md, CLAUDE.md, "
            "skills, memory) and reports which of them can actually be "
            "verified from the repository."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version="kibsu %s (scorer %s)" % (__version__, _scorer_version()),
    )

    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    for name, (help_text, _handler) in _SUBCOMMANDS.items():
        if name == "survey":
            sp = subparsers.add_parser(name, help=help_text)
            sp.add_argument(
                "local",
                nargs="?",
                default=None,
                help="optional local repo to audit for comparison (this still clones and "
                     "audits public repos over the network regardless)",
            )
        else:
            # For _FORWARDED names this subparser only exists so `python -m kibsu --help`
            # lists them; real invocations are intercepted in main() before parse_args runs.
            subparsers.add_parser(name, help=help_text)

    return parser


def main(argv=None):
    raw = sys.argv[1:] if argv is None else list(argv)

    if raw and raw[0] in _FORWARDED:
        return _forward(raw[0], raw[1:])

    parser = build_parser()
    args = parser.parse_args(raw)

    if not args.command:
        parser.print_help()
        return 0

    _help_text, handler = _SUBCOMMANDS[args.command]
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
