from pathlib import Path
import argparse
import json
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "data" / "state.json"
SOURCES = {
    "kondo": (
        "https://raw.githubusercontent.com/tbillington/kondo/master/kondo-lib/src/lib.rs",
        ROOT / "data" / "kondo" / "lib.rs",
    ),
    "tokei": (
        "https://raw.githubusercontent.com/XAMPPRocky/tokei/master/languages.json",
        ROOT / "data" / "tokei" / "languages.json",
    ),
}


def build() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Refresh cached upstream files")
    parser.add_argument("names", nargs="*", choices=sorted(SOURCES))
    parser.add_argument("--check", action="store_true")
    return parser


def read(url: str) -> str:
    with urlopen(url) as response:
        return response.read().decode()


def load() -> dict[str, dict[str, str]]:
    if not STATE.is_file():
        return {}
    return json.loads(STATE.read_text())


def save(state: dict[str, dict[str, str]]) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def sync(names: list[str] | None = None, check: bool = False) -> bool:
    chosen = names or sorted(SOURCES)
    state = load()
    changed = False

    for name in chosen:
        url, path = SOURCES[name]
        text = read(url)
        current = path.read_text() if path.is_file() else ""
        fresh = current != text
        changed = changed or fresh
        if fresh and not check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        state[name] = {
            "path": str(path.relative_to(ROOT)),
            "status": "changed" if fresh else "unchanged",
            "url": url,
        }
        print(f"{name}: {'changed' if fresh else 'unchanged'}")

    if not check:
        save(state)

    return changed


def main() -> int:
    args = build().parse_args()
    changed = sync(args.names, args.check)
    return 1 if args.check and changed else 0


if __name__ == "__main__":
    raise SystemExit(main())
