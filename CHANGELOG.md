# Changelog

## 0.5.0 - 2026-08-28

An audit of this project against its own standard, and the fixes it produced. Twenty candidate
findings went through an adversarial pass instructed to refute rather than confirm; two fell.
Seven of the survivors ship here, every one of them a case of kibsu asserting something it could
not back - which is the exact failure this tool exists to name in other people's repositories.

The scorer is untouched - still 0.6.0 - so **NO published figure moves in this release**. The
survey table, the median, and every number in the README were re-derived from the pinned SHAs
before any code was written, not asserted afterwards. Minor version, not patch: four changes are
observable to consumers - the installed gate hook now chains a carried pre-existing pre-commit,
`discover`'s gate classifier answers differently (so `guide`'s ENFORCED/ON-YOU verdicts move),
`report` measures a repo layout it used to abstain on, and `audit` gains an `instruction-files`
discovery mode.

Two of these are security fixes. Anyone running 0.4.0 against a repository they did not write
should upgrade.

- **SECURITY. Fixed #59-class: `install --uninstall` could delete files anywhere on the disk.**
  The delete list was built with a bare `os.path.join(root, declared)` over paths recorded in
  `.kibsu/install.json`. That call DISCARDS root entirely when the declared path is absolute, and
  a `../../..` prefix simply walks out. install.json is read off the disk of the repo being
  operated on, and kibsu is pointed at repos it did not author - the survey clones ten - so that
  record is untrusted input. Paths are now resolved and required to sit inside the repo;
  out-of-tree entries are skipped and named on stderr, never silently.

- **SECURITY. Fixed #65-class: a scan could read files outside the repo through a symlink.**
  `os.walk` does not descend directory links, but a symlinked FILE is followed by `open()` like
  any other and git tracks it as mode 120000. Measured: a repo carrying `leak.md -> <outside>`
  had that file's frontmatter copied verbatim into `idx.json` AND its key promoted into the
  derived taxonomy - a committed artifact carrying content from outside the repository. `index`
  and `audit` now resolve each path and skip, loudly, anything that leaves the tree. An in-repo
  link is still read: the guard is about escaping the tree, not about links being suspicious.

- **Fixed #60-class: the gate could be talked out of a finding by the wording of its own message.**
  `is_ignored_violation()` asked whether ANY path-shaped substring anywhere in a violation's text
  was gitignored. An ordinary see-also reference therefore excused the finding: a real, new
  violation in a fully tracked file vanished because its description mentioned an ignored path,
  and the gate printed `PASS` and allowed the commit. A gate that can be argued out of a finding
  is the worst defect this project can carry. Judgement is now the violation's declared subject -
  the path the item leads with, per the shared gate contract. The behaviour `ignored()` was built
  for is unaffected: a finding whose SUBJECT is gitignored is still skipped, and a test pins it.

- **Fixed #62-class: `gate --install` orphaned a pre-existing pre-commit hook.** Setting
  `core.hooksPath` makes git stop reading `.git/hooks` entirely. install.py was fixed for that in
  #33; gate.py never was - it computed the same list and used it only to print a warning. A repo
  whose hook blocked commits carrying secrets would, after this file's own documented one-liner,
  commit them silently. The hook is now carried as `pre-commit.carried` and exec'd first, its
  failure still blocking. Uninstall re-derives what it carried and claims a file only when it is
  provably a copy - an uninstall removing a file it did not write would be the same damage.

- **Fixed #63-class: a forced re-install lost the hooksPath that predates kibsu.**
  `previous_hookspath` was captured from what is set right now, which after a first install is
  kibsu's own directory - so `--install --force` recorded ours, and `--uninstall` then "restored"
  `core.hooksPath` to a directory whose hook it had just deleted. The user's setting was gone and
  NO hooks ran, neither theirs nor kibsu's. The prior record is now carried forward, but only when
  the current value is in fact ours; a path set since install is still recorded as a real one.

- **Fixed #64-class: `guide` reported ENFORCED for gates that nothing runs.** The classifier used
  bare substring containment on filenames - `lint.py` is inside `pylint.py`, `check.py` inside
  `spellcheck.py`, and a commented-out mention matched too. This one is worse than its inverse: a
  missed gate reads as ON YOU and you go check it, while a phantom gate reads as handled and you
  stop looking. A script name must now appear as a whole path component.

- **Fixed #61-class: the first run could not see a root `AGENTS.md`.** `find_skills_dir()` only
  ever probed for directories, so a repo whose entire agent contract is the layout this README
  names in its second sentence - and that `config.DEFAULTS` has always declared - was told "no
  agent-instruction directory found. Nothing here tells agents how to work." `find_skills()` gains
  an `instruction-files` mode, placed BELOW both directory modes so no existing measurement
  changes; at the ten pinned SHAs the two repos that land in the catch-all carry no root
  instruction file, checked against the git trees before the code was written.

- Fixed #29 structurally: the README's "count it yourself" paragraph is now enforced by the suite -
  `tests/test_readme_counts.py` runs the paragraph's own commands (same glob, same splitlines, the
  same discovery count `unittest discover` prints) and fails while the prose disagrees. The counts
  had drifted a FOURTH time in the nine days after #29 was filed, while every other finding was
  being fixed - the class does not die by diligence, only by machine. The specific figures are
  deliberately NOT repeated here: a changelog is history, and a number that has to track HEAD
  belongs on the enforced surface, not in an entry that can never be re-checked.

- The CORRECTIONS.md index is enforced rather than promised - a swallowed correction round now
  fails the suite (#58) - and the 0.2.0 round got its heading back, which an earlier edit had
  written over rather than above.

- CI actions bumped across the board (#57).

## 0.4.0 - 2026-08-15

The 2026-08-07 review's confirmed-findings ledger, closed: every high and medium shipped
across five PRs plus the project's first outside code contribution (#40, merged from
@Partharsid; #36's fix from @HeaTTap follows when its Windows test fixture lands). The
scorer is untouched - still 0.6.0 - so NO published figure moves in this release; every
change below is behavioral. Minor version, not patch: three changes are observable to
consumers - discover's JSON gains a machine-readable `scripts` map, the installed
pre-commit template changed (it now chains a carried pre-existing hook), and the gate's
identity acceptance is a multiset (a surplus occurrence of an accepted violation now
blocks, as the docstring always promised).

- Fixed #39: every scan-path read carries a 5 MB per-file ceiling (MAX_READ_BYTES) checked
  before the read - a scanned repo git-tracking a multi-gigabyte markdown file no longer
  triggers an unbounded whole-file read (the realistic failure being the OOM-killer's
  SIGKILL, which no except clause sees). Over-ceiling files are skipped with a printed
  reason on stderr, never silently; learn.py's read - the one with no try/except at all -
  is guarded both ways.
- Fixed #33: install carries a pre-existing pre-commit hook as `pre-commit.carried` and the
  generated hook execs it FIRST - its logic keeps firing and its failure keeps blocking,
  exactly as before kibsu arrived. It used to be excluded from the carry list outright,
  silently disabled the moment core.hooksPath redirected git, while the module docstring
  promised "nothing is silently disabled". The docstring now describes the chain, the
  dry-run preview announces it, and install.json records it.
- Fixed #32: discover's Mandated-gates capability carries a machine-readable `scripts`
  map ({script: live|monitored|unenforced}) and guide's buckets() consumes it instead of
  regexing prose - a schedule-only gate now reads MONITORED ("still on you before a
  commit"), never ENFORCED. Unclassified scripts default to the SAFE reading (ON YOU); the
  prose parse survives only as a fallback for older discover JSON.
- Fixed #35: the hook indirection resolver probes a `$VAR` path's variable-stripped,
  root-relative remainder before its bare basename - kibsu's own installed-hook idiom
  (`$ROOT/.kibsu/bin/check.py`) is followed, so a genuinely-enforced gate no longer reads
  INERT on the tool's own primary layout.
- Fixed #30: the headline "in-scope mandated artifacts" aggregate applies the same
  unusable-history guard its counterfactual sibling always had - a shallow-history repo's
  mandates no longer pad the denominator while contributing nothing to the numerator. No
  published figure moves: at the pinned SHAs every ranked repo has usable history.
- Fixed #34: the printed "genre mix" census includes doctrine - all five genres, not four.
  The test that previously PINNED the buggy output now asserts the honest one.

- Fixed #31: gate identity acceptance is a MULTISET. Two distinct violations that digit-fold
  to the same identity are two accepted occurrences, and a third occurrence of that identity
  now BLOCKS - it used to pass silently, the exact case the gate's own docstring promised to
  catch. No baseline schema change and no migration: the accepted list on disk always carried
  the duplicates; only the in-memory set() collapsed them. The blocked report names the
  arithmetic ("3 occurrence(s) now, 2 accepted"), and the FIXED tally now counts occurrences.

## 0.3.0 - 2026-08-07

Three scorer corrections (audit.py, scorer 0.5.0 -> 0.6.0, PR #42: issues #26/#27/#28), the
survey re-measured at the same pinned SHAs, `evidence/` regenerated, both PREREGISTRATION
baselines re-measured per that file's own standing clause, and every number that moved is
indexed in [CORRECTIONS.md](CORRECTIONS.md) (2026-08-07 entry). This round the headline
median moved: 11.1% -> 9.4%, because case-insensitive MODALS grew instruction counts ~17%
across every ranked collection. Ablation runs attribute every moved number to #26 alone;
#27 and #28 are real bugs with nothing to bite at these pins. README's pasted report sample
re-run and re-pasted (third time, recorded in place); report.py's PEER_MEDIAN follows the
new median.

- Fixed #26: MODALS compiles with re.IGNORECASE; Title-case directives count.
- Fixed #27: check_artifacts() records every ancestor directory, not just immediate parents.
- Fixed #28: strip_frontmatter() strips a UTF-8 BOM, as index.py already did.

Minor version, not patch, same reasoning as 0.2.0: no API change, but the scorer's judgments
and every published figure move, so anyone comparing numbers across versions sees a
difference that is the instrument's, not their repo's.

## 0.2.1 - 2026-08-01

One character. `glob_re()`'s docstring quotes the `\*` / `\?` escape sequences it explains,
inside a non-raw string - Python 3.12+ raises SyntaxWarning on every fresh compile, so
pip-installing 0.2.0 printed a warning at the user. The docstring is raw now; it documents
escaping and finally practices it. Found minutes after the 0.2.0 release by upgrading the
local install - the first 0.2.0 user was its own maintainer.

## 0.2.0 - 2026-07-31

Five scorer bugs fixed (audit.py, scorer 0.3.0 -> 0.5.0), the survey re-measured at the same
pinned SHAs, `evidence/` regenerated, and every number that moved is indexed in
[CORRECTIONS.md](CORRECTIONS.md) - new in this release - along with each bug's bias
direction. Minor version, not patch: the evidence JSON schema gained fields (`templated`,
`match_count`, `unverifiable_pattern`, the per-class exclusion ledger) and the phantom
definition changed (zero instances anywhere, for literal and templated mandates alike), so
consumers of the output see a difference. The headline median did not move (11.1%); the
aggregate phantom line did (103 mandates / 44 phantom / 43% -> 134 / 56 / 42%).

- Fixed #13: fence tracking records delimiter char, run length, and info string; a fence
  closes only on a bare, same-char, >=length line (CommonMark 4.5). `~~~` fences recognized.
  Fenced examples containing fences no longer leak instructions or flip genre.
- Fixed #14: `{placeholder}` segments in mandated paths expand like `*` (in the directory
  prefix too, so a brace in a folder name is no longer dropped as "path prefix does not
  exist"), phantom is redefined as zero instances anywhere (`match_count == 0`), and a
  mandate whose expanded basename keeps no literal characters lands in a new
  `unverifiable_pattern` bucket - in neither the phantom numerator nor denominator, always
  reported with its count. The previously undocumented `*`/`?` expansion is now disclosed
  in `--definitions`.
- `FILE_TOKEN`/`PATHY` gained `re.IGNORECASE` (`NOTES.MD` is the same mandate as
  `notes.md`); `FILE_TOKEN` also learned `.tsx`/`.jsx`.
- The scaffold-scope exclusion moved from unit level (one keyword near the top removed
  every artifact the unit mandated) to the mandate's own line, requiring keyword +
  user-scope language co-occurrence with a negation guard; a frontmatter
  `scope: user-project|repo` declaration overrides the heuristic in both directions. Every
  exclusion class now reports full counts (never samples) plus a with/without-exclusions
  counterfactual phantom rate, and the old bracket label that named one class for all of
  them is gone.
- Hook hardening (both installed hook templates): the interpreter is validated before it
  is trusted - Windows' App Execution Alias stub used to satisfy `command -v` and either
  blocked every commit (gate) or silently passed with a Microsoft Store message (install);
  candidates now prove themselves with `-c "import sys"` first, `py -3` joins the chain,
  and an unexpected checker exit prints a branded "commit ALLOWED, nothing was verified"
  instead of silence.
- `check`'s baseline exclude-globs use `fnmatchcase`: the same baseline no longer excludes
  different files on Windows vs Linux/macOS.
- `index` refuses a nonexistent path (exit 3) instead of creating the directory and
  reporting a clean, empty, fabricated success.
- The hook end-to-end tests prove WHICH vendored copy ran (byte-compare against source)
  instead of asserting kibsu is not importable - the suite now passes on machines where
  kibsu is pip-installed, i.e. any contributor's.
- `kibsu --version` prints both versions: `kibsu 0.2.0 (scorer 0.5.0)`.

## 0.1.1 - 2026-07-29

Fixed #2: `check --backtest-mode existence` scoped its "touched a watched .md" filter to
`dirname(index_path)` instead of the configured `docs_root` (+ `skills_dir` + `instruction_files`),
so a repo using kibsu's own default config (`index_path=".kibsu/index.json"`, `docs_root="docs"`)
always replayed 0 eligible commits and `report`'s HISTORY check (question 5) always rendered
COULD NOT CHECK.

## 0.1.0 - 2026-07-26

Initial release.
