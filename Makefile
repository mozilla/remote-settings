SERVER_CONFIG = config/kinto.ini
VIRTUALENV = virtualenv
VENV := $(shell echo $${VIRTUAL_ENV-.venv})
PYTHON = $(VENV)/bin/python
DEV_STAMP = $(VENV)/.dev_env_installed.stamp
INSTALL_STAMP = $(VENV)/.install.stamp
TEMPDIR := $(shell mktemp -d)

.PHONY: all install migrate serve virtualenv

OBJECTS = .venv .coverage

all: install
install: $(INSTALL_STAMP)
$(INSTALL_STAMP): $(PYTHON) setup.py
	$(VENV)/bin/pip install -U pip
	$(VENV)/bin/pip install -Ue . -c requirements.txt
	touch $(INSTALL_STAMP)

install-dev: $(INSTALL_STAMP) $(DEV_STAMP)
$(DEV_STAMP): $(PYTHON) dev-requirements.txt
	$(VENV)/bin/pip install -r dev-requirements.txt
	touch $(DEV_STAMP)

virtualenv: $(PYTHON)
$(PYTHON):
	$(VIRTUALENV) $(VENV)

migrate:
	$(VENV)/bin/kinto --ini $(SERVER_CONFIG) migrate

$(SERVER_CONFIG):
	$(VENV)/bin/kinto --ini $(SERVER_CONFIG) init

serve: install $(SERVER_CONFIG) migrate
	$(VENV)/bin/kinto --ini $(SERVER_CONFIG) start

build-requirements:
	$(VIRTUALENV) $(TEMPDIR)
	$(TEMPDIR)/bin/pip install -U pip
	$(TEMPDIR)/bin/pip install -Ue .
	$(TEMPDIR)/bin/pip freeze > requirements.txt

need-kinto-running:
	@curl http://localhost:8888/v1/ 2>/dev/null 1>&2 || (echo "Run 'make run-kinto' before starting tests." && exit 1)

tests: need-kinto-running
	autograph -c .autograph.yml & PID=$$!; \
	  sleep 1 && bash smoke-test.sh; \
      EXIT_CODE=$$?; kill $$PID; exit $$EXIT_CODE

clean:
	rm -fr build/ dist/ .tox .venv
	find . -name '*.pyc' -delete
	find . -name '__pycache__' -type d | xargs rm -fr
