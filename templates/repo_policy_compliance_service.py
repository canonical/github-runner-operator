# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Flask application for repo policy compliance.

This module is loaded into juju unit and run with gunicorn.
"""

# This module is executed in a different environment.
from flask import Flask  # pylint: disable=import-error
from repo_policy_compliance.blueprint import repo_policy_compliance  # pylint: disable=import-error

app = Flask(__name__)
app.register_blueprint(repo_policy_compliance)
