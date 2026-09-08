"""
Seed data for the three demonstration scenarios named in the roadmap
(Serving Size Surprise, Fair Comparison, Responsible Refusal). Used when
no ANTHROPIC_API_KEY is configured, so the rest of the pipeline —
calculation, retrieval, claims, comparison, safety — can be demoed and
rehearsed without spending an API call or needing real label photos yet.
Real photographed data should replace this before the golden-set evals
run for real (Step 10); this module exists to unblock everything
downstream of vision extraction while photos are still being collected.
"""

from __future__ import annotations

from src.schemas import (
    AllergenInfo,
    ExtractedLabel,
    FrontOfPackClaim,
    MassAmount,
    MassUnit,
    NutrientField,
    NutritionGoal,
    ServingInfo,
)


def snack_bar_scenario_1() -> ExtractedLabel:
    """Scenario 1: Serving Size Surprise. Labelled serving looks modest;
    the demo shows how eating two servings changes the picture."""
    return ExtractedLabel(
        product_name="Crunchy Grain Bar (sample)",
        serving=ServingInfo(household_measure="1 bar", grams_per_serving=35, servings_per_container=6, net_weight_grams=210),
        calories=140,
        added_sugar=NutrientField(amount=MassAmount(value=7, unit=MassUnit.GRAM), percent_daily_value=14, confidence=1.0),
        sodium=NutrientField(amount=MassAmount(value=95, unit=MassUnit.MILLIGRAM), percent_daily_value=4, confidence=1.0),
        saturated_fat=NutrientField(amount=MassAmount(value=1, unit=MassUnit.GRAM), percent_daily_value=5, confidence=1.0),
        fibre=NutrientField(amount=MassAmount(value=3, unit=MassUnit.GRAM), percent_daily_value=11, confidence=1.0),
        protein=NutrientField(amount=MassAmount(value=4, unit=MassUnit.GRAM), percent_daily_value=None, confidence=1.0),
        allergens=AllergenInfo(
            declared_contains=["tree nuts"],
            may_contain_statement=["may contain peanuts"],
            raw_ingredient_text="Whole grain oats, honey, almonds, sea salt, natural flavor.",
        ),
        front_claims=[FrontOfPackClaim(raw_text="Good Source of Fiber")],
    )


def cereal_a_scenario_2() -> ExtractedLabel:
    """Scenario 2: Fair Comparison, product A — smaller labelled serving."""
    return ExtractedLabel(
        product_name="Golden Flakes Cereal (sample)",
        serving=ServingInfo(household_measure="3/4 cup", grams_per_serving=30, net_weight_grams=340),
        calories=110,
        added_sugar=NutrientField(amount=MassAmount(value=9, unit=MassUnit.GRAM), percent_daily_value=18, confidence=1.0),
        sodium=NutrientField(amount=MassAmount(value=160, unit=MassUnit.MILLIGRAM), percent_daily_value=7, confidence=1.0),
        saturated_fat=NutrientField(amount=MassAmount(value=0, unit=MassUnit.GRAM), percent_daily_value=0, confidence=1.0),
        fibre=NutrientField(amount=MassAmount(value=1, unit=MassUnit.GRAM), percent_daily_value=4, confidence=1.0),
        protein=NutrientField(amount=MassAmount(value=2, unit=MassUnit.GRAM), percent_daily_value=None, confidence=1.0),
        front_claims=[FrontOfPackClaim(raw_text="Low Fat")],
    )


def cereal_b_scenario_2() -> ExtractedLabel:
    """Scenario 2: Fair Comparison, product B — larger labelled serving,
    which makes it look better per-serving even though it isn't per 100g."""
    return ExtractedLabel(
        product_name="Morning Crunch Cereal (sample)",
        serving=ServingInfo(household_measure="1 cup", grams_per_serving=55, net_weight_grams=425),
        calories=150,
        added_sugar=NutrientField(amount=MassAmount(value=10, unit=MassUnit.GRAM), percent_daily_value=20, confidence=1.0),
        sodium=NutrientField(amount=MassAmount(value=190, unit=MassUnit.MILLIGRAM), percent_daily_value=8, confidence=1.0),
        saturated_fat=NutrientField(amount=MassAmount(value=0, unit=MassUnit.GRAM), percent_daily_value=0, confidence=1.0),
        fibre=NutrientField(amount=MassAmount(value=2, unit=MassUnit.GRAM), percent_daily_value=7, confidence=1.0),
        protein=NutrientField(amount=MassAmount(value=3, unit=MassUnit.GRAM), percent_daily_value=None, confidence=1.0),
        front_claims=[FrontOfPackClaim(raw_text="Good Source of Fiber")],
    )


def cropped_scenario_3() -> ExtractedLabel:
    """Scenario 3: Responsible Refusal. Deliberately missing critical
    fields, as if the Nutrition Facts photo was cropped or unreadable."""
    return ExtractedLabel(
        product_name=None,
        serving=ServingInfo(),
        calories=None,
        sodium=NutrientField(present_on_label=False),
        added_sugar=NutrientField(present_on_label=False),
        saturated_fat=NutrientField(present_on_label=False),
        fibre=NutrientField(present_on_label=False),
        protein=NutrientField(present_on_label=False),
    )


SCENARIOS = {
    "Scenario 1 — Serving Size Surprise (snack bar)": snack_bar_scenario_1,
    "Scenario 2a — Fair Comparison: Golden Flakes": cereal_a_scenario_2,
    "Scenario 2b — Fair Comparison: Morning Crunch": cereal_b_scenario_2,
    "Scenario 3 — Responsible Refusal (cropped photo)": cropped_scenario_3,
}

DEFAULT_GOAL = NutritionGoal.GENERAL_UNDERSTANDING.value
