#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""An installed kibsu must answer to its own name.

Through 0.8.0 the package declared no console script. `python -m kibsu` worked, and nothing
else did: `uvx kibsu report .` - the way a stranger tries a tool without installing it -
stopped at "Package `kibsu` does not provide any executables" (`pipx run` needs the same
declaration), and a plain `pip install kibsu` left no `kibsu` command behind. A tool whose
first claim is "run it and see" was unreachable by the shortest way of running it.

What is checked is the declaration and that it resolves: `[project.scripts]` names `kibsu`,
and the target is the same callable `python -m kibsu` runs - not a second entry point that
could come to behave differently. The file is read as text because tomllib arrived in 3.11
and the floor is 3.8. Nothing here installs anything (#111): the installed half - the built
wheel, in an empty virtualenv, answering `kibsu --version` with its own version - is a step in
.github/workflows/roundtrip.yml, with a negative control that builds the wheel without
[project.scripts] and must fail.

Per CONTRIBUTING rule 4 each check has a negative control driven through the same function."""
import importlib
import io
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from support import PACKAGE_ROOT

sys.path.insert(0, PACKAGE_ROOT)

SECTION_RE = re.compile(r"^\[project\.scripts\]\s*$(.*?)(?=^\[|\Z)", re.M | re.S)
ENTRY_RE = re.compile(r'^kibsu\s*=\s*"([\w.]+):(\w+)"\s*$', re.M)


def pyproject_text():
    with io.open(os.path.join(PACKAGE_ROOT, "pyproject.toml"), encoding="utf-8") as fh:
        return fh.read()


def console_script_problems(text):
    """Why `kibsu` would not be a working command after install. Empty when it would be."""
    section = SECTION_RE.search(text)
    if not section:
        return ["pyproject.toml has no [project.scripts] table - install puts no command on PATH"]
    entry = ENTRY_RE.search(section.group(1))
    if not entry:
        return ["[project.scripts] does not declare a `kibsu` command"]
    module_name, func_name = entry.groups()
    try:
        target = getattr(importlib.import_module(module_name), func_name, None)
    except ImportError as exc:
        return ["`kibsu` points at %s, which does not import: %s" % (module_name, exc)]
    if not callable(target):
        return ["`kibsu` points at %s:%s, which is not callable" % (module_name, func_name)]
    return []


class ConsoleScriptTests(unittest.TestCase):
    def test_the_package_declares_a_kibsu_command_that_resolves(self):
        self.assertEqual(console_script_problems(pyproject_text()), [])

    def test_the_command_is_the_same_main_python_dash_m_runs(self):
        from kibsu import __main__ as entry
        module_name, func_name = ENTRY_RE.search(
            SECTION_RE.search(pyproject_text()).group(1)).groups()
        self.assertIs(getattr(importlib.import_module(module_name), func_name), entry.main)

    def test_negative_control_no_scripts_table_is_caught(self):
        text = SECTION_RE.sub("", pyproject_text())
        self.assertNotIn("[project.scripts]", text)
        self.assertEqual(len(console_script_problems(text)), 1)

    def test_negative_control_a_target_that_does_not_exist_is_caught(self):
        text = pyproject_text().replace('"kibsu.__main__:main"', '"kibsu.__main__:no_such_main"')
        problems = console_script_problems(text)
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("not callable", problems[0])


if __name__ == "__main__":
    unittest.main()
