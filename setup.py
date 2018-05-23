import os
import codecs
from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))


def read_file(filename):
    """Open a related file and return its content."""
    with codecs.open(os.path.join(here, filename), encoding='utf-8') as f:
        content = f.read()
    return content

README = read_file('README.rst')
CHANGELOG = read_file('CHANGELOG.rst')

REQUIREMENTS = [
    "pyramid>=1.9.1,<2.0",
    "kinto[postgresql,memcached,monitoring]>=9.1.1,<10.0",
    "kinto-attachment>=3.0,<3.1",
    "kinto-amo>=1.0.1,<1.1.0",
    "kinto-changes>=1.1.1,<1.2.0",
    "kinto-elasticsearch>=0.3.0,<0.4",
    "kinto-emailer>=1.0.2,<1.1",
    "kinto-signer>=3.2.3,<3.3",
    "kinto-fxa[scripts]>=2.5.0,<2.6",
    "kinto-ldap>=0.3.0,<0.4",
    "amo2kinto>=3.2,<3.3",
    "boto>=2.46,<2.47",
]
ENTRY_POINTS = {}
DEPENDENCY_LINKS = []

setup(name='kinto-dist',
      version='7.2.0',
      description='Kinto Distribution',
      long_description=README + "\n\n" + CHANGELOG,
      license='Apache License (2.0)',
      classifiers=[
          "Programming Language :: Python",
          "Programming Language :: Python :: 3",
          "Programming Language :: Python :: 3.5",
          "Programming Language :: Python :: 3.6",
          "Programming Language :: Python :: Implementation :: CPython",
          "Programming Language :: Python :: Implementation :: PyPy",
          "Topic :: Internet :: WWW/HTTP",
          "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
          "License :: OSI Approved :: Apache Software License"
      ],
      keywords="web services",
      author='Mozilla Services',
      author_email='services-dev@mozilla.com',
      url='https://github.com/mozilla-services/kinto-dist',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      install_requires=REQUIREMENTS)
