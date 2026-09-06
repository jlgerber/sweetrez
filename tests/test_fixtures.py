from rez.resolved_context import ResolvedContext


def _versions(ctx):
    return {v.name: str(v.version) for v in ctx.resolved_packages}


def test_foo_range_resolves_newest(package_repo):
    assert _versions(ResolvedContext(["foo-1+"])) == {"foo": "1.1.0"}


def test_bar_pulls_foo_1_0(package_repo):
    assert _versions(ResolvedContext(["bar"])) == {"bar": "2.0.0", "foo": "1.0.0"}


def test_added_package_is_visible(package_repo, add_package):
    add_package(package_repo, "foo", "1.2.0", tools=["foo", "foo-helper"])
    assert _versions(ResolvedContext(["foo-1+"])) == {"foo": "1.2.0"}
