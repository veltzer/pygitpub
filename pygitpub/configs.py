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


class ConfigOutput(Config):
    """
    Parameters to control output
    """
    verbose = ParamCreator.create_bool(
        help_string="be verbose?",
        default=False,
    )
