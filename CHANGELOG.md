# Changelog

## Unreleased

- **Scorer 0.12.0: five places a soft line break still moved a count** (#113, CORRECTIONS
  2026-10-14). The 0.10.0 entry below says "Where a soft line break falls no longer
  changes a number." In five places that was false. In each, the reader took a
  continuation line for the start of a block where CommonMark does not:
  - a number inside a list item;
  - an escaped backslash at a line end;
  - a bullet four columns past an item's text;
  - a `|`-led line with no delimiter row;
  - a list after a quote inside an item.
  The property test had refused the wraps that showed the first; it now refuses only what
  CommonMark refuses.
  **Re-measured at the pinned SHAs: no published figure moves.** 14 of the 6,490 Markdown
  files in the ten pinned repositories read differently. None is a surveyed unit, and
  none changes an instruction count. `evidence/` changes only its scorer version.
  `report`'s public median stays 7.6, now labelled scorer 0.12.0. The private origin
  workspace of the pre-registration still has to be re-measured before release
  (PREREGISTRATION, 2026-10-14 note).
  **Observable to consumers:** `audit --json` reports version 0.12.0. For a file written
  in one of the five shapes, `steps`, `logical_lines` and the detected genre can change.

## 0.10.0 - 2026-10-11

The sentence round (CORRECTIONS 2026-10-11), and the command that found it. This package
carries **scorer 0.11.0** - the two numbering lines are easy to cross: scorer 0.10.0 shipped
in package 0.9.0. Minor version, not patch, because three changes are observable to
consumers: every percentage `audit`, `report` and `explain` print can change for the same
repository at the same commit (the scorer counts sentences, not lines); `report` compares
against a public median of 7.6% instead of 7.5%; and there is a new command, `kibsu explain`.

- **Scorer 0.11.0: what is counted is the sentence, not the line** (CORRECTIONS
  2026-10-11). Through 0.10.0 a sentence hard-wrapped over three lines was scored once per
  line that carried a directive word, and a line holding three sentences was scored once,
  so a file's score moved when it was re-wrapped. The document is now read the way Markdown
  renders it - the lines of a paragraph, list item or blockquote joined, by CommonMark's own
  rules for what may end a paragraph - and every signal, genre included, is computed from
  that. Each block is then cut into sentences, and a mandated file is read from one
  sentence, not one line. A tick-box item counts once.
  **Every published figure was re-measured at the same pinned SHAs.** The median moves
  7.5% -> 7.6%; single collections move by up to 1.6 points in both directions (hard-wrapped
  prose had been scored too low, long lines too high); in-scope mandated artifacts go
  229 -> 172 and never-existed 96 -> 75, with every mention that left or arrived classified
  by hand in CORRECTIONS. `evidence/` is regenerated, `report`'s public median is 7.6
  (scorer 0.11.0), and PREREGISTRATION carries the re-measured column.
  **Observable to consumers:** every percentage `audit`, `report` and `explain` print can
  change for the same repository at the same commit; `audit --json` gains `logical_lines`
  per unit, and `--lines` records gain `end_line`. The limit this corrects was disclosed in
  the README the day `explain` showed it, before it was fixed.
- **Where a soft line break falls no longer changes a number.** `tests/test_sentences.py`
  holds it as a property over described documents at 29 widths, with a control showing a
  line count does move on the same fixtures. The first draft's property test passed and was
  wrong; an adversarial pass with an independent CommonMark parser as oracle found six ways
  a re-wrap changed a count, and the reader was rewritten to the spec's interruption rules.
  Two places side with the file's reader against the renderer, on purpose and tested: a
  fence on the line under a tag is a fence, and a pipe table with a ragged delimiter row is
  a table.
- **The sentence scan is linear.** The draft's splitter went quadratic and its code-span
  pattern cubic - one hostile line could hold a scan for minutes. Both are single passes
  now, with timing tests.
- **`explain` says "instruction", and lists whole sentences.** Its entries were physical
  lines, fragments included; they are sentences now, shown at the line they start on. The
  wording follows: `N instruction(s) can only be confirmed...`.
- **A README sentence its own evidence had stopped supporting** ("Three of the eight mandate
  zero artifacts") reads one of eight, and the survey table says what `—` means.
- **`kibsu explain` - the lines behind the percentage.** `report` says "47.8% of your
  procedural instructions are verifiable" and stops; `explain` lists the lines that make up
  the rest, as `path:line  text`. Read-only. Only procedure units are listed by default - a
  doctrine unit's 0% is the genre working, and its lines are not a to-do list - with the
  units held back counted in the output. `--unit TEXT` narrows to one file, `--all-genres`
  and `--full` lift the two limits, `--json` carries every instruction with both verdicts
  and the reason for each.
- **The list and the percentage are decided by one function.** `audit.checkable_because()`
  is the single place a verdict is made; `analyse()` counts from it and
  `audit --json --lines` reports from it. At three pinned repositories (kibsu-lab `2d49abf`,
  obra/superpowers `3dcbd5c`, wshobson/agents `c4b82b0`) the entries `explain` lists equal
  the gap in the headline exactly: 19, 306 and 1,412.

## 0.9.0 - 2026-10-11

The front-door round (CORRECTIONS 2026-10-10): the published 0.8.0 was installed into an
empty environment and both READMEs were followed as a stranger would. The scorer is untouched
- still 0.10.0 - and no survey figure moves; what changes is what `report` says and how the
package is reached. Minor version, not patch, because three changes are observable to
consumers: question 3's mark and the score can change for a repository between 7.5% and
9.4%, question 5's line changes for a repository whose index was never committed, and the
install gains a `kibsu` command.

- **`report` compares against the median the table publishes.** The constant behind question
  3 sat at 9.4 (scorer 0.6.0) through releases 0.6.0-0.8.0 while the published median moved to
  7.7 and 7.5. It is 7.5 now, stored with the scorer that measured it, and
  `tests/test_peer_median.py` fails while the pair disagrees with `evidence/`. When the running
  scorer differs from the median's, the finding says so.
- **Question 5 abstains on an index that was never committed** instead of convicting every
  commit that added a doc - the layout `kibsu index` itself produces when the file is
  gitignored. A committed index left stale is still convicted.
- **Question 5 counts the commits it actually replayed**, not the cap of 200.
- **`pip install kibsu` provides a `kibsu` command**, so `uvx kibsu report .` and
  `pipx run kibsu report .` work. `python -m kibsu` is unchanged and remains the form that
  runs from a bare clone.
- **README:** an install line (there was none), and the pasted sample re-run - it had shown
  15.6% for a repository the table below it gave 13.1%.
- **`tools/refresh_readme_counts.py` refuses a count it cannot measure.** Run on a machine with
  an older kibsu pip-installed, it imported that copy during test discovery, lost a test
  module to an import error, and wrote a case count seven short with exit 0. It measures this
  checkout now, and exits 2 when any test module fails to load.
- **`install.json` records when the install happened (#43, closes #36).** `installed_at`
  carried the HEAD commit's timestamp; it is wall-clock now, with the commit time kept beside
  it. Contributed by @HeaTTap - the project's second outside code contribution.

## 0.8.0 - 2026-09-05

The pre-release audit round. Before this package was cut, `main` was audited the way the
survey repos are - adversarial agents over the three scorer rounds of 2026-08-31, refuters
defaulting to "refuted" when a claim could not be reproduced - and everything that survived
ships here. Minor version: the published figures move, the sdist's contents change, and this
package carries scorer 0.10.0 (the 0.7.0 package carried 0.8.0; scorer 0.9.0 was never on PyPI).

- **SCORER 0.10.0 (#89; CORRECTIONS 2026-09-01): three refinements, one moves numbers.** Five
  verb-vocabulary entries - `note`, `state`, `list`, `record`, `track` - stop counting
  `Note: ...`, `List of ...` and `State of ...` openers as instructions (20 of 5,930 counted
  lines on a 250-file public corpus; `List the files` still counts). Two measured nulls: the
  directory-prefix SCOPE check had gone case-sensitive with 0.9.0's byte-exact existence check
  (scope and existence are different questions - two matchers now), and the mandate rule read
  user-scope mentions ("save it into *your* notes") as this repository's promises. Zero pinned
  tokens hit either. Re-measured at the same pinned SHAs (#92): median procedure-only
  7.7% -> 7.5%, instructions 26,698 -> 26,623, in-scope mandated artifacts 230 -> 229 with
  phantoms unmoved at 96 (42%). The median moved DOWN because many of the dropped callouts
  carried a backtick command and had been counted CHECKABLE - a note about a command is not a
  command.
- **Scorer 0.9.0 (#85, #86) reaches a package for the first time:** file existence is byte-exact,
  like git; detection stays case-insensitive. One flip at the pins, phantoms 95 -> 96.
- **The sdist can run its own test suite (#90, #91).** The 0.7.0 tarball on PyPI could not:
  setuptools' legacy finder dropped `tests/support.py`, `tests/__init__.py`, `tools/` and
  `evidence/`. `MANIFEST.in` now carries them, plus the CI definitions the suite reads;
  `tools/assert_dist_roundtrip.py --sdist-contents --sdist-suite` proves it against every build
  in CI, unpacking behind a containment check after CodeQL flagged the first draft's
  `extractall()`. #90's commit message described three parts and shipped one; #91's message
  owns that, and CORRECTIONS records it.
- **`kibsu audit --definitions` describes the ruleset it runs (#88).** The text had stopped at
  scorer 0.6.0 while the code was at 0.9.0.
- **PREREGISTRATION.md carries a dated correction.** Two cells of the 2026-08-07 table were
  copies of the baseline row (post-cycle-1 doctrine, 0/34 and 0/37; re-run from the v0.2.1 and
  v0.3.0 tags: 0/40 and 0/44). Doctrine was 0.0% at every state under every instrument - no
  conclusion moves. The chaining check runs before any note is committed from here on.

## 0.7.0 - 2026-08-31

The genre round, alone by design. Scorer 0.8.0's mandate rule is the only change: a unit
that mandates artifacts or carries runnable fences cannot be DETECTED as doctrine - derived
from this project's own v0.3.0 definition (doctrine produces judgement, not files), so a
unit promising files cannot claim the 0%-by-construction exemption. Declared genre still
beats detection in both directions. Minor version: the genre census and two survey cells
move; package and scorer version independently - this package carries scorer 0.8.0.

- Calibrated over 1,561 pinned-corpus units before freezing: three candidate designs, the
  two heuristic ones rejected for failing the audited repro, the definition-derived one
  shipped with 8 flips (0.5%) - every one a visible misclassification, each demoting to the
  genre its own next-best score already indicated. The full flip list is published in
  CORRECTIONS.md (second 2026-08-31 entry).
- Re-measured at the same pinned SHAs: median procedure-only 7.7% UNMOVED, phantoms 95/230
  UNMOVED, two cells shift a tenth of a point in mixed directions, and both preregistration
  workspaces reproduce to the digit - the fourth appended note is a recorded null. Clause
  3's doctrine floor is now stricter than pre-registered: a mandating unit cannot drift
  into the watched pool by detection.

## 0.6.0 - 2026-08-31

The K-check trio and the scorer 0.7.0 round: the incident checks born from a real production
morning ship as product features, and the instrument corrects the biggest flattery bias it
has ever carried. Minor version: discover gains three capability rows and its verdicts move;
the scorer's published figures move with a full CORRECTIONS round. Package and scorer
version independently, as always - this package carries scorer 0.7.0.

- **SCORER 0.7.0 (#79, #80; CORRECTIONS 2026-08-31): four blind spots closed, every
  published figure re-measured at the pinned SHAs.** The imperative anchor reads through
  markdown emphasis (#56 - an experiment cycle had moved its own numbers by DE-BOLDING
  verbs); the verb vocabulary grew by 55 census-approved entries while noun-heavy candidates
  were rejected on the same evidence (#74 - `import` alone would have added 1,625 false
  instructions); artifact extraction accepts the optional delimiters checkability always did
  (#75 - "Create config.yml" was checkable yet could never be phantom); and every mention of
  a mandate counts toward its scope, uncapped (#76). Instruction counts grew 31.6% and 97%
  of the growth is claimable: the blind spots overwhelmingly hid unverifiable instructions,
  so every earlier table flattered every repo it measured. Median procedure-only 9.4% ->
  7.7%; phantoms 69/159 -> 95/230; PREREGISTRATION carries its third appended note with both
  workspaces re-baselined and pin authentication done by digit-for-digit reproduction of the
  old column first. Deferred with reasons on the record: #77 (genre vote), #78 (glob case).
- **discover gains "Dangerous flags" (#68): instructions that hand an agent gate-removing
  flags** (--auto-approve / --skip-* / --force / --yes / --no-verify) with no approval or
  prohibition rule within two lines read INERT, exit 1, file:line named. A prohibition
  ("never run --force") is the opposite of a grant and does not fire; bare "-y" is out of
  scope by the cry-wolf rule. One bug the fail-first discipline caught is worth retelling:
  the approval vocabulary contained "approv" and --auto-approve CONTAINS "approve" - the
  most dangerous flag on the list gated itself until the flag tokens were struck from the
  window before the approval test.
- **discover gains "Scope defaults" (#69): a doc-mandated python entry point whose
  data-scope default is a hardcoded date literal** (module assignment or argparse default=)
  reads INERT. A literal scope was true the day it was written; the day an argument is
  omitted it silently scopes the run to a stale window. The scan universe is exactly the
  scripts the instructions mandate - never the whole tree.
- **discover gains "Writes verified" (#71): a commanded state-changing action with no
  verification instruction within three lines** reads INERT. Calibrated over a 250-file
  public corpus before freezing, then attacked by adversarial agents that reproduced nine
  wrong verdicts - six fixed and pinned, two disclosed as deliberate v1 scope (line-leading
  commands only; the verify window crosses into the next list item because "1. Push.
  2. Then verify CI is green." is how real docs verify), one rejected with a pinning test.
- **tooling: the README's count-it-yourself paragraph is produced, not authored (#67).**
  `tools/refresh_readme_counts.py` imports the #29 guard's own measure() - asserted by
  IDENTITY in a test, because a second implementation of a measurement is the drift class
  itself - and rewrites only the four numbers, byte-identical everywhere else. Born from
  seven forced re-syncs in one merge day; on the pre-PR checklist now. It promptly rejected
  its own round's PR when a test re-pin followed the refresh, which is the system working.

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
