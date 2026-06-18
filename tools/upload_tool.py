import mimetypes
import tempfile
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from app.config import Settings, get_settings
from tools.ocr_tool import OCRTool
from tools.pdf_parser_tool import PDFParser
from tools.supabase_tool import SupabaseRepository


class UploadService:
    IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp"}
    DOCUMENT_TYPES = {"application/pdf", "text/plain"}

    def __init__(
        self,
        repository: SupabaseRepository | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.repository = repository or SupabaseRepository(self.settings)
        self.pdf_parser = PDFParser()
        self.ocr_tool = OCRTool()

    def save_upload(self, user_id: str, file_name: str, file_obj: BinaryIO, bucket: str) -> dict:
        content = file_obj.read()
        if len(content) > self.settings.max_upload_bytes:
            raise ValueError("Upload exceeds max_upload_bytes.")
        mime_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"
        object_path = f"{user_id}/{uuid4()}-{Path(file_name).name}"
        self.repository.upload_file(bucket, object_path, content, mime_type)
        return {
            "bucket": bucket,
            "path": object_path,
            "mime_type": mime_type,
            "size_bytes": len(content),
        }

    def persist_temp_file(self, file_name: str, file_obj: BinaryIO) -> tuple[Path, str]:
        content = file_obj.read()
        if len(content) > self.settings.max_upload_bytes:
            raise ValueError("Upload exceeds max_upload_bytes.")
        mime_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"
        suffix = Path(file_name).suffix
        handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        try:
            handle.write(content)
            return Path(handle.name), mime_type
        finally:
            handle.close()

    def extract_document_text(self, file_path: str | Path, mime_type: str) -> dict:
        path = Path(file_path)
        if mime_type == "text/plain":
            return {"text": path.read_text(encoding="utf-8"), "needs_ocr": False}
        if mime_type != "application/pdf":
            raise ValueError(f"Unsupported document type: {mime_type}")
        parsed = self.pdf_parser.extract_pdf_text(path)
        if parsed["needs_ocr"]:
            parsed["ocr_text"] = self.ocr_tool.ocr_pdf(path)
        return parsed
