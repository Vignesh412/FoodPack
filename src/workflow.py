"""
Step 8: connects the tool modules with LangGraph.

Design choice, stated explicitly rather than left implicit: tool
*selection* here is rule-based on which optional inputs are present
(a barcode, a second product, a free-text question), not an LLM decision.
Genuine model judgment is reserved for vision classification and
extraction (Steps 4-5) and, optionally, ambiguous safety phrasing
(src/safety_gate.py's needs_llm_review path). The safety gate and the
final evidence-card assembly are fixed nodes every run passes through —
routing around them is not possible from within the graph. Every node
appends a line to the shared trace, which is what the UI renders as the
"visible workflow trace" panel.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Optional, TypedDict

from langgraph.graph import END, StateGraph

from src.claim_evidence import ClaimVerdict, evaluate_claims
from src.comparison import ComparisonResult, compare_products
from src.nutrition_rules import PortionCalculation, calculate_portion
from src.product_lookup import DeltaFlag, OFFLookupResult, compute_delta_flags, lookup_barcode
from src.rag_retriever import RetrievedPassage, get_retriever
from src.safety_gate import SafetyDecision, evaluate_safety
from src.schemas import ExtractedLabel, PortionSelection


class WorkflowState(TypedDict, total=False):
    # inputs
    label: ExtractedLabel
    portion: PortionSelection
    goal: Optional[str]
    question: Optional[str]
    barcode: Optional[str]
    second_label: Optional[ExtractedLabel]
    second_portion: Optional[PortionSelection]
    first_name: str
    second_name: Optional[str]

    # accumulated trace (list-concatenating reducer, so every node's log
    # line is appended rather than overwriting the previous ones)
    trace: Annotated[list[str], operator.add]

    # per-node outputs
    safety_decision: Optional[SafetyDecision]
    blocked: bool
    calculation: Optional[PortionCalculation]
    retrieved_passages: Optional[list[RetrievedPassage]]
    claim_verdicts: Optional[list[ClaimVerdict]]
    off_lookup: Optional[OFFLookupResult]
    delta_flags: Optional[list[DeltaFlag]]
    comparison: Optional[ComparisonResult]
    evidence_card: Optional[dict[str, Any]]


def node_safety_check(state: WorkflowState) -> dict:
    question = state.get("question")
    if not question:
        return {
            "blocked": False,
            "safety_decision": None,
            "trace": ["Safety gate: no free-text question asked — informational label walkthrough only."],
        }

    decision = evaluate_safety(question)
    if decision.allowed:
        log = f"Safety gate: question passed ({decision.intent.rationale})."
    else:
        log = f"Safety gate: BLOCKED — {decision.message}"
    return {"safety_decision": decision, "blocked": not decision.allowed, "trace": [log]}


def node_calculate(state: WorkflowState) -> dict:
    if state.get("blocked"):
        return {"trace": ["Calculation: skipped — safety gate blocked this request."]}
    calc = calculate_portion(state["label"], state["portion"])
    return {
        "calculation": calc,
        "trace": [f"Calculation: recomputed {len(calc.results)} nutrients for {state['portion'].servings_consumed:g} serving(s)."],
    }


def node_retrieve(state: WorkflowState) -> dict:
    if state.get("blocked"):
        return {"trace": ["FDA retrieval: skipped — request was blocked."]}
    goal = state.get("goal")
    if not goal:
        return {"trace": ["FDA retrieval: skipped — no nutrition goal selected."]}
    query = state.get("question") or goal.replace("_", " ")
    passages = get_retriever().retrieve(query, goal=goal)
    if passages:
        log = f"FDA retrieval: {len(passages)} passage(s) retrieved for goal '{goal}' (top: {passages[0].section})."
    else:
        log = f"FDA retrieval: no passage cleared the relevance threshold for goal '{goal}'."
    return {"retrieved_passages": passages, "trace": [log]}


def node_claims(state: WorkflowState) -> dict:
    if state.get("blocked"):
        return {"trace": ["Claim evidence: skipped — request was blocked."]}
    label = state["label"]
    if not label.front_claims:
        return {"trace": ["Claim evidence: skipped — no front-of-pack claims were captured."]}
    verdicts = evaluate_claims(label)
    return {
        "claim_verdicts": verdicts,
        "trace": [f"Claim evidence: checked {len(verdicts)} front-of-pack claim(s) against confirmed values."],
    }


def node_barcode(state: WorkflowState) -> dict:
    if state.get("blocked"):
        return {"trace": ["Barcode lookup: skipped — request was blocked."]}
    barcode = state.get("barcode")
    if not barcode:
        return {"trace": ["Barcode lookup: skipped — no barcode provided."]}

    result = lookup_barcode(barcode)
    if not result.found:
        return {"off_lookup": result, "trace": [f"Barcode lookup: no historical record found ({result.raw_error})."]}

    calc: Optional[PortionCalculation] = state.get("calculation")
    fresh_per_100g: dict[str, float] = {}
    if calc:
        for name, res in calc.results.items():
            if res.per_100g is not None:
                fresh_per_100g[name] = res.per_100g.value

    flags = compute_delta_flags(fresh_per_100g, result)
    if flags:
        log = f"Barcode delta-check: {len(flags)} nutrient(s) differ from the historical record by 20%+ — flagged, photo still treated as primary evidence."
    else:
        log = "Barcode delta-check: fresh values are consistent with the historical record."
    return {"off_lookup": result, "delta_flags": flags, "trace": [log]}


def node_compare(state: WorkflowState) -> dict:
    if state.get("blocked"):
        return {"trace": ["Comparison: skipped — request was blocked."]}
    second_label = state.get("second_label")
    if second_label is None:
        return {"trace": ["Comparison: skipped — only one product was provided."]}

    name_a = state.get("first_name", "Product A")
    name_b = state.get("second_name") or "Product B"
    result = compare_products(
        state["label"], state["portion"], name_a,
        second_label, state.get("second_portion") or PortionSelection(), name_b,
    )
    availability = "available" if result.per_100g_available else "refused (missing weight data)"
    return {
        "comparison": result,
        "trace": [f"Comparison: {name_a} vs {name_b} normalized per serving, per portion, and per 100g ({availability})."],
    }


def node_build_evidence_card(state: WorkflowState) -> dict:
    if state.get("blocked"):
        decision: SafetyDecision = state["safety_decision"]
        card = {"refused": True, "message": decision.message, "category": decision.intent.category}
        return {"evidence_card": card, "trace": ["Evidence Card: refusal message assembled — no nutrient data disclosed for an unsafe request."]}

    label: ExtractedLabel = state["label"]
    card = {
        "refused": False,
        "product_name": label.product_name,
        "missing_fields": label.missing_fields,
        "calculation": state.get("calculation"),
        "citations": state.get("retrieved_passages") or [],
        "claim_verdicts": state.get("claim_verdicts") or [],
        "delta_flags": state.get("delta_flags") or [],
        "comparison": state.get("comparison"),
    }
    return {"evidence_card": card, "trace": ["Evidence Card: assembled with citations, uncertainty, and missing-field notes."]}


def _route_after_safety(state: WorkflowState) -> str:
    return "evidence_card" if state.get("blocked") else "calculate"


def build_workflow():
    graph = StateGraph(WorkflowState)
    graph.add_node("safety_check", node_safety_check)
    graph.add_node("calculate", node_calculate)
    graph.add_node("retrieve", node_retrieve)
    graph.add_node("claims", node_claims)
    graph.add_node("barcode", node_barcode)
    graph.add_node("compare", node_compare)
    graph.add_node("evidence_card", node_build_evidence_card)

    graph.set_entry_point("safety_check")
    graph.add_conditional_edges(
        "safety_check", _route_after_safety, {"evidence_card": "evidence_card", "calculate": "calculate"}
    )
    graph.add_edge("calculate", "retrieve")
    graph.add_edge("retrieve", "claims")
    graph.add_edge("claims", "barcode")
    graph.add_edge("barcode", "compare")
    graph.add_edge("compare", "evidence_card")
    graph.add_edge("evidence_card", END)

    return graph.compile()


_compiled_workflow = None


def get_workflow():
    global _compiled_workflow
    if _compiled_workflow is None:
        _compiled_workflow = build_workflow()
    return _compiled_workflow


def run_workflow(
    label: ExtractedLabel,
    portion: PortionSelection,
    goal: Optional[str] = None,
    question: Optional[str] = None,
    barcode: Optional[str] = None,
    second_label: Optional[ExtractedLabel] = None,
    second_portion: Optional[PortionSelection] = None,
    first_name: str = "This product",
    second_name: Optional[str] = None,
) -> WorkflowState:
    initial_state: WorkflowState = {
        "label": label,
        "portion": portion,
        "goal": goal,
        "question": question,
        "barcode": barcode,
        "second_label": second_label,
        "second_portion": second_portion,
        "first_name": first_name,
        "second_name": second_name,
        "trace": [],
        "blocked": False,
    }
    return get_workflow().invoke(initial_state)
