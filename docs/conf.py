# Configuration file for Sphinx.

import os
import sys
sys.path.insert(0, os.path.abspath(".."))

project = "Ordex Python Library"
copyright = "2026, Ordex"
author = "Ordex"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "alabaster"
html_static_path = ["_static"]

nitpicky = True