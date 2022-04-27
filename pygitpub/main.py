"""
main entry point to the program
"""

import pylogconf.core
from pytconf import register_main, config_arg_parse_and_launch, register_endpoint

from pygitpub.configs import ConfigGithub
from pygitpub.static import VERSION_STR


@register_endpoint(
    description="Show workflow runs",
    configs=[
        ConfigGithub,
    ],
)
def show_runs() -> None:
    g = github.Github(login_or_token=ConfigGithub.token)
    for repo in g.get_user(ConfigGithub.username).get_repos():
        for workflow in repo.get_workflows():
            for run in workflow.get_runs():
                print(f"{repo.name}: {workflow.name} {run.conclusion}")


@register_endpoint(
    description="Show failing workflows",
    configs=[
        ConfigGithub,
    ],
)
def show_failing_run() -> None:
    g = github.Github(login_or_token=ConfigGithub.token)
    for repo in g.get_user(ConfigGithub.username).get_repos():
        for workflow in repo.get_workflows():
            for run in workflow.get_runs():
                last_run = run
                break
            else:
                continue
            if last_run.conclusion != "success":
                print(f"{repo.name}: {workflow.name} {last_run.conclusion}")


@register_main(
    main_description="pygitpub will help you work with github",
    app_name="pygitpub",
    version=VERSION_STR,
)
def main():
    pylogconf.core.setup()
    config_arg_parse_and_launch()


if __name__ == '__main__':
    main()
