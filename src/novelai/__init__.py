"""Novel AI core package."""

# Import core registries to trigger provider/source registration side effects.
from novelai import providers  # noqa: F401
from novelai import sources  # noqa: F401

__version__ = "0.1.0"
