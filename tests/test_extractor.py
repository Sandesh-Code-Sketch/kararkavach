from core.extractor import extract_clauses, split_clauses


def test_extracts_fair_rent_and_deposit():
    clauses = extract_clauses("1. Monthly rent is ₹15,000. Refundable security deposit of ₹30,000.")
    clause = clauses[0]
    assert clause.monthly_rent == 15000
    assert clause.security_deposit == 30000
    assert clause.deposit_to_rent_ratio == 2


def test_extracts_predatory_metrics_and_risks():
    text = (
        "1. Monthly rent is ₹15,000 and security deposit of ₹90,000.\n"
        "2. Lock-in period is 11 months.\n"
        "3. Landlord will forfeit 100% of deposit.\n"
        "4. Landlord may enter without prior notice.\n"
        "5. Painting deduction shall be three months rent."
    )
    clauses = extract_clauses(text)
    assert len(clauses) == 5
    assert clauses[0].deposit_to_rent_ratio == 6
    assert clauses[1].lock_in_months == 11
    assert clauses[2].forfeiture_percent == 100
    assert "without prior notice" in clauses[3].risk_keywords
    assert clauses[4].painting_deduction_months == 3


def test_split_clauses_without_numbered_markers():
    assert split_clauses("Plain agreement text") == [(1, "Plain agreement text")]


def test_ignores_currency_symbol_followed_by_ocr_comma():
    clauses = extract_clauses("1. Monthly rent is ₹, and refundable deposit is ₹30,000.")
    assert clauses[0].monthly_rent is None
    assert clauses[0].security_deposit == 30000
