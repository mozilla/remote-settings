# TODO: This hardcoded version is a temporary fix to provide a version proprety
# as server metadata. This value will eventually be replaced by a version
# provided when we install `kinto_remote_settings` as a package.
__version__ = "27.0.1"


def includeme(config):
    config.include("kinto_remote_settings.changes")
    config.include("kinto_remote_settings.signer")
