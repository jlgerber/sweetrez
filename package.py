# rez package for sweetrez. Install with `just rez-install` (rez-build --install)
# from the repository root.
#
# package.py is evaluated both at build (source tree present) and at resolve
# (only the installed copy present), so the version comes from an @early()
# reader that runs at build time only and is baked into the installed file.

name = "sweetrez"


# Read the version from pyproject.toml, the single source of truth. A build runs
# from the repository root, so pyproject.toml is in the working directory. A
# regex rather than tomllib, because tomllib needs Python 3.11 and this runs
# under whatever Python rez was installed with.
@early()
def version():
    import os
    import re

    pyproject = os.path.join(os.getcwd(), "pyproject.toml")
    if not os.path.isfile(pyproject):
        raise RuntimeError(
            "sweetrez package.py: pyproject.toml not found in %s; run rez-build "
            "from the repository root (where package.py lives)." % os.getcwd()
        )
    with open(pyproject) as f:
        match = re.search(r'^version\s*=\s*"([^"]+)"', f.read(), re.MULTILINE)
    if not match:
        raise RuntimeError("sweetrez package.py: no version in pyproject.toml")
    return match.group(1)


authors = ["Jonathan Gerber"]

description = "Build versioned rez suites from YAML recipes."

tools = ["sweetrez"]

# Pure Python, so no variants. PyYAML comes from `rez-pip --install pyyaml`.
requires = ["python-3.9+", "rez-3", "PyYAML-6"]

build_command = "python {root}/rezbuild.py"


def commands():
    env.PATH.prepend("{root}/bin")
    env.PYTHONPATH.prepend("{root}/python")


tests = {
    "version": "sweetrez --version",
}
