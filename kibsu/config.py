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
    prints a warning to stderr and also falls back to DEFAULTS. This
    function never raises.
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
        result[key] = value

    return result
