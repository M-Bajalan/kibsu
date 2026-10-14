#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for kibsu/config.py - the `.kibsu.json` loader every consumer with teeth sits on.

Issue #38: config.py had no test file at all, while its output feeds report.py's readiness
score (index_path/docs_root gate the "Find your docs" finding), gate.py's commit-blocking
gate list (four call sites), learn.py's memory_root, and check.py's index_path. The three
documented behaviors pinned here are exactly the ones a future edit could silently invert
with nothing to catch it:

  - the malformed-JSON and non-object fallbacks (warn on stderr, return DEFAULTS, never
    raise) - the fail-safe posture a git hook depends on when a human hand-edits the file;
  - the SHALLOW merge contract ("lists are not concatenated, nested dicts are not
    deep-merged") - flipping it to a deep merge would change what report.py scores and what
    gate.py blocks for any repo with a partial config;
  - the fresh-deepcopy contract - a caller mutating its returned config must never corrupt
    DEFAULTS for every later caller in the same process.

Direct in-process calls (config.load is an ordinary importable function); each test builds
its own throwaway root dir. Per CONTRIBUTING rule 4, the failure paths are DRIVEN, not
assumed: real malformed bytes on disk, real stderr captured.
"""
import contextlib
import copy
import io
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kibsu import config


class ConfigLoadTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="kibsu_test_config_")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _write(self, body):
        with open(os.path.join(self.root, ".kibsu.json"), "w", encoding="utf-8",
                  newline="\n") as fh:
            fh.write(body)

    def _load(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            result = config.load(self.root)
        return result, err.getvalue()

    def test_missing_file_returns_defaults_silently(self):
        result, err = self._load()
        self.assertEqual(result, config.DEFAULTS)
        self.assertEqual(err, "", "the common no-config case must not warn")

    def test_malformed_json_warns_on_stderr_and_returns_defaults(self):
        self._write('{"gates": [oops')
        result, err = self._load()
        self.assertEqual(result, config.DEFAULTS)
        self.assertIn("could not read", err)
        self.assertIn("using defaults", err)

    def test_non_object_body_warns_and_returns_defaults(self):
        self._write('[1, 2, 3]\n')
        result, err = self._load()
        self.assertEqual(result, config.DEFAULTS)
        self.assertIn("does not contain a JSON object", err)

    def test_a_wrongly_typed_key_warns_and_keeps_only_that_key_at_its_default(self):
        """#112: the callers trust the types, so {"skills_dir": 5} reached `.replace()` in
        report and was a traceback. Same contract as malformed JSON, scoped to the one key:
        warned about, left at its default - and the well-typed keys beside it still apply."""
        self._write('{"skills_dir": 5, "instruction_files": "AGENTS.md", '
                    '"docs_root": "handbook"}\n')
        result, err = self._load()
        self.assertEqual(result["skills_dir"], config.DEFAULTS["skills_dir"])
        self.assertEqual(result["instruction_files"], config.DEFAULTS["instruction_files"])
        self.assertEqual(result["docs_root"], "handbook")
        self.assertIn('"skills_dir" must be a string, not 5', err)
        self.assertIn('"instruction_files" must be a list, not "AGENTS.md"', err)

    def test_a_list_holding_a_non_string_is_refused_and_unknown_keys_pass_through(self):
        self._write('{"instruction_files": ["AGENTS.md", 7], "my_extension": {"x": 1}}\n')
        result, err = self._load()
        self.assertEqual(result["instruction_files"], config.DEFAULTS["instruction_files"])
        self.assertIn('"instruction_files" must be a list of strings', err)
        self.assertEqual(result["my_extension"], {"x": 1})

    def test_null_stays_null_where_the_callers_read_it_as_not_set(self):
        """skills_dir and instruction_files are read null-safely (`cfg.get(..) and`, `or
        DEFAULTS`), and check.py drops a null skills_dir from its existence scope: replacing null
        with the default changed a question-5 verdict. gates is gate.py's to judge, a dict of
        gates included - it says what is wrong with them better than a type check."""
        self._write('{"skills_dir": null, "instruction_files": null, '
                    '"gates": {"lint": {"cmd": ""}}}\n')
        result, err = self._load()
        self.assertIsNone(result["skills_dir"])
        self.assertIsNone(result["instruction_files"])
        self.assertEqual(result["gates"], {"lint": {"cmd": ""}})
        self.assertEqual(err, "")

    def test_null_where_it_was_a_traceback_is_a_warning_and_a_key_warns_once(self):
        self._write('{"docs_root": null}\n')
        result, err = self._load()
        self.assertEqual(result["docs_root"], config.DEFAULTS["docs_root"])
        self.assertIn('"docs_root" must be a string, not null', err)
        _, again = self._load()                    # gate.py loads the config twice per run
        self.assertEqual(again, "", "the same key in the same file warns once per run")

    def test_negative_control_well_typed_values_are_kept_and_nothing_is_warned(self):
        self._write('{"skills_dir": "agents", "instruction_files": ["AGENTS.md"], '
                    '"gates": [{"name": "g"}]}\n')
        result, err = self._load()
        self.assertEqual((result["skills_dir"], result["instruction_files"], result["gates"]),
                         ("agents", ["AGENTS.md"], [{"name": "g"}]))
        self.assertEqual(err, "")

    def test_merge_is_shallow_and_wholesale(self):
        """The documented contract, verbatim: "lists are not concatenated, nested dicts are
        not deep-merged". A one-item instruction_files list REPLACES the three-item default
        outright, gates is replaced wholesale, and untouched keys keep their defaults."""
        self._write('{"instruction_files": ["ONLY.md"], '
                    '"gates": [{"name": "g", "cmd": ["x"]}]}\n')
        result, err = self._load()
        self.assertEqual(err, "")
        self.assertEqual(result["instruction_files"], ["ONLY.md"])
        self.assertEqual(result["gates"], [{"name": "g", "cmd": ["x"]}])
        self.assertEqual(result["docs_root"], config.DEFAULTS["docs_root"])
        self.assertEqual(result["index_path"], config.DEFAULTS["index_path"])

    def test_returned_config_is_a_fresh_copy_mutation_does_not_leak_into_defaults(self):
        """load() deepcopies DEFAULTS; a caller appending to result["instruction_files"]
        must not poison every later load() in the same process. A future edit downgrading
        deepcopy to a shallow dict copy would pass every other test here and fail this one."""
        pristine = copy.deepcopy(config.DEFAULTS)
        first, _ = self._load()
        first["instruction_files"].append("INJECTED.md")
        first["docs_root"] = "elsewhere"

        second, _ = self._load()
        self.assertEqual(second, pristine)
        self.assertEqual(config.DEFAULTS, pristine)


if __name__ == "__main__":
    unittest.main()
