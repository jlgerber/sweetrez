name = "foo"
version = "1.1.0"
tools = ["foo", "foo-helper"]

def commands():
    env.PATH.prepend("{root}/bin")
