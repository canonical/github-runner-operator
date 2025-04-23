#!/usr/bin/env python3
#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Script to spawn a reactive runner process."""
import getpass
import grp
import logging
import os
import sys

from github_runner_manager.configuration import UserInfo
from github_runner_manager.manager.runner_manager import RunnerManager
from github_runner_manager.openstack_cloud.openstack_runner_manager import OpenStackRunnerManager
from github_runner_manager.platform.multiplexer_provider import MultiplexerPlatform
from github_runner_manager.reactive.consumer import consume
from github_runner_manager.reactive.process_manager import RUNNER_CONFIG_ENV_VAR
from github_runner_manager.reactive.types_ import ReactiveProcessConfig


def setup_root_logging() -> None:
    """Set up logging for the reactive runner process."""
    # setup root logger to log in a file which will be picked up by grafana agent and sent to Loki
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def main() -> None:
    """Spawn a process that consumes a message from the queue to create a runner.

    Raises:
        ValueError: If the required environment variables are not set
    """
    runner_config_str = os.environ.get(RUNNER_CONFIG_ENV_VAR)

    if not runner_config_str:
        raise ValueError(
            f"Missing {RUNNER_CONFIG_ENV_VAR} environment variable. "
            "Please set it to the message queue URI."
        )

    runner_config = ReactiveProcessConfig.parse_raw(runner_config_str)

    setup_root_logging()
    queue_config = runner_config.queue

    user = UserInfo(getpass.getuser(), grp.getgrgid(os.getgid()))
    openstack_runner_manager = OpenStackRunnerManager(
        config=runner_config.cloud_runner_manager, user=user
    )
    github_provider = MultiplexerPlatform.build(
        prefix=runner_config.cloud_runner_manager.prefix,
        github_configuration=runner_config.github_configuration,
    )
    runner_manager = RunnerManager(
        manager_name=runner_config.manager_name,
        platform_provider=github_provider,
        cloud_runner_manager=openstack_runner_manager,
        labels=runner_config.labels,
    )
    consume(
        queue_config=queue_config,
        runner_manager=runner_manager,
        platform_provider=github_provider,
        supported_labels=runner_config.supported_labels,
    )


if __name__ == "__main__":
    main()
