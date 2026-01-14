#  Copyright 2026 Canonical Ltd.
#  See LICENSE file for licensing details.

from pathlib import Path

import manager_service


def _convert_root_path(root_dir: Path):
    def map_path(path_input: str | Path):
        # Map absolute paths into an isolated temp root; pass through Path objects.
        if isinstance(path_input, Path):
            path_str = str(path_input)
        else:
            path_str = path_input
        if path_str.startswith("/"):
            return root_dir / path_str.lstrip("/")
        return root_dir / path_str

    return map_path


def test_get_http_port_persists_and_reuses(tmp_path, monkeypatch):
    """
    Arrange: isolate filesystem via Path monkeypatch and stub ports as available.
    Act: request a port twice for the same unit, flipping availability between calls.
    Assert: first call writes and returns a port; second call reuses persisted value.
    """
    # Scenario 1: port is available, should be allocated and persisted.
    monkeypatch.setattr(manager_service, "Path", _convert_root_path(tmp_path))
    monkeypatch.setattr(manager_service, "_port_available", lambda host, port: True)
    unit_name = "github-runner-operator/0"

    first_port = manager_service.get_http_port_for_unit(unit_name)

    unit_dir = tmp_path / "var/lib/github-runner-manager" / unit_name.replace("/", "-")
    port_file = unit_dir / "http_port"
    assert port_file.exists(), "Expected persisted port file"
    assert int(port_file.read_text(encoding="utf-8").strip()) == first_port

    # Scenario 2: port is not available, but persisted value should be reused.
    monkeypatch.setattr(manager_service, "_port_available", lambda host, port: False)

    second_port = manager_service.get_http_port_for_unit(unit_name)

    assert second_port == first_port, "Expected persisted port to be reused"


def test_get_http_port_collision_scan(tmp_path, monkeypatch):
    """
    Arrange: map Path to temp root and stub availability so base and next two are busy.
    Act: request a port for a unit whose base is 55555.
    Assert: selected port is base+3 and persisted to the per-unit file.
    """
    monkeypatch.setattr(manager_service, "Path", _convert_root_path(tmp_path))

    def stub_port_available(host, port):
        """Simulate port availability.

        Base port 55555 and the next two ports are busy; ports from base+3 onward
        are available.
        """
        base_port = manager_service._BASE_PORT
        return port >= base_port + 3

    monkeypatch.setattr(manager_service, "_port_available", stub_port_available)
    unit_name = "github-runner-operator/0"

    selected_port = manager_service.get_http_port_for_unit(unit_name)

    assert selected_port == manager_service._BASE_PORT + 3
    unit_dir = tmp_path / "var/lib/github-runner-manager" / unit_name.replace("/", "-")
    port_file = unit_dir / "http_port"
    assert int(port_file.read_text(encoding="utf-8").strip()) == selected_port
