"""
main entry point to the program
"""

import json
import os
import subprocess
import sys
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import github
import pyapikey
import pylogconf.core
from pytconf import config_arg_parse_and_launch, register_endpoint, register_main
from pytconf.pydoc import get_first_line
from pytconf.registry import the_registry

import pygitpub.static
from pygitpub.configs import AFFILIATIONS, ConfigAlgo, ConfigGithub, ConfigOutput, ConfigRuns
from pygitpub.utils.lua import config_path, load_lua_file
from pygitpub.utils.misc import get_all_git_repos


def get_base_dir() -> str:
    base_dir: str = ConfigAlgo.base_dir
    return os.path.expanduser(base_dir)


def get_repo_folder(repo) -> str:
    return os.path.join(get_base_dir(), repo.name)


def get_affiliation() -> str:
    """ validate the affiliation parameter and return it in the form github wants """
    values: list[str] = [x.strip() for x in ConfigAlgo.affiliation.split(",")]
    values = [x for x in values if x != ""]
    if not values:
        raise ValueError("affiliation must not be empty")
    for value in values:
        if value not in AFFILIATIONS:
            raise ValueError(f"bad affiliation [{value}], must be one of [{','.join(AFFILIATIONS)}]")
    return ",".join(values)


def get_github(**kwargs: Any) -> github.Github:
    apikey = pyapikey.get_key(ConfigGithub.apikey)
    return github.Github(auth=github.Auth.Token(apikey), **kwargs)


def yield_repos():
    g = get_github()
    # github filters by affiliation server side, so repos we are not interested
    # in (org repos, by default) are never fetched in the first place
    affiliation = get_affiliation()
    for repo in g.get_user().get_repos(affiliation=affiliation):
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
def fix_metadata() -> None:
    for repo in yield_repos():
        folder = get_repo_folder(repo)
        if not os.path.isdir(folder):
            continue
        file_path = os.path.join(folder, config_path("project"))
        if not os.path.isfile(file_path):
            continue
        project = load_lua_file(file_path)
        if "DESCRIPTION_SHORT" not in project:
            continue
        description_short = project["DESCRIPTION_SHORT"]
        if description_short != repo.description:
            print(f"in {folder}...")
            print(f"description_short is [{description_short}]")
            print(f"repo.description is [{repo.description}]")
            if not ConfigAlgo.dryrun:
                repo.edit(description=description_short)
        if "KEYWORDS" not in project:
            print(f"{folder} no keywords")
            continue
        keywords = project["KEYWORDS"]
        if set(keywords) != set(repo.get_topics()):
            print(f"in {folder}...")
            print(f"keywords is [{keywords}]")
            print(f"repo.get_topics() is [{repo.get_topics()}]")
            if not ConfigAlgo.dryrun:
                repo.replace_topics(keywords)


@register_endpoint(
    description="Set the correct website for the project on all repos where it is not correct",
    configs=[
        ConfigGithub,
        ConfigOutput,
        ConfigAlgo,
    ],
)
def homepage_fix() -> None:
    for repo in yield_repos():
        owner = repo.owner.login
        # the user site repo is served at the root of the site, usually under
        # a custom domain, so the pattern below does not apply to it
        if repo.name.lower() == f"{owner.lower()}.github.io":
            if ConfigOutput.verbose:
                print(f"skipping [{repo.name}] because it is the user site")
            continue
        if repo.has_pages:
            right_homepage = f"https://{owner}.github.io/{repo.name}/"
        else:
            right_homepage = f"https://github.com/{owner}/{repo.name}/"
        if repo.homepage != right_homepage:
            print(f"{repo.name} is wrong!")
            print(f"homepage: {repo.homepage}")
            print(f"right_homepage: {right_homepage}")
            if not ConfigAlgo.dryrun:
                print(f"patching [{repo.name}]...")
                repo.edit(repo.name, homepage=right_homepage)


@register_endpoint(
    description="Show all data about repositories as JSON",
    configs=[
        ConfigGithub,
        ConfigAlgo,
    ],
)
def repos_json() -> None:
    for repo in yield_repos():
        json.dump(repo.raw_data, fp=sys.stdout, indent=4)
        print()


@register_endpoint(
    description="Show github homepage for github pages sites",
    configs=[
        ConfigGithub,
        ConfigAlgo,
    ],
)
def repos_show_pages() -> None:
    for repo in yield_repos():
        if repo.has_pages:
            print(f"{repo.name}: {repo.homepage}")


@register_endpoint(
    description="Show github homepage",
    configs=[
        ConfigGithub,
        ConfigAlgo,
    ],
)
def repos_show_homepage() -> None:
    for repo in yield_repos():
        print(f"{repo.name}: {repo.homepage}")


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
            print()
        else:
            print(f"{repo.name}")


@register_endpoint(
    description="Cleanup old failing or un-needed runs, deployments, and releases in all repositories",
    configs=[
        ConfigGithub,
        ConfigOutput,
        ConfigAlgo,
    ],
)
def cleanup() -> None:
    for repo in yield_repos():
        # 1. Cleanup workflow runs
        for workflow in repo.get_workflows():
            existing = 0
            for run in workflow.get_runs():
                if ConfigOutput.verbose:
                    print(f"inspecting [workflow run] {repo.name} {workflow.name} {run.status} {run.conclusion}")
                # github refuses to delete a run that is queued or still
                # running, so leave those alone and don't count them
                if run.status != "completed":
                    continue
                delete_it = False
                # if its a pages build delete it
                if workflow.name == "pages-build-deployment":
                    delete_it = True
                # if its not on the default branch, delete it
                if run.head_branch != repo.default_branch:
                    delete_it = True
                # if its not a paged build and it failed then delete it
                if workflow.name != "pages-build-deployment" and run.conclusion in (
                    "failure", "cancelled", "timed_out", "startup_failure", "action_required"
                ):
                    delete_it = True
                if existing >= 4:
                    delete_it = True
                if delete_it:
                    print(f"deleting [workflow run] {repo.name} {workflow.name} {run.head_branch} {run.conclusion} {run.url}")
                    if ConfigAlgo.dryrun:
                        continue
                    try:
                        run.delete()
                    except github.GithubException as e:
                        print(f"Failed to delete run: {e}")
                else:
                    existing += 1

        # 2. Cleanup deployments
        existing_deployments = 0
        for deployment in repo.get_deployments():
            state = None
            for status in deployment.get_statuses():
                state = status.state
                break

            delete_it = False
            if state in ("failure", "error") or existing_deployments >= 4:
                delete_it = True
            else:
                existing_deployments += 1

            if delete_it:
                print(f"deleting [deployment] {repo.name} {deployment.id}")
                if ConfigAlgo.dryrun:
                    continue
                try:
                    deployment.create_status("inactive")
                except github.GithubException as e:
                    print(f"Failed to deactivate deployment: {e}")
                try:
                    status, _, _ = deployment._requester.requestJson("DELETE", deployment.url)
                    if status != 204:
                        print(f"Failed to delete deployment: HTTP {status}")
                except github.GithubException as e:
                    print(f"Failed to delete deployment: {e}")

        # 3. Cleanup releases
        existing_releases = 0
        for release in repo.get_releases():
            if existing_releases >= 4:
                print(f"deleting [release] {repo.name} {release.title}")
                if ConfigAlgo.dryrun:
                    continue
                try:
                    release.delete_release()
                except github.GithubException as e:
                    print(f"Failed to delete release: {e}")
            else:
                existing_releases += 1


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
                if run.status in ("in_progress", "queued"):
                    print(f"{repo.name}: {workflow.name} {run.status}")


# repos per GraphQL query; measured fastest at around 10
GRAPHQL_BATCH_SIZE = 10
# GraphQL queries in flight at once, well below github's concurrency limits
GRAPHQL_WORKERS = 26

GRAPHQL_ROLLUP_FIELD = """
r{index}: repository(owner: {owner}, name: {name}) {{
  defaultBranchRef {{ target {{ ... on Commit {{ statusCheckRollup {{ state }} }} }} }}
}}
"""

GRAPHQL_SUITES_QUERY = """
query($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    defaultBranchRef {
      target {
        ... on Commit {
          checkSuites(first: 50) {
            nodes {
              status
              conclusion
              workflowRun { workflow { name } }
            }
          }
        }
      }
    }
  }
}
"""


def graphql_show_runs(bad_state: Callable[[str], bool], bad_conclusion: Callable[[str], bool]) -> None:
    """
    Print the workflows that are not green on the default branch head commit
    of every repo.

    Resolving statusCheckRollup is slow on github's side (~4.5s per 50 repos)
    and cursor pagination would run the pages one after another, so the repos
    are split into small batches, each batch is one query with an aliased
    `repository` field per repo, and the batches run in parallel. Repos whose
    rollup state is bad then get one more query each to name the workflows.
    Only the head commit of the default branch is looked at, so a failed run
    on another branch, or a scheduled run on an older commit, does not show.
    """
    # the default client sleeps a second between POSTs, and every GraphQL
    # query is a POST, which would serialize the parallel queries
    g = get_github(
        pool_size=GRAPHQL_WORKERS,
        seconds_between_requests=None,
        seconds_between_writes=None,
    )

    def graphql(query: str, variables: dict[str, str]) -> dict[str, Any]:
        _headers, data = g.requester.graphql_query(query, variables)
        result: dict[str, Any] = data["data"]
        return result

    def get_states(batch: list[str]) -> list[str | None]:
        fields = []
        for index, full_name in enumerate(batch):
            owner, name = full_name.split("/", 1)
            # json.dumps gives a correctly quoted GraphQL string literal
            fields.append(GRAPHQL_ROLLUP_FIELD.format(index=index, owner=json.dumps(owner), name=json.dumps(name)))
        data = graphql("query {" + "".join(fields) + "}", {})
        states: list[str | None] = []
        for index in range(len(batch)):
            ref = data[f"r{index}"]["defaultBranchRef"]
            rollup = ref and ref["target"].get("statusCheckRollup")
            states.append(rollup and rollup["state"])
        return states

    def get_bad_workflows(full_name: str) -> list[tuple[str, str]]:
        owner, name = full_name.split("/", 1)
        data = graphql(GRAPHQL_SUITES_QUERY, {"owner": owner, "name": name})
        workflows = []
        for suite in data["repository"]["defaultBranchRef"]["target"]["checkSuites"]["nodes"]:
            # github creates an empty, never-run suite for every installed
            # app; without a workflow run behind it, it tells us nothing
            if suite["workflowRun"] is None:
                continue
            # an unfinished suite has no conclusion yet; report its status
            conclusion = suite["conclusion"] or suite["status"]
            if bad_conclusion(conclusion):
                workflows.append((suite["workflowRun"]["workflow"]["name"], conclusion.lower()))
        return workflows

    full_names = [repo.full_name for repo in yield_repos()]
    batches = [full_names[i:i + GRAPHQL_BATCH_SIZE] for i in range(0, len(full_names), GRAPHQL_BATCH_SIZE)]
    with ThreadPoolExecutor(GRAPHQL_WORKERS) as executor:
        states = [state for result in executor.map(get_states, batches) for state in result]
        # repos without any checks have no state and are skipped, as the rest
        # api path skips workflows that never ran
        bad = [full_name for full_name, state in zip(full_names, states) if state is not None and bad_state(state)]
        for full_name, workflows in zip(bad, executor.map(get_bad_workflows, bad)):
            name = full_name.split("/", 1)[1]
            for workflow, conclusion in workflows:
                print(f"{name}: {workflow} {conclusion}")


@register_endpoint(
    description="Show all runs which are last and failing in all workflows and all repositories",
    configs=[
        ConfigGithub,
        ConfigAlgo,
        ConfigRuns,
    ],
)
def runs_show_failing() -> None:
    if ConfigRuns.api == "graphql":
        graphql_show_runs(
            lambda state: state in ("FAILURE", "ERROR"),
            lambda conclusion: conclusion == "FAILURE",
        )
        return
    for repo in yield_repos():
        for workflow in repo.get_workflows():
            last_run = next(iter(workflow.get_runs()), None)
            if last_run is not None and last_run.conclusion == "failure":
                print(f"{repo.name}: {workflow.name} {last_run.conclusion}")


@register_endpoint(
    description="Show all runs which are not success at last run",
    configs=[
        ConfigGithub,
        ConfigAlgo,
        ConfigRuns,
    ],
)
def runs_show_not_success() -> None:
    if ConfigRuns.api == "graphql":
        graphql_show_runs(
            lambda state: state != "SUCCESS",
            lambda conclusion: conclusion != "SUCCESS",
        )
        return
    for repo in yield_repos():
        for workflow in repo.get_workflows():
            last_run = next(iter(workflow.get_runs()), None)
            if last_run is not None and last_run.conclusion != "success":
                print(f"{repo.name}: {workflow.name} {last_run.conclusion}")


@register_endpoint(
    description="Pull all projects from github",
    configs=[
        ConfigGithub,
        ConfigAlgo,
    ],
)
def pull_all() -> None:
    base_dir = get_base_dir()
    for repo in yield_repos():
        project = repo.name
        folder = get_repo_folder(repo)
        if os.path.isdir(folder):
            if not os.path.isfile(os.path.join(folder, ".skip")):
                print(f"project [{project}] exists, pulling it...")
                subprocess.check_call(
                    [
                        "git",
                        "pull",
                    ],
                    cwd=folder,
                )
            else:
                print(f"project [{project}] exists, skipping it because of .skip file...")
        else:
            print(f"project [{project}] does not exists, cloning it from [{repo.ssh_url}] to [{folder}]...")
            os.makedirs(base_dir, exist_ok=True)
            subprocess.check_call(
                [
                    "git",
                    "clone",
                    repo.ssh_url,
                ],
                cwd=base_dir,
            )


@register_endpoint(
    description="Clone all projects from github",
    configs=[
        ConfigGithub,
        ConfigAlgo,
    ],
)
def clone_all() -> None:
    all_repo_folders = set()
    base_dir = get_base_dir()
    for repo in yield_repos():
        project = repo.name
        folder = get_repo_folder(repo)
        all_repo_folders.add(folder)
        if os.path.isfile(folder):
            continue
        if os.path.isdir(folder):
            continue
        if ConfigAlgo.dryrun:
            continue
        print(f"cloning [{project}] from [{repo.ssh_url}] to [{folder}]")
        os.makedirs(base_dir, exist_ok=True)
        subprocess.check_call(
            [
                "git",
                "clone",
                repo.ssh_url,
            ],
            cwd=base_dir,
            stdout=subprocess.DEVNULL,
        )
    if ConfigAlgo.show_extra:
        disk_repos = get_all_git_repos(base_dir)
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
            print(f"{repo.name}: {workflow.name}...", end="")
            sys.stdout.flush()
            ret = workflow.create_dispatch(ref=repo.default_branch)
            print(f"{ret}")


@register_endpoint(
    description="Show all configuration options and their current values",
    configs=[
        ConfigGithub,
        ConfigAlgo,
        ConfigOutput,
    ],
)
def config() -> None:
    for config_class in [ConfigGithub, ConfigAlgo, ConfigOutput]:
        print(f"{config_class.__name__}: {get_first_line(config_class, 'undocumented')}")
        for name, param in the_registry.yield_name_data_for_config(config_class):
            value = getattr(config_class, name)
            if param.required and value is param.default:
                value_str = "MANDATORY (not set)"
            else:
                value_str = param.t2s(value)
            print(f"    {name} [{param.get_type_name()}]: {value_str}")
            print(f"        {param.help_string}")
            if not param.required:
                print(f"        default: {param.t2s(param.default)}")
            more_help = param.more_help()
            if more_help is not None:
                print(f"        {more_help}")
        print()
    print(f"repos are cloned to and pulled from: {get_base_dir()}/<repo-name>")


@register_main(
    main_description=pygitpub.static.DESCRIPTION,
    app_name=pygitpub.static.APP_NAME,
    version=pygitpub.static.VERSION_STR,
)
def main():
    pylogconf.core.setup()
    config_arg_parse_and_launch()


if __name__ == "__main__":
    main()
