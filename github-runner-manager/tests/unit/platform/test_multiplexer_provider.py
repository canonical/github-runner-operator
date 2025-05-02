#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.
from github_runner_manager.platform.multiplexer_provider import MultiplexerPlatform


def test_multiplexer_build_without_github():
    """
    arrange: no GithubConfiguration.
    act: call build
    assert: no github in the multiplexer provider map
    """
    github_config = None

    multiplexer = MultiplexerPlatform.build(
        prefix="unit-0",
        github_configuration=github_config,
    )

    assert "github" not in multiplexer._providers
