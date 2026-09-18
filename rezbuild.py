"""rez build for sweetrez: copy the Python package and write a bin/ launcher.

Run by package.py's build_command. rez sets:
  REZ_BUILD_SOURCE_PATH   the repository root
  REZ_BUILD_PATH          the build directory (used when not installing)
  REZ_BUILD_INSTALL_PATH  where to install
  REZ_BUILD_INSTALL       "1" when installing (-i), else "0"
"""

import os
import shutil
import stat
import sys

LAUNCHER = """\
#!/usr/bin/env python
import sys
from sweetrez.cli import main
sys.exit(main())
"""


def main():
    src = os.path.join(os.environ["REZ_BUILD_SOURCE_PATH"], "src", "sweetrez")
    if os.environ.get("REZ_BUILD_INSTALL") == "1":
        dest = os.environ["REZ_BUILD_INSTALL_PATH"]
    else:
        dest = os.environ["REZ_BUILD_PATH"]

    python_dir = os.path.join(dest, "python", "sweetrez")
    if os.path.exists(python_dir):
        shutil.rmtree(python_dir)
    shutil.copytree(src, python_dir, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    bin_dir = os.path.join(dest, "bin")
    os.makedirs(bin_dir, exist_ok=True)
    launcher = os.path.join(bin_dir, "sweetrez")
    with open(launcher, "w") as f:
        f.write(LAUNCHER)
    mode = os.stat(launcher).st_mode
    os.chmod(launcher, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print("rezbuild: sweetrez -> %s" % dest)


if __name__ == "__main__":
    sys.exit(main())
