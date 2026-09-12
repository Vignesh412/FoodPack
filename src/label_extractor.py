"""
Step 5: vision extraction into the structured schema, followed by human
confirmation in the UI (this module produces the pre-confirmation record;
app.py is what makes the user confirm or correct it before anything else
runs).
"""

from __future__ import annotations

import base64
import io
import json
import os
from typing import Optional

from PIL import Image, ImageOps
from pydantic import ValidationError

from src.schemas import (
    AllergenInfo,
    ExtractedLabel,
    FrontOfPackClaim,
    MassAmount,
    MassUnit,
    NutrientField,
    PanelType,
    ServingInfo,
)

_EXTRACTION_SCHEMA_INSTRUCTIONS = """You are extracting data from photographs of a US packaged food label into
strict JSON. Respond with ONLY a JSON object matching exactly this shape
(use null for anything not visible or not present — never guess a number):

{
  "product_name": string or null,
  "serving": {
    "household_measure": string or null,
    "grams_per_serving": number or null,
    "servings_per_container": number or null,
    "net_weight_grams": number or null
  },
  "calories": number or null,
  "added_sugar": {"value": number or null, "unit": "g", "percent_daily_value": number or null, "present_on_label": true or false},
  "sodium": {"value": number or null, "unit": "mg", "percent_daily_value": number or null, "present_on_label": true or false},
  "saturated_fat": {"value": number or null, "unit": "g", "percent_daily_value": number or null, "present_on_label": true or false},
  "fibre": {"value": number or null, "unit": "g", "percent_daily_value": number or null, "present_on_label": true or false},
  "protein": {"value": number or null, "unit": "g", "percent_daily_value": number or null, "present_on_label": true or false},
  "allergens": {
    "declared_contains": [string, ...],
    "may_contain_statement": [string, ...],
    "raw_ingredient_text": string or null
  },
  "front_claims": [{"raw_text": string, "claim_type": string or null}],
  "panels_captured": [array using only "front_of_pack", "nutrition_facts", "ingredients_allergens"],
  "field_confidence": {"added_sugar": 0-1 number, "sodium": 0-1 number, "saturated_fat": 0-1 number, "fibre": 0-1 number, "protein": 0-1 number}
}

Rules:
- Use only what is visibly printed on the label. Never estimate or infer a missing number.
- percent_daily_value is the %DV printed on the Nutrition Facts panel for that nutrient, if shown.
- front_claims are marketing phrases from the front-of-pack photo only (e.g. "Low Sodium", "No Added Sugar"), not from the Nutrition Facts panel.
- field_confidence should be lower when text was small, angled, or partially obscured.
"""


class ExtractionError(Exception):
    pass


MAX_VISION_EDGE_PX = 1600


def prepare_image_for_vision(image_bytes: bytes) -> tuple[bytes, str]:
    """Normalize orientation and bound image size before a paid vision call."""
    image = ImageOps.exif_transpose(Image.open(io.BytesIO(image_bytes))).convert("RGB")
    image.thumbnail((MAX_VISION_EDGE_PX, MAX_VISION_EDGE_PX), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=90, optimize=True)
    return buffer.getvalue(), "image/jpeg"


def _mass_field(raw: Optional[dict], default_unit: MassUnit, confidence_notes: dict) -> NutrientField:
    if raw is None:
        return NutrientField(present_on_label=False)
    value = raw.get("value")
    unit_str = raw.get("unit") or default_unit.value
    present = raw.get("present_on_label", value is not None)
    amount = None
    if value is not None:
        try:
            amount = MassAmount(value=float(value), unit=MassUnit(unit_str))
        except (ValueError, ValidationError):
            amount = None
    return NutrientField(
        amount=amount,
        percent_daily_value=raw.get("percent_daily_value"),
        present_on_label=present,
    )


def parse_extraction_response(raw: dict) -> ExtractedLabel:
    """
    Maps the LLM's raw JSON into the validated Pydantic schema. Kept as a
    pure function, separate from the API call, so it can be unit tested
    with synthetic dicts and never needs network access or an API key.
    """
    confidence_notes = raw.get("field_confidence", {}) or {}

    serving_raw = raw.get("serving") or {}
    serving = ServingInfo(
        household_measure=serving_raw.get("household_measure"),
        grams_per_serving=serving_raw.get("grams_per_serving"),
        servings_per_container=serving_raw.get("servings_per_container"),
        net_weight_grams=serving_raw.get("net_weight_grams"),
    )

    allergens_raw = raw.get("allergens") or {}
    allergens = AllergenInfo(
        declared_contains=allergens_raw.get("declared_contains", []) or [],
        may_contain_statement=allergens_raw.get("may_contain_statement", []) or [],
        raw_ingredient_text=allergens_raw.get("raw_ingredient_text"),
    )

    front_claims = [
        FrontOfPackClaim(raw_text=c["raw_text"], claim_type=c.get("claim_type"))
        for c in (raw.get("front_claims") or [])
        if c.get("raw_text")
    ]

    panels_captured = []
    for p in raw.get("panels_captured", []) or []:
        try:
            panels_captured.append(PanelType(p))
        except ValueError:
            continue

    label = ExtractedLabel(
        product_name=raw.get("product_name"),
        serving=serving,
        calories=raw.get("calories"),
        added_sugar=_mass_field(raw.get("added_sugar"), MassUnit.GRAM, confidence_notes),
        sodium=_mass_field(raw.get("sodium"), MassUnit.MILLIGRAM, confidence_notes),
        saturated_fat=_mass_field(raw.get("saturated_fat"), MassUnit.GRAM, confidence_notes),
        fibre=_mass_field(raw.get("fibre"), MassUnit.GRAM, confidence_notes),
        protein=_mass_field(raw.get("protein"), MassUnit.GRAM, confidence_notes),
        allergens=allergens,
        front_claims=front_claims,
        panels_captured=panels_captured,
    )

    # Apply per-field confidence after construction (NutrientField is
    # immutable-by-convention elsewhere, but plain attribute assignment is
    # fine here since we're finishing construction of a fresh object).
    for name in ("added_sugar", "sodium", "saturated_fat", "fibre", "protein"):
        if name in confidence_notes:
            getattr(label, name).confidence = float(confidence_notes[name])

    if confidence_notes:
        label.overall_confidence = sum(confidence_notes.values()) / len(confidence_notes)

    return label


def _call_vision_model(images: list[tuple[bytes, str]], extra_instruction: str = "") -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ExtractionError(
            "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add a real key."
        )

    import anthropic  # lazy import

    client = anthropic.Anthropic(api_key=api_key, timeout=90.0, max_retries=0)
    model = os.environ.get("FOODPROOF_VISION_MODEL", "claude-sonnet-4-6")

    content = []
    for image_bytes, _media_type in images:
        image_bytes, media_type = prepare_image_for_vision(image_bytes)
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        content.append({"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}})
    content.append({"type": "text", "text": _EXTRACTION_SCHEMA_INSTRUCTIONS + extra_instruction})

    response = client.messages.create(
        model=model,
        max_tokens=1500,
        messages=[{"role": "user", "content": content}],
    )
    return response.content[0].text.strip()


def _strip_code_fence(text: str) -> str:
    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            text = text.split("\n", 1)[1]
    return text.strip()


def extract_label(images: list[tuple[bytes, str]], max_repair_attempts: int = 1) -> ExtractedLabel:
    """
    images: list of (image_bytes, media_type) tuples for whichever of the
    three panels were captured. Calls the vision model, validates the
    response against the schema, and retries once with the validation
    error fed back to the model if parsing fails.
    """
    last_error: Optional[str] = None
    extra_instruction = ""

    for attempt in range(max_repair_attempts + 1):
        raw_text = _call_vision_model(images, extra_instruction=extra_instruction)
        cleaned = _strip_code_fence(raw_text)
        try:
            raw = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            last_error = f"Response was not valid JSON: {exc}"
            extra_instruction = f"\n\nYour previous response failed to parse: {last_error}\nReturn ONLY the corrected JSON object, no commentary."
            continue

        try:
            return parse_extraction_response(raw)
        except ValidationError as exc:
            last_error = str(exc)
            extra_instruction = (
                f"\n\nYour previous response failed schema validation: {last_error}\n"
                "Return ONLY the corrected JSON object, no commentary."
            )
            continue

    raise ExtractionError(f"Extraction failed after {max_repair_attempts + 1} attempts: {last_error}")
