from pathlib import Path
import shutil

from app.config import Settings, get_settings


class OCRTool:
    COMMON_WINDOWS_PATHS = (
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    )

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def ocr_pdf(self, pdf_path: str | Path) -> str:
        try:
            import fitz
            import pytesseract
            from PIL import Image
            import io
        except ImportError as exc:
            raise RuntimeError("PyMuPDF, Pillow, and pytesseract are required for OCR.") from exc

        pytesseract.pytesseract.tesseract_cmd = self._resolve_tesseract_cmd()

        doc = fitz.open(str(pdf_path))
        chunks: list[str] = []
        for page in doc:
            pix = page.get_pixmap(dpi=200)
            image = Image.open(io.BytesIO(pix.tobytes("png")))
            chunks.append(pytesseract.image_to_string(image))
        return "\n".join(chunks)

    def _resolve_tesseract_cmd(self) -> str:
        configured = self.settings.tesseract_cmd
        if configured and Path(configured).exists():
            return configured

        discovered = shutil.which("tesseract")
        if discovered:
            return discovered

        for candidate in self.COMMON_WINDOWS_PATHS:
            if Path(candidate).exists():
                return candidate

        raise RuntimeError(
            "Tesseract OCR is installed but tesseract.exe was not found. "
            "Set TESSERACT_CMD in .env, for example: "
            r"TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe"
        )

    def diagnostics(self) -> dict[str, str]:
        command = self._resolve_tesseract_cmd()
        return {"tesseract_cmd": command, "status": "available"}
