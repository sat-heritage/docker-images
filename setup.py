# -*- coding: utf-8

import os
import re
from setuptools import setup

META = {}
META_FILE = "satex.py"
with open(META_FILE) as f:
    __data = f.read()
for key in ["version"]:
    match = re.search(r"^__{0}__ = ['\"]([^'\"]*)['\"]".format(key), __data, re.M)
    if not match:
        raise RuntimeError("Unable to find __{meta}__ string.".format(meta=key))
    META[key] = match.group(1)

setup(name="satex",
    author = "Loïc Paulevé",
    author_email = "loic.pauleve@labri.fr",
    url = "https://github.com/sat-heritage/docker-images",
    description = "Helper script for managing SAT Heritage docker images",
    py_modules = ["satex"],
    install_requires = ["appdirs"],
    entry_points = {
        "console_scripts": [
            "satex= satex:main"
        ]
    },
    **META
)
