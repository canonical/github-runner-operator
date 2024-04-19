#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Classes and functions defining the metrics storage."""
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Protocol


@dataclass
class MetricsStorage:
    """Storage for the metrics.

    Attributes:
        path: The path to the directory holding the metrics inside the charm.
        runner_name: The name of the associated runner.
    """

    path: Path
    runner_name: str


class StorageManager(Protocol):
    """A protocol defining the methods for managing the metrics storage.

    Attributes:
        create: Method to create a new storage. Returns the created storage.
          Raises an exception CreateMetricsStorageError if the storage already exists.
        list_all: Method to list all storages.
        get: Method to get a storage by name.
        delete: Method to delete a storage by name.
        move_to_quarantine: Method to move a storage to quarantine.
    """

    create: Callable[[str], MetricsStorage]
    list_all: Callable[[], Iterator[MetricsStorage]]
    get: Callable[[str], MetricsStorage]
    delete: Callable[[str], None]
    move_to_quarantine: Callable[[str], None]
