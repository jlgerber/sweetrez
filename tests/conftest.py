from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from rez.config import config as rez_config
from rez.package_repository import package_repository_manager

FIXTURE_PACKAGES = Path(__file__).parent / "packages"


@pytest.fixture
def package_repo(tmp_path):
    repo = tmp_path / "packages"
    shutil.copytree(FIXTURE_PACKAGES, repo)
    rez_config.override("packages_path", [str(repo)])
    package_repository_manager.clear_caches()
    try:
        yield repo
    finally:
        rez_config.remove_override("packages_path")


@pytest.fixture
def add_package():
    def _add(repo: Path, name: str, version: str, tools: list[str], requires: list[str] | None = None):
        pkg_dir = repo / name / version
        pkg_dir.mkdir(parents=True)
        lines = [
            f"name = {name!r}",
            f"version = {version!r}",
            f"requires = {list(requires or [])!r}",
            f"tools = {list(tools)!r}",
            "",
            "def commands():",
            '    env.PATH.prepend("{root}/bin")',
            "",
        ]
        (pkg_dir / "package.py").write_text("\n".join(lines))
        # rez caches package listings per process; without this the new version is invisible.
        package_repository_manager.clear_caches()

    return _add


@pytest.fixture
def write_recipe():
    def _write(directory: Path, body: str, filename: str = "recipe.yaml") -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / filename
        path.write_text(body)
        return path

    return _write
