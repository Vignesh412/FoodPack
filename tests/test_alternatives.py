from src.alternatives import AlternativeCategory, find_live_alternatives, rank_alternatives
from src.sample_data import snack_bar_scenario_1
from src.schemas import PersonalizationProfile


def _product(
    code: str,
    name: str,
    *,
    sodium_g: float = 0.1,
    fibre_g: float = 5,
    allergens: list[str] | None = None,
    countries: list[str] | None = None,
    diet_tags: list[str] | None = None,
    category_tags: list[str] | None = None,
) -> dict:
    return {
        "code": code,
        "product_name": name,
        "brands": ["Example Brand"],
        "nutriments": {"sodium_100g": sodium_g, "fiber_100g": fibre_g},
        "allergens_tags": allergens or [],
        "ingredients_analysis_tags": diet_tags or [],
        "countries_tags": countries or ["en:united-states"],
        "categories_tags": category_tags or ["en:snack-bars"],
        "completeness": 0.8,
    }


def test_lower_sodium_candidates_are_ranked_deterministically():
    current = snack_bar_scenario_1().model_copy(update={"user_confirmed": True})
    result = rank_alternatives(
        [
            _product("11111111", "Lower Sodium Bar", sodium_g=0.05),
            _product("22222222", "Medium Sodium Bar", sodium_g=0.15),
            _product("33333333", "Non US Bar", sodium_g=0.01, countries=["en:canada"]),
        ],
        current,
        AlternativeCategory.SNACK_BARS,
        "lower_sodium",
    )

    assert result.status == "ready"
    assert [item.product_name for item in result.alternatives] == ["Lower Sodium Bar", "Medium Sodium Bar"]
    assert result.alternatives[0].value_per_100g == 50


def test_allergen_conflict_is_excluded_without_claiming_clearance():
    current = snack_bar_scenario_1().model_copy(update={"user_confirmed": True})
    profile = PersonalizationProfile(declared_allergens=["milk"])
    result = rank_alternatives(
        [
            _product("11111111", "Milk Bar", allergens=["en:milk"]),
            _product("22222222", "Candidate With Evidence", allergens=["en:soybeans"]),
            _product("33333333", "Candidate With Unknown Allergens"),
        ],
        current,
        AlternativeCategory.SNACK_BARS,
        "lower_sodium",
        profile,
    )

    names = [item.product_name for item in result.alternatives]
    assert "Milk Bar" not in names
    assert "Candidate With Evidence" in names
    assert next(item for item in result.alternatives if item.product_name == "Candidate With Evidence").allergen_status == "no_declared_match"
    assert next(item for item in result.alternatives if item.product_name == "Candidate With Unknown Allergens").allergen_status == "not_verified"


def test_added_sugar_refuses_to_use_total_sugar_as_a_substitute():
    current = snack_bar_scenario_1().model_copy(update={"user_confirmed": True})
    result = rank_alternatives(
        [_product("11111111", "Example Bar")],
        current,
        AlternativeCategory.SNACK_BARS,
        "lower_added_sugar",
    )

    assert result.status == "unsupported_goal"
    assert "will not substitute total sugar" in result.message


def test_full_text_hit_from_wrong_category_is_excluded():
    current = snack_bar_scenario_1().model_copy(update={"user_confirmed": True})
    result = rank_alternatives(
        [_product("11111111", "Chocolate Cashews", sodium_g=0.01, category_tags=["en:cashew-nuts"])],
        current,
        AlternativeCategory.SNACK_BARS,
        "lower_sodium",
    )

    assert result.status == "no_reliable_candidates"


def test_missing_current_serving_weight_stops_comparison():
    current = snack_bar_scenario_1().model_copy(update={"user_confirmed": True})
    current.serving.grams_per_serving = None
    result = rank_alternatives(
        [_product("11111111", "Example Bar")],
        current,
        AlternativeCategory.SNACK_BARS,
        "higher_fibre",
    )

    assert result.status == "current_evidence_missing"


def test_live_search_identifies_the_app_and_limits_requested_fields(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"hits": [_product("11111111", "Live Candidate")]}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr("src.alternatives.requests.post", fake_post)
    current = snack_bar_scenario_1().model_copy(update={"user_confirmed": True})
    result = find_live_alternatives(current, AlternativeCategory.SNACK_BARS, "lower_sodium")

    assert result.status == "ready"
    assert captured["headers"]["User-Agent"].startswith("FoodProofFit/")
    assert captured["json"]["page_size"] == 40
    assert "nutriments" in captured["json"]["fields"]
    assert "categories_tags" in captured["json"]["fields"]


def test_unsupported_added_sugar_goal_does_not_call_live_catalogue(monkeypatch):
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("Live catalogue should not be called for an unsupported goal")

    monkeypatch.setattr("src.alternatives.requests.post", fail_if_called)
    current = snack_bar_scenario_1().model_copy(update={"user_confirmed": True})
    result = find_live_alternatives(current, AlternativeCategory.SNACK_BARS, "lower_added_sugar")

    assert result.status == "unsupported_goal"
    assert result.candidates_searched == 0
