from __future__ import annotations

from pathlib import Path

from novelai.inputs.base import DocumentAdapter
from novelai.inputs.models import ImportedAsset, ImportedDocument, ImportedUnit
from novelai.inputs.utils import guess_content_type, image_placeholder, is_image_name


class ImageFolderDocumentAdapter(DocumentAdapter):
    @property
    def key(self) -> str:
        return "image_folder"

    def probe(self, source: str | Path) -> bool:
        path = Path(source)
        if path.is_file():
            return is_image_name(path)
        if not path.is_dir():
            return False
        return any(is_image_name(child) for child in path.iterdir() if child.is_file())

    async def import_document(
        self,
        source: str | Path,
        *,
        max_units: int | None = None,
    ) -> ImportedDocument:
        path = Path(source)
        files = [path] if path.is_file() else sorted(child for child in path.iterdir() if child.is_file() and is_image_name(child))
        if max_units is not None:
            files = files[:max_units]
        if not files:
            raise RuntimeError(f"No image files found at {path}")

        units: list[ImportedUnit] = []
        for index, file_path in enumerate(files, start=1):
            placeholder = image_placeholder(file_path.name, index)
            units.append(
                ImportedUnit(
                    unit_id=str(index),
                    import_order=index,
                    title=file_path.stem.replace("_", " ").strip() or f"Page {index}",
                    text=placeholder,
                    source_ref=str(file_path.resolve()),
                    unit_type="page",
                    images=(
                        ImportedAsset(
                            source_ref=str(file_path.resolve()),
                            content=file_path.read_bytes(),
                            content_type=guess_content_type(file_path.name),
                            placeholder=placeholder,
                            alt=file_path.stem.replace("_", " ").strip() or f"Page {index}",
                            title=file_path.name,
                        ),
                    ),
                    ocr_required=True,
                    context_group_id=path.stem or path.name,
                )
            )

        return ImportedDocument(
            adapter_key=self.key,
            origin_type="file" if path.is_file() else "directory",
            origin_uri_or_path=str(path.resolve()),
            document_type="images",
            title=path.stem.replace("_", " ").strip() or "Imported Images",
            units=tuple(units),
        )
