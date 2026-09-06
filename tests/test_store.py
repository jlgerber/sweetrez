import os
from datetime import datetime

import pytest

from sweetrez.errors import StoreError
from sweetrez.store import SuiteStore, new_build_id


def test_build_id_format():
    assert new_build_id(datetime(2026, 9, 6, 14, 32, 10)) == "2026-09-06T14-32-10"


def test_empty_root(tmp_path):
    store = SuiteStore(tmp_path)
    assert store.suites() == []
    assert store.builds("x") == []
    assert store.newest("x") is None
    assert store.promoted("x") is None


def _make(store, name, build_id, marker="ok"):
    def writer(path):
        path.mkdir()
        (path / "marker").write_text(marker)

    return store.write_build(name, build_id, writer)


def test_write_build_renames_temp_into_place(tmp_path):
    store = SuiteStore(tmp_path)
    seen = {}

    def writer(path):
        seen["tmp"] = path
        path.mkdir()

    final = store.write_build("s", "2026-01-01T00-00-00", writer)
    assert seen["tmp"] == tmp_path / "s" / ".tmp-2026-01-01T00-00-00"
    assert not seen["tmp"].exists()
    assert final == tmp_path / "s" / "2026-01-01T00-00-00"
    assert final.is_dir()


def test_write_build_cleans_up_when_writer_fails(tmp_path):
    store = SuiteStore(tmp_path)

    def writer(path):
        path.mkdir()
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        store.write_build("s", "2026-01-01T00-00-00", writer)
    assert list((tmp_path / "s").iterdir()) == []


def test_write_build_refuses_existing_id(tmp_path):
    store = SuiteStore(tmp_path)
    _make(store, "s", "2026-01-01T00-00-00")
    with pytest.raises(StoreError, match="exists"):
        _make(store, "s", "2026-01-01T00-00-00")


def test_builds_are_sorted_and_ignore_hidden_and_current(tmp_path):
    store = SuiteStore(tmp_path)
    _make(store, "s", "2026-01-02T00-00-00")
    _make(store, "s", "2026-01-01T00-00-00")
    (tmp_path / "s" / ".tmp-2026-01-03T00-00-00").mkdir()
    store.promote("s")
    assert store.builds("s") == ["2026-01-01T00-00-00", "2026-01-02T00-00-00"]
    assert store.newest("s") == "2026-01-02T00-00-00"
    assert store.suites() == ["s"]


def test_promote_defaults_to_newest_and_is_relative(tmp_path):
    store = SuiteStore(tmp_path)
    _make(store, "s", "2026-01-01T00-00-00")
    _make(store, "s", "2026-01-02T00-00-00")
    assert store.promote("s") == "2026-01-02T00-00-00"
    link = tmp_path / "s" / "current"
    assert os.readlink(link) == "2026-01-02T00-00-00"
    assert store.promoted("s") == "2026-01-02T00-00-00"


def test_promote_specific_id_replaces_existing_link(tmp_path):
    store = SuiteStore(tmp_path)
    _make(store, "s", "2026-01-01T00-00-00")
    _make(store, "s", "2026-01-02T00-00-00")
    store.promote("s")
    assert store.promote("s", "2026-01-01T00-00-00") == "2026-01-01T00-00-00"
    assert store.promoted("s") == "2026-01-01T00-00-00"


def test_promote_errors(tmp_path):
    store = SuiteStore(tmp_path)
    with pytest.raises(StoreError, match="no builds"):
        store.promote("s")
    _make(store, "s", "2026-01-01T00-00-00")
    with pytest.raises(StoreError, match="no such build"):
        store.promote("s", "2026-01-09T00-00-00")


def test_build_path_checks_existence(tmp_path):
    store = SuiteStore(tmp_path)
    _make(store, "s", "2026-01-01T00-00-00")
    assert store.build_path("s", "2026-01-01T00-00-00") == tmp_path / "s" / "2026-01-01T00-00-00"
    with pytest.raises(StoreError, match="no such build"):
        store.build_path("s", "2026-01-09T00-00-00")
