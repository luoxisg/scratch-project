"""Bounded, text-only extraction. No links or document actions are followed."""
from io import BytesIO
from pathlib import PurePosixPath
from zipfile import ZipFile

from defusedxml.ElementTree import fromstring

MAX_UPLOAD = 4 * 1024 * 1024
MAX_TEXT = 20_000
MAX_PAGES = 30
DOCX_TEXT = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"


def extract(name: str, data: bytes) -> dict:
    name = PurePosixPath(name.replace(chr(92), "/")).name
    if not name or len(name) > 150 or not data or len(data) > MAX_UPLOAD:
        raise ValueError("invalid_file")
    suffix = PurePosixPath(name).suffix.lower()
    if suffix in {".txt", ".md", ".markdown"}:
        text = data.decode("utf-8-sig")
        if any(ord(ch) < 32 and ch not in "\t\r\n" for ch in text):
            raise ValueError("invalid_text")
    elif suffix == ".docx":
        with ZipFile(BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > 250 or sum(item.file_size for item in entries) > 12 * 1024 * 1024:
                raise ValueError("oversized_docx")
            if any(item.flag_bits & 1 or item.filename.lower().endswith("vbaproject.bin") for item in entries):
                raise ValueError("unsupported_docx")
            tree = fromstring(archive.read("word/document.xml"))
            text = "\n".join(element.text for element in tree.iter(DOCX_TEXT) if element.text)
    elif suffix == ".pdf":
        if not data.startswith(b"%PDF-"):
            raise ValueError("invalid_pdf")
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted or len(reader.pages) > MAX_PAGES:
            raise ValueError("unsupported_pdf")
        parts = []
        remaining = MAX_TEXT + 1
        for page in reader.pages:
            part = (page.extract_text() or "")[:remaining]
            parts.append(part)
            remaining -= len(part) + 1
            if remaining <= 0:
                break
        text = "\n".join(parts)
    else:
        raise ValueError("unsupported_file")
    text = text.strip()
    if not text:
        raise ValueError("no_extractable_text")
    return {"document_name": name, "document_text": text[:MAX_TEXT], "truncated": len(text) > MAX_TEXT}
