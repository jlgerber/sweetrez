from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rez.suite import Suite

Versions = dict[str, dict[str, str]]


@dataclass(frozen=True)
class Change:
    context: str
    package: str
    old: str | None
    new: str | None


def resolved_versions(build_path: Path) -> Versions:
    return suite_versions(Suite.load(str(build_path)))


def suite_versions(suite: Suite) -> Versions:
    result: Versions = {}
    for name in suite.context_names:
        ctx = suite.context(name)
        result[name] = {v.name: str(v.version) for v in ctx.resolved_packages or []}
    return result


def diff_versions(old: Versions, new: Versions) -> list[Change]:
    changes: list[Change] = []
    for context in sorted(set(old) | set(new)):
        old_pkgs = old.get(context, {})
        new_pkgs = new.get(context, {})
        for package in sorted(set(old_pkgs) | set(new_pkgs)):
            o, n = old_pkgs.get(package), new_pkgs.get(package)
            if o != n:
                changes.append(Change(context, package, o, n))
    return changes


def format_diff(changes: list[Change]) -> str:
    if not changes:
        return "no changes"
    lines = []
    for c in changes:
        old = c.old if c.old is not None else "(added)"
        new = c.new if c.new is not None else "(removed)"
        lines.append(f"  {c.context}: {c.package} {old} -> {new}")
    return "\n".join(lines)
