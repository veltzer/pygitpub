import config.project

package_name = config.project.project_name

console_scripts = [
    'pygitpub=pygitpub.main:main',
]

setup_requires = [
]

run_requires = [
    'pytconf',
    'pylogconf',
    'PyGithub',
]

test_requires = [
    'pylint',
    'pytest',
    'pytest-cov',
    'flake8',
    'pymakehelper',
]

dev_requires = [
    'pyclassifiers',
    'pypitools',
    'pydmt',
    'Sphinx',
    'pyyaml',
]

install_requires = list(setup_requires)
install_requires.extend(run_requires)

python_requires = ">=3.9"

extras_require = {
}
test_os = "[ubuntu-20.04]"
test_python = "[3.7, 3.8, 3.9]"
test_container = "[ubuntu:20.04]"
