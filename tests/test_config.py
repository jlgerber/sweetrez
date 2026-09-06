from pathlib import Path

import pytest

from sweetrez.config import load_config
from sweetrez.errors import ConfigError


def test_loads_root_and_recipe_dir(tmp_path):
    conf = tmp_path / "conf.yaml"
    conf.write_text("root: /srv/suites\nrecipe_dir: /srv/recipes\n")
    cfg = load_config(conf)
    assert cfg.root == Path("/srv/suites")
    assert cfg.recipe_dir == Path("/srv/recipes")


def test_expands_user_in_paths(tmp_path):
    conf = tmp_path / "conf.yaml"
    conf.write_text("root: ~/suites\nrecipe_dir: ~/recipes\n")
    cfg = load_config(conf)
    assert cfg.root == Path.home() / "suites"
    assert cfg.recipe_dir == Path.home() / "recipes"


def test_missing_file_is_config_error(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nope.yaml")


@pytest.mark.parametrize("body", ["root: /x\n", "recipe_dir: /x\n", "- a\n", ""])
def test_missing_keys_or_wrong_shape_is_config_error(tmp_path, body):
    conf = tmp_path / "conf.yaml"
    conf.write_text(body)
    with pytest.raises(ConfigError):
        load_config(conf)


def test_unknown_key_is_config_error(tmp_path):
    conf = tmp_path / "conf.yaml"
    conf.write_text("root: /a\nrecipe_dir: /b\nbogus: 1\n")
    with pytest.raises(ConfigError, match="bogus"):
        load_config(conf)


def test_invalid_yaml_is_config_error(tmp_path):
    conf = tmp_path / "conf.yaml"
    conf.write_text("root: [1, 2\n")
    with pytest.raises(ConfigError, match="invalid YAML"):
        load_config(conf)
