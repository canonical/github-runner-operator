# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

from enum import Enum, auto
from typing import Sequence

from charm_state import GithubPath
from github_client import GithubClient
from github_type import GitHubRunnerStatus, SelfHostedRunner


class GithubRunnerState(str, Enum):
    BUSY = "busy"
    IDLE = "idle"
    OFFLINE = "offline"
    UNKNOWN = "unknown"

    @staticmethod
    def from_runner(runner: SelfHostedRunner) -> "GithubRunnerState":
        state = GithubRunnerState.OFFLINE
        if runner.status == GitHubRunnerStatus.ONLINE:
            if runner.busy:
                state = GithubRunnerState.BUSY
            if not runner.busy:
                state = GithubRunnerState.IDLE
        return state


class GithubRunnerManager:

    def __init__(self, prefix: str, token: str, path: GithubPath):
        self._prefix = prefix
        self._path = path
        self._github = GithubClient(token)

    def get_runners(
        self, states: Sequence[GithubRunnerState] | None = None
    ) -> tuple[SelfHostedRunner]:
        runner_list = self._github.get_runner_github_info(self._path)
        return tuple(
            runner
            for runner in runner_list
            if runner.name.startswith(self._prefix)
            and GithubRunnerManager._filter_runner_state(runner, states)
        )

    def delete_runners(self, states: Sequence[GithubRunnerState] | None = None) -> None:
        runner_list = self.get_runners(states)
        for runner in runner_list:
            self._github.delete_runner(self._path, runner.id)

    def get_registration_token(self) -> str:
        return self._github.get_runner_registration_token(self._path)

    def get_removal_token(self) -> str:
        return self._github.get_runner_remove_token(self._path)

    @staticmethod
    def _filter_runner_state(
        runner: SelfHostedRunner, states: Sequence[GithubRunnerState] | None
    ) -> bool:
        if states is None:
            return True
        return GithubRunnerState.from_runner(runner) in states
