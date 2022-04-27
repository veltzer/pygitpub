"""
main entry point to the program
"""

import pylogconf.core
from pytconf import register_main, config_arg_parse_and_launch, register_endpoint

from pygitpub.utils import get_logger
from pygitpub.static import VERSION_STR


@register_endpoint(
    description="Show workflow runs",
    configs=[
    ],
)
def show_runs() -> None:
    logger = get_logger()


@register_main(
    main_description="pygitpub will help you work with github",
    app_name="pygitpub",
    version=VERSION_STR,
)
def main():
    pylogconf.core.setup()
    config_arg_parse_and_launch()


if __name__ == '__main__':
    main()
