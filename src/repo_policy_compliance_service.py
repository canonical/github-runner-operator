from flask import Flask
from repo_policy_compliance.blueprint import repo_policy_compliance

app = Flask(__name__)
app.register_blueprint(repo_policy_compliance)
