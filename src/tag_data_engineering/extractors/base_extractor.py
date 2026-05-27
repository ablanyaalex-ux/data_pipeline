from abc import ABC
from abc import abstractmethod
from typing import Iterator

from tag_data_engineering.extractors.models import ExtractionBatch
from tag_data_engineering.models import ExtractionMetadata
from tag_data_engineering.secrets.secret_provider import SecretProvider


class BaseExtractor(ABC):
    """Abstract base class for all extractors.

    Extractors are responsible for fetching data from source systems
    and yielding it as batches. They do NOT handle file writing -
    that's the responsibility of the LandingRunner.

    Extractors should be reusable - create once and call extract()
    with different metadata configurations.

    Example:
        extractor = MyExtractor()
        for batch in extractor.extract(metadata):
            # LandingRunner writes batch to file
    """

    def __init__(self, secret_provider: SecretProvider):
        """Initialize the extractor with a secret provider.

        Args:
            secret_provider: Provider for retrieving secrets from secure storage.
        """
        self.secret_provider = secret_provider

    @property
    @abstractmethod
    def extractor_type(self) -> str:
        """Return the type of this extractor."""
        ...

    @abstractmethod
    def extract(
        self,
        metadata: ExtractionMetadata,
        cursor: dict[str, str | None] | None = None,
    ) -> Iterator[ExtractionBatch]:
        """Extract data based on metadata configuration.

        Yields batches of data as they are fetched from the source.
        Each batch contains field metadata and rows.

        Args:
            metadata: Extraction metadata with source, entity, and extractor config

        Yields:
            ExtractionBatch objects containing field metadata and rows
        """
        ...
