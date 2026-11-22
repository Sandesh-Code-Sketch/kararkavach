from core.extractor import extract_clauses
from core.rule_engine import evaluate_contract, evaluate_clauses


def test_fair_clause_is_green():
    result = evaluate_contract(
        "Agreement dated this 1st day of June 2026. Premises: Flat No 12, Example Apartment. "
        "1. Monthly rent is ₹15,000. Security deposit of ₹30,000, refundable. "
        "Signed by both parties in the presence of witness signatures."
    )
    assert result.safety_score == 100
    assert result.verdict == "GREEN"
    assert result.clauses[0].fired_rules == []


def test_predatory_clauses_trigger_expected_rules_and_score():
    text = (
        "1. Monthly rent is ₹15,000 and security deposit of ₹90,000.\n"
        "2. Lock-in period is 11 months.\n"
        "3. Landlord will forfeit 100% of deposit.\n"
        "4. Landlord may enter without prior notice.\n"
        "5. Painting deduction shall be three months rent.\n"
        "Premises: Flat No 4, Example Building. Dated this 1st day of June 2026. Witness signatures follow."
    )
    result = evaluate_contract(text)
    fired_ids = {rule.rule_id for clause in result.clauses for rule in clause.fired_rules}
    assert fired_ids == {
        "TENANCY_DEPOSIT_CAP", "EXCESSIVE_LOCKIN", "FORFEITURE_PENALTY",
        "UNANNOUNCED_ENTRY", "ARBITRARY_PAINTING_DEDUCTION",
    }
    assert result.verdict == "RED"
    assert result.safety_score == 82
    assert result.clauses[0].score == 70


def test_validity_checks_pass_for_complete_agreement():
    text = (
        "Dated this 1st day of June 2026. Effective date is June 1, 2026. "
        "Schedule A: Flat No 12, Example Apartment, situated at Main Road. "
        "Tenure is 11 months. Signed in the presence of witnesses."
    )
    result = evaluate_contract(text)
    fired_ids = {rule.rule_id for clause in result.clauses for rule in clause.fired_rules}
    assert not fired_ids.intersection({
        "MISSING_WITNESS_BLOCK", "MISSING_PROPERTY_ADDRESS",
        "UNREGISTERED_LONG_LEASE", "MISSING_EXECUTION_DATE",
    })


def test_sham_incomplete_agreement_flags_missing_validity_markers():
    result = evaluate_contract("Rental term is 2 years. Rent is payable monthly.")
    findings = [clause for clause in result.clauses if clause.clause_number == 0]
    fired_ids = {rule.rule_id for clause in findings for rule in clause.fired_rules}
    assert fired_ids == {
        "MISSING_WITNESS_BLOCK", "MISSING_PROPERTY_ADDRESS",
        "UNREGISTERED_LONG_LEASE", "MISSING_EXECUTION_DATE",
    }
    assert findings[0].bbox == (0, 0, 1000, 100)
    assert result.safety_score < 100
    assert result.verdict == "RED"


def test_boundary_values_do_not_trigger_strict_thresholds():
    clauses = extract_clauses(
        "1. Monthly rent ₹10,000 and security deposit ₹20,000. Lock-in period 6 months."
    )
    result = evaluate_clauses(clauses)
    assert result.verdict == "GREEN"


def test_small_student_education_loan_collateral_trap_is_red():
    result = evaluate_contract(
        "1. Education loan amount is Rs. 7,50,000. The student must provide collateral security over property."
    )
    rule_ids = {rule.rule_id for clause in result.clauses for rule in clause.fired_rules}
    assert "ILLEGAL_COLLATERAL_SMALL_LOAN" in rule_ids
    finding = next(clause for clause in result.clauses if clause.fired_rules)
    assert finding.verdict == "RED"
