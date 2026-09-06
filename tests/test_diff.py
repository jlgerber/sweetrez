from sweetrez.build import build_suite
from sweetrez.diff import Change, diff_versions, format_diff, resolved_versions
from sweetrez.recipe import load_recipe
from sweetrez.store import SuiteStore

RECIPE = """\
name: demo
contexts:
  a:
    requires: [foo-1+]
  b:
    requires: [bar]
"""


def test_resolved_versions_reads_saved_suite(package_repo, tmp_path, write_recipe):
    recipe = load_recipe(write_recipe(tmp_path / "r", RECIPE))
    path = build_suite(recipe, SuiteStore(tmp_path / "root"), build_id="2026-01-01T00-00-00")
    assert resolved_versions(path) == {
        "a": {"foo": "1.1.0"},
        "b": {"bar": "2.0.0", "foo": "1.0.0"},
    }


def test_two_builds_differ_after_new_package(package_repo, tmp_path, write_recipe, add_package):
    recipe = load_recipe(write_recipe(tmp_path / "r", RECIPE))
    store = SuiteStore(tmp_path / "root")
    old = build_suite(recipe, store, build_id="2026-01-01T00-00-00")
    add_package(package_repo, "foo", "1.2.0", tools=["foo", "foo-helper"])
    new = build_suite(recipe, store, build_id="2026-01-02T00-00-00")
    changes = diff_versions(resolved_versions(old), resolved_versions(new))
    assert changes == [Change("a", "foo", "1.1.0", "1.2.0")]


def test_diff_versions_reports_added_and_removed():
    old = {"a": {"foo": "1.0.0", "gone": "1"}, "dropped": {"x": "1"}}
    new = {"a": {"foo": "1.0.0", "fresh": "2"}, "added": {"y": "3"}}
    assert diff_versions(old, new) == [
        Change("a", "fresh", None, "2"),
        Change("a", "gone", "1", None),
        Change("added", "y", None, "3"),
        Change("dropped", "x", "1", None),
    ]


def test_format_diff():
    changes = [
        Change("a", "foo", "1.1.0", "1.2.0"),
        Change("a", "fresh", None, "2"),
        Change("b", "gone", "1", None),
    ]
    assert format_diff(changes) == (
        "  a: foo 1.1.0 -> 1.2.0\n"
        "  a: fresh (added) -> 2\n"
        "  b: gone 1 -> (removed)"
    )
    assert format_diff([]) == "no changes"
