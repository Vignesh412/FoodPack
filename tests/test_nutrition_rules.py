from src.nutrition_rules import calculate_portion, dv_level
from src.schemas import DVLevel, ExtractedLabel, MassAmount, MassUnit, NutrientField, PortionSelection, ServingInfo


def _label():
    return ExtractedLabel(
        serving=ServingInfo(grams_per_serving=40),
        calories=180,
        added_sugar=NutrientField(amount=MassAmount(value=8, unit=MassUnit.GRAM), percent_daily_value=16),
        sodium=NutrientField(amount=MassAmount(value=150, unit=MassUnit.MILLIGRAM), percent_daily_value=6),
    )


def test_dv_level_thresholds():
    assert dv_level(5) == DVLevel.LOW
    assert dv_level(4.9) == DVLevel.LOW
    assert dv_level(20) == DVLevel.HIGH
    assert dv_level(19.9) == DVLevel.MODERATE
    assert dv_level(None) == DVLevel.UNKNOWN


def test_portion_scaling_is_linear():
    calc = calculate_portion(_label(), PortionSelection(servings_consumed=2))
    assert calc.calories_per_actual_portion == 360.0
    sugar = calc.results["added_sugar"]
    assert sugar.per_actual_portion.value == 16.0
    assert sugar.per_actual_portion_dv == 32.0
    assert sugar.per_actual_portion_dv_level == DVLevel.HIGH


def test_per_100g_requires_grams_per_serving():
    label = _label()
    label.serving.grams_per_serving = None
    calc = calculate_portion(label, PortionSelection(servings_consumed=1))
    sugar = calc.results["added_sugar"]
    assert sugar.per_100g is None
    assert sugar.per_100g_unavailable_reason is not None


def test_per_100g_conversion_is_correct():
    calc = calculate_portion(_label(), PortionSelection(servings_consumed=1))
    sugar = calc.results["added_sugar"]
    # 8g per 40g serving -> 20g per 100g
    assert sugar.per_100g.value == 20.0


def test_missing_nutrient_reports_reason_not_a_crash():
    label = _label()
    calc = calculate_portion(label, PortionSelection(servings_consumed=1))
    fibre = calc.results["fibre"]
    assert fibre.per_serving is None
    assert fibre.per_100g_unavailable_reason == "Nutrient value was not present on the label."
