from fastapi.testclient import TestClient
from fpdf import FPDF
from io import BytesIO

from app.main import app


client = TestClient(app)


def test_homepage_serves_frontend():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "KararKavach" in response.text


def test_sample_audit_returns_pipeline_result():
    response = client.get("/api/v1/audit-sample")
    assert response.status_code == 200
    payload = response.json()
    assert payload["audit"]["clauses"]
    assert payload["audit"]["verdict"] in {"RED", "YELLOW", "GREEN"}
    assert payload["explanations"]
    assert all(item["verdict"] in {"RED", "YELLOW"} for item in payload["explanations"])


def test_poster_is_a_downloadable_pdf():
    response = client.get("/api/v1/poster")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


def test_selectable_text_pdf_audit_does_not_require_tesseract():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, 8, "1. Monthly rent is Rs. 15000. Tenant must give 30 days notice.")
    content = bytes(pdf.output())
    response = client.post(
        "/api/v1/audit",
        files={"file": ("agreement.pdf", BytesIO(content), "application/pdf")},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["ocr"]["pages"][0]["clauses"]
    assert "15000" in payload["ocr"]["pages"][0]["clauses"][0]["text"]
    assert payload["ocr"]["pages"][0]["preview"].startswith("data:image/png;base64,")
    fired_ids = {rule["rule_id"] for clause in payload["audit"]["clauses"] for rule in clause["fired_rules"]}
    assert "MISSING_WITNESS_BLOCK" in fired_ids


def test_multi_page_pdf_returns_page_previews_and_page_aware_boxes():
    pdf = FPDF()
    pdf.set_font("Helvetica", size=12)
    for page_number in range(1, 3):
        pdf.add_page()
        pdf.multi_cell(0, 8, f"{page_number}. Education loan amount Rs. 500000. Provide collateral security.")
    content = bytes(pdf.output())
    response = client.post(
        "/api/v1/audit",
        files={"file": ("education-loan.pdf", BytesIO(content), "application/pdf")},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["ocr"]["page_count"] == 2
    assert [page["page"] for page in payload["ocr"]["pages"]] == [1, 2]
    assert all(page["preview"].startswith("data:image/png;base64,") for page in payload["ocr"]["pages"])
    second_page_clause = payload["ocr"]["pages"][1]["clauses"][0]
    assert len(second_page_clause["bbox"]) == 5
    assert second_page_clause["bbox"][0] == 2
    assert any(clause.get("page") == 2 for clause in payload["audit"]["clauses"])
