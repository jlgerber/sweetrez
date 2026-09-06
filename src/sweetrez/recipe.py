from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .errors import RecipeError

NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_RECIPE_KEYS = {"name", "description", "contexts"}
_CONTEXT_KEYS = {"requires", "prefix", "suffix", "alias", "hide"}


@dataclass(frozen=True)
class ContextSpec:
    name: str
    requires: tuple[str, ...]
    prefix: str = ""
    suffix: str = ""
    alias: dict[str, str] = field(default_factory=dict)
    hide: tuple[str, ...] = ()


@dataclass(frozen=True)
class Recipe:
    name: str
    description: str
    contexts: tuple[ContextSpec, ...]
    source_path: Path


def _str_list(value, where: str, key: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
        raise RecipeError(f"{where}: '{key}' must be a list of non-empty strings")
    return tuple(value)


def _str(value, where: str, key: str) -> str:
    if not isinstance(value, str):
        raise RecipeError(f"{where}: '{key}' must be a string")
    return value


def _parse_context(name: str, data, where: str) -> ContextSpec:
    where = f"{where}: context '{name}'"
    if not isinstance(name, str) or not name:
        raise RecipeError(f"{where}: context names must be non-empty strings")
    if not NAME_RE.fullmatch(name):
        raise RecipeError(f"{where}: context names must match {NAME_RE.pattern}")
    if not isinstance(data, dict):
        raise RecipeError(f"{where}: must be a mapping with a 'requires' list")
    unknown = set(data) - _CONTEXT_KEYS
    if unknown:
        raise RecipeError(f"{where}: unknown keys: {', '.join(sorted(unknown))}")
    if "requires" not in data:
        raise RecipeError(f"{where}: 'requires' is required")
    requires = _str_list(data["requires"], where, "requires")
    if not requires:
        raise RecipeError(f"{where}: 'requires' must not be empty")
    alias = data.get("alias", {})
    if not isinstance(alias, dict) or not all(
        isinstance(k, str) and isinstance(v, str) and k and v for k, v in alias.items()
    ):
        raise RecipeError(f"{where}: 'alias' must be a mapping of tool name to alias")
    return ContextSpec(
        name=name,
        requires=requires,
        prefix=_str(data.get("prefix", ""), where, "prefix"),
        suffix=_str(data.get("suffix", ""), where, "suffix"),
        alias=dict(alias),
        hide=_str_list(data.get("hide", []), where, "hide"),
    )


def load_recipe(path: Path) -> Recipe:
    path = Path(path)
    if not path.is_file():
        raise RecipeError(f"recipe not found: {path}")
    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError as e:
        raise RecipeError(f"{path}: invalid YAML: {e}") from e
    where = str(path)
    if not isinstance(data, dict):
        raise RecipeError(f"{where}: recipe must be a mapping")
    unknown = set(data) - _RECIPE_KEYS
    if unknown:
        raise RecipeError(f"{where}: unknown keys: {', '.join(sorted(unknown))}")
    name = data.get("name")
    if not isinstance(name, str) or not NAME_RE.fullmatch(name):
        raise RecipeError(f"{where}: 'name' is required and must match {NAME_RE.pattern}")
    if name == "current":
        raise RecipeError(f"{where}: 'current' is a reserved name")
    description = _str(data.get("description", ""), where, "description")
    contexts = data.get("contexts")
    if not isinstance(contexts, dict) or not contexts:
        raise RecipeError(f"{where}: 'contexts' must be a non-empty mapping")
    specs = tuple(_parse_context(cname, cdata, where) for cname, cdata in contexts.items())
    return Recipe(name=name, description=description, contexts=specs, source_path=path)


def load_recipes(recipe_dir: Path) -> dict[str, Recipe]:
    recipe_dir = Path(recipe_dir)
    if not recipe_dir.is_dir():
        raise RecipeError(f"recipe directory not found: {recipe_dir}")
    recipes: dict[str, Recipe] = {}
    paths = sorted(list(recipe_dir.glob("*.yaml")) + list(recipe_dir.glob("*.yml")))
    for path in paths:
        recipe = load_recipe(path)
        if recipe.name in recipes:
            raise RecipeError(
                f"duplicate recipe name '{recipe.name}': "
                f"{recipes[recipe.name].source_path} and {path}"
            )
        recipes[recipe.name] = recipe
    return recipes
