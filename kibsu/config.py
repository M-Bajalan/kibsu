"""Load kibsu's per-repo configuration.

The schema is intentionally small and flat. Every key is optional; a repo
that has never heard of kibsu must still work, driven entirely by DEFAULTS.
"""

import copy
import json
import os
import sys

DEFAULTS = {
    "docs_root": "docs",
    "instruction_files": ["AGENTS.md", "CLAUDE.md", ".cursorrules"],
    "skills_dir": ".claude/skills",
    "memory_root": "docs/memory",
    "index_path": ".kibsu/index.json",
    "gates": [],
}


def load(root):
    """Load ``<root>/.kibsu.json`` and merge it over DEFAULTS.

    The merge is shallow and top-level only: a key present in the config
    file replaces the default value for that key wholesale (lists are not
    concatenated, nested dicts are not deep-merged). Keys absent from the
    file keep their default value.

    A missing config file is never an error - it is the expected, common
    case for a repo that has never heard of kibsu - and returns a fresh
    copy of DEFAULTS. Malformed JSON (or a config that isn't a JSON object)
    prints a warning to stderr and also falls back to DEFAULTS. A known key
    whose value has the wrong type gets the same treatment, for that key
    alone: warned about (once per run), and left at its default. Its callers
    trust the types, so `{"skills_dir": 5}` used to surface as an
    AttributeError traceback from `report` and `explain` (#112). Null stays
    null where the callers read it as "not set". This function never raises.
    """
    result = copy.deepcopy(DEFAULTS)

    config_path = os.path.join(root, ".kibsu.json")

    if not os.path.isfile(config_path):
        return result

    try:
        with open(config_path, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, ValueError) as exc:
        sys.stderr.write(
            "kibsu: warning: could not read %s (%s); using defaults\n"
            % (config_path, exc)
        )
        return result

    if not isinstance(raw, dict):
        sys.stderr.write(
            "kibsu: warning: %s does not contain a JSON object; using defaults\n"
            % config_path
        )
        return result

    for key, value in raw.items():
        wanted = _type_problem(key, value)
        if wanted:
            if (config_path, key) not in _WARNED:      # gate.py loads twice per run
                _WARNED.add((config_path, key))
                sys.stderr.write(
                    "kibsu: warning: %s: \"%s\" must be %s, not %s; using the default %s\n"
                    % (config_path, key, wanted, json.dumps(value), json.dumps(DEFAULTS[key]))
                )
            continue
        result[key] = value

    return result


# Null is a value for these two, not a type error: their callers read it as "not set"
# (`cfg.get("skills_dir") and ...`, `... or DEFAULTS["instruction_files"]`), and check.py drops
# a null skills_dir from its existence scope - replacing it with the default would change that
# verdict. The other path keys reach os.path.join, where null was always a traceback.
_NULLABLE = ("skills_dir", "instruction_files")
_WARNED = set()


def _type_problem(key, value):
    """What a known key's value must be, when it is not that - else None. Unknown keys pass
    through untouched, as they always have, and so does `gates`: gate.py judges its own
    shapes, a dict of gates included, and says what is wrong with them better than a type."""
    if key not in DEFAULTS or key == "gates" or (value is None and key in _NULLABLE):
        return None
    default = DEFAULTS[key]
    if isinstance(default, str):
        return None if isinstance(value, str) else "a string"
    if not isinstance(value, list):
        return "a list"
    if key == "instruction_files" and not all(isinstance(v, str) for v in value):
        return "a list of strings"
    return None
