"""Vercel Functions entrypoint for disposable monolith previews."""

from novelai.api.app import app

__all__ = ["app"]
