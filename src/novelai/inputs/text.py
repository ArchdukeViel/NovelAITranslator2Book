from __future__ import annotations

from pathlib import Path

from novelai.inputs.base import DocumentAdapter
from novelai.inputs.models import ImportedDocument, ImportedUnit
from novelai.inputs.utils import normalize_text


class TextDocumentAdapter(DocumentAdapter):
    @property
    def key(self) -> str:
        return "text"

    def probe(self, source: str | Path) -> bool:
        path = Path(source)
        if path.is_dir():
            return any(child.suffix.lower() in {".txt", ".md"} for child in path.iterdir() if child.is_file())
        return path.suffix.lower() in {".txt", ".md"}

    async def import_document(
        self,
        source: str | Path,
        *,
        max_units: int | None = None,
    ) -> ImportedDocument:
        path = Path(source)
        files = [path] if path.is_file() else sorted(
            child for child in path.iterdir() if child.is_file() and child.suffix.lower() in {".txt", ".md"}
        )
        if max_units is not None:
            files = files[:max_units]

        units: list[ImportedUnit] = []
        for index, file_path in enumerate(files, start=1):
            units.append(
                ImportedUnit(
                    unit_id=str(index),
                    import_order=index,
                    title=file_path.stem.replace("_", " ").strip() or f"Unit {index}",
                    text=normalize_text(file_path.read_text(encoding="utf-8")),
                    source_ref=str(file_path),
                    unit_type="chapter" if file_path.suffix.lower() == ".txt" else "section",
                )
            )

        if not units:
            raise RuntimeError(f"No text files found at {path}")

        document_type = "markdown" if all(file.suffix.lower() == ".md" for file in files) else "text"
        return ImportedDocument(
            adapter_key=self.key,
            origin_type="file",
            origin_uri_or_path=str(path.resolve()),
            document_type=document_type,
            title=path.stem.replace("_", " ").strip() or "Imported Text",
            units=tuple(units),
        )
