#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Integration test for github-runner-manager cli."""

import subprocess
from multiprocessing import Process
from threading import Thread
from time import sleep

from tests.integration.helper import (
    acquire_lock,
    flush_runner,
    get_app_log,
    get_lock_status,
    poll_lock_status,
)


def test_lock_with_reconcile(app: subprocess.Popen):
    """
    arrange: Run the github-runner-manager CLI application.
    act: Check the state of the lock over time.
    assert: The reconcile service should run and acquire the lock at some point.
    """
    assert "locked" in poll_lock_status(15)


def test_lock_without_reconcile(no_reconcile_app: subprocess.Popen):
    """
    arrange: Run the github-runner-manager CLI application without reconcile service running.
    act: None.
    assert: The lock should never be acquired in the logs of the reconcile service.
    """
    assert "locked" not in poll_lock_status(15)


def test_lock_with_flush_runner(no_reconcile_app: subprocess.Popen):
    """
    arrange: Run the github-runner-manager CLI application without reconcile service running.
    act: Run flush runner.
    assert: The lock should be acquired by flush runner, and then released at the end.
    """
    app = no_reconcile_app
    assert "unlocked" == get_lock_status()
    flush = Thread(target=flush_runner, args=(False,))
    flush.start()
    assert "locked" in poll_lock_status(10)
    flush.join()
    assert "unlocked" == get_lock_status()
    app.kill()
    log = get_app_log(app)
    # The lock should be unlock at the start, which will produce this line.
    assert "Lock locked: False" in log


def test_flush_runner_with_locked_lock(no_reconcile_app: subprocess.Popen):
    """
    arrange: Acquire the lock.
    act: Run flush runner.
    assert: The flush runner should wait on the lock indefinitely.
    """
    app = no_reconcile_app
    assert "unlocked" == get_lock_status()
    acquire_lock()
    assert "locked" == get_lock_status()
    # Process is used here, since it is safe to terminate process.
    flush = Process(target=flush_runner, args=(False,))
    flush.start()
    # Not waiting for indefinitely, hence terminating the process after some time.
    sleep(15)
    flush.terminate()

    app.kill()
    log = get_app_log(app)
    # The lock should be locked at the start, which will produce this line.
    assert "Lock locked: True" in log
    # The flush_runner should never acquire the lock therefore, this line will never be logged.
    assert "Flush: Sleeping a while..." not in log
