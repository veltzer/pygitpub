"""Behavioural tests for pygitpub's pure helpers."""

import os
import tempfile
import unittest

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
    def test_get_number_of_files_recursive(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "a"), "w", encoding="utf-8"):
                pass
            sub = os.path.join(d, "sub")
            os.mkdir(sub)
            with open(os.path.join(sub, "b"), "w", encoding="utf-8"):
                pass
            self.assertEqual(misc.get_number_of_files(d), 2)

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

        class FakeRepo:  # pylint: disable=too-few-public-methods
            name = "myrepo"

        expected = os.path.join(os.path.expanduser("~/somebase"), "myrepo")
        self.assertEqual(main.get_repo_folder(FakeRepo()), expected)
