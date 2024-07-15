#!/usr/bin/env python3
#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Script to spawn a reactive runner."""
import argparse
import logging
import os
import sys

from reactive.runner import reactive_runner
from reactive.runner_manager import MQ_URI_ENV_VAR


def setup_root_logging() -> None:
    """Set up logging for the reactive runner."""
    # setup root logger to log in a file which will be picked up by grafana agent and sent to Loki
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "queue_name", help="Name of the message queue to consume from. E.g. : large"
    )

    mq_uri = os.environ.get(MQ_URI_ENV_VAR)
    argument_opts: dict = {"default": mq_uri} if mq_uri else {"required": True}
    parser.add_argument(
        "--mq-uri",
        help="URI of the message queue database. This should include authentication information."
        f"The argument is required but can also be set via the {MQ_URI_ENV_VAR} "
        "environment variable."
        " Example URI : mongodb://user:pw@10.36.24.114/github-runner-webhook-router"
        "?replicaSet=mongodb&authSource=admin",
        **argument_opts,
    )
    arguments = parser.parse_args()

    setup_root_logging()
    reactive_runner(arguments.mq_uri, arguments.queue_name)
