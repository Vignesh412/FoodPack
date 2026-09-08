from src.product_lookup import OFFLookupResult, compute_delta_flags


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
