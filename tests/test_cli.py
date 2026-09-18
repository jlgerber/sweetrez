import os

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
RECIPE_CONFLICT = """\
name: gamma
contexts:
  a:
    requires: [foo]
  b:
    requires: [foo]
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


def test_build_duplicate_name_is_deduped(env, capsys):
    assert env.run("build", "alpha", "alpha") == 0
    out = capsys.readouterr().out
    assert out.count("built alpha ") == 1


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


def test_build_all_continues_past_os_error(env, capsys):
    alpha_dir = env.root / "alpha"
    alpha_dir.mkdir(parents=True)
    os.chmod(alpha_dir, 0o500)
    try:
        assert env.run("build", "--all") == 1
    finally:
        os.chmod(alpha_dir, 0o700)
    captured = capsys.readouterr()
    assert "built beta " in captured.out
    assert "error:" in captured.err


def test_diff_against_non_suite_directory_is_clean_error(env, capsys):
    assert env.run("build", "alpha") == 0
    capsys.readouterr()
    bogus_id = "2026-01-01T00-00-00"
    (env.root / "alpha" / bogus_id).mkdir(parents=True)
    assert env.run("diff", "alpha", bogus_id) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "error:" in captured.err


def test_build_warns_on_conflicting_tools(env, write_recipe, capsys):
    write_recipe(env.recipes, RECIPE_CONFLICT, "gamma.yaml")
    assert env.run("build", "gamma") == 0
    captured = capsys.readouterr()
    assert "warning: gamma: conflicting tools hidden: foo, foo-helper" in captured.err


def test_build_requires_name_or_all(env):
    with pytest.raises(SystemExit) as info:
        env.run("build")
    assert info.value.code == 2


def test_build_name_and_all_together_is_error(env):
    with pytest.raises(SystemExit) as info:
        env.run("build", "alpha", "--all")
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
    capsys.readouterr()
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


def test_new_writes_template_into_recipe_dir(env, capsys):
    assert env.run("new", "gamma") == 0
    path = env.recipes / "gamma.yaml"
    assert capsys.readouterr().out == f"created {path}\n"
    assert path.is_file()
    assert env.run("list") == 0  # the template parses; nothing built yet


def test_new_refuses_existing_recipe(env, capsys):
    assert env.run("new", "alpha") == 1
    assert "exists" in capsys.readouterr().err
    assert env.recipes.joinpath("alpha.yaml").read_text() == RECIPE_A


def test_new_rejects_bad_name(env, capsys):
    assert env.run("new", "current") == 1
    assert "reserved" in capsys.readouterr().err


RECIPE_ARGS = """\
name: delta
contexts:
  d:
    requires: [foo-1+]
    alias: {foo: foo_d}
    args:
      foo: [--root, ~/books]
"""


def test_build_lists_default_args_per_tool(env, write_recipe, capsys):
    write_recipe(env.recipes, RECIPE_ARGS, "delta.yaml")
    assert env.run("build", "delta") == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith("built delta ")
    assert out[1] == '  foo_d: default args --root "$HOME"/books'


def test_contents_defaults_to_promoted_package_tree(env, capsys):
    assert env.run("build", "beta") == 0
    assert env.run("promote", "beta") == 0
    capsys.readouterr()
    assert env.run("contents", "beta") == 0
    assert capsys.readouterr().out == "b\n    bar-2.0.0\n    foo-1.0.0\n"


def test_contents_explicit_build_with_combined_flags(env, capsys):
    assert env.run("build", "beta") == 0
    build_id = capsys.readouterr().out.split()[2]
    assert env.run("contents", "beta", build_id, "--wrappers", "--contexts") == 0
    assert capsys.readouterr().out == (
        "contexts:\n"
        "    b\n"
        "wrappers:\n"
        "    bar  (b: bar)\n"
    )


def test_contents_without_promoted(env, capsys):
    assert env.run("build", "beta") == 0
    assert env.run("contents", "beta") == 1
    assert "nothing promoted; pass BUILD_ID explicitly" in capsys.readouterr().err


def test_contents_unknown_build(env, capsys):
    assert env.run("build", "beta") == 0
    assert env.run("contents", "beta", "2000-01-01T00-00-00") == 1
    assert "no such build" in capsys.readouterr().err


def test_contents_short_flags(env, capsys):
    assert env.run("build", "beta") == 0
    build_id = capsys.readouterr().out.split()[2]
    assert env.run("contents", "beta", build_id, "-c", "-w") == 0
    long_out = capsys.readouterr().out
    assert env.run("contents", "beta", build_id, "--contexts", "--wrappers") == 0
    assert long_out == capsys.readouterr().out
    assert env.run("contents", "beta", build_id, "-p") == 0
    assert capsys.readouterr().out == "b\n    bar-2.0.0\n    foo-1.0.0\n"
