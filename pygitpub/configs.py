"""
All configurations for pygitpub
"""
from pytconf import Config, ParamCreator


class ConfigGithub(Config):
    """
    Paramters for your github account
    """
    username = ParamCreator.create_str(
        help_string="What is your github username?",
    )
    token = ParamCreator.create_str(
        help_string="What is your github token?",
    )
    token_name = ParamCreator.create_str(
        help_string="What is the name of the token on github?",
    )


class ConfigAlgo(Config):
    """
    Parameters to control the algorithm
    """
    private = ParamCreator.create_bool(
        help_string="Include private repos?",
        default=True,
    )
    public = ParamCreator.create_bool(
        help_string="Include public repos?",
        default=True,
    )
    fork = ParamCreator.create_bool(
        help_string="Include forks?",
        default=True,
    )
    dryrun = ParamCreator.create_bool(
        help_string="Do a try run?",
        default=False,
    )
    owner_login = ParamCreator.create_str_or_none(
        help_string="Only include repos owned by this owner (None for dont mind)",
        default=None,
    )
    show_extra = ParamCreator.create_bool(
        help_string="Show extra git repos lygin around?",
        default=True,
    )


class ConfigOutput(Config):
    """
    Parameters to control output
    """
    verbose = ParamCreator.create_bool(
        help_string="be verbose?",
        default=False,
    )
