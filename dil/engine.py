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


@dataclass(frozen=True)
class Detect:
    files: int
    suffix: int
    names: int
    env: int
    shebang: int


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


def _has_ancestor_suffix(
    current: Path, root: Path, suffixes: tuple[str, ...], cache: dict[Path, bool]
) -> bool:
    if current in cache:
        return cache[current]

    wanted = {suffix.casefold() for suffix in suffixes}
    try:
        with os.scandir(current) as entries:
            for entry in entries:
                if not entry.is_file(follow_symlinks=False):
                    continue
                if any(part.casefold() in wanted for part in Path(entry.name).suffixes):
                    cache[current] = True
                    return True
    except FileNotFoundError:
        cache[current] = False
        return False

    if current == root:
        cache[current] = False
        return False

    result = _has_ancestor_suffix(current.parent, root, suffixes, cache)
    cache[current] = result
    return result


def _read_head(path: Path) -> str:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            return handle.readline().strip()
    except OSError:
        return ""


def _signature(
    rule: TypeRules,
) -> tuple[
    tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]
]:
    return (
        tuple(sorted(rule.detect_files)),
        tuple(sorted(rule.detect_suffix)),
        tuple(sorted(rule.detect_names)),
        tuple(sorted(rule.detect_env)),
        tuple(sorted(rule.detect_shebang)),
    )


def detect_types(root: Path, rules: dict[str, TypeRules]) -> dict[str, Detect]:
    counts: dict[str, dict[str, int]] = {}
    signatures: dict[
        tuple[
            tuple[str, ...],
            tuple[str, ...],
            tuple[str, ...],
            tuple[str, ...],
            tuple[str, ...],
        ],
        list[str],
    ] = {}

    for name, rule in rules.items():
        if name == "common":
            continue
        counts[name] = {
            "files": 0,
            "suffix": 0,
            "names": 0,
            "env": 0,
            "shebang": 0,
        }
        signatures.setdefault(_signature(rule), []).append(name)

    stack = [root]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    if entry.is_dir(follow_symlinks=False):
                        stack.append(Path(entry.path))
                        continue
                    if not entry.is_file(follow_symlinks=False):
                        continue

                    first = ""
                    suffixes = {part.casefold() for part in Path(entry.name).suffixes}
                    lowered = entry.name.casefold()
                    for name, rule in rules.items():
                        if name == "common":
                            continue
                        current_counts = counts[name]

                        if rule.detect_names and lowered in {
                            item.casefold() for item in rule.detect_names
                        }:
                            current_counts["names"] += 1

                        if rule.detect_files and entry.name in rule.detect_files:
                            current_counts["files"] += 1

                        if rule.detect_suffix and any(
                            suffix.casefold() in suffixes
                            for suffix in rule.detect_suffix
                        ):
                            current_counts["suffix"] += 1

                        if rule.detect_env or rule.detect_shebang:
                            if not first:
                                first = _read_head(Path(entry.path))
                            if first:
                                if rule.detect_shebang and first in rule.detect_shebang:
                                    current_counts["shebang"] += 1
                                if rule.detect_env and first.startswith("#!"):
                                    for value in rule.detect_env:
                                        if f"env {value}" in first or first.endswith(
                                            f"/{value}"
                                        ):
                                            current_counts["env"] += 1
                                            break
        except FileNotFoundError:
            continue

    detected: dict[str, Detect] = {}
    for name, current in counts.items():
        if not any(current.values()):
            continue
        detected[name] = Detect(
            files=current["files"],
            suffix=current["suffix"],
            names=current["names"],
            env=current["env"],
            shebang=current["shebang"],
        )

    kept: dict[str, Detect] = {}
    for names in signatures.values():
        present = [name for name in names if name in detected]
        if not present:
            continue
        priority = min(rules[name].priority for name in present)
        for name in present:
            if rules[name].priority == priority:
                kept[name] = detected[name]

    ordered: dict[str, Detect] = {}
    for name in sorted(kept):
        ordered[name] = kept[name]
    if "common" in rules:
        ordered["common"] = Detect(files=0, suffix=0, names=0, env=0, shebang=0)
    return ordered


def find_matches(
    root: Path, selected_types: list[str], available_rules: dict[str, TypeRules]
) -> list[Match]:
    matches: list[Match] = []
    seen: set[Path] = set()
    ancestor_cache: dict[tuple[str, Path], bool] = {}

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

    def allowed(path: Path, type_name: str) -> bool:
        rule = available_rules[type_name]
        if not rule.require_ancestor:
            return True
        if not rule.detect_suffix:
            return True
        current = path if path.is_dir() else path.parent
        key = (type_name, current)
        if key not in ancestor_cache:
            ancestor_cache[key] = _has_ancestor_suffix(
                current, root, rule.detect_suffix, {}
            )
        return ancestor_cache[key]

    def stopword(path: Path, relative: str) -> bool:
        for type_name in selected_types:
            rules = available_rules[type_name]
            for pattern in rules.paths:
                if _path_matches(relative, pattern) and allowed(path, type_name):
                    return True
            for pattern in rules.dirs:
                if fnmatch.fnmatchcase(path.name, pattern) and allowed(path, type_name):
                    return True
        return False

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
                        blocked = stopword(entry_path, relative)
                        for type_name in selected_types:
                            rules = available_rules[type_name]
                            for pattern in rules.paths:
                                if _path_matches(relative, pattern):
                                    if not allowed(entry_path, type_name):
                                        continue
                                    add_match(entry_path, "dir", type_name, pattern)
                                    pruned = True
                                    break
                            if pruned:
                                break
                            for pattern in rules.dirs:
                                if fnmatch.fnmatchcase(entry.name, pattern):
                                    if not allowed(entry_path, type_name):
                                        continue
                                    add_match(entry_path, "dir", type_name, pattern)
                                    pruned = True
                                    break
                            if pruned:
                                break

                        if not pruned and not blocked:
                            stack.append(entry_path)
                        continue

                    if not entry.is_file(follow_symlinks=False):
                        continue

                    for type_name in selected_types:
                        rules = available_rules[type_name]
                        matched = False
                        for pattern in rules.paths:
                            if _path_matches(relative, pattern):
                                if not allowed(entry_path, type_name):
                                    continue
                                add_match(entry_path, "file", type_name, pattern)
                                matched = True
                                break
                        if matched:
                            break
                        for pattern in rules.files:
                            if fnmatch.fnmatchcase(entry.name, pattern):
                                if not allowed(entry_path, type_name):
                                    continue
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

    stack = [(root, False)]
    while stack:
        current, blocked = stack.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    entry_path = Path(entry.path)
                    resolved = entry_path.resolve()
                    is_matched = resolved in matched

                    if entry.is_dir(follow_symlinks=False):
                        total_dirs += 1
                        child_blocked = blocked or is_matched
                        if not child_blocked:
                            clean_dirs += 1
                        stack.append((entry_path, child_blocked))
                        continue

                    if not entry.is_file(follow_symlinks=False):
                        continue

                    size_bytes = entry.stat(follow_symlinks=False).st_size
                    total_files += 1
                    total_bytes += size_bytes
                    if not blocked and not is_matched:
                        clean_files += 1
                        clean_bytes += size_bytes
        except FileNotFoundError:
            continue

    return Summary(
        total_files=total_files,
        total_dirs=total_dirs,
        total_bytes=total_bytes,
        clean_files=clean_files,
        clean_dirs=clean_dirs,
        clean_bytes=clean_bytes,
    )
