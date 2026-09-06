name = "bar"
version = "2.0.0"
requires = ["foo-1.0"]
tools = ["bar"]

def commands():
    env.PATH.prepend("{root}/bin")
