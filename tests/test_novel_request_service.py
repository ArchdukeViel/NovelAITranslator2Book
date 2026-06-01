from __future__ import annotations

import shutil
from uuid import uuid4

import pytest

from novelai.services.novel_request_service import NovelRequestService
from tests.conftest import TESTS_TMP_ROOT


@pytest.fixture
def requests() -> NovelRequestService:
    TESTS_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    data_dir = TESTS_TMP_ROOT / f"requests_{uuid4().hex}"
    data_dir.mkdir(parents=True, exist_ok=False)
    service = NovelRequestService(data_dir)
    yield service
    shutil.rmtree(data_dir, ignore_errors=True)


def test_create_request_with_source_candidate(requests: NovelRequestService) -> None:
    created = requests.create_request(
        title="Requested Novel",
        source_key="syosetu_ncode",
        source_url="https://ncode.syosetu.com/n1234ab/",
        requested_by="reader-1",
        notes="Looks promising",
    )

    loaded = requests.get_request(created["id"])

    assert loaded is not None
    assert loaded["title"] == "Requested Novel"
    assert loaded["status"] == "pending"
    assert loaded["requested_by"] == "reader-1"
    assert len(loaded["source_candidates"]) == 1
    assert loaded["source_candidates"][0]["source_key"] == "syosetu_ncode"


def test_vote_request_counts_anonymous_and_unique_named_voters(requests: NovelRequestService) -> None:
    created = requests.create_request(title="Requested Novel")

    requests.vote_request(created["id"])
    requests.vote_request(created["id"], voter="reader-1")
    voted = requests.vote_request(created["id"], voter="reader-1")

    assert voted is not None
    assert voted["vote_count"] == 2
    assert voted["voters"] == ["reader-1"]


def test_update_status_and_add_source_candidate(requests: NovelRequestService) -> None:
    created = requests.create_request(title="Requested Novel")

    approved = requests.update_request_status(created["id"], "approved", reviewed_by="admin")
    candidate = requests.add_source_candidate(
        created["id"],
        source_key="kakuyomu",
        source_url="https://kakuyomu.jp/works/123",
        submitted_by="reader-2",
    )
    loaded = requests.get_request(created["id"])

    assert approved is not None
    assert approved["status"] == "approved"
    assert approved["reviewed_by"] == "admin"
    assert candidate is not None
    assert loaded is not None
    assert loaded["source_candidates"][0]["source_key"] == "kakuyomu"


def test_list_requests_filters_by_status_and_sorts_by_votes(requests: NovelRequestService) -> None:
    low = requests.create_request(title="Low Vote")
    high = requests.create_request(title="High Vote")
    requests.vote_request(high["id"])
    requests.update_request_status(low["id"], "approved")

    pending = requests.list_requests(status="pending")

    assert [item["id"] for item in pending] == [high["id"]]
