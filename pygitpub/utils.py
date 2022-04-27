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
