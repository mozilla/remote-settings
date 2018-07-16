# This name comes from the docker-compose yml file that defines a name
# for the "web" container's image.
FROM kinto:build

ENV PYTHONUNBUFFERED=1

USER root

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl wget

RUN pip install httpie kinto-http kinto-wizard

WORKDIR /app
ADD tests /app

ENTRYPOINT ["/bin/bash", "/app/run.sh"]
CMD ["start"]
