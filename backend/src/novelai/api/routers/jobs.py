from __future__ import annotations

"""Compatibility import for the renamed activity router.

New code should import from ``novelai.api.routers.activity``.
"""

from novelai.api.routers.activity import (
    ActivityStatusUpdateRequest,
    CrawlActivityRequest,
    CrawlJobRequest,
    JobStatusUpdateRequest,
    TranslationActivityRequest,
    TranslationJobRequest,
    create_crawl_activity,
    create_translation_activity,
    delete_activity,
    get_activity,
    get_source_health,
    list_activity,
    list_source_health,
    router,
    run_activity,
    run_next_activity,
    update_activity_status,
)

__all__ = [
    "ActivityStatusUpdateRequest",
    "CrawlActivityRequest",
    "CrawlJobRequest",
    "JobStatusUpdateRequest",
    "TranslationActivityRequest",
    "TranslationJobRequest",
    "create_crawl_activity",
    "create_translation_activity",
    "delete_activity",
    "get_activity",
    "get_source_health",
    "list_activity",
    "list_source_health",
    "router",
    "run_activity",
    "run_next_activity",
    "update_activity_status",
]
