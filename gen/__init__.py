from __future__ import annotations

import tomlkit
from tomlkit.items import Array, Table

# detect field name → TOML subtable key
_DETECT_KEYS = {
    "detect_files": "files",
    "detect_suffix": "suffix",
    "detect_names": "names",
    "detect_env": "env",
    "detect_shebang": "shebang",
}


def array(items: list[str]) -> Array:
    data = tomlkit.array()
    for item in items:
        data.append(item)
    if len(items) > 1:
        data.multiline(True)
    return data


def build_detect(rule: dict[str, list[str]]) -> Table:
    table = tomlkit.table()
    for field, key in _DETECT_KEYS.items():
        if rule.get(field):
            table.add(key, array(rule[field]))
    return table
