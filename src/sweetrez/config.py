from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from .errors import ConfigError

DEFAULT_CONFIG_PATH = Path("~/.config/sweetrez/conf.yaml").expanduser()
_REQUIRED_KEYS = ("root", "recipe_dir")


@dataclass(frozen=True)
class Config:
    root: Path
    recipe_dir: Path


def load_config(path: Path | None = None) -> Config:
    path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    if not path.is_file():
        raise ConfigError(f"config file not found: {path}")
    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError as e:
        raise ConfigError(f"{path}: invalid YAML: {e}") from e
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: expected a mapping with keys {', '.join(_REQUIRED_KEYS)}")
    unknown = set(data) - set(_REQUIRED_KEYS)
    if unknown:
        raise ConfigError(f"{path}: unknown keys: {', '.join(sorted(unknown))}")
    values = {}
    for key in _REQUIRED_KEYS:
        value = data.get(key)
        if not isinstance(value, str) or not value:
            raise ConfigError(f"{path}: '{key}' must be a non-empty path string")
        values[key] = Path(value).expanduser()
    return Config(**values)
