from typing import List


console_scripts: List[str] = [
    "pygitpub=pygitpub.main:main",
]
dev_requires: List[str] = [
    "pypitools",
]
config_requires: List[str] = [
    "pyyaml",
    "pyclassifiers",
]
install_requires: List[str] = [
    "pytconf",
    "pylogconf",
    "PyGithub",
]
build_requires: List[str] = [
    "pymakehelper",
    "pydmt",
]
test_requires: List[str] = [
    "pylint",
    "pytest",
    "pytest-cov",
    "flake8",
    "mypy",
]
requires = config_requires + install_requires + build_requires + test_requires
