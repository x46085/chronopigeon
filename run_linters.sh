#!/bin/bash

# Run flake8 linter https://pypi.org/project/flake8/
echo -e "########   Running Flake8 Python Linting...   ########"
flake8 mh_cli.py server.py
echo -e "########   Flake8 Linting complete   ######## \n"

# Run Pylint linter https://pypi.org/project/pylint/
echo "########   Running Pylint Python Linting...   ########"
pylint mh_cli.py server.py
echo -e "########   Pylint Linting complete   ######## \n"

# Run Bandit security / pyc audit https://pypi.org/project/bandit/
echo -e "########   Running Bandit Python Linting...   ########"
bandit -r mh_cli.py server.py
echo -e "########   Bandit Linting complete   ######## \n"