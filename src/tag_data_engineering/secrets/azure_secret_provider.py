from azure.core.credentials import TokenCredential
from azure.keyvault.secrets import SecretClient

from tag_data_engineering.secrets.secret_provider import SecretProvider


class AzureKeyVaultSecretProvider(SecretProvider):
    """Retrieves secrets from Azure Key Vault using DefaultAzureCredential.

    This provider works in multiple environments:
    - Fabric (production): Uses workspace managed identity automatically
    - Local development: Uses Azure CLI credentials (requires 'az login')
    - CI/CD: Uses service principal or federated credentials

    Example:
        >>> provider = AzureKeyVaultSecretProvider("https://my-vault.vault.azure.net/", DefaultAzureCredential())
        >>> api_key = provider.get_secret("api-key")
    """

    def __init__(self, vault_url: str, credential: TokenCredential):
        self.vault_url = vault_url
        self._client = SecretClient(vault_url=vault_url, credential=credential)

    def get_secret(self, secret_name: str) -> str:
        """Retrieve a secret from Azure Key Vault.

        Args:
            secret_name: The name of the secret in Key Vault

        Returns:
            The secret value as a string

        Raises:
            azure.core.exceptions.ResourceNotFoundError: If secret doesn't exist
            azure.core.exceptions.HttpResponseError: If access is denied
        """
        secret = self._client.get_secret(secret_name)
        if secret.value is None:
            raise ValueError(f"Secret '{secret_name}' has no value")
        return secret.value
