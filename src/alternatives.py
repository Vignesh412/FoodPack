"""Live, evidence-bounded alternative search over Open Food Facts.

The current confirmed package remains the primary evidence. Open Food Facts
records are used only to surface same-category candidates that are better on
one explicitly selected nutrient. The module never emits a universal health
score or allergy-safety claim.
"""

from __future__ import annotations

import os
import re
from enum import Enum
from typing import Any, Literal, Optional

import requests
from pydantic import BaseModel, Field

from src.personalization import match_allergens
from src.schemas import AllergenInfo, ExtractedLabel, PersonalizationProfile


SEARCH_API_URL = os.environ.get("OFF_SEARCH_API_URL", "https://search.openfoodfacts.org/search")
OFF_USER_AGENT = os.environ.get(
    "OFF_USER_AGENT",
    "FoodProofFit/1.1 (https://github.com/Vignesh412/FoodPack)",
)
SEARCH_TIMEOUT_SECONDS = 12
SEARCH_PAGE_SIZE = 40
MINIMUM_IMPROVEMENT_PERCENT = 5.0


class AlternativeCategory(str, Enum):
    SNACK_BARS = "snack_bars"
    BREAKFAST_CEREALS = "breakfast_cereals"
    CANNED_SOUPS = "canned_soups"
    CRACKERS = "crackers"


CATEGORY_CONFIG = {
    AlternativeCategory.SNACK_BARS: ("Snack bars", "snack bar"),
    AlternativeCategory.BREAKFAST_CEREALS: ("Breakfast cereals", "breakfast cereal"),
    AlternativeCategory.CANNED_SOUPS: ("Canned soups", "canned soup"),
    AlternativeCategory.CRACKERS: ("Crackers", "crackers"),
}

# Full-text search is deliberately followed by a strict category-tag gate. This
# prevents a query such as "snack bar" from returning a nutritionally appealing
# but irrelevant product such as chocolate-covered nuts.
CATEGORY_TAGS = {
    AlternativeCategory.SNACK_BARS: {
        "en:bars",
        "en:cereal-bars",
        "en:energy-bars",
        "en:fruit-and-nut-bars",
        "en:nutrition-bars",
        "en:protein-bars",
        "en:snack-bars",
    },
    AlternativeCategory.BREAKFAST_CEREALS: {
        "en:breakfast-cereals",
        "en:cereals-and-potatoes",
        "en:hot-cereals",
        "en:mueslis",
    },
    AlternativeCategory.CANNED_SOUPS: {
        "en:canned-soups",
        "en:soups",
        "en:vegetable-soups",
    },
    AlternativeCategory.CRACKERS: {
        "en:crackers",
        "en:crackers-and-biscuits",
        "en:salty-snacks",
    },
}

AlternativeGoal = Literal["lower_sodium", "lower_added_sugar", "higher_fibre"]
AlternativeStatus = Literal[
    "ready",
    "unsupported_goal",
    "current_evidence_missing",
    "no_reliable_candidates",
    "search_unavailable",
]


class AlternativeCandidate(BaseModel):
    barcode: str
    product_name: str
    brands: list[str] = Field(default_factory=list)
    value_per_100g: float
    current_value_per_100g: float
    unit: str
    improvement_percent: float
    reason: str
    allergen_status: Literal["not_requested", "no_declared_match", "not_verified"]
    allergen_note: str
    dietary_status: Literal["not_requested", "matches", "not_verified"]
    dietary_note: str
    completeness: Optional[float] = None
    source_url: str
    availability_note: str = "Listed for the United States in Open Food Facts; local store availability is not verified."


class AlternativeSearchResult(BaseModel):
    status: AlternativeStatus
    message: str
    category: AlternativeCategory
    category_label: str
    goal: AlternativeGoal
    goal_label: str
    candidates_searched: int = 0
    alternatives: list[AlternativeCandidate] = Field(default_factory=list)
    source_name: str = "Open Food Facts"
    source_url: str = "https://world.openfoodfacts.org/"
    evidence_note: str = (
        "These are database candidates, not medical recommendations. Open Food Facts records may be incomplete or outdated; "
        "verify the current package before purchase or consumption."
    )


GOAL_CONFIG: dict[str, dict[str, str]] = {
    "lower_sodium": {
        "label": "Lower sodium",
        "label_field": "sodium",
        "off_field": "sodium_100g",
        "unit": "mg",
        "direction": "lower",
    },
    "lower_added_sugar": {
        "label": "Lower added sugar",
        "label_field": "added_sugar",
        "off_field": "added-sugars_100g",
        "unit": "g",
        "direction": "lower",
    },
    "higher_fibre": {
        "label": "Higher fibre",
        "label_field": "fibre",
        "off_field": "fiber_100g",
        "unit": "g",
        "direction": "higher",
    },
}

SEARCH_FIELDS = [
    "code",
    "product_name",
    "brands",
    "nutriments",
    "allergens_tags",
    "ingredients_analysis_tags",
    "ingredients_text",
    "countries_tags",
    "categories_tags",
    "completeness",
]


def _current_value_per_100g(label: ExtractedLabel, goal: AlternativeGoal) -> Optional[float]:
    grams = label.serving.grams_per_serving
    field_name = GOAL_CONFIG[goal]["label_field"]
    nutrient = getattr(label, field_name)
    if not grams or not nutrient.amount:
        return None
    grams_of_nutrient = nutrient.amount.to_grams()
    value = grams_of_nutrient * 100 / grams
    if goal == "lower_sodium":
        value *= 1000
    return value


def _normalise_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _candidate_goal_value(product: dict[str, Any], goal: AlternativeGoal) -> Optional[float]:
    value = (product.get("nutriments") or {}).get(GOAL_CONFIG[goal]["off_field"])
    if not isinstance(value, (int, float)) or value < 0:
        return None
    if goal == "lower_sodium":
        return float(value) * 1000  # Open Food Facts stores sodium_100g in grams.
    return float(value)


def _dietary_outcome(product: dict[str, Any], preference: str) -> tuple[bool, str, str]:
    if preference == "none":
        return True, "not_requested", "No dietary preference was selected."
    tags = set(product.get("ingredients_analysis_tags") or [])
    positive = f"en:{preference}"
    negative = f"en:non-{preference}"
    if negative in tags:
        return False, "not_verified", f"The database record marks this product as non-{preference}."
    if positive in tags:
        return True, "matches", f"The database record marks this product as {preference}; verify the current package."
    return True, "not_verified", f"The database record does not verify that this product is {preference}."


def _allergen_outcome(product: dict[str, Any], profile: PersonalizationProfile) -> tuple[bool, str, str]:
    if not profile.declared_allergens:
        return True, "not_requested", "No personal allergens were entered."
    tags = product.get("allergens_tags") or []
    ingredient_text = product.get("ingredients_text") or ""
    if not tags and not ingredient_text:
        return True, "not_verified", "Allergen evidence is incomplete in the database; verify the current package."
    label = ExtractedLabel(
        allergens=AllergenInfo(
            declared_contains=[tag.removeprefix("en:").replace("-", " ") for tag in tags],
            raw_ingredient_text=ingredient_text,
        )
    )
    match = match_allergens(label, profile)
    if match.status in {"declared_match", "ingredient_match", "advisory_match"}:
        return False, "not_verified", "A listed allergen or ingredient conflicts with the user profile."
    return True, "no_declared_match", "No declared match was found in the available record; this is not allergy clearance."


def rank_alternatives(
    products: list[dict[str, Any]],
    current_label: ExtractedLabel,
    category: AlternativeCategory,
    goal: AlternativeGoal,
    profile: Optional[PersonalizationProfile] = None,
    current_barcode: Optional[str] = None,
    limit: int = 3,
) -> AlternativeSearchResult:
    category_label, _ = CATEGORY_CONFIG[category]
    goal_label = GOAL_CONFIG[goal]["label"]
    if goal == "lower_added_sugar":
        return AlternativeSearchResult(
            status="unsupported_goal",
            message=(
                "Live alternatives are not available for added sugar because the candidate records do not reliably contain "
                "added-sugar values. FoodProof Fit will not substitute total sugar for added sugar."
            ),
            category=category,
            category_label=category_label,
            goal=goal,
            goal_label=goal_label,
            candidates_searched=len(products),
        )

    current_value = _current_value_per_100g(current_label, goal)
    if current_value is None or (GOAL_CONFIG[goal]["direction"] == "lower" and current_value == 0):
        return AlternativeSearchResult(
            status="current_evidence_missing",
            message=f"The confirmed package does not contain enough evidence to compare products for {goal_label.lower()}.",
            category=category,
            category_label=category_label,
            goal=goal,
            goal_label=goal_label,
            candidates_searched=len(products),
        )

    active_profile = profile or PersonalizationProfile()
    generic_names = {
        "snack bar", "snack bars", "breakfast cereal", "breakfast cereals", "canned soup", "canned soups", "cracker", "crackers"
    }
    ranked: list[AlternativeCandidate] = []
    seen_names: set[str] = set()
    for product in products:
        if "en:united-states" not in (product.get("countries_tags") or []):
            continue
        if not CATEGORY_TAGS[category].intersection(product.get("categories_tags") or []):
            continue
        barcode = str(product.get("code") or "").strip()
        name = str(product.get("product_name") or "").strip()
        normalised_name = _normalise_name(name)
        if not barcode or not name or normalised_name in generic_names or barcode == current_barcode or normalised_name in seen_names:
            continue
        candidate_value = _candidate_goal_value(product, goal)
        if candidate_value is None:
            continue
        direction = GOAL_CONFIG[goal]["direction"]
        if direction == "lower":
            improvement = (current_value - candidate_value) / current_value * 100
        else:
            if current_value == 0:
                improvement = 100.0 if candidate_value > 0 else 0.0
            else:
                improvement = (candidate_value - current_value) / current_value * 100
        if improvement < MINIMUM_IMPROVEMENT_PERCENT:
            continue
        allergen_ok, allergen_status, allergen_note = _allergen_outcome(product, active_profile)
        dietary_ok, dietary_status, dietary_note = _dietary_outcome(product, active_profile.dietary_preference)
        if not allergen_ok or not dietary_ok:
            continue
        brands = product.get("brands") or []
        if isinstance(brands, str):
            brands = [item.strip() for item in brands.split(",") if item.strip()]
        reason = (
            f"{round(improvement, 1):g}% {'less sodium' if direction == 'lower' else 'more fibre'} per 100 g "
            "than the confirmed current package."
        )
        ranked.append(
            AlternativeCandidate(
                barcode=barcode,
                product_name=name,
                brands=brands,
                value_per_100g=round(candidate_value, 2),
                current_value_per_100g=round(current_value, 2),
                unit=GOAL_CONFIG[goal]["unit"],
                improvement_percent=round(improvement, 1),
                reason=reason,
                allergen_status=allergen_status,
                allergen_note=allergen_note,
                dietary_status=dietary_status,
                dietary_note=dietary_note,
                completeness=product.get("completeness") if isinstance(product.get("completeness"), (int, float)) else None,
                source_url=f"https://world.openfoodfacts.org/product/{barcode}",
            )
        )
        seen_names.add(normalised_name)

    ranked.sort(key=lambda item: (-item.improvement_percent, -(item.completeness or 0)))
    selected = ranked[: max(1, min(limit, 5))]
    if not selected:
        return AlternativeSearchResult(
            status="no_reliable_candidates",
            message=(
                f"No sufficiently complete U.S. {category_label.lower()} records were at least "
                f"{MINIMUM_IMPROVEMENT_PERCENT:g}% better for {goal_label.lower()}."
            ),
            category=category,
            category_label=category_label,
            goal=goal,
            goal_label=goal_label,
            candidates_searched=len(products),
        )
    return AlternativeSearchResult(
        status="ready",
        message=f"Found {len(selected)} database candidate{'s' if len(selected) != 1 else ''} better aligned with {goal_label.lower()}.",
        category=category,
        category_label=category_label,
        goal=goal,
        goal_label=goal_label,
        candidates_searched=len(products),
        alternatives=selected,
    )


def find_live_alternatives(
    current_label: ExtractedLabel,
    category: AlternativeCategory,
    goal: AlternativeGoal,
    profile: Optional[PersonalizationProfile] = None,
    current_barcode: Optional[str] = None,
    limit: int = 3,
) -> AlternativeSearchResult:
    category_label, search_query = CATEGORY_CONFIG[category]
    goal_label = GOAL_CONFIG[goal]["label"]
    if goal == "lower_added_sugar":
        # Do not spend a network request on a field that is not sufficiently
        # populated to support a responsible live comparison.
        return rank_alternatives([], current_label, category, goal, profile, current_barcode, limit)
    try:
        response = requests.post(
            SEARCH_API_URL,
            headers={"User-Agent": OFF_USER_AGENT, "Content-Type": "application/json"},
            json={
                "q": search_query,
                "page": 1,
                "page_size": SEARCH_PAGE_SIZE,
                "langs": ["en"],
                "fields": SEARCH_FIELDS,
            },
            timeout=SEARCH_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        products = payload.get("hits", [])
        if not isinstance(products, list):
            raise ValueError("Open Food Facts returned an unexpected search response.")
    except (requests.RequestException, ValueError) as exc:
        return AlternativeSearchResult(
            status="search_unavailable",
            message="The live product catalogue is temporarily unavailable. The confirmed FoodProof Fit result is unchanged.",
            category=category,
            category_label=category_label,
            goal=goal,
            goal_label=goal_label,
            evidence_note=f"Live search failed safely: {type(exc).__name__}. Try again later.",
        )
    return rank_alternatives(products, current_label, category, goal, profile, current_barcode, limit)
