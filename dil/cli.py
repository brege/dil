from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from .config import TypeRules, load_rules
from .engine import Match, find_matches, summarize


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dil", description="Detect and prune disposable project litter"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ("scan", "prune", "report"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("path", nargs="?", default=".")
        subparser.add_argument("--type", dest="types", action="append", required=True)
        subparser.add_argument("--pretty", action="store_true")
        subparser.add_argument("-f", "--force", action="store_true")
        subparser.add_argument("-n", "--dry-run", action="store_true")

    return parser


def flatten_types(values: list[str]) -> list[str]:
    types: list[str] = []
    for raw in values:
        types.extend(part for part in raw.split("|") if part)
    return types


def require_root(path_value: str) -> Path:
    root = Path(path_value).expanduser().resolve()
    if not root.exists():
        raise SystemExit(f"error: path does not exist: {root}")
    if root == Path("/"):
        raise SystemExit("error: refusing to operate on /")
    return root


def resolve_types(
    root: Path, raw_types: list[str]
) -> tuple[list[str], dict[str, TypeRules]]:
    rules = load_rules(root)
    selected = flatten_types(raw_types)
    unsupported = [name for name in selected if name not in rules]
    if unsupported:
        raise SystemExit(f"error: unsupported type(s): {', '.join(unsupported)}")
    return selected, rules


def print_scan(
    matches: list[Match], root: Path, selected_types: list[str], pretty: bool
) -> None:
    type_label = "|".join(selected_types)
    if pretty:
        print(f"Skip analysis for type '{type_label}' in directory: {root}")
        print("Dry run mode: no files will be deleted")
        print()
        print(f"Project directory: {root}")
        if matches:
            print("  WOULD DELETE:")
            for match in matches:
                suffix = "/" if match.kind == "dir" else ""
                print(f"    {match.path}{suffix}")
        else:
            print("  No junk files found.")
        print()
        print("Dry run complete: no files deleted")
        return

    for match in matches:
        suffix = "/" if match.kind == "dir" else ""
        print(f"{match.path}{suffix}")


def print_report(root: Path, matches: list[Match], selected_types: list[str]) -> None:
    summary = summarize(root, matches)
    grouped: dict[tuple[str, str], tuple[int, int]] = {}
    for match in matches:
        key = (match.rule_type, match.rule_value)
        count, size_bytes = grouped.get(key, (0, 0))
        grouped[key] = (count + 1, size_bytes + match.size_bytes)

    print("Litter Summary")
    print("--------------")
    print(f"{'Type':12} {'Rule':24} {'Matches':>7} {'Bytes':>12}")
    for (rule_type, rule_value), (count, size_bytes) in sorted(grouped.items()):
        print(f"{rule_type:12} {rule_value:24} {count:7d} {size_bytes:12d}")
    print()
    print("Project Summary")
    print("---------------")
    print(f"Types: {', '.join(selected_types)}")
    print(f"Total files: {summary.total_files}")
    print(f"Total dirs: {summary.total_dirs}")
    print(f"Total bytes: {summary.total_bytes}")
    print(f"Clean files: {summary.clean_files}")
    print(f"Clean dirs: {summary.clean_dirs}")
    print(f"Clean bytes: {summary.clean_bytes}")


def prune_matches(matches: list[Match]) -> None:
    for match in reversed(matches):
        if match.kind == "dir":
            shutil.rmtree(match.path)
        else:
            match.path.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    root = require_root(args.path)
    selected_types, rules = resolve_types(root, args.types)
    matches = find_matches(root, selected_types, rules)

    if args.command == "scan":
        print_scan(matches, root, selected_types, args.pretty)
        return 0

    if args.command == "report":
        print_report(root, matches, selected_types)
        return 0

    if not args.force:
        print_scan(matches, root, selected_types, pretty=True)
        print()
        print("Refusing to delete without --force.")
        return 0

    prune_matches(matches)
    print(f"Deleted {len(matches)} item(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
