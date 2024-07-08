#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.
import argparse
import logging

from reactive.job import Job, JobError, MessageQueueConnectionInfo

logger = logging.getLogger(__name__)


def reactive_runner(mq_uri: str, queue_name: str) -> None:
    """Spawn a runner reactively.

    Args:
        mq_uri: The URI of the message queue.
        queue_name: The name of the queue.
    """
    # The runner manager is not yet fully implemented in reactive mode. We are just logging
    # the received job for now.
    mq_conn_info = MessageQueueConnectionInfo(uri=mq_uri, queue_name=queue_name)
    job = Job.from_message_queue(mq_conn_info)
    try:
        job_details = job.get_details()
    except JobError as e:
        logger.error("Error getting job details: %s", e)
        job.reject()
    else:
        logger.info(
            "Received job with labels %s and run_url %s", job_details.labels, job_details.run_url
        )
        job.picked_up()
