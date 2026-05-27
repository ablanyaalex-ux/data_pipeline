"""Base abstract class for secret providers."""

from abc import ABC
from abc import abstractmethod


class SecretProvider(ABC):
    """Abstract base class for retrieving secrets from various secret stores.

    Implementations should provide concrete methods to retrieve secrets from
    specific backends like Azure Key Vault, AWS Secrets Manager, environment
    variables, or mock stores for testing.
    """

    @abstractmethod
    def get_secret(self, secret_name: str) -> str:
        """Retrieve a secret value by its name.

        Args:
            secret_name: The name/key of the secret to retrieve

        Returns:
            The secret value as a string

        Raises:
            Exception: If the secret cannot be found or retrieved
        """
        ...
