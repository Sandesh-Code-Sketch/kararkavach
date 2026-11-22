"""Deterministic rental agreement clause and metric extraction."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import spacy
from spacy.language import Language


@dataclass
class ExtractedClause:
    """A numbered clause with the metrics and risk phrases found in its text."""

    number: int
    text: str
    monthly_rent: float | None = None
    security_deposit: float | None = None
    lock_in_months: float | None = None
    forfeiture_percent: float | None = None
    painting_deduction_months: float | None = None
    risk_keywords: list[str] = field(default_factory=list)
    page: int | None = None
    bbox: tuple[int, int, int, int] | None = None

    @property
    def deposit_to_rent_ratio(self) -> float | None:
        """Return the deposit/rent ratio when both amounts are known."""
        if self.monthly_rent and self.security_deposit is not None:
            return self.security_deposit / self.monthly_rent
        return None


# Require at least one digit before accepting an OCR amount. A permissive
# comma-only match (for example, "₹,") reaches float conversion and crashes
# the entire uploaded-document review.
_AMOUNT = r"(?:₹|Rs\.?\s*)\s*(\d[\d,]*(?:\.\d+)?)"
_RISK_PATTERNS = [
    {"label": "RISK_UNANNOUNCED_ENTRY", "pattern": [{"LOWER": {"IN": ["without", "unannounced"]}}, {"LOWER": {"IN": ["prior", "notice", "announced"]}}]},
    {"label": "RISK_FORFEITURE", "pattern": [{"LOWER": {"IN": ["forfeit", "forfeiture"]}}]},
    {"label": "RISK_PAINTING", "pattern": [{"LOWER": {"IN": ["paint", "painting"]}}]},
]


def _make_ruler() -> Language:
    nlp = spacy.blank("en")
    ruler = nlp.add_pipe("entity_ruler", config={"phrase_matcher_attr": "LOWER"})
    ruler.add_patterns(_RISK_PATTERNS)
    return nlp


_RULER = _make_ruler()


def split_clauses(text: str) -> list[tuple[int, str]]:
    """Split text at numbered clause markers such as `1.` or `(2)`."""
    marker = re.compile(r"(?m)(?:^|\n|(?<=\s))(\d{1,3})[.)]\s*")
    matches = list(marker.finditer(text))
    if not matches:
        return [(1, text.strip())] if text.strip() else []
    clauses: list[tuple[int, str]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if body:
            clauses.append((int(match.group(1)), body))
    return clauses


def _amounts(text: str) -> list[float]:
    return [float(value.replace(",", "")) for value in re.findall(_AMOUNT, text, flags=re.IGNORECASE)]


def _extract_clause(number: int, text: str) -> ExtractedClause:
    clause = ExtractedClause(number=number, text=text)
    amounts = _amounts(text)
    rent_match = re.search(r"monthly\s+rent\s+(?:is|of|:)?\s*" + _AMOUNT, text, re.IGNORECASE)
    deposit_match = re.search(r"(?:security\s+)?deposit\s+(?:of|is|:)?\s*" + _AMOUNT, text, re.IGNORECASE)
    if rent_match:
        clause.monthly_rent = float(rent_match.group(1).replace(",", ""))
    if deposit_match:
        clause.security_deposit = float(deposit_match.group(1).replace(",", ""))
    # A simple fallback supports common rent/deposit clauses when OCR punctuation varies.
    if len(amounts) >= 2:
        lower = text.lower()
        if clause.monthly_rent is None and "rent" in lower:
            clause.monthly_rent = amounts[0]
        if clause.security_deposit is None and "deposit" in lower:
            clause.security_deposit = amounts[1] if clause.monthly_rent is not None else amounts[0]

    lock = re.search(r"(?:lock[\s-]*in|minimum\s+(?:term|period))[^.\n]{0,50}?(\d+(?:\.\d+)?)\s*(months?|mos?\b)", text, re.IGNORECASE)
    if not lock:
        lock = re.search(r"(\d+(?:\.\d+)?)\s*(months?|mos?\b)[^.\n]{0,30}(?:lock[\s-]*in|minimum\s+(?:term|period))", text, re.IGNORECASE)
    if lock:
        clause.lock_in_months = float(lock.group(1))

    percent_values = [float(value) for value in re.findall(r"(\d+(?:\.\d+)?)\s*%", text)]
    if re.search(r"forfeit|forfeiture|penalty", text, re.IGNORECASE):
        if percent_values:
            clause.forfeiture_percent = max(percent_values)
        elif re.search(r"(?:entire|full|whole|all)\s+(?:security\s+)?deposit", text, re.IGNORECASE):
            clause.forfeiture_percent = 100.0

    number = r"(\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten)"
    painting = re.search(r"painting[^.\n]{0,80}?" + number + r"\s*months?\s*(?:'s\s*)?rent", text, re.IGNORECASE)
    if painting:
        clause.painting_deduction_months = _number_value(painting.group(1))
    else:
        painting = re.search(number + r"\s*months?\s*(?:'s\s*)?rent[^.\n]{0,50}painting", text, re.IGNORECASE)
        if painting:
            clause.painting_deduction_months = _number_value(painting.group(1))

    doc = _RULER(text)
    clause.risk_keywords = sorted({entity.text.lower() for entity in doc.ents})
    # Preserve the exact rule trigger phrases for easy downstream inspection.
    for phrase in ("without prior notice", "without notice", "unannounced entry"):
        if phrase in text.lower() and phrase not in clause.risk_keywords:
            clause.risk_keywords.append(phrase)
    return clause


def _number_value(value: str) -> float:
    """Convert a numeric string or common small English number word."""
    words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
             "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
    return float(words[value.lower()]) if value.lower() in words else float(value)


def extract_clauses(text: str) -> list[ExtractedClause]:
    """Split agreement text and deterministically extract clause level fields."""
    return [_extract_clause(number, clause) for number, clause in split_clauses(text)]
