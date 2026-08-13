#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kibsu audit v0.6.0 - how much of an agent instruction set can actually be checked?

An instruction is CHECKABLE if a reviewer could tell from the repo alone whether it happened: it
runs a command, produces or edits a named file, or is a tick-box. It is CLAIMABLE if the only
evidence is the agent saying so.

v0.6.0 is three corrections to what the scorer can SEE, none to how it judges (#26/#27/#28):
MODALS is case-insensitive ("- Must run the tests." was counted as no instruction at all -
Title-case matched neither the ALL-CAPS nor the lowercase alternation, and SHOULD / REQUIRED /
MANDATORY had no lowercase branch to begin with); check_artifacts() records every ancestor
directory, not just immediate parents, so a mandate under a directory holding only
subdirectories (skills/ in a skills/<name>/SKILL.md tree) stays in the phantom population; and
strip_frontmatter() strips a UTF-8 BOM before testing for "---", the fix parse_frontmatter in
index.py had already carried. All three widen what is measured, so figures moved and the
re-measure is indexed in CORRECTIONS.md like every round before it.

v0.5.0 is the SCAFFOLD-SCOPE redesign plus the disclosure ledger. The scope filter used to sweep
at the UNIT level: one scaffold keyword anywhere in a skill's frontmatter or the first 1500
characters of its body excluded every artifact that skill mandated, no matter how far the
keyword was from the actual mandate line. That blanket-excluded artifacts a skill never
scaffolds at all - a persona skill that merely described "Template-driven and reactive forms"
lost phantom-checking on an unrelated `CHANGELOG.md` mandate three paragraphs later, because
"template" matched somewhere upstream. Replaced by a LINE-LEVEL rule scoped to the mandate's own
captured line: excluded as scaffold-scope only when a scaffold keyword and user-scope language
("your project", "the new project", "the generated", "into the user's ...") co-occur on THAT
line, and the keyword itself is not negated within a few tokens before it ("do not scaffold",
"never scaffold any project"). A unit's frontmatter can also DECLARE its scope explicitly
(`scope: user-project` or `scope: repo`) and the declaration wins over the heuristic in both
directions - it is checked first and, when present, the heuristic never runs at all.

The second half is the disclosure ledger: every exclusion reason-class this tool applies
(scaffold-scope, user-scope, prefix-missing, declared-scope, unverifiable_pattern, length-cap)
is now reported with its FULL count, not a handful of samples, in both --json and text output -
and the phantom rate is printed twice: once over the in-scope, verifiable artifacts alone (what
the headline PHANTOM line already reported), and once as a counterfactual that simply counts
every excluded artifact too, so nobody has to take on faith that the scope filtering itself
isn't quietly doing the flattering work.

v0.4.0 was the INSTANCE-COUNT phantom redesign (public issue #14). Before that, a `{...}`
placeholder in a mandated artifact - `logs/report_{date}.md` - survived re.escape() as two
literal brace characters, so it could only ever match a file that literally contained a brace:
every templated mandate read as phantom, no matter how many real report_2026-07-30.md files a
repo had ever committed. Fixed by giving `{...}` the identical expansion `*` already got -
"any run of non-slash characters" - applied to the directory prefix as well as the basename, so
a brace in a directory segment is no longer dropped as "path prefix does not exist" (the wrong
reason) before the phantom check ever sees it. phantom is now redefined as match_count == 0 for
literal and templated mandates alike - a templated mandate that DOES match something is not
phantom, but it is CHECKED BY PATTERN, which is weaker evidence than a literal hit and is
labelled as such. A mandate whose expanded basename keeps no literal character beyond the
extension (`{name}.md`, `*.md`) has nothing left to search FOR; it lands in a new
unverifiable_pattern bucket, excluded from the phantom numerator and denominator both, always
reported with its own count. v0.3.0 added the DOCTRINE genre. v0.2.0 added the rest.
  GENRE      persona / procedure / reference / DOCTRINE / mixed. Only PROCEDURE units are fairly
             judged on checkability. A role description promises nothing. A DOCTRINE - "restate the
             intent", "name the hidden assumption" - produces better judgement, not a file, so it
             scores 0% by construction and that says nothing about its worth. Without this genre
             the tool defames the best-written skills in a collection: it rated one at 0/22 and
             called it the most claimable unit in the set, while that skill's own transcripts
             showed 47 uses across 13 sessions. Scoring a doctrine on checkability is a category
             error, and it is the easiest rebuttal to this whole measurement - so the tool makes
             the split itself.
  --artifacts  Extract the files a skill MANDATES, then look for them in the working tree and in
             full git history. A mandated artifact with zero instances, ever, is a phantom: an
             instruction no model has ever been caught skipping.

DESIGN BIAS: every ambiguous instruction counts as CHECKABLE. Reported ratios are CEILINGS.
Dependency-free, Python 3.8+. Reads only - never executes anything it scans.

EXIT CODES
  0  the audit ran to completion and printed its measurements (text or --json). A low
     checkable:claimable ratio, however low, never changes this code - this tool measures, it
     does not pass/fail.
  1  no .md files were found under <dir> - there was nothing to audit. The only other code this
     tool returns.

  python -m kibsu audit <dir> [--json] [--definitions] [--artifacts] [--limit N]
"""
import argparse
import io
import json
import os
import re
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

VERSION = "0.6.0"

# Issue #39: kibsu scans arbitrary third-party repositories, and nothing stops one from
# git-tracking a multi-gigabyte markdown file. A whole-file .read() of that is an unbounded
# allocation the kernel OOM-killer ends with a SIGKILL no `except` clause sees. 5 MB is
# generous for instruction markdown; over-ceiling files are SKIPPED WITH A PRINTED REASON
# on stderr (stdout stays clean for --json), never silently.
MAX_READ_BYTES = 5 * 1024 * 1024
INCLUDE_ARCHIVED = False

RUNNABLE_LANGS = {"bash", "sh", "shell", "console", "powershell", "ps1", "pwsh", "zsh",
                  "python", "py", "cmd", "bat", "sql", "javascript", "js", "node", "ruby", "go"}
BINARIES = r"(?:python3?|py|pip3?|git|npm|npx|pnpm|yarn|node|deno|bun|pytest|tox|make|cargo|go|dotnet|" \
           r"docker|kubectl|terraform|aws|az|gcloud|gh|curl|wget|jq|rg|grep|sed|awk|find|ls|cat|" \
           r"pwsh|powershell|bash|sh|sqlcmd|psql|mysql|ruby|rake|mvn|gradle|java|tsc|eslint|prettier|" \
           r"ruff|black|mypy|vitest|jest|cypress|playwright|bundle|composer|php|dart|flutter|swift)"
INLINE_CMD = re.compile(r"`\s*" + BINARIES + r"\b[^`]*`")
BARE_CMD = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)?" + BINARIES + r"\b\s+\S")
CHECKBOX = re.compile(r"^\s*(?:[-*+]\s*)?(?:\[[ xX]\]|[□☐☑☒])")
# A fence-looking line: a run of 3+ backticks OR 3+ tildes (CommonMark section 4.5), plus
# whatever follows on the line (the candidate info string / closer test happens in analyse()).
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})(.*)$")
PATHY = re.compile(r"[`\"']?[\w./\\*-]+\.(?:md|json|ya?ml|py|ps1|sh|js|ts|tsx|jsx|sql|toml|ini|cfg|txt|csv|lock)\b", re.I)
EXITY = re.compile(r"\b(exit code|exit 0|exit 1|non-zero|returns? 0|must pass|passes|green|fails? loud|"
                   r"assert|verify that|diff|git status|git log|numstat)\b", re.I)
MODALS = re.compile(r"\b(MUST|SHOULD|ALWAYS|NEVER|REQUIRED|DO NOT|DON'T|MANDATORY|"
                    r"ENSURE|MAKE SURE)\b", re.I)
VERBS = (r"add|append|apply|archive|ask|assert|bump|build|call|change|check|clean|clear|close|commit|"
         r"compare|confirm|copy|create|declare|delete|deploy|describe|do|document|edit|enable|ensure|"
         r"enumerate|execute|explain|export|extract|fetch|fill|find|finish|fix|follow|generate|get|give|"
         r"go|grep|handle|identify|implement|include|insert|inspect|install|invoke|keep|list|load|log|"
         r"look|maintain|make|mark|measure|merge|move|name|note|open|output|parse|pass|perform|pick|"
         r"place|prefer|prepare|print|produce|prove|pull|push|put|read|record|refresh|regenerate|"
         r"register|remove|rename|render|repeat|replace|report|require|reset|resolve|restate|restore|"
         r"return|review|rewrite|run|save|scan|search|select|send|set|show|skip|sort|split|stamp|start|"
         r"state|stop|store|summarise|summarize|surface|sweep|switch|sync|tag|take|tell|test|track|"
         r"translate|treat|trigger|update|upgrade|use|validate|verify|walk|write")
IMPERATIVE = re.compile(r"^\s*(?:[-*+>]\s+|\d+[.)]\s+|\|\s*)?(?:" + VERBS + r")\b", re.I)

# ---- genre signals -------------------------------------------------------------------------
PERSONA_RE = [re.compile(p, re.I) for p in (
    r"^\s*you are (a|an|the)\b", r"\byour expertise\b", r"\byou specialize\b", r"\byou specialise\b",
    r"^\s*as an? [\w\s-]{3,30}(,|you)", r"\byour role is\b", r"\byou are responsible for\b",
    r"\bexpert (in|at)\b", r"\byears of experience\b", r"\byou excel at\b", r"\byou have deep\b")]
# --- doctrine signals -------------------------------------------------------------------
# A DOCTRINE tells the agent how to THINK, not what to DO. Scoring it on checkability is a
# category error: "name the hidden assumption" produces better judgement, not a file, so it
# will always score 0% and that says nothing about its worth. Without this genre the tool
# systematically defames the best-written skills in any collection - it scored a skill whose
# own transcripts show 47 uses at 0/22 and called it the most claimable unit in the set.
DOCTRINE_RE = [re.compile(p, re.I) for p in (
    r"\b(ask yourself|before you (act|build|answer|start|begin)|the temptation|resist the|"
    r"instead of|rather than|do not assume|question the|challenge the|hidden assumption|"
    r"think (about|through|twice)|notice (when|that)|judgement call|judgment call|"
    r"when in doubt|it is not enough|the point is not|second-guess)\b",
    r"\b(anti-?pattern|red flag|failure mode|smell test|rationalis\w*|rationaliz\w*|"
    r"blind spot|assumption)\b",
    r"\bnot\b[^.\n]{0,45}\bbut\b",          # contrast construction: "not X, but Y"
)]
# The load-bearing discriminator: what does the INSTRUCTION ask for? An epistemic instruction
# asks the agent to think differently ("restate the intent", "name the hidden assumption").
# An action instruction asks it to change the world ("run the checker", "update the index").
# Document furniture - numbered headings, tables - does not distinguish the two: ten numbered
# PRINCIPLES look identical to ten numbered STEPS. The verb does distinguish them.
EPISTEMIC = re.compile(
    r"^\s*(?:[-*+>]\s+|\d+[.)]\s+|\*\*)?(?:restate|question|challenge|assume|notice|consider|"
    r"judge|doubt|think|understand|interpret|weigh|distinguish|recogni[sz]e|resist|avoid|prefer|"
    r"name|surface|separate|reframe|suspect|verify before|ask)", re.I)
STEPY = re.compile(r"^\s*(?:#+\s*)?(?:step\s*)?\d+[.)]\s+\S", re.I)
SEQ = re.compile(r"^\s*(?:#+\s*)?(first|then|next|finally|afterwards|before you|after you|"
                 r"once you|begin by|start by)\b", re.I)
TABLE = re.compile(r"^\s*\|.*\|\s*$")
ARTIFACT_VERB = re.compile(
    r"\b(creat|writ|wrote|append|produc|generat|sav|emit|updat|record|log|output|add|regenerat|"
    # "scaffold" added alongside "generate" - a skill that SCAFFOLDS a file is describing the
    # identical artifact-producing action, just usually one aimed at the user's project rather
    # than this repo. Without it, a genuine "scaffolds `src/App.tsx` in the new project" line
    # never even reached FILE_TOKEN extraction, so the new line-level scaffold-scope rule below
    # (see SCAFFOLD_SKILL / USER_SCOPE_LINE) had nothing to apply to in the one case it exists
    # to catch.
    r"stamp|bump|export|scaffold)\w*\b", re.I)
FILE_TOKEN = re.compile(
    # tsx/jsx added to the extension list - previously missing here even though PATHY (above)
    # already recognised them for checkability. A mandate naming a `.tsx`/`.jsx` file - exactly
    # the shape a React/Angular scaffolding skill mandates - silently never became an "artifact"
    # at all before this, regardless of any scope rule. re.I carried from the
    # case-insensitivity fix: `NOTES.MD` is the same mandate as `notes.md`.
    r"`([^`\s]*?[\w*\[\]{}-]+\.(?:md|json|ya?ml|py|ps1|sh|js|ts|tsx|jsx|sql|toml|ini|cfg|txt|csv))`", re.I)

# --- phantom-scope filters (fix for the false-positive class) --------------------------------
# A mandated artifact only counts as a PHANTOM if the skill claims it is produced INSIDE the repo
# the skill lives in. Skills that scaffold the *user's* project legitimately name files that will
# never exist here, and scoring them was wrong.
#
# v0.5.0: this used to be swept at the UNIT level (see module docstring) - SCAFFOLD_SKILL run
# against a skill's frontmatter and the first 1500 characters of its body, and a single hit
# excluded EVERY artifact that unit mandates. It is now applied LINE-BY-LINE, at each artifact's
# own captured mandate line, by scaffold_scope_reason() below - SCAFFOLD_SKILL and
# USER_SCOPE_LINE are the same two vocabularies, just no longer searched across the whole unit.
SCAFFOLD_SKILL = re.compile(
    r"\b(scaffold|boilerplate|starter|template|generator|generate a new|create a new project|"
    r"new project|project init|bootstrap a)\w*\b", re.I)
USER_SCOPE_LINE = re.compile(
    r"\b(your|the user'?s?|target|destination|output|new)\s+"
    r"(project|repo(sitory)?|app|application|codebase|directory|folder)\b|"
    r"\bin your\b|\bfor the user\b|\bthe generated\b|"
    # "into the user's ..." on its own - not conditioned on one of the specific nouns above, so
    # "into the user's workspace" / "into the user's home directory" count too, not just the
    # fixed noun list a phrase like that might otherwise miss.
    r"\binto the user'?s\b", re.I)

# NEGATED: a scaffold keyword match is disqualified when one of these sits a few tokens before
# it on the same line - "do not scaffold", "don't scaffold a new project", "never scaffold any
# project". Without this, a skill that explicitly documents what it does NOT do ("do NOT ...
# scaffold any project") would still be read as claiming exactly the behaviour it just denied.
NEGATION_RE = re.compile(r"\b(?:do\s+not|don'?t|never)\b", re.I)
NEGATION_WINDOW_TOKENS = 6


def _negated_before(line, match_start):
    """True if a negation word (do not / don't / never) appears within a few tokens
    immediately before a scaffold-keyword match starting at `match_start` in `line`."""
    prefix_tokens = line[:match_start].split()
    window = " ".join(prefix_tokens[-NEGATION_WINDOW_TOKENS:])
    return bool(NEGATION_RE.search(window))


def scaffold_scope_reason(line):
    """The v0.5.0 LINE-LEVEL scaffold-scope rule: an artifact's own mandate line is excluded as
    scaffold-scope only when BOTH are true on that exact line -

      1. user-scope language is present at all (USER_SCOPE_LINE) - otherwise a bare "scaffold"
         mention (e.g. a persona skill's unrelated "Template-driven forms" aside) has nothing to
         co-occur with and proves nothing about where the mandated artifact lands.
      2. at least one scaffold keyword on that line is not negated within a few tokens before it
         - "do not ... scaffold any project" must not exclude the artifact it is denied on.

    Returns a human-readable reason string, or None if the line does not qualify.
    """
    if not USER_SCOPE_LINE.search(line):
        return None
    for m in SCAFFOLD_SKILL.finditer(line):
        if not _negated_before(line, m.start()):
            return "scaffold keyword and user-scope language co-occur on this line"
    return None


# DECLARED SCOPE OVERRIDE: a unit's frontmatter can say `scope: user-project` or `scope: repo`
# outright, and that declaration wins over the heuristic above in BOTH directions - see
# analyse()'s `declared_scope` and check_artifacts()'s scope-determination block.
DECLARED_SCOPE_RE = re.compile(r"^\s*scope\s*:\s*([A-Za-z-]+)\s*(?:#.*)?$", re.M)
VALID_DECLARED_SCOPES = ("user-project", "repo")

DEFINITIONS = """
METRIC DEFINITIONS (contest them - that is the point)

  instruction  a non-heading, non-code line telling the agent to do something: opens with an
               imperative verb, or carries a modal (must / should / always / never / required /
               do not / mandatory / ensure / make sure - any capitalisation; "Must run the
               tests" counts the same as "MUST run the tests").

  CHECKABLE    a reviewer could confirm it happened from the repo alone:
                 tick-box | runnable command | names a concrete file | exit code / diff / assertion
  CLAIMABLE    everything else. Only evidence is the agent's own report.

  GENRE        persona   - describes WHO the agent is ("You are a senior Rust engineer...").
                           Promises nothing, so checkability is NOT a fair measure of it.
               procedure - describes WHAT TO DO, in order. Checkability applies fully.
               doctrine  - describes HOW TO THINK ("name the hidden assumption before building").
                           Produces judgement, not artifacts. Checkability does NOT apply, and a
                           0% here is the genre working as intended, not a defect.
               reference - lookup material: tables, definitions, options.
               mixed     - no signal dominates.
               NOTE: procedure is weighted toward EXECUTABLE signals (commands, checkboxes), not
               merely numbered ones - ten numbered principles are not a ten-step procedure.

  phantom      an artifact a skill mandates with ZERO matching instances anywhere - working tree
               OR git history, counted together as match_count. Requires full history; a shallow
               clone reports UNKNOWN, never zero. This applies identically to a literal mandate
               (`CHANGELOG.md`) and a templated one (`logs/report_{date}.md`): a templated
               mandate that matches something is not phantom, and a templated mandate that
               matches nothing is STILL phantom - braces do not launder a mandate nobody served.

  templated    the mandated token contains a wildcard (`*`, `?`) or a `{...}` placeholder
               segment, either of which expands to "any run of non-slash characters" when
               searched for (a lone `?` expands to "any one character"). A match found this way
               is CHECKED BY PATTERN, which is weaker evidence than a literal match: it proves
               *some* file of that shape exists, not that this exact name does. `*` has expanded
               this way since v0.1.0 - that was never written down until now. `{...}` gets the
               identical treatment as of v0.4.0 (public issue #14).

  unverifiable_pattern
               a mandated artifact whose basename, once every wildcard/placeholder is stripped
               back out, has no literal character left besides the extension - `{name}.md`,
               `*.md`, or `{a}/{b}.yml` (empty literal basename). There is nothing left to search
               FOR: any file with that extension would "match", so neither a hit nor a miss means
               anything. A binary structural rule, not a tunable threshold - excluded from both
               the phantom numerator and denominator, always reported separately with its count.

  scaffold-scope (v0.5.0)
               a mandated artifact is excluded as scaffold-scope when a scaffold keyword
               (scaffold/boilerplate/starter/template/generator/bootstrap/"new project"/...) and
               user-scope language ("your project", "the new project", "the generated", "into
               the user's ...") BOTH appear on the artifact's own mandate line, and the keyword
               is not negated within a few tokens before it ("do not scaffold", "never scaffold
               any project" do NOT exclude). LINE-LEVEL as of v0.5.0 - before this, one keyword
               hit ANYWHERE in a skill's frontmatter or first 1500 characters of body excluded
               EVERY artifact that skill mandates, however unrelated. A persona skill whose body
               merely says "Template-driven and reactive forms" no longer sweeps an unrelated
               `CHANGELOG.md` mandate three paragraphs later out of scope.

  user-scope   a weaker, independent signal: the mandate line carries user-scope language with
               no scaffold keyword required at all ("Save `x.md` into your project's config
               directory."). Reported as its own reason-class, distinct from scaffold-scope.

  declared scope (v0.5.0)
               a unit's frontmatter can declare its scope outright - `scope: user-project` or
               `scope: repo` - and the declaration wins over the heuristic above in BOTH
               directions: `user-project` excludes even a mandate line with no scope language at
               all, `repo` keeps the scaffold-scope/user-scope heuristic from ever running (the
               path-prefix check still applies either way - it is a directory-existence fact,
               not a scope judgement call).

  exclusion ledger (v0.5.0)
               every exclusion reason-class this tool applies - scaffold-scope, user-scope,
               prefix-missing, declared-scope, unverifiable_pattern, length-cap - reported with
               its FULL count, in both --json (`exclusion_ledger`) and text output, never
               sampled down the way the illustrative "sample" lists elsewhere in this output are.

  phantom counterfactual (v0.5.0)
               the phantom rate printed TWICE: once over in-scope, verifiable artifacts alone
               (`in_scope_pct` - what the headline PHANTOM line has always reported), and once
               as though every exclusion above were simply counted instead (`all_pct`) - so the
               scope filtering's own effect on the number is visible, not silent denominator
               surgery. The counterfactual cannot include length-cap drops (they never became an
               artifact record with a match_count to test), so `all_pct` is itself a floor, not
               "truly everything" - the ledger's separate length-cap count discloses that gap.

  BIAS         ambiguity resolves to CHECKABLE. Reported ratios are ceilings.
"""


def strip_frontmatter(t):
    # A UTF-8 BOM defeats startswith("---"). Same bytes, same fix as index.py's
    # parse_frontmatter - the two must not disagree about whether frontmatter exists (#28).
    t = t.lstrip("﻿")
    if t.startswith("---"):
        e = t.find("\n---", 3)
        if e != -1:
            return t[e + 4:], t[3:e]
    return t, ""


def classify(sig, lines):
    """Explicit, contestable. Densities per 100 lines so long files are not penalised.

    PROCEDURE is weighted toward EXECUTABLE signals - commands and checkboxes - not merely
    numbered ones. A doctrine with ten numbered principles is not a ten-step procedure, and
    an earlier version of this function classified exactly that way.
    """
    k = 100.0 / max(1, lines)
    persona = sig["persona_hits"] * k * 3.0
    procedure = (sig["steps"] * 0.5 + sig["checkboxes"] * 2 + sig["runnable_fences"] * 3
                 + sig["seq"]) * k
    reference = sig["tables"] * k * 0.7
    doctrine = sig["doctrine_hits"] * k * 1.6
    scores = dict(persona=round(persona, 2), procedure=round(procedure, 2),
                  reference=round(reference, 2), doctrine=round(doctrine, 2))
    best = max(persona, procedure, reference, doctrine)
    if best < 0.8:
        return "mixed", scores
    for name, val in (("doctrine", doctrine), ("procedure", procedure),
                      ("persona", persona), ("reference", reference)):
        if val == best:
            return name, scores
    return "mixed", scores


def analyse(text):
    body, fm = strip_frontmatter(text)
    m = re.search(r"^\s*genre\s*:\s*([A-Za-z]+)\s*(?:#.*)?$", fm, re.M)
    fm_genre = m.group(1) if m else None
    # DECLARED SCOPE: `scope: user-project` / `scope: repo` in frontmatter. Parsed here,
    # identically to genre above, so check_artifacts() can honour it over the line-level
    # heuristic in both directions (see scaffold_scope_reason() and DECLARED_SCOPE_RE).
    m_scope = DECLARED_SCOPE_RE.search(fm)
    fm_scope = (m_scope.group(1) if m_scope else "").strip().lower()
    lines = body.split("\n")
    o = dict(lines=len(lines), fences=0, runnable_fences=0, checkboxes=0, instructions=0,
             checkable=0, claimable=0, inline_cmds=0, steps=0, seq=0, tables=0,
             persona_hits=0, doctrine_hits=0, epistemic=0, action=0, mandated=[],
             length_cap_dropped=0,
             declared_scope=(fm_scope if fm_scope in VALID_DECLARED_SCOPES else None))
    if any(r.search(fm) for r in PERSONA_RE):
        o["persona_hits"] += 2
    # CommonMark-aligned fence tracking (fixes public issue #13 and its ~~~ sibling). A fence
    # OPENS on a run of 3+ backticks or 3+ tildes, and records the delimiter char, the run
    # length, and the info string (lang). While inside, a line CLOSES the fence only if it
    # repeats the SAME delimiter char, with a run at least as long as the opener, and carries
    # NO info string (a bare closer) - section 4.5. The old code was a plain boolean that
    # toggled on ANY ```-looking line: no delimiter check, no length check, no info-string
    # check, and no ~~~ support at all. That meant a fenced EXAMPLE that itself contained a
    # fence (e.g. a ```md block showing a ```bash snippet) flipped the state early and let the
    # example's checkboxes/instructions/mandated artifacts leak into the real counts. Any
    # fence-looking line that fails the closer test is just fence CONTENT - skip it exactly
    # like the rest of the fence body, don't toggle.
    in_fence, fence_char, fence_len, lang = False, "", 0, ""
    for ln in lines:
        f = FENCE_RE.match(ln)
        if f:
            run, rest = f.group(1), f.group(2)
            if in_fence:
                if run[0] == fence_char and len(run) >= fence_len and not rest.strip():
                    in_fence, fence_char, fence_len, lang = False, "", 0, ""
                # else: fence-looking but not a valid closer (wrong char, too short, or carries
                # an info string) - it's content inside the still-open fence, fall through to
                # "if in_fence: continue" below like any other line in the fence body.
            else:
                in_fence, fence_char, fence_len = True, run[0], len(run)
                lang = (re.match(r"^\s*([\w+-]*)", rest).group(1) or "").lower()
                o["fences"] += 1
                if lang in RUNNABLE_LANGS:
                    o["runnable_fences"] += 1
            continue
        if in_fence:
            continue
        if TABLE.match(ln):
            o["tables"] += 1
        if any(r.search(ln) for r in PERSONA_RE):
            o["persona_hits"] += 1
        for r in DOCTRINE_RE:
            o["doctrine_hits"] += len(r.findall(ln))
        if STEPY.match(ln):
            o["steps"] += 1
        if SEQ.match(ln):
            o["seq"] += 1
        if ln.lstrip().startswith("#"):
            continue
        n_inline = len(INLINE_CMD.findall(ln))
        o["inline_cmds"] += n_inline
        is_box = bool(CHECKBOX.match(ln))
        if is_box:
            o["checkboxes"] += 1
        if not ln.strip():
            continue
        if not (is_box or IMPERATIVE.match(ln) or MODALS.search(ln)):
            continue
        o["instructions"] += 1
        o["epistemic" if EPISTEMIC.match(ln) else "action"] += 1
        checkable = (is_box or n_inline > 0 or bool(BARE_CMD.match(ln))
                     or bool(PATHY.search(ln)) or bool(EXITY.search(ln)))
        o["checkable" if checkable else "claimable"] += 1
        if ARTIFACT_VERB.search(ln):
            for m in FILE_TOKEN.findall(ln):
                # Strip a leading "./" as a PREFIX. lstrip("./\\") takes a character SET and
                # eats the dot of ".agents/skills/x", turning a real path into one that resolves
                # nowhere - so the artifact is silently dropped and reads as "not mandated".
                # See memory/learnings/a-checker-that-guesses-the-base-path-cries-wolf.md rule 3.
                tok = m.strip().replace("\\", "/")
                while tok.startswith("./"):
                    tok = tok[2:]
                if tok and len(tok) < 90:
                    o["mandated"].append({"tok": tok, "line": ln.strip()[:200]})
                elif tok:
                    # LENGTH-CAP: a token this long never becomes an "artifact" record at all -
                    # it is dropped here, before check_artifacts() ever sees it, so it cannot
                    # appear in `arts` for the disclosure ledger to count by inspecting records
                    # that don't exist. Counted here instead, and summed across all rows in
                    # main(), so this exclusion class is disclosed too, not just silently gone.
                    o["length_cap_dropped"] += 1
    seen = set()
    uniq = []
    for m in o["mandated"]:
        if m["tok"] not in seen:
            seen.add(m["tok"]); uniq.append(m)  # noqa: E702 -- mandated-token dedup; out of scope for lint-wiring
    o["mandated"] = uniq
    detected, o["genre_scores"] = classify(o, o["lines"])
    # DECLARATION BEATS DETECTION. Auto-detecting "doctrine" reliably proved beyond this tool:
    # ten numbered PRINCIPLES are structurally identical to ten numbered STEPS, and every
    # heuristic tried was really the author's prior belief in regex form. So the skill author
    # states the genre and the tool reports it - while still detecting independently and
    # FLAGGING disagreement, so a declaration cannot quietly buy a better score.
    declared = (fm_genre or "").strip().lower()
    if declared in ("procedure", "doctrine", "persona", "reference", "mixed"):
        o["genre"], o["genre_source"] = declared, "declared"
        o["genre_conflict"] = (declared != detected)
    else:
        o["genre"], o["genre_source"] = detected, "detected"
        o["genre_conflict"] = False
    o["genre_detected"] = detected
    return o


META = {"readme", "contributing", "license", "licence", "changelog", "code_of_conduct", "security",
        "index", "install", "installation", "faq", "authors", "notice", "roadmap", "support",
        "governance", "history", "upgrading", "migration", "todo"}
INSTR_DIRS = {"skills", "agents", "subagents", "commands", "rules", "prompts", "plugins",
              ".claude", ".cursor", "categories"}


def _walk(root):
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in (".git", "node_modules", "__pycache__", ".venv", "dist", "build")
                 and (INCLUDE_ARCHIVED or not d.startswith("_"))]
        yield dp, fn


def find_skills(root):
    hits = [os.path.join(dp, f) for dp, fn in _walk(root) for f in fn if f.lower() == "skill.md"]
    if hits:
        return hits, "SKILL.md"
    ok = lambda f: f.lower().endswith(".md") and os.path.splitext(f)[0].lower() not in META  # noqa: E731 -- find_skills() predicate; out of scope for lint-wiring
    parts = lambda dp: {p.lower() for p in os.path.relpath(dp, root).replace("\\", "/").split("/")}  # noqa: E731 -- same, find_skills() predicate
    hits = [os.path.join(dp, f) for dp, fn in _walk(root) for f in fn if ok(f) and (parts(dp) & INSTR_DIRS)]
    if hits:
        return hits, "instruction-dir/*.md"
    return [os.path.join(dp, f) for dp, fn in _walk(root) for f in fn if ok(f)], "*.md (no instruction dir)"


# ---- artifacts ----------------------------------------------------------------------------
def git_root(path):
    p = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=path,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.stdout.strip() if p.returncode == 0 else None


def history_paths(root):
    """All paths ever touched, plus whether history is shallow (which makes zero meaningless)."""
    shallow = os.path.isfile(os.path.join(root, ".git", "shallow"))
    p = subprocess.run(["git", "log", "--all", "--pretty=format:", "--name-only"], cwd=root,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    paths = {l.strip() for l in p.stdout.split("\n") if l.strip()} if p.returncode == 0 else set()  # noqa: E741 -- history_paths() measurement logic; out of scope for lint-wiring
    return paths, shallow


def tree_paths(root):
    out = set()
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d != ".git"]
        for f in fn:
            out.add(os.path.relpath(os.path.join(dp, f), root).replace("\\", "/"))
    return out


# A `{...}` placeholder segment - the `{date}` in `logs/report_{date}.md` - gets the IDENTICAL
# expansion a bare `*` already gets: "any run of non-slash characters". This is the ONE shared
# regex both glob_re() (which builds the search pattern) and the templated-ness classification
# below use to find those segments, so the two can never quietly drift apart on what counts as a
# placeholder.
PLACEHOLDER_RE = re.compile(r"\{[^{}]*\}")
# templated = the token carries EITHER kind of wildcard - `*`/`?` or a `{...}` placeholder. Any
# match found through one of these is CHECKED BY PATTERN: weaker evidence than a literal path
# match (see --definitions), and worth labelling as such in the output either way.
TEMPLATED_RE = re.compile(r"[*?]|\{[^{}]*\}")


def glob_re(tok):
    r"""Build the matcher for a mandated-artifact token.

    `*` -> "any run of non-slash characters" and `?` -> "any one character" have been true since
    v0.1.0 - undocumented until this version's --definitions update. `{...}` placeholder segments
    get the IDENTICAL expansion as of v0.4.0 (public issue #14): before this fix, `re.escape()`
    ran across the whole token and locked `{`/`}` down as two more literal characters, so a
    templated mandate could only ever match a file whose name literally contained a brace.

    The fix has to split the token on PLACEHOLDER_RE *before* calling re.escape() - once
    re.escape() has run, a `{...}` segment is indistinguishable from any other literal substring,
    so there is nothing left to find and swap out afterwards (unlike `*`/`?`, which are single
    characters and survive escaping as a fixed, greppable `\*` / `\?` token). Each literal
    segment between placeholders is escaped on its own and the pieces are rejoined with the same
    "[^/]*" a bare `*` gets, so the expansion is identical either way and the two can never mean
    different things in the same pattern.
    """
    segments = PLACEHOLDER_RE.split(tok)
    escaped = [re.escape(seg).replace(r"\*", "[^/]*").replace(r"\?", ".") for seg in segments]
    esc = "[^/]*".join(escaped)
    return re.compile(r"(^|/)" + esc + r"$", re.I)


def check_artifacts(root, rows):
    gr = git_root(root)
    hist, shallow = (history_paths(gr) if gr else (set(), False))
    tree = tree_paths(gr or root)
    # Every ancestor, not just the immediate parent: a directory holding only subdirectories
    # (skills/ in a skills/<name>/SKILL.md tree) exists just as surely as one holding a file,
    # and the prefix check below is meant to be a directory-existence fact (#27).
    dirs = set()
    for p in (tree | hist):
        d = os.path.dirname(p)
        while d:
            dirs.add(d)
            d = os.path.dirname(d)
    res = []
    for r in rows:
        for m in r["mandated"]:
            tok, line = m["tok"], m["line"]
            # Classified BEFORE the path-prefix filter below, on purpose - see glob_re()'s
            # docstring and the module docstring: a brace in a DIRECTORY segment must not get
            # this mandate dropped as "path prefix does not exist" (comparing `{lang}` to real
            # directory names literally, which always loses) before the phantom check below ever
            # runs the pattern against it. That silent drop-for-the-wrong-reason was issue #14's
            # second bug, hiding behind the first.
            templated = bool(TEMPLATED_RE.search(tok))

            # --- scope filter: is this artifact claimed to live in THIS repo? ---
            # v0.5.0: DECLARED SCOPE (a `scope: user-project` / `scope: repo` key in the unit's
            # own frontmatter) is checked FIRST and, when present, wins over everything below -
            # both directions. A declared `user-project` excludes even a mandate line that
            # carries no scaffold or user-scope language at all; a declared `repo` keeps the
            # line-level scaffold-scope heuristic from ever running, though the path-prefix
            # check further down still applies (the council's ruling to keep it stands - see
            # module docstring - it is a directory-existence fact, not a whose-project-is-it
            # judgement call the author's declaration speaks to).
            reason, reason_class = None, None
            declared_scope = r.get("declared_scope")
            if declared_scope == "user-project":
                reason = "declared scope: user-project (frontmatter overrides the heuristic)"
                reason_class = "declared-scope"
            else:
                if declared_scope != "repo":
                    sreason = scaffold_scope_reason(line)
                    if sreason:
                        reason, reason_class = sreason, "scaffold-scope"
                    elif USER_SCOPE_LINE.search(line):
                        reason = "line refers to the user's project, not this repo"
                        reason_class = "user-scope"
                if reason is None:
                    pre = os.path.dirname(tok.replace("\\", "/"))
                    if pre:
                        # Pattern-aware now, not a literal `d == pre or d.endswith("/" + pre)`: a
                        # `{lang}` or `*` in the directory portion gets the SAME [^/]* expansion
                        # glob_re() gives the filename, via the identical helper, so a templated
                        # directory prefix is checked WITH the pattern applied instead of being
                        # compared to itself literally and always losing.
                        pre_rx = glob_re(pre)
                        if not any(pre_rx.search(d) for d in dirs):
                            reason = "path prefix '%s/' does not exist in this repo" % pre
                            reason_class = "prefix-missing"
            in_scope = reason is None

            rx = glob_re(tok)
            matched_tree = {p for p in tree if rx.search(p)}
            matched_hist = {p for p in hist if rx.search(p)}
            # match_count is the whole point of the redesign: how many distinct instances - tree
            # plus history, deduplicated - this mandate actually has, not just whether it has
            # any. in_tree/in_history are kept as booleans for existing consumers.
            match_count = len(matched_tree | matched_hist)
            hit_tree = bool(matched_tree)
            hit_hist = bool(matched_hist)

            # UNVERIFIABLE: the basename, once every wildcard/placeholder is stripped back out,
            # has no literal character left besides the extension - {name}.md, *.md,
            # {a}/{b}.yml. There is nothing left to search FOR: any file with that extension
            # would "match", so a hit proves nothing and a miss proves nothing either. Binary
            # structural rule, no tunable threshold - and it catches a brace-laundering attempt
            # (a mandate written with zero literal content specifically to dodge the phantom
            # check) as visibly as it catches an honest fully-generic pattern.
            basename = os.path.basename(tok.replace("\\", "/"))
            stem, _ext = os.path.splitext(basename)
            literal_remainder = PLACEHOLDER_RE.sub("", stem).replace("*", "").replace("?", "")
            unverifiable = in_scope and literal_remainder == ""
            unverifiable_reason = (
                "expanded basename has no literal character beyond the extension"
                if unverifiable else None
            )

            # PHANTOM, redefined: zero matching instances anywhere, for literal and templated
            # mandates alike. A templated mandate that DOES match something is not phantom - it
            # is "checked by pattern", weaker evidence than a literal hit, but it is evidence -
            # and a templated mandate with ZERO matches is STILL phantom. Unverifiable mandates
            # are excluded here entirely: there was nothing to check, so calling the outcome
            # "phantom" would claim a check that never happened.
            phantom = in_scope and not unverifiable and match_count == 0

            res.append(dict(
                skill=r["skill"], artifact=tok,
                in_tree=hit_tree, in_history=hit_hist,
                in_scope=in_scope, out_of_scope_reason=reason, out_of_scope_class=reason_class,
                templated=templated, match_count=match_count,
                unverifiable_pattern=unverifiable, unverifiable_reason=unverifiable_reason,
                phantom=phantom,
            ))
    return res, shallow, bool(gr), len(tree | hist)


def build_exclusion_ledger(arts, length_cap_total):
    """The disclosure ledger (council ruling #3, non-negotiable): every exclusion reason-class
    this tool applies, with its FULL count - never a sample. Two kinds of exclusion feed it:

      - every OUT-OF-SCOPE artifact in `arts`, keyed by its own `out_of_scope_class`
        (scaffold-scope / user-scope / prefix-missing / declared-scope);
      - every IN-SCOPE but `unverifiable_pattern` artifact in `arts`, keyed "unverifiable_pattern";

    plus one class that never reaches `arts` at all: `length_cap_total`, the count of mandated
    tokens analyse() dropped for being too long to be a plausible real path (see its
    `length_cap_dropped` counter) before check_artifacts() ever ran - there is no per-artifact
    record for those, only a total.
    """
    ledger = {}
    for x in arts:
        if not x["in_scope"]:
            cls = x.get("out_of_scope_class") or "unspecified"
            ledger[cls] = ledger.get(cls, 0) + 1
        elif x.get("unverifiable_pattern"):
            ledger["unverifiable_pattern"] = ledger.get("unverifiable_pattern", 0) + 1
    if length_cap_total:
        ledger["length-cap"] = length_cap_total
    return ledger


def phantom_counterfactual(arts):
    """The two phantom rates side by side, so the scope/unverifiable filtering's own effect on
    the headline number is never silent (council ruling #3):

      in_scope_pct / in_scope_n   the rate this tool has always reported: in-scope, VERIFIABLE
                                   artifacts only (excludes unverifiable_pattern too - the same
                                   `ver` set the headline "PHANTOM, in-scope" line uses).
      all_pct / all_n             the counterfactual: what the rate would be if every excluded
                                   artifact were simply counted instead, using each one's own
                                   already-computed match_count==0 as "phantom" - no new
                                   evidence gathered, just the exclusions undone. Artifacts that
                                   never reached `arts` at all (the length-cap drops) cannot be
                                   included here - there is no match_count for a token that was
                                   never searched for - so this counterfactual is itself a floor,
                                   not the true "everything" number; the ledger's separate
                                   length-cap count discloses that gap rather than hiding it.
    """
    ver = [x for x in arts if x["in_scope"] and not x["unverifiable_pattern"]]
    in_scope_n = len(ver)
    in_scope_phantom = len([x for x in ver if x["phantom"]])
    in_scope_pct = (100.0 * in_scope_phantom / in_scope_n) if in_scope_n else 0.0

    all_n = len(arts)
    all_phantom = len([x for x in arts if x["match_count"] == 0])
    all_pct = (100.0 * all_phantom / all_n) if all_n else 0.0

    return dict(in_scope_pct=round(in_scope_pct, 1), in_scope_n=in_scope_n,
                all_pct=round(all_pct, 1), all_n=all_n)


def main():
    ap = argparse.ArgumentParser(prog="python -m kibsu audit", description="Measure the checkable:claimable ratio of an agent skill set.")
    ap.add_argument("path")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--definitions", action="store_true")
    ap.add_argument("--artifacts", action="store_true", help="find mandated artifacts and hunt for them")
    ap.add_argument("--limit", type=int, default=12)
    ap.add_argument("--include-archived", action="store_true")
    a = ap.parse_args()
    global INCLUDE_ARCHIVED
    INCLUDE_ARCHIVED = a.include_archived
    if a.definitions:
        print(DEFINITIONS)

    root = os.path.abspath(a.path)
    files, mode = find_skills(root)
    if not files:
        print("no .md found under " + root)
        return 1
    rows = []
    for p in sorted(files):
        try:
            if os.path.getsize(p) > MAX_READ_BYTES:
                sys.stderr.write("kibsu audit: skipping %s (%d bytes > %d byte ceiling)\n"
                                 % (p, os.path.getsize(p), MAX_READ_BYTES))
                continue
            t = io.open(p, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        r = analyse(t)
        rel = os.path.relpath(p, root).replace("\\", "/")
        r["skill"] = (os.path.dirname(rel) or rel) if mode == "SKILL.md" else rel
        rows.append(r)

    def agg(rs):
        t = {k: sum(r[k] for r in rs) for k in ("lines", "instructions", "checkable", "claimable",
                                                "runnable_fences", "checkboxes")}
        t["units"] = len(rs)
        t["pct"] = (100.0 * t["checkable"] / t["instructions"]) if t["instructions"] else 0.0
        t["zero"] = len([r for r in rs if r["checkable"] == 0 and r["instructions"] > 0])
        return t

    ALL, PROC = agg(rows), agg([r for r in rows if r["genre"] == "procedure"])
    by_genre = {}
    for g in ("procedure", "doctrine", "persona", "reference", "mixed"):
        sub = [r for r in rows if r["genre"] == g]
        if sub:
            by_genre[g] = agg(sub)

    arts, shallow, has_git, _ = ([], False, False, 0)
    ledger, counterfactual = {}, None
    if a.artifacts:
        arts, shallow, has_git, _ = check_artifacts(root, rows)
        length_cap_total = sum(r.get("length_cap_dropped", 0) for r in rows)
        ledger = build_exclusion_ledger(arts, length_cap_total)
        counterfactual = phantom_counterfactual(arts)

    if a.json:
        print(json.dumps(dict(version=VERSION, root=root, mode=mode, all=ALL, procedure_only=PROC,
                              by_genre=by_genre, artifacts=arts, history_shallow=shallow,
                              has_git=has_git, skills=rows, exclusion_ledger=ledger,
                              phantom_counterfactual=counterfactual), indent=2))
        return 0

    print("\nkibsu audit (scorer %s)   %s" % (VERSION, root))
    print("  %d units (%s), %s lines\n" % (ALL["units"], mode, format(ALL["lines"], ",")))
    print("  %-11s %6s %8s %8s %8s %9s" % ("genre", "units", "instr", "check", "CHECK%", "0-check"))
    for g in ("procedure", "doctrine", "persona", "reference", "mixed"):
        if g in by_genre:
            t = by_genre[g]
            print("  %-11s %6d %8s %8s %7.1f%% %6d/%-3d" % (g, t["units"], format(t["instructions"], ","),
                  format(t["checkable"], ","), t["pct"], t["zero"], t["units"]))
    print("  " + "-" * 56)
    print("  %-11s %6d %8s %8s %7.1f%% %6d/%-3d" % ("ALL", ALL["units"], format(ALL["instructions"], ","),
          format(ALL["checkable"], ","), ALL["pct"], ALL["zero"], ALL["units"]))
    print("\n  >> HEADLINE (procedure units only - the fair comparison): %.1f%% checkable"
          % PROC["pct"] if PROC["units"] else "\n  >> no procedure-genre units found")

    # A declared genre must never quietly buy a better score, so detection still runs and any
    # disagreement is printed. Silent trust would make the declaration a loophole.
    dec = [r for r in rows if r.get("genre_source") == "declared"]
    conf = [r for r in dec if r.get("genre_conflict")]
    if dec:
        print("\n  genre declared in frontmatter: %d unit(s), %d disagreeing with detection"
              % (len(dec), len(conf)))
        for r in conf[:6]:
            print("     %-32s declared=%-9s detected=%s"
                  % (r["skill"][:32], r["genre"], r["genre_detected"]))

    if a.artifacts:
        print("\n  --- mandated artifacts ---")
        if not has_git:
            print("    not a git repo: history check unavailable (tree only)")
        elif shallow:
            print("    SHALLOW CLONE: git history unavailable. 'never existed' cannot be established;")
            print("    phantom counts below are UNKNOWN, not zero. Re-clone with full history to use this.")
        inn = [x for x in arts if x["in_scope"]]
        out = [x for x in arts if not x["in_scope"]]
        # unverifiable_pattern mandates are in-scope but carry no literal content to check - they
        # are excluded from BOTH the phantom numerator and denominator, per --definitions.
        unver = [x for x in inn if x["unverifiable_pattern"]]
        ver = [x for x in inn if not x["unverifiable_pattern"]]
        ph = [x for x in ver if x["phantom"]]
        ver_templated = [x for x in ver if x["templated"]]
        print("    %d references, %d distinct" % (len(arts), len({x["artifact"] for x in arts})))
        print("    in-scope (claimed to live in THIS repo): %d   out-of-scope: %d" % (len(inn), len(out)))
        if unver:
            print("    unverifiable_pattern (no literal char beyond the extension - excluded from "
                  "phantom numerator AND denominator): %d" % len(unver))
            for x in unver[:a.limit]:
                print("      %-34s  mandated by %s  (%s)"
                      % (x["artifact"][:34], x["skill"][:40], x["unverifiable_reason"]))
        # DISCLOSURE LEDGER (council ruling #3): every exclusion reason-class, FULL count - not
        # a sample, and not limited by --limit the way the per-reason lists above are. Printed
        # unconditionally (unlike the phantom rate below) because it is about the scope/length
        # filters this tool applies, not about git-history evidence.
        if ledger:
            print("    exclusion ledger (every reason-class, full count - not a sample):")
            for cls in sorted(ledger):
                print("      %s: %d" % (cls, ledger[cls]))
        if has_git and not shallow:
            print("    PHANTOM, in-scope (0 instances in tree or any commit): %d of %d  "
                  "(%d of them templated, checked by pattern)" % (len(ph), len(ver), len(ver_templated)))
            for x in ph[:a.limit]:
                tag = "  [templated - checked by pattern]" if x["templated"] else ""
                print("      %-34s  mandated by %s%s" % (x["artifact"][:34], x["skill"][:40], tag))
            if out:
                # "out" aggregates every exclusion class (scaffold-scope, user-scope,
                # prefix-missing, declared-scope), not just the original user-project reason -
                # the header must say so, or the per-class ledger above gets contradicted by
                # its own sample listing's title.
                print("    excluded from the phantom check (%d, all classes - see ledger), sample:" % len(out))
                for x in out[:3]:
                    print("      %-30s  [%s] %s"
                          % (x["artifact"][:30], x.get("out_of_scope_class") or "?",
                             x["out_of_scope_reason"][:50]))
            if counterfactual:
                # No denominator surgery is silent (council ruling #3): the rate this tool has
                # always reported (in-scope, verifiable artifacts only) right next to what it
                # would read if every exclusion were simply counted instead.
                print("    phantom rate: %.1f%% in-scope-only (%d artifacts) / %.1f%% if all "
                      "exclusions are counted (%d artifacts)"
                      % (counterfactual["in_scope_pct"], counterfactual["in_scope_n"],
                         counterfactual["all_pct"], counterfactual["all_n"]))
        elif arts:
            print("    history unavailable - phantom status UNKNOWN, not zero")

    worst = sorted([r for r in rows if r["instructions"] >= 5 and r["genre"] == "procedure"],
                   key=lambda r: (r["checkable"] / r["instructions"], -r["instructions"]))[:a.limit]
    if worst:
        print("\n  most claimable PROCEDURE units (>=5 instructions):")
        for r in worst:
            print("    %-44s %5d instr %5d check %4.0f%%" % (r["skill"][:44], r["instructions"],
                  r["checkable"], 100.0 * r["checkable"] / r["instructions"]))
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
