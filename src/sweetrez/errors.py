class SweetrezError(Exception):
    """Base class for every error sweetrez reports to the user."""


class ConfigError(SweetrezError):
    pass


class RecipeError(SweetrezError):
    pass


class StoreError(SweetrezError):
    pass


class BuildError(SweetrezError):
    pass
