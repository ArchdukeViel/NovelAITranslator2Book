from __future__ import annotations

from fastapi import APIRouter, Depends

from novelai.inputs.registry import available_input_adapters
from novelai.api.auth.roles import require_role
from novelai.sources.registry import available_sources

router = APIRouter()


@router.get("/sources", response_model=list[str])
async def list_sources(_owner=Depends(require_role("owner"))) -> list[str]:
    return available_sources()


@router.get("/input-adapters", response_model=list[str])
async def list_input_adapters(_owner=Depends(require_role("owner"))) -> list[str]:
    return available_input_adapters()
