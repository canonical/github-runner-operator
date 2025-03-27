# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Test the thread_manager module"""

from queue import Queue
import secrets

import pytest
from src.github_runner_manager.thread_manager import ThreadManager

def test_thread_manager_run():
    """
    arrange: Add a thread that puts a message in to a queue.
    act: Start the thread manager.
    assert: Receive the message in the queue.
    """
    message = f"task: {secrets.token_hex(12)}"
    thread_manager = ThreadManager()
    msg_queue = Queue()
    thread_manager.add_thread(lambda: msg_queue.put(message))

    thread_manager.start()
    
    msg = msg_queue.get_nowait()
    assert msg == message

def test_thread_manager_crash():
    """
    arrange: Add a thread that raises a error.
    act: Start the thread manager.
    assert: The error is raised by thread manager.
    """
    class CustomException(Exception):
        """Custom exception for testing."""

    error_message = f"error: {secrets.token_hex(12)}"
    def raise_custom_exception():
        raise CustomException(error_message)

    thread_manager = ThreadManager()
    thread_manager.add_thread(target=raise_custom_exception)
    
    thread_manager.start()

    with pytest.raises(CustomException) as err:
        thread_manager.raise_on_error()
    
    assert str(err.value) == error_message
    