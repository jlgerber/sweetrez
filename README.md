# sweetrez

Build versioned [rez](https://github.com/AcademySoftwareFoundation/rez) suites
from YAML recipes. The recipe is the source of truth; suites on disk are build
products that can be regenerated at any time, so a scheduled rebuild picks up
new package versions inside the requested ranges.

## Install

sweetrez uses the rez Python API. The rez venv at `/opt/rez` is root-owned,
so sweetrez lives in its own venv that can see rez through a `.pth` file:

```bash
/usr/bin/python3.14 -m venv .venv
echo /opt/rez/lib/python3.14/site-packages > .venv/lib/python3.14/site-packages/rez.pth
.venv/bin/pip install -e '.[dev]'
ln -s "$PWD/.venv/bin/sweetrez" ~/.local/bin/sweetrez
```

## Configure

`~/.config/sweetrez/conf.yaml`:

```yaml
root: ~/suites          # suites are built here
recipe_dir: ~/recipes   # *.yaml recipes live here
```

## Recipe

```yaml
name: lighting
description: Lighting DCCs pinned to the studio USD line.
contexts:
  maya:
    requires: [maya-2025, usd-24, renderman-26+]
    prefix: ""                 # optional; or suffix
    alias: {mayapy: maya_py}   # optional, tool -> alias
    hide: [some_tool]          # optional
  houdini:
    requires: [houdini-20.5, usd-24]
```

`alias` and `hide` only accept tools from packages listed in `requires`, not
from their dependencies. That is a rez rule.

## Commands

```bash
sweetrez build lighting        # resolve every context; write nothing if any fails
sweetrez build --all           # every recipe in recipe_dir (good for cron)
sweetrez promote lighting      # point current -> newest build
sweetrez promote lighting 2026-09-01T09-00-00   # roll back
sweetrez list                  # suites, builds, promoted marked with *
sweetrez diff lighting         # promoted vs newest, resolved versions only
sweetrez diff lighting 2026-09-01T09-00-00 2026-09-06T14-32-10
```

`build` never touches `current`. Activate a suite by putting
`<root>/<name>/current/bin` on your `PATH`. rez's own `/opt/rez/bin/rez`
directory must also be on `PATH`, because the wrapper scripts in `bin/`
start with `#!/usr/bin/env _rez_fwd`, which resolves through that
directory.

## Layout

```
<root>/lighting/
  2026-09-06T14-32-10/   # rez suite: bin/, contexts/*.rxt, suite.yaml, recipe.yaml
  2026-09-01T09-00-00/
  current -> 2026-09-06T14-32-10
```

Builds are written to a `.tmp-<id>` directory and renamed into place, so a
half-written build is never visible to `list`, `diff`, or `promote`.

## Tests

```bash
.venv/bin/python -m pytest
```

Tests resolve real packages from `tests/packages` with the real rez API.
