#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.
import secrets

from event_timer import EventTimer


def test_is_active_true():
    """
    arrange: create an EventTimer object and mock exec command to return zero exit code.
    act: call is_active.
    assert: return True.
    """
    event = EventTimer(unit_name=secrets.token_hex(16))
    assert event.is_active(event_name=secrets.token_hex(16))


def test_is_active_false(exec_command):
    """
    arrange: create an EventTimer object and mock exec command to return non-zero exit code.
    act: call is_active.
    assert: return False.
    """
    exec_command.return_value = ("", 1)

    event = EventTimer(unit_name=secrets.token_hex(16))
    assert not event.is_active(event_name=secrets.token_hex(16))
