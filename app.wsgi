try:
    import ConfigParser as configparser
except ImportError:
    import configparser
import logging.config
import os

from kinto import main

here = os.path.dirname(__file__)

ini_path = os.environ.get('KINTO_INI')
if ini_path is None:
    ini_path = os.path.join(here, 'config', 'kinto.ini')

# If, for some reason you accidentally get the config file path wrong
# you'll get really cryptic errors from `logging.config.fileConfig(ini_path)`
# so to save yourself the pain of debugging, make sure the file definitely
# does exist and can be read.
# Actually opening it to read will check permissions *and* presence.
with open(ini_path) as f:
    assert f.read(), '{} empty'.format(ini_path)

# Set up logging
logging.config.fileConfig(ini_path)

# Parse config and create WSGI app
config = configparser.ConfigParser()
config.read(ini_path)

application = main(config.items('DEFAULT'), **dict(config.items('app:main')))
