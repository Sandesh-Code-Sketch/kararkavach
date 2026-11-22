from core.ocr import extract_clauses


def test_sample_image_returns_five_clauses_with_valid_pixel_boxes():
    result = extract_clauses("assets/sample_rental_agreement.png")
    assert len(result.clauses) == 5
    assert (result.width, result.height) == (1700, 2400)
    for clause in result.clauses:
        x, y, width, height = clause.bbox
        assert clause.number in range(1, 6)
        assert clause.text.strip()
        assert width > 0 and height > 0
        assert 0 <= x < result.width
        assert 0 <= y < result.height
        assert x + width <= result.width
        assert y + height <= result.height
