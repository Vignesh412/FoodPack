"""Run FoodProof Fit's deterministic golden-set evaluation.

The report intentionally keeps real photographed products separate from the
automated metrics. A few integration examples prove that the path works, but
are not enough evidence for a general vision-accuracy claim.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.nutrition_rules import calculate_portion
from src.alternatives import AlternativeCategory, rank_alternatives
from src.personalization import personalize
from src.comparison import compare_products
from src.product_lookup import OFFLookupResult, compute_delta_flags
from src.rag_retriever import get_retriever
from src.safety_gate import evaluate_safety
from src.sample_data import cereal_a_scenario_2, cereal_b_scenario_2, snack_bar_scenario_1
from src.schemas import PersonalizationProfile, PortionSelection


SAFETY_SET = ROOT / "tests" / "golden_cases.json"
GOLDEN_SET = ROOT / "evals" / "golden_set.json"
REPORT_PATH = ROOT / "eval_results" / "latest.json"
WEB_REPORT_PATH = ROOT / "web" / "public" / "eval-report.json"

SCENARIOS = {
    "snack_bar": snack_bar_scenario_1,
    "cereal_a": cereal_a_scenario_2,
    "cereal_b": cereal_b_scenario_2,
}


def _metric(key: str, label: str, passed: int, total: int, target: str, direction: str = "minimum") -> dict[str, Any]:
    percent = round(passed / total * 100, 1) if total else 0.0
    return {
        "key": key,
        "label": label,
        "passed": passed,
        "total": total,
        "percent": percent,
        "target": target,
        "direction": direction,
        "gate_passed": passed == total,
    }


def build_report() -> dict[str, Any]:
    safety = json.loads(SAFETY_SET.read_text(encoding="utf-8"))
    golden = json.loads(GOLDEN_SET.read_text(encoding="utf-8"))

    unsafe_cases = safety["safety_direct_unsafe"] + safety["safety_adversarial"]
    unsafe_results = [
        {"id": case["id"], "passed": not evaluate_safety(case["question"]).allowed}
        for case in unsafe_cases
    ]
    answerable_results = [
        {"id": case["id"], "passed": evaluate_safety(case["question"]).allowed}
        for case in safety["safety_answerable"]
    ]

    calculation_results = []
    for case in golden["calculation_cases"]:
        calculation = calculate_portion(
            SCENARIOS[case["scenario"]](),
            PortionSelection(servings_consumed=case["servings"]),
        )
        if case["field"] == "calories":
            actual = calculation.calories_per_actual_portion
        else:
            amount = calculation.results[case["field"]].per_actual_portion
            actual = amount.value if amount else None
        calculation_results.append({
            "id": case["id"],
            "passed": actual is not None and abs(actual - case["expected"]) < 0.001,
            "expected": case["expected"],
            "actual": actual,
            "unit": case["unit"],
        })

    retrieval_results = []
    for case in golden["retrieval_cases"]:
        passages = get_retriever().retrieve(case["query"], goal=case["goal"])
        actual_top_id = passages[0].id if passages else None
        retrieval_results.append({
            "id": case["id"],
            "passed": actual_top_id == case["expected_top_id"],
            "expected": case["expected_top_id"],
            "actual": actual_top_id,
        })

    personalization_results = []
    label = snack_bar_scenario_1()
    calculation = calculate_portion(label, PortionSelection())
    for case in golden["personalization_cases"]:
        result = personalize(
            label,
            calculation,
            PersonalizationProfile(
                declared_allergens=case["allergens"],
                dietary_preference=case["preference"],
            ),
        )
        passed = (
            result.allergen_match.status == case["expected_allergen_status"]
            and result.dietary_preference.status == case["expected_diet_status"]
        )
        personalization_results.append({
            "id": case["id"],
            "passed": passed,
            "expected": f"{case['expected_allergen_status']} / {case['expected_diet_status']}",
            "actual": f"{result.allergen_match.status} / {result.dietary_preference.status}",
        })

    comparison_results = []
    comparison = compare_products(
        cereal_a_scenario_2(), PortionSelection(), "Golden Flakes",
        cereal_b_scenario_2(), PortionSelection(), "Morning Crunch",
    )
    comparison_without_weight_b = cereal_b_scenario_2()
    comparison_without_weight_b.serving.grams_per_serving = None
    missing_weight_comparison = compare_products(
        cereal_a_scenario_2(), PortionSelection(), "Golden Flakes",
        comparison_without_weight_b, PortionSelection(), "Morning Crunch",
    )
    for case in golden["comparison_cases"]:
        if case["check"] == "per_100g_available":
            actual = comparison.per_100g_available
        elif case["check"] == "product_a_added_sugar_per_100g":
            amount = comparison.product_a.calculation.results["added_sugar"].per_100g
            actual = amount.value if amount else None
        else:
            actual = missing_weight_comparison.per_100g_available
        comparison_results.append({
            "id": case["id"],
            "passed": actual == case["expected"],
            "expected": case["expected"],
            "actual": actual,
        })

    historical_barcode = OFFLookupResult(
        found=True,
        product_name="Golden Flakes historical record",
        per_100g={"sodium": 500.0, "added_sugar": 30.0},
    )
    barcode_inputs = {
        "within_tolerance": {"sodium": 530.0, "added_sugar": 29.0},
        "meaningful_mismatch": {"sodium": 700.0, "added_sugar": 29.0},
    }
    barcode_results = []
    for case in golden["barcode_cases"]:
        flags = compute_delta_flags(barcode_inputs[case["check"]], historical_barcode)
        actual = len(flags)
        barcode_results.append({
            "id": case["id"],
            "passed": actual == case["expected_flags"],
            "expected": case["expected_flags"],
            "actual": actual,
        })

    def alternative_product(
        code: str,
        name: str,
        *,
        sodium_g: float = 0.05,
        category_tags: list[str] | None = None,
        allergens: list[str] | None = None,
    ) -> dict[str, Any]:
        return {
            "code": code,
            "product_name": name,
            "brands": ["Golden Set Brand"],
            "nutriments": {"sodium_100g": sodium_g, "fiber_100g": 7},
            "allergens_tags": allergens or [],
            "ingredients_analysis_tags": [],
            "countries_tags": ["en:united-states"],
            "categories_tags": category_tags or ["en:snack-bars"],
            "completeness": 0.9,
        }

    alternative_results = []
    for case in golden["alternative_cases"]:
        current = snack_bar_scenario_1().model_copy(deep=True, update={"user_confirmed": True})
        check = case["check"]
        if check == "lower_sodium_ranking":
            result = rank_alternatives(
                [
                    alternative_product("11111111", "Low Sodium Bar", sodium_g=0.03),
                    alternative_product("22222222", "Medium Sodium Bar", sodium_g=0.12),
                ],
                current,
                AlternativeCategory.SNACK_BARS,
                "lower_sodium",
            )
            actual = result.alternatives[0].product_name if result.alternatives else result.status
        elif check == "category_relevance_gate":
            result = rank_alternatives(
                [alternative_product("33333333", "Chocolate Cashews", sodium_g=0.01, category_tags=["en:cashew-nuts"])],
                current,
                AlternativeCategory.SNACK_BARS,
                "lower_sodium",
            )
            actual = result.status
        elif check == "allergen_conflict_exclusion":
            result = rank_alternatives(
                [
                    alternative_product("44444444", "Milk Bar", allergens=["en:milk"]),
                    alternative_product("55555555", "Candidate With Evidence", allergens=["en:soybeans"]),
                ],
                current,
                AlternativeCategory.SNACK_BARS,
                "lower_sodium",
                PersonalizationProfile(declared_allergens=["milk"]),
            )
            actual = result.alternatives[0].product_name if result.alternatives else result.status
        elif check == "added_sugar_refusal":
            result = rank_alternatives(
                [alternative_product("66666666", "Sugar Unknown Bar")],
                current,
                AlternativeCategory.SNACK_BARS,
                "lower_added_sugar",
            )
            actual = result.status
        else:
            current.serving.grams_per_serving = None
            result = rank_alternatives(
                [alternative_product("77777777", "Fibre Bar")],
                current,
                AlternativeCategory.SNACK_BARS,
                "higher_fibre",
            )
            actual = result.status
        alternative_results.append({
            "id": case["id"],
            "passed": actual == case["expected"],
            "expected": case["expected"],
            "actual": actual,
        })

    metrics = [
        _metric("safe_refusal_recall", "Unsafe requests correctly refused", sum(item["passed"] for item in unsafe_results), len(unsafe_results), "100%"),
        _metric("answerable_pass_rate", "Answerable requests correctly allowed", sum(item["passed"] for item in answerable_results), len(answerable_results), "100%"),
        _metric("calculation_exactness", "Portion calculations exact", sum(item["passed"] for item in calculation_results), len(calculation_results), "100%"),
        _metric("retrieval_top_hit", "Expected FDA source ranked first", sum(item["passed"] for item in retrieval_results), len(retrieval_results), "100%"),
        _metric("personalization_accuracy", "Personalization outcomes correct", sum(item["passed"] for item in personalization_results), len(personalization_results), "100%"),
        _metric("comparison_exactness", "Fair-comparison rules correct", sum(item["passed"] for item in comparison_results), len(comparison_results), "100%"),
        _metric("barcode_delta_rules", "Barcode cross-check rules correct", sum(item["passed"] for item in barcode_results), len(barcode_results), "100%"),
        _metric("alternative_safety_rules", "Alternative-finder rules correct", sum(item["passed"] for item in alternative_results), len(alternative_results), "100%"),
    ]
    total_passed = sum(item["passed"] for item in unsafe_results + answerable_results + calculation_results + retrieval_results + personalization_results + comparison_results + barcode_results + alternative_results)
    total_cases = len(unsafe_results) + len(answerable_results) + len(calculation_results) + len(retrieval_results) + len(personalization_results) + len(comparison_results) + len(barcode_results) + len(alternative_results)
    automated_gates_pass = all(metric["gate_passed"] for metric in metrics)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "automated_gates_pass": automated_gates_pass,
            "passed": total_passed,
            "total": total_cases,
            "headline": f"{total_passed}/{total_cases} automated golden cases passed",
            "image_readiness": "limited",
            "image_note": "Four photographed US product sets completed the full path. A fifth was correctly rejected because its Nutrition Facts image was below the minimum resolution. This small, non-random set is still not enough for a general vision-accuracy rate.",
        },
        "metrics": metrics,
        "suites": {
            "unsafe_requests": unsafe_results,
            "answerable_requests": answerable_results,
            "calculations": calculation_results,
            "retrieval": retrieval_results,
            "personalization": personalization_results,
            "comparison": comparison_results,
            "barcode": barcode_results,
            "alternatives": alternative_results,
        },
        "vision_evidence": {
            "attempted_product_sets": 5,
            "completed_end_to_end": 4,
            "retake_requested": 1,
            "accuracy_rate_published": False,
            "cases": [
                {"product": "Nature Valley Oats 'N Honey", "outcome": "completed", "note": "Selected label facts matched manual review."},
                {"product": "Campbell's Cream of Mushroom", "outcome": "completed", "note": "Milk match found; missing gram weight stayed unknown."},
                {"product": "CLIF Bar variety pack", "outcome": "completed", "note": "Peanut declared-allergen match found."},
                {"product": "Premium Original Saltine Crackers", "outcome": "completed", "note": "Wide ingredients panel accepted; wheat profile match and selected facts verified."},
                {"product": "Doritos Nacho Cheese", "outcome": "retake", "note": "Nutrition image rejected at 562 × 1200 pixels."},
            ],
        },
        "failure_taxonomy": [
            "blurred, cropped, dark, or reflective images",
            "missing serving weight or nutrient values",
            "allergen aliases and ambiguous ingredient names",
            "unsafe medical or allergy-safety requests",
            "irrelevant or unresolved evidence citations",
            "misleading serving-size comparisons or missing weight evidence",
            "irrelevant, incomplete, or unsafe alternative-product candidates",
        ],
    }


def main() -> None:
    report = build_report()
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    WEB_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(payload, encoding="utf-8")
    WEB_REPORT_PATH.write_text(payload, encoding="utf-8")
    print(report["summary"]["headline"])
    print(f"Automated gates: {'PASS' if report['summary']['automated_gates_pass'] else 'FAIL'}")
    print("Vision extraction readiness: LIMITED - 4 completed product sets, 1 correct retake request")


if __name__ == "__main__":
    main()
