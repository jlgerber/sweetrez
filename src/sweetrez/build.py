from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from rez.exceptions import RezError, SuiteError
from rez.resolved_context import ResolvedContext
from rez.suite import Suite

from .errors import BuildError as _BuildError
from .recipe import ContextSpec, Recipe
from .store import TMP_PREFIX, SuiteStore, new_build_id

RECIPE_COPY_NAME = "recipe.yaml"


@dataclass(frozen=True)
class ContextFailure:
    context: str
    reason: str


class BuildError(_BuildError):
    def __init__(self, message: str, failures: list[ContextFailure] | None = None):
        super().__init__(message)
        self.failures = list(failures or [])

    @classmethod
    def from_failures(cls, recipe_name: str, failures: list[ContextFailure]) -> "BuildError":
        lines = [f"{recipe_name}: {len(failures)} context(s) failed to resolve:"]
        lines += [f"  {f.context}: {f.reason}" for f in failures]
        return cls("\n".join(lines), failures)


def _resolve_one(spec: ContextSpec) -> ResolvedContext | ContextFailure:
    try:
        ctx = ResolvedContext(list(spec.requires))
    except RezError as e:
        return ContextFailure(spec.name, str(e))
    if not ctx.success:
        return ContextFailure(spec.name, ctx.failure_description or "resolve failed")
    return ctx


def resolve_contexts(recipe: Recipe) -> dict[str, ResolvedContext]:
    contexts: dict[str, ResolvedContext] = {}
    failures: list[ContextFailure] = []
    for spec in recipe.contexts:
        result = _resolve_one(spec)
        if isinstance(result, ContextFailure):
            failures.append(result)
        else:
            contexts[spec.name] = result
    if failures:
        raise BuildError.from_failures(recipe.name, failures)
    return contexts


def assemble_suite(recipe: Recipe, contexts: dict[str, ResolvedContext]) -> Suite:
    suite = Suite()
    try:
        for spec in recipe.contexts:
            suite.add_context(spec.name, contexts[spec.name])
            if spec.prefix:
                suite.set_context_prefix(spec.name, spec.prefix)
            if spec.suffix:
                suite.set_context_suffix(spec.name, spec.suffix)
            for tool, alias in spec.alias.items():
                suite.alias_tool(spec.name, tool, alias)
            for tool in spec.hide:
                suite.hide_tool(spec.name, tool)
    except SuiteError as e:
        raise BuildError(f"{recipe.name}: {e}") from e
    return suite


def build_suite(recipe: Recipe, store: SuiteStore, build_id: str | None = None) -> Path:
    contexts = resolve_contexts(recipe)
    suite = assemble_suite(recipe, contexts)
    build_id = build_id or new_build_id()

    def writer(path: Path) -> None:
        suite.save(str(path))
        # Suite.save() stamps each context with the tmp directory it was just
        # written to (its own _set_parent_suite call, the same one rez uses
        # internally); re-stamp and re-save with the final, post-rename path
        # so the shipped .rxt files don't point at a directory that is about
        # to disappear.
        final = path.with_name(path.name.removeprefix(TMP_PREFIX))
        for name in suite.context_names:
            ctx = suite.context(name)
            ctx._set_parent_suite(str(final), name)
            ctx.save(str(path / "contexts" / f"{name}.rxt"))
        shutil.copyfile(recipe.source_path, path / RECIPE_COPY_NAME)

    return store.write_build(recipe.name, build_id, writer)
