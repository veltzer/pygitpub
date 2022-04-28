"""
main entry point to the program
"""

import pylogconf.core
from pytconf import register_main, config_arg_parse_and_launch, register_endpoint

import github
from pygitpub.configs import ConfigGithub
from pygitpub.static import VERSION_STR
from pygitpub.utils import delete


@register_endpoint(
    description="List all repos",
    configs=[
        ConfigGithub,
    ],
)
def repos_list() -> None:
    g = github.Github(login_or_token=ConfigGithub.token)
    for repo in g.get_user(ConfigGithub.username).get_repos():
        print(repo.name)


@register_endpoint(
    description="Cleanup old failing or un-needed runs",
    configs=[
        ConfigGithub,
    ],
)
def runs_cleanup() -> None:
    g = github.Github(login_or_token=ConfigGithub.token)
    for repo in g.get_user(ConfigGithub.username).get_repos():
        for workflow in repo.get_workflows():
            existing = 0
            for run in workflow.get_runs():
                print(f"inspecting {repo.name} {workflow.name} {run.conclusion}")
                delete_it = False
                # if it's a pages build delete it unless it's in mid work (run.conclusion is None)
                if workflow.name == "pages-build-deployment" and run.conclusion is not None:
                    delete_it = True
                # if it's not a paged build and it failed then delete it
                if workflow.name != "pages-build-deployment" and run.conclusion == "failure":
                    delete_it = True
                if existing >= 4:
                    delete_it = True
                if delete_it:
                    print(f"deleting {repo.name} {workflow.name} {run.conclusion} {run.url}")
                    delete(run)
                else:
                    existing += 1


@register_endpoint(
    description="Show workflow runs",
    configs=[
        ConfigGithub,
    ],
)
def runs_show() -> None:
    g = github.Github(login_or_token=ConfigGithub.token)
    for repo in g.get_user(ConfigGithub.username).get_repos():
        for workflow in repo.get_workflows():
            for run in workflow.get_runs():
                print(f"{repo.name}: {workflow.name} {run.conclusion}")


@register_endpoint(
    description="Show failing workflow last run",
    configs=[
        ConfigGithub,
    ],
)
def runs_show_failing() -> None:
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
