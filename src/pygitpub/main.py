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
from github.Repository import Repository
from pytconf import config_arg_parse_and_launch, register_endpoint, register_main
from pytconf.pydoc import get_first_line
from pytconf.registry import the_registry

import pygitpub.static
from pygitpub.configs import AFFILIATIONS, ConfigAlgo, ConfigCleanup, ConfigGithub, ConfigOutput, ConfigRuns
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


# REST calls in flight at once when walking the repos in parallel
REST_WORKERS = 16


def get_parallel_github() -> github.Github:
    """
    A client for walking the repos from several threads. The default client
    sleeps 0.25s before every request, which serializes the threads and alone
    made cleanup take 15 minutes; that pause is dropped. The 1s pause between
    writes stays, so parallel deletes do not trip github's secondary limits.
    """
    return get_github(per_page=100, pool_size=REST_WORKERS, seconds_between_requests=None)


def for_each_repo(func: Callable[[Repository], list[str]]) -> None:
    """ run func on every repo in parallel and print the lines it returns, in repo order """
    with ThreadPoolExecutor(REST_WORKERS) as executor:
        for lines in executor.map(func, yield_repos(get_parallel_github())):
            for line in lines:
                print(line)


def get_workflow_names(repo: Repository) -> dict[int, str]:
    """ a run's own name is not always its workflow's (pages runs are
    'pages build and deployment' of workflow 'pages-build-deployment') """
    return {workflow.id: workflow.name for workflow in repo.get_workflows()}


def yield_repos(g: github.Github | None = None):
    if g is None:
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
        # the repo listing already carries the topics, no need for get_topics()
        if set(keywords) != set(repo.topics):
            print(f"in {folder}...")
            print(f"keywords is [{keywords}]")
            print(f"repo.topics is [{repo.topics}]")
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
        ConfigCleanup,
    ],
)
def cleanup() -> None:
    for_each_repo(cleanup_repo)


def cleanup_repo(repo: Repository) -> list[str]:
    lines: list[str] = []
    # 1. Cleanup workflow runs, listed for the whole repo in one go rather
    # than workflow by workflow; `existing` still counts per workflow
    workflow_names = get_workflow_names(repo)
    existing: dict[int, int] = {}
    for run in repo.get_workflow_runs():
        workflow_name = workflow_names.get(run.workflow_id, run.name)
        if ConfigOutput.verbose:
            lines.append(f"inspecting [workflow run] {repo.name} {workflow_name} {run.status} {run.conclusion}")
        # github refuses to delete a run that is queued or still
        # running, so leave those alone and don't count them
        if run.status != "completed":
            continue
        delete_it = False
        # if its a pages build delete it
        if workflow_name == "pages-build-deployment":
            delete_it = True
        # if its not on the default branch, delete it
        if run.head_branch != repo.default_branch:
            delete_it = True
        # if its not a paged build and it failed then delete it
        if workflow_name != "pages-build-deployment" and run.conclusion in (
            "failure", "cancelled", "timed_out", "startup_failure", "action_required"
        ):
            delete_it = True
        # if it was not triggered by a commit (manual dispatch, schedule, ...)
        if ConfigCleanup.delete_non_push_runs and run.event != "push":
            delete_it = True
        if existing.get(run.workflow_id, 0) >= 4:
            delete_it = True
        if delete_it:
            lines.append(
                f"deleting [workflow run] {repo.name} {workflow_name} {run.head_branch} {run.event} {run.conclusion} {run.url}"
            )
            if ConfigAlgo.dryrun:
                continue
            try:
                run.delete()
            except github.GithubException as e:
                lines.append(f"Failed to delete run: {e}")
        else:
            existing[run.workflow_id] = existing.get(run.workflow_id, 0) + 1

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
            lines.append(f"deleting [deployment] {repo.name} {deployment.id}")
            if ConfigAlgo.dryrun:
                continue
            try:
                deployment.create_status("inactive")
            except github.GithubException as e:
                lines.append(f"Failed to deactivate deployment: {e}")
            try:
                status, _, _ = deployment.requester.requestJson("DELETE", deployment.url)
                if status != 204:
                    lines.append(f"Failed to delete deployment: HTTP {status}")
            except github.GithubException as e:
                lines.append(f"Failed to delete deployment: {e}")

    # 3. Cleanup releases
    existing_releases = 0
    for release in repo.get_releases():
        if existing_releases >= 4:
            lines.append(f"deleting [release] {repo.name} {release.title}")
            if ConfigAlgo.dryrun:
                continue
            try:
                release.delete_release()
            except github.GithubException as e:
                lines.append(f"Failed to delete release: {e}")
        else:
            existing_releases += 1
    return lines


@register_endpoint(
    description="Show all runs in all workflows in all repos",
    configs=[
        ConfigGithub,
        ConfigAlgo,
    ],
)
def runs_show() -> None:
    def show(repo: Repository) -> list[str]:
        runs = list(repo.get_workflow_runs())
        if not runs:
            return []
        workflow_names = get_workflow_names(repo)
        return [f"{repo.name}: {workflow_names.get(run.workflow_id, run.name)} {run.conclusion}" for run in runs]
    for_each_repo(show)


@register_endpoint(
    description="Show all running runs in all workflows in all repositories",
    configs=[
        ConfigGithub,
        ConfigAlgo,
    ],
)
def runs_show_running() -> None:
    def show(repo: Repository) -> list[str]:
        # github filters by status server side, so this is two small calls
        runs = [run for status in ("in_progress", "queued") for run in repo.get_workflow_runs(status=status)]
        if not runs:
            return []
        workflow_names = get_workflow_names(repo)
        return [f"{repo.name}: {workflow_names.get(run.workflow_id, run.name)} {run.status}" for run in runs]
    for_each_repo(show)


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
              workflowRun { databaseId workflow { name } }
            }
          }
        }
      }
    }
  }
}
"""


def graphql_bad_runs(
    bad_state: Callable[[str], bool],
    bad_conclusion: Callable[[str], bool],
) -> list[tuple[str, str, str, int]]:
    """
    Return (repo full name, workflow name, conclusion, run id) for every
    workflow that is not green on the default branch head commit of a repo.

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

    def get_bad_workflows(full_name: str) -> list[tuple[str, str, str, int]]:
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
                run = suite["workflowRun"]
                workflows.append((full_name, run["workflow"]["name"], conclusion.lower(), run["databaseId"]))
        return workflows

    full_names = [repo.full_name for repo in yield_repos()]
    batches = [full_names[i:i + GRAPHQL_BATCH_SIZE] for i in range(0, len(full_names), GRAPHQL_BATCH_SIZE)]
    with ThreadPoolExecutor(GRAPHQL_WORKERS) as executor:
        states = [state for result in executor.map(get_states, batches) for state in result]
        # repos without any checks have no state and are skipped, as the rest
        # api path skips workflows that never ran
        bad = [full_name for full_name, state in zip(full_names, states) if state is not None and bad_state(state)]
        return [run for runs in executor.map(get_bad_workflows, bad) for run in runs]


def graphql_show_runs(bad_state: Callable[[str], bool], bad_conclusion: Callable[[str], bool]) -> None:
    for full_name, workflow, conclusion, _run_id in graphql_bad_runs(bad_state, bad_conclusion):
        print(f"{full_name.split('/', 1)[1]}: {workflow} {conclusion}")


def is_failing_state(state: str) -> bool:
    return state in ("FAILURE", "ERROR")


def is_failing_conclusion(conclusion: str) -> bool:
    return conclusion == "FAILURE"


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
        graphql_show_runs(is_failing_state, is_failing_conclusion)
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
    description="Rerun the failed jobs of every failing workflow on the default branch of all repositories",
    configs=[
        ConfigGithub,
        ConfigAlgo,
    ],
)
def workflows_rerun_failing() -> None:
    # rerun rather than dispatch: a rerun works whatever the workflow's
    # triggers are, while a dispatch needs a workflow_dispatch trigger
    g = get_github()
    for full_name, workflow, _conclusion, run_id in graphql_bad_runs(is_failing_state, is_failing_conclusion):
        print(f"{full_name.split('/', 1)[1]}: rerunning failed jobs of {workflow}")
        if ConfigAlgo.dryrun:
            continue
        try:
            g.requester.requestJsonAndCheck("POST", f"/repos/{full_name}/actions/runs/{run_id}/rerun-failed-jobs")
        except github.GithubException as e:
            print(f"Failed to rerun: {e}")


@register_endpoint(
    description="Check that repos with a docs/index.html have github pages and that branch pages are served from docs",
    configs=[
        ConfigGithub,
        ConfigAlgo,
    ],
)
def pages_check() -> None:
    def exists(repo: Repository, path: str) -> bool:
        try:
            repo.get_contents(path)
        except github.GithubException as e:
            # 404 covers a missing path and an empty repo
            if e.status != 404:
                raise
            return False
        return True

    def check(repo: Repository) -> list[str]:
        if not repo.has_pages:
            # many repos keep notes (TODO.txt, *.md) in docs; only a docs
            # folder with an index.html is a web site that wants pages
            return [f"{repo.name}: has a docs/index.html but no github pages"] if exists(repo, "docs/index.html") else []
        _headers, pages = repo.requester.requestJsonAndCheck("GET", f"{repo.url}/pages")
        # pages built by a workflow deploy whatever the build produces, so the
        # docs folder only matters for pages served straight from a branch
        if pages["build_type"] != "legacy":
            return []
        source = pages["source"]
        if source["path"] != "/docs":
            return [f"{repo.name}: github pages served from [{source['branch']}:{source['path']}] and not from docs"]
        # an asset site (web-assets) serves docs without an index.html, so
        # only the folder itself has to be there
        if not exists(repo, "docs"):
            return [f"{repo.name}: github pages served from docs but there is no docs folder"]
        return []
    for_each_repo(check)


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
    description="Run all workflows again by rerunning their last run on the default branch",
    configs=[
        ConfigGithub,
        ConfigOutput,
        ConfigAlgo,
    ],
)
def workflows_run() -> None:
    # rerun rather than dispatch: a dispatch needs a workflow_dispatch
    # trigger, which build.yml (on: push) does not have
    def run(repo: Repository) -> list[str]:
        lines = []
        for workflow in repo.get_workflows():
            last_run = next(iter(workflow.get_runs(branch=repo.default_branch)), None)
            if last_run is None:
                continue
            # github refuses to rerun a run that has not finished
            if last_run.status != "completed":
                lines.append(f"{repo.name}: {workflow.name} is {last_run.status}, not rerunning")
                continue
            lines.append(f"{repo.name}: rerunning {workflow.name}")
            if ConfigAlgo.dryrun:
                continue
            try:
                last_run.rerun()
            except github.GithubException as e:
                lines.append(f"Failed to rerun: {e}")
        return lines
    for_each_repo(run)


@register_endpoint(
    description="Show all configuration options and their current values",
    configs=[
        ConfigGithub,
        ConfigAlgo,
        ConfigOutput,
        ConfigRuns,
        ConfigCleanup,
    ],
)
def config() -> None:
    for config_class in [ConfigGithub, ConfigAlgo, ConfigOutput, ConfigRuns, ConfigCleanup]:
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
