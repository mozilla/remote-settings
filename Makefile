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

$(INSTALL_STAMP): requirements.txt requirements-dev.txt
	virtualenv $(VENV) --python=python3
	$(VENV)/bin/python -m pip install --upgrade pip
	$(VENV)/bin/pip install -r requirements.txt
	$(VENV)/bin/pip install -r requirements-dev.txt
	touch $(INSTALL_STAMP)

format: $(INSTALL_STAMP)
	$(VENV)/bin/isort . --virtual-env=$(VENV)
	$(VENV)/bin/black kinto_remote_settings tests

lint: $(INSTALL_STAMP)
	$(VENV)/bin/isort . --check-only --virtual-env=$(VENV)
	$(VENV)/bin/black --check kinto_remote_settings tests --diff
	$(VENV)/bin/flake8 kinto_remote_settings tests

test: $(INSTALL_STAMP) lint
	PYTHONPATH=. $(VENV)/bin/pytest kinto_remote_settings

integration-test: $(INSTALL_STAMP) lint need-kinto-running
	docker-compose run tests

need-kinto-running:
	@curl http://localhost:8888/v1/ 2>/dev/null 1>&2 || (echo "Run 'make run-kinto' before starting tests." && exit 1)

run-kinto: $(INSTALL_STAMP) restart

build:
	./bin/build-images.sh
	docker-compose build

build-db:
ifdef PSQL_INSTALLED
	@pg_isready 2>/dev/null 1>&2 || (echo Run PostgreSQL before starting tests. && exit 1)
	@echo Creating db...
	@psql -c "CREATE DATABASE testdb ENCODING 'UTF8' TEMPLATE template0;" -U postgres -h localhost
	@psql -c "ALTER DATABASE testdb SET TIMEZONE TO UTC;"
	@echo Done!
else
	@echo PostgreSQL not installed. Please install PostgreSQL to use this command.
endif

stop:
	docker-compose stop

down:
	docker-compose down

restart:
	docker-compose down
	docker-compose run web migrate
	docker-compose up -d web
