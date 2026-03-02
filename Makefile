VENV := $(shell echo $${VIRTUAL_ENV-.venv})
INSTALL_STAMP := $(VENV)/.install.stamp
DOC_STAMP := $(VENV)/.doc.install.stamp
SPHINX_BUILDDIR = docs/_build
PSQL_INSTALLED := $(shell psql --version 2>/dev/null)
SOURCES := kinto-remote-settings cronjobs git-reader browser-tests bin
TY_SOURCES := kinto-remote-settings cronjobs git-reader bin

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
	rm -rf browser-tests/.pytest_cache
	find . -name '*.orig' -delete
	docker compose down --remove-orphans --volumes --rmi all

install: $(INSTALL_STAMP)  ## Install dependencies
$(INSTALL_STAMP): uv.lock
	uv sync --no-install-project --group kinto-remote-settings --group dev --group cronjobs --group git-reader
	touch $(INSTALL_STAMP)

format: $(INSTALL_STAMP)  ## Format code base
	$(VENV)/bin/ruff check --fix $(SOURCES)
	$(VENV)/bin/ruff format $(SOURCES)

lint: $(INSTALL_STAMP)  ## Analyze code base
	$(VENV)/bin/ruff check $(SOURCES)
	$(VENV)/bin/ruff format $(SOURCES)
	$(VENV)/bin/ty check $(TY_SOURCES)
	$(VENV)/bin/detect-secrets-hook `git ls-files | grep -v uv.lock` --baseline .secrets.baseline
	$(VENV)/bin/python bin/repo-python-versions.py

test: $(INSTALL_STAMP)  ## Run unit tests
	PYTHONPATH=. $(VENV)/bin/pytest \
    --cov=kinto-remote-settings \
    --cov=cronjobs \
    --cov=git-reader \
    --cov-report=term-missing \
    --cov-fail-under=99 \
    kinto-remote-settings cronjobs git-reader

browser-test:  ## Run browser tests using Docker
	docker compose --profile=browser-tests build browser-tests -q
	docker compose run --rm web migrate
	docker compose run --rm browser-tests

build:  ## Build containers
	docker build --file RemoteSettings.Dockerfile --target production --tag remotesettings/server .
	docker compose --profile browser-tests build

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

down:  ## Shutdown all containers and remove volumes
	docker compose down --volumes

install-docs: $(DOC_STAMP)  ## Install documentation build dependencies
$(DOC_STAMP): uv.lock
	uv sync --no-install-project --group docs
	touch $(DOC_STAMP)

docs: install-docs  ## Build documentation
	$(VENV)/bin/sphinx-build -a -W -n -b html -d $(SPHINX_BUILDDIR)/doctrees docs $(SPHINX_BUILDDIR)/html
	@echo
	@echo "Build finished. The HTML pages are in $(SPHINX_BUILDDIR)/html/index.html"
