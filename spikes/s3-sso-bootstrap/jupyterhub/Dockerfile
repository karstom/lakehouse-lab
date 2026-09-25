ARG JUPYTERHUB_VERSION
FROM quay.io/jupyterhub/jupyterhub:${JUPYTERHUB_VERSION}
ARG OAUTHENTICATOR_VERSION
RUN pip install --no-cache-dir "oauthenticator==${OAUTHENTICATOR_VERSION}"
COPY jupyterhub_config.py /srv/jupyterhub/jupyterhub_config.py
