import importlib.util


def module_exists(module_name):
    """ return if a module exists or not """
    spec = importlib.util.find_spec(module_name)
    return spec is not None


def import_file(file_path):
    spec = importlib.util.spec_from_file_location("foo", file_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
