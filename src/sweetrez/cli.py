from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rez.exceptions import RezError

from . import __version__
from .build import build_suite
from .config import Config, load_config
from .contents import CONTEXTS, PACKAGES, WRAPPERS, format_contents, load_contents
from .diff import diff_versions, format_diff, resolved_versions
from .errors import RecipeError, StoreError, SweetrezError
from .recipe import Recipe, load_recipes, write_recipe_template
from .store import SuiteStore


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sweetrez", description="Build rez suites from YAML recipes.")
    p.add_argument("--config", type=Path, default=None, help="path to conf.yaml")
    p.add_argument("--version", action="version", version=f"sweetrez {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    b = sub.add_parser("build", help="resolve a recipe and write a new build")
    b.add_argument("names", nargs="*", metavar="NAME")
    b.add_argument("--all", action="store_true", help="build every recipe in recipe_dir")

    pr = sub.add_parser("promote", help="point 'current' at a build")
    pr.add_argument("name", metavar="NAME")
    pr.add_argument("build_id", nargs="?", metavar="BUILD_ID")

    ls = sub.add_parser("list", help="list suites and builds")
    ls.add_argument("name", nargs="?", metavar="NAME")

    n = sub.add_parser("new", help="create a recipe template in recipe_dir for you to fill in")
    n.add_argument("name", metavar="NAME")

    d = sub.add_parser("diff", help="diff resolved package versions between two builds")
    d.add_argument("name", metavar="NAME")
    d.add_argument("old", nargs="?", metavar="OLD")
    d.add_argument("new", nargs="?", metavar="NEW")

    c = sub.add_parser("contents", help="list a build's contexts, packages, or wrappers")
    c.add_argument("name", metavar="NAME")
    c.add_argument("build_id", nargs="?", metavar="BUILD_ID", help="defaults to the promoted build")
    c.add_argument("--contexts", action="store_true", help="list context names")
    c.add_argument("--packages", action="store_true",
                   help="list resolved packages under each context (the default)")
    c.add_argument("--wrappers", action="store_true", help="list the tools in bin/ and where they come from")
    return p


def _select_recipes(cfg: Config, names: list[str], build_all: bool) -> list[Recipe]:
    recipes = load_recipes(cfg.recipe_dir)
    if build_all:
        return list(recipes.values())
    names = list(dict.fromkeys(names))
    missing = [n for n in names if n not in recipes]
    if missing:
        raise RecipeError(
            f"no recipe named {', '.join(missing)} in {cfg.recipe_dir} "
            f"(known: {', '.join(sorted(recipes)) or 'none'})"
        )
    return [recipes[n] for n in names]


def cmd_build(cfg: Config, args) -> int:
    store = SuiteStore(cfg.root)
    failed = False
    for recipe in _select_recipes(cfg, args.names, args.all):
        notes: list[str] = []
        try:
            path = build_suite(
                recipe,
                store,
                on_warning=lambda msg: print(f"warning: {msg}", file=sys.stderr),
                on_info=notes.append,
            )
        except (SweetrezError, OSError, RezError) as e:
            failed = True
            print(f"error: {e}", file=sys.stderr)
            continue
        print(f"built {recipe.name} {path.name} -> {path}")
        for note in notes:
            print(f"  {note}")
    return 1 if failed else 0


def cmd_promote(cfg: Config, args) -> int:
    store = SuiteStore(cfg.root)
    build_id = store.promote(args.name, args.build_id)
    print(f"promoted {args.name} -> {build_id}")
    return 0


def _print_suite(store: SuiteStore, name: str) -> None:
    builds = store.builds(name)
    promoted = store.promoted(name)
    print(name)
    if not builds:
        print("  (no builds)")
    for build_id in builds:
        print(f"  {build_id}{' *' if build_id == promoted else ''}")


def cmd_list(cfg: Config, args) -> int:
    store = SuiteStore(cfg.root)
    if args.name:
        if not store.suite_dir(args.name).is_dir():
            raise StoreError(f"no such suite: {args.name}")
        _print_suite(store, args.name)
    else:
        for name in store.suites():
            _print_suite(store, name)
    return 0


def cmd_diff(cfg: Config, args) -> int:
    store = SuiteStore(cfg.root)
    old = args.old
    if old is None:
        old = store.promoted(args.name)
        if old is None:
            raise StoreError(f"{args.name}: nothing promoted; pass OLD explicitly")
    new = args.new
    if new is None:
        new = store.newest(args.name)
        if new is None:
            raise StoreError(f"{args.name}: no builds")
    changes = diff_versions(
        resolved_versions(store.build_path(args.name, old)),
        resolved_versions(store.build_path(args.name, new)),
    )
    print(f"{args.name}: {old} -> {new}")
    print(format_diff(changes))
    return 0


def cmd_contents(cfg: Config, args) -> int:
    store = SuiteStore(cfg.root)
    build_id = args.build_id
    if build_id is None:
        build_id = store.promoted(args.name)
        if build_id is None:
            raise StoreError(f"{args.name}: nothing promoted; pass BUILD_ID explicitly")
    flags = {CONTEXTS: args.contexts, PACKAGES: args.packages, WRAPPERS: args.wrappers}
    sections = [s for s, on in flags.items() if on] or [PACKAGES]
    print(format_contents(load_contents(store.build_path(args.name, build_id)), sections))
    return 0


def cmd_new(cfg: Config, args) -> int:
    path = write_recipe_template(cfg.recipe_dir, args.name)
    print(f"created {path}")
    return 0


_COMMANDS = {
    "build": cmd_build,
    "promote": cmd_promote,
    "list": cmd_list,
    "diff": cmd_diff,
    "new": cmd_new,
    "contents": cmd_contents,
}


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.command == "build" and not args.names and not args.all:
        parser.error("build requires NAME... or --all")
    if args.command == "build" and args.names and args.all:
        parser.error("build takes NAME... or --all, not both")
    try:
        cfg = load_config(args.config)
        return _COMMANDS[args.command](cfg, args)
    except (SweetrezError, OSError, RezError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
