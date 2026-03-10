"""DEPRECATED: Use PreferencesService directly.

This module exists only for backward compatibility.
SettingsService is now an alias for PreferencesService.
"""

from __future__ import annotations

from novelai.services.preferences_service import PreferencesService

# Backward-compatible alias
SettingsService = PreferencesService
