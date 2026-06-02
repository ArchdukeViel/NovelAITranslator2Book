from __future__ import annotations

from fastapi import APIRouter, Depends

from novelai.inputs.registry import available_input_adapters
from novelai.api.routers.dependencies import verify_api_key
from novelai.sources.registry import available_sources

router = APIRouter()


@router.get("/sources", response_model=list[str])
async def list_sources(_auth: None = Depends(verify_api_key)) -> list[str]:
    return available_sources()


@router.get("/input-adapters", response_model=list[str])
async def list_input_adapters(_auth: None = Depends(verify_api_key)) -> list[str]:
    return available_input_adapters()
