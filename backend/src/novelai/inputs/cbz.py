from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

from novelai.inputs.base import DocumentAdapter
from novelai.inputs.models import ImportedAsset, ImportedDocument, ImportedUnit
from novelai.inputs.utils import guess_content_type, image_placeholder, is_image_name


class CBZDocumentAdapter(DocumentAdapter):
    @property
    def key(self) -> str:
        return "cbz"

    def probe(self, source: str | Path) -> bool:
        return Path(source).suffix.lower() == ".cbz"

    async def import_document(
        self,
        source: str | Path,
        *,
        max_units: int | None = None,
    ) -> ImportedDocument:
        path = Path(source)
        units: list[ImportedUnit] = []
        with ZipFile(path) as archive:
            image_names = sorted(name for name in archive.namelist() if is_image_name(name))
            if max_units is not None:
                image_names = image_names[:max_units]
            for index, name in enumerate(image_names, start=1):
                placeholder = image_placeholder(name, index)
                units.append(
                    ImportedUnit(
                        unit_id=str(index),
                        import_order=index,
                        title=Path(name).stem.replace("_", " ").strip() or f"Page {index}",
                        text=placeholder,
                        source_ref=f"{path.resolve()}!/{name}",
                        unit_type="page",
                        images=(
                            ImportedAsset(
                                source_ref=f"{path.resolve()}!/{name}",
                                content=archive.read(name),
                                content_type=guess_content_type(name),
                                placeholder=placeholder,
                                alt=Path(name).stem.replace("_", " ").strip() or f"Page {index}",
                                title=name,
                            ),
                        ),
                        ocr_required=True,
                        context_group_id=path.stem,
                    )
                )

        if not units:
            raise RuntimeError(f"No image entries found in {path}")

        return ImportedDocument(
            adapter_key=self.key,
            origin_type="archive",
            origin_uri_or_path=str(path.resolve()),
            document_type="cbz",
            title=path.stem.replace("_", " ").strip() or "Imported CBZ",
            units=tuple(units),
        )
