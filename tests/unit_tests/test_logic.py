"""Behavioural tests for pygitpub's pure helpers."""

import os
import tempfile
import unittest
from types import SimpleNamespace
from typing import ClassVar
from unittest import mock

import github

from pygitpub import main
from pygitpub.configs import ConfigAlgo
from pygitpub.utils import lua, misc


class LuaTests(unittest.TestCase):
    def test_config_path(self):
        self.assertEqual(lua.config_path("project"), os.path.join("config", "project.lua"))

    def test_lua_to_python_scalar(self):
        self.assertEqual(lua.lua_to_python(5), 5)
        self.assertEqual(lua.lua_to_python("hello"), "hello")

    def test_load_lua_file_dict_and_list(self):
        source = 'NAME = "pygitpub"\nKEYWORDS = {"a", "b", "c"}\n'
        with tempfile.NamedTemporaryFile("w", suffix=".lua", delete=False, encoding="utf-8") as fh:
            fh.write(source)
            name = fh.name
        try:
            values = lua.load_lua_file(name)
            self.assertEqual(values["NAME"], "pygitpub")
            self.assertEqual(values["KEYWORDS"], ["a", "b", "c"])
        finally:
            os.unlink(name)

    def test_load_lua_file_nested_table(self):
        source = 'DATA = {x = 1, y = 2}\n'
        with tempfile.NamedTemporaryFile("w", suffix=".lua", delete=False, encoding="utf-8") as fh:
            fh.write(source)
            name = fh.name
        try:
            values = lua.load_lua_file(name)
            self.assertEqual(values["DATA"], {"x": 1, "y": 2})
        finally:
            os.unlink(name)

    def test_load_lua_file_missing_raises(self):
        with self.assertRaises(FileNotFoundError):
            lua.load_lua_file(os.path.join(tempfile.gettempdir(), "no_such_pygitpub_file.lua"))


class MiscTests(unittest.TestCase):
    def test_get_all_git_repos_finds_top_level_only(self):
        with tempfile.TemporaryDirectory() as d:
            for repo in ("r1", "r2"):
                os.makedirs(os.path.join(d, repo, ".git"))
            # a submodule-style nested .git must NOT be reported
            os.makedirs(os.path.join(d, "r1", "sub", ".git"))
            found = misc.get_all_git_repos(d)
            self.assertEqual(found, {os.path.join(d, "r1"), os.path.join(d, "r2")})


class AffiliationTests(unittest.TestCase):
    def tearDown(self):
        ConfigAlgo.affiliation = "owner"
        ConfigAlgo.base_dir = "~/git"

    def test_get_affiliation_normalizes_whitespace(self):
        ConfigAlgo.affiliation = " owner , collaborator "
        self.assertEqual(main.get_affiliation(), "owner,collaborator")

    def test_get_affiliation_rejects_bad_value(self):
        ConfigAlgo.affiliation = "owner,bogus"
        with self.assertRaises(ValueError):
            main.get_affiliation()

    def test_get_affiliation_rejects_empty(self):
        ConfigAlgo.affiliation = " , "
        with self.assertRaises(ValueError):
            main.get_affiliation()

    def test_get_repo_folder_uses_expanded_base_dir(self):
        ConfigAlgo.base_dir = "~/somebase"

        class FakeRepo:
            name = "myrepo"

        expected = os.path.join(os.path.expanduser("~/somebase"), "myrepo")
        self.assertEqual(main.get_repo_folder(FakeRepo()), expected)


class GraphqlBadRunsTests(unittest.TestCase):
    """ graphql_bad_runs against a fake github: 12 repos, so two batches """

    STATES: ClassVar[dict[str, str | None]] = {"r3": "FAILURE", "r7": "PENDING", "r11": None}

    def fake_graphql_query(self, query, variables):
        if "checkSuites" in query:
            self.assertIn(variables["name"], ("r3", "r7"))
            nodes = [
                # the empty suite an installed app leaves on every commit
                {"status": "QUEUED", "conclusion": None, "workflowRun": None},
                {"status": "COMPLETED", "conclusion": "SUCCESS",
                 "workflowRun": {"databaseId": 1, "workflow": {"name": "lint"}}},
                {"status": "COMPLETED", "conclusion": "FAILURE",
                 "workflowRun": {"databaseId": 2, "workflow": {"name": "build"}}},
                {"status": "IN_PROGRESS", "conclusion": None,
                 "workflowRun": {"databaseId": 3, "workflow": {"name": "pages"}}},
            ]
            target = {"checkSuites": {"nodes": nodes}}
            return {}, {"data": {"repository": {"defaultBranchRef": {"target": target}}}}
        # a batch query: map each alias back to the repo named in its field
        data = {}
        for line in query.splitlines():
            if ": repository(" in line:
                alias = line.split(":", 1)[0].strip()
                name = line.split('name: "', 1)[1].split('"', 1)[0]
                state = self.STATES.get(name, "SUCCESS")
                rollup = None if state is None else {"state": state}
                data[alias] = {"defaultBranchRef": {"target": {"statusCheckRollup": rollup}}}
        return {}, {"data": data}

    def run_bad_runs(self, bad_state, bad_conclusion):
        repos = [SimpleNamespace(full_name=f"me/r{i}") for i in range(12)]
        fake_github = SimpleNamespace(requester=SimpleNamespace(graphql_query=self.fake_graphql_query))
        with mock.patch.object(main, "get_github", return_value=fake_github), \
                mock.patch.object(main, "yield_repos", return_value=repos):
            return main.graphql_bad_runs(bad_state, bad_conclusion)

    def test_not_success(self):
        runs = self.run_bad_runs(lambda state: state != "SUCCESS", lambda conclusion: conclusion != "SUCCESS")
        self.assertEqual(runs, [
            ("me/r3", "build", "failure", 2),
            ("me/r3", "pages", "in_progress", 3),
            ("me/r7", "build", "failure", 2),
            ("me/r7", "pages", "in_progress", 3),
        ])

    def test_failing(self):
        runs = self.run_bad_runs(main.is_failing_state, main.is_failing_conclusion)
        self.assertEqual(runs, [("me/r3", "build", "failure", 2)])


def not_found() -> github.GithubException:
    return github.GithubException(404, {"message": "Not Found"})


class FakePagesRepo:
    """ a repo with the given files; pages is the /pages answer or None """

    def __init__(self, files, pages=None):
        self.name = "r"
        self.url = "https://api.github.com/repos/me/r"
        self.files = files
        self.has_pages = pages is not None
        self.requester = SimpleNamespace(requestJsonAndCheck=lambda verb, url: ({}, pages))

    def get_contents(self, path):
        if path not in self.files:
            raise not_found()
        return SimpleNamespace(path=path)


def legacy_pages(path="/docs"):
    return {"build_type": "legacy", "source": {"branch": "master", "path": path}}


class PagesCheckTests(unittest.TestCase):
    def test_site_without_pages(self):
        repo = FakePagesRepo({"docs", "docs/index.html"})
        self.assertEqual(main.pages_check_repo(repo), ["r: has a docs/index.html but no github pages"])

    def test_notes_folder_without_pages_is_fine(self):
        self.assertEqual(main.pages_check_repo(FakePagesRepo({"docs", "docs/TODO.txt"})), [])

    def test_workflow_pages_are_not_checked(self):
        repo = FakePagesRepo(set(), {"build_type": "workflow", "source": {"branch": "master", "path": "/"}})
        self.assertEqual(main.pages_check_repo(repo), [])

    def test_branch_pages_not_from_docs(self):
        repo = FakePagesRepo({"docs"}, legacy_pages("/"))
        self.assertEqual(main.pages_check_repo(repo), ["r: github pages served from [master:/] and not from docs"])

    def test_branch_pages_from_missing_docs(self):
        repo = FakePagesRepo(set(), legacy_pages())
        self.assertEqual(main.pages_check_repo(repo), ["r: github pages served from docs but there is no docs folder"])

    def test_asset_site_without_index_is_fine(self):
        self.assertEqual(main.pages_check_repo(FakePagesRepo({"docs"}, legacy_pages())), [])

    def test_other_errors_are_raised(self):
        repo = FakePagesRepo(set())
        repo.get_contents = mock.Mock(side_effect=github.GithubException(500, {}))
        with self.assertRaises(github.GithubException):
            main.pages_check_repo(repo)


class WorkflowsRunTests(unittest.TestCase):
    def tearDown(self):
        ConfigAlgo.dryrun = False

    def make_repo(self):
        self.done = mock.Mock(status="completed")
        self.running = mock.Mock(status="in_progress")
        # SimpleNamespace, since Mock(name=...) names the mock instead of
        # setting a name attribute
        self.workflows = [
            SimpleNamespace(name="build", get_runs=mock.Mock(return_value=[self.done, mock.Mock()])),
            SimpleNamespace(name="pages", get_runs=mock.Mock(return_value=[self.running])),
            SimpleNamespace(name="never", get_runs=mock.Mock(return_value=[])),
        ]
        return SimpleNamespace(name="r", default_branch="main", get_workflows=lambda: self.workflows)

    def test_reruns_last_finished_run_on_default_branch(self):
        lines = main.workflows_run_repo(self.make_repo())
        self.assertEqual(lines, ["r: rerunning build", "r: pages is in_progress, not rerunning"])
        self.done.rerun.assert_called_once_with()
        self.running.rerun.assert_not_called()
        for workflow in self.workflows:
            workflow.get_runs.assert_called_once_with(branch="main")

    def test_dryrun_does_not_rerun(self):
        ConfigAlgo.dryrun = True
        lines = main.workflows_run_repo(self.make_repo())
        self.assertIn("r: rerunning build", lines)
        self.done.rerun.assert_not_called()

    def test_rerun_failure_is_reported(self):
        repo = self.make_repo()
        self.done.rerun.side_effect = github.GithubException(403, {"message": "nope"})
        self.assertTrue(main.workflows_run_repo(repo)[1].startswith("Failed to rerun:"))


class YieldReposTests(unittest.TestCase):
    def tearDown(self):
        ConfigAlgo.repos = []

    def fake_github(self, names):
        repos = [
            SimpleNamespace(name=name, fork=False, private=False, owner=SimpleNamespace(login="me"))
            for name in names
        ]
        user = SimpleNamespace(get_repos=lambda affiliation: repos)
        return SimpleNamespace(get_user=lambda: user)

    def test_all_repos_by_default(self):
        found = [repo.name for repo in main.yield_repos(self.fake_github(["a", "b"]))]
        self.assertEqual(found, ["a", "b"])

    def test_repos_selects_and_reports_unknown_names(self):
        ConfigAlgo.repos = ["b", "zz"]
        with mock.patch("sys.stderr") as stderr:
            found = [repo.name for repo in main.yield_repos(self.fake_github(["a", "b"]))]
        self.assertEqual(found, ["b"])
        written = "".join(call.args[0] for call in stderr.write.call_args_list)
        self.assertIn("no repo named [zz] found", written)
