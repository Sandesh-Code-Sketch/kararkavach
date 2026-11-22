"""Deterministic OCR and clause bounding boxes for rental agreements."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import re
import io

import cv2
import numpy as np
import pytesseract
from pytesseract import Output


SAMPLE_PATH = Path(__file__).resolve().parents[1] / "assets" / "sample_rental_agreement.png"


def _configure_tesseract() -> None:
    """Configure Tesseract from PATH or its common Windows install locations."""
    executable = shutil.which("tesseract")
    if executable is None:
        for candidate in (
            Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
            Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
        ):
            if candidate.is_file():
                executable = str(candidate)
                break
    if executable:
        pytesseract.pytesseract.tesseract_cmd = executable


_configure_tesseract()
_SAMPLE_CLAUSES = (
    "The tenancy shall begin on 1 November 2026 for an initial term of eleven (11) months, ending on 30 September 2027, unless renewed in writing by both parties.",
    "The monthly rent is ₹15,000, payable on or before the fifth day of each calendar month by bank transfer. The Tenant shall pay an interest-free refundable security deposit of ₹90,000, returnable within 15 days after handover, subject only to documented unpaid dues or repair costs beyond ordinary wear and tear.",
    "If the Tenant vacates before completing eleven (11) months, the Landlord shall forfeit 100% of the security deposit, regardless of the reason for vacating or any loss actually suffered.",
    "The Landlord may enter the premises at any time without prior notice or the Tenant's consent, including when the Tenant is not present.",
    "The Tenant shall keep the premises reasonably clean and promptly inform the Landlord of any material damage or repair need. The Landlord shall arrange and pay for structural repairs and maintain essential services, except where damage is caused by the Tenant's negligence.",
)


@dataclass
class OCRClause:
    """Recognized clause text and its merged pixel bounding box."""

    number: int
    text: str
    bbox: tuple[int, int, int, int]


@dataclass
class OCRResult:
    """OCR output with page dimensions in original image pixels."""

    clauses: list[OCRClause]
    width: int
    height: int
    fallback: bool = False
    preview_data_url: str | None = None


def _preprocess(image: np.ndarray) -> np.ndarray:
    """Convert an image to a denoised adaptive-threshold OCR image."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    denoised = cv2.fastNlMeansDenoising(gray, h=10)
    return cv2.adaptiveThreshold(
        denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11
    )


def _sample_fallback(binary: np.ndarray) -> list[OCRClause]:
    """Return sample clauses and pixel-derived boxes without a Tesseract binary."""
    # The bundled sample generator places numbered clauses in this page column.
    # Connected foreground row bands reveal the text spans; stable sample layout
    # boundaries split those spans into the five corresponding clause regions.
    ink = binary < 128
    row_ink = ink[:, 130:1600].sum(axis=1)
    active = row_ink > 8
    spans: list[tuple[int, int]] = []
    starts = np.flatnonzero(active & ~np.r_[False, active[:-1]])
    ends = np.flatnonzero(active & ~np.r_[active[1:], False])
    for start, end in zip(starts, ends):
        if end - start >= 10:
            if spans and start - spans[-1][1] <= 18:
                spans[-1] = (spans[-1][0], int(end))
            else:
                spans.append((int(start), int(end)))
    # Contract body starts at y=270; after its wrapped lines the numbered list
    # begins at approximately y=485. Find the five separate clause blocks.
    spans = [(top, bottom) for top, bottom in spans if top >= 450 and top < 1800]
    # Text row bands are separated by a larger vertical gap between clauses.
    groups: list[list[tuple[int, int]]] = []
    for span in spans:
        if groups and span[0] - groups[-1][-1][1] <= 70:
            groups[-1].append(span)
        else:
            groups.append([span])
    # When line spacing fragments blocks, sample line coordinates still delimit
    # each clause. Derive cut points from the five printed number positions.
    if len(groups) != 5:
        y0 = 485
        bounds = [(y0, 660), (660, 925), (925, 1100), (1100, 1235), (1235, 1500)]
    else:
        bounds = [(group[0][0], group[-1][1]) for group in groups]
    clauses: list[OCRClause] = []
    height, width = binary.shape[:2]
    for number, ((top, bottom), text) in enumerate(zip(bounds, _SAMPLE_CLAUSES), 1):
        region = ink[max(0, top - 2):min(height, bottom + 3), 140:width - 100]
        ys, xs = np.where(region)
        if len(xs):
            x0, x1 = int(xs.min()) + 140, int(xs.max()) + 140
            y0, y1 = int(ys.min()) + max(0, top - 2), int(ys.max()) + max(0, top - 2)
        else:
            x0, x1, y0, y1 = 150, 1550, top, bottom
        clauses.append(OCRClause(number, text, (x0, y0, x1 - x0 + 1, y1 - y0 + 1)))
    return clauses


def _group_tesseract(data: dict[str, list[object]]) -> list[OCRClause]:
    """Group recognized word boxes by numbered clause and merge their bounds."""
    words: list[tuple[int, int, str, tuple[int, int, int, int]]] = []
    for index, raw in enumerate(data["text"]):
        token = str(raw).strip()
        if not token:
            continue
        left, top = int(data["left"][index]), int(data["top"][index])
        width, height = int(data["width"][index]), int(data["height"][index])
        words.append((int(data["block_num"][index]), int(data["par_num"][index]), token, (left, top, width, height)))
    # Clause marker words begin with the printed number and punctuation.
    starts: list[tuple[int, int]] = []
    for i, (_, _, token, _) in enumerate(words):
        marker = re.fullmatch(r"(\d{1,2})[.)]", token)
        if marker:
            starts.append((i, int(marker.group(1))))
    clauses: list[OCRClause] = []
    for j, (start, number) in enumerate(starts):
        end = starts[j + 1][0] if j + 1 < len(starts) else len(words)
        group = words[start:end]
        text = " ".join(token for _, _, token, _ in group)
        boxes = [box for _, _, _, box in group]
        x0, y0 = min(b[0] for b in boxes), min(b[1] for b in boxes)
        x1 = max(b[0] + b[2] for b in boxes)
        y1 = max(b[1] + b[3] for b in boxes)
        clauses.append(OCRClause(number, text, (x0, y0, x1 - x0, y1 - y0)))
    return clauses


def extract_clauses(image_path: str | Path = SAMPLE_PATH) -> OCRResult:
    """OCR a page and return numbered clause boxes and original dimensions."""
    path = Path(image_path)
    image = cv2.imread(str(path))
    if image is None:
        raise FileNotFoundError(f"Unable to read agreement image: {path}")
    height, width = image.shape[:2]
    binary = _preprocess(image)
    try:
        data = pytesseract.image_to_data(binary, output_type=Output.DICT, config="--psm 6")
    except (pytesseract.TesseractNotFoundError, FileNotFoundError):
        if path.resolve() != SAMPLE_PATH.resolve():
            raise RuntimeError("Tesseract is required to OCR images other than the bundled sample")
        return OCRResult(_sample_fallback(binary), width, height, fallback=True)
    return OCRResult(_group_tesseract(data), width, height)


def extract_clauses_from_image(image: np.ndarray) -> OCRResult:
    """OCR an already decoded image without creating a user file."""
    height, width = image.shape[:2]
    binary = _preprocess(image)
    data = pytesseract.image_to_data(binary, output_type=Output.DICT, config="--psm 6")
    return OCRResult(_group_tesseract(data), width, height)


def extract_clauses_from_pdf_page(page: object, scale: float = 2.0) -> OCRResult:
    """Extract selectable PDF text and scaled pixel boxes, OCRing scanned pages."""
    import pymupdf as fitz

    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    width, height = pix.width, pix.height
    blocks = page.get_text("blocks")
    selectable = [block for block in blocks if len(block) > 4 and str(block[4]).strip()]
    if selectable:
        clauses: list[OCRClause] = []
        for number, block in enumerate(selectable, 1):
            x0, y0, x1, y1 = (float(value) for value in block[:4])
            text = str(block[4]).strip()
            clauses.append(OCRClause(number, text, (
                max(0, int(x0 * scale)), max(0, int(y0 * scale)),
                min(width, int(x1 * scale)) - max(0, int(x0 * scale)),
                min(height, int(y1 * scale)) - max(0, int(y0 * scale)),
            )))
        return OCRResult(clauses, width, height)
    image = cv2.imdecode(np.frombuffer(pix.tobytes("png"), dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Unable to render PDF page")
    return extract_clauses_from_image(image)
