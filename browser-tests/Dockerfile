#
# Install Firefox Nightly and geckodriver in order to execute
# end-to-end synchronization from real JS and Rust clients
# like we do in Telescope.
#
FROM debian:bookworm-slim AS downloadfirefox

ARG TARGETARCH
ARG GECKODRIVER_VERSION=0.36.0

RUN apt-get update && \
    apt-get install --yes --no-install-recommends ca-certificates curl xz-utils

# Download to files (instead of piping into `tar`) so that interrupted transfers
# from the CDN can be retried.
RUN if [ "${TARGETARCH}" = "arm64" ]; then \
        FIREFOX_OS=linux64-aarch64; GECKODRIVER_OS=linux-aarch64; \
    else \
        FIREFOX_OS=linux64; GECKODRIVER_OS=linux64; \
    fi && \
    CURL="curl -sSfL --http1.1 --retry 5 --retry-all-errors --retry-delay 5" && \
    $CURL -o /tmp/firefox.tar.xz \
        "https://download.mozilla.org/?product=firefox-nightly-latest-ssl&os=${FIREFOX_OS}&lang=en-US" && \
    $CURL -o /tmp/geckodriver.tar.gz \
        "https://github.com/mozilla/geckodriver/releases/download/v${GECKODRIVER_VERSION}/geckodriver-v${GECKODRIVER_VERSION}-${GECKODRIVER_OS}.tar.gz" && \
    tar -xJf /tmp/firefox.tar.xz -C /opt && \
    tar -xzf /tmp/geckodriver.tar.gz -C /opt

FROM python:3.15.2-slim-bookworm

ENV UV_PROJECT_ENVIRONMENT=/opt/.venv \
    PATH="/opt/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app" \
    UV_CACHE_DIR=/tmp/uv-cache

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /opt
COPY pyproject.toml uv.lock ./

RUN apt-get update && apt-get install -y --no-install-recommends wget build-essential \
 && uv venv "$UV_PROJECT_ENVIRONMENT" \
 && uv sync --frozen --no-install-project --no-editable \
 && playwright install-deps firefox \
 && rm -rf /var/lib/apt/lists/* /tmp/uv-cache

COPY --from=downloadfirefox /opt/firefox /opt/firefox
COPY --from=downloadfirefox /opt/geckodriver /usr/local/bin/geckodriver
ENV FIREFOX_BINARY_PATH=/opt/firefox/firefox \
    GECKODRIVER_BINARY_PATH=/usr/local/bin/geckodriver

RUN addgroup --gid 10001 app \
 && adduser --disabled-password --gecos '' --gid 10001 --home /app --uid 10001 app
USER app
RUN playwright install firefox

WORKDIR /app
COPY . .
ENTRYPOINT ["./run.sh"]
