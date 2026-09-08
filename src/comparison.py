"""
Step 6 (Fair Product Comparison): compares two products per labelled
serving, per actual user portion, and per 100 grams — refusing the
per-100g view rather than faking it when weight data is missing.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from src.nutrition_rules import CRITICAL_NUTRIENTS, PortionCalculation, calculate_portion
from src.schemas import ExtractedLabel, PortionSelection


class ProductSide(BaseModel):
    label: str  # display name for the product
    calculation: PortionCalculation


class NutrientComparison(BaseModel):
    nutrient: str
    per_serving_note: Optional[str] = None
    per_actual_portion_note: Optional[str] = None
    per_100g_note: Optional[str] = None
    per_100g_available: bool = True


class ComparisonResult(BaseModel):
    product_a: ProductSide
    product_b: ProductSide
    per_100g_available: bool
    per_100g_unavailable_reason: Optional[str] = None
    nutrient_comparisons: list[NutrientComparison]


def _format_amount(amount) -> str:
    if amount is None:
        return "not available"
    return f"{amount.value:g} {amount.unit.value}"


def compare_products(
    label_a: ExtractedLabel,
    portion_a: PortionSelection,
    name_a: str,
    label_b: ExtractedLabel,
    portion_b: PortionSelection,
    name_b: str,
) -> ComparisonResult:
    calc_a = calculate_portion(label_a, portion_a)
    calc_b = calculate_portion(label_b, portion_b)

    weight_a = label_a.serving.grams_per_serving
    weight_b = label_b.serving.grams_per_serving
    per_100g_available = bool(weight_a and weight_b)
    per_100g_reason = None
    if not per_100g_available:
        missing = []
        if not weight_a:
            missing.append(name_a)
        if not weight_b:
            missing.append(name_b)
        per_100g_reason = (
            f"Per-100g comparison is refused: grams-per-serving is missing for "
            f"{' and '.join(missing)}. Confirm the net weight or household measure "
            "to unlock a fair per-100g view."
        )

    comparisons: list[NutrientComparison] = []
    for nutrient in CRITICAL_NUTRIENTS:
        result_a = calc_a.results[nutrient]
        result_b = calc_b.results[nutrient]

        nc = NutrientComparison(nutrient=nutrient)
        nc.per_serving_note = (
            f"{name_a}: {_format_amount(result_a.per_serving)} vs "
            f"{name_b}: {_format_amount(result_b.per_serving)} (per labelled serving)"
        )
        nc.per_actual_portion_note = (
            f"{name_a}: {_format_amount(result_a.per_actual_portion)} vs "
            f"{name_b}: {_format_amount(result_b.per_actual_portion)} (per your actual portion)"
        )
        if per_100g_available:
            nc.per_100g_note = (
                f"{name_a}: {_format_amount(result_a.per_100g)} vs "
                f"{name_b}: {_format_amount(result_b.per_100g)} (per 100 g)"
            )
        else:
            nc.per_100g_available = False
        comparisons.append(nc)

    return ComparisonResult(
        product_a=ProductSide(label=name_a, calculation=calc_a),
        product_b=ProductSide(label=name_b, calculation=calc_b),
        per_100g_available=per_100g_available,
        per_100g_unavailable_reason=per_100g_reason,
        nutrient_comparisons=comparisons,
    )
