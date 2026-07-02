# Design: End-to-End Integration Testing

## Overview

Create a self-contained e2e test suite under `backend/tests/e2e/` using a dummy novel source fixture and a mock Gemini provider. Tests exercise the full pipeline: create, scrape, translate, publish, and read via public API. Uses in-memory SQLite and `tmp_path` for zero side effects.

## Architecture

### Affected Files

| File | Change type |
|---|---|
| `backend/tests/e2e/__init__.py` | New — e2e test package |
| `backend/tests/e2e/conftest.py` | New — shared fixtures: FastAPI client, DB, storage, mock provider |
| `backend/tests/e2e/test_full_pipeline.py` | New — happy path and error path tests |
| `backend/tests/fixtures/e2e/test_novel/index.html` | New — dummy novel HTML fixture |
| `backend/tests/fixtures/e2e/dummy_source.py` | New — `DummySource` adapter |
| `backend/tests/fixtures/e2e/mock_provider.py` | New — `MockGeminiProvider` |
| `pyproject.toml` | Update — add `e2e` pytest marker |
| `.github/workflows/ci.yml` | Update — add e2e test step |

### Files Not Touched

- All production code files — no changes
- DB models — no changes
- Existing unit tests — no changes

## Component Design

### 1. Dummy Novel Fixture (`tests/fixtures/e2e/test_novel/index.html`)

A minimal HTML file representing a Japanese web novel:

```html
<!DOCTYPE html>
<html lang="ja">
<head><title>Test Novel - テスト小説</title></head>
<body>
<h1>テスト小説</h1>
<div class="novel-info">
  <p class="title">テスト小説</p>
  <p class="author">テスト作者</p>
</div>
<div class="chapters">
  <div class="chapter" id="ch1">
    <h2>第一章：始まり</h2>
    <p>これはテスト小説の最初の章です。主人公は新しい冒険に出発します。</p>
    <p>道中で不思議な生き物と出会い、重要な選択を迫られます。</p>
  </div>
  <div class="chapter" id="ch2">
    <h2>第二章：旅路</h2>
    <p>第二章では、主人公は仲間と共に困難な山道を進みます。</p>
    <p>頂上に到着すると、驚くべき光景が広がっていました。</p>
  </div>
  <div class="chapter" id="ch3">
    <h2>第三章：決着</h2>
    <p>最終章では、全ての謎が明らかになります。</p>
    <p>主人公は正しい選択をして、物語は幕を閉じます。</p>
  </div>
</div>
</body>
</html>
```

### 2. `DummySource` Adapter (`tests/fixtures/e2e/dummy_source.py`)

```python
from pathlib import Path
from bs4 import BeautifulSoup
from novelai.sources.base import SourceAdapter

FIXTURE_DIR = Path(__file__).parent / "test_novel"
HTML_PATH = FIXTURE_DIR / "index.html"


class DummySource(SourceAdapter):
    source_key = "dummy-e2e"

    @classmethod
    def can_handle(cls, source: str) -> bool:
        return source == "dummy://test-novel"

    def fetch_metadata(self, source: str) -> dict:
        soup = self._load()
        chapters = []
        for el in soup.select(".chapter"):
            ch_id = el.get("id", "")
            title = el.find("h2").get_text(strip=True) if el.find("h2") else ""
            chapters.append({"id": ch_id, "num": len(chapters) + 1, "title": title})
        return {
            "title": "テスト小説",
            "source_url": source,
            "language": "ja",
            "origin_type": "url",
            "chapters": chapters,
        }

    def fetch_chapter(self, source: str, chapter_id: str) -> dict:
        soup = self._load()
        ch = soup.find(id=chapter_id)
        if ch is None:
            raise ValueError(f"Chapter {chapter_id} not found")
        paragraphs = [p.get_text(strip=True) for p in ch.find_all("p")]
        return {
            "chapter_id": chapter_id,
            "title": ch.find("h2").get_text(strip=True) if ch.find("h2") else "",
            "paragraphs": paragraphs,
        }

    def _load(self) -> BeautifulSoup:
        with open(HTML_PATH, "r", encoding="utf-8") as f:
            return BeautifulSoup(f.read(), "html.parser")
```

### 3. `MockGeminiProvider` (`tests/fixtures/e2e/mock_provider.py`)

```python
from novelai.providers.base import BaseProvider

class MockGeminiProvider(BaseProvider):
    provider_key = "mock-gemini"

    def __init__(self):
        self._call_counts: dict[str, int] = {}
        self._fail_chapters: set[str] = set()

    def fail_on_chapter(self, chapter_id: str) -> None:
        self._fail_chapters.add(chapter_id)

    def get_call_count(self, chapter_id: str) -> int:
        return self._call_counts.get(chapter_id, 0)

    async def translate(self, text: str, source_lang: str, target_lang: str, **kwargs) -> str:
        ch_id = kwargs.get("chapter_id", "unknown")
        self._call_counts[ch_id] = self._call_counts.get(ch_id, 0) + 1

        if ch_id in self._fail_chapters:
            raise Exception(f"Simulated provider failure for {ch_id}")

        return f"[EN] {text}"

    def supports_language_pair(self, source: str, target: str) -> bool:
        return source == "ja" and target == "en"
```

### 4. Shared E2E Conftest (`tests/e2e/conftest.py`)

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pathlib import Path

from novelai.main import app
from novelai.db.engine import get_db_session
from novelai.sources.registry import get_registry
from tests.fixtures.e2e.dummy_source import DummySource
from tests.fixtures.e2e.mock_provider import MockGeminiProvider


@pytest.fixture(scope="session")
def mock_provider():
    return MockGeminiProvider()


@pytest.fixture(scope="session")
def test_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    # Create all tables
    from novelai.db.models.base import Base
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)
    return TestingSession


@pytest.fixture(scope="session")
def test_client(test_db, tmp_path_factory, mock_provider):
    storage_dir = tmp_path_factory.mktemp("e2e_storage")

    # Override dependencies
    app.dependency_overrides[get_db_session] = test_db

    # Register dummy source
    registry = get_registry()
    registry.register(DummySource)

    # Override provider with mock
    # (app-specific provider injection)

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def owner_auth(test_client):
    """Get auth header for owner user."""
    resp = test_client.post("/api/auth/login", json={
        "username": "testowner",
        "password": "testpass",
    })
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
```

### 5. Test Cases (`tests/e2e/test_full_pipeline.py`)

```python
import pytest

@pytest.mark.e2e
class TestFullPipeline:

    def test_full_pipeline_create_to_public_read(self, test_client, owner_auth, mock_provider):
        novel_id = "dummy://test-novel"

        # Step 1: Create novel
        resp = test_client.post("/api/admin/novels", json={
            "novel_id": "test-novel-e2e",
            "title": "E2E Test Novel",
            "source_url": novel_id,
        }, headers=owner_auth)
        assert resp.status_code == 201

        # Step 2: Scrape
        resp = test_client.post(f"/{novel_id}/scrape", headers=owner_auth)
        assert resp.status_code == 200

        # Step 3: Refresh projection
        resp = test_client.post(f"/{novel_id}/refresh-catalog-projection", headers=owner_auth)
        assert resp.status_code == 200

        # Step 4: Translate
        resp = test_client.post(f"/{novel_id}/translate", headers=owner_auth)
        assert resp.status_code == 200

        # Step 5: Publish
        resp = test_client.post(f"/{novel_id}/publish", headers=owner_auth)
        assert resp.status_code == 200

        # Step 6: Public catalog
        resp = test_client.get("/api/public/catalog")
        assert resp.status_code == 200
        slugs = [n["slug"] for n in resp.json()["novels"]]
        assert "test-novel-e2e" in slugs

        # Step 7: Public chapter read
        resp = test_client.get("/api/public/novels/test-novel-e2e/chapters/ch1")
        assert resp.status_code == 200
        assert "[EN]" in resp.json()["text"]

    def test_pipeline_handles_provider_failure(self, test_client, owner_auth, mock_provider):
        """One chapter fails; translation returns partial success."""
        mock_provider.fail_on_chapter("ch2")
        # ... similar flow, assert ch2 has error, ch1 and ch3 succeed

    def test_pipeline_idempotent_retranslate(self, test_client, owner_auth, mock_provider):
        """Run translate twice; second is no-op."""
        # First translate
        resp = test_client.post(f"/test-novel-e2e/translate", headers=owner_auth)
        assert resp.status_code == 200
        first_calls = dict(mock_provider._call_counts)
        # Second translate
        resp = test_client.post(f"/test-novel-e2e/translate", headers=owner_auth)
        assert resp.status_code == 200
        # No new calls made
        assert mock_provider._call_counts == first_calls

    def test_pipeline_with_glossary(self, test_client, owner_auth, mock_provider):
        """Glossary terms appear in translated output."""
        # Create glossary
        resp = test_client.post(f"/test-novel-e2e/glossary", json={
            "terms": [{"source": "主人公", "target": "Hero"}],
        }, headers=owner_auth)
        assert resp.status_code == 200
        # Translate
        resp = test_client.post(f"/test-novel-e2e/translate", headers=owner_auth)
        assert resp.status_code == 200
        # Read chapter
        resp = test_client.get("/api/public/novels/test-novel-e2e/chapters/ch1")
        # Verify glossary term appears
        # (depends on prompt injection implementation)

    def test_pipeline_empty_novel(self, test_client, owner_auth):
        """Novel with zero chapters yields catalog entry with count=0."""
        resp = test_client.post("/api/public/catalog")
        # ... verify empty novel appears
```

## Migration and Backward Compatibility

- All test code is additive. No production code is changed.
- Existing unit tests are unaffected.
- The `e2e` marker allows running e2e tests separately: `pytest -m e2e`.

## Acceptance Criteria

1. `test_full_pipeline_create_to_public_read` passes: 8-step flow succeeds end-to-end.
2. `test_pipeline_handles_provider_failure` passes: partial failure does not crash the pipeline.
3. `test_pipeline_idempotent_retranslate` passes: second translate call is a no-op.
4. `test_pipeline_with_glossary` passes: glossary terms are used during translation.
5. `test_pipeline_empty_novel` passes: empty novels are handled gracefully.
6. Full e2e suite (`pytest -m e2e`) completes in under 60 seconds.
7. All tests use in-memory SQLite and `tmp_path`; no persistent state between runs.
