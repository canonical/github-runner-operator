#!/usr/bin/env python3
from unittest.mock import patch


@patch("shutil.chown")
def test_download(chown, runner):
    runner.download()
    config_file = runner.runner_path / "config.sh"
    run_file = runner.runner_path / "run.sh"
    assert config_file.exists()
    assert run_file.exists()
    chown.assert_called()


@patch("shutil.chown")
def test_setup_env(chown, runner):
    runner.proxies = {"http": "mockhttpproxy", "https": "mockhttpsproxy"}
    runner.setup_env()
    assert runner.env_file.exists()
    chown.assert_called()
    contents = runner.env_file.read_text()
    assert "http_proxy=mockhttpproxy" in contents
    assert "https_proxy=mockhttpsproxy" in contents
