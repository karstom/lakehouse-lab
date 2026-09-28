FROM quay.io/jupyterhub/jupyterhub:4.1.5

USER root

# Install system packages
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    git \
    vim \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages for JupyterHub
RUN pip install --no-cache-dir \
    jupyterhub \
    dockerspawner \
    oauthenticator \
    psycopg2-binary \
    pyspark==3.5.0 \
    notebook \
    jupyterlab

# Create JupyterHub configuration directory
RUN mkdir -p /srv/jupyterhub

# Copy configuration file
COPY jupyterhub_config.py /srv/jupyterhub/

WORKDIR /srv/jupyterhub

EXPOSE 8000

CMD ["jupyterhub", "-f", "/srv/jupyterhub/jupyterhub_config.py"]