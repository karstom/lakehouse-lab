# Smoke test image: Playwright (headless Chromium) + the Trino and PyIceberg clients.
# Pins: versions.env only (ADR-012). The test scripts are mounted, not copied.
ARG PLAYWRIGHT_IMAGE_TAG
ARG PLAYWRIGHT_IMAGE_DIGEST
FROM mcr.microsoft.com/playwright/python:${PLAYWRIGHT_IMAGE_TAG}@${PLAYWRIGHT_IMAGE_DIGEST}
ARG PLAYWRIGHT_VERSION
ARG TRINO_PYTHON_VERSION
ARG PYICEBERG_VERSION
ARG PYARROW_VERSION
RUN apt-get update \
    && apt-get install -y --no-install-recommends libnss3-tools \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir --break-system-packages \
      "playwright==${PLAYWRIGHT_VERSION}" \
      "trino==${TRINO_PYTHON_VERSION}" \
      "pyiceberg==${PYICEBERG_VERSION}" \
      "pyarrow==${PYARROW_VERSION}"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
