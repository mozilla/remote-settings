SERVER_CONFIG = config/kinto.ini
VIRTUALENV = virtualenv
VENV := $(shell echo $${VIRTUAL_ENV-.venv})
PYTHON = $(VENV)/bin/python
DEV_STAMP = $(VENV)/.dev_env_installed.stamp
INSTALL_STAMP = $(VENV)/.install.stamp
TEMPDIR := $(shell mktemp -d)

.IGNORE: clean distclean maintainer-clean
.PHONY: all install virtualenv tests

OBJECTS = .venv .coverage

all: install
install: $(INSTALL_STAMP)
$(INSTALL_STAMP): $(PYTHON) setup.py
	$(VENV)/bin/pip install -U pip
	$(VENV)/bin/pip install -Ue .
	touch $(INSTALL_STAMP)

virtualenv: $(PYTHON)
$(PYTHON):
	virtualenv $(VENV)

$(SERVER_CONFIG):
	$(VENV)/bin/kinto --ini $(SERVER_CONFIG) init

serve: install-dev $(SERVER_CONFIG) migrate
	$(VENV)/bin/kinto --ini $(SERVER_CONFIG) start
