"""
Pydantic data contracts for FoodProof.

Design rule (Step 3 of the roadmap): every nutrient amount carries its unit
explicitly, so grams, milligrams and percentages can never be silently
confused downstream. Nothing here calls a model or does arithmetic — this
module only defines what a valid extracted record looks like and rejects
anything malformed or physically impossible before it reaches the rest of
the pipeline.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# --------------------------------------------------------------------------
# Enums
# --------------------------------------------------------------------------

class MassUnit(str, Enum):
    GRAM = "g"
    MILLIGRAM = "mg"
    MICROGRAM = "mcg"


class PanelType(str, Enum):
    FRONT_OF_PACK = "front_of_pack"
    NUTRITION_FACTS = "nutrition_facts"
    INGREDIENTS_ALLERGENS = "ingredients_allergens"
    UNKNOWN = "unknown"


class NutritionGoal(str, Enum):
    LOWER_ADDED_SUGAR = "lower_added_sugar"
    LOWER_SODIUM = "lower_sodium"
    HIGHER_FIBRE = "higher_fibre"
    GENERAL_UNDERSTANDING = "general_understanding"
    PRODUCT_COMPARISON = "product_comparison"


class DVLevel(str, Enum):
    """FDA consumer guide: 5% DV or less is low, 20% DV or more is high."""
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    UNKNOWN = "unknown"


# --------------------------------------------------------------------------
# Small value objects
# --------------------------------------------------------------------------

class MassAmount(BaseModel):
    """A nutrient amount with an explicit unit. Never a bare float."""

    value: float = Field(ge=0, le=100000)
    unit: MassUnit

    def to_grams(self) -> float:
        factor = {MassUnit.GRAM: 1.0, MassUnit.MILLIGRAM: 0.001, MassUnit.MICROGRAM: 0.000001}
        return self.value * factor[self.unit]


class NutrientField(BaseModel):
    """One critical nutrient as read off the label, with provenance."""

    amount: Optional[MassAmount] = None
    percent_daily_value: Optional[float] = Field(default=None, ge=0, le=1000)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    present_on_label: bool = True

    @property
    def is_missing(self) -> bool:
        """
        A nutrient counts as missing whenever we don't have a confirmed
        amount for it — whether that's because the label explicitly omits
        it (present_on_label=False) or because it simply hasn't been
        extracted/confirmed yet. present_on_label only affects how the UI
        phrases the gap, never whether downstream calculations can trust
        the value.
        """
        return self.amount is None


class ServingInfo(BaseModel):
    household_measure: Optional[str] = None
    grams_per_serving: Optional[float] = Field(default=None, gt=0, le=5000)
    servings_per_container: Optional[float] = Field(default=None, gt=0, le=500)
    net_weight_grams: Optional[float] = Field(default=None, gt=0, le=20000)


class AllergenInfo(BaseModel):
    declared_contains: list[str] = Field(default_factory=list)
    may_contain_statement: list[str] = Field(default_factory=list)
    raw_ingredient_text: Optional[str] = None


class FrontOfPackClaim(BaseModel):
    raw_text: str
    claim_type: Optional[str] = None  # e.g. "low_sodium", "no_added_sugar", "high_fibre"


class ExtractedLabel(BaseModel):
    """
    The full structured record produced by vision extraction, after schema
    validation but BEFORE the user has confirmed or corrected it in the UI.
    """

    product_name: Optional[str] = None
    barcode: Optional[str] = None

    serving: ServingInfo = Field(default_factory=ServingInfo)

    calories: Optional[float] = Field(default=None, ge=0, le=5000)
    added_sugar: NutrientField = Field(default_factory=NutrientField)
    sodium: NutrientField = Field(default_factory=NutrientField)
    saturated_fat: NutrientField = Field(default_factory=NutrientField)
    fibre: NutrientField = Field(default_factory=NutrientField)
    protein: NutrientField = Field(default_factory=NutrientField)

    allergens: AllergenInfo = Field(default_factory=AllergenInfo)
    front_claims: list[FrontOfPackClaim] = Field(default_factory=list)

    panels_captured: list[PanelType] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    overall_confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    user_confirmed: bool = False

    @field_validator("missing_fields")
    @classmethod
    def dedupe_missing(cls, v: list[str]) -> list[str]:
        return sorted(set(v))

    @model_validator(mode="after")
    def flag_missing_critical_fields(self) -> "ExtractedLabel":
        """
        Recompute missing_fields from the actual nutrient state rather than
        trusting whatever the model said, so a downstream bug in the vision
        prompt can't quietly suppress a legitimate gap.
        """
        computed_missing = set(self.missing_fields)
        for name in ("added_sugar", "sodium", "saturated_fat", "fibre", "protein"):
            field: NutrientField = getattr(self, name)
            if field.is_missing:
                computed_missing.add(name)
        if self.serving.grams_per_serving is None:
            computed_missing.add("serving.grams_per_serving")
        self.missing_fields = sorted(computed_missing)
        return self


class PortionSelection(BaseModel):
    """What the user actually eats, versus the labelled serving."""

    servings_consumed: float = Field(default=1.0, gt=0, le=50)


class PersonalizationProfile(BaseModel):
    """User-entered preferences and targets; never inferred as medical advice."""

    declared_allergens: list[str] = Field(default_factory=list, max_length=30)
    dietary_preference: Literal["none", "vegetarian", "vegan"] = "none"
    daily_calorie_goal: Optional[float] = Field(default=None, gt=0, le=10000)
    daily_protein_goal_g: Optional[float] = Field(default=None, gt=0, le=1000)
    daily_fibre_goal_g: Optional[float] = Field(default=None, gt=0, le=500)
    daily_sodium_limit_mg: Optional[float] = Field(default=None, gt=0, le=50000)
    daily_added_sugar_limit_g: Optional[float] = Field(default=None, gt=0, le=1000)

    @field_validator("declared_allergens")
    @classmethod
    def clean_allergens(cls, values: list[str]) -> list[str]:
        cleaned = {value.strip().lower() for value in values if value.strip()}
        return sorted(cleaned)


class RetakeInstruction(BaseModel):
    """Output of the image quality gate when a photo is not usable."""

    panel: PanelType
    accepted: bool
    reason: Optional[str] = None
    retake_instruction: Optional[str] = None
