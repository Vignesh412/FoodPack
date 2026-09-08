from src.schemas import ExtractedLabel, MassAmount, MassUnit, NutrientField, ServingInfo


def test_missing_fields_computed_from_nutrient_state():
    label = ExtractedLabel(
        serving=ServingInfo(grams_per_serving=40),
        sodium=NutrientField(amount=MassAmount(value=100, unit=MassUnit.MILLIGRAM), percent_daily_value=4),
    )
    assert "sodium" not in label.missing_fields
    assert "added_sugar" in label.missing_fields
    assert "protein" in label.missing_fields


def test_missing_grams_per_serving_is_flagged():
    label = ExtractedLabel()
    assert "serving.grams_per_serving" in label.missing_fields


def test_mass_amount_rejects_negative_value():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        MassAmount(value=-5, unit=MassUnit.GRAM)


def test_mass_amount_unit_conversion():
    mg = MassAmount(value=1500, unit=MassUnit.MILLIGRAM)
    assert mg.to_grams() == 1.5
