"""
Load "config/*.lua" data files.

The config files used to be python modules loaded via importlib; they are now
lua data files (config/project.lua and friends). A file is run in a fresh lua
runtime and the globals it declares are returned as a plain dict.
"""

import os.path
from typing import Any

# lupa exposes LuaRuntime through a module level __getattr__ that points at the
# bundled lua version (lupa.lua54, lupa.lua55, ...), so it cannot be imported
# by name. Going through the package attribute works for any bundled version.
import lupa

CONFIG_FOLDER = "config"


def lua_to_python(value: Any) -> Any:
    """
    Recursively convert a lua value into its python equivalent.

    Lua has a single table type, so a table is a list if its keys are exactly
    1..n and a dict otherwise. An empty table becomes an empty list, which
    matches how the config files use them.
    """
    if not hasattr(value, "values"):
        return value
    keys = list(value.keys())
    if keys == list(range(1, len(keys) + 1)):
        return [lua_to_python(x) for x in value.values()]
    return {k: lua_to_python(value[k]) for k in keys}


def config_path(name: str) -> str:
    """ return the path of a config file by its short name ("project") """
    return os.path.join(CONFIG_FOLDER, f"{name}.lua")


def load_lua_file(path: str) -> dict[str, Any]:
    """
    Run a lua file and return the globals it declared as a dict.

    Raises FileNotFoundError if the file does not exist.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    runtime = lupa.LuaRuntime()
    with open(path, encoding="utf-8") as stream:
        runtime.execute(stream.read())
    globals_table = runtime.globals()
    values = {}
    for key in globals_table:
        # skip the lua standard library, we only want what the file declared
        if key in _LUA_BUILTINS:
            continue
        values[key] = lua_to_python(globals_table[key])
    return values


_LUA_BUILTINS = frozenset({
    "_G", "_VERSION", "assert", "collectgarbage", "coroutine", "debug", "dofile",
    "error", "getmetatable", "io", "ipairs", "load", "loadfile", "math", "next",
    "os", "package", "pairs", "pcall", "print", "python", "rawequal", "rawget",
    "rawlen", "rawset", "require", "select", "setmetatable", "string", "table",
    "tonumber", "tostring", "type", "utf8", "warn", "xpcall",
})
