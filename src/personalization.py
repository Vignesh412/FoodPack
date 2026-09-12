"""Deterministic personalization over confirmed package facts.

The module compares user-entered allergens and daily targets with the
calculated portion. It never recommends a diet, diagnoses a condition, or
claims that a product is allergy-safe.
"""

from __future__ import annotations

import re
from typing import Literal, Optional

from pydantic import BaseModel, Field

from src.nutrition_rules import PortionCalculation
from src.schemas import ExtractedLabel, PersonalizationProfile


AllergenStatus = Literal["profile_not_provided", "declared_match", "advisory_match", "ingredient_match", "no_match_found"]

ALLERGEN_ALIASES: dict[str, tuple[str, ...]] = {
    "milk": ("milk", "dairy", "whey", "casein", "caseinate", "lactalbumin"),
    "egg": ("egg", "albumen", "ovalbumin"),
    "peanut": ("peanut", "groundnut"),
    "tree_nuts": ("tree nut", "almond", "cashew", "walnut", "pecan", "pistachio", "hazelnut", "macadamia", "brazil nut"),
    "soy": ("soy", "soya", "soybean"),
    "wheat": ("wheat", "semolina", "durum", "spelt"),
    "sesame": ("sesame", "tahini"),
    "fish": ("fish", "anchovy", "salmon", "tuna", "cod"),
    "shellfish": ("shellfish", "shrimp", "prawn", "crab", "lobster", "crayfish"),
}

ANIMAL_INGREDIENTS = {
    "vegan": ("milk", "whey", "casein", "egg", "honey", "gelatin", "gelatine", "meat", "chicken", "beef", "pork", "fish", "shellfish"),
    "vegetarian": ("gelatin", "gelatine", "meat", "chicken", "beef", "pork", "fish", "shellfish"),
}


class AllergenMatchResult(BaseModel):
    status: AllergenStatus
    declared_matches: list[str] = Field(default_factory=list)
    advisory_matches: list[str] = Field(default_factory=list)
    ingredient_matches: list[str] = Field(default_factory=list)
    message: str


class GoalContribution(BaseModel):
    key: str
    label: str
    consumed: float
    target: float
    unit: str
    percent_of_target: float
    target_type: Literal["goal", "limit"]


class DietaryPreferenceResult(BaseModel):
    preference: str
    status: Literal["not_requested", "possible_conflict", "not_verified"]
    matched_terms: list[str] = Field(default_factory=list)
    message: str


class PersonalizationResult(BaseModel):
    allergen_match: AllergenMatchResult
    dietary_preference: DietaryPreferenceResult
    goal_contributions: list[GoalContribution] = Field(default_factory=list)
    disclaimer: str = "Personalized comparisons use goals entered by the user and do not replace medical or dietetic advice."


def _canonical_allergens(text: str) -> set[str]:
    lowered = text.lower()
    matches: set[str] = set()
    for canonical, aliases in ALLERGEN_ALIASES.items():
        if any(re.search(rf"\b{re.escape(alias)}s?\b", lowered) for alias in aliases):
            matches.add(canonical)
    return matches


def _normalized_term(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", text.lower())).strip().removesuffix("s")


def _profile_allergens(values: list[str]) -> set[str]:
    matches: set[str] = set()
    for value in values:
        canonical = _canonical_allergens(value)
        matches.update(canonical or {_normalized_term(value)})
    return {value for value in matches if value}


def _label_allergens(values: list[str]) -> set[str]:
    matches = _canonical_allergens(" ".join(values))
    matches.update(_normalized_term(value.replace("may contain", "")) for value in values)
    return {value for value in matches if value}


def _display(canonical: str) -> str:
    return canonical.replace("_", " ")


def match_allergens(label: ExtractedLabel, profile: PersonalizationProfile) -> AllergenMatchResult:
    user_allergens = _profile_allergens(profile.declared_allergens)
    if not user_allergens:
        return AllergenMatchResult(
            status="profile_not_provided",
            message="No personal allergens were entered. FoodProof can only repeat the package allergen statement.",
        )

    declared = _label_allergens(label.allergens.declared_contains) & user_allergens
    advisory = _label_allergens(label.allergens.may_contain_statement) & user_allergens
    ingredient_text = label.allergens.raw_ingredient_text or ""
    ingredient_candidates = _canonical_allergens(ingredient_text)
    ingredient_candidates.update(
        value for value in user_allergens if re.search(rf"\b{re.escape(value)}s?\b", ingredient_text.lower())
    )
    ingredient = ingredient_candidates & user_allergens
    display_declared = sorted(_display(value) for value in declared)
    display_advisory = sorted(_display(value) for value in advisory)
    display_ingredient = sorted(_display(value) for value in ingredient - declared - advisory)

    if declared:
        status: AllergenStatus = "declared_match"
        message = "Stop and review: the package’s declared allergen statement matches your profile. This is not an allergy-safety decision."
    elif advisory:
        status = "advisory_match"
        message = "Caution: the package’s ‘may contain’ statement matches your profile. This is not an allergy-safety decision."
    elif ingredient:
        status = "ingredient_match"
        message = "Caution: an ingredient term matches your profile even though no matching ‘contains’ statement was captured. Review the original package."
    else:
        status = "no_match_found"
        message = "No matching allergen term was found in the captured text. This does not mean the product is allergy-safe."

    return AllergenMatchResult(
        status=status,
        declared_matches=display_declared,
        advisory_matches=display_advisory,
        ingredient_matches=display_ingredient,
        message=message,
    )


def check_dietary_preference(label: ExtractedLabel, profile: PersonalizationProfile) -> DietaryPreferenceResult:
    preference = profile.dietary_preference
    if preference == "none":
        return DietaryPreferenceResult(preference=preference, status="not_requested", message="No dietary preference was selected.")
    text = (label.allergens.raw_ingredient_text or "").lower()
    matched = sorted({term for term in ANIMAL_INGREDIENTS[preference] if re.search(rf"\b{re.escape(term)}s?\b", text)})
    if matched:
        return DietaryPreferenceResult(
            preference=preference,
            status="possible_conflict",
            matched_terms=matched,
            message=f"Possible {preference} conflict found in the captured ingredients. Review the original package.",
        )
    return DietaryPreferenceResult(
        preference=preference,
        status="not_verified",
        message=f"No obvious {preference} conflict was found, but the captured text is not enough to certify the product.",
    )


def _contribution(key: str, label: str, consumed: Optional[float], target: Optional[float], unit: str, target_type: Literal["goal", "limit"]) -> Optional[GoalContribution]:
    if consumed is None or target is None:
        return None
    return GoalContribution(
        key=key,
        label=label,
        consumed=round(consumed, 2),
        target=round(target, 2),
        unit=unit,
        percent_of_target=round(consumed / target * 100, 1),
        target_type=target_type,
    )


def personalize(label: ExtractedLabel, calculation: PortionCalculation, profile: PersonalizationProfile) -> PersonalizationResult:
    results = calculation.results
    protein = results["protein"].per_actual_portion
    fibre = results["fibre"].per_actual_portion
    sodium = results["sodium"].per_actual_portion
    sugar = results["added_sugar"].per_actual_portion

    contributions = [
        _contribution("calories", "Calories", calculation.calories_per_actual_portion, profile.daily_calorie_goal, "kcal", "goal"),
        _contribution("protein", "Protein", protein.to_grams() if protein else None, profile.daily_protein_goal_g, "g", "goal"),
        _contribution("fibre", "Fibre", fibre.to_grams() if fibre else None, profile.daily_fibre_goal_g, "g", "goal"),
        _contribution("sodium", "Sodium", sodium.to_grams() * 1000 if sodium else None, profile.daily_sodium_limit_mg, "mg", "limit"),
        _contribution("added_sugar", "Added sugar", sugar.to_grams() if sugar else None, profile.daily_added_sugar_limit_g, "g", "limit"),
    ]
    return PersonalizationResult(
        allergen_match=match_allergens(label, profile),
        dietary_preference=check_dietary_preference(label, profile),
        goal_contributions=[item for item in contributions if item is not None],
    )
