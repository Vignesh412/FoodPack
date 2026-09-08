from src.comparison import compare_products
from src.schemas import ExtractedLabel, MassAmount, MassUnit, NutrientField, PortionSelection, ServingInfo


def test_per_100g_refused_when_weight_missing():
    a = ExtractedLabel(serving=ServingInfo(grams_per_serving=40))
    b = ExtractedLabel(serving=ServingInfo())  # no weight
    result = compare_products(a, PortionSelection(), "A", b, PortionSelection(), "B")
    assert result.per_100g_available is False
    assert "B" in result.per_100g_unavailable_reason


def test_per_100g_available_when_both_have_weight():
    a = ExtractedLabel(serving=ServingInfo(grams_per_serving=40))
    b = ExtractedLabel(serving=ServingInfo(grams_per_serving=55))
    result = compare_products(a, PortionSelection(), "A", b, PortionSelection(), "B")
    assert result.per_100g_available is True


def test_comparison_normalizes_different_serving_sizes():
    # Same per-serving sugar, but very different serving sizes -> different per-100g picture.
    a = ExtractedLabel(
        serving=ServingInfo(grams_per_serving=30),
        added_sugar=NutrientField(amount=MassAmount(value=9, unit=MassUnit.GRAM), percent_daily_value=18),
    )
    b = ExtractedLabel(
        serving=ServingInfo(grams_per_serving=60),
        added_sugar=NutrientField(amount=MassAmount(value=9, unit=MassUnit.GRAM), percent_daily_value=18),
    )
    result = compare_products(a, PortionSelection(), "A", b, PortionSelection(), "B")
    sugar_comp = next(nc for nc in result.nutrient_comparisons if nc.nutrient == "added_sugar")
    assert result.product_a.calculation.results["added_sugar"].per_100g.value == 30.0
    assert result.product_b.calculation.results["added_sugar"].per_100g.value == 15.0
    assert "A: 30" in sugar_comp.per_100g_note
    assert "B: 15" in sugar_comp.per_100g_note
