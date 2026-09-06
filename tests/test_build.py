import pytest
from rez.resolved_context import ResolvedContext
from rez.suite import Suite

from sweetrez.build import RECIPE_COPY_NAME, build_suite, resolve_contexts
from sweetrez.errors import BuildError
from sweetrez.recipe import load_recipe
from sweetrez.store import SuiteStore

GOOD = """\
name: demo
description: two contexts
contexts:
  a:
    requires: [foo-1+]
    prefix: a_
    hide: [foo-helper]
  b:
    requires: [bar]
    alias: {bar: barz}
"""


def _versions(ctx):
    return {v.name: str(v.version) for v in ctx.resolved_packages}


def test_resolve_contexts_resolves_every_context(package_repo, tmp_path, write_recipe):
    recipe = load_recipe(write_recipe(tmp_path / "r", GOOD))
    contexts = resolve_contexts(recipe)
    assert list(contexts) == ["a", "b"]
    assert _versions(contexts["a"]) == {"foo": "1.1.0"}
    assert _versions(contexts["b"]) == {"bar": "2.0.0", "foo": "1.0.0"}


def test_resolve_contexts_reports_all_failures_at_once(package_repo, tmp_path, write_recipe):
    body = """\
name: broken
contexts:
  missing_version:
    requires: [foo-9+]
  unknown_family:
    requires: [nope]
  conflict:
    requires: [bar, foo-1.1]
  fine:
    requires: [foo]
"""
    recipe = load_recipe(write_recipe(tmp_path / "r", body))
    with pytest.raises(BuildError) as info:
        resolve_contexts(recipe)
    failed = {f.context for f in info.value.failures}
    assert failed == {"missing_version", "unknown_family", "conflict"}
    text = str(info.value)
    assert "missing_version" in text and "foo-9+" in text
    assert "unknown_family" in text and "nope" in text
    assert "conflict" in text and "foo" in text


def test_build_suite_writes_suite_and_recipe_copy(package_repo, tmp_path, write_recipe):
    recipe_path = write_recipe(tmp_path / "r", GOOD)
    recipe = load_recipe(recipe_path)
    store = SuiteStore(tmp_path / "root")
    path = build_suite(recipe, store, build_id="2026-01-01T00-00-00")
    assert path == tmp_path / "root" / "demo" / "2026-01-01T00-00-00"
    assert store.builds("demo") == ["2026-01-01T00-00-00"]
    assert store.promoted("demo") is None
    assert (path / RECIPE_COPY_NAME).read_text() == recipe_path.read_text()
    suite = Suite.load(str(path))
    assert suite.context_names == ["a", "b"]
    assert _versions(suite.context("a")) == {"foo": "1.1.0"}
    assert sorted(p.name for p in (path / "bin").iterdir()) == ["a_foo", "barz"]
    assert sorted(p.name for p in (path / "contexts").iterdir()) == ["a.rxt", "b.rxt"]


def test_saved_context_records_final_suite_path(package_repo, tmp_path, write_recipe):
    recipe = load_recipe(write_recipe(tmp_path / "r", GOOD))
    store = SuiteStore(tmp_path / "root")
    path = build_suite(recipe, store, build_id="2026-01-01T00-00-00")
    ctx = ResolvedContext.load(str(path / "contexts" / "a.rxt"))
    assert ctx.parent_suite_path == str(path)
    assert ctx.suite_context_name == "a"


def test_build_suite_generates_build_id(package_repo, tmp_path, write_recipe):
    recipe = load_recipe(write_recipe(tmp_path / "r", GOOD))
    store = SuiteStore(tmp_path / "root")
    path = build_suite(recipe, store)
    assert store.builds("demo") == [path.name]
    assert len(path.name) == len("2026-01-01T00-00-00")


def test_bad_alias_is_build_error_and_writes_nothing(package_repo, tmp_path, write_recipe):
    body = """\
name: demo
contexts:
  b:
    requires: [bar]
    alias: {foo: foo2}
"""
    recipe = load_recipe(write_recipe(tmp_path / "r", body))
    store = SuiteStore(tmp_path / "root")
    with pytest.raises(BuildError, match="foo"):
        build_suite(recipe, store)
    assert store.builds("demo") == []
    assert not (tmp_path / "root" / "demo").exists() or list((tmp_path / "root" / "demo").iterdir()) == []


def test_bad_hide_is_build_error(package_repo, tmp_path, write_recipe):
    body = """\
name: demo
contexts:
  a:
    requires: [foo]
    hide: [nothing]
"""
    recipe = load_recipe(write_recipe(tmp_path / "r", body))
    with pytest.raises(BuildError, match="nothing"):
        build_suite(recipe, SuiteStore(tmp_path / "root"))


def test_failed_resolve_writes_nothing(package_repo, tmp_path, write_recipe):
    body = """\
name: demo
contexts:
  a:
    requires: [foo]
  b:
    requires: [foo-9+]
"""
    recipe = load_recipe(write_recipe(tmp_path / "r", body))
    store = SuiteStore(tmp_path / "root")
    with pytest.raises(BuildError):
        build_suite(recipe, store)
    assert not (tmp_path / "root" / "demo").exists()
