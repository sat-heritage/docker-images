# -*- coding: utf-8

from setuptools import setup

setup(name="satex",
    version = "0.90",
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
    }
)
