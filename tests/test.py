from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


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
