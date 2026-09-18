from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rez.suite import Suite

from .diff import Versions, suite_versions

CONTEXTS = "contexts"
PACKAGES = "packages"
WRAPPERS = "wrappers"
SECTIONS = (CONTEXTS, PACKAGES, WRAPPERS)
INDENT = "    "


@dataclass(frozen=True)
class Wrapper:
    tool: str  # name in bin/, after prefix, suffix, and alias
    context: str
    original: str  # tool name inside the context


@dataclass(frozen=True)
class SuiteContents:
    contexts: list[str]
    packages: Versions
    wrappers: list[Wrapper]


def load_contents(build_path: Path) -> SuiteContents:
    suite = Suite.load(str(build_path))
    wrappers = [
        Wrapper(alias, t["context_name"], t["tool_name"])
        for alias, t in sorted(suite.get_tools().items())
    ]
    return SuiteContents(sorted(suite.context_names), suite_versions(suite), wrappers)


def _contexts_lines(contents: SuiteContents) -> list[str]:
    return list(contents.contexts)


def _packages_lines(contents: SuiteContents) -> list[str]:
    lines = []
    for context in contents.contexts:
        lines.append(context)
        pkgs = contents.packages.get(context, {})
        lines.extend(f"{INDENT}{name}-{pkgs[name]}" for name in sorted(pkgs))
    return lines


def _wrappers_lines(contents: SuiteContents) -> list[str]:
    if not contents.wrappers:
        return ["(no wrappers)"]
    width = max(len(w.tool) for w in contents.wrappers)
    return [f"{w.tool:<{width}}  ({w.context}: {w.original})" for w in contents.wrappers]


_FORMATTERS = {CONTEXTS: _contexts_lines, PACKAGES: _packages_lines, WRAPPERS: _wrappers_lines}


def format_contents(contents: SuiteContents, sections: list[str]) -> str:
    """Render the requested sections in SECTIONS order; headers only when there are several."""
    chosen = [s for s in SECTIONS if s in sections]
    if len(chosen) == 1:
        return "\n".join(_FORMATTERS[chosen[0]](contents))
    lines = []
    for section in chosen:
        lines.append(f"{section}:")
        lines.extend(f"{INDENT}{line}" for line in _FORMATTERS[section](contents))
    return "\n".join(lines)
