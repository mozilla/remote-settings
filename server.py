import os
import logging.config
import configparser

# from granian.utils.proxies import wrap_wsgi_with_proxy_headers
from kinto import main


def load_application():
    ini_path = os.environ.get("KINTO_INI")
    if not ini_path:
        raise RuntimeError("Environment variable KINTO_INI is not set")

    if not os.path.isfile(ini_path):
        raise RuntimeError(f"KINTO_INI file not found: {ini_path}")

    logging.config.fileConfig(ini_path, disable_existing_loggers=False)

    config = configparser.ConfigParser()
    config.read(ini_path)

    app = main(
        config.items("DEFAULT"),
        **dict(config.items("app:main")),
    )

    # Try whether removing the proxy fixes the functional tests.
    # trusted_hosts = os.getenv("GRANIAN_TRUSTED_HOSTS", "").split(",")
    # return wrap_wsgi_with_proxy_headers(app, trusted_hosts=trusted_hosts)
    return app


app = load_application()
