"""Deterministic text extraction and OCR metadata for claim evidence."""

from dataclasses import dataclass
from pathlib import Path

try:
    import pytesseract
    from PIL import Image
    from pytesseract import Output

    _OCR_AVAILABLE = True
except ImportError:
    _OCR_AVAILABLE = False


@dataclass(frozen=True)
class ExtractionResult:
    text: str | None
    status: str
    method: str
    engine: str
    engine_version: str
    confidence: float | None = None


def extract_document(storage_path: str, content_type: str) -> ExtractionResult:
    path = Path(storage_path)
    extension = path.suffix.lower()

    try:
        if extension == ".pdf":
            return _result(_extract_pdf_text(path), "text_layer", "pypdf", _pypdf_version())
        if extension == ".txt":
            text = path.read_text(encoding="utf-8", errors="ignore")
            return _result(text, "direct_text", "python", "3.11")
        if extension in {".png", ".jpg", ".jpeg", ".tiff"}:
            if not _OCR_AVAILABLE:
                return ExtractionResult(None, "unavailable", "ocr", "tesseract", "unavailable")
            return _extract_image(path)
    except Exception:
        return ExtractionResult(None, "failed", "unsupported", "unknown", "unknown")

    return ExtractionResult(None, "unsupported", "unsupported", "none", "none")


def extract_text(storage_path: str, content_type: str) -> str | None:
    """Compatibility wrapper for callers that only need extracted text."""
    return extract_document(storage_path, content_type).text


def _result(text: str | None, method: str, engine: str, version: str) -> ExtractionResult:
    sanitized = _sanitize_text(text)
    return ExtractionResult(
        text=sanitized,
        status="succeeded" if sanitized else "no_text",
        method=method,
        engine=engine,
        engine_version=version,
    )


def _sanitize_text(text: str | None) -> str | None:
    if text is None:
        return None
    sanitized = text.replace("\x00", "").strip()
    return sanitized or None


def _extract_pdf_text(path: Path) -> str | None:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages_text = [page.extract_text() or "" for page in reader.pages]
    text = "\n".join(pages_text).strip()
    return text or None


def _pypdf_version() -> str:
    try:
        from pypdf import __version__

        return __version__
    except ImportError:
        return "unavailable"


def _extract_image(path: Path) -> ExtractionResult:
    image = Image.open(path)
    data = pytesseract.image_to_data(image, output_type=Output.DICT)
    words: list[str] = []
    confidences: list[float] = []
    for word, raw_confidence in zip(data["text"], data["conf"], strict=True):
        word = word.strip()
        try:
            confidence = float(raw_confidence)
        except (TypeError, ValueError):
            continue
        if word and confidence >= 0:
            words.append(word)
            confidences.append(confidence / 100)
    text = _sanitize_text(" ".join(words))
    average_confidence = round(sum(confidences) / len(confidences), 4) if confidences else None
    return ExtractionResult(
        text=text,
        status="succeeded" if text else "no_text",
        method="ocr",
        engine="tesseract",
        engine_version=str(pytesseract.get_tesseract_version()),
        confidence=average_confidence,
    )


def is_ocr_available() -> bool:
    return _OCR_AVAILABLE
