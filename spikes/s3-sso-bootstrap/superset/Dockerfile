ARG SUPERSET_VERSION
FROM apache/superset:${SUPERSET_VERSION}
ARG AUTHLIB_VERSION
ARG PSYCOPG2_BINARY_VERSION
USER root
RUN uv pip install --no-cache --python /app/.venv/bin/python \
      "authlib==${AUTHLIB_VERSION}" "psycopg2-binary==${PSYCOPG2_BINARY_VERSION}"
COPY superset_config.py /app/pythonpath/superset_config.py
COPY start.sh /app/lakehouse/start.sh
USER superset
