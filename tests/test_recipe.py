from pathlib import Path

import pytest

from sweetrez.errors import RecipeError
from sweetrez.recipe import load_recipe, load_recipes

FULL = """\
name: lighting
description: Lighting DCCs
contexts:
  maya:
    requires: [foo-1+, bar]
    prefix: m_
    alias: {foo: foo_maya}
    hide: [foo-helper]
  houdini:
    requires: [foo-1.1]
    suffix: _h
"""


def _write(tmp_path, body, filename="r.yaml"):
    p = tmp_path / filename
    p.write_text(body)
    return p


def test_full_recipe_round_trips(tmp_path):
    p = _write(tmp_path, FULL)
    r = load_recipe(p)
    assert r.name == "lighting"
    assert r.description == "Lighting DCCs"
    assert r.source_path == p
    assert [c.name for c in r.contexts] == ["maya", "houdini"]
    maya, houdini = r.contexts
    assert maya.requires == ("foo-1+", "bar")
    assert maya.prefix == "m_"
    assert maya.suffix == ""
    assert maya.alias == {"foo": "foo_maya"}
    assert maya.hide == ("foo-helper",)
    assert houdini.suffix == "_h"
    assert houdini.alias == {}
    assert houdini.hide == ()


def test_description_is_optional(tmp_path):
    r = load_recipe(_write(tmp_path, "name: a\ncontexts:\n  x:\n    requires: [foo]\n"))
    assert r.description == ""


@pytest.mark.parametrize(
    "body,match",
    [
        ("contexts:\n  x:\n    requires: [foo]\n", "name"),
        ("name: 'bad name'\ncontexts:\n  x:\n    requires: [foo]\n", "name"),
        ("name: a\n", "contexts"),
        ("name: a\ncontexts: {}\n", "contexts"),
        ("name: a\ncontexts:\n  x: {}\n", "requires"),
        ("name: a\ncontexts:\n  x:\n    requires: []\n", "requires"),
        ("name: a\ncontexts:\n  x:\n    requires: foo\n", "requires"),
        ("name: a\ncontexts:\n  x:\n    requires: [foo]\n    bogus: 1\n", "bogus"),
        ("name: a\ncontexts:\n  x:\n    requires: [foo]\n    alias: [a]\n", "alias"),
        ("name: a\ncontexts:\n  x:\n    requires: [foo]\n    hide: foo\n", "hide"),
        ("name: a\ncontexts:\n  x:\n    requires: [foo]\n    prefix: 3\n", "prefix"),
        ("name: a\nbogus: 1\ncontexts:\n  x:\n    requires: [foo]\n", "bogus"),
        ("- not a mapping\n", "mapping"),
    ],
)
def test_invalid_recipes(tmp_path, body, match):
    with pytest.raises(RecipeError, match=match):
        load_recipe(_write(tmp_path, body))


def test_invalid_yaml_is_recipe_error(tmp_path):
    with pytest.raises(RecipeError, match="YAML"):
        load_recipe(_write(tmp_path, "name: [\n"))


def test_missing_file_is_recipe_error(tmp_path):
    with pytest.raises(RecipeError, match="not found"):
        load_recipe(tmp_path / "nope.yaml")


def test_load_recipes_keys_by_name_and_accepts_yml(tmp_path):
    _write(tmp_path, "name: a\ncontexts:\n  x:\n    requires: [foo]\n", "one.yaml")
    _write(tmp_path, "name: b\ncontexts:\n  x:\n    requires: [foo]\n", "two.yml")
    (tmp_path / "notes.txt").write_text("ignored")
    recipes = load_recipes(tmp_path)
    assert sorted(recipes) == ["a", "b"]
    assert recipes["b"].source_path == tmp_path / "two.yml"


def test_load_recipes_duplicate_name_is_error(tmp_path):
    _write(tmp_path, "name: a\ncontexts:\n  x:\n    requires: [foo]\n", "one.yaml")
    _write(tmp_path, "name: a\ncontexts:\n  x:\n    requires: [foo]\n", "two.yaml")
    with pytest.raises(RecipeError, match="duplicate"):
        load_recipes(tmp_path)


def test_load_recipes_missing_dir_is_error(tmp_path):
    with pytest.raises(RecipeError, match="not found"):
        load_recipes(tmp_path / "nope")


def test_name_with_trailing_newline_is_rejected(tmp_path):
    body = "name: |\n  lighting\ncontexts:\n  x:\n    requires: [foo]\n"
    with pytest.raises(RecipeError, match="name"):
        load_recipe(_write(tmp_path, body))


def test_context_name_with_path_separator_is_rejected(tmp_path):
    body = "name: a\ncontexts:\n  sub/dir:\n    requires: [foo]\n"
    with pytest.raises(RecipeError, match="context names"):
        load_recipe(_write(tmp_path, body))
