"""Mock implementation of SecretProvider for testing."""

from tag_data_engineering.secrets.secret_provider import SecretProvider


class MockSecretProvider(SecretProvider):
    """In-memory secret provider for testing purposes.

    Stores secrets in a dictionary and retrieves them without any external calls.
    Useful for unit tests and integration tests where you want to control
    secret values without accessing real secret stores.

    Example:
        >>> provider = MockSecretProvider({
        ...     "api-key": "test-key-12345",
        ...     "github-token": "ghp_test123"
        ... })
        >>> api_key = provider.get_secret("api-key")
        >>> assert api_key == "test-key-12345"
    """

    def __init__(self, secrets: dict[str, str]):
        """Initialize the mock provider with a dictionary of secrets.

        Args:
            secrets: Dictionary mapping secret names to secret values
        """
        self._secrets = secrets

    def get_secret(self, secret_name: str) -> str:
        """Retrieve a secret from the in-memory dictionary.

        Args:
            secret_name: The name of the secret to retrieve

        Returns:
            The secret value as a string

        Raises:
            ValueError: If the secret name is not found in the dictionary
        """
        if secret_name not in self._secrets:
            raise ValueError(f"Mock secret '{secret_name}' not configured")
        return self._secrets[secret_name]
