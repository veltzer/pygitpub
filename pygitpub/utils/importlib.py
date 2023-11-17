from importlib.util import find_spec


def module_exists(module_name):
    """ return if a module exists or not """
    spec = find_spec(module_name)
    return spec is not None
