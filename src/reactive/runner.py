#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.
import argparse
import logging

from reactive.job import Job, MessageQueueConnectionInfo

logger = logging.getLogger(__name__)


def reactive_runner(mq_uri: str, queue_name: str) -> None:
    """Spawn a runner reactively.

    Args:
    """
    # The runner manager is not yet fully implemented in reactive mode. We are just logging
    # the received job for now.
    mq_conn_info = MessageQueueConnectionInfo(uri=mq_uri, queue_name=queue_name)
    job = Job.from_message_queue(mq_conn_info)
    job_details = job.get_details()
    logger.info(
        "Received job with labels %s and run_url %s", job_details.labels, job_details.run_url
    )
    job.picked_up()
