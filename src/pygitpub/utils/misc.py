""" misc.py """

import glob
import os.path


def get_all_git_repos(base_dir: str) -> set[str]:
    """ we use */.git under base_dir with recursive=False (which is the default)
    because otherwise we would find submodules too
    """
    return {os.path.dirname(x) for x in glob.glob(os.path.join(base_dir, "*/.git"))}
