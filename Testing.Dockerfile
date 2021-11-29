# syntax=docker/dockerfile:1.3

# This name comes from the docker-compose yml file that defines a name
# for the "web" container's image.
FROM kinto:build

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app:$PYTHONPATH"

USER root

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl wget

RUN pip install httpie kinto-http kinto-wizard

COPY tests .
COPY kinto_remote_settings ./kinto_remote_settings

ENTRYPOINT ["/bin/bash", "/app/run.sh"]
CMD ["start"]
