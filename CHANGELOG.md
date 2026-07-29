# Changelog

## 0.1.1 - 2026-07-29

Fixed #2: `check --backtest-mode existence` scoped its "touched a watched .md" filter to
`dirname(index_path)` instead of the configured `docs_root` (+ `skills_dir` + `instruction_files`),
so a repo using kibsu's own default config (`index_path=".kibsu/index.json"`, `docs_root="docs"`)
always replayed 0 eligible commits and `report`'s HISTORY check (question 5) always rendered
COULD NOT CHECK.

## 0.1.0 - 2026-07-26

Initial release.
