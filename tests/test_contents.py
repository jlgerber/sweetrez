from sweetrez.build import build_suite
from sweetrez.contents import (
    CONTEXTS,
    PACKAGES,
    WRAPPERS,
    SuiteContents,
    Wrapper,
    format_contents,
    load_contents,
)
from sweetrez.recipe import load_recipe
from sweetrez.store import SuiteStore

RECIPE = """\
name: demo
contexts:
  b:
    requires: [bar]
    hide: [bar]
  a:
    requires: [foo-1+]
    alias: {foo-helper: fh}
"""

CONTENTS = SuiteContents(
    contexts=["a", "b"],
    packages={"a": {"foo": "1.1.0"}, "b": {"foo": "1.0.0", "bar": "2.0.0"}},
    wrappers=[Wrapper("fh", "a", "foo-helper"), Wrapper("foo", "a", "foo")],
)


def test_load_contents_reads_saved_suite(package_repo, tmp_path, write_recipe):
    recipe = load_recipe(write_recipe(tmp_path / "r", RECIPE))
    path = build_suite(recipe, SuiteStore(tmp_path / "root"), build_id="2026-01-01T00-00-00")
    contents = load_contents(path)
    assert contents.contexts == ["a", "b"]
    assert contents.packages == {"a": {"foo": "1.1.0"}, "b": {"bar": "2.0.0", "foo": "1.0.0"}}
    # bar is hidden; b's foo conflicts with a's foo, so rez keeps a single foo.
    assert [w.tool for w in contents.wrappers] == ["fh", "foo"]
    assert Wrapper("fh", "a", "foo-helper") in contents.wrappers


def test_format_packages_alone_is_tree_without_header():
    assert format_contents(CONTENTS, [PACKAGES]) == (
        "a\n"
        "    foo-1.1.0\n"
        "b\n"
        "    bar-2.0.0\n"
        "    foo-1.0.0"
    )


def test_format_contexts_alone():
    assert format_contents(CONTENTS, [CONTEXTS]) == "a\nb"


def test_format_wrappers_alone_aligns_columns():
    assert format_contents(CONTENTS, [WRAPPERS]) == (
        "fh   (a: foo-helper)\n"
        "foo  (a: foo)"
    )


def test_format_combined_uses_headers_in_fixed_order():
    assert format_contents(CONTENTS, [WRAPPERS, CONTEXTS]) == (
        "contexts:\n"
        "    a\n"
        "    b\n"
        "wrappers:\n"
        "    fh   (a: foo-helper)\n"
        "    foo  (a: foo)"
    )


def test_format_empty_wrappers():
    empty = SuiteContents(contexts=["a"], packages={"a": {}}, wrappers=[])
    assert format_contents(empty, [WRAPPERS]) == "(no wrappers)"
