from __future__ import annotations

from pathlib import Path
from urllib.parse import urljoin
from xml.etree import ElementTree
from zipfile import ZipFile

from bs4 import BeautifulSoup

from novelai.inputs.base import DocumentAdapter
from novelai.inputs.models import ImportedAsset, ImportedDocument, ImportedUnit
from novelai.inputs.utils import guess_content_type, normalize_text

_CONTAINER_NS = {"c": "urn:oasis:names:tc:opendocument:xmlns:container"}
_OPF_NS = {
    "opf": "http://www.idpf.org/2007/opf",
    "dc": "http://purl.org/dc/elements/1.1/",
}


class EPUBDocumentAdapter(DocumentAdapter):
    @property
    def key(self) -> str:
        return "epub"

    def probe(self, source: str | Path) -> bool:
        return Path(source).suffix.lower() == ".epub"

    async def import_document(
        self,
        source: str | Path,
        *,
        max_units: int | None = None,
    ) -> ImportedDocument:
        path = Path(source)
        with ZipFile(path) as archive:
            container = ElementTree.fromstring(archive.read("META-INF/container.xml"))
            rootfile = container.find(".//c:rootfile", _CONTAINER_NS)
            if rootfile is None:
                raise RuntimeError("EPUB container.xml is missing the rootfile declaration.")
            opf_path = rootfile.attrib["full-path"]
            opf_dir = Path(opf_path).parent.as_posix()
            package = ElementTree.fromstring(archive.read(opf_path))
            manifest = {
                item.attrib["id"]: item.attrib.get("href", "")
                for item in package.findall(".//opf:manifest/opf:item", _OPF_NS)
            }
            spine_ids = [
                itemref.attrib["idref"]
                for itemref in package.findall(".//opf:spine/opf:itemref", _OPF_NS)
                if itemref.attrib.get("idref")
            ]

            title = package.findtext(".//dc:title", default=path.stem, namespaces=_OPF_NS)
            author = package.findtext(".//dc:creator", default=None, namespaces=_OPF_NS)
            units: list[ImportedUnit] = []
            for index, item_id in enumerate(spine_ids, start=1):
                href = manifest.get(item_id)
                if not href:
                    continue
                full_path = urljoin(f"{opf_dir}/", href).lstrip("/")
                document_bytes = archive.read(full_path)
                soup = BeautifulSoup(document_bytes, "lxml")
                chapter_title = soup.title.get_text(strip=True) if soup.title else None
                body = soup.body or soup
                text = normalize_text(body.get_text("\n"))
                image_assets: list[ImportedAsset] = []
                for img in body.find_all("img"):
                    img_src = img.get("src")
                    if not isinstance(img_src, str) or not img_src.strip():
                        continue
                    img_full_path = urljoin(f"{Path(full_path).parent.as_posix()}/", img_src).lstrip("/")
                    image_assets.append(
                        ImportedAsset(
                            source_ref=f"{path.resolve()}!/{img_full_path}",
                            content=archive.read(img_full_path),
                            content_type=guess_content_type(img_full_path),
                            placeholder=img.get("alt") or img.get("title") or f"[Image {len(image_assets) + 1}]",
                            alt=img.get("alt"),
                            title=img.get("title"),
                        )
                    )

                if not text and not image_assets:
                    continue
                units.append(
                    ImportedUnit(
                        unit_id=str(index),
                        import_order=index,
                        title=chapter_title or f"Section {index}",
                        text=text,
                        source_ref=f"{path.resolve()}!/{full_path}",
                        unit_type="chapter",
                        images=tuple(image_assets),
                        ocr_required=bool(image_assets and not text),
                        context_group_id=path.stem,
                    )
                )
                if max_units is not None and len(units) >= max_units:
                    break

        if not units:
            raise RuntimeError(f"No readable spine documents found in {path}")

        return ImportedDocument(
            adapter_key=self.key,
            origin_type="file",
            origin_uri_or_path=str(path.resolve()),
            document_type="epub",
            title=title.strip() if isinstance(title, str) and title.strip() else path.stem,
            author=author.strip() if isinstance(author, str) and author.strip() else None,
            units=tuple(units),
        )
