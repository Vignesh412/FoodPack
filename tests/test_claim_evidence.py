from src.claim_evidence import evaluate_claims
from src.schemas import AllergenInfo, ExtractedLabel, FrontOfPackClaim, MassAmount, MassUnit, NutrientField


def test_low_sodium_claim_supported():
    label = ExtractedLabel(
        sodium=NutrientField(amount=MassAmount(value=100, unit=MassUnit.MILLIGRAM), percent_daily_value=4),
        front_claims=[FrontOfPackClaim(raw_text="Low Sodium")],
    )
    verdicts = evaluate_claims(label)
    assert verdicts[0].verdict == "supported"


def test_low_sodium_claim_contradicted():
    label = ExtractedLabel(
        sodium=NutrientField(amount=MassAmount(value=300, unit=MassUnit.MILLIGRAM), percent_daily_value=13),
        front_claims=[FrontOfPackClaim(raw_text="Low Sodium")],
    )
    verdicts = evaluate_claims(label)
    assert verdicts[0].verdict == "not_supported"


def test_no_added_sugar_contradicted_by_ingredients():
    label = ExtractedLabel(
        front_claims=[FrontOfPackClaim(raw_text="No Added Sugar")],
        allergens=AllergenInfo(raw_ingredient_text="Oats, cane sugar, salt"),
    )
    verdicts = evaluate_claims(label)
    assert verdicts[0].verdict == "not_supported"


def test_no_added_sugar_supported_when_no_sugar_terms_present():
    label = ExtractedLabel(
        front_claims=[FrontOfPackClaim(raw_text="No Added Sugar")],
        allergens=AllergenInfo(raw_ingredient_text="Oats, almonds, sea salt"),
    )
    verdicts = evaluate_claims(label)
    assert verdicts[0].verdict == "supported"


def test_claim_never_declares_legal_compliance_language():
    label = ExtractedLabel(
        sodium=NutrientField(amount=MassAmount(value=300, unit=MassUnit.MILLIGRAM), percent_daily_value=13),
        front_claims=[FrontOfPackClaim(raw_text="Low Sodium")],
    )
    verdicts = evaluate_claims(label)
    forbidden_terms = ["violat", "illegal", "complies with the law", "against the law"]
    rationale_lower = verdicts[0].rationale.lower()
    assert not any(term in rationale_lower for term in forbidden_terms)


def test_missing_nutrient_gives_insufficient_evidence():
    label = ExtractedLabel(front_claims=[FrontOfPackClaim(raw_text="Low Sodium")])
    verdicts = evaluate_claims(label)
    assert verdicts[0].verdict == "insufficient_evidence"
