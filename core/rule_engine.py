"""YAML-driven deterministic tenancy rule evaluation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
import re
from pydantic import BaseModel, Field

from core.extractor import ExtractedClause


RULES_DIR = Path(__file__).resolve().parents[1] / "rules"
RULES_PATH = RULES_DIR / "tenancy_india.yaml"


class FiredRule(BaseModel):
    """A statutory risk rule triggered by a clause."""

    rule_id: str
    description: str
    severity: Literal["RED", "YELLOW", "GREEN"]
    penalty: int
    legal_reference: str | None = None


class ClauseAudit(BaseModel):
    """Audit result for one extracted agreement clause."""

    clause_number: int
    clause_text: str
    verdict: Literal["RED", "YELLOW", "GREEN"]
    score: int = Field(ge=0, le=100)
    fired_rules: list[FiredRule]
    page: int | None = None
    bbox: tuple[int, int, int, int] | None = None


class AuditResult(BaseModel):
    """Structured full agreement audit."""

    safety_score: int = Field(ge=0, le=100)
    verdict: Literal["RED", "YELLOW", "GREEN"]
    clauses: list[ClauseAudit]


def load_rules(path: Path | None = None) -> list[dict[str, Any]]:
    """Load and validate the configured deterministic rule definitions."""
    paths = [path] if path is not None else sorted(RULES_DIR.glob("*.yaml"))
    combined: list[dict[str, Any]] = []
    for rules_path in paths:
        with rules_path.open("r", encoding="utf-8") as rules_file:
            data = yaml.safe_load(rules_file)
        rules = data.get("rules") if isinstance(data, dict) else None
        if not isinstance(rules, list):
            raise ValueError(f"Rule YAML must contain a rules list: {rules_path}")
        for rule in rules:
            rule["_source"] = rules_path.stem
        combined.extend(rules)
    return combined


def _value(clause: ExtractedClause, field: str) -> Any:
    if field == "deposit_to_rent_ratio":
        return clause.deposit_to_rent_ratio
    return getattr(clause, field, None)


def _matches(rule: dict[str, Any], clause: ExtractedClause, document_text: str = "") -> bool:
    text = clause.text.lower()
    operator = rule["operator"]
    if operator == "education_loan_rule":
        kind = rule["condition"]
        amount_pattern = r"(?:₹|â‚¹|rs\.?\s*)\s*(\d[\d,]*(?:\.\d+)?)"
        contextual_amounts = re.findall(r"(?:education|student|sanctioned?)\s+(?:loan|amount)?[^\n.;]{0,45}?" + amount_pattern, document_text, re.I)
        amounts = contextual_amounts or re.findall(amount_pattern, document_text, re.I)
        loan_amount = float(amounts[0].replace(",", "")) if amounts and re.search(r"education|student|loan|sanction", document_text, re.I) else None
        if kind == "small_loan_collateral":
            return loan_amount is not None and loan_amount <= 750000 and bool(re.search(r"collateral|security|mortgage|pledge|charge on", text))
        if kind == "floating_foreclosure":
            return bool(re.search(r"floating", text)) and bool(re.search(r"prepayment|foreclos|pre-?pay", text)) and bool(re.search(r"charge|penalt|fee", text))
        if kind == "unilateral_interest_hike":
            return bool(re.search(r"interest rate|penal charge|penalty", text)) and bool(re.search(r"increase|enhance|revise|change|vary", text)) and bool(re.search(r"without.{0,35}(?:prior )?written notice|without notice", text))
        if kind == "blank_cheque":
            return bool(re.search(r"cheque|check", text)) and bool(re.search(r"blank|undated|signed in advance", text))
        if kind == "bundled_insurance":
            return bool(re.search(r"insurance", text)) and bool(re.search(r"mandatory|must purchase|shall purchase|compulsory", text)) and bool(re.search(r"bank.{0,35}(?:partner|affiliate|nominee|designated)|only from|exclusively", text))
        raise ValueError(f"Unsupported education loan condition: {kind}")
    value = _value(clause, rule["field"])
    if value is None:
        return False
    threshold = rule["threshold"]
    if operator == "greater_than":
        return value > threshold
    if operator == "greater_than_or_equal":
        return value >= threshold
    if operator == "contains_any":
        return any(str(term).lower() in " ".join(value).lower() for term in threshold)
    raise ValueError(f"Unsupported rule operator: {rule['operator']}")


def _document_rule_matches(rule: dict[str, Any], text: str) -> bool:
    """Evaluate deterministic whole-document validity conditions."""
    lowered = text.lower()
    operator = rule["operator"]
    if operator == "document_missing_any":
        return not any(str(marker).lower() in lowered for marker in rule["threshold"])
    if operator == "unregistered_long_lease":
        months = [float(value) for value in re.findall(r"\b(\d+(?:\.\d+)?)\s*months?\b", lowered)]
        years = [float(value) * 12 for value in re.findall(r"\b(\d+(?:\.\d+)?)\s*years?\b", lowered)]
        words = {"one": 12, "two": 24, "three": 36, "four": 48}
        word_years = [months_value for word, months_value in words.items()
                      if re.search(rf"\b{word}\s+years?\b", lowered)]
        tenure = months + years + word_years
        return bool(tenure) and max(tenure) >= float(rule["threshold"]) and not re.search(r"\b(register(?:ed|ation)?|sub[ -]?registrar)\b", lowered)
    raise ValueError(f"Unsupported document rule operator: {operator}")


def evaluate_clauses(clauses: list[ExtractedClause], rules_path: Path | None = None, document_text: str | None = None) -> AuditResult:
    """Apply YAML rules and calculate capped 0–100 clause and agreement scores."""
    rules = load_rules(rules_path)
    education_document = bool(re.search(r"education\s+loan|student\s+loan|education loan", document_text or "", re.I))
    if education_document:
        rules = [rule for rule in rules if rule.get("_source") != "tenancy_india"]
    audited: list[ClauseAudit] = []
    for clause in clauses:
        fired = [rule for rule in rules if rule["field"] != "document_text" and _matches(rule, clause, document_text or "")]
        penalty = sum(int(rule["penalty"]) for rule in fired)
        verdict: Literal["RED", "YELLOW", "GREEN"] = (
            "RED" if any(rule["severity"] == "RED" for rule in fired)
            else "YELLOW" if fired else "GREEN"
        )
        audited.append(ClauseAudit(
            clause_number=clause.number,
            clause_text=clause.text,
            page=clause.page,
            bbox=clause.bbox,
            verdict=verdict,
            score=max(0, 100 - penalty),
            fired_rules=[FiredRule(
                rule_id=rule["id"], description=rule["description"],
                severity=rule["severity"], penalty=int(rule["penalty"]),
                legal_reference=rule.get("legal_reference"),
            ) for rule in fired],
        ))
    if document_text is not None:
        document_rules = [rule for rule in rules if rule["field"] == "document_text"]
        document_fired = [rule for rule in document_rules if _document_rule_matches(rule, document_text)]
        if document_fired:
            penalty = sum(int(rule["penalty"]) for rule in document_fired)
            verdict: Literal["RED", "YELLOW", "GREEN"] = (
                "RED" if any(rule["severity"] == "RED" for rule in document_fired) else "YELLOW"
            )
            audited.append(ClauseAudit(
                clause_number=0, clause_text="Document validity checks", verdict=verdict,
                score=max(0, 100 - penalty), bbox=(0, 0, 1000, 100),
                fired_rules=[FiredRule(
                    rule_id=rule["id"], description=rule["description"], severity=rule["severity"],
                    penalty=int(rule["penalty"]), legal_reference=rule.get("legal_reference"),
                ) for rule in document_fired],
            ))
    overall_score = round(sum(item.score for item in audited) / len(audited)) if audited else 100
    overall_verdict: Literal["RED", "YELLOW", "GREEN"] = (
        "RED" if any(item.verdict == "RED" for item in audited)
        else "YELLOW" if any(item.verdict == "YELLOW" for item in audited)
        else "GREEN"
    )
    return AuditResult(safety_score=overall_score, verdict=overall_verdict, clauses=audited)


def evaluate_contract(text: str, rules_path: Path | None = None) -> AuditResult:
    """Extract and audit agreement text in one deterministic call."""
    from core.extractor import extract_clauses

    return evaluate_clauses(extract_clauses(text), rules_path, document_text=text)
