# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

from flask import Flask
from repo_policy_compliance.blueprint import repo_policy_compliance

app = Flask(__name__)
app.register_blueprint(repo_policy_compliance)
