"""
Optional supporting tool: Open Food Facts barcode lookup, plus the
"winning strategy" delta-check — comparing a freshly photographed value
against the historical record for that barcode and flagging a mismatch.

This module never overrides the photograph. Per the roadmap's evidence
hierarchy, the current photograph and user confirmation stay primary;
barcode data can only support or flag, never silently replace, the label.
"""

from __future__ import annotations

import os
from typing import Optional

import requests
from pydantic import BaseModel

OFF_API_BASE = os.environ.get("OFF_API_BASE", "https://world.openfoodfacts.org")
OFF_USER_AGENT = os.environ.get(
    "OFF_USER_AGENT",
    "FoodProofFit/1.1 (https://github.com/Vignesh412/FoodPack)",
)
REQUEST_TIMEOUT_SECONDS = 6

# Fields we can meaningfully diff against our schema, mapped to OFF's
# per-100g nutriment keys.
_OFF_FIELD_MAP = {
    "added_sugar": "sugars_100g",
    "sodium": "sodium_100g",  # OFF reports sodium in grams per 100g
    "saturated_fat": "saturated-fat_100g",
    "fibre": "fiber_100g",
    "protein": "proteins_100g",
}

# Fractional tolerance before we call something a real discrepancy rather
# than rounding/unit noise between two independent sources.
MISMATCH_TOLERANCE = 0.20


class OFFLookupResult(BaseModel):
    found: bool
    product_name: Optional[str] = None
    per_100g: dict[str, float] = {}
    raw_error: Optional[str] = None


class DeltaFlag(BaseModel):
    nutrient: str
    photographed_per_100g: float
    historical_per_100g: float
    percent_difference: float


def lookup_barcode(barcode: str) -> OFFLookupResult:
    url = f"{OFF_API_BASE}/api/v2/product/{barcode}.json"
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": OFF_USER_AGENT},
            params={"fields": "product_name,nutriments"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        return OFFLookupResult(found=False, raw_error=str(exc))

    if data.get("status") != 1 or "product" not in data:
        return OFFLookupResult(found=False, raw_error="Barcode not found in Open Food Facts.")

    product = data["product"]
    nutriments = product.get("nutriments", {})
    per_100g = {}
    for our_key, off_key in _OFF_FIELD_MAP.items():
        value = nutriments.get(off_key)
        if isinstance(value, (int, float)):
            # sodium_100g from OFF is grams; convert to mg to match our schema's
            # native unit for sodium so the delta-check compares like with like.
            if our_key == "sodium":
                value = value * 1000
            per_100g[our_key] = float(value)

    return OFFLookupResult(
        found=True,
        product_name=product.get("product_name"),
        per_100g=per_100g,
    )


def compute_delta_flags(
    photographed_per_100g: dict[str, float],
    historical: OFFLookupResult,
) -> list[DeltaFlag]:
    """
    Compare fresh label values against the historical OFF record. Only
    flags a mismatch beyond MISMATCH_TOLERANCE — small differences are
    expected noise between independently-sourced data, not a real change.
    """
    if not historical.found:
        return []

    flags: list[DeltaFlag] = []
    for nutrient, fresh_value in photographed_per_100g.items():
        old_value = historical.per_100g.get(nutrient)
        if old_value is None or old_value == 0:
            continue
        percent_diff = abs(fresh_value - old_value) / old_value
        if percent_diff >= MISMATCH_TOLERANCE:
            flags.append(
                DeltaFlag(
                    nutrient=nutrient,
                    photographed_per_100g=fresh_value,
                    historical_per_100g=old_value,
                    percent_difference=round(percent_diff * 100, 1),
                )
            )
    return flags
