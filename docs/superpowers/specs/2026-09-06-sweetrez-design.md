# sweetrez design

Agreed 2026-09-06 in a grilling session.

## Purpose

`sweetrez` builds [rez](https://github.com/AcademySoftwareFoundation/rez) suites
from versioned YAML recipes so that suites are reproducible (the recipe is the
source of truth, the suite on disk is a build product) and can be rebuilt on a
schedule as packages update (requests are version ranges; every rebuild
re-resolves and regenerates the `.rxt` context files).

## Recipe

```yaml
name: lighting
description: Lighting DCCs pinned to the studio USD line.
contexts:
  maya:
    requires: [maya-2025, usd-24, renderman-26+]
    prefix: ""            # optional; or suffix
    alias: {mayapy: maya_py}   # optional, tool -> alias
    hide: [some_tool]     # optional
  houdini:
    requires: [houdini-20.5, usd-24]
```

- `name` is required and is the suite's identity. Duplicate names across the
  recipe directory are a hard error.
- `description` is optional free text.
- `contexts` is a non-empty mapping. Each context has a non-empty `requires`
  list and optional `prefix`, `suffix`, `alias`, `hide`. That is exactly what
  `rez-suite` can express, nothing more.
- Rez validates `alias` and `hide` against tools of *requested* packages only
  (not transitive dependencies). A bad alias/hide is a build failure.

## Configuration

`~/.config/sweetrez/conf.yaml`:

```yaml
root: /home/me/suites        # where suites are built
recipe_dir: /home/me/recipes # where *.yaml recipes live
```

The CLI accepts `--config PATH` to point at another file.

## On-disk layout

```
<root>/
  lighting/
    2026-09-06T14-32-10/     # a normal rez suite dir: bin/, contexts/*.rxt, suite.yaml
      recipe.yaml            # copy of the recipe used for this build
    2026-09-01T09-00-00/
    current -> 2026-09-06T14-32-10
```

- Build ids are local-time timestamps formatted `%Y-%m-%dT%H-%M-%S`, so
  lexicographic order is chronological.
- A build is written into `<root>/<name>/.tmp-<id>` and renamed into place on
  success. Dot-prefixed directories are invisible to every command.
- `current` is a relative symlink to the promoted build. No lock file.

## Commands

- `sweetrez build <name>... | --all`: resolve every context of the recipe
  first; if any fails (unresolvable range, conflict, bad alias/hide), report all
  failures and write nothing. Otherwise write the suite and the recipe copy.
  Never touches `current`.
- `sweetrez promote <name> [<build-id>]`: repoint `current`; defaults to the
  newest build. Rollback is the same command with an older id.
- `sweetrez list [<name>]`: suites, their builds, and which is promoted.
- `sweetrez diff <name> [<old> [<new>]]`: resolved package versions per
  context; `old` defaults to the promoted build, `new` to the newest build.
  Only package versions are compared.

## Implementation

- Python package (`pyproject.toml`, `src/` layout), editable-installed into the
  rez venv at `/opt/rez` so it can use the rez API directly
  (`rez.resolved_context.ResolvedContext`, `rez.suite.Suite`).
- Integration tests with pytest against tiny fixture packages checked into
  `tests/packages`, run with the rez venv's Python. No mocking of rez.
- Linux, single user.
