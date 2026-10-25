"""FastAPI application for the Campus Compass document assistant."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .config import MAX_UPLOAD_BYTES
from .db import connect, initialize_database
from .ingestion import ingest_document
from .service import answer_question

STATIC_DIR = Path(__file__).resolve().parents[1] / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title="Campus Compass",
    description="A cite-first question answering assistant for campus documents.",
    version="1.0.0",
    lifespan=lifespan,
)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/static/{filename}", include_in_schema=False)
def static_file(filename: str) -> FileResponse:
    if filename not in {"styles.css", "app.js"}:
        raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(STATIC_DIR / filename)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "campus-compass"}


@app.get("/api/documents")
def list_documents() -> list[dict[str, object]]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT id, filename, created_at, chunk_count FROM documents ORDER BY created_at DESC"
        ).fetchall()
    return [dict(row) for row in rows]


@app.post("/api/documents", status_code=201)
async def upload_document(file: Annotated[UploadFile, File(...)]) -> dict[str, object]:
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"Files must be {MAX_UPLOAD_BYTES // (1024 * 1024)} MB or smaller.")
    try:
        return ingest_document(file.filename or "", content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/documents/{document_id}", status_code=204)
def delete_document(document_id: str) -> None:
    with connect() as connection:
        cursor = connection.execute("DELETE FROM documents WHERE id = ?", (document_id,))
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Document not found.")


@app.post("/api/chat")
def chat(request: ChatRequest) -> dict[str, object]:
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Enter a question.")
    try:
        return answer_question(question)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

