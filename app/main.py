import asyncio
from contextlib import suppress
from datetime import date
import logging
from io import BytesIO
from pathlib import Path
from urllib.parse import quote
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile
from typing import Any

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from app.config import get_settings
from jobs.daily_reminder_job import send_due_reminders
from jobs.search_job_worker import dispatch_search_job
from fastapi.middleware.cors import CORSMiddleware
from app.graph import CompassGraph
from schemas.profile_schema import StudentProfile
from tools.auth_tool import CurrentUser, get_current_user
from tools.email_tool import EmailClient
from tools.short_id import normalize_opportunity_id

settings = get_settings()
settings.require_groq()
settings.require_tavily()
settings.require_supabase()
app = FastAPI(title=settings.app_name)
logger = logging.getLogger(__name__)
reminder_task: asyncio.Task | None = None

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_cors_origins,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
graph = CompassGraph()


def dispatch_due_reminders_once(background_tasks: BackgroundTasks) -> None:
    if settings.auto_dispatch_reminders:
        background_tasks.add_task(_send_due_reminders_safely)


def _send_due_reminders_safely() -> None:
    try:
        sent = send_due_reminders()
        if sent:
            logger.info("Sent %s reminder email(s).", len(sent))
    except Exception as exc:
        logger.warning("Reminder dispatch failed: %s", exc)


@app.on_event("startup")
def dispatch_pending_search_jobs() -> None:
    if not settings.auto_dispatch_search_jobs:
        return
    for job in graph.repository.list_queued_search_jobs():
        dispatch_search_job(job["id"])


async def _reminder_loop() -> None:
    while True:
        try:
            sent = await asyncio.to_thread(send_due_reminders)
            if sent:
                logger.info("Sent %s reminder email(s).", len(sent))
        except Exception as exc:
            logger.warning("Reminder dispatch failed: %s", exc)
        await asyncio.sleep(max(60, settings.reminder_poll_seconds))


@app.on_event("startup")
async def start_reminder_dispatcher() -> None:
    global reminder_task
    if not settings.auto_dispatch_reminders:
        if not settings.email_configured:
            logger.info("Reminder auto-dispatch disabled because email settings are not configured.")
        return
    reminder_task = asyncio.create_task(_reminder_loop())


@app.on_event("shutdown")
async def stop_reminder_dispatcher() -> None:
    global reminder_task
    if not reminder_task:
        return
    reminder_task.cancel()
    with suppress(asyncio.CancelledError):
        await reminder_task
    reminder_task = None


@app.middleware("http")
async def cors_safe_errors(request: Request, call_next):
    origin = request.headers.get("origin")
    try:
        response = await call_next(request)
    except Exception as exc:
        detail = str(exc) if settings.environment != "production" else "Backend request failed."
        response = JSONResponse(status_code=500, content={"detail": detail})
    if settings.is_allowed_cors_origin(origin):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Vary"] = "Origin"
    return response


class ProfileUpdateRequest(BaseModel):
    text: str
    profile: StudentProfile | None = None


class SearchRequest(BaseModel):
    query: str
    profile: StudentProfile | None = None
    max_results_per_query: int = Field(default=2, ge=1, le=5)


class DocumentGenerateRequest(BaseModel):
    opportunity_id: str = Field(min_length=1, max_length=8)
    document_type: str
    profile: StudentProfile
    cv_text: str | None = None
    uploaded_file_id: str | None = None
    regeneration_instruction: str | None = None
    parent_document_id: str | None = None


class DocumentUpdateRequest(BaseModel):
    content: str = Field(min_length=1)


class DocumentDownloadRequest(BaseModel):
    format: str = Field(default="txt")


class TrackerUpdateRequest(BaseModel):
    text: str
    opportunity_id: str | None = Field(default=None, min_length=1, max_length=8)


class TrackerStatusUpdateRequest(BaseModel):
    status: str = Field(min_length=1, max_length=32)


class NotificationPreferencesRequest(BaseModel):
    email_enabled: bool = True
    notification_email: str | None = None
    reminder_days: list[int] = Field(default_factory=lambda: [15, 7, 3, 1, 0])


class SaveOpportunityRequest(BaseModel):
    opportunity: dict[str, Any]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "date": date.today().isoformat()}


@app.get("/health/ocr")
def ocr_health(current_user: CurrentUser = Depends(get_current_user)) -> dict[str, str]:
    return graph.ocr_diagnostics()


def _build_docx_bytes(content: str) -> bytes:
    title, meta, paragraphs, closing = _format_document_blocks(content)
    body_parts = []
    if title:
        body_parts.append(_docx_paragraph(title, bold=True, size=28, spacing_after=120, align="center"))
    if meta:
        body_parts.append(_docx_paragraph(meta, italic=True, size=20, spacing_after=220, align="center"))
    for paragraph in paragraphs:
        body_parts.append(_docx_paragraph(paragraph, size=24, spacing_after=160, first_line=360))
    if closing:
        body_parts.append(_docx_paragraph(closing, size=24, spacing_before=160, spacing_after=120))
    body_parts.append(_docx_paragraph("Sincerely,", size=24, spacing_before=220, spacing_after=120))
    body_parts.append(_docx_paragraph("Compass Draft", size=24, bold=True, spacing_after=0))
    body = "".join(body_parts)
    document_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<w:document xmlns:wpc=\"http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas\" "
        "xmlns:mc=\"http://schemas.openxmlformats.org/markup-compatibility/2006\" "
        "xmlns:o=\"urn:schemas-microsoft-com:office:office\" "
        "xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\" "
        "xmlns:m=\"http://schemas.openxmlformats.org/officeDocument/2006/math\" "
        "xmlns:v=\"urn:schemas-microsoft-com:vml\" "
        "xmlns:wp14=\"http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing\" "
        "xmlns:wp=\"http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing\" "
        "xmlns:w10=\"urn:schemas-microsoft-com:office:word\" "
        "xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\" "
        "xmlns:w14=\"http://schemas.microsoft.com/office/word/2010/wordml\" "
        "xmlns:wpg=\"http://schemas.microsoft.com/office/word/2010/wordprocessingGroup\" "
        "xmlns:wpi=\"http://schemas.microsoft.com/office/word/2010/wordprocessingInk\" "
        "xmlns:wne=\"http://schemas.microsoft.com/office/word/2006/wordml\" "
        "xmlns:wps=\"http://schemas.microsoft.com/office/word/2010/wordprocessingShape\" mc:Ignorable=\"w14 wp14\">"
        "<w:body>"
        f"{body}"
        "<w:sectPr><w:pgSz w:w=\"12240\" w:h=\"15840\"/><w:pgMar w:top=\"1440\" w:right=\"1440\" w:bottom=\"1440\" w:left=\"1440\" w:header=\"708\" w:footer=\"708\" w:gutter=\"0\"/></w:sectPr>"
        "</w:body></w:document>"
    )
    content_types = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">"
        "<Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>"
        "<Default Extension=\"xml\" ContentType=\"application/xml\"/>"
        "<Override PartName=\"/word/document.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml\"/>"
        "</Types>"
    )
    rels = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\"/>"
    )
    root_rels = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
        "<Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"word/document.xml\"/>"
        "</Relationships>"
    )
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as docx:
        docx.writestr("[Content_Types].xml", content_types)
        docx.writestr("_rels/.rels", root_rels)
        docx.writestr("word/_rels/document.xml.rels", rels)
        docx.writestr("word/document.xml", document_xml)
    return buffer.getvalue()


def _format_document_blocks(content: str) -> tuple[str | None, str | None, list[str], str | None]:
    lines = [line.rstrip() for line in content.splitlines()]
    cleaned = [line for line in lines if line.strip()]
    if not cleaned:
        return None, None, [""], None
    lower = content.lower()
    title = None
    meta = None
    closing = None
    if "professor email" in lower or "email" in lower and len(cleaned) <= 8:
        title = "Subject: Inquiry About Research Opportunity"
        meta = "Professional outreach email"
        closing = "Best regards,\n[Your Name]"
    elif "cover letter" in lower or len(cleaned) >= 4 and "dear" in lower:
        title = "Cover Letter"
        meta = "Application letter"
        closing = "Thank you for your time and consideration."
    elif "statement of purpose" in lower or "sop" in lower:
        title = "Statement of Purpose"
        meta = "Graduate application statement"
        closing = "I would be grateful for the opportunity to contribute and grow in this program."
    elif "recommendation" in lower:
        title = "Letter of Recommendation"
        meta = "Professional recommendation"
        closing = "I recommend this candidate without reservation."
    else:
        title = "Application Document"
    paragraphs = cleaned[:]
    return title, meta, paragraphs, closing


def _docx_paragraph(
    text: str,
    *,
    bold: bool = False,
    italic: bool = False,
    size: int = 24,
    spacing_before: int = 0,
    spacing_after: int = 0,
    first_line: int = 0,
    align: str = "left",
) -> str:
    lines = text.splitlines() or [""]
    runs = "".join(
        _docx_run(line, bold=bold, italic=italic, size=size)
        for idx, line in enumerate(lines)
    )
    return (
        f"<w:p><w:pPr>"
        f"{_docx_align(align)}"
        f"<w:spacing w:before=\"{spacing_before}\" w:after=\"{spacing_after}\"/>"
        f"{'<w:ind w:firstLine=\"%d\"/>' % first_line if first_line else ''}"
        f"</w:pPr>{runs}</w:p>"
    )


def _docx_run(text: str, *, bold: bool = False, italic: bool = False, size: int = 24) -> str:
    escaped = escape(text) or " "
    return (
        "<w:r><w:rPr>"
        "<w:rFonts w:ascii=\"Times New Roman\" w:hAnsi=\"Times New Roman\"/>"
        f"<w:sz w:val=\"{size}\"/><w:szCs w:val=\"{size}\"/>"
        f"{'<w:b/>' if bold else ''}{'<w:i/>' if italic else ''}"
        "</w:rPr>"
        f"<w:t xml:space=\"preserve\">{escaped}</w:t></w:r>"
    )


def _docx_align(align: str) -> str:
    if align == "center":
        return "<w:jc w:val=\"center\"/>"
    if align == "right":
        return "<w:jc w:val=\"right\"/>"
    return "<w:jc w:val=\"left\"/>"


@app.post("/profile/update")
def update_profile(request: ProfileUpdateRequest, current_user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    return graph.update_profile_only(
        user_id=current_user.id,
        text=request.text,
        existing_profile=request.profile.model_dump() if request.profile else None,
    )


@app.get("/profile/me")
def get_profile(current_user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    compass_user_id = graph.repository.ensure_compass_user_id(current_user.id)
    profile = graph.repository.get_profile(current_user.id)
    return {"profile": profile, "compass_user_id": compass_user_id}


@app.put("/profile/me")
def save_profile(profile: StudentProfile, current_user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    profile_dict = profile.model_dump()
    saved = graph.repository.save_profile(current_user.id, profile_dict)
    return {
        "profile": profile_dict,
        "saved_profile": saved,
        "compass_user_id": saved.get("compass_user_id"),
    }


@app.post("/opportunities/search")
def search_opportunities(
    request: SearchRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    profile = request.profile.model_dump() if request.profile else graph.repository.get_profile(current_user.id) or {}
    job = graph.create_search_job(
        user_id=current_user.id,
        query=request.query,
        profile=profile,
        max_results_per_query=request.max_results_per_query,
    )
    if settings.auto_dispatch_search_jobs:
        dispatch_search_job(job["id"])
    return {"job": job}


@app.get("/opportunities/search/jobs")
def list_search_jobs(limit: int = 20, current_user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    return {"jobs": graph.list_search_jobs(user_id=current_user.id, limit=limit)}


@app.get("/opportunities/search/jobs/{job_id}")
def get_search_job(job_id: str, current_user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    job = graph.get_search_job(user_id=current_user.id, job_id=job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Search job not found.")
    return {"job": job}


@app.post("/opportunities/search/jobs/{job_id}/cancel")
def cancel_search_job(job_id: str, current_user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    try:
        return {"job": graph.cancel_search_job(user_id=current_user.id, job_id=job_id)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/opportunities/search/jobs/{job_id}/retry")
def retry_search_job(job_id: str, current_user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    try:
        job = graph.retry_search_job(user_id=current_user.id, job_id=job_id)
        if settings.auto_dispatch_search_jobs:
            dispatch_search_job(job["id"])
        return {"job": job}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/opportunities/search/jobs/{job_id}")
def delete_search_job(job_id: str, current_user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    try:
        return {"deleted": graph.delete_search_job(user_id=current_user.id, job_id=job_id)}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/opportunities")
def list_opportunities(limit: int = 50, current_user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    return {"opportunities": graph.list_opportunities(user_id=current_user.id, limit=limit)}


@app.get("/opportunities/{opportunity_id}")
def get_opportunity(opportunity_id: str, current_user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    try:
        return {"opportunity": graph.get_opportunity(normalize_opportunity_id(opportunity_id))}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/opportunities/save")
def save_opportunity_from_payload(
    request: SaveOpportunityRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        return {"saved": graph.save_opportunity(current_user.id, opportunity=request.opportunity)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/opportunities/{opportunity_id}/save")
def save_opportunity(opportunity_id: str, current_user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    try:
        return {"saved": graph.save_opportunity(current_user.id, opportunity_id=normalize_opportunity_id(opportunity_id))}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.delete("/opportunities/{opportunity_id}/save")
def unsave_opportunity(opportunity_id: str, current_user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    try:
        return {"unsaved": graph.unsave_opportunity(current_user.id, normalize_opportunity_id(opportunity_id))}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/opportunities/{opportunity_id}/deadline-plan")
def create_deadline_plan(
    opportunity_id: str,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        tasks = graph.create_deadline_plan(current_user.id, normalize_opportunity_id(opportunity_id))
        dispatch_due_reminders_once(background_tasks)
        return {"tasks": tasks}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/opportunities/{opportunity_id}/verify-deadline")
def verify_opportunity_deadline(
    opportunity_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        return graph.verify_deadline(normalize_opportunity_id(opportunity_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/documents/generate")
def generate_document(request: DocumentGenerateRequest, current_user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    try:
        return {
            "document": graph.draft_document(
                user_id=current_user.id,
                profile=request.profile.model_dump(),
                opportunity_id=request.opportunity_id,
                document_type=request.document_type,
                cv_text=request.cv_text,
                uploaded_file_id=request.uploaded_file_id,
                regeneration_instruction=request.regeneration_instruction,
                parent_document_id=request.parent_document_id,
            )
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.patch("/documents/{document_id}")
def update_document(
    document_id: str,
    request: DocumentUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        return {"document": graph.update_document(current_user.id, document_id, request.content)}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/documents/{document_id}/download")
def download_document(
    document_id: str,
    format: str = "txt",
    current_user: CurrentUser = Depends(get_current_user),
) -> Response:
    try:
        documents = graph.list_documents(current_user.id, limit=500)
        document = next((row for row in documents if row.get("id") == document_id), None)
        if not document:
            raise ValueError("Document not found.")
        content = str(document.get("content") or "")
        base_name = f"{document.get('document_type') or 'document'}-{document_id}"
        if format.lower() == "docx":
            filename = f"{base_name}.docx"
            return Response(
                content=_build_docx_bytes(content),
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
            )
        filename = f"{base_name}.txt"
        return Response(
            content=content,
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/tracker/update")
def update_tracker(
    request: TrackerUpdateRequest,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    tracker_item = graph.update_tracker(current_user.id, request.text, request.opportunity_id)
    dispatch_due_reminders_once(background_tasks)
    return {"tracker_item": tracker_item}


@app.patch("/tracker/{task_id}/status")
def update_tracker_status(
    task_id: str,
    request: TrackerStatusUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        tracker_item = graph.update_tracker_status(current_user.id, task_id, request.status)
        return {"tracker_item": tracker_item}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/tracker")
def list_tracker(limit: int = 50, current_user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    return {"tracker": graph.list_tracker_items(user_id=current_user.id, limit=limit)}


@app.get("/documents")
def list_documents(limit: int = 50, current_user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    return {"documents": graph.list_documents(user_id=current_user.id, limit=limit)}


@app.get("/uploads")
def list_uploads(
    purpose: str | None = None,
    limit: int = 50,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    return {"uploads": graph.list_uploaded_files(user_id=current_user.id, purpose=purpose, limit=limit)}


def require_admin_user(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if not graph.repository.is_admin_user(current_user.id):
        raise HTTPException(status_code=403, detail="Admin access is required.")
    return current_user


@app.get("/admin/eval-runs")
def list_eval_runs(limit: int = 50, current_user: CurrentUser = Depends(require_admin_user)) -> dict[str, Any]:
    return {"eval_runs": graph.list_eval_runs(limit=limit)}


@app.post("/admin/run-eval")
def run_eval(current_user: CurrentUser = Depends(require_admin_user)) -> dict[str, Any]:
    try:
        from eval.run_eval import run_eval as run_eval_report

        report = run_eval_report(
            Path("eval/golden_set/sample_opportunities.json"),
            output_path=Path("eval/latest_eval_report.json"),
            resume=True,
        )
        saved = graph.repository.save_eval_run(
            {
                "model_name": "mistral-extraction-eval",
                "extraction_accuracy": report["extraction_accuracy"],
                "hallucination_rate": report["hallucination_rate"],
                "notes": f"{report['case_count']} golden-set cases",
            }
        )
        return {"report": report, "saved_eval_run": saved}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/admin/source-flags")
def list_source_flags(limit: int = 100, current_user: CurrentUser = Depends(require_admin_user)) -> dict[str, Any]:
    return {"source_flags": graph.list_source_flags(limit=limit)}


@app.get("/admin/health")
def admin_health(current_user: CurrentUser = Depends(require_admin_user)) -> dict[str, Any]:
    return {"health": graph.repository.admin_health_summary(), "ocr": graph.ocr_diagnostics()}


@app.post("/admin/test-email")
def admin_test_email(current_user: CurrentUser = Depends(require_admin_user)) -> dict[str, Any]:
    try:
        response = EmailClient().send(
            to_email=current_user.email,
            subject="Compass email test",
            text="This is a test email from deployed Compass.",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}") from exc
    return {"sent": True, "response": response}


@app.get("/notifications/preferences")
def get_notification_preferences(current_user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    return {"preferences": graph.get_notification_preferences(current_user.id)}


@app.post("/notifications/preferences")
def update_notification_preferences(
    request: NotificationPreferencesRequest,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    preferences = graph.update_notification_preferences(
        user_id=current_user.id,
        email_enabled=request.email_enabled,
        notification_email=request.notification_email or current_user.email,
        reminder_days=request.reminder_days,
    )
    dispatch_due_reminders_once(background_tasks)
    return {
        "preferences": preferences
    }


@app.post("/upload/poster")
def upload_poster(
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    return graph.extract_poster(user_id=current_user.id, file_name=file.filename or "poster", file_obj=file.file)


@app.post("/upload/document")
def upload_document(
    purpose: str = Form(default="cv"),
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    return graph.upload_document(user_id=current_user.id, file_name=file.filename or "document", file_obj=file.file, purpose=purpose)
