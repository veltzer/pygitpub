""" misc.py """

import glob
import logging
import os
import os.path

from pygitpub import LOGGER_NAME


def get_logger():
    return logging.getLogger(LOGGER_NAME)


def get_number_of_files(folder: str) -> int:
    count = 0
    for _root, _directories, files in os.walk(folder):
        count += len(files)
    return count




def get_all_git_repos(base_dir: str) -> set[str]:
    """ we use */.git under base_dir with recursive=False (which is the default)
    because otherwise we would find submodules too
    """
    return {os.path.dirname(x) for x in glob.glob(os.path.join(base_dir, "*/.git"))}
