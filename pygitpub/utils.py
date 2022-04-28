import logging
import os

from pygitpub import LOGGER_NAME


def get_logger():
    return logging.getLogger(LOGGER_NAME)


def get_number_of_files(folder: str) -> int:
    count = 0
    for _root, _directories, files in os.walk(folder):
        count += len(files)
    return count


def delete(workflow_run):
    # stolen from
    # https://github.com/PyGithub/PyGithub/blob/master/github/WorkflowRun.py
    # which is not yet in released
    # pylint: disable=protected-access
    status, _, _ = workflow_run._requester.requestJson("DELETE", workflow_run.url)
    return status == 204
