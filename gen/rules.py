from pathlib import Path
import argparse
from difflib import unified_diff
import sys

import tomlkit
from tomlkit.items import Array

from gen import kondo
from gen import refs
from gen import tokei
from gen.policy import DETECT
from gen.policy import PRUNE
from gen.policy import SOURCE as POLICY
from gen.policy import load


ROOT = Path(__file__).resolve().parent.parent
KONDO = ROOT / "data" / "kondo" / "lib.rs"
TOKEI = ROOT / "data" / "tokei" / "languages.json"
TARGET = ROOT / "dil" / "rules.toml"


def build() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build dil rules from cached data")
    parser.add_argument("--kondo", type=Path, default=KONDO)
    parser.add_argument("--tokei", type=Path, default=TOKEI)
    parser.add_argument("--policy", type=Path, default=POLICY)
    return parser


def merge(
    litter: dict[str, dict[str, list[str]]],
    detect: dict[str, dict[str, list[str]]],
) -> dict[str, dict[str, list[str]]]:
    merged: dict[str, dict[str, list[str]]] = {}
    for name in sorted(set(litter) | set(detect)):
        current = {field: [] for field in PRUNE + DETECT}
        for field in PRUNE:
            current[field] = litter.get(name, {}).get(field, [])
        for field in DETECT:
            current[field] = detect.get(name, {}).get(field, [])
        merged[name] = current
    return merged


def array(items: list[str]) -> Array:
    data = tomlkit.array()
    for item in items:
        data.append(item)
    if len(items) > 1:
        data.multiline(True)
    return data


def render(
    rules: dict[str, dict[str, list[str]]],
    priority: dict[str, int],
    require_ancestor: dict[str, bool],
) -> str:
    doc = tomlkit.document()
    for name, rule in rules.items():
        table = tomlkit.table()
        if priority.get(name, 99) != 99:
            table.add("priority", priority[name])
        if require_ancestor.get(name, False):
            table.add("require-ancestor", True)
        table.add("patterns", array(rule["patterns"]))
        if any(rule[field] for field in DETECT):
            detect_table = tomlkit.table()
            if rule["detect_files"]:
                detect_table.add("files", array(rule["detect_files"]))
            if rule["detect_suffix"]:
                detect_table.add("suffix", array(rule["detect_suffix"]))
            if rule["detect_names"]:
                detect_table.add("names", array(rule["detect_names"]))
            if rule["detect_env"]:
                detect_table.add("env", array(rule["detect_env"]))
            if rule["detect_shebang"]:
                detect_table.add("shebang", array(rule["detect_shebang"]))
            table.add("detect", detect_table)
        doc.add(name, table)
    return tomlkit.dumps(doc)


def diff(path: Path, text: str) -> str:
    current = path.read_text() if path.is_file() else ""
    if current == text:
        return ""
    lines = unified_diff(
        current.splitlines(keepends=True),
        text.splitlines(keepends=True),
        fromfile=str(path),
        tofile=str(path),
    )
    return "".join(lines)


def ensure() -> bool:
    missing: list[str] = []
    if not KONDO.is_file():
        missing.append("kondo")
    if not TOKEI.is_file():
        missing.append("tokei")
    if not missing:
        return False
    return refs.sync(missing)


def main() -> int:
    args = build().parse_args()
    refreshed = ensure()
    litter = kondo.merge(kondo.parse(args.kondo.read_text()), args.policy)
    detect = tokei.merge(tokei.parse(args.tokei), args.policy)
    policy = load(args.policy)
    priority = {name: rule.priority for name, rule in policy.items()}
    require_ancestor = {name: rule.require_ancestor for name, rule in policy.items()}
    text = render(merge(litter, detect), priority, require_ancestor)
    delta = diff(TARGET, text)
    if not delta:
        if refreshed:
            print("refreshed data cache")
        print(f"{TARGET.relative_to(ROOT)} unchanged")
        return 0
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(text)
    if refreshed:
        print("refreshed data cache")
    print(f"updated {TARGET.relative_to(ROOT)}")
    sys.stdout.write(delta)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
