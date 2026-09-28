ARG PLAYWRIGHT_IMAGE_TAG
FROM mcr.microsoft.com/playwright/python:${PLAYWRIGHT_IMAGE_TAG}
ARG PLAYWRIGHT_VERSION
RUN apt-get update && apt-get install -y --no-install-recommends libnss3-tools \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir --break-system-packages "playwright==${PLAYWRIGHT_VERSION}"
COPY run.sh sso_test.py oq3_probe.py /opt/tester/
ENTRYPOINT ["/opt/tester/run.sh"]
