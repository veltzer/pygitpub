""" python deps for this project """

import config.shared

install_requires: list[str] = [
    "pytconf",
    "pylogconf",
    "PyGithub",
    "pyapikey",
    "pyyaml",
]
build_requires: list[str] = [
    "hatch",
    "pydmt",
    "pymakehelper",
    "pycmdtools",
]
test_requires: list[str] = [
    "pylint",
    "pytest",
    "mypy",
    "ruff",
]
requires = install_requires + build_requires + test_requires

dcripts: dict[str,str] = {
    "pygitpub": "pygitpub.main:main",
}
