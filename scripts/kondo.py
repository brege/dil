from pathlib import Path
import argparse
import re
import sys
import tomllib

import tomlkit


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "refs" / "kondo" / "kondo-lib" / "src" / "lib.rs"
EXTRA = ROOT / "scripts" / "extra.toml"
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
EXACT = re.compile(r"(FILE_\w+) => Some\(ProjectType::(\w+)\)")
SUFFIX = re.compile(r"ends_with\((FILE_\w+)\).*?Some\(ProjectType::(\w+)\)", re.S)


def build() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build dil seed rules from cached Kondo data"
    )
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--extra", type=Path, default=EXTRA)
    parser.add_argument("--detect", action="store_true")
    parser.add_argument("--write", type=Path)
    return parser


def parse(text: str) -> dict[str, dict[str, list[str]]]:
    consts = dict(STR.findall(text))
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
            "dirs": [item for item in items if "/" not in item],
            "files": [],
            "paths": [item for item in items if "/" in item],
            "detect_files": [],
            "detect_suffix": [],
        }

    block = match.group(1)
    for const, project in EXACT.findall(block):
        slug = NAMES[project]
        rules.setdefault(
            slug,
            {
                "dirs": [],
                "files": [],
                "paths": [],
                "detect_files": [],
                "detect_suffix": [],
            },
        )
        rules[slug].setdefault("detect_files", []).append(consts[const])

    for const, project in SUFFIX.findall(block):
        slug = NAMES[project]
        rules.setdefault(
            slug,
            {
                "dirs": [],
                "files": [],
                "paths": [],
                "detect_files": [],
                "detect_suffix": [],
            },
        )
        rules[slug].setdefault("detect_suffix", []).append(consts[const])

    return dict(sorted(rules.items()))


def load(path: Path) -> dict[str, dict[str, list[str]]]:
    if not path.is_file():
        return {}

    with path.open("rb") as handle:
        raw = tomllib.load(handle)

    rules: dict[str, dict[str, list[str]]] = {}
    for name, value in raw.items():
        if not isinstance(value, dict):
            raise SystemExit(f"error: invalid rule table in {path}: {name}")

        table: dict[str, list[str]] = {}
        for field in ("dirs", "files", "paths", "detect_files", "detect_suffix"):
            items = value.get(field, [])
            if not isinstance(items, list) or any(
                not isinstance(item, str) for item in items
            ):
                raise SystemExit(
                    f"error: {path}: {name}.{field} must be a list of strings"
                )
            table[field] = items
        rules[name] = table

    return rules


def merge(
    base: dict[str, dict[str, list[str]]], extra: dict[str, dict[str, list[str]]]
) -> dict[str, dict[str, list[str]]]:
    merged = {
        name: {field: items[:] for field, items in rule.items()}
        for name, rule in base.items()
    }

    for name, rule in extra.items():
        current = merged.setdefault(
            name,
            {
                "dirs": [],
                "files": [],
                "paths": [],
                "detect_files": [],
                "detect_suffix": [],
            },
        )
        for field, items in rule.items():
            for item in items:
                if item not in current[field]:
                    current[field].append(item)

    return dict(sorted(merged.items()))


def array(items: list[str]) -> tomlkit.items.Array:
    data = tomlkit.array()
    for item in items:
        data.append(item)
    if len(items) > 1:
        data.multiline(True)
    return data


def render(rules: dict[str, dict[str, list[str]]], include_detect: bool) -> str:
    doc = tomlkit.document()
    for name, rule in rules.items():
        table = tomlkit.table()
        table.add("dirs", array(rule["dirs"]))
        table.add("files", array(rule["files"]))
        table.add("paths", array(rule["paths"]))
        if include_detect and (rule["detect_files"] or rule["detect_suffix"]):
            detect_table = tomlkit.table()
            if rule["detect_files"]:
                detect_table.add("files", array(rule["detect_files"]))
            if rule["detect_suffix"]:
                detect_table.add("suffix", array(rule["detect_suffix"]))
            table.add("detect", detect_table)
        doc.add(name, table)
    return tomlkit.dumps(doc)


def main() -> int:
    args = build().parse_args()
    if not args.source.is_file():
        raise SystemExit(f"error: source does not exist: {args.source}")
    text = render(merge(parse(args.source.read_text()), load(args.extra)), args.detect)
    if args.write is None:
        sys.stdout.write(text)
        return 0
    args.write.parent.mkdir(parents=True, exist_ok=True)
    args.write.write_text(text)
    print(args.write)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
