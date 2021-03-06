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
        default=False,
    )


class ConfigOutput(Config):
    """
    Parameters to control output
    """
    verbose = ParamCreator.create_bool(
        help_string="be verbose?",
        default=False,
    )
