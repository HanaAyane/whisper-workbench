"""术语表列表、导入导出与预览接口。"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from app.glossary.io import merge_duplicates, parse_entries
from app.glossary.models import (
    GlossaryEntry,
    GlossaryNotFoundError,
    GlossaryValidationError,
)
from app.glossary.replacer import preview_text
from app.glossary.store import GlossaryStore

router = APIRouter()


class GlossaryImportRequest(BaseModel):
    glossary_id: str = Field(default="default", min_length=1)
    format: Literal["csv", "json"] = "json"
    content: str = Field(min_length=1)


class GlossaryPreviewRequest(BaseModel):
    text: str
    field: Literal["text", "translation"] = "text"
    glossary_id: str = "default"


def _store(request: Request) -> GlossaryStore:
    return GlossaryStore(request.app.state.settings)


@router.get("/glossary")
def list_glossaries(request: Request) -> dict[str, object]:
    return {"glossaries": _store(request).list_glossaries()}


@router.post("/glossary/import")
def import_glossary(payload: GlossaryImportRequest, request: Request) -> dict[str, object]:
    store = _store(request)
    try:
        entries = parse_entries(payload.content, payload.format)
        entries, warnings = merge_duplicates(entries)
        if not entries:
            raise GlossaryValidationError("词表没有可导入的有效词条。")
        store.save(payload.glossary_id, entries)
    except GlossaryValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"glossary_id": payload.glossary_id, "entry_count": len(entries), "warnings": warnings}


@router.put("/glossary/{glossary_id}")
def save_glossary(
    glossary_id: str, payload: list[GlossaryEntry], request: Request
) -> dict[str, object]:
    try:
        entries, warnings = merge_duplicates(payload)
        _store(request).save(glossary_id, entries)
    except GlossaryValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"glossary_id": glossary_id, "entry_count": len(entries), "warnings": warnings}


@router.delete("/glossary/{glossary_id}", status_code=204)
def delete_glossary(glossary_id: str, request: Request) -> Response:
    try:
        _store(request).delete(glossary_id)
    except GlossaryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except GlossaryValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(status_code=204)


@router.get("/glossary/{glossary_id}/export")
def export_glossary(
    glossary_id: str,
    request: Request,
    format: Literal["csv", "json"] = "json",
) -> PlainTextResponse:
    try:
        content = _store(request).export(glossary_id, format)
    except GlossaryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except GlossaryValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    media_type = "text/csv" if format == "csv" else "application/json"
    return PlainTextResponse(
        content,
        media_type=f"{media_type}; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{glossary_id}.{format}"'},
    )


@router.post("/glossary/preview")
def preview(payload: GlossaryPreviewRequest, request: Request) -> dict[str, object]:
    try:
        entries = _store(request).load(payload.glossary_id)
    except GlossaryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except GlossaryValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    result = preview_text(payload.text, entries, payload.field)
    return {
        "text": result.text,
        "replaced_text": result.replaced_text,
        "hits": [hit.model_dump(mode="json") for hit in result.hits],
    }
