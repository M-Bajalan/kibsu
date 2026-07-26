#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
skill-audit v0.3.0 - how much of an agent instruction set can actually be checked?

An instruction is CHECKABLE if a reviewer could tell from the repo alone whether it happened: it
runs a command, produces or edits a named file, or is a tick-box. It is CLAIMABLE if the only
evidence is the agent saying so.

v0.3.0 adds the DOCTRINE genre. v0.2.0 added the rest.
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
import argparse, io, json, os, re, subprocess, sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

VERSION = "0.3.0"
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
PATHY = re.compile(r"[`\"']?[\w./\\*-]+\.(?:md|json|ya?ml|py|ps1|sh|js|ts|tsx|jsx|sql|toml|ini|cfg|txt|csv|lock)\b")
EXITY = re.compile(r"\b(exit code|exit 0|exit 1|non-zero|returns? 0|must pass|passes|green|fails? loud|"
                   r"assert|verify that|diff|git status|git log|numstat)\b", re.I)
MODALS = re.compile(r"\b(MUST|SHOULD|ALWAYS|NEVER|REQUIRED|DO NOT|DON'T|MANDATORY|"
                    r"must|never|always|do not|don't|ensure|make sure)\b")
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
    r"stamp|bump|export)\w*\b", re.I)
FILE_TOKEN = re.compile(
    r"`([^`\s]*?[\w*\[\]{}-]+\.(?:md|json|ya?ml|py|ps1|sh|js|ts|sql|toml|ini|cfg|txt|csv))`")

# --- phantom-scope filters (fix for the false-positive class) --------------------------------
# A mandated artifact only counts as a PHANTOM if the skill claims it is produced INSIDE the repo
# the skill lives in. Skills that scaffold the *user's* project legitimately name files that will
# never exist here, and scoring them was wrong.
SCAFFOLD_SKILL = re.compile(
    r"\b(scaffold|boilerplate|starter|template|generator|generate a new|create a new project|"
    r"new project|project init|bootstrap a)\w*\b", re.I)
USER_SCOPE_LINE = re.compile(
    r"\b(your|the user'?s?|target|destination|output|new)\s+"
    r"(project|repo(sitory)?|app|application|codebase|directory|folder)\b|"
    r"\bin your\b|\bfor the user\b|\bthe generated\b", re.I)

DEFINITIONS = """
METRIC DEFINITIONS (contest them - that is the point)

  instruction  a non-heading, non-code line telling the agent to do something: opens with an
               imperative verb, or carries a modal (MUST / NEVER / ALWAYS / DO NOT / ensure).

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

  phantom      an artifact a skill mandates that has never existed in the working tree OR in git
               history. Requires full history; a shallow clone reports UNKNOWN, never zero.

  BIAS         ambiguity resolves to CHECKABLE. Reported ratios are ceilings.
"""


def strip_frontmatter(t):
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
    lines = body.split("\n")
    o = dict(lines=len(lines), fences=0, runnable_fences=0, checkboxes=0, instructions=0,
             checkable=0, claimable=0, inline_cmds=0, steps=0, seq=0, tables=0,
             persona_hits=0, doctrine_hits=0, epistemic=0, action=0, mandated=[])
    if any(r.search(fm) for r in PERSONA_RE):
        o["persona_hits"] += 2
    in_fence, lang = False, ""
    for ln in lines:
        f = re.match(r"^\s*```+\s*([\w+-]*)", ln)
        if f:
            if not in_fence:
                in_fence, lang = True, (f.group(1) or "").lower()
                o["fences"] += 1
                if lang in RUNNABLE_LANGS:
                    o["runnable_fences"] += 1
            else:
                in_fence, lang = False, ""
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
    seen = set()
    uniq = []
    for m in o["mandated"]:
        if m["tok"] not in seen:
            seen.add(m["tok"]); uniq.append(m)
    o["mandated"] = uniq
    o["scaffolding"] = bool(SCAFFOLD_SKILL.search(fm) or SCAFFOLD_SKILL.search(body[:1500]))
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
    ok = lambda f: f.lower().endswith(".md") and os.path.splitext(f)[0].lower() not in META
    parts = lambda dp: {p.lower() for p in os.path.relpath(dp, root).replace("\\", "/").split("/")}
    hits = [os.path.join(dp, f) for dp, fn in _walk(root) for f in fn if ok(f) and (parts(dp) & INSTR_DIRS)]
    if hits:
        return hits, "instruction-dir/*.md"
    return [os.path.join(dp, f) for dp, fn in _walk(root) for f in fn if ok(f)], "*.md (no instruction dir)"


# ---- artifacts ----------------------------------------------------------------------------
def git_root(path):
    p = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=path,
                       capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 else None


def history_paths(root):
    """All paths ever touched, plus whether history is shallow (which makes zero meaningless)."""
    shallow = os.path.isfile(os.path.join(root, ".git", "shallow"))
    p = subprocess.run(["git", "log", "--all", "--pretty=format:", "--name-only"], cwd=root,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    paths = {l.strip() for l in p.stdout.split("\n") if l.strip()} if p.returncode == 0 else set()
    return paths, shallow


def tree_paths(root):
    out = set()
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d != ".git"]
        for f in fn:
            out.add(os.path.relpath(os.path.join(dp, f), root).replace("\\", "/"))
    return out


def glob_re(tok):
    esc = re.escape(tok).replace(r"\*", "[^/]*").replace(r"\?", ".")
    return re.compile(r"(^|/)" + esc + r"$", re.I)


def check_artifacts(root, rows):
    gr = git_root(root)
    hist, shallow = (history_paths(gr) if gr else (set(), False))
    tree = tree_paths(gr or root)
    dirs = {os.path.dirname(p) for p in (tree | hist)}
    dirs.discard("")
    res = []
    for r in rows:
        for m in r["mandated"]:
            tok, line = m["tok"], m["line"]
            # --- scope filter: is this artifact claimed to live in THIS repo? ---
            reason = None
            if r.get("scaffolding"):
                reason = "skill scaffolds the user's project"
            elif USER_SCOPE_LINE.search(line):
                reason = "line refers to the user's project, not this repo"
            else:
                pre = os.path.dirname(tok.replace("\\", "/"))
                if pre and not any(d == pre or d.endswith("/" + pre) for d in dirs):
                    reason = "path prefix '%s/' does not exist in this repo" % pre
            rx = glob_re(tok)
            hit_tree = any(rx.search(p) for p in tree)
            hit_hist = any(rx.search(p) for p in hist)
            res.append(dict(skill=r["skill"], artifact=tok, in_tree=hit_tree, in_history=hit_hist,
                            in_scope=(reason is None), out_of_scope_reason=reason,
                            phantom=(reason is None and not hit_tree and not hit_hist)))
    return res, shallow, bool(gr), len(tree | hist)


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
    if a.artifacts:
        arts, shallow, has_git, _ = check_artifacts(root, rows)

    if a.json:
        print(json.dumps(dict(version=VERSION, root=root, mode=mode, all=ALL, procedure_only=PROC,
                              by_genre=by_genre, artifacts=arts, history_shallow=shallow,
                              has_git=has_git, skills=rows), indent=2))
        return 0

    print("\nskill-audit v%s   %s" % (VERSION, root))
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
        ph = [x for x in inn if x["phantom"]]
        print("    %d references, %d distinct" % (len(arts), len({x["artifact"] for x in arts})))
        print("    in-scope (claimed to live in THIS repo): %d   out-of-scope: %d" % (len(inn), len(out)))
        if has_git and not shallow:
            print("    PHANTOM, in-scope (never in tree, never in any commit): %d of %d  (%.0f%%)"
                  % (len(ph), len(inn), 100.0 * len(ph) / max(1, len(inn))))
            for x in ph[:a.limit]:
                print("      %-34s  mandated by %s" % (x["artifact"][:34], x["skill"][:40]))
            if out:
                print("    excluded as user-project scope (%d), sample:" % len(out))
                for x in out[:3]:
                    print("      %-30s  %s" % (x["artifact"][:30], x["out_of_scope_reason"][:56]))
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
