import logging
import os
import configparser
import github

from pygitpub import LOGGER_NAME


def get_logger():
    return logging.getLogger(LOGGER_NAME)


def get_number_of_files(folder: str) -> int:
    count = 0
    for _root, _directories, files in os.walk(folder):
        count += len(files)
    return count


def github_login():
    inifile = os.path.expanduser("~/.details.ini")
    config = configparser.ConfigParser()
    config.read(inifile)
    # all of our github secret info
    # opt_username = config.get("github", "username")
    # opt_password = config.get("github", "password")
    opt_personal_token = config.get("github", "personal_token")
    g = github.Github(login_or_token=opt_personal_token)
    return g
