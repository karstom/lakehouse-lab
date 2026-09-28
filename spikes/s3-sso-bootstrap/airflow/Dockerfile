ARG AIRFLOW_VERSION
ARG AIRFLOW_PYTHON
FROM apache/airflow:${AIRFLOW_VERSION}-python${AIRFLOW_PYTHON}
ARG AIRFLOW_VERSION
ARG AIRFLOW_PROVIDERS_KEYCLOAK_VERSION
RUN pip install --no-cache-dir "apache-airflow==${AIRFLOW_VERSION}" \
      "apache-airflow-providers-keycloak==${AIRFLOW_PROVIDERS_KEYCLOAK_VERSION}"
COPY init.sh ensure_keycloak_authz.py /opt/lakehouse/
