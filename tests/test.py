from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
import tomllib

import pytest

from gen import kondo
from gen.policy import load as load_policy
from gen import rules
from gen import tokei


ROOT = Path(__file__).resolve().parents[1]
PYTHON = shutil.which("python3") or "python3"


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
        env={"PYTHONPATH": str(ROOT)},
        check=False,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    assert str(tmp_path).startswith("/tmp/")
    root = tmp_path / "demo"
    root.mkdir()
    (root / "src").mkdir()
    (root / "__pycache__").mkdir()
    (root / "__pycache__" / "main.pyc").write_bytes(b"compiled")
    (root / "src" / "app.py").write_text("print('hi')\n")
    (root / ".pytest_cache").mkdir()
    (root / ".uv-cache" / "archive-v0").mkdir(parents=True)
    (root / ".uv-cache" / "archive-v0" / "wheel.txt").write_text("cached\n")
    return root


def test_paths(repo: Path) -> None:
    result = run("-p", str(repo))
    assert result.returncode == 0
    assert "Type" in result.stdout
    assert "Rule" in result.stdout
    assert "Path" in result.stdout
    assert "src/app.py" not in result.stdout
    assert ".pytest_cache/" in result.stdout
    assert "dil/__pycache__/" not in result.stdout


def test_compact(repo: Path) -> None:
    result = run(str(repo))
    assert result.returncode == 0
    assert "Type" in result.stdout
    assert "Matches" in result.stdout
    assert "Size" in result.stdout
    assert "__pycache__" in result.stdout


def test_default_detect(repo: Path) -> None:
    result = run(cwd=repo)
    assert result.returncode == 0
    assert "Type" in result.stdout
    assert "Rule" in result.stdout
    assert "Matches" in result.stdout
    assert "python" in result.stdout
    assert "pixi" not in result.stdout


def test_path_arg(repo: Path) -> None:
    result = run(str(repo))
    assert result.returncode == 0
    assert "python" in result.stdout


def test_cargo(tmp_path: Path) -> None:
    assert str(tmp_path).startswith("/tmp/")
    repo = tmp_path / "cargo"
    repo.mkdir()
    (repo / "main.rs").write_text("fn main() {}\n")
    result = run(cwd=repo)
    assert result.returncode == 0
    assert "Total" in result.stdout
    assert "0 B" in result.stdout


def test_guard(repo: Path) -> None:
    result = run("-d", "-n", "--type", "python", str(repo))
    assert result.returncode == 0
    assert "Path" in result.stdout
    assert ".pytest_cache" in result.stdout
    assert (repo / "__pycache__").exists()


def test_prune(repo: Path) -> None:
    result = run("-d", "-y", "--type", "python", str(repo))
    assert result.returncode == 0
    assert not (repo / "__pycache__").exists()
    assert not (repo / ".pytest_cache").exists()
    assert not (repo / ".uv-cache").exists()


def test_prompt_abort(repo: Path) -> None:
    result = run("-d", "--type", "python", str(repo), stdin="n\n")
    assert result.returncode == 0
    assert "Path" in result.stdout
    assert "/tmp/pytest-of-notroot/" in result.stdout
    assert ".pytest_cache" in result.stdout
    assert "Delete matched items? [y/N]" in result.stdout
    assert "Aborted." in result.stdout
    assert (repo / "__pycache__").exists()


def test_prompt_prune(repo: Path) -> None:
    result = run("-d", "--type", "python", str(repo), stdin="y\n")
    assert result.returncode == 0
    assert "Delete matched items? [y/N]" in result.stdout
    assert "Deleted 3 item(s)" in result.stdout
    assert not (repo / "__pycache__").exists()
    assert not (repo / ".pytest_cache").exists()
    assert not (repo / ".uv-cache").exists()


def test_short(repo: Path) -> None:
    result = run("-d", "-n", "-s", "--type", "python", str(repo))
    assert result.returncode == 0
    assert f"PROJECT: {repo}" in result.stdout
    assert "TYPES:   python" in result.stdout
    assert "WOULD DELETE:" in result.stdout
    assert str(repo / ".pytest_cache") in result.stdout
    assert f"To delete, run: dil -d -y {repo}" in result.stdout


def test_short_empty(tmp_path: Path) -> None:
    assert str(tmp_path).startswith("/tmp/")
    repo = tmp_path / "empty"
    repo.mkdir()
    result = run("-d", "-n", "-s", "--type", "python", str(repo))
    assert result.returncode == 0
    assert result.stdout == ""


def test_union(repo: Path) -> None:
    node_modules = repo / "node_modules"
    node_modules.mkdir()
    (node_modules / "pkg.json").write_text("{}\n")
    result = run("-p", "--type", "python|node", str(repo))
    assert result.returncode == 0
    assert "node_modules/" in result.stdout


def test_stopword(repo: Path) -> None:
    build = repo / "node_modules" / "pkg" / "build"
    build.mkdir(parents=True)
    (build / "artifact.js").write_text("x\n")
    result = run("-p", "--type", "python|node", str(repo))
    assert result.returncode == 0
    assert "node_modules/pkg/build/" not in result.stdout


def test_path(repo: Path) -> None:
    target = repo / "project" / "target"
    target.mkdir(parents=True)
    (target / "classes.bin").write_bytes(b"x")
    result = run("-p", "--type", "sbt", str(repo))
    assert result.returncode == 0
    assert "project/target/" in result.stdout


def test_common(repo: Path) -> None:
    swap = repo / "note.swp"
    swap.write_text("junk\n")
    result = run("-p", "--type", "common", str(repo))
    assert result.returncode == 0
    assert "note.swp" in result.stdout


def test_latex_ancestor(tmp_path: Path) -> None:
    assert str(tmp_path).startswith("/tmp/")
    repo = tmp_path / "latex"
    repo.mkdir()
    (repo / "project").mkdir()
    (repo / "project" / "foo.tex").write_text("\\documentclass{article}\n")
    (repo / "project" / "build").mkdir()
    (repo / "project" / "build" / "foo.log").write_text("latex\n")
    (repo / "other").mkdir()
    (repo / "other" / "foo.log").write_text("app\n")

    result = run("-p", "--type", "latex", str(repo))
    assert result.returncode == 0
    assert "project/build/foo.log" in result.stdout
    assert "other/foo.log" not in result.stdout


def test_shebang(repo: Path) -> None:
    tool = repo / "tool"
    tool.write_text("#!/usr/bin/env python3\nprint('hi')\n")
    result = run(cwd=repo)
    assert result.returncode == 0
    assert "python" in result.stdout


def test_absolute(repo: Path) -> None:
    result = run("-P", "--type", "python", str(repo))
    assert result.returncode == 0
    assert str(repo) in result.stdout
    assert ".pytest_cache" in result.stdout


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
    assert "__pycache__" in data["python"]["dirs"]
    assert ".pytest_cache" in data["python"]["dirs"]
    assert "*.pyc" in data["python"]["files"]
    assert "node_modules" in data["node"]["dirs"]
    assert "project/target" in data["sbt"]["paths"]
    assert "*.aux" in data["latex"]["files"]


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
