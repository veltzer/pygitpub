"""
All configurations for pygitpub
"""
from pytconf import Config, ParamCreator

# The values github accepts in the "affiliation" parameter of its
# "list repositories" api. They are sent over the wire verbatim.
AFFILIATIONS = [
    "owner",
    "collaborator",
    "organization_member",
]


class ConfigGithub(Config):
    """
    Paramters for your github account
    """
    username = ParamCreator.create_str(
        help_string="What is your github username?",
    )
    apikey = ParamCreator.create_str(
        help_string="What is the name of your apikey (see pyapikey)?",
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
    affiliation = ParamCreator.create_str(
        help_string="Comma separated list of how you are affiliated with the repos to work on"
                    f" (any of {','.join(AFFILIATIONS)})",
        default="owner",
    )
    show_extra = ParamCreator.create_bool(
        help_string="Show extra git repos lying around?",
        default=True,
    )
    base_dir = ParamCreator.create_str(
        help_string="Base directory under which repos are cloned",
        default="~/git",
    )


# The ways the runs_show_failing and runs_show_not_success endpoints can
# query github. The first is the default.
RUNS_APIS = [
    "graphql",
    "rest",
]


class ConfigRuns(Config):
    """
    Parameters to control how workflow runs are queried
    """
    api = ParamCreator.create_choice(
        choice_list=RUNS_APIS,
        help_string="graphql: check the default branch head commit of all repos in parallel batches (fast);"
                    " rest: walk every workflow's last run on any branch (slow, one call per workflow)",
        default="graphql",
    )


class ConfigOutput(Config):
    """
    Parameters to control output
    """
    verbose = ParamCreator.create_bool(
        help_string="be verbose?",
        default=False,
    )
