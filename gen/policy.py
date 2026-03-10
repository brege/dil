from dataclasses import dataclass
from pathlib import Path
from typing import cast
import tomllib


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "dil.toml"
PRUNE = ("patterns",)
DETECT = (
    "detect_files",
    "detect_suffix",
    "detect_names",
    "detect_env",
    "detect_shebang",
)
FIELDS = PRUNE + DETECT


@dataclass(frozen=True)
class Type:
    priority: int
    require_ancestor: bool
    kondo: tuple[str, ...]
    tokei: tuple[str, ...]
    add: dict[str, tuple[str, ...]]
    rm: dict[str, tuple[str, ...]]


def blank() -> dict[str, list[str]]:
    return {field: [] for field in FIELDS}


def _list(value: object, source: str, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise SystemExit(f"error: {source}: {field} must be a list of strings")
    return tuple(cast(list[str], value))


def _priority(value: object, source: str) -> int:
    if value is None:
        return 99
    if not isinstance(value, int):
        raise SystemExit(f"error: {source}: priority must be an integer")
    return value


def _require_ancestor(value: object, source: str) -> bool:
    if value is None:
        return False
    if not isinstance(value, bool):
        raise SystemExit(f"error: {source}: require-ancestor must be a boolean")
    return value


def _table(value: object, source: str) -> dict[str, tuple[str, ...]]:
    if not isinstance(value, dict):
        raise SystemExit(f"error: invalid rule table in {source}")
    table = cast(dict[str, object], value)
    return {field: _list(table.get(field, []), source, field) for field in FIELDS}


def load(path: Path = SOURCE) -> dict[str, Type]:
    if not path.is_file():
        raise SystemExit(f"error: source does not exist: {path}")

    with path.open("rb") as handle:
        raw = tomllib.load(handle)

    types = raw.get("type")
    if not isinstance(types, dict):
        raise SystemExit(f"error: invalid type table in {path}")

    rules: dict[str, Type] = {}
    for name, value in types.items():
        if not isinstance(value, dict):
            raise SystemExit(f"error: invalid type entry in {path}: {name}")
        rules[name] = Type(
            priority=_priority(value.get("priority"), f"{path}:{name}"),
            require_ancestor=_require_ancestor(
                value.get("require-ancestor"), f"{path}:{name}"
            ),
            kondo=_list(value.get("kondo", []), f"{path}:{name}", "kondo"),
            tokei=_list(value.get("tokei", []), f"{path}:{name}", "tokei"),
            add=_table(value.get("add", {}), f"{path}:{name}.add"),
            rm=_table(value.get("rm", {}), f"{path}:{name}.rm"),
        )
    return dict(sorted(rules.items()))
