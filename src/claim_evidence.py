"""
Marketing Evidence Review: places front-of-pack claims beside the
confirmed Nutrition Facts and ingredient evidence. Per the roadmap, this
module may explain what the label shows, but it must never declare that
a manufacturer has complied with or violated the law — every verdict is
phrased as "consistent with" / "not consistent with" a named FDA
reference threshold, with an explicit caveat when we can't check at all.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

from src.schemas import ExtractedLabel, FrontOfPackClaim

Verdict = Literal["supported", "not_supported", "insufficient_evidence"]

# Deterministic keyword classifier for claim type. Kept intentionally
# narrow and literal — an LLM would over-generalize on marketing phrasing
# that this project does not need to interpret creatively.
_CLAIM_KEYWORD_MAP: dict[str, list[str]] = {
    "low_sodium": ["low sodium", "low salt"],
    "sodium_free": ["sodium free", "no sodium"],
    "low_saturated_fat": ["low saturated fat"],
    "saturated_fat_free": ["saturated fat free"],
    "good_source_fiber": ["good source of fiber", "good source of fibre"],
    "high_fiber": ["high fiber", "high fibre", "excellent source of fiber", "rich in fiber"],
    "sugar_free": ["sugar free", "no sugar"],
    "no_added_sugar": ["no added sugar", "no added sugars", "unsweetened"],
}

_ADDED_SUGAR_INGREDIENT_TERMS = [
    "sugar", "syrup", "honey", "dextrose", "sucrose", "fructose",
    "concentrated fruit juice", "concentrated juice", "cane juice", "maltose",
]


class ClaimVerdict(BaseModel):
    claim_text: str
    claim_type: Optional[str]
    verdict: Verdict
    rationale: str
    citation_ids: list[str] = []


def classify_claim(claim: FrontOfPackClaim) -> Optional[str]:
    if claim.claim_type:
        return claim.claim_type
    lowered = claim.raw_text.lower()
    for claim_type, phrases in _CLAIM_KEYWORD_MAP.items():
        if any(phrase in lowered for phrase in phrases):
            return claim_type
    return None


def _verdict(verdict: Verdict, rationale: str, citations: list[str]) -> tuple[Verdict, str, list[str]]:
    return verdict, rationale, citations


def _evaluate_one(claim_type: str, label: ExtractedLabel) -> tuple[Verdict, str, list[str]]:
    if claim_type == "low_sodium":
        field = label.sodium
        if field.amount is None:
            return _verdict("insufficient_evidence", "Sodium was not confirmed on this label.", [])
        mg = field.amount.to_grams() * 1000
        if mg <= 140:
            return _verdict(
                "supported",
                f"Confirmed sodium is {mg:.0f} mg per labelled serving, at or under the FDA's "
                "140 mg reference threshold for a low-sodium claim. This checks the labelled "
                "serving, not necessarily the FDA reference amount for this food category.",
                ["claim-001"],
            )
        return _verdict(
            "not_supported",
            f"Confirmed sodium is {mg:.0f} mg per labelled serving, above the FDA's 140 mg "
            "low-sodium reference threshold. This is informational, not a compliance finding.",
            ["claim-001"],
        )

    if claim_type == "sodium_free":
        field = label.sodium
        if field.amount is None:
            return _verdict("insufficient_evidence", "Sodium was not confirmed on this label.", [])
        mg = field.amount.to_grams() * 1000
        if mg < 5:
            return _verdict("supported", f"Confirmed sodium is {mg:.1f} mg, under the 5 mg free-claim threshold.", ["claim-003"])
        return _verdict("not_supported", f"Confirmed sodium is {mg:.1f} mg, at or above the 5 mg free-claim threshold.", ["claim-003"])

    if claim_type == "low_saturated_fat":
        field = label.saturated_fat
        if field.amount is None:
            return _verdict("insufficient_evidence", "Saturated fat was not confirmed on this label.", [])
        grams = field.amount.to_grams()
        return _verdict(
            "insufficient_evidence",
            f"Confirmed saturated fat is {grams:.2f} g per labelled serving, but this prototype "
            "does not have the FDA reference amount or the percentage of calories from saturated "
            "fat needed to check the complete low-saturated-fat rule.",
            ["claim-002"],
        )

    if claim_type == "saturated_fat_free":
        field = label.saturated_fat
        if field.amount is None:
            return _verdict("insufficient_evidence", "Saturated fat was not confirmed on this label.", [])
        grams = field.amount.to_grams()
        return _verdict(
            "insufficient_evidence",
            f"Confirmed saturated fat is {grams:.2f} g per labelled serving, but trans fat and the "
            "FDA reference amount are also needed to check the complete saturated-fat-free rule.",
            ["claim-003"],
        )

    if claim_type in ("good_source_fiber", "high_fiber"):
        field = label.fibre
        if field.percent_daily_value is None:
            return _verdict("insufficient_evidence", "Fibre %DV was not confirmed on this label.", [])
        dv = field.percent_daily_value
        if claim_type == "good_source_fiber" and 10 <= dv < 20:
            return _verdict("supported", f"Confirmed fibre is {dv:.0f}% DV, within the 10%–19% DV good-source reference range.", ["claim-005"])
        if claim_type == "high_fiber" and dv >= 20:
            return _verdict("supported", f"Confirmed fibre is {dv:.0f}% DV, meeting the 20% DV high/excellent-source reference.", ["claim-005"])
        if claim_type == "good_source_fiber" and dv >= 20:
            return _verdict("not_supported", f"Confirmed fibre is {dv:.0f}% DV, outside the 10%–19% DV good-source reference range and within the separate high range.", ["claim-005"])
        return _verdict("not_supported", f"Confirmed fibre is {dv:.0f}% DV, below the reference range for this claim.", ["claim-005"])

    if claim_type == "sugar_free":
        return _verdict(
            "insufficient_evidence",
            "A sugar-free claim depends on total sugars and FDA reference-amount conditions. "
            "This prototype captures added sugar, which is not enough to check that claim safely.",
            ["claim-003"],
        )

    if claim_type == "no_added_sugar":
        ingredient_text = (label.allergens.raw_ingredient_text or "").lower()
        if not ingredient_text:
            return _verdict("insufficient_evidence", "Ingredient list was not confirmed, so this claim can't be checked against ingredients.", [])
        found = [term for term in _ADDED_SUGAR_INGREDIENT_TERMS if term in ingredient_text]
        if found:
            return _verdict(
                "not_supported",
                f"Ingredient list includes {', '.join(found)}, which reads as an added-sugar "
                "source alongside a \"no added sugar\" claim on the front of the package.",
                ["nfl-002"],
            )
        return _verdict("supported", "No added-sugar ingredient terms were found in the confirmed ingredient list.", ["nfl-002"])

    return _verdict("insufficient_evidence", "This claim type is not yet covered by an automated check.", [])


def evaluate_claims(label: ExtractedLabel) -> list[ClaimVerdict]:
    results: list[ClaimVerdict] = []
    for claim in label.front_claims:
        claim_type = classify_claim(claim)
        if claim_type is None:
            results.append(
                ClaimVerdict(
                    claim_text=claim.raw_text,
                    claim_type=None,
                    verdict="insufficient_evidence",
                    rationale="This claim wasn't recognized by the prototype's claim checker.",
                )
            )
            continue
        verdict, rationale, citations = _evaluate_one(claim_type, label)
        results.append(
            ClaimVerdict(
                claim_text=claim.raw_text,
                claim_type=claim_type,
                verdict=verdict,
                rationale=rationale,
                citation_ids=citations,
            )
        )
    return results
