"""Translation model provider adapters."""

# Import available providers to ensure they register themselves.
from novelai.providers import dummy_provider  # noqa: F401
from novelai.providers import openai_provider  # noqa: F401
