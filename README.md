# github-runner-operator

## Description

TODO

## Usage

TODO

## Development

This charm uses black and flake8 for formatting. Both are run with the lint stage of tox.


## Testing

Testing is run via tox and pytest. To run the full test run:

    tox

Dependencies are installed in virtual environments. Integration testing requires a juju controller to execute. These tests will use the existing controller, creating an ephemeral
model for the tests which is removed after the testing. If you do not already have a controller setup, you can configure a local instance via LXD, see the [upstream
documentation][https://juju.is/docs/lxd-cloud] for details.

