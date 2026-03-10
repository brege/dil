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


@dataclass(frozen=True)
class Sig:
    files: tuple[str, ...]
    suffix: tuple[str, ...]
    names: tuple[str, ...]
    env: tuple[str, ...]
    shebang: tuple[str, ...]


def _path_matches(path: str, pattern: str) -> bool:
    return fnmatch.fnmatchcase(path.strip("/"), pattern.strip("/"))


def _rule_matches(name: str, relative: str, pattern: str, *, is_dir: bool) -> bool:
    rule = pattern.strip()
    if not rule:
        return False

    dir_only = rule.endswith("/")
    if dir_only and not is_dir:
        return False

    target = rule.rstrip("/")
    if "/" in target:
        return _path_matches(relative, target)
    return fnmatch.fnmatchcase(name, target)


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


def _read_head(path: Path) -> str:
    try:
        with path.open("rb") as handle:
            head = handle.read(128)
    except OSError:
        return ""
    line = head.splitlines()[0] if head else b""
    return line.decode("utf-8", errors="ignore").strip()


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


class Index:
    def __init__(self, rules: dict[str, TypeRules]) -> None:
        self.rules = rules
        self.signatures: dict[Sig, list[str]] = {}
        self.suffix_map: dict[str, list[str]] = {}
        self.file_map: dict[str, list[str]] = {}
        self.name_map: dict[str, list[str]] = {}
        self.head_types: list[str] = []
        self.stop_patterns: list[tuple[str, ...]] = []

        for name, rule in rules.items():
            if rule.priority == 0:
                self.stop_patterns.append(rule.patterns)

            if name == "common":
                continue

            sig = Sig(
                tuple(sorted(rule.detect_files)),
                tuple(sorted(rule.detect_suffix)),
                tuple(sorted(rule.detect_names)),
                tuple(sorted(rule.detect_env)),
                tuple(sorted(rule.detect_shebang)),
            )
            self.signatures.setdefault(sig, []).append(name)

            for suffix in rule.detect_suffix:
                self.suffix_map.setdefault(suffix.casefold(), []).append(name)
            for item in rule.detect_files:
                self.file_map.setdefault(item, []).append(name)
            for item in rule.detect_names:
                self.name_map.setdefault(item.casefold(), []).append(name)
            if rule.detect_env or rule.detect_shebang:
                self.head_types.append(name)

    def stopword(self, name: str, relative: str) -> bool:
        for patterns in self.stop_patterns:
            for pattern in patterns:
                if _rule_matches(name, relative, pattern, is_dir=True):
                    return True
        return False


class Detector:
    def __init__(self, root: Path, index: Index) -> None:
        self.root = root
        self.index = index
        self.counts = {
            name: {"files": 0, "suffix": 0, "names": 0, "env": 0, "shebang": 0}
            for name in index.rules
            if name != "common"
        }

    def run(self) -> dict[str, Detect]:
        stack = [(self.root, "")]
        while stack:
            current, base = stack.pop()
            try:
                with os.scandir(current) as entries:
                    for entry in entries:
                        if entry.is_dir(follow_symlinks=False):
                            if entry.name == ".git":
                                continue
                            relative = f"{base}/{entry.name}" if base else entry.name
                            if not self.index.stopword(entry.name, relative):
                                stack.append((Path(entry.path), relative))
                            continue
                        if not entry.is_file(follow_symlinks=False):
                            continue
                        self._add_file(entry)
            except FileNotFoundError:
                continue
        return self._finish()

    def _add_file(self, entry: os.DirEntry[str]) -> None:
        suffixes = {part.casefold() for part in Path(entry.name).suffixes}
        lowered = entry.name.casefold()

        for name in self.index.file_map.get(entry.name, []):
            self.counts[name]["files"] += 1
        for name in self.index.name_map.get(lowered, []):
            self.counts[name]["names"] += 1

        seen: set[str] = set()
        for suffix in suffixes:
            for name in self.index.suffix_map.get(suffix, []):
                if name in seen:
                    continue
                self.counts[name]["suffix"] += 1
                seen.add(name)

        if suffixes or not self.index.head_types:
            return

        first = _read_head(Path(entry.path))
        if not first:
            return

        for name in self.index.head_types:
            rule = self.index.rules[name]
            count = self.counts[name]
            if rule.detect_shebang and first in rule.detect_shebang:
                count["shebang"] += 1
            if rule.detect_env and first.startswith("#!"):
                for value in rule.detect_env:
                    if f"env {value}" in first or first.endswith(f"/{value}"):
                        count["env"] += 1
                        break

    def _finish(self) -> dict[str, Detect]:
        detected: dict[str, Detect] = {}
        for name, count in self.counts.items():
            if not any(count.values()):
                continue
            detected[name] = Detect(
                files=count["files"],
                suffix=count["suffix"],
                names=count["names"],
                env=count["env"],
                shebang=count["shebang"],
            )

        kept: dict[str, Detect] = {}
        for names in self.index.signatures.values():
            present = [name for name in names if name in detected]
            if not present:
                continue
            priority = min(self.index.rules[name].priority for name in present)
            for name in present:
                if self.index.rules[name].priority == priority:
                    kept[name] = detected[name]

        ordered = {name: kept[name] for name in sorted(kept)}
        if "common" in self.index.rules:
            ordered["common"] = Detect(0, 0, 0, 0, 0)
        return ordered


class Matcher:
    def __init__(
        self,
        root: Path,
        selected: list[str],
        rules: dict[str, TypeRules],
        *,
        with_size: bool,
    ) -> None:
        self.root = root
        self.selected = selected
        self.rules = rules
        self.with_size = with_size
        self.matches: list[Match] = []
        self.seen: set[str] = set()
        self.ancestor: dict[tuple[str, Path], bool] = {}

    def run(self) -> list[Match]:
        stack = [(self.root, "")]
        while stack:
            current, base = stack.pop()
            try:
                with os.scandir(current) as entries:
                    for entry in entries:
                        relative = f"{base}/{entry.name}" if base else entry.name
                        if entry.is_dir(follow_symlinks=False):
                            if entry.name == ".git":
                                continue
                            path = Path(entry.path)
                            pruned = self._dir(path, entry.name, relative)
                            if not pruned and not self._stopword(path, relative):
                                stack.append((path, relative))
                            continue
                        if entry.is_file(follow_symlinks=False):
                            self._file(Path(entry.path), entry.name, relative)
            except FileNotFoundError:
                continue

        self.matches.sort(key=lambda item: item.path.as_posix())
        return self.matches

    def _dir(self, path: Path, name: str, relative: str) -> bool:
        for type_name in self.selected:
            rule = self.rules[type_name]
            for pattern in rule.patterns:
                if not _rule_matches(name, relative, pattern, is_dir=True):
                    continue
                if not self._allowed(path, type_name, True):
                    continue
                self._add(path, "dir", type_name, pattern)
                return True
        return False

    def _file(self, path: Path, name: str, relative: str) -> None:
        for type_name in self.selected:
            rule = self.rules[type_name]
            for pattern in rule.patterns:
                if not _rule_matches(name, relative, pattern, is_dir=False):
                    continue
                if not self._allowed(path, type_name, False):
                    continue
                self._add(path, "file", type_name, pattern)
                return

    def _stopword(self, path: Path, relative: str) -> bool:
        for type_name in self.selected:
            rule = self.rules[type_name]
            for pattern in rule.patterns:
                if not _rule_matches(path.name, relative, pattern, is_dir=True):
                    continue
                if self._allowed(path, type_name, True):
                    return True
        return False

    def _allowed(self, path: Path, type_name: str, is_dir: bool) -> bool:
        rule = self.rules[type_name]
        if not rule.require_ancestor or not rule.detect_suffix:
            return True
        current = path if is_dir else path.parent
        key = (type_name, current)
        if key not in self.ancestor:
            self.ancestor[key] = _has_ancestor_suffix(
                current, self.root, rule.detect_suffix, {}
            )
        return self.ancestor[key]

    def _add(self, path: Path, kind: str, rule_type: str, rule_value: str) -> None:
        key = path.as_posix()
        if key in self.seen:
            return
        self.seen.add(key)
        size_bytes = 0
        if self.with_size:
            size_bytes = _directory_size(path) if kind == "dir" else path.stat().st_size
        self.matches.append(Match(path, kind, rule_type, rule_value, size_bytes))


class Sizer:
    def __init__(self, root: Path, matches: list[Match]) -> None:
        self.root = root
        self.matched = {match.path.resolve() for match in matches}

    def run(self) -> Summary:
        total_files = 0
        total_dirs = 1
        total_bytes = 0
        clean_files = 0
        clean_dirs = 1
        clean_bytes = 0

        stack = [(self.root, False)]
        while stack:
            current, blocked = stack.pop()
            try:
                with os.scandir(current) as entries:
                    for entry in entries:
                        path = Path(entry.path)
                        resolved = path.resolve()
                        is_matched = resolved in self.matched

                        if entry.is_dir(follow_symlinks=False):
                            total_dirs += 1
                            child_blocked = blocked or is_matched
                            if not child_blocked:
                                clean_dirs += 1
                            stack.append((path, child_blocked))
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


def detect_types(root: Path, rules: dict[str, TypeRules]) -> dict[str, Detect]:
    return Detector(root, Index(rules)).run()


def find_matches(
    root: Path,
    selected_types: list[str],
    available_rules: dict[str, TypeRules],
    with_size: bool = False,
) -> list[Match]:
    return Matcher(root, selected_types, available_rules, with_size=with_size).run()


def summarize(root: Path, matches: list[Match]) -> Summary:
    return Sizer(root, matches).run()
