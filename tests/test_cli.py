import pytest

from sweetrez.cli import main

RECIPE_A = """\
name: alpha
contexts:
  a:
    requires: [foo-1+]
"""
RECIPE_B = """\
name: beta
contexts:
  b:
    requires: [bar]
"""
RECIPE_BAD = """\
name: broken
contexts:
  x:
    requires: [foo-9+]
"""


@pytest.fixture
def env(package_repo, tmp_path, write_recipe):
    recipes = tmp_path / "recipes"
    root = tmp_path / "root"
    conf = tmp_path / "conf.yaml"
    conf.write_text(f"root: {root}\nrecipe_dir: {recipes}\n")
    write_recipe(recipes, RECIPE_A, "alpha.yaml")
    write_recipe(recipes, RECIPE_B, "beta.yaml")

    def run(*args):
        return main(["--config", str(conf), *args])

    return type("Env", (), {"run": staticmethod(run), "root": root, "recipes": recipes, "conf": conf})


def test_build_one(env, capsys):
    assert env.run("build", "alpha") == 0
    out = capsys.readouterr().out
    assert out.startswith("built alpha ")
    build_id = out.split()[2]
    assert (env.root / "alpha" / build_id / "suite.yaml").is_file()
    assert not (env.root / "alpha" / "current").exists()


def test_build_unknown_recipe(env, capsys):
    assert env.run("build", "nope") == 1
    assert "nope" in capsys.readouterr().err


def test_build_all_continues_past_failures(env, write_recipe, capsys):
    write_recipe(env.recipes, RECIPE_BAD, "broken.yaml")
    assert env.run("build", "--all") == 1
    captured = capsys.readouterr()
    assert "built alpha " in captured.out
    assert "built beta " in captured.out
    assert "broken" in captured.err and "foo-9+" in captured.err
    assert not (env.root / "broken").exists()


def test_build_requires_name_or_all(env):
    with pytest.raises(SystemExit) as info:
        env.run("build")
    assert info.value.code == 2


def test_promote_and_list(env, capsys):
    env.run("build", "alpha")
    first = capsys.readouterr().out.split()[2]
    assert env.run("promote", "alpha") == 0
    assert capsys.readouterr().out == f"promoted alpha -> {first}\n"
    assert env.run("list") == 0
    assert capsys.readouterr().out == f"alpha\n  {first} *\n"
    env.run("build", "beta")
    capsys.readouterr()
    assert env.run("list", "beta") == 0
    out = capsys.readouterr().out
    assert out.startswith("beta\n  ") and not out.rstrip().endswith("*")


def test_list_unknown_suite(env, capsys):
    assert env.run("list", "ghost") == 1
    assert "ghost" in capsys.readouterr().err


def test_promote_specific_build(env, capsys):
    env.run("build", "alpha")
    first = capsys.readouterr().out.split()[2]
    import time; time.sleep(1.1)  # build ids have one-second resolution
    env.run("build", "alpha")
    second = capsys.readouterr().out.split()[2]
    assert first != second
    assert env.run("promote", "alpha", first) == 0
    assert capsys.readouterr().out == f"promoted alpha -> {first}\n"
    env.run("list", "alpha")
    assert capsys.readouterr().out == f"alpha\n  {first} *\n  {second}\n"


def test_promote_without_builds(env, capsys):
    assert env.run("promote", "alpha") == 1
    assert "no builds" in capsys.readouterr().err


def test_diff_promoted_vs_newest(env, add_package, package_repo, capsys):
    env.run("build", "alpha")
    first = capsys.readouterr().out.split()[2]
    env.run("promote", "alpha")
    add_package(package_repo, "foo", "1.2.0", tools=["foo", "foo-helper"])
    import time; time.sleep(1.1)
    env.run("build", "alpha")
    second = capsys.readouterr().out.split()[2]
    assert env.run("diff", "alpha") == 0
    assert capsys.readouterr().out == f"alpha: {first} -> {second}\n  a: foo 1.1.0 -> 1.2.0\n"
    assert env.run("diff", "alpha", first, first) == 0
    assert capsys.readouterr().out == f"alpha: {first} -> {first}\nno changes\n"


def test_diff_without_promoted(env, capsys):
    env.run("build", "alpha")
    capsys.readouterr()
    assert env.run("diff", "alpha") == 1
    assert "nothing promoted" in capsys.readouterr().err


def test_missing_config(tmp_path, capsys):
    assert main(["--config", str(tmp_path / "none.yaml"), "list"]) == 1
    assert "not found" in capsys.readouterr().err
