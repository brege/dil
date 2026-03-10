from __future__ import annotations

from importlib import resources
from pathlib import Path
import tomllib
from typing import cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class DetectRules(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    files: tuple[str, ...] = ()
    suffix: tuple[str, ...] = ()
    names: tuple[str, ...] = ()
    env: tuple[str, ...] = ()
    shebang: tuple[str, ...] = ()

    def merge(self, other: DetectRules, drop: DetectRules) -> DetectRules:
        return self.model_copy(
            update={
                "files": _merge_values(self.files, other.files, drop.files),
                "suffix": _merge_values(self.suffix, other.suffix, drop.suffix),
                "names": _merge_values(self.names, other.names, drop.names),
                "env": _merge_values(self.env, other.env, drop.env),
                "shebang": _merge_values(self.shebang, other.shebang, drop.shebang),
            }
        )


class TypeRules(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    priority: int = 99
    require_ancestor: bool = Field(False, alias="require-ancestor")
    dirs: tuple[str, ...] = ()
    files: tuple[str, ...] = ()
    paths: tuple[str, ...] = ()
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
    dirs: tuple[str, ...] = ()
    files: tuple[str, ...] = ()
    paths: tuple[str, ...] = ()
    detect: DetectRules = DetectRules()
    drop_dirs: tuple[str, ...] = Field((), alias="drop-dirs")
    drop_files: tuple[str, ...] = Field((), alias="drop-files")
    drop_paths: tuple[str, ...] = Field((), alias="drop-paths")
    suppress_detect: DetectRules = Field(
        default_factory=DetectRules, alias="suppress-detect"
    )

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
                "dirs": _merge_values(current.dirs, self.dirs, self.drop_dirs),
                "files": _merge_values(current.files, self.files, self.drop_files),
                "paths": _merge_values(current.paths, self.paths, self.drop_paths),
                "detect": current.detect.merge(self.detect, self.suppress_detect),
            }
        )


POLICY_FIELDS = (
    "dirs",
    "files",
    "paths",
    "detect_files",
    "detect_suffix",
    "detect_names",
    "detect_env",
    "detect_shebang",
)


def _merge_values(
    base: tuple[str, ...], add: tuple[str, ...], drop: tuple[str, ...]
) -> tuple[str, ...]:
    blocked = set(drop)
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


def _coerce_patch(name: str, value: object, source: str) -> TypePatch:
    if not isinstance(value, dict):
        raise ValueError(f"invalid rule table in {source}")
    try:
        return TypePatch.model_validate(value)
    except ValidationError as err:
        raise ValueError(f"{source}: invalid {name} rules") from err


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


def _load_policy_patches(path: Path, raw: dict[str, object]) -> dict[str, TypePatch]:
    types = raw.get("type")
    if not isinstance(types, dict):
        raise ValueError(f"invalid type table in {path}")
    type_map = cast(dict[str, object], types)

    loaded: dict[str, TypePatch] = {}
    for name, value in type_map.items():
        if not isinstance(value, dict):
            raise ValueError(f"invalid type entry in {path}: {name}")
        table = cast(dict[str, object], value)
        add = _policy_table(table.get("add"), str(path), f"{name}.add")
        drop = _policy_table(table.get("drop"), str(path), f"{name}.drop")
        try:
            loaded[name] = TypePatch.model_validate(
                {
                    "priority": table.get("priority"),
                    "require-ancestor": table.get("require-ancestor"),
                    "dirs": add["dirs"],
                    "files": add["files"],
                    "paths": add["paths"],
                    "detect": {
                        "files": add["detect_files"],
                        "suffix": add["detect_suffix"],
                        "names": add["detect_names"],
                        "env": add["detect_env"],
                        "shebang": add["detect_shebang"],
                    },
                    "drop-dirs": drop["dirs"],
                    "drop-files": drop["files"],
                    "drop-paths": drop["paths"],
                    "suppress-detect": {
                        "files": drop["detect_files"],
                        "suffix": drop["detect_suffix"],
                        "names": drop["detect_names"],
                        "env": drop["detect_env"],
                        "shebang": drop["detect_shebang"],
                    },
                }
            )
        except ValidationError as err:
            raise ValueError(f"{path}: invalid {name} rules") from err
    return loaded


def _load_patches(path: Path) -> dict[str, TypePatch]:
    raw = _load_toml(path)
    if "type" in raw:
        return _load_policy_patches(path, raw)

    loaded: dict[str, TypePatch] = {}
    for name, value in raw.items():
        loaded[name] = _coerce_patch(name, value, str(path))
    return loaded


def load_rules(root: Path) -> dict[str, TypeRules]:
    loaded = _load_builtin()

    for candidate in _config_candidates(root):
        for name, patch in _load_patches(candidate).items():
            loaded[name] = patch.apply(loaded.get(name))

    return loaded
