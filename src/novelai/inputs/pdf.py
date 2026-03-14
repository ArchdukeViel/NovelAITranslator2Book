from __future__ import annotations

from pathlib import Path

from novelai.inputs.base import DocumentAdapter
from novelai.inputs.models import ImportedDocument, ImportedUnit
from novelai.inputs.utils import normalize_text


class PDFDocumentAdapter(DocumentAdapter):
    @property
    def key(self) -> str:
        return "pdf"

    def probe(self, source: str | Path) -> bool:
        return Path(source).suffix.lower() == ".pdf"

    async def import_document(
        self,
        source: str | Path,
        *,
        max_units: int | None = None,
    ) -> ImportedDocument:
        try:
            from pypdf import PdfReader
        except ModuleNotFoundError as exc:
            raise RuntimeError("PDF import requires the optional 'pypdf' dependency.") from exc

        path = Path(source)
        reader = PdfReader(str(path))
        units: list[ImportedUnit] = []
        for index, page in enumerate(reader.pages, start=1):
            text = normalize_text(page.extract_text() or "")
            units.append(
                ImportedUnit(
                    unit_id=str(index),
                    import_order=index,
                    title=f"Page {index}",
                    text=text or f"[PDF page {index}]",
                    source_ref=f"{path.resolve()}#page={index}",
                    unit_type="page",
                    ocr_required=not bool(text),
                    context_group_id=path.stem,
                )
            )
            if max_units is not None and len(units) >= max_units:
                break

        if not units:
            raise RuntimeError(f"No pages found in {path}")

        title = None
        if reader.metadata is not None:
            title = getattr(reader.metadata, "title", None) or reader.metadata.get("/Title")

        return ImportedDocument(
            adapter_key=self.key,
            origin_type="file",
            origin_uri_or_path=str(path.resolve()),
            document_type="pdf",
            title=title.strip() if isinstance(title, str) and title.strip() else path.stem,
            units=tuple(units),
        )
