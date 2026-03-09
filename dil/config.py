from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import cast
import tomllib


@dataclass(frozen=True)
class TypeRules:
    priority: int
    require_ancestor: bool
    dirs: tuple[str, ...]
    files: tuple[str, ...]
    paths: tuple[str, ...]
    detect_files: tuple[str, ...]
    detect_suffix: tuple[str, ...]
    detect_names: tuple[str, ...]
    detect_env: tuple[str, ...]
    detect_shebang: tuple[str, ...]


def _load_toml(path: Path) -> dict[str, object]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _coerce_list(value: object, source: str, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{source}: {field} must be a list of strings")
    return tuple(cast(list[str], value))


def _coerce_priority(value: object, source: str) -> int:
    if value is None:
        return 99
    if not isinstance(value, int):
        raise ValueError(f"{source}: priority must be an integer")
    return value


def _coerce_require_ancestor(value: object, source: str) -> bool:
    if value is None:
        return False
    if not isinstance(value, bool):
        raise ValueError(f"{source}: require-ancestor must be a boolean")
    return value


def _coerce_rules(raw: object, source: str) -> TypeRules:
    if not isinstance(raw, dict):
        raise ValueError(f"invalid rule table in {source}")

    table = cast(dict[str, object], raw)
    return TypeRules(
        priority=_coerce_priority(table.get("priority"), source),
        require_ancestor=_coerce_require_ancestor(
            table.get("require-ancestor"), source
        ),
        dirs=_coerce_list(table.get("dirs", []), source, "dirs"),
        files=_coerce_list(table.get("files", []), source, "files"),
        paths=_coerce_list(table.get("paths", []), source, "paths"),
        detect_files=_coerce_list(
            table.get("detect_files", []), source, "detect_files"
        ),
        detect_suffix=_coerce_list(
            table.get("detect_suffix", []), source, "detect_suffix"
        ),
        detect_names=_coerce_list(
            table.get("detect_names", []), source, "detect_names"
        ),
        detect_env=_coerce_list(table.get("detect_env", []), source, "detect_env"),
        detect_shebang=_coerce_list(
            table.get("detect_shebang", []), source, "detect_shebang"
        ),
    )


def _merge_rules(base: TypeRules, override: TypeRules) -> TypeRules:
    return TypeRules(
        priority=base.priority,
        require_ancestor=base.require_ancestor,
        dirs=base.dirs + override.dirs,
        files=base.files + override.files,
        paths=base.paths + override.paths,
        detect_files=base.detect_files,
        detect_suffix=base.detect_suffix,
        detect_names=base.detect_names,
        detect_env=base.detect_env,
        detect_shebang=base.detect_shebang,
    )


def _config_candidates(root: Path) -> list[Path]:
    candidates: list[Path] = []
    config_home = Path.home() / ".config" / "dil" / "config.toml"
    if config_home.is_file():
        candidates.append(config_home)

    local = root / ".dil.toml"
    if local.is_file():
        candidates.append(local)

    return candidates


def load_rules(root: Path) -> dict[str, TypeRules]:
    package_rules = resources.files("dil").joinpath("rules.toml")
    with package_rules.open("rb") as handle:
        raw_rules = tomllib.load(handle)

    loaded: dict[str, TypeRules] = {}
    for name, value in raw_rules.items():
        if not isinstance(value, dict):
            raise ValueError("invalid rule table in built-in rules")
        table = cast(dict[str, object], value)
        detect = table.get("detect", {})
        if not isinstance(detect, dict):
            raise ValueError("invalid rule table in built-in rules")
        detect_table = cast(dict[str, object], detect)
        merged = dict(table)
        merged["detect_files"] = detect_table.get("files", [])
        merged["detect_suffix"] = detect_table.get("suffix", [])
        merged["detect_names"] = detect_table.get("names", [])
        merged["detect_env"] = detect_table.get("env", [])
        merged["detect_shebang"] = detect_table.get("shebang", [])
        loaded[name] = _coerce_rules(merged, "built-in rules")

    for candidate in _config_candidates(root):
        for name, value in _load_toml(candidate).items():
            override = _coerce_rules(value, str(candidate))
            if name in loaded:
                loaded[name] = _merge_rules(loaded[name], override)
            else:
                loaded[name] = override

    return loaded
