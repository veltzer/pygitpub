extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.coverage",
    "sphinx.ext.viewcode",
    "sphinx.ext.githubpages",
]
import os
import sys

# Add the projects "src" directory to the Python path.
# This allows Sphinx to find and import your package.
sys.path.insert(0, os.path.abspath("../src"))
sys.path.insert(0, os.path.abspath(".."))

# Treat all warnings as errors.
# This can also be set by passing the -W flag to the sphinx-build command.
warning_is_error = True

# Enable "nit-picky mode". This will issue warnings for all missing
# cross-references (e.g., a link to a class that doesnt exist).
# nitpicky = True

project = "pygitpub"
author = "Mark Veltzer"
project_copyright = "2022, 2023, 2024, 2025, 2026 Mark Veltzer"
version = "0.0.59"
release = "0.0.59"

html_theme_options = {
        "show_powered_by": False,
}
# allow us to use |project| in our snippets and rst files
rst_epilog = f"""
.. |project| replace:: {project}
"""
# title without a version
html_title = "%s Documentation" % project
# This is the default
# html_title = "%s %s Documentation" % (project, version)
