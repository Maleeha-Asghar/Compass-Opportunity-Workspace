from pathlib import Path


class PDFParser:
    def extract_pdf_text(self, pdf_path: str | Path) -> dict:
        try:
            import fitz
        except ImportError as exc:
            raise RuntimeError("PyMuPDF is required for PDF parsing. Install requirements.txt.") from exc

        doc = fitz.open(str(pdf_path))
        pages_text: list[str] = []
        needs_ocr = False
        for page in doc:
            text = page.get_text()
            if len(text.strip()) < 20:
                needs_ocr = True
            pages_text.append(text)
        return {"text": "\n".join(pages_text), "needs_ocr": needs_ocr}
