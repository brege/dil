from __future__ import annotations

from importlib import resources
from pathlib import Path
import tomllib

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class DetectRules(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    files: tuple[str, ...] = ()
    suffix: tuple[str, ...] = ()
    names: tuple[str, ...] = ()
    env: tuple[str, ...] = ()
    shebang: tuple[str, ...] = ()


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

    def merge(self, other: TypeRules) -> TypeRules:
        return self.model_copy(
            update={
                "dirs": self.dirs + other.dirs,
                "files": self.files + other.files,
                "paths": self.paths + other.paths,
            }
        )


def _load_toml(path: Path) -> dict[str, object]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _config_candidates(root: Path) -> list[Path]:
    candidates: list[Path] = []
    config_home = Path.home() / ".config" / "dil" / "config.toml"
    if config_home.is_file():
        candidates.append(config_home)

    local = root / ".dil.toml"
    if local.is_file():
        candidates.append(local)

    return candidates


def _coerce_type(name: str, value: object, source: str) -> TypeRules:
    if not isinstance(value, dict):
        raise ValueError(f"invalid rule table in {source}")
    try:
        return TypeRules.model_validate(value)
    except ValidationError as err:
        raise ValueError(f"{source}: invalid {name} rules") from err


def _load_builtin() -> dict[str, TypeRules]:
    package_rules = resources.files("dil").joinpath("rules.toml")
    with package_rules.open("rb") as handle:
        raw = tomllib.load(handle)

    loaded: dict[str, TypeRules] = {}
    for name, value in raw.items():
        loaded[name] = _coerce_type(name, value, "built-in rules")
    return loaded


def load_rules(root: Path) -> dict[str, TypeRules]:
    loaded = _load_builtin()

    for candidate in _config_candidates(root):
        for name, value in _load_toml(candidate).items():
            override = _coerce_type(name, value, str(candidate))
            if name in loaded:
                loaded[name] = loaded[name].merge(override)
            else:
                loaded[name] = override

    return loaded
