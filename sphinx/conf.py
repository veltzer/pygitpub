extensions = ['sphinx.ext.autodoc',
              'sphinx.ext.coverage',
              'sphinx.ext.viewcode']


project = 'pygitpub'
project_copyright = '2020, Mark Veltzer'
author = 'Mark Veltzer'
import config.version
version = ".".join(str(x) for x in config.version.tup)
release = '0.0.1'

html_theme_options = {
        "show_powered_by": "false",
}
rst_epilog = f'''
.. |project| replace:: {project}
'''
