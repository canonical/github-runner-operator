#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.
import logging
import secrets

from event_timer import EventTimer


def test_is_active_true():
    """
    arrange: create an EventTimer object and mock exec command to return zero exit code
    act: call is_active
    assert: return True
    """
    evt = EventTimer(secrets.token_hex(16))
    assert evt.is_active(secrets.token_hex(16))


def test_is_active_false(exec_command):
    """
    arrange: create an EventTimer object and mock exec command to return non-zero exit code
    act: call is_active
    assert: return False
    """
    exec_command.return_value = ("", 1)

    evt = EventTimer(secrets.token_hex(16))
    assert not evt.is_active(secrets.token_hex(16))


def test_is_active_false_list_timers(exec_command, caplog):
    """
    arrange: create an EventTimer object and mock exec command to return non-zero exit code
     and set log level to debug
    act: call is_active
    assert: list-timers is called
    """
    exec_command.return_value = ("", 1)
    caplog.set_level(logging.DEBUG)

    evt = EventTimer(secrets.token_hex(16))
    assert not evt.is_active(secrets.token_hex(16))
    assert exec_command.call_count == 2
    assert "list-timers" in exec_command.call_args_list[1][0][0]
