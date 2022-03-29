VENV := $(shell echo $${VIRTUAL_ENV-.venv})
INSTALL_STAMP := $(VENV)/.install.stamp
DOC_STAMP := $(VENV)/.doc.install.stamp
SPHINX_BUILDDIR = docs/_build
PSQL_INSTALLED := $(shell psql --version 2>/dev/null)
VOLUMES_FOLDERS := autograph-certs mail

clean:
	find . -name '*.pyc' -delete
	find . -name '__pycache__' -type d | xargs rm -rf

distclean: clean
	rm -rf *.egg *.egg-info/ dist/ build/

maintainer-clean: distclean
	deactivate ; rm -rf .venv/
	rm -rf .pytest_cache
	rm -rf tests/.pytest_cache
	find . -name '*.orig' -delete
	docker-compose stop
	docker-compose rm -f
	RS_DB_DATA_VOL=$$(docker volume ls -q -f name="rs-db-data") ;\
	[ -z "$$RS_DB_DATA_VOL" ] && docker volume rm -f $$RS_DB_DATA_VOL ;\
	rm -rf $(VOLUMES_FOLDERS)

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
	mkdir -p -m 777 $(VOLUMES_FOLDERS)
	docker-compose run --rm web migrate
	docker-compose run --rm tests integration-test

browser-test:
	mkdir -p -m 777 $(VOLUMES_FOLDERS)
	docker-compose run --rm web migrate
	docker-compose run --rm tests browser-test

build:
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

start:
	make build
	docker-compose up

stop:
	docker-compose stop

down:
	docker-compose down

install-docs: $(DOC_STAMP)
$(DOC_STAMP): $(VENV)/bin/python docs/requirements.txt
	$(VENV)/bin/pip install -Ur docs/requirements.txt
	touch $(DOC_STAMP)

docs: install-docs
	$(VENV)/bin/sphinx-build -a -W -n -b html -d $(SPHINX_BUILDDIR)/doctrees docs $(SPHINX_BUILDDIR)/html
	@echo
	@echo "Build finished. The HTML pages are in $(SPHINX_BUILDDIR)/html/index.html"

