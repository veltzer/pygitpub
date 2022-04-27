"""
All configurations for pygitpub
"""
import hashlib
from pytconf import Config, ParamCreator


class ConfigScan(Config):
    """
    Parameters that control the scanning phase
    """
    folder = ParamCreator.create_existing_folder(
        help_string="Which folder to work on?",
        default=".",
    )


class ConfigAlgo(Config):
    """
    Parameters at the core of the algorithm
    """
    digest = ParamCreator.create_choice(
        help_string="Which digest to use?",
        default="sha256",
        choice_list=list(hashlib.algorithms_available),
    )
    encoding = ParamCreator.create_str(
        help_string="Which encoding to use?",
        default='utf-8',
    )


class ConfigLMDB(Config):
    """
    Parameters that control working with LMDB (experts only)
    """
    map_size = ParamCreator.create_int(
        help_string="Which size of mmap to use?",
        default=1000000000000,
    )
    buffers = ParamCreator.create_bool(
        help_string="Should we use buffers? (lmdb default is False)",
        default=False,
    )
