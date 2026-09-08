"""
Step 6: deterministic calculations.

Every number here comes from ordinary Python arithmetic on values the user
has already confirmed — no model call happens in this module. That is a
deliberate design boundary, not an implementation detail: judgment calls
(is this label readable? is this question safe to answer?) go through the
LLM; arithmetic on confirmed numbers never does.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from src.schemas import DVLevel, ExtractedLabel, MassAmount, MassUnit, NutrientField, PortionSelection

CRITICAL_NUTRIENTS = ("added_sugar", "sodium", "saturated_fat", "fibre", "protein")

# FDA consumer guide: 5% DV or less is low, 20% DV or more is high.
LOW_DV_THRESHOLD = 5.0
HIGH_DV_THRESHOLD = 20.0


def dv_level(percent_daily_value: Optional[float]) -> DVLevel:
    if percent_daily_value is None:
        return DVLevel.UNKNOWN
    if percent_daily_value <= LOW_DV_THRESHOLD:
        return DVLevel.LOW
    if percent_daily_value >= HIGH_DV_THRESHOLD:
        return DVLevel.HIGH
    return DVLevel.MODERATE


class NutrientResult(BaseModel):
    nutrient: str
    per_serving: Optional[MassAmount] = None
    per_serving_dv: Optional[float] = None
    per_serving_dv_level: DVLevel = DVLevel.UNKNOWN

    per_actual_portion: Optional[MassAmount] = None
    per_actual_portion_dv: Optional[float] = None
    per_actual_portion_dv_level: DVLevel = DVLevel.UNKNOWN

    per_100g: Optional[MassAmount] = None
    per_100g_unavailable_reason: Optional[str] = None


class PortionCalculation(BaseModel):
    servings_consumed: float
    results: dict[str, NutrientResult] = Field(default_factory=dict)
    calories_per_serving: Optional[float] = None
    calories_per_actual_portion: Optional[float] = None


def _scale(amount: MassAmount, factor: float) -> MassAmount:
    return MassAmount(value=round(amount.value * factor, 3), unit=amount.unit)


def _scale_dv(dv: Optional[float], factor: float) -> Optional[float]:
    if dv is None:
        return None
    return round(dv * factor, 1)


def calculate_nutrient(
    field: NutrientField,
    servings_consumed: float,
    grams_per_serving: Optional[float],
) -> NutrientResult:
    result = NutrientResult(nutrient="")

    if field.amount is not None:
        result.per_serving = field.amount
        result.per_serving_dv = field.percent_daily_value
        result.per_serving_dv_level = dv_level(field.percent_daily_value)

        result.per_actual_portion = _scale(field.amount, servings_consumed)
        result.per_actual_portion_dv = _scale_dv(field.percent_daily_value, servings_consumed)
        result.per_actual_portion_dv_level = dv_level(result.per_actual_portion_dv)

        if grams_per_serving and grams_per_serving > 0:
            grams_amount = field.amount.to_grams()
            per_gram = grams_amount / grams_per_serving
            per_100g_value = per_gram * 100
            # Report back in the original unit's scale for readability.
            if field.amount.unit == MassUnit.MILLIGRAM:
                result.per_100g = MassAmount(value=round(per_100g_value * 1000, 2), unit=MassUnit.MILLIGRAM)
            elif field.amount.unit == MassUnit.MICROGRAM:
                result.per_100g = MassAmount(value=round(per_100g_value * 1_000_000, 2), unit=MassUnit.MICROGRAM)
            else:
                result.per_100g = MassAmount(value=round(per_100g_value, 3), unit=MassUnit.GRAM)
        else:
            result.per_100g_unavailable_reason = (
                "Grams per serving is missing from the confirmed label, so a per-100g "
                "figure would be a guess rather than a calculation. Provide the net "
                "weight or household measure to unlock this comparison."
            )
    else:
        result.per_100g_unavailable_reason = "Nutrient value was not present on the label."

    return result


def calculate_portion(label: ExtractedLabel, portion: PortionSelection) -> PortionCalculation:
    """Recompute every critical nutrient for the user's actual eaten portion."""
    grams_per_serving = label.serving.grams_per_serving
    calc = PortionCalculation(servings_consumed=portion.servings_consumed)

    for name in CRITICAL_NUTRIENTS:
        field: NutrientField = getattr(label, name)
        result = calculate_nutrient(field, portion.servings_consumed, grams_per_serving)
        result.nutrient = name
        calc.results[name] = result

    if label.calories is not None:
        calc.calories_per_serving = label.calories
        calc.calories_per_actual_portion = round(label.calories * portion.servings_consumed, 1)

    return calc
