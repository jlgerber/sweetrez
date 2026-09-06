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


def test_recipe_named_current_is_rejected(tmp_path):
    body = "name: current\ncontexts:\n  x:\n    requires: [foo]\n"
    with pytest.raises(RecipeError, match="reserved"):
        load_recipe(_write(tmp_path, body))


def test_write_recipe_template_creates_loadable_recipe(tmp_path):
    from sweetrez.recipe import write_recipe_template

    path = write_recipe_template(tmp_path / "recipes", "lighting")
    assert path == tmp_path / "recipes" / "lighting.yaml"
    recipe = load_recipe(path)
    assert recipe.name == "lighting"
    assert len(recipe.contexts) == 1
    assert "#" in path.read_text()  # guidance comments for the user


def test_write_recipe_template_refuses_to_overwrite(tmp_path):
    from sweetrez.recipe import write_recipe_template

    path = write_recipe_template(tmp_path, "a")
    path.write_text("name: a\ncontexts:\n  x:\n    requires: [foo]\n")
    with pytest.raises(RecipeError, match="exists"):
        write_recipe_template(tmp_path, "a")
    assert "x:" in path.read_text()


@pytest.mark.parametrize("name", ["bad name", "current", "-x", ""])
def test_write_recipe_template_validates_name(tmp_path, name):
    from sweetrez.recipe import write_recipe_template

    with pytest.raises(RecipeError):
        write_recipe_template(tmp_path, name)
    assert not list(tmp_path.iterdir())


def test_context_args_parse_to_tuples(tmp_path):
    body = (
        "name: a\ncontexts:\n  x:\n    requires: [foo]\n"
        "    args:\n      foo: [--renderer, RenderMan]\n      foo-helper: []\n"
    )
    r = load_recipe(_write(tmp_path, body))
    assert r.contexts[0].args == {"foo": ("--renderer", "RenderMan"), "foo-helper": ()}


def test_context_args_default_empty(tmp_path):
    r = load_recipe(_write(tmp_path, "name: a\ncontexts:\n  x:\n    requires: [foo]\n"))
    assert r.contexts[0].args == {}


@pytest.mark.parametrize(
    "args_yaml",
    ["args: [--x]", "args: {foo: --x}", "args: {foo: [1]}", "args: {foo: ['']}", "args: {'': [--x]}"],
)
def test_context_args_invalid_shapes(tmp_path, args_yaml):
    body = f"name: a\ncontexts:\n  x:\n    requires: [foo]\n    {args_yaml}\n"
    with pytest.raises(RecipeError, match="args"):
        load_recipe(_write(tmp_path, body))
