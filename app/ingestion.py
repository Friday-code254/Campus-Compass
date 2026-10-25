"""Document parsing, section-aware chunking, and SQLite ingestion."""

from __future__ import annotations

import hashlib
import io
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader

from .config import CHUNK_OVERLAP, CHUNK_SIZE
from .db import connect

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md"}
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")


def parse_document(filename: str, content: bytes) -> list[tuple[int | None, str]]:
    """Return (page number, text) pairs from a PDF or plain-text document."""
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError("Upload a PDF, TXT, or Markdown file.")
    if not content:
        raise ValueError("The uploaded file is empty.")

    if suffix == ".pdf":
        try:
            reader = PdfReader(io.BytesIO(content))
            pages = [(index + 1, page.extract_text() or "") for index, page in enumerate(reader.pages)]
        except Exception as exc:
            raise ValueError("This PDF could not be read. Try a text-based PDF.") from exc
        return [(page, text) for page, text in pages if text.strip()]

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Text files must use UTF-8 encoding.") from exc
    return [(None, text)]


def make_chunks(filename: str, pages: list[tuple[int | None, str]]) -> list[dict[str, object]]:
    """Keep short sections together and split long sections into overlapping windows."""
    chunks: list[dict[str, object]] = []
    stride = CHUNK_SIZE - CHUNK_OVERLAP

    def emit(body: str, section: str | None, page_number: int | None) -> None:
        body = body.strip()
        start = 0
        while start < len(body):
            end = min(start + CHUNK_SIZE, len(body))
            excerpt = body[start:end].strip()
            if excerpt:
                context = f"Document: {filename}"
                if section:
                    context += f"\nSection: {section}"
                chunks.append(
                    {
                        "filename": filename,
                        "page_number": page_number,
                        "section": section,
                        "body": excerpt,
                        "retrieval_text": f"{context}\n\n{excerpt}",
                    }
                )
            if end == len(body):
                break
            start += stride

    for page_number, text in pages:
        clean = text.strip()
        if not clean:
            continue
        section: str | None = None
        paragraphs: list[str] = []

        def flush() -> None:
            if paragraphs:
                emit("\n\n".join(paragraphs), section, page_number)
                paragraphs.clear()

        for block in re.split(r"\n\s*\n", clean):
            lines = block.splitlines()
            if not lines:
                continue
            heading = HEADING_RE.match(lines[0].strip())
            if heading:
                flush()
                section = heading.group(1).strip()
                body_lines = lines[1:]
            else:
                body_lines = lines
            body = "\n".join(body_lines).strip()
            if body:
                paragraphs.append(body)
        flush()
    return chunks


def ingest_document(filename: str, content: bytes) -> dict[str, object]:
    """Parse, chunk, and persist a document. Duplicate file contents are ignored."""
    safe_name = Path(filename.replace("\\", "/")).name.strip()
    if not safe_name:
        raise ValueError("Choose a filename for the document.")
    pages = parse_document(safe_name, content)
    chunks = make_chunks(safe_name, pages)
    if not chunks:
        raise ValueError("No readable text was found in this document.")

    digest = hashlib.sha256(content).hexdigest()
    with connect() as connection:
        existing = connection.execute(
            "SELECT id, filename, chunk_count FROM documents WHERE sha256 = ?", (digest,)
        ).fetchone()
        if existing:
            return {"id": existing["id"], "filename": existing["filename"], "chunk_count": existing["chunk_count"], "duplicate": True}

        document_id = uuid.uuid4().hex
        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        connection.execute(
            "INSERT INTO documents (id, filename, sha256, created_at, chunk_count) VALUES (?, ?, ?, ?, ?)",
            (document_id, safe_name, digest, created_at, len(chunks)),
        )
        connection.executemany(
            """INSERT INTO chunks
               (document_id, chunk_index, page_number, section, body, retrieval_text)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                (
                    document_id,
                    index,
                    chunk["page_number"],
                    chunk["section"],
                    chunk["body"],
                    chunk["retrieval_text"],
                )
                for index, chunk in enumerate(chunks)
            ],
        )
    return {"id": document_id, "filename": safe_name, "chunk_count": len(chunks), "duplicate": False}

