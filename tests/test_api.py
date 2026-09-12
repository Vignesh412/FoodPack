from io import BytesIO

from PIL import Image
from fastapi.testclient import TestClient

import api as api_module
from api import app
from src.sample_data import cereal_a_scenario_2, cereal_b_scenario_2, snack_bar_scenario_1


client = TestClient(app)


def _small_png() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (80, 80), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def test_health():
    response = client.get("/health")
    assert response.json() == {"status": "ok"}
    assert response.headers["x-request-id"]


def test_hosted_service_token_protects_paid_endpoints_but_not_health(monkeypatch):
    monkeypatch.setattr(api_module, "API_TOKEN", "test-service-token")
    label = snack_bar_scenario_1().model_copy(update={"user_confirmed": True})
    payload = {"label": label.model_dump(mode="json"), "servings_consumed": 1}

    assert client.get("/health").status_code == 200
    assert client.post("/v1/analyze", json=payload).status_code == 401
    authorized = client.post(
        "/v1/analyze",
        json=payload,
        headers={"Authorization": "Bearer test-service-token"},
    )

    assert authorized.status_code == 200
    assert authorized.headers["x-request-id"]


def test_extract_rejects_low_resolution_before_model_call():
    image = _small_png()
    files = {
        "front": ("front.png", image, "image/png"),
        "nutrition": ("nutrition.png", image, "image/png"),
        "ingredients": ("ingredients.png", image, "image/png"),
    }
    response = client.post("/v1/extract", files=files)
    assert response.status_code == 422


def test_analyze_rejects_a_label_the_user_has_not_confirmed():
    label = snack_bar_scenario_1().model_copy(update={"user_confirmed": False})
    response = client.post(
        "/v1/analyze",
        json={"label": label.model_dump(mode="json"), "servings_consumed": 1},
    )
    assert response.status_code == 422
    assert "Confirm the extracted label values" in response.json()["detail"]


def test_analyze_accepts_an_explicitly_confirmed_label():
    label = snack_bar_scenario_1().model_copy(update={"user_confirmed": True})
    response = client.post(
        "/v1/analyze",
        json={"label": label.model_dump(mode="json"), "servings_consumed": 1},
    )
    assert response.status_code == 200
    assert response.json()["evidence_card"]["refused"] is False


def test_two_confirmed_products_return_different_visible_evidence_values():
    snack = snack_bar_scenario_1().model_copy(update={"user_confirmed": True})
    cereal = cereal_a_scenario_2().model_copy(update={"user_confirmed": True})

    snack_card = client.post(
        "/v1/analyze",
        json={"label": snack.model_dump(mode="json"), "servings_consumed": 1, "goal": "lower_sodium"},
    ).json()["evidence_card"]
    cereal_card = client.post(
        "/v1/analyze",
        json={"label": cereal.model_dump(mode="json"), "servings_consumed": 1, "goal": "lower_sodium"},
    ).json()["evidence_card"]

    assert snack_card["product_name"] != cereal_card["product_name"]
    assert (
        snack_card["calculation"]["results"]["sodium"]["per_actual_portion"]["value"]
        != cereal_card["calculation"]["results"]["sodium"]["per_actual_portion"]["value"]
    )


def test_compare_endpoint_normalizes_two_confirmed_products():
    product_a = cereal_a_scenario_2().model_copy(update={"user_confirmed": True})
    product_b = cereal_b_scenario_2().model_copy(update={"user_confirmed": True})

    response = client.post(
        "/v1/compare",
        json={
            "product_a": {"label": product_a.model_dump(mode="json"), "name": "Golden Flakes", "servings_consumed": 1},
            "product_b": {"label": product_b.model_dump(mode="json"), "name": "Morning Crunch", "servings_consumed": 1},
        },
    )

    assert response.status_code == 200
    comparison = response.json()
    assert comparison["per_100g_available"] is True
    assert comparison["product_a"]["calculation"]["results"]["added_sugar"]["per_100g"]["value"] == 30
    assert comparison["product_b"]["calculation"]["results"]["added_sugar"]["per_100g"]["value"] == 18.182


def test_compare_endpoint_requires_both_labels_to_be_confirmed():
    product_a = cereal_a_scenario_2().model_copy(update={"user_confirmed": True})
    product_b = cereal_b_scenario_2()

    response = client.post(
        "/v1/compare",
        json={
            "product_a": {"label": product_a.model_dump(mode="json"), "name": "Golden Flakes"},
            "product_b": {"label": product_b.model_dump(mode="json"), "name": "Morning Crunch"},
        },
    )

    assert response.status_code == 422
    assert "Confirm the label values" in response.json()["detail"]


def test_alternatives_endpoint_requires_a_confirmed_current_label():
    label = snack_bar_scenario_1().model_copy(update={"user_confirmed": False})
    response = client.post(
        "/v1/alternatives",
        json={"label": label.model_dump(mode="json"), "category": "snack_bars", "goal": "lower_sodium"},
    )

    assert response.status_code == 422
    assert "Confirm the current product label" in response.json()["detail"]


def test_alternatives_endpoint_returns_the_bounded_search_result(monkeypatch):
    label = snack_bar_scenario_1().model_copy(update={"user_confirmed": True})

    def fake_find_live_alternatives(**kwargs):
        from src.alternatives import AlternativeSearchResult

        assert kwargs["current_label"].user_confirmed is True
        return AlternativeSearchResult(
            status="no_reliable_candidates",
            message="No sufficiently complete candidates were found.",
            category="snack_bars",
            category_label="Snack bars",
            goal="lower_sodium",
            goal_label="Lower sodium",
        )

    monkeypatch.setattr("api.find_live_alternatives", fake_find_live_alternatives)
    response = client.post(
        "/v1/alternatives",
        json={"label": label.model_dump(mode="json"), "category": "snack_bars", "goal": "lower_sodium"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "no_reliable_candidates"


def test_analyze_returns_deterministic_personalized_goal_and_allergen_results():
    label = snack_bar_scenario_1().model_copy(update={"user_confirmed": True})
    response = client.post(
        "/v1/analyze",
        json={
            "label": label.model_dump(mode="json"),
            "servings_consumed": 1,
            "goal": "higher_fibre",
            "profile": {
                "declared_allergens": ["almond"],
                "dietary_preference": "vegan",
                "daily_calorie_goal": 2000,
                "daily_protein_goal_g": 50,
                "daily_fibre_goal_g": 28,
                "daily_sodium_limit_mg": 2300,
                "daily_added_sugar_limit_g": 50,
            },
        },
    )
    personalization = response.json()["evidence_card"]["personalization"]

    assert response.status_code == 200
    assert personalization["allergen_match"]["status"] == "declared_match"
    assert personalization["dietary_preference"]["status"] == "possible_conflict"
    assert len(personalization["goal_contributions"]) == 5


def test_analyze_passes_a_valid_barcode_to_the_workflow(monkeypatch):
    captured = {}

    def fake_run_workflow(**kwargs):
        captured.update(kwargs)
        return {"evidence_card": {"refused": False}, "trace": []}

    monkeypatch.setattr("api.run_workflow", fake_run_workflow)
    label = snack_bar_scenario_1().model_copy(update={"user_confirmed": True})
    response = client.post(
        "/v1/analyze",
        json={"label": label.model_dump(mode="json"), "barcode": "0016000264694"},
    )

    assert response.status_code == 200
    assert captured["barcode"] == "0016000264694"


def test_analyze_rejects_an_invalid_barcode_before_the_workflow():
    label = snack_bar_scenario_1().model_copy(update={"user_confirmed": True})
    response = client.post(
        "/v1/analyze",
        json={"label": label.model_dump(mode="json"), "barcode": "123"},
    )

    assert response.status_code == 422
