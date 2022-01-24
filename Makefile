VENV := $(shell echo $${VIRTUAL_ENV-.venv})
INSTALL_STAMP := $(VENV)/.install.stamp
PSQL_INSTALLED := $(shell psql --version 2>/dev/null)

clean:
	find . -name '*.pyc' -delete
	find . -name '__pycache__' -type d | xargs rm -rf

distclean: clean
	rm -rf *.egg *.egg-info/ dist/ build/

maintainer-clean: distclean
	rm -rf .venv/

$(VENV)/bin/python:
	virtualenv $(VENV) --python=python3

$(INSTALL_STAMP): $(VENV)/bin/python requirements.txt requirements-dev.txt
	$(VENV)/bin/python -m pip install --upgrade pip
	$(VENV)/bin/pip install -r requirements.txt
	$(VENV)/bin/pip install -e kinto-remote-settings
	$(VENV)/bin/pip install -r requirements-dev.txt
	touch $(INSTALL_STAMP)

format: $(INSTALL_STAMP)
	$(VENV)/bin/isort . --virtual-env=$(VENV)
	$(VENV)/bin/black kinto-remote-settings tests

lint: $(INSTALL_STAMP)
	$(VENV)/bin/isort . --check-only --virtual-env=$(VENV)
	$(VENV)/bin/black --check kinto-remote-settings tests --diff
	$(VENV)/bin/flake8 kinto-remote-settings tests

test: $(INSTALL_STAMP)
	PYTHONPATH=. $(VENV)/bin/pytest kinto-remote-settings

integration-test:
	mkdir -p --mode=777 autograph-certs mail
	docker-compose run web migrate
	docker-compose run tests

build:
	docker build . -t remotesettings:build
	docker build . --file Dockerfile.Testing -t remotesettings:tests
	docker-compose build

build-db:
ifdef PSQL_INSTALLED
	@pg_isready 2>/dev/null 1>&2 || (echo Run PostgreSQL before starting tests. && exit 1)
	@echo Creating db...
	@psql -tc "SELECT 1 FROM pg_database WHERE datname = 'testdb'" -U postgres -h localhost | grep -q 1 || psql -c "CREATE DATABASE testdb ENCODING 'UTF8' TEMPLATE template0;" -U postgres -h localhost
	@psql -c "ALTER DATABASE testdb SET TIMEZONE TO UTC;"
	@echo Done!
else
	@echo PostgreSQL not installed. Please install PostgreSQL to use this command.
endif

stop:
	docker-compose stop

down:
	docker-compose down
