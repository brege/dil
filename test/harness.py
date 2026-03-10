from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, cast
import tomllib

import pytest

from dil.config import load_rules
from gen import kondo
from gen.policy import load as load_policy
from gen import rules
from gen import tokei

from . import setup


ROOT = Path(__file__).resolve().parents[1]
PYTHON = shutil.which("python3") or "python3"
CASES = tuple(cast(dict[str, Any], setup.load()["projects"]))
HOME = Path("/tmp/dil-test-home")


def run(
    *args: str, cwd: Path | None = None, stdin: str | None = None
) -> subprocess.CompletedProcess[str]:
    command = [PYTHON, "-m", "dil.cli", *args]
    return subprocess.run(
        command,
        cwd=cwd or ROOT,
        text=True,
        capture_output=True,
        input=stdin,
        env={"HOME": str(HOME), "PYTHONPATH": str(ROOT)},
        check=False,
    )


def run_json(*args: str, cwd: Path | None = None) -> dict[str, Any]:
    result = run("--json", *args, cwd=cwd)
    assert result.returncode == 0
    return cast(dict[str, Any], json.loads(result.stdout))


def make_case(tmp_path: Path, name: str) -> tuple[Path, dict[str, Any]]:
    assert str(tmp_path).startswith("/tmp/")
    return setup.build(tmp_path, name)


def rules_map(payload: dict[str, Any]) -> dict[str, dict[str, dict[str, int]]]:
    grouped: dict[str, dict[str, dict[str, int]]] = {}
    for row in cast(list[dict[str, Any]], payload["rules"]):
        type_name = cast(str, row["type"])
        rule_name = cast(str, row["rule"])
        grouped.setdefault(type_name, {})[rule_name] = {
            "matches": cast(int, row["matches"]),
            "size": cast(int, row["size"]),
        }
    return grouped


def abs_paths(root: Path, paths: list[str]) -> list[str]:
    values: list[str] = []
    for path in paths:
        if path.endswith("/"):
            values.append(f"{root / path[:-1]}/")
        else:
            values.append(str(root / path))
    return values


def assert_kept(root: Path, paths: list[str]) -> None:
    for path in paths:
        assert (root / path).exists()


def assert_gone(root: Path, paths: list[str]) -> None:
    for path in paths:
        assert not (root / path.rstrip("/")).exists()


def assert_present(root: Path, paths: list[str]) -> None:
    for path in paths:
        assert (root / path.rstrip("/")).exists()


@pytest.mark.parametrize("name", CASES)
def test_compact(tmp_path: Path, name: str) -> None:
    root, expect = make_case(tmp_path, name)
    payload = run_json(str(root))
    assert payload["root"] == str(root)
    assert payload["types"] == cast(list[str], expect["types"])
    assert payload["total"] == cast(dict[str, int], expect["total"])
    assert rules_map(payload) == cast(
        dict[str, dict[str, dict[str, int]]], expect["rules"]
    )


@pytest.mark.parametrize("name", CASES)
def test_paths(tmp_path: Path, name: str) -> None:
    root, expect = make_case(tmp_path, name)
    payload = run_json("-p", str(root))
    assert payload["types"] == cast(list[str], expect["types"])
    assert [
        cast(str, row["path"]) for row in cast(list[dict[str, Any]], payload["matches"])
    ] == cast(list[str], expect["paths"])


@pytest.mark.parametrize("name", CASES)
def test_absolute(tmp_path: Path, name: str) -> None:
    root, expect = make_case(tmp_path, name)
    payload = run_json("-P", str(root))
    assert payload["types"] == cast(list[str], expect["types"])
    assert [
        cast(str, row["path"]) for row in cast(list[dict[str, Any]], payload["matches"])
    ] == abs_paths(root, cast(list[str], expect["paths"]))


@pytest.mark.parametrize("name", CASES)
def test_dry(tmp_path: Path, name: str) -> None:
    root, expect = make_case(tmp_path, name)
    payload = run_json("-d", "-n", str(root))
    assert payload["types"] == cast(list[str], expect["types"])
    assert [
        cast(str, row["path"]) for row in cast(list[dict[str, Any]], payload["matches"])
    ] == cast(list[str], expect["paths"])
    assert_present(root, cast(list[str], expect["paths"]))
    assert_kept(root, cast(list[str], expect["keep"]))


@pytest.mark.parametrize("name", CASES)
def test_dry_absolute(tmp_path: Path, name: str) -> None:
    root, expect = make_case(tmp_path, name)
    payload = run_json("-d", "-n", "-P", str(root))
    assert payload["types"] == cast(list[str], expect["types"])
    assert [
        cast(str, row["path"]) for row in cast(list[dict[str, Any]], payload["matches"])
    ] == abs_paths(root, cast(list[str], expect["paths"]))
    assert_present(root, cast(list[str], expect["paths"]))
    assert_kept(root, cast(list[str], expect["keep"]))


@pytest.mark.parametrize("name", CASES)
def test_delete(tmp_path: Path, name: str) -> None:
    root, expect = make_case(tmp_path, name)
    result = run("-d", "-y", str(root))
    assert result.returncode == 0
    assert_gone(root, cast(list[str], expect["paths"]))
    assert_kept(root, cast(list[str], expect["keep"]))


def test_prompt_abort(tmp_path: Path) -> None:
    root, expect = make_case(tmp_path, "python")
    result = run("-d", str(root), stdin="\n")
    assert result.returncode == 0
    assert "__pycache__/" in result.stdout
    assert str(root / "__pycache__") not in result.stdout
    assert_present(root, cast(list[str], expect["paths"]))
    assert_kept(root, cast(list[str], expect["keep"]))


def test_prompt_abort_absolute(tmp_path: Path) -> None:
    root, expect = make_case(tmp_path, "python")
    result = run("-d", "-P", str(root), stdin="\n")
    assert result.returncode == 0
    assert "/tmp/" in result.stdout
    assert "__pycache__" in result.stdout
    assert_present(root, cast(list[str], expect["paths"]))
    assert_kept(root, cast(list[str], expect["keep"]))


def test_delete_paths_flag(tmp_path: Path) -> None:
    root, expect = make_case(tmp_path, "common")
    result = run("-d", "-p", "-y", str(root))
    assert result.returncode == 0
    assert_gone(root, cast(list[str], expect["paths"]))
    assert_kept(root, cast(list[str], expect["keep"]))


def test_prompt_delete(tmp_path: Path) -> None:
    root, expect = make_case(tmp_path, "common")
    result = run("-d", str(root), stdin="y\n")
    assert result.returncode == 0
    assert_gone(root, cast(list[str], expect["paths"]))
    assert_kept(root, cast(list[str], expect["keep"]))


def test_short_dry(tmp_path: Path) -> None:
    root, expect = make_case(tmp_path, "aoife")
    result = run("-d", "-n", "-s", str(root))
    assert result.returncode == 0
    assert "node_modules/" in result.stdout
    assert str(root / "node_modules") not in result.stdout
    assert_present(root, cast(list[str], expect["paths"]))
    assert_kept(root, cast(list[str], expect["keep"]))


def test_short_dry_absolute(tmp_path: Path) -> None:
    root, expect = make_case(tmp_path, "aoife")
    result = run("-d", "-n", "-s", "-P", str(root))
    assert result.returncode == 0
    assert f"{root / 'node_modules'}/" in result.stdout
    assert_present(root, cast(list[str], expect["paths"]))
    assert_kept(root, cast(list[str], expect["keep"]))


@pytest.mark.parametrize("args", [(), ("-p",), ("-P",), ("-d", "-n")])
def test_empty_output_message(tmp_path: Path, args: tuple[str, ...]) -> None:
    root, expect = make_case(tmp_path, "docs")
    result = run(*args, str(root))
    assert result.returncode == 0
    assert result.stdout.strip() == "No files detected to delete."
    assert result.stderr == ""
    assert_kept(root, cast(list[str], expect["keep"]))


def test_repo_dil_toml_loads(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    ruleset = load_rules(ROOT)

    assert "python" in ruleset
    assert ruleset["python"].patterns.count(".uv-cache/") == 1
    assert ruleset["node"].detect_env.count("node") == 1


def test_local_dil_toml_add_and_rm(tmp_path: Path) -> None:
    root, _ = make_case(tmp_path, "python")
    extra = root / ".cachekeep"
    extra.mkdir()
    (extra / "cache.bin").write_bytes(b"x")
    (root / "dil.toml").write_text(
        (
            "[type.python.add]\n"
            'patterns = [".cachekeep/"]\n'
            "\n"
            "[type.python.rm]\n"
            'patterns = [".pytest_cache/", "__pycache__/", ".uv-cache/", ".uv-cache/**", "*.pyc"]\n'
        ),
        encoding="utf-8",
    )

    payload = run_json(str(root))

    assert payload["types"] == ["python"]
    assert [
        cast(str, row["path"]) for row in cast(list[dict[str, Any]], payload["matches"])
    ] == [".cachekeep/"]


def test_local_dil_toml_suppress_detect(tmp_path: Path) -> None:
    root, _ = make_case(tmp_path, "python")
    (root / "dil.toml").write_text(
        (
            "[type.python.rm]\n"
            'detect_suffix = [".py", ".pyw", ".pyi"]\n'
            'detect_env = ["python", "python2", "python3"]\n'
        ),
        encoding="utf-8",
    )

    payload = run_json(str(root))

    assert payload["types"] == []
    assert payload["matches"] == []
    assert payload["rules"] == []
    assert payload["total"] == {"matches": 0, "size": 0}


def test_rules(tmp_path: Path) -> None:
    rules.ensure()
    litter = kondo.merge(kondo.parse(kondo.SOURCE.read_text()), kondo.POLICY)
    detect = tokei.merge(tokei.parse(tokei.SOURCE), tokei.POLICY)
    policy = load_policy(rules.POLICY)
    priority = {name: rule.priority for name, rule in policy.items()}
    require_ancestor = {name: rule.require_ancestor for name, rule in policy.items()}
    data = tomllib.loads(
        rules.render(rules.merge(litter, detect), priority, require_ancestor)
    )

    assert data["python"]["priority"] == 0
    assert data["latex"]["require-ancestor"] is True
    assert "__pycache__/" in data["python"]["patterns"]
    assert ".pytest_cache/" in data["python"]["patterns"]
    assert "*.pyc" in data["python"]["patterns"]
    assert "node_modules/" in data["node"]["patterns"]
    assert "project/target/" in data["sbt"]["patterns"]
    assert "*.aux" in data["latex"]["patterns"]


def test_detect(tmp_path: Path) -> None:
    rules.ensure()
    data = tomllib.loads(
        tokei.render(tokei.merge(tokei.parse(tokei.SOURCE), tokei.POLICY))
    )

    assert ".py" in data["python"]["detect"]["suffix"]
    assert "python3" in data["python"]["detect"]["env"]
    assert ".tex" in data["latex"]["detect"]["suffix"]
    assert ".jsx" in data["react"]["detect"]["suffix"]
    assert "node" in data["node"]["detect"]["env"]


def test_ensure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(rules, "KONDO", tmp_path / "kondo" / "lib.rs")
    monkeypatch.setattr(rules, "TOKEI", tmp_path / "tokei" / "languages.json")

    calls: list[list[str]] = []

    def fake_sync(names: list[str] | None = None, check: bool = False) -> bool:
        assert check is False
        assert names is not None
        calls.append(names)
        return True

    monkeypatch.setattr(rules.refs, "sync", fake_sync)

    assert rules.ensure() is True
    assert calls == [["kondo", "tokei"]]
