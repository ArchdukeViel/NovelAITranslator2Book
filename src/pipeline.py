"""Legacy chapter extraction pipeline.

.. deprecated::
    This module is superseded by ``src/novelai/pipeline/`` which provides
    an async, stage-based pipeline with provider and source registries.
    Use ``novelai.pipeline`` for all new work.  This file is kept only for
    backward compatibility with the standalone ``python -m src.pipeline`` CLI.
"""

from __future__ import annotations

import argparse
import json
import logging
import warnings
from pathlib import Path

from bs4 import BeautifulSoup

from src.adapters.generic import GenericAdapter
from src.adapters.registry import AdapterRegistry
from src.fetch import ChapterFetcher
from src.models import StoredChapter
from src.parse import build_chapter_document
from src.utils import ensure_dir, storage_key

logger = logging.getLogger(__name__)
DEFAULT_DATA_DIR = Path("novel_library") / "source_pipeline"


class ChapterPipeline:
    """Fetch, extract, normalize, parse, and persist a chapter document."""

    def __init__(
        self,
        *,
        data_dir: str | Path = DEFAULT_DATA_DIR,
        fetcher: ChapterFetcher | None = None,
        registry: AdapterRegistry | None = None,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.fetcher = fetcher or ChapterFetcher()
        self.registry = registry or AdapterRegistry()
        self.raw_dir = ensure_dir(self.data_dir / "raw")
        self.html_dir = ensure_dir(self.data_dir / "chapters" / "html")
        self.json_dir = ensure_dir(self.data_dir / "chapters" / "json")

    def run(self, url: str) -> StoredChapter:
        fetched = self.fetcher.fetch(url)
        soup = BeautifulSoup(fetched.html, "lxml")
        adapter = self.registry.detect(fetched.url, fetched.html)
        logger.info("Detected adapter: %s", adapter.__class__.__name__)

        title = adapter.extract_title(soup)
        metadata = adapter.extract_metadata(soup, fetched.url)
        novel_id, chapter_id = adapter.build_ids(fetched.url, soup, metadata)
        key = storage_key(adapter.site, novel_id, chapter_id)
        raw_path = self.raw_dir / f"{key}.raw.html"
        raw_path.write_text(fetched.html, encoding="utf-8")

        source_html = self._extract_canonical_fragment(adapter, soup, fetched.url)
        document = build_chapter_document(
            site=adapter.site,
            adapter_name=adapter.__class__.__name__,
            novel_id=novel_id,
            chapter_id=chapter_id,
            url=fetched.url,
            fetched_at=fetched.fetched_at,
            title=title,
            metadata=metadata,
            source_html=source_html,
        )

        html_path = self.html_dir / f"{key}.html"
        html_path.write_text(document.source_html, encoding="utf-8")

        json_path = self.json_dir / f"{key}.json"
        json_path.write_text(json.dumps(document.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Stored chapter artifacts: raw=%s html=%s json=%s", raw_path, html_path, json_path)
        return StoredChapter(document=document, raw_html_path=raw_path, cleaned_html_path=html_path, json_path=json_path)

    def _extract_canonical_fragment(self, adapter, soup: BeautifulSoup, url: str) -> str:
        try:
            body = adapter.extract_chapter_body(soup)
            fragment = adapter.normalize_chapter_html(body, base_url=url)
            if fragment.strip():
                return fragment
        except Exception as exc:
            logger.warning("Adapter %s failed to extract canonical fragment: %s", adapter.__class__.__name__, exc)

        if isinstance(adapter, GenericAdapter):
            raise ValueError("Generic adapter could not extract chapter content.")

        fallback = self.registry.fallback
        logger.info("Falling back to %s for body extraction.", fallback.__class__.__name__)
        body = fallback.extract_chapter_body(soup)
        return fallback.normalize_chapter_html(body, base_url=url)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch and parse a web novel chapter into canonical HTML + JSON.")
    parser.add_argument("--url", required=True, help="Chapter URL to fetch and parse.")
    parser.add_argument(
        "--data-dir",
        default=str(DEFAULT_DATA_DIR),
        help="Output directory for raw HTML and parsed chapter artifacts.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        help="Logging verbosity.",
    )
    return parser


def main() -> None:
    warnings.warn(
        "src.pipeline is deprecated. Use the novelai CLI (novelaibook) instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    args = build_parser().parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level), format="[%(levelname)s] %(name)s: %(message)s")
    pipeline = ChapterPipeline(data_dir=args.data_dir)
    stored = pipeline.run(args.url)
    print(stored.json_path)


if __name__ == "__main__":
    main()
