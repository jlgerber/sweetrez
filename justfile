# sweetrez task runner. Run `just` to list targets.

venv := ".venv"
python := venv / "bin/python"
rez_site := "/opt/rez/lib/python3.14/site-packages"
bin_dir := env("HOME") / ".local/bin"
conf_dir := env("HOME") / ".config/sweetrez"
conf := conf_dir / "conf.yaml"
default_root := "~/suites"
default_recipe_dir := "~/.config/sweetrez/recipes"

default:
    @just --list

# Create the project venv (with access to rez) and install sweetrez editable.
setup:
    test -x {{python}} || /usr/bin/python3.14 -m venv {{venv}}
    echo {{rez_site}} > {{venv}}/lib/python3.14/site-packages/rez.pth
    {{python}} -m pip install -q -e '.[dev]'
    {{python}} -c 'import rez, yaml, pytest, sweetrez'

# Write a default ~/.config/sweetrez/conf.yaml if none exists, and create the recipe dir.
config:
    #!/usr/bin/env bash
    set -euo pipefail
    if [ -e "{{conf}}" ]; then
        echo "config exists, leaving it alone: {{conf}}"
    else
        mkdir -p "{{conf_dir}}"
        printf 'root: %s\nrecipe_dir: %s\n' "{{default_root}}" "{{default_recipe_dir}}" > "{{conf}}"
        echo "wrote {{conf}}"
    fi
    recipe_dir="{{default_recipe_dir}}"
    mkdir -p "${recipe_dir/#\~/$HOME}"

# Install: run setup and config, then symlink the sweetrez command into ~/.local/bin.
install: setup config
    mkdir -p {{bin_dir}}
    ln -sfn "{{justfile_directory()}}/{{venv}}/bin/sweetrez" {{bin_dir}}/sweetrez
    @echo "installed -> {{bin_dir}}/sweetrez"

# Create a recipe template named NAME in the configured recipe_dir, for you to edit.
new name:
    {{venv}}/bin/sweetrez new {{name}}

# Remove the ~/.local/bin symlink (leaves the venv alone).
uninstall:
    rm -f {{bin_dir}}/sweetrez

# Run the test suite.
test:
    {{python}} -m pytest -q
