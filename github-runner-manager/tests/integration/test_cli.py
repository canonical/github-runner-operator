#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Integration test for github-runner-manager cli."""

import subprocess

from tests.integration.helper import (
    acquire_lock,
    get_app_log,
    get_lock_status,
    release_lock,
    wait_for_reconcile,
)


def test_lock_unchange(app: subprocess.Popen):
    """
    arrange: Run the github-runner-manager CLI application.
    act: None.
    assert: The lock should never be acquired in the logs of the reconcile service.
    """
    wait_for_reconcile()
    app.kill()
    log = get_app_log(app)
    assert "lock locked: False" in log
    assert "lock locked: True" not in log


def test_lock_acquire_release(app: subprocess.Popen):
    """
    arrange: Run the github-runner-manager CLI application.
    act: Acquire and release the lock.
    assert: The lock status should be correct when queried. The lock should be been acquired in
        the log at one point.
    """
    assert "unlock" in get_lock_status()
    acquire_lock()
    wait_for_reconcile()
    assert "locked" in get_lock_status()
    release_lock()
    wait_for_reconcile()
    assert "unlock" in get_lock_status()

    app.kill()
    log = get_app_log(app)
    assert "lock locked: False" in log
    assert "lock locked: True" in log
