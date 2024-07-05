#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.
import argparse
import logging

from reactive.runner import reactive_runner
from reactive.runner_manager import REACTIVE_RUNNER_LOG_FILE


def spawn_runner(mq_uri: str, queue_name: str):
    # TODO: use charm state from disk to get reactive configuration
    reactive_runner(mq_uri=mq_uri, queue_name=queue_name)


def setup_root_logging():
    # setup root logger to log in a file called /var/log/reactive_runner.log
    logging.basicConfig(
        filename=REACTIVE_RUNNER_LOG_FILE,
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("mq_uri", help="URI of the message queue database. This should include authentication information. E.g. : mongodb://user:pw@10.36.24.114/github-runner-webhook-router?replicaSet=mongodb&authSource=admin ")
    parser.add_argument("queue_name", help="Name of the message queue to consume from. E.g. : large")
    arguments = parser.parse_args()

    setup_root_logging()
    reactive_runner(arguments.mq_uri, arguments.queue_name)
