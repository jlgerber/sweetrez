from __future__ import annotations

import shlex
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from rez.exceptions import RezError, SuiteError
from rez.resolved_context import ResolvedContext
from rez.suite import Suite

from .errors import BuildError as _BuildError
from .recipe import ContextSpec, Recipe
from .store import TMP_PREFIX, SuiteStore, new_build_id

RECIPE_COPY_NAME = "recipe.yaml"
SHIM_DIR = ".rez-wrappers"  # sibling of bin/: rez finds the suite two levels up from a wrapper


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


def _tool_aliases(suite: Suite) -> dict[tuple[str, str], str]:
    """Map (context name, tool name) to the alias rez exposes in bin/."""
    return {
        (t["context_name"], t["tool_name"]): alias
        for alias, t in suite.get_tools().items()
    }


def resolve_arg_shims(recipe: Recipe, suite: Suite) -> dict[str, tuple[str, ...]]:
    """Map bin/ alias -> default args for every tool a recipe gives args to.

    Raises BuildError if a tool with args has no wrapper in the suite: it is not
    provided by a requested package, is hidden, or lost a cross-context conflict.
    """
    aliases = _tool_aliases(suite)
    shims: dict[str, tuple[str, ...]] = {}
    for spec in recipe.contexts:
        for tool, args in spec.args.items():
            alias = aliases.get((spec.name, tool))
            if alias is None:
                raise BuildError(
                    f"{recipe.name}: args given for tool {tool!r} in context "
                    f"{spec.name!r}, but it has no wrapper (not provided by a "
                    "requested package, hidden, or shadowed by a conflict)"
                )
            shims[alias] = args
    return shims


def shell_args(args: tuple[str, ...]) -> str:
    """Quote default args for a POSIX shell.

    A leading ``~`` (``~`` or ``~/...``) becomes ``"$HOME"`` so it expands for
    whoever runs the tool; everything else is quoted literally.
    """
    parts = []
    for a in args:
        if a == "~":
            parts.append('"$HOME"')
        elif a.startswith("~/"):
            parts.append('"$HOME"' + shlex.quote(a[1:]))
        else:
            parts.append(shlex.quote(a))
    return " ".join(parts)


def _write_arg_shims(suite_path: Path, shims: dict[str, tuple[str, ...]]) -> None:
    """Move rez's wrapper aside and put a shell shim that prepends args in its place.

    The real wrapper goes to <suite>/.rez-wrappers/<alias>, not under bin/,
    because rez locates the suite as the grandparent of the wrapper file.
    """
    if not shims:
        return
    bin_dir = suite_path / "bin"
    hidden = suite_path / SHIM_DIR
    hidden.mkdir(exist_ok=True)
    for alias, args in shims.items():
        (bin_dir / alias).rename(hidden / alias)
        quoted = shell_args(args)
        script = (
            "#!/bin/sh\n"
            f"# sweetrez shim: runs rez's wrapper for {alias} with default arguments.\n"
            "# Set SWEETREZ_DEBUG=1 to print the exact command before it runs.\n"
            'here=$(cd "$(dirname "$0")" && pwd)\n'
            f'target="$here/../{SHIM_DIR}/{alias}"\n'
            f'set -- {quoted} "$@"\n'
            'if [ -n "${SWEETREZ_DEBUG:-}" ]; then\n'
            f'    printf \'sweetrez: exec %s %s\' "$target" "{quoted}" >&2\n'
            f'    shift {len(args)}\n'
            "    printf ' %s' \"$@\" >&2\n"
            "    printf '\\n' >&2\n"
            f'    set -- {quoted} "$@"\n'
            "fi\n"
            'exec "$target" "$@"\n'
        )
        shim = bin_dir / alias
        shim.write_text(script)
        shim.chmod(0o755)

def build_suite(
    recipe: Recipe,
    store: SuiteStore,
    build_id: str | None = None,
    on_warning: Callable[[str], None] | None = None,
    on_info: Callable[[str], None] | None = None,
) -> Path:
    contexts = resolve_contexts(recipe)
    suite = assemble_suite(recipe, contexts)
    shims = resolve_arg_shims(recipe, suite)
    if on_info:
        for alias, args in shims.items():
            on_info(f"{alias}: default args {shell_args(args)}")
    conflicts = suite.get_conflicting_aliases()
    if conflicts and on_warning:
        on_warning(f"{recipe.name}: conflicting tools hidden: {', '.join(sorted(conflicts))}")
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
        _write_arg_shims(path, shims)
        shutil.copyfile(recipe.source_path, path / RECIPE_COPY_NAME)

    return store.write_build(recipe.name, build_id, writer)
