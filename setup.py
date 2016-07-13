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
    "kinto[postgresql,monitoring]>=3.2.2,<4.0",
    "kinto-attachment>=0.7.0,<0.8",
    "kinto-amo>=0.2.0,<0.3",
    "kinto-changes>=0.3,<0.4",
    "kinto-signer>=0.7,<0.8",
    "kinto-fxa>=2.0.0,<3.0",
    "kinto-ldap>=0.1,<0.2",
    "boto>=2.40,<2.41",
]
ENTRY_POINTS = {}
DEPENDENCY_LINKS = []

setup(name='kinto-dist',
      version='0.6.1',
      description='Kinto Distribution',
      long_description=README + "\n\n" + CHANGELOG,
      license='Apache License (2.0)',
      classifiers=[
          "Programming Language :: Python",
          "Programming Language :: Python :: 2",
          "Programming Language :: Python :: 2.7",
          "Programming Language :: Python :: 3",
          "Programming Language :: Python :: 3.4",
          "Programming Language :: Python :: 3.5",
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
