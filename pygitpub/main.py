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
import pygitpub.static
from pygitpub.utils.misc import delete, get_all_git_repos
from pygitpub.utils.importlib import import_file


def yield_repos():
    g = github.Github(login_or_token=ConfigGithub.token)
    for repo in g.get_user().get_repos():
        reason = "no reason set"
        skip = False
        if not ConfigAlgo.fork and repo.fork:
            reason = "repo is a fork"
            skip = True
        if ConfigAlgo.owner_login is not None and repo.owner.login != ConfigAlgo.owner_login:
            reason = f"wrong owner [{repo.owner.login}]"
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
    description="Fix the metadata of the project on github to match the source code",
    configs=[
        ConfigGithub,
        ConfigAlgo,
    ],
)
def check_metadata() -> None:
    orig_folder = os.getcwd()
    for repo in yield_repos():
        owner = repo.owner.login
        folder = os.path.join(owner, repo.name)
        if not os.path.isdir(folder):
            # print(f"folder [{folder}] does not exist, continuing...")
            continue
        os.chdir(folder)
        file_path = "config/project.py"
        if not os.path.isfile(file_path):
            os.chdir(orig_folder)
            continue
        mod = import_file(file_path)
        if not hasattr(mod, "description_short"):
            os.chdir(orig_folder)
            continue
        description_short = getattr(mod, "description_short")
        if description_short != repo.description:
            print(f"in {folder}...")
            print(f"description_short is [{description_short}]")
            print(f"repo.description is [{repo.description}]")
        os.chdir(orig_folder)


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
    description="Show name and website for each repo",
    configs=[
        ConfigGithub,
        ConfigAlgo,
    ],
)
def show_website() -> None:
    for repo in yield_repos():
        print(f"{repo.name} {repo.html_url}")


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
            json.dump(obj=repo.raw_data, fp=sys.stdout, indent=4, sort_keys=True)
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
    description="Show all runs which are not success at last run",
    configs=[
        ConfigGithub,
        ConfigAlgo,
    ],
)
def runs_show_not_success() -> None:
    for repo in yield_repos():
        for workflow in repo.get_workflows():
            for run in workflow.get_runs():
                last_run = run
                break
            else:
                continue
            if last_run.conclusion != "success":
                print(f"{repo.name}: {workflow.name} {last_run.conclusion}")


@register_endpoint(
    description="Pull all projects from github",
    configs=[
        ConfigGithub,
    ],
)
def pull_all() -> None:
    orig_folder = os.getcwd()
    for repo in yield_repos():
        owner = repo.owner.login
        project = repo.name
        folder = os.path.join(owner, repo.name)
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
                os.chdir(orig_folder)
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
        ConfigAlgo,
    ],
)
def clone_all() -> None:
    all_repo_folders = set()
    for repo in yield_repos():
        owner = repo.owner.login
        project = repo.name
        folder = os.path.join(owner, repo.name)
        all_repo_folders.add(folder)
        # print(f"considering [{project}] from [{repo.ssh_url}]...")
        if os.path.isfile(folder):
            # print(f"skipping [{folder}] as it is not to be cloned...")
            continue
        if os.path.isdir(folder):
            # print(f"skipping [{folder}] as it is already cloned...")
            continue
        if ConfigAlgo.dryrun:
            continue
        print(f"cloning [{owner}:{project}] from [{repo.ssh_url}] to [{folder}]")
        if not os.path.isdir(owner):
            os.mkdir(owner)
        subprocess.check_call(
            [
                "git",
                "clone",
                repo.ssh_url,
            ],
            cwd=owner,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    if ConfigAlgo.show_extra:
        disk_repos = get_all_git_repos()
        extra_repos = disk_repos - all_repo_folders
        if extra_repos:
            print("extra repos follow:")
            for extra_repo in extra_repos:
                print(extra_repo)


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
    main_description=pygitpub.static.DESCRIPTION,
    app_name=pygitpub.static.APP_NAME,
    version=pygitpub.static.VERSION_STR,
)
def main():
    pylogconf.core.setup()
    config_arg_parse_and_launch()


if __name__ == '__main__':
    main()
