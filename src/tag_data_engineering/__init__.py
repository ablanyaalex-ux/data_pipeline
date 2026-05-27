"""tag-data-engineering: Common utilities for Spark jobs in Microsoft Fabric."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version


try:
    __version__ = version("tag-data-engineering")
except PackageNotFoundError:
    __version__ = "unknown"
