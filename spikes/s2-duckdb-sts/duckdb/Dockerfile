# DuckDB client for S-2: python + duckdb (pinned) with the iceberg/httpfs/avro extensions pre-installed
# at build time (extension builds are tied to the DuckDB version). No credentials in the image.
ARG PYTHON_IMAGE_TAG
FROM python:${PYTHON_IMAGE_TAG}
ARG DUCKDB_VERSION
RUN pip install --no-cache-dir "duckdb==${DUCKDB_VERSION}" \
 && useradd -m -u 1000 duck
USER duck
COPY --chown=duck install-ext.py /tmp/install-ext.py
RUN python /tmp/install-ext.py
WORKDIR /home/duck
