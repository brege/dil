from __future__ import annotations

import argparse
import json
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
    parser.add_argument("path", nargs="?", default=".", help="path to scan")
    parser.add_argument(
        "--type", dest="types", action="append", help="limit results to type names"
    )
    parser.add_argument("-p", "--paths", action="store_true", help="show matched paths")
    parser.add_argument(
        "-P",
        "--absolute-paths",
        action="store_true",
        help="show absolute matched paths",
    )
    parser.add_argument("-d", "--delete", action="store_true", help="delete matches")
    parser.add_argument(
        "-n", "--dry-run", action="store_true", help="show what would be deleted"
    )
    parser.add_argument(
        "-s", "--short", action="store_true", help="use short dry-run output"
    )
    parser.add_argument(
        "-y", "--yes", action="store_true", help="skip the delete prompt"
    )
    parser.add_argument("--json", action="store_true", help="emit json output")
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


def print_litter(matches: list[Match], selected_types: list[str]) -> None:
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


def display_path(match: Match, root: Path, *, absolute: bool) -> str:
    path = match.path if absolute else match.path.relative_to(root).as_posix()
    suffix = "/" if match.kind == "dir" else ""
    return f"{path}{suffix}"


def print_paths(
    matches: list[Match], root: Path, selected_types: list[str], *, absolute: bool
) -> None:
    rows: list[ui.ScanRow] = []
    for type_name in selected_types:
        for match in matches:
            if match.rule_type != type_name:
                continue
            rows.append(
                ui.ScanRow(
                    type=type_name,
                    rule=match.rule_value,
                    path=display_path(match, root, absolute=absolute),
                )
            )
    ui.scan(Console(), rows)


def print_short(
    matches: list[Match], root: Path, selected_types: list[str], *, absolute: bool
) -> None:
    if not matches:
        return
    active = [
        name
        for name in selected_types
        if any(match.rule_type == name for match in matches)
    ]
    print(f"PROJECT: {root}")
    print(f"TYPES:   {'|'.join(active)}")
    print("WOULD DELETE:")
    print("-----")
    for match in matches:
        print(display_path(match, root, absolute=absolute))
    print()
    print(f"To delete these items, run: dil -d -y {root}")


def active_types(matches: list[Match], selected_types: list[str]) -> list[str]:
    return [
        name
        for name in selected_types
        if any(match.rule_type == name for match in matches)
    ]


def payload(
    matches: list[Match], root: Path, selected_types: list[str], *, absolute: bool
) -> dict[str, object]:
    active = active_types(matches, selected_types)
    grouped: dict[str, dict[str, tuple[int, int]]] = defaultdict(dict)
    items: list[dict[str, object]] = []
    total_size = 0
    for match in matches:
        path = match.path if absolute else match.path.relative_to(root)
        suffix = "/" if match.kind == "dir" else ""
        items.append(
            {
                "type": match.rule_type,
                "rule": match.rule_value,
                "path": f"{path}{suffix}",
                "kind": match.kind,
                "size": match.size_bytes,
            }
        )
        total_size += match.size_bytes
        count, size_bytes = grouped[match.rule_type].get(match.rule_value, (0, 0))
        grouped[match.rule_type][match.rule_value] = (
            count + 1,
            size_bytes + match.size_bytes,
        )

    rules: list[dict[str, object]] = []
    for type_name in active:
        for rule_value, (count, size_bytes) in sorted(
            grouped.get(type_name, {}).items()
        ):
            rules.append(
                {
                    "type": type_name,
                    "rule": rule_value,
                    "matches": count,
                    "size": size_bytes,
                }
            )

    return {
        "root": str(root),
        "types": active,
        "matches": items,
        "rules": rules,
        "total": {
            "matches": len(matches),
            "size": total_size,
        },
    }


def prune_matches(matches: list[Match]) -> None:
    for match in reversed(matches):
        if match.kind == "dir":
            shutil.rmtree(match.path)
        else:
            match.path.unlink(missing_ok=True)


def confirm() -> bool:
    try:
        reply = input("Delete matched items? [y/N] ")
    except EOFError:
        return False
    return reply in {"y", "Y"}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.paths and args.absolute_paths:
        raise SystemExit("error: choose only one of --paths or --absolute-paths")
    if args.dry_run and not args.delete:
        raise SystemExit("error: --dry-run requires --delete")
    if args.yes and not args.delete:
        raise SystemExit("error: --yes requires --delete")
    if args.short and not (args.delete and args.dry_run):
        raise SystemExit("error: --short requires --delete --dry-run")
    if args.json and args.delete and not args.dry_run:
        raise SystemExit("error: --json requires --dry-run when used with --delete")

    root = require_root(args.path)
    selected_types, rules = resolve_types(root, args.types)
    matches = find_matches(
        root,
        selected_types,
        rules,
        with_size=not args.paths and not args.absolute_paths,
    )
    if args.json:
        absolute = args.absolute_paths
        print(json.dumps(payload(matches, root, selected_types, absolute=absolute)))
        return 0

    if args.delete:
        if args.dry_run:
            if args.short:
                print_short(
                    matches,
                    root,
                    selected_types,
                    absolute=args.absolute_paths,
                )
                return 0
            print_paths(
                matches,
                root,
                selected_types,
                absolute=args.absolute_paths,
            )
            return 0

        if not args.yes:
            if not matches:
                return 0
            print_paths(
                matches,
                root,
                selected_types,
                absolute=args.absolute_paths,
            )
            if not confirm():
                print("Aborted.")
                return 0

        prune_matches(matches)
        print(f"Deleted {len(matches)} item(s)")
        return 0

    if args.paths or args.absolute_paths:
        print_paths(matches, root, selected_types, absolute=args.absolute_paths)
        return 0

    print_litter(matches, selected_types)
    return 0


if __name__ == "__main__":
    sys.exit(main())
