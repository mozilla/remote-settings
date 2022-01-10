import pkg_resources


__version__ = pkg_resources.get_distribution("kinto_remote_settings").version


def includeme(config):
    config.include("kinto_remote_settings.changes")
    config.include("kinto_remote_settings.signer")
