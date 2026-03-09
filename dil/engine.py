from __future__ import annotations

from dataclasses import dataclass
import fnmatch
import os
from pathlib import Path

from .config import TypeRules


@dataclass(frozen=True)
class Match:
    path: Path
    kind: str
    rule_type: str
    rule_value: str
    size_bytes: int


@dataclass(frozen=True)
class Summary:
    total_files: int
    total_dirs: int
    total_bytes: int
    clean_files: int
    clean_dirs: int
    clean_bytes: int


def _path_matches(relative_path: str, pattern: str) -> bool:
    normalized_path = relative_path.strip("/")
    normalized_pattern = pattern.strip("/")
    return fnmatch.fnmatchcase(normalized_path, normalized_pattern)


def _directory_size(path: Path) -> int:
    total = 0
    stack = [path]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(Path(entry.path))
                        elif entry.is_file(follow_symlinks=False):
                            total += entry.stat(follow_symlinks=False).st_size
                    except FileNotFoundError:
                        continue
        except FileNotFoundError:
            continue
    return total


def find_matches(
    root: Path, selected_types: list[str], available_rules: dict[str, TypeRules]
) -> list[Match]:
    matches: list[Match] = []
    seen: set[Path] = set()

    def add_match(path: Path, kind: str, rule_type: str, rule_value: str) -> None:
        resolved = path.resolve()
        if resolved in seen:
            return
        seen.add(resolved)
        size_bytes = _directory_size(path) if kind == "dir" else path.stat().st_size
        matches.append(
            Match(
                path=path,
                kind=kind,
                rule_type=rule_type,
                rule_value=rule_value,
                size_bytes=size_bytes,
            )
        )

    stack = [root]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    entry_path = Path(entry.path)
                    relative = entry_path.relative_to(root).as_posix()
                    pruned = False

                    if entry.is_dir(follow_symlinks=False):
                        for type_name in selected_types:
                            rules = available_rules[type_name]
                            for pattern in rules.paths:
                                if _path_matches(relative, pattern):
                                    add_match(entry_path, "dir", type_name, pattern)
                                    pruned = True
                                    break
                            if pruned:
                                break
                            for pattern in rules.dirs:
                                if fnmatch.fnmatchcase(entry.name, pattern):
                                    add_match(entry_path, "dir", type_name, pattern)
                                    pruned = True
                                    break
                            if pruned:
                                break

                        if not pruned:
                            stack.append(entry_path)
                        continue

                    if not entry.is_file(follow_symlinks=False):
                        continue

                    for type_name in selected_types:
                        rules = available_rules[type_name]
                        matched = False
                        for pattern in rules.paths:
                            if _path_matches(relative, pattern):
                                add_match(entry_path, "file", type_name, pattern)
                                matched = True
                                break
                        if matched:
                            break
                        for pattern in rules.files:
                            if fnmatch.fnmatchcase(entry.name, pattern):
                                add_match(entry_path, "file", type_name, pattern)
                                break
        except FileNotFoundError:
            continue

    matches.sort(key=lambda item: item.path.as_posix())
    return matches


def summarize(root: Path, matches: list[Match]) -> Summary:
    matched = {match.path.resolve() for match in matches}
    total_files = 0
    total_dirs = 1
    total_bytes = 0
    clean_files = 0
    clean_dirs = 1
    clean_bytes = 0

    stack = [root]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    entry_path = Path(entry.path)
                    resolved = entry_path.resolve()
                    is_matched = resolved in matched

                    if entry.is_dir(follow_symlinks=False):
                        total_dirs += 1
                        if not is_matched:
                            clean_dirs += 1
                            stack.append(entry_path)
                        continue

                    if not entry.is_file(follow_symlinks=False):
                        continue

                    size_bytes = entry.stat(follow_symlinks=False).st_size
                    total_files += 1
                    total_bytes += size_bytes
                    if not is_matched:
                        clean_files += 1
                        clean_bytes += size_bytes
        except FileNotFoundError:
            continue

    matched_bytes = sum(match.size_bytes for match in matches if match.kind == "dir")
    matched_bytes += sum(match.size_bytes for match in matches if match.kind == "file")

    return Summary(
        total_files=total_files,
        total_dirs=total_dirs,
        total_bytes=total_bytes,
        clean_files=clean_files,
        clean_dirs=clean_dirs,
        clean_bytes=max(total_bytes - matched_bytes, 0),
    )
