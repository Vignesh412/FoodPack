from src.product_lookup import OFFLookupResult, compute_delta_flags, lookup_barcode


def test_delta_flag_triggers_above_tolerance():
    historical = OFFLookupResult(found=True, per_100g={"added_sugar": 15.0, "sodium": 300.0})
    flags = compute_delta_flags({"added_sugar": 20.0, "sodium": 305.0}, historical)
    assert len(flags) == 1
    assert flags[0].nutrient == "added_sugar"


def test_no_flags_when_within_tolerance():
    historical = OFFLookupResult(found=True, per_100g={"added_sugar": 15.0})
    flags = compute_delta_flags({"added_sugar": 15.5}, historical)
    assert flags == []


def test_no_flags_when_historical_lookup_not_found():
    historical = OFFLookupResult(found=False, raw_error="not found")
    flags = compute_delta_flags({"added_sugar": 50.0}, historical)
    assert flags == []


def test_barcode_lookup_identifies_the_app_and_requests_only_needed_fields(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "status": 1,
                "product": {
                    "product_name": "Example product",
                    "nutriments": {"sodium_100g": 0.14},
                },
            }

    def fake_get(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr("src.product_lookup.requests.get", fake_get)
    result = lookup_barcode("0016000264694")

    assert result.found is True
    assert captured["headers"]["User-Agent"].startswith("FoodProofFit/")
    assert captured["params"] == {"fields": "product_name,nutriments"}
    assert result.per_100g["sodium"] == 140
