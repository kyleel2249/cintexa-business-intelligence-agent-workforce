"""Document parsers for binary office formats.

Closes G12 in docs/GAP_REGISTER.md ("PDF/DOCX ingestion... explicit
rejection remains until parsers ship"). `python-docx` was already a
declared dependency in requirements.txt but was never actually imported
anywhere in the codebase — this module is what was missing to use it.

Both parsers take raw bytes and return plain text suitable for the existing
`knowledge_fabric.chunking` pipeline. Parsing failures raise
`core.errors.ValidationError` with a clear message rather than propagating
a library-specific exception or silently returning empty/garbled text.
"""

from __future__ import annotations

import io

from core.errors import ValidationError


def extract_pdf_text(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - dependency always declared in requirements.txt
        raise ValidationError(
            "PDF parsing requires the 'pypdf' package, which is not installed."
        ) from exc

    if not data:
        raise ValidationError("Empty PDF content")

    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as exc:
        raise ValidationError(f"Could not read PDF: {exc}") from exc

    if getattr(reader, "is_encrypted", False):
        try:
            reader.decrypt("")
        except Exception:
            pass
    if getattr(reader, "is_encrypted", False):
        raise ValidationError("PDF is password-protected; cannot extract text")

    pages = []
    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        pages.append(f"[page {i + 1}]\n{text}".strip())

    combined = "\n\n".join(p for p in pages if p)
    if not combined.strip():
        raise ValidationError(
            "No extractable text found in PDF (it may be a scanned/image-only "
            "document — OCR is not supported)"
        )
    return combined


def extract_docx_text(data: bytes) -> str:
    try:
        import docx
    except ImportError as exc:
        raise ValidationError(
            "DOCX parsing requires the 'python-docx' package, which is not installed."
        ) from exc

    if not data:
        raise ValidationError("Empty DOCX content")

    try:
        document = docx.Document(io.BytesIO(data))
    except Exception as exc:
        raise ValidationError(f"Could not read DOCX: {exc}") from exc

    parts = []
    for para in document.paragraphs:
        if para.text and para.text.strip():
            heading = para.style.name if para.style and para.style.name else ""
            if heading.lower().startswith("heading"):
                parts.append(f"\n## {para.text.strip()}\n")
            else:
                parts.append(para.text.strip())

    for table in document.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            if any(cells):
                parts.append(" | ".join(cells))

    combined = "\n".join(parts)
    if not combined.strip():
        raise ValidationError("No extractable text found in DOCX (document appears empty)")
    return combined
