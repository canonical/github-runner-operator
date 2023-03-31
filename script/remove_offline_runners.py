# Copyright 2022 Canonical
# See LICENSE file for licensing details.

import sys
import logging

import requests

ORG = "<your org>"
TOKEN = "<your token>"


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_runners():
    try:
        response = requests.get(
            f"https://api.github.com/orgs/{ORG}/actions/runners?per_page=100",
            # "https://api.github.com/repos/canonical/github-runner-operator/actions/runners",
            headers={
                "X-GitHub-Api-Version": "2022-11-28",
                "Authorization": "Bearer " + TOKEN,
                "Accept": "application/vnd.github+json",
            },
        )

        response.raise_for_status()
        runners = response.json()
        logger.info("Runners found: %s", runners)
        return runners
    except requests.HTTPError as http_err:
        sys.exit(f"HTTP error occurred: {http_err}")
    except Exception as err:
        sys.exit(f"Other error occurred: {err}")


def filter_offline_runners(runners):
    offline_runners = []

    runner_list = runners["runners"]
    for runner in runner_list:
        if runner["status"] == "offline":
            offline_runners.append(runner)

    return offline_runners


def delete_runner(runner):
    logger.info("Deleting runner with id %s", runner["id"])

    try:
        response = requests.delete(
            f"https://api.github.com/orgs/{ORG}/actions/runners/{runner['id']}",
            # f"https://api.github.com/repos/canonical/github-runner-operator/actions/runners/{runner['id']}",
            headers={
                "X-GitHub-Api-Version": "2022-11-28",
                "Authorization": "Bearer " + TOKEN,
                "Accept": "application/vnd.github+json",
            },
        )

        response.raise_for_status()
    except requests.HTTPError as http_err:
        sys.exit(f"HTTP error occurred: {http_err}")
    except Exception as err:
        sys.exit(f"Other error occurred: {err}")


if __name__ == "__main__":
    while True:
        runners = get_runners()
        offline_runners = filter_offline_runners(runners)
        if len(offline_runners)<=0:
            break

        for runner in offline_runners:
            delete_runner(runner)
