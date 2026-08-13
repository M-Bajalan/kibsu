# Changelog

## Unreleased

- Fixed #33: install carries a pre-existing pre-commit hook as `pre-commit.carried` and the
  generated hook execs it FIRST - its logic keeps firing and its failure keeps blocking,
  exactly as before kibsu arrived. It used to be excluded from the carry list outright,
  silently disabled the moment core.hooksPath redirected git, while the module docstring
  promised "nothing is silently disabled". The docstring now describes the chain, the
  dry-run preview announces it, and install.json records it.
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
