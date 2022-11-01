"""
main entry point to the program
"""

import os
import subprocess
import sys
import json

import pylogconf.core
from pytconf import register_main, config_arg_parse_and_launch, register_endpoint

import github
from pygitpub.configs import ConfigGithub, ConfigOutput, ConfigAlgo
from pygitpub.static import VERSION_STR
from pygitpub.utils import delete


def yield_repos():
    g = github.Github(login_or_token=ConfigGithub.token)
    for repo in g.get_user().get_repos():
        reason = "no reason set"
        skip = False
        if not ConfigAlgo.fork and repo.fork:
            reason = "repo is a fork"
            skip = True
        if ConfigAlgo.owner is not None and repo.owner.name != ConfigAlgo.owner:
            reason = f"wrong owner [{repo.owner.name}]"
            skip = True
        if not ConfigAlgo.private and repo.private:
            reason = "repo is private"
            skip = True
        if not ConfigAlgo.public and not repo.private:
            reason = "repo is public"
            skip = True
        if skip:
            if ConfigOutput.verbose:
                print(f"skipping [{repo.name}] because [{reason}]...")
            continue
        yield repo


@register_endpoint(
    description="Set the correct website for the project on all repos where it is not correct",
    configs=[
        ConfigGithub,
        ConfigAlgo,
    ],
)
def fix_website() -> None:
    for repo in yield_repos():
        if repo.homepage == "" or repo.homepage is None:
            homepage = f"{repo.html_url}"
            print(f"patching [{repo.name}]...")
            repo.edit(repo.name, homepage=homepage)


@register_endpoint(
    description="List repos",
    configs=[
        ConfigGithub,
        ConfigOutput,
        ConfigAlgo,
    ],
)
def repos_list() -> None:
    for repo in yield_repos():
        if ConfigOutput.verbose:
            obj = json.loads(repo.raw_data)
            json.dump(obj=obj, fp=sys.stdout, indent=4, sort_keys=True)
        else:
            print(f"{repo.name}")


@register_endpoint(
    description="Cleanup old failing or un-needed runs in all workflows in all repositories",
    configs=[
        ConfigGithub,
        ConfigOutput,
        ConfigAlgo,
    ],
)
def runs_cleanup() -> None:
    for repo in yield_repos():
        for workflow in repo.get_workflows():
            existing = 0
            for run in workflow.get_runs():
                if ConfigOutput.verbose:
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
    description="Show all runs in all workflows in all repos",
    configs=[
        ConfigGithub,
        ConfigAlgo,
    ],
)
def runs_show() -> None:
    for repo in yield_repos():
        for workflow in repo.get_workflows():
            for run in workflow.get_runs():
                print(f"{repo.name}: {workflow.name} {run.conclusion}")


@register_endpoint(
    description="Show all running runs in all workflows in all repositories",
    configs=[
        ConfigGithub,
        ConfigAlgo,
    ],
)
def runs_show_running() -> None:
    for repo in yield_repos():
        for workflow in repo.get_workflows():
            for run in workflow.get_runs():
                if run.conclusion is None:
                    print(f"{repo.name}: {workflow.name} {run.conclusion}")


@register_endpoint(
    description="Show all runs which are last and failing in all workflows and all repositories",
    configs=[
        ConfigGithub,
        ConfigAlgo,
    ],
)
def runs_show_failing() -> None:
    for repo in yield_repos():
        for workflow in repo.get_workflows():
            for run in workflow.get_runs():
                last_run = run
                break
            else:
                continue
            if last_run.conclusion == "failure":
                print(f"{repo.name}: {workflow.name} {last_run.conclusion}")


@register_endpoint(
    description="Pull all projects from github",
    configs=[
        ConfigGithub,
    ],
)
def pull_all() -> None:
    for repo in yield_repos():
        folder = repo.name
        project = folder
        if os.path.isdir(folder):
            if not os.path.isfile(os.path.join(folder, ".skip")):
                print(f"project [{project}] exists, pulling it...")
                os.chdir(folder)
                subprocess.check_call(
                    [
                        "git",
                        "pull",
                        # '--tags',
                    ]
                )
                os.chdir("..")
            else:
                print(f"project [{project}] exists, skipping it because of .skip file...")
        else:
            print(f"project [{project}] does not exists, cloning it from [{repo.ssh_url}]...")
            subprocess.check_call(
                [
                    "git",
                    "clone",
                    repo.ssh_url,
                ]
            )


@register_endpoint(
    description="Pull all projects from github",
    configs=[
        ConfigGithub,
    ],
)
def clone_all() -> None:
    for repo in yield_repos():
        folder = repo.name
        project = folder
        print(f"considering [{project}] from [{repo.ssh_url}]...")
        if os.path.isfile(folder):
            print(f"skipping [{folder}] as it is not to be cloned...")
            continue
        if os.path.isdir(folder):
            print(f"skipping [{folder}] as it is already cloned...")
            continue
        print(f"project [{project}] does not exist, cloning it from [{repo.ssh_url}]...")
        subprocess.check_call(
            [
                "git",
                "clone",
                repo.ssh_url,
            ]
        )


@register_endpoint(
    description="Run all workflows",
    configs=[
        ConfigGithub,
        ConfigOutput,
        ConfigAlgo,
    ],
)
def workflows_run() -> None:
    for repo in yield_repos():
        for workflow in repo.get_workflows():
            print(f"{repo.name}: {workflow.name}...", end='')
            sys.stdout.flush()
            ret = workflow.create_dispatch(ref="master")
            print(f"{ret}")


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
