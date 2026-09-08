import pytest

from src.label_extractor import ExtractionError, extract_label, parse_extraction_response
from src.schemas import MassUnit


def test_parse_full_response():
    raw = {
        "product_name": "Test Bar",
        "serving": {"household_measure": "1 bar", "grams_per_serving": 35},
        "calories": 140,
        "added_sugar": {"value": 7, "unit": "g", "percent_daily_value": 14, "present_on_label": True},
        "sodium": {"value": 95, "unit": "mg", "percent_daily_value": 4, "present_on_label": True},
        "front_claims": [{"raw_text": "Good Source of Fiber"}],
        "field_confidence": {"added_sugar": 0.9, "sodium": 0.85},
    }
    label = parse_extraction_response(raw)
    assert label.product_name == "Test Bar"
    assert label.sodium.amount.unit == MassUnit.MILLIGRAM
    assert label.sodium.confidence == 0.85
    assert 0.87 < label.overall_confidence < 0.88


def test_parse_handles_missing_optional_sections():
    raw = {"serving": {"grams_per_serving": 40}}
    label = parse_extraction_response(raw)
    assert label.added_sugar.is_missing
    assert "added_sugar" in label.missing_fields


def test_extract_label_raises_clear_error_without_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ExtractionError, match="ANTHROPIC_API_KEY"):
        extract_label([(b"fake-bytes", "image/jpeg")])
