# Lakehouse Lab V3 bootstrap image: python stdlib + the scripts in bootstrap/.
# Build context: v3/bootstrap (so .env/.secrets.env/state never enter a build context). Pins: versions.env only (ADR-012).
ARG PYTHON_IMAGE_TAG
ARG PYTHON_IMAGE_DIGEST
FROM python:${PYTHON_IMAGE_TAG}@${PYTHON_IMAGE_DIGEST}
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/opt/lab
COPY . /opt/lab/bootstrap/
RUN chmod 0755 /opt/lab/bootstrap/trust-init.sh
WORKDIR /opt/lab
CMD ["python3", "-m", "bootstrap"]
