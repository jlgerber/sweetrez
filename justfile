# sweetrez task runner. Run `just` to list targets.

venv := ".venv"
python := venv / "bin/python"
rez_site := "/opt/rez/lib/python3.14/site-packages"
bin_dir := env("HOME") / ".local/bin"

default:
    @just --list

# Create the project venv (with access to rez) and install sweetrez editable.
setup:
    test -x {{python}} || /usr/bin/python3.14 -m venv {{venv}}
    echo {{rez_site}} > {{venv}}/lib/python3.14/site-packages/rez.pth
    {{python}} -m pip install -q -e '.[dev]'
    {{python}} -c 'import rez, yaml, pytest, sweetrez'

# Install: run setup, then symlink the sweetrez command into ~/.local/bin.
install: setup
    mkdir -p {{bin_dir}}
    ln -sfn "{{justfile_directory()}}/{{venv}}/bin/sweetrez" {{bin_dir}}/sweetrez
    @echo "installed -> {{bin_dir}}/sweetrez"

# Remove the ~/.local/bin symlink (leaves the venv alone).
uninstall:
    rm -f {{bin_dir}}/sweetrez

# Run the test suite.
test:
    {{python}} -m pytest -q
