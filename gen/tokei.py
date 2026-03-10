from pathlib import Path
import argparse
import json
import sys

import tomlkit
from tomlkit.items import Array

from gen.policy import SOURCE as POLICY
from gen.policy import load


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "data" / "tokei" / "languages.json"


def build() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build dil detector rules from cached Tokei data"
    )
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--policy", type=Path, default=POLICY)
    return parser


def parse(path: Path) -> dict[str, dict[str, list[str]]]:
    if not path.is_file():
        raise SystemExit(f"error: source does not exist: {path}")

    raw = json.loads(path.read_text())
    languages = raw["languages"]
    rules: dict[str, dict[str, list[str]]] = {}
    for name, data in languages.items():
        rules[name] = {
            "detect_files": [],
            "detect_suffix": [f".{item}" for item in data.get("extensions", [])],
            "detect_names": list(data.get("filenames", [])),
            "detect_env": list(data.get("env", [])),
            "detect_shebang": list(data.get("shebangs", [])),
        }
    return rules


def merge(
    base: dict[str, dict[str, list[str]]], policy_path: Path
) -> dict[str, dict[str, list[str]]]:
    merged: dict[str, dict[str, list[str]]] = {}
    for name, rule in load(policy_path).items():
        current = {
            "detect_files": [],
            "detect_suffix": [],
            "detect_names": [],
            "detect_env": [],
            "detect_shebang": [],
        }
        for key in rule.tokei:
            for field, items in base.get(key, {}).items():
                for item in items:
                    if item not in current[field]:
                        current[field].append(item)
        for field, items in rule.add.items():
            if not field.startswith("detect_"):
                continue
            for item in items:
                if item not in current[field]:
                    current[field].append(item)
        for field, items in rule.rm.items():
            if not field.startswith("detect_"):
                continue
            current[field] = [item for item in current[field] if item not in items]
        if any(current.values()):
            merged[name] = current
    return dict(sorted(merged.items()))


def array(items: list[str]) -> Array:
    data = tomlkit.array()
    for item in items:
        data.append(item)
    if len(items) > 1:
        data.multiline(True)
    return data


def render(rules: dict[str, dict[str, list[str]]]) -> str:
    doc = tomlkit.document()
    for name, rule in rules.items():
        table = tomlkit.table()
        detect = tomlkit.table()
        if rule["detect_files"]:
            detect.add("files", array(rule["detect_files"]))
        if rule["detect_suffix"]:
            detect.add("suffix", array(rule["detect_suffix"]))
        if rule["detect_names"]:
            detect.add("names", array(rule["detect_names"]))
        if rule["detect_env"]:
            detect.add("env", array(rule["detect_env"]))
        if rule["detect_shebang"]:
            detect.add("shebang", array(rule["detect_shebang"]))
        table.add("detect", detect)
        doc.add(name, table)
    return tomlkit.dumps(doc)


def main() -> int:
    args = build().parse_args()
    text = render(merge(parse(args.source), args.policy))
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
