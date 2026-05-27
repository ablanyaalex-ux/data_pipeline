from azure.core.credentials import AccessToken
from notebookutils import mssparkutils  # type: ignore[import-not-found]


class FabricNotebookCredential:
    """A minimal credential wrapper for Microsoft Fabric."""

    def get_token(self, *scopes, **kwargs):
        # Fabric handles the token generation and caching internally
        token_string = mssparkutils.credentials.getToken("keyvault")
        # We return an AccessToken object with a dummy far-future expiry
        return AccessToken(token_string, 9999999999)
