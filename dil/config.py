from __future__ import annotations

from importlib import resources
from pathlib import Path
import tomllib
from typing import cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError


POLICY_FIELDS = (
    "patterns",
    "detect_files",
    "detect_suffix",
    "detect_names",
    "detect_env",
    "detect_shebang",
)


class DetectRules(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    files: tuple[str, ...] = ()
    suffix: tuple[str, ...] = ()
    names: tuple[str, ...] = ()
    env: tuple[str, ...] = ()
    shebang: tuple[str, ...] = ()

    def merge(self, other: DetectRules, removed: DetectRules) -> DetectRules:
        return self.model_copy(
            update={
                "files": _merge_values(self.files, other.files, removed.files),
                "suffix": _merge_values(self.suffix, other.suffix, removed.suffix),
                "names": _merge_values(self.names, other.names, removed.names),
                "env": _merge_values(self.env, other.env, removed.env),
                "shebang": _merge_values(self.shebang, other.shebang, removed.shebang),
            }
        )


class PatchRules(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    patterns: tuple[str, ...] = ()
    detect_files: tuple[str, ...] = ()
    detect_suffix: tuple[str, ...] = ()
    detect_names: tuple[str, ...] = ()
    detect_env: tuple[str, ...] = ()
    detect_shebang: tuple[str, ...] = ()

    @property
    def detect(self) -> DetectRules:
        return DetectRules(
            files=self.detect_files,
            suffix=self.detect_suffix,
            names=self.detect_names,
            env=self.detect_env,
            shebang=self.detect_shebang,
        )


class TypeRules(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    priority: int = 99
    require_ancestor: bool = Field(False, alias="require-ancestor")
    patterns: tuple[str, ...] = ()
    detect: DetectRules = DetectRules()

    @property
    def detect_files(self) -> tuple[str, ...]:
        return self.detect.files

    @property
    def detect_suffix(self) -> tuple[str, ...]:
        return self.detect.suffix

    @property
    def detect_names(self) -> tuple[str, ...]:
        return self.detect.names

    @property
    def detect_env(self) -> tuple[str, ...]:
        return self.detect.env

    @property
    def detect_shebang(self) -> tuple[str, ...]:
        return self.detect.shebang


class TypePatch(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    priority: int | None = None
    require_ancestor: bool | None = Field(None, alias="require-ancestor")
    add: PatchRules = Field(default_factory=PatchRules)
    rm: PatchRules = Field(default_factory=PatchRules)

    def apply(self, base: TypeRules | None) -> TypeRules:
        current = base or TypeRules()
        return current.model_copy(
            update={
                "priority": current.priority
                if self.priority is None
                else self.priority,
                "require_ancestor": (
                    current.require_ancestor
                    if self.require_ancestor is None
                    else self.require_ancestor
                ),
                "patterns": _merge_values(
                    current.patterns, self.add.patterns, self.rm.patterns
                ),
                "detect": current.detect.merge(self.add.detect, self.rm.detect),
            }
        )


def _merge_values(
    base: tuple[str, ...], add: tuple[str, ...], removed: tuple[str, ...]
) -> tuple[str, ...]:
    blocked = set(removed)
    merged: list[str] = []
    seen: set[str] = set()
    for item in (*base, *add):
        if item in seen or item in blocked:
            continue
        seen.add(item)
        merged.append(item)
    return tuple(merged)


def _load_toml(path: Path) -> dict[str, object]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _config_candidates(root: Path) -> list[Path]:
    candidates: list[Path] = []
    config_home = Path.home() / ".config" / "dil" / "config.toml"
    if config_home.is_file():
        candidates.append(config_home)

    local = root / "dil.toml"
    if local.is_file():
        candidates.append(local)

    return candidates


def _load_builtin() -> dict[str, TypeRules]:
    package_rules = resources.files("dil").joinpath("rules.toml")
    with package_rules.open("rb") as handle:
        raw = tomllib.load(handle)

    loaded: dict[str, TypeRules] = {}
    for name, value in raw.items():
        if not isinstance(value, dict):
            raise ValueError("invalid rule table in built-in rules")
        try:
            loaded[name] = TypeRules.model_validate(value)
        except ValidationError as err:
            raise ValueError(f"built-in rules: invalid {name} rules") from err
    return loaded


def _policy_table(value: object, source: str, field: str) -> dict[str, tuple[str, ...]]:
    if value is None:
        return {name: () for name in POLICY_FIELDS}
    if not isinstance(value, dict):
        raise ValueError(f"{source}: invalid {field} table")
    table = cast(dict[str, object], value)
    loaded: dict[str, tuple[str, ...]] = {}
    for name in POLICY_FIELDS:
        items = table.get(name, [])
        if not isinstance(items, list) or any(
            not isinstance(item, str) for item in items
        ):
            raise ValueError(f"{source}: {field}.{name} must be a list of strings")
        loaded[name] = tuple(cast(list[str], items))
    return loaded


def _patch_from_table(path: Path, name: str, value: object) -> TypePatch:
    if not isinstance(value, dict):
        raise ValueError(f"invalid type entry in {path}: {name}")
    table = cast(dict[str, object], value)
    add = _policy_table(table.get("add"), str(path), f"{name}.add")
    removed = _policy_table(table.get("rm"), str(path), f"{name}.rm")
    try:
        return TypePatch.model_validate(
            {
                "priority": table.get("priority"),
                "require-ancestor": table.get("require-ancestor"),
                "add": add,
                "rm": removed,
            }
        )
    except ValidationError as err:
        raise ValueError(f"{path}: invalid {name} rules") from err


def _load_patches(path: Path) -> dict[str, TypePatch]:
    raw = _load_toml(path)
    types = raw.get("type")
    if not isinstance(types, dict):
        raise ValueError(f"invalid type table in {path}")
    return {
        name: _patch_from_table(path, name, value)
        for name, value in cast(dict[str, object], types).items()
    }


def load_rules(root: Path) -> dict[str, TypeRules]:
    loaded = _load_builtin()

    for candidate in _config_candidates(root):
        for name, patch in _load_patches(candidate).items():
            loaded[name] = patch.apply(loaded.get(name))

    return loaded
