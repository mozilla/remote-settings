"""
This module provides a mock for signer tests. Normally a file like this would
be defined in a tests directory separate from this src directory, but to
provide this module, Kinto expects to find it in a package found in
`site-packages`.
"""


class Listener(object):
    def __init__(self):
        self.received = []

    def __call__(self, event):
        self.received.append(event)


listener = Listener()


def load_from_config(config, prefix):
    return listener
