from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Callable

from .errors import StoreError

CURRENT = "current"
BUILD_ID_FORMAT = "%Y-%m-%dT%H-%M-%S"
TMP_PREFIX = ".tmp-"


def new_build_id(now: datetime | None = None) -> str:
    return (now or datetime.now()).strftime(BUILD_ID_FORMAT)


def _visible(name: str) -> bool:
    return not name.startswith(".") and name != CURRENT


class SuiteStore:
    def __init__(self, root: Path):
        self.root = Path(root)

    def suite_dir(self, name: str) -> Path:
        return self.root / name

    def suites(self) -> list[str]:
        if not self.root.is_dir():
            return []
        return sorted(p.name for p in self.root.iterdir() if p.is_dir() and _visible(p.name))

    def builds(self, name: str) -> list[str]:
        suite_dir = self.suite_dir(name)
        if not suite_dir.is_dir():
            return []
        return sorted(
            p.name for p in suite_dir.iterdir()
            if p.is_dir() and not p.is_symlink() and _visible(p.name)
        )

    def newest(self, name: str) -> str | None:
        builds = self.builds(name)
        return builds[-1] if builds else None

    def promoted(self, name: str) -> str | None:
        link = self.suite_dir(name) / CURRENT
        if not link.is_symlink():
            return None
        return os.path.basename(os.readlink(link))

    def build_path(self, name: str, build_id: str) -> Path:
        if build_id not in self.builds(name):
            raise StoreError(f"{name}: no such build: {build_id}")
        return self.suite_dir(name) / build_id

    def write_build(self, name: str, build_id: str, writer: Callable[[Path], None]) -> Path:
        suite_dir = self.suite_dir(name)
        final = suite_dir / build_id
        tmp = suite_dir / f"{TMP_PREFIX}{build_id}"
        if final.exists():
            raise StoreError(f"{name}: build already exists: {final}")
        suite_dir.mkdir(parents=True, exist_ok=True)
        if tmp.exists():
            shutil.rmtree(tmp)
        try:
            writer(tmp)
        except BaseException:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
        if final.exists():
            shutil.rmtree(tmp, ignore_errors=True)
            raise StoreError(f"{name}: build already exists: {final}")
        tmp.rename(final)
        return final

    def promote(self, name: str, build_id: str | None = None) -> str:
        builds = self.builds(name)
        if not builds:
            raise StoreError(f"{name}: no builds to promote")
        if build_id is None:
            build_id = builds[-1]
        elif build_id not in builds:
            raise StoreError(f"{name}: no such build: {build_id}")
        suite_dir = self.suite_dir(name)
        link = suite_dir / CURRENT
        tmp_link = suite_dir / f".{CURRENT}.tmp"
        if tmp_link.is_symlink() or tmp_link.exists():
            tmp_link.unlink()
        os.symlink(build_id, tmp_link)
        os.replace(tmp_link, link)
        return build_id
