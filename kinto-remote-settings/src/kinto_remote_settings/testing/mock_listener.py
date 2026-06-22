"""
This module provides a mock for signer tests. Normally a file like this would
be defined in a tests directory separate from this src directory, but to
provide this module, Kinto expects to find it in a package found in
`site-packages`.
"""

from typing import Any


class Listener(object):
    def __init__(self) -> None:
        self.received: list[Any] = []

    def __call__(self, event: Any) -> None:
        self.received.append(event)


listener = Listener()


def load_from_config(config: Any, prefix: str) -> Listener:
    return listener
