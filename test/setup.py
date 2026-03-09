from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml


ROOT = Path(__file__).resolve().parent
FIXTURES = ROOT / "fixtures.yml"


def load() -> dict[str, Any]:
    with FIXTURES.open("r", encoding="utf-8") as handle:
        return cast(dict[str, Any], yaml.safe_load(handle))


def build(base: Path, name: str) -> tuple[Path, dict[str, Any]]:
    projects = cast(dict[str, dict[str, Any]], load()["projects"])
    data = projects[name]
    root = base / name
    root.mkdir()
    for entry in cast(list[dict[str, Any]], data["entries"]):
        if "dir" in entry:
            (root / entry["dir"]).mkdir(parents=True, exist_ok=True)
            continue

        path = root / cast(str, entry["file"])
        path.parent.mkdir(parents=True, exist_ok=True)
        if "text" in entry:
            path.write_text(cast(str, entry["text"]), encoding="utf-8")
        else:
            path.write_bytes(b"x" * cast(int, entry["bytes"]))
    return root, cast(dict[str, Any], data["expect"])
