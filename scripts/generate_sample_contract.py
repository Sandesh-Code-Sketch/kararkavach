"""Generate a realistic sample Indian residential rental agreement image."""

from pathlib import Path
from typing import Final

from PIL import Image, ImageDraw, ImageFont


ROOT: Final[Path] = Path(__file__).resolve().parents[1]
OUTPUT: Final[Path] = ROOT / "assets" / "sample_rental_agreement.png"
PAGE_SIZE: Final[tuple[int, int]] = (1700, 2400)


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a common system font, falling back to Pillow's built-in font."""
    candidates = (
        ["arialbd.ttf", "DejaVuSans-Bold.ttf"]
        if bold
        else ["arial.ttf", "DejaVuSans.ttf"]
    )
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, width: int) -> list[str]:
    """Wrap text to a measured pixel width."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        proposed = f"{current} {word}".strip()
        if current and draw.textlength(proposed, font=font) > width:
            lines.append(current)
            current = word
        else:
            current = proposed
    if current:
        lines.append(current)
    return lines


def generate_contract(output: Path = OUTPUT) -> Path:
    """Create a high-resolution PNG of a five-clause residential rent agreement."""
    image = Image.new("RGB", PAGE_SIZE, "#fdfcf8")
    draw = ImageDraw.Draw(image)
    margin = 150
    ink = "#202326"
    muted = "#62696f"
    accent = "#263f57"

    # Thin inset border and a restrained document header make the page look printed.
    draw.rectangle((58, 58, PAGE_SIZE[0] - 58, PAGE_SIZE[1] - 58), outline="#b8b4a9", width=2)
    title_font = _font(46, bold=True)
    subtitle_font = _font(24)
    section_font = _font(25, bold=True)
    body_font = _font(27)
    small_font = _font(20)
    center_x = PAGE_SIZE[0] // 2

    draw.text((center_x, 125), "RESIDENTIAL RENTAL AGREEMENT", font=title_font, fill=accent, anchor="mm")
    draw.text((center_x, 183), "(Leave and License for Residential Premises)", font=subtitle_font, fill=muted, anchor="mm")
    draw.line((margin, 225, PAGE_SIZE[0] - margin, 225), fill="#8c969e", width=2)

    y = 270
    intro = (
        "This Agreement is made on 1 November 2026 at Bengaluru, Karnataka, between "
        "Ananya Rao (""Landlord""), residing at 14 Lake View Road, Bengaluru, and "
        "Rohan Mehta (""Tenant""), residing at 8 Green Park, Bengaluru. The Landlord "
        "agrees to let and the Tenant agrees to occupy the residential premises at "
        "Flat 3B, Cedar Residency, Indiranagar, Bengaluru, subject to the following terms."
    )
    for line in _wrap_text(draw, intro, body_font, PAGE_SIZE[0] - 2 * margin):
        draw.text((margin, y), line, font=body_font, fill=ink)
        y += 43

    y += 28
    clauses = [
        "The tenancy shall begin on 1 November 2026 for an initial term of eleven (11) months, ending on 30 September 2027, unless renewed in writing by both parties.",
        "The monthly rent is ₹15,000, payable on or before the fifth day of each calendar month by bank transfer. The Tenant shall pay an interest-free refundable security deposit of ₹90,000, returnable within 15 days after handover, subject only to documented unpaid dues or repair costs beyond ordinary wear and tear.",
        "If the Tenant vacates before completing eleven (11) months, the Landlord shall forfeit 100% of the security deposit, regardless of the reason for vacating or any loss actually suffered.",
        "The Landlord may enter the premises at any time without prior notice or the Tenant's consent, including when the Tenant is not present.",
        "The Tenant shall keep the premises reasonably clean and promptly inform the Landlord of any material damage or repair need. The Landlord shall arrange and pay for structural repairs and maintain essential services, except where damage is caused by the Tenant's negligence.",
    ]
    for index, clause in enumerate(clauses, start=1):
        draw.text((margin, y), f"{index}.", font=section_font, fill=accent)
        lines = _wrap_text(draw, clause, body_font, PAGE_SIZE[0] - 2 * margin - 65)
        for line in lines:
            draw.text((margin + 58, y), line, font=body_font, fill=ink)
            y += 44
        y += 32

    y += 8
    draw.text((margin, y), "SIGNED by the parties on the date stated above.", font=section_font, fill=accent)
    y += 100
    sign_width = 500
    draw.line((margin, y, margin + sign_width, y), fill="#555b60", width=2)
    draw.line((PAGE_SIZE[0] - margin - sign_width, y, PAGE_SIZE[0] - margin, y), fill="#555b60", width=2)
    y += 16
    draw.text((margin, y), "Ananya Rao  |  Landlord", font=small_font, fill=muted)
    draw.text((PAGE_SIZE[0] - margin - sign_width, y), "Rohan Mehta  |  Tenant", font=small_font, fill=muted)
    y += 85
    draw.line((margin, y, margin + 300, y), fill="#a0a3a3", width=1)
    draw.line((PAGE_SIZE[0] - margin - 300, y, PAGE_SIZE[0] - margin, y), fill="#a0a3a3", width=1)
    y += 10
    draw.text((margin, y), "Witness 1", font=small_font, fill=muted)
    draw.text((PAGE_SIZE[0] - margin - 300, y), "Witness 2", font=small_font, fill=muted)

    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, format="PNG", dpi=(300, 300), optimize=True)
    return output


if __name__ == "__main__":
    print(generate_contract())
