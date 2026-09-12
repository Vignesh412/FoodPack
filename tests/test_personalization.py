from src.nutrition_rules import calculate_portion
from src.personalization import personalize
from src.sample_data import snack_bar_scenario_1
from src.schemas import PersonalizationProfile, PortionSelection


def test_declared_tree_nut_match_is_flagged_without_safety_clearance():
    label = snack_bar_scenario_1()
    calculation = calculate_portion(label, PortionSelection())
    result = personalize(label, calculation, PersonalizationProfile(declared_allergens=["almond"]))

    assert result.allergen_match.status == "declared_match"
    assert "tree nuts" in result.allergen_match.declared_matches
    assert "not an allergy-safety decision" in result.allergen_match.message


def test_advisory_peanut_match_is_flagged():
    label = snack_bar_scenario_1()
    calculation = calculate_portion(label, PortionSelection())
    result = personalize(label, calculation, PersonalizationProfile(declared_allergens=["peanuts"]))

    assert result.allergen_match.status == "advisory_match"
    assert "peanut" in result.allergen_match.advisory_matches


def test_daily_goal_contributions_use_actual_portion():
    label = snack_bar_scenario_1()
    calculation = calculate_portion(label, PortionSelection(servings_consumed=2))
    profile = PersonalizationProfile(
        daily_calorie_goal=2000,
        daily_protein_goal_g=50,
        daily_fibre_goal_g=28,
        daily_sodium_limit_mg=2300,
        daily_added_sugar_limit_g=50,
    )
    result = personalize(label, calculation, profile)
    by_key = {item.key: item for item in result.goal_contributions}

    assert by_key["calories"].consumed == 280
    assert by_key["calories"].percent_of_target == 14
    assert by_key["added_sugar"].consumed == 14
    assert by_key["added_sugar"].percent_of_target == 28


def test_vegan_preference_reports_possible_conflict_not_certification():
    label = snack_bar_scenario_1()
    calculation = calculate_portion(label, PortionSelection())
    result = personalize(label, calculation, PersonalizationProfile(dietary_preference="vegan"))

    assert result.dietary_preference.status == "possible_conflict"
    assert "honey" in result.dietary_preference.matched_terms


def test_missing_product_nutrient_omits_that_goal_contribution():
    label = snack_bar_scenario_1()
    label.fibre.amount = None
    calculation = calculate_portion(label, PortionSelection())
    result = personalize(label, calculation, PersonalizationProfile(daily_fibre_goal_g=28))

    assert not result.goal_contributions


def test_custom_allergen_term_can_be_matched_without_an_alias():
    label = snack_bar_scenario_1()
    label.allergens.declared_contains = ["mustard"]
    calculation = calculate_portion(label, PortionSelection())
    result = personalize(label, calculation, PersonalizationProfile(declared_allergens=["mustard"]))

    assert result.allergen_match.status == "declared_match"
    assert result.allergen_match.declared_matches == ["mustard"]
