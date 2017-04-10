SERVER_CONFIG_SAMPLE = config/example.ini
SERVER_CONFIG_LOCAL = config/development.ini
VIRTUALENV = virtualenv --python python3.5
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

virtualenv: $(PYTHON)
$(PYTHON):
	$(VIRTUALENV) $(VENV)

$(SERVER_CONFIG_LOCAL): $(SERVER_CONFIG_SAMPLE)
	cp $(SERVER_CONFIG_SAMPLE) $(SERVER_CONFIG_LOCAL)

migrate: $(SERVER_CONFIG_LOCAL)
	$(VENV)/bin/kinto migrate --ini $(SERVER_CONFIG_LOCAL)

serve: install $(SERVER_CONFIG_LOCAL) migrate
	$(VENV)/bin/kinto start --ini $(SERVER_CONFIG_LOCAL)

build-requirements:
	$(VIRTUALENV) $(TEMPDIR)
	$(TEMPDIR)/bin/pip install -U pip
	$(TEMPDIR)/bin/pip install -Ue .
	$(TEMPDIR)/bin/pip freeze | grep -v -- '^-e' > requirements.txt

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
