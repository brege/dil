from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from collections import defaultdict

from rich.console import Console

from .config import TypeRules, load_rules
from .engine import Match, detect_types, find_matches
from . import ui


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dil", description="Detect and prune disposable project litter"
    )
    subparsers = parser.add_subparsers(dest="command")

    scan = subparsers.add_parser("scan")
    scan.add_argument("path", nargs="?", default=".")
    scan.add_argument("--type", dest="types", action="append")
    scan.add_argument("-c", "--compact", action="store_true")

    prune = subparsers.add_parser("prune")
    prune.add_argument("path", nargs="?", default=".")
    prune.add_argument("--type", dest="types", action="append", required=True)
    prune.add_argument("--pretty", action="store_true")
    prune.add_argument("-f", "--force", action="store_true")
    prune.add_argument("-n", "--dry-run", action="store_true")

    return parser


def _overview_path(argv: list[str] | None) -> str | None:
    if not argv:
        return "."
    first = argv[0]
    if first in {"scan", "prune", "-h", "--help"}:
        return None
    if first.startswith("-"):
        return None
    return first


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
    root: Path, raw_types: list[str] | None
) -> tuple[list[str], dict[str, TypeRules]]:
    rules = load_rules(root)
    if not raw_types:
        return list(detect_types(root, rules)), rules
    selected = flatten_types(raw_types)
    unsupported = [name for name in selected if name not in rules]
    if unsupported:
        raise SystemExit(f"error: unsupported type(s): {', '.join(unsupported)}")
    return selected, rules


def print_scan(
    matches: list[Match], root: Path, selected_types: list[str], compact: bool
) -> None:
    if compact:
        grouped: dict[str, dict[str, tuple[int, int]]] = defaultdict(dict)
        for match in matches:
            count, size_bytes = grouped[match.rule_type].get(match.rule_value, (0, 0))
            grouped[match.rule_type][match.rule_value] = (
                count + 1,
                size_bytes + match.size_bytes,
            )

        rows: list[ui.LitterRow] = []
        for type_name in selected_types:
            for rule_value, (count, size_bytes) in sorted(
                grouped.get(type_name, {}).items()
            ):
                rows.append(
                    ui.LitterRow(
                        type=type_name,
                        rule=rule_value,
                        matches=count,
                        size=size_bytes,
                    )
                )
        ui.litter(Console(), rows)
        return

    rows: list[ui.ScanRow] = []
    for type_name in selected_types:
        for match in matches:
            if match.rule_type != type_name:
                continue
            suffix = "/" if match.kind == "dir" else ""
            rows.append(
                ui.ScanRow(
                    type=type_name,
                    rule=match.rule_value,
                    path=f"{match.path.relative_to(root).as_posix()}{suffix}",
                )
            )

    ui.scan(Console(), rows)


def print_prune(matches: list[Match], root: Path, selected_types: list[str]) -> None:
    type_label = "|".join(selected_types)
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


def print_overview(root: Path, rules: dict[str, TypeRules]) -> None:
    console = Console()
    detected = detect_types(root, rules)
    rows: list[ui.OverviewRow] = []
    for name in detected:
        matches = find_matches(root, [name], rules)
        size_bytes = sum(match.size_bytes for match in matches)
        rows.append(
            ui.OverviewRow(
                type=name,
                matches=len(matches),
                size=size_bytes,
            )
        )
    ui.overview(console, str(root), rows)


def prune_matches(matches: list[Match]) -> None:
    for match in reversed(matches):
        if match.kind == "dir":
            shutil.rmtree(match.path)
        else:
            match.path.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    argsv = sys.argv[1:] if argv is None else argv
    path_value = _overview_path(argsv)
    if path_value is not None:
        root = require_root(path_value)
        print_overview(root, load_rules(root))
        return 0

    parser = build_parser()
    args = parser.parse_args(argsv)

    root = require_root(args.path)
    selected_types, rules = resolve_types(root, args.types)
    matches = find_matches(root, selected_types, rules)

    if args.command == "scan":
        print_scan(matches, root, selected_types, args.compact)
        return 0

    if not args.force:
        print_prune(matches, root, selected_types)
        print()
        print("Refusing to delete without --force.")
        return 0

    prune_matches(matches)
    print(f"Deleted {len(matches)} item(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
