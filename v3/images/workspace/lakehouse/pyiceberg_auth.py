"""PyIceberg auth manager: a current lab_token() as the Bearer token on every catalog call.

Referenced from $PYICEBERG_HOME/.pyiceberg.yaml as
    auth: {type: custom, impl: lakehouse.pyiceberg_auth.LabAuthManager}
so `load_catalog("lakehouse")` works as the logged-in user for as long as the session lasts.
"""
from pyiceberg.catalog.rest.auth import AuthManager

from .token import lab_token


class LabAuthManager(AuthManager):
    def __init__(self, **_ignored):
        pass

    def auth_header(self):
        return f"Bearer {lab_token()}"
