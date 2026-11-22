"""FastAPI endpoints for rental agreement audits and awareness materials."""

from __future__ import annotations

from pathlib import Path
import base64
from io import BytesIO
import secrets
from typing import Any

import cv2
import numpy as np
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fpdf import FPDF
import qrcode
from PIL import Image, ImageDraw, ImageFont

from adapters.vernacular import explain_flagged_clauses
from core.extractor import extract_clauses as extract_metrics
from core.ocr import SAMPLE_PATH, OCRResult, extract_clauses, extract_clauses_from_image, extract_clauses_from_pdf_page
from core.rule_engine import evaluate_clauses


app = FastAPI(title="KararKavach API", version="1.0.0")
_AUDIO_FILES: dict[str, Path] = {}
_ROOT = Path(__file__).resolve().parents[1]
app.mount("/assets", StaticFiles(directory=_ROOT / "assets"), name="assets")
app.mount("/frontend", StaticFiles(directory=_ROOT / "frontend"), name="frontend")


@app.get("/", include_in_schema=False)
def frontend() -> FileResponse:
    """Serve the installable browser frontend."""
    return FileResponse(_ROOT / "frontend" / "index.html", media_type="text/html")


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    """Return no content for browsers requesting the default favicon."""
    return Response(status_code=204)


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    """Report that the API process is available to the browser frontend."""
    return {"status": "ok"}


@app.get("/sw.js", include_in_schema=False)
def service_worker() -> FileResponse:
    """Serve the PWA worker at the origin root so it can control the app."""
    return FileResponse(_ROOT / "frontend" / "sw.js", media_type="application/javascript",
                        headers={"Service-Worker-Allowed": "/"})


def _ocr_bytes(data: bytes, filename: str) -> list[OCRResult]:
    """Decode uploaded image/PDF bytes and OCR pages without saving uploads."""
    if filename.lower().endswith(".pdf") or data.startswith(b"%PDF"):
        try:
            import pymupdf as fitz
        except ImportError as exc:
            raise HTTPException(501, "PDF support requires PyMuPDF") from exc
        pages: list[OCRResult] = []
        try:
            document = fitz.open(stream=data, filetype="pdf")
            if document.page_count > 15:
                raise HTTPException(413, "PDFs are limited to 15 pages")
            for page_index, page in enumerate(document):
                ocr_page = extract_clauses_from_pdf_page(page)
                pixmap = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
                png = pixmap.tobytes("png")
                ocr_page.preview_data_url = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
                for clause in ocr_page.clauses:
                    clause.page = page_index + 1
                pages.append(ocr_page)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(400, f"Could not read PDF: {type(exc).__name__}") from exc
        if not pages:
            raise HTTPException(400, "PDF contains no readable pages")
        return pages
    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(400, "Upload must be a readable image or PDF")
    try:
        ocr_page = extract_clauses_from_image(image)
        mime = "image/png"
        encoded, extension = cv2.imencode(".png", image)
        if encoded:
            ocr_page.preview_data_url = f"data:{mime};base64," + base64.b64encode(encoded.tobytes()).decode("ascii")
        return [ocr_page]
    except Exception as exc:
        raise HTTPException(422, f"OCR failed: {type(exc).__name__}") from exc


def _run_pipeline(pages: list[OCRResult], lang: str) -> dict[str, Any]:
    extracted = []
    document_text = "\n".join(clause.text for page in pages for clause in page.clauses)
    global_number = 0
    for page_index, page in enumerate(pages, 1):
        for clause in page.clauses:
            global_number += 1
            clause.number = global_number
            metrics = extract_metrics(f"{global_number}. {clause.text}")
            if metrics:
                metrics[0].page = page_index
                metrics[0].bbox = clause.bbox
                extracted.extend(metrics)
    audit = evaluate_clauses(extracted, document_text=document_text)
    explanations = explain_flagged_clauses(audit, lang=lang)
    for item in explanations:
        path = item.pop("audio_path", None)
        if path:
            token = secrets.token_urlsafe(18)
            _AUDIO_FILES[token] = Path(path)
            item["audio_url"] = f"/api/v1/audio/{token}"
        else:
            item["audio_url"] = None
    return {
        "audit": audit.model_dump(),
        "explanations": explanations,
        "ocr": {"page_count": len(pages), "pages": [{"page": index, "width": p.width, "height": p.height, "fallback": p.fallback, "preview": p.preview_data_url,
                            "clauses": [{"number": c.number, "text": c.text, "page": index, "bbox": (index, *c.bbox)} for c in p.clauses]} for index, p in enumerate(pages, 1)]},
    }


@app.post("/api/v1/audit")
async def audit_upload(file: UploadFile = File(...), lang: str = Query("en", pattern="^(en|kn|hi)$")) -> dict[str, Any]:
    """Audit an uploaded image or PDF, keeping the upload in memory."""
    content = await file.read()
    if not content:
        raise HTTPException(400, "Uploaded file is empty")
    pages = _ocr_bytes(content, file.filename or "upload")
    return _run_pipeline(pages, lang)


@app.get("/api/v1/audit-sample")
def audit_sample(lang: str = Query("en", pattern="^(en|kn|hi)$")) -> dict[str, Any]:
    """Run an instant audit of the bundled rental agreement demo."""
    try:
        return _run_pipeline([extract_clauses(SAMPLE_PATH)], lang)
    except Exception as exc:
        raise HTTPException(500, f"Sample audit failed: {type(exc).__name__}") from exc


@app.get("/api/v1/audio/{token}")
def serve_audio(token: str, background_tasks: BackgroundTasks) -> FileResponse:
    """Serve and then remove a temporary vernacular MP3."""
    path = _AUDIO_FILES.pop(token, None)
    if path is None or not path.exists():
        raise HTTPException(404, "Audio not found or already served")
    background_tasks.add_task(path.unlink, missing_ok=True)
    return FileResponse(path, media_type="audio/mpeg", filename="explanation.mp3")


@app.get("/api/poster")
@app.get("/api/v1/poster")
def awareness_poster(request: Request, base_url: str | None = Query(None)) -> Response:
    """Create a downloadable A4 Kannada/English awareness poster."""
    # Use the address the visitor used to reach the app. A localhost fallback
    # makes the QR point back to the scanning phone instead of this server.
    public_base_url = (base_url or str(request.base_url)).rstrip("/")
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(public_base_url + "/api/v1/audit-sample")
    qr.make(fit=True)
    qr_image = qr.make_image(fill_color="black", back_color="white").get_image().convert("RGB")
    qr_buffer = BytesIO()
    qr_image.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)
    canvas = Image.new("RGB", (1240, 1754), "white")
    draw = ImageDraw.Draw(canvas)
    font_candidates = (
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    )
    font_path = next((path for path in font_candidates if path.exists()), None)
    if font_path is None:
        title_font = ImageFont.load_default()
        body_font = ImageFont.load_default()
    else:
        title_font = ImageFont.truetype(str(font_path), 52)
        body_font = ImageFont.truetype(str(font_path), 34)
    def centered(text: str, y: int, font: ImageFont.FreeTypeFont) -> None:
        box = draw.textbbox((0, 0), text, font=font)
        draw.text(((1240 - (box[2] - box[0])) / 2, y), text, fill="black", font=font)
    centered("CHECK YOUR RENTAL AGREEMENT", 120, title_font)
    centered("ಕರಾರು ಪತ್ರವನ್ನು ಪರಿಶೀಲಿಸಿ", 220, body_font)
    centered("Scan to learn about deposits, penalties and your rights.", 320, body_font)
    centered("ಠೇವಣಿ, ದಂಡ ಮತ್ತು ನಿಮ್ಮ ಹಕ್ಕುಗಳ ಬಗ್ಗೆ ತಿಳಿಯಲು ಸ್ಕ್ಯಾನ್ ಮಾಡಿ.", 380, body_font)
    centered("Private demo audit  •  ಪರಿಶೀಲನೆಗಾಗಿ ಮಾದರಿ", 1280, body_font)
    poster_buffer = BytesIO()
    canvas.save(poster_buffer, format="PNG")
    poster_buffer.seek(0)
    pdf = FPDF(format="A4")
    pdf.add_page()
    pdf.image(poster_buffer, x=0, y=0, w=210, h=297)
    pdf.image(qr_buffer, x=50.8, y=93.1, w=108.4, h=108.4)
    pdf_bytes = bytes(pdf.output())
    return Response(content=pdf_bytes, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=kararkavach-awareness-poster.pdf"})
