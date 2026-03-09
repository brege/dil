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
    stack = [path.as_posix()]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
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
        with path.open("rb") as handle:
            head = handle.read(128)
    except OSError:
        return ""
    line = head.splitlines()[0] if head else b""
    return line.decode("utf-8", errors="ignore").strip()


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


def _detect_stopword(name: str, relative: str, rules: dict[str, TypeRules]) -> bool:
    for rule in rules.values():
        if rule.priority != 0:
            continue
        for pattern in rule.paths:
            if _path_matches(relative, pattern):
                return True
        for pattern in rule.dirs:
            if fnmatch.fnmatchcase(name, pattern):
                return True
    return False


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
    suffix_map: dict[str, list[str]] = {}
    file_map: dict[str, list[str]] = {}
    name_map: dict[str, list[str]] = {}
    head_types: list[str] = []

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
        for suffix in rule.detect_suffix:
            suffix_map.setdefault(suffix.casefold(), []).append(name)
        for item in rule.detect_files:
            file_map.setdefault(item, []).append(name)
        for item in rule.detect_names:
            name_map.setdefault(item.casefold(), []).append(name)
        if rule.detect_env or rule.detect_shebang:
            head_types.append(name)

    stack = [(root, "")]
    while stack:
        current, base = stack.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name == ".git":
                            continue
                        relative = f"{base}/{entry.name}" if base else entry.name
                        if not _detect_stopword(entry.name, relative, rules):
                            stack.append((Path(entry.path), relative))
                        continue
                    if not entry.is_file(follow_symlinks=False):
                        continue

                    suffixes = {part.casefold() for part in Path(entry.name).suffixes}
                    lowered = entry.name.casefold()
                    for name in file_map.get(entry.name, []):
                        counts[name]["files"] += 1

                    for name in name_map.get(lowered, []):
                        counts[name]["names"] += 1

                    seen_suffix: set[str] = set()
                    for suffix in suffixes:
                        for name in suffix_map.get(suffix, []):
                            if name in seen_suffix:
                                continue
                            counts[name]["suffix"] += 1
                            seen_suffix.add(name)

                    if suffixes or not head_types:
                        continue

                    first = _read_head(Path(entry.path))
                    if not first:
                        continue
                    for name in head_types:
                        rule = rules[name]
                        current_counts = counts[name]
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
    root: Path,
    selected_types: list[str],
    available_rules: dict[str, TypeRules],
    with_size: bool = False,
) -> list[Match]:
    matches: list[Match] = []
    seen: set[str] = set()
    ancestor_cache: dict[tuple[str, Path], bool] = {}

    def add_match(path: Path, kind: str, rule_type: str, rule_value: str) -> None:
        key = path.as_posix()
        if key in seen:
            return
        seen.add(key)
        if with_size:
            size_bytes = _directory_size(path) if kind == "dir" else path.stat().st_size
        else:
            size_bytes = 0
        matches.append(
            Match(
                path=path,
                kind=kind,
                rule_type=rule_type,
                rule_value=rule_value,
                size_bytes=size_bytes,
            )
        )

    def allowed(path: Path, type_name: str, is_dir: bool) -> bool:
        rule = available_rules[type_name]
        if not rule.require_ancestor:
            return True
        if not rule.detect_suffix:
            return True
        current = path if is_dir else path.parent
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
                if _path_matches(relative, pattern) and allowed(path, type_name, True):
                    return True
            for pattern in rules.dirs:
                if fnmatch.fnmatchcase(path.name, pattern) and allowed(
                    path, type_name, True
                ):
                    return True
        return False

    stack = [(root, "")]
    while stack:
        current, base = stack.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    relative = f"{base}/{entry.name}" if base else entry.name
                    pruned = False

                    if entry.is_dir(follow_symlinks=False):
                        if entry.name == ".git":
                            continue
                        entry_path = Path(entry.path)
                        blocked = stopword(entry_path, relative)
                        for type_name in selected_types:
                            rules = available_rules[type_name]
                            for pattern in rules.paths:
                                if _path_matches(relative, pattern):
                                    if not allowed(entry_path, type_name, True):
                                        continue
                                    add_match(entry_path, "dir", type_name, pattern)
                                    pruned = True
                                    break
                            if pruned:
                                break
                            for pattern in rules.dirs:
                                if fnmatch.fnmatchcase(entry.name, pattern):
                                    if not allowed(entry_path, type_name, True):
                                        continue
                                    add_match(entry_path, "dir", type_name, pattern)
                                    pruned = True
                                    break
                            if pruned:
                                break

                        if not pruned and not blocked:
                            stack.append((entry_path, relative))
                        continue

                    if not entry.is_file(follow_symlinks=False):
                        continue

                    for type_name in selected_types:
                        rules = available_rules[type_name]
                        matched = False
                        for pattern in rules.paths:
                            if _path_matches(relative, pattern):
                                entry_path = Path(entry.path)
                                if not allowed(entry_path, type_name, False):
                                    continue
                                add_match(entry_path, "file", type_name, pattern)
                                matched = True
                                break
                        if matched:
                            break
                        for pattern in rules.files:
                            if fnmatch.fnmatchcase(entry.name, pattern):
                                entry_path = Path(entry.path)
                                if not allowed(entry_path, type_name, False):
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
