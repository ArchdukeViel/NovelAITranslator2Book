from __future__ import annotations

from fastapi import APIRouter, Depends

from novelai.api.auth.roles import require_role
from novelai.services.source_catalog_service import list_available_input_adapters, list_available_sources

router = APIRouter()


@router.get("/sources", response_model=list[str])
async def list_sources(_owner=Depends(require_role("owner"))) -> list[str]:
    return list_available_sources()


@router.get("/input-adapters", response_model=list[str])
async def list_input_adapters(_owner=Depends(require_role("owner"))) -> list[str]:
    return list_available_input_adapters()
