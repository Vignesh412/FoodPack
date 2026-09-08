from src.sample_data import cereal_a_scenario_2, cereal_b_scenario_2, cropped_scenario_3, snack_bar_scenario_1
from src.schemas import PortionSelection
from src.workflow import run_workflow


def test_informational_run_is_not_blocked_and_has_trace():
    result = run_workflow(snack_bar_scenario_1(), PortionSelection(servings_consumed=1), goal="higher_fibre")
    assert result["evidence_card"]["refused"] is False
    assert len(result["trace"]) >= 4


def test_unsafe_question_blocks_before_calculation():
    result = run_workflow(
        snack_bar_scenario_1(), PortionSelection(), question="Is this safe for my diabetic child?"
    )
    assert result["evidence_card"]["refused"] is True
    # Blocked requests route straight from the safety gate to the evidence
    # card via the conditional edge, so the tool nodes never run at all —
    # not "run and no-op". Confirm none of their outputs were populated.
    assert result.get("calculation") is None
    assert result.get("retrieved_passages") is None
    assert result.get("claim_verdicts") is None
    assert any("BLOCKED" in line for line in result["trace"])
    assert not any(line.startswith("Calculation:") for line in result["trace"])


def test_comparison_scenario_normalizes_per_100g():
    result = run_workflow(
        cereal_a_scenario_2(), PortionSelection(), second_label=cereal_b_scenario_2(),
        second_portion=PortionSelection(), first_name="Golden Flakes", second_name="Morning Crunch",
    )
    comparison = result["evidence_card"]["comparison"]
    assert comparison is not None
    assert comparison.per_100g_available is True


def test_cropped_scenario_still_produces_a_card_with_missing_fields_listed():
    result = run_workflow(cropped_scenario_3(), PortionSelection())
    assert result["evidence_card"]["refused"] is False
    assert len(result["evidence_card"]["missing_fields"]) > 0


def test_portion_scaling_flows_through_the_whole_workflow():
    result_1x = run_workflow(snack_bar_scenario_1(), PortionSelection(servings_consumed=1))
    result_2x = run_workflow(snack_bar_scenario_1(), PortionSelection(servings_consumed=2))
    sugar_1x = result_1x["evidence_card"]["calculation"].results["added_sugar"].per_actual_portion.value
    sugar_2x = result_2x["evidence_card"]["calculation"].results["added_sugar"].per_actual_portion.value
    assert sugar_2x == sugar_1x * 2
