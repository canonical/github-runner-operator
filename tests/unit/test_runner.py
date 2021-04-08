#!/usr/bin/env python3


def test_download(runner):
    runner.download()
    config_file = runner.runner_path / "config.sh"
    run_file = runner.runner_path / "run.sh"
    assert config_file.exists()
    assert run_file.exists()
