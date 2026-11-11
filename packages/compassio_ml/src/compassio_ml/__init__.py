"""Compassio ML package.

Phase 0 contains only data-integrity foundations (file hashing, source-file
guards and the source manifest model). Data cleaning, feature engineering,
training, evaluation and inference are planned for later phases and are
intentionally absent.
"""

from importlib.metadata import version

__version__ = version("compassio-ml")

__all__ = ["__version__"]
