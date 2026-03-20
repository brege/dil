from pathlib import Path
import argparse
import re
import sys

import tomlkit

from gen import array
from gen.policy import PRUNE
from gen.policy import SOURCE as POLICY
from gen.policy import load


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "data" / "kondo" / "lib.rs"
NAMES = {
    "Cargo": "cargo",
    "Node": "node",
    "Unity": "unity",
    "Stack": "stack",
    "Cabal": "cabal",
    "SBT": "sbt",
    "Maven": "maven",
    "Gradle": "gradle",
    "CMake": "cmake",
    "Unreal": "unreal",
    "Jupyter": "jupyter",
    "Python": "python",
    "Pixi": "pixi",
    "Composer": "composer",
    "Pub": "pub",
    "Elixir": "elixir",
    "Swift": "swift",
    "Zig": "zig",
    "Godot4": "godot4",
    "Dotnet": "dotnet",
    "Turborepo": "turborepo",
    "Terraform": "terraform",
    "Cocoapods": "cocoapods",
}
ALIASES = {"mvn": "maven", "reactnative": "reactnative"}

# Kondo stores project markers as Rust string constants.
STR = re.compile(r'^const (\w+): &str = "([^"]+)";$', re.M)

# Kondo stores artifact directories as Rust string arrays.
ARRAY = re.compile(
    r"^const (PROJECT_\w+_DIRS): \[&str; \d+\] = \[\s*(.*?)\s*\];$", re.M | re.S
)

# Project detection comes from the file_name match block in ProjectIter::next().
MATCH = re.compile(r"let p_type = match file_name \{(.*?)_ => None,", re.S)


def build() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build dil litter rules from cached Kondo data"
    )
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--policy", type=Path, default=POLICY)
    return parser


def parse(text: str) -> dict[str, dict[str, list[str]]]:
    arrays = {
        name: re.findall(r'"([^"]+)"', body) for name, body in ARRAY.findall(text)
    }
    match = MATCH.search(text)
    if match is None:
        raise SystemExit("error: could not parse Kondo match block")

    rules: dict[str, dict[str, list[str]]] = {}
    for name, items in arrays.items():
        slug = (
            name.removeprefix("PROJECT_").removesuffix("_DIRS").lower().replace("_", "")
        )
        slug = ALIASES.get(slug, slug)
        rules[slug] = {
            "patterns": [f"{item.rstrip('/')}/" for item in items],
        }
    for project in NAMES.values():
        rules.setdefault(
            project,
            {
                "patterns": [],
            },
        )

    return dict(sorted(rules.items()))


def merge(
    base: dict[str, dict[str, list[str]]], policy_path: Path
) -> dict[str, dict[str, list[str]]]:
    merged: dict[str, dict[str, list[str]]] = {}
    for name, rule in load(policy_path).items():
        current = {field: [] for field in PRUNE}
        for key in rule.kondo:
            for field in PRUNE:
                for item in base.get(key, {}).get(field, []):
                    if item not in current[field]:
                        current[field].append(item)
        for field, items in rule.add.items():
            if field not in PRUNE:
                continue
            for item in items:
                if item not in current[field]:
                    current[field].append(item)
        for field, items in rule.rm.items():
            if field not in PRUNE:
                continue
            current[field] = [item for item in current[field] if item not in items]
        merged[name] = current
    return dict(sorted(merged.items()))


def render(rules: dict[str, dict[str, list[str]]]) -> str:
    doc = tomlkit.document()
    for name, rule in rules.items():
        table = tomlkit.table()
        table.add("patterns", array(rule["patterns"]))
        doc.add(name, table)
    return tomlkit.dumps(doc)


def main() -> int:
    args = build().parse_args()
    if not args.source.is_file():
        raise SystemExit(f"error: source does not exist: {args.source}")
    text = render(merge(parse(args.source.read_text()), args.policy))
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
