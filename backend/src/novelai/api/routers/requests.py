from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from novelai.api.response_helpers import request_list_response, request_response, source_candidate_response
from novelai.api.routers.dependencies import get_requests, verify_api_key
from novelai.services.novel_request_service import NovelRequestService

router = APIRouter()


class NovelRequestCreateRequest(BaseModel):
    title: str
    source_key: str | None = None
    source_url: str | None = None
    requested_by: str | None = None
    notes: str | None = None


class NovelRequestVoteRequest(BaseModel):
    voter: str | None = None


class NovelRequestStatusRequest(BaseModel):
    status: str
    reviewed_by: str | None = None
    notes: str | None = None


class SourceCandidateCreateRequest(BaseModel):
    source_key: str | None = None
    source_url: str | None = None
    submitted_by: str | None = None
    notes: str | None = None


@router.get("/requests")
async def list_novel_requests(
    status: str | None = None,
    limit: int | None = None,
    requests: NovelRequestService = Depends(get_requests),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    try:
        items = requests.list_requests(status=status, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"requests": request_list_response(items)}


@router.post("/requests")
async def create_novel_request(
    body: NovelRequestCreateRequest,
    requests: NovelRequestService = Depends(get_requests),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    try:
        return request_response(
            requests.create_request(
                title=body.title,
                source_key=body.source_key,
                source_url=body.source_url,
                requested_by=body.requested_by,
                notes=body.notes,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/requests/{request_id}")
async def get_novel_request(
    request_id: str,
    requests: NovelRequestService = Depends(get_requests),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    item = requests.get_request(request_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Novel request not found")
    return request_response(item)


@router.post("/requests/{request_id}/vote")
async def vote_novel_request(
    request_id: str,
    body: NovelRequestVoteRequest,
    requests: NovelRequestService = Depends(get_requests),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    item = requests.vote_request(request_id, voter=body.voter)
    if item is None:
        raise HTTPException(status_code=404, detail="Novel request not found")
    return request_response(item)


@router.patch("/requests/{request_id}")
async def update_novel_request_status(
    request_id: str,
    body: NovelRequestStatusRequest,
    requests: NovelRequestService = Depends(get_requests),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    try:
        item = requests.update_request_status(
            request_id,
            body.status,
            reviewed_by=body.reviewed_by,
            notes=body.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Novel request not found")
    return request_response(item)


@router.post("/requests/{request_id}/source-candidates")
async def add_source_candidate(
    request_id: str,
    body: SourceCandidateCreateRequest,
    requests: NovelRequestService = Depends(get_requests),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    try:
        item = requests.add_source_candidate(
            request_id,
            source_key=body.source_key,
            source_url=body.source_url,
            submitted_by=body.submitted_by,
            notes=body.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Novel request not found")
    return source_candidate_response(item)
