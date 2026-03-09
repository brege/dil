from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
import tomllib

import pytest

from gen import kondo
from gen import rules
from gen import tokei


ROOT = Path(__file__).resolve().parents[1]
PYTHON = shutil.which("python3") or "python3"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    command = [PYTHON, "-m", "dil.cli", *args]
    return subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
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


def test_scan(repo: Path) -> None:
    result = run("scan", "--pretty", "--type", "python", str(repo))
    assert result.returncode == 0
    assert "WOULD DELETE:" in result.stdout
    assert "__pycache__/" in result.stdout
    assert ".pytest_cache/" in result.stdout


def test_guard(repo: Path) -> None:
    result = run("prune", "--type", "python", str(repo))
    assert result.returncode == 0
    assert "Refusing to delete without --force." in result.stdout
    assert (repo / "__pycache__").exists()


def test_prune(repo: Path) -> None:
    result = run("prune", "--force", "--type", "python", str(repo))
    assert result.returncode == 0
    assert not (repo / "__pycache__").exists()
    assert not (repo / ".pytest_cache").exists()
    assert not (repo / ".uv-cache").exists()


def test_report(repo: Path) -> None:
    result = run("report", "--type", "python", str(repo))
    assert result.returncode == 0
    assert "Litter Summary" in result.stdout
    assert "Project Summary" in result.stdout
    assert "python" in result.stdout


def test_union(repo: Path) -> None:
    node_modules = repo / "node_modules"
    node_modules.mkdir()
    (node_modules / "pkg.json").write_text("{}\n")
    result = run("scan", "--type", "python|node", str(repo))
    assert result.returncode == 0
    assert "node_modules/" in result.stdout


def test_path(repo: Path) -> None:
    target = repo / "project" / "target"
    target.mkdir(parents=True)
    (target / "classes.bin").write_bytes(b"x")
    result = run("scan", "--type", "sbt", str(repo))
    assert result.returncode == 0
    assert "project/target/" in result.stdout


def test_common(repo: Path) -> None:
    swap = repo / "note.swp"
    swap.write_text("junk\n")
    result = run("scan", "--type", "common", str(repo))
    assert result.returncode == 0
    assert "note.swp" in result.stdout


def test_rules(tmp_path: Path) -> None:
    litter = kondo.merge(kondo.parse(kondo.SOURCE.read_text()), kondo.POLICY)
    detect = tokei.merge(tokei.parse(tokei.SOURCE), tokei.POLICY)
    data = tomllib.loads(rules.render(rules.merge(litter, detect)))

    assert "__pycache__" in data["python"]["dirs"]
    assert ".pytest_cache" in data["python"]["dirs"]
    assert "*.pyc" in data["python"]["files"]
    assert "node_modules" in data["node"]["dirs"]
    assert "project/target" in data["sbt"]["paths"]
    assert "*.aux" in data["latex"]["files"]


def test_detect(tmp_path: Path) -> None:
    data = tomllib.loads(
        tokei.render(tokei.merge(tokei.parse(tokei.SOURCE), tokei.POLICY))
    )

    assert ".py" in data["python"]["detect"]["suffix"]
    assert "python3" in data["python"]["detect"]["env"]
    assert ".tex" in data["latex"]["detect"]["suffix"]
    assert ".jsx" in data["react"]["detect"]["suffix"]
    assert "node" in data["node"]["detect"]["env"]
