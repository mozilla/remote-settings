FROM python:3.11.3-slim

ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH" \ 
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app:$PYTHONPATH"

COPY /bin/update_and_install_system_packages.sh /opt
RUN /opt/update_and_install_system_packages.sh wget

COPY tests/requirements.txt /opt
RUN pip install --no-cache-dir -r /opt/requirements.txt

WORKDIR /app
COPY tests/ pyproject.toml ./
# ./tests/run.sh, not ./bin/run.sh
ENTRYPOINT ["/app/run.sh"]
