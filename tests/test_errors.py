import sweetrez
from sweetrez import errors


def test_version():
    assert sweetrez.__version__ == "0.1.0"


def test_all_errors_share_a_base():
    for cls in (errors.ConfigError, errors.RecipeError, errors.StoreError, errors.BuildError):
        assert issubclass(cls, errors.SweetrezError)
