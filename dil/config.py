from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import cast
import tomllib


@dataclass(frozen=True)
class TypeRules:
    dirs: tuple[str, ...]
    files: tuple[str, ...]
    paths: tuple[str, ...]


def _load_toml(path: Path) -> dict[str, object]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _coerce_list(value: object, source: str, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{source}: {field} must be a list of strings")
    return tuple(cast(list[str], value))


def _coerce_rules(raw: object, source: str) -> TypeRules:
    if not isinstance(raw, dict):
        raise ValueError(f"invalid rule table in {source}")

    table = cast(dict[str, object], raw)
    return TypeRules(
        dirs=_coerce_list(table.get("dirs", []), source, "dirs"),
        files=_coerce_list(table.get("files", []), source, "files"),
        paths=_coerce_list(table.get("paths", []), source, "paths"),
    )


def _merge_rules(base: TypeRules, override: TypeRules) -> TypeRules:
    return TypeRules(
        dirs=base.dirs + override.dirs,
        files=base.files + override.files,
        paths=base.paths + override.paths,
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

    loaded: dict[str, TypeRules] = {
        name: _coerce_rules(value, "built-in rules")
        for name, value in raw_rules.items()
    }

    for candidate in _config_candidates(root):
        for name, value in _load_toml(candidate).items():
            override = _coerce_rules(value, str(candidate))
            if name in loaded:
                loaded[name] = _merge_rules(loaded[name], override)
            else:
                loaded[name] = override

    return loaded
