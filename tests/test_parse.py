from __future__ import annotations

import json
import shutil
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from src.models import FetchResult
from src.pipeline import ChapterPipeline

FIXTURES = Path(__file__).parent / "fixtures"
EXAMPLES = FIXTURES / "examples"
TMP_ROOT = Path("tests/.tmp/pipeline_runs")


class StubFetcher:
    def __init__(self, pages: dict[str, str], fetched_at: str = "2026-03-07T00:00:00Z") -> None:
        self.pages = pages
        self.fetched_at = fetched_at

    def fetch(self, url: str) -> FetchResult:
        return FetchResult(
            url=url,
            html=self.pages[url],
            fetched_at=self.fetched_at,
            status_code=200,
        )


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _example(name: str) -> dict[str, object]:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


@contextmanager
def _temp_dir() -> Path:
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    path = TMP_ROOT / f"run_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def test_pipeline_writes_syosetu_artifacts_and_matches_example() -> None:
    url = "https://ncode.syosetu.com/n8733gf/1/"
    with _temp_dir() as temp_dir:
        pipeline = ChapterPipeline(
            data_dir=temp_dir / "data",
            fetcher=StubFetcher({url: _fixture("syosetu_chapter.html")}),
        )

        stored = pipeline.run(url)
        expected = _example("syosetu_example.json")

        assert stored.raw_html_path.exists()
        assert stored.cleaned_html_path.exists()
        assert stored.json_path.exists()
        assert stored.document.to_dict() == expected


def test_pipeline_writes_kakuyomu_artifacts_and_matches_example() -> None:
    url = "https://kakuyomu.jp/works/16818093001234567890/episodes/16818093001234567999"
    with _temp_dir() as temp_dir:
        pipeline = ChapterPipeline(
            data_dir=temp_dir / "data",
            fetcher=StubFetcher({url: _fixture("kakuyomu_chapter.html")}),
        )

        stored = pipeline.run(url)
        expected = _example("kakuyomu_example.json")

        assert stored.document.to_dict() == expected
        assert stored.document.segments[0].kind == "paragraph"
        assert stored.document.segments[-1].kind == "image"
