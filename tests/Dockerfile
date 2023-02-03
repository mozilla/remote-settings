FROM python:3.11.1-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app:$PYTHONPATH"

COPY /bin/update_and_install_system_packages.sh /opt
RUN /opt/update_and_install_system_packages.sh wget

WORKDIR /app

COPY tests/requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY tests .

ENTRYPOINT ["/bin/bash", "/app/run.sh"]
