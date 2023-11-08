VENV := $(shell echo $${VIRTUAL_ENV-.venv})
INSTALL_STAMP := $(VENV)/.install.stamp
DOC_STAMP := $(VENV)/.doc.install.stamp
SPHINX_BUILDDIR = docs/_build
PSQL_INSTALLED := $(shell psql --version 2>/dev/null)


help:
	@echo "Please use 'make <target>' where <target> is one of the following commands.\n"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' Makefile | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'
	@echo "\nCheck the Makefile to know exactly what each target is doing."

clean: ## Delete Python cache files
	find . -name '*.pyc' -delete
	find . -name '__pycache__' -type d | xargs rm -rf
	rm -rf .coverage

distclean: clean ## Delete packaging and cache files
	rm -rf *.egg *.egg-info/ dist/ build/

maintainer-clean: distclean ## Delete all non versioned files
	deactivate ; rm -rf .venv/
	rm -rf .pytest_cache
	rm -rf tests/.pytest_cache
	find . -name '*.orig' -delete
	docker compose down --remove-orphans --volumes --rmi all

$(VENV)/bin/python:  ## Create virtualenv
	python3 -m venv $(VENV)

install: $(VENV)/bin/python $(INSTALL_STAMP)  ## Install dependencies
$(INSTALL_STAMP): poetry.lock
	@if [ -z $(shell command -v poetry 2> /dev/null) ]; then echo "Poetry could not be found. See https://python-poetry.org/docs/"; exit 2; fi
	POETRY_VIRTUALENVS_IN_PROJECT=1 poetry install --no-root
	touch $(INSTALL_STAMP)

format: $(INSTALL_STAMP)  ## Format code base
	$(VENV)/bin/isort . --virtual-env=$(VENV)
	$(VENV)/bin/black kinto-remote-settings tests

lint: $(INSTALL_STAMP)  ## Analyze code base
	$(VENV)/bin/isort . --check-only --virtual-env=$(VENV)
	$(VENV)/bin/black --check kinto-remote-settings tests --diff
	$(VENV)/bin/flake8 kinto-remote-settings tests
	$(VENV)/bin/detect-secrets-hook `git ls-files | grep -v poetry.lock` --baseline .secrets.baseline

test: $(INSTALL_STAMP)  ## Run unit tests
	PYTHONPATH=. $(VENV)/bin/coverage run -m pytest kinto-remote-settings
	$(VENV)/bin/coverage report -m --fail-under 99

integration-test:  ## Run integration tests using Docker
	docker compose build tests
	docker compose run --rm web migrate
	docker compose run --rm tests integration-test

browser-test:  ## Run browser tests using Docker
	docker compose build tests
	docker compose run --rm web migrate
	docker compose run --rm tests browser-test

build:  ## Build containers
	docker build --file RemoteSettings.Dockerfile --target production --tag remotesettings/server .
	docker compose --profile integration-test build

build-db:  ## Initialize database 'postgresql://postgres@localhost/testdb'
ifdef PSQL_INSTALLED
	@pg_isready 2>/dev/null 1>&2 || (echo Run PostgreSQL before starting tests. && exit 1)
	@echo Creating db...
	@psql -tc "SELECT 1 FROM pg_database WHERE datname = 'testdb'" -U postgres -h localhost | grep -q 1 || psql -c "CREATE DATABASE testdb ENCODING 'UTF8' TEMPLATE template0;" -U postgres -h localhost
	@psql -c "ALTER DATABASE testdb SET TIMEZONE TO UTC;"
	@echo Done!
else
	@echo PostgreSQL not installed. Please install PostgreSQL to use this command.
endif

start:  ## Run the services using Docker
	docker compose build
	docker compose run --rm web migrate
	docker compose up

stop:  ## Stop the services
	docker compose stop

down:  ## Shutwdown all containers
	docker compose down

install-docs: $(VENV)/bin/python $(DOC_STAMP)  ## Install documentation build dependencies
$(DOC_STAMP): poetry.lock
	POETRY_VIRTUALENVS_IN_PROJECT=1 poetry install --no-root --only docs
	touch $(DOC_STAMP)

docs: install-docs  ## Build documentation
	$(VENV)/bin/sphinx-build -a -W -n -b html -d $(SPHINX_BUILDDIR)/doctrees docs $(SPHINX_BUILDDIR)/html
	@echo
	@echo "Build finished. The HTML pages are in $(SPHINX_BUILDDIR)/html/index.html"

