FROM python:3.11.1-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app:$PYTHONPATH"

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY . .

ENTRYPOINT ["/bin/bash", "/app/run.sh"]
