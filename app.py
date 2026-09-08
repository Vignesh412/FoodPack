"""
FoodProof — Streamlit prototype entry point.

Run with: streamlit run app.py

If ANTHROPIC_API_KEY is not set, the app runs in demo mode: instead of
photo uploads driving vision extraction, you pick one of the roadmap's
three demonstration scenarios and the rest of the pipeline (confirmation,
calculation, retrieval, claims, comparison, safety gate, evidence card)
runs exactly as it would on real extracted data. This keeps every
downstream module demoable and testable before real label photos and API
billing are both sorted out.
"""

from __future__ import annotations

import os

import streamlit as st
from dotenv import load_dotenv

from src.image_quality import run_quality_gate
from src.label_extractor import ExtractionError, extract_label
from src.nutrition_rules import dv_level
from src.product_lookup import lookup_barcode
from src.sample_data import SCENARIOS
from src.schemas import (
    AllergenInfo,
    DVLevel,
    ExtractedLabel,
    FrontOfPackClaim,
    MassAmount,
    MassUnit,
    NutrientField,
    NutritionGoal,
    PortionSelection,
    ServingInfo,
)
from src.workflow import run_workflow

load_dotenv()

st.set_page_config(page_title="FoodProof", page_icon="🏷️", layout="wide")

HAS_API_KEY = bool(os.environ.get("ANTHROPIC_API_KEY"))

_DV_COLOR = {
    DVLevel.LOW: "#2E7D32",
    DVLevel.MODERATE: "#B8860B",
    DVLevel.HIGH: "#C62828",
    DVLevel.UNKNOWN: "#888888",
}

NUTRIENT_LABELS = {
    "added_sugar": "Added sugar",
    "sodium": "Sodium",
    "saturated_fat": "Saturated fat",
    "fibre": "Fibre",
    "protein": "Protein",
}


# --------------------------------------------------------------------------
# Session state helpers
# --------------------------------------------------------------------------

def _init_state():
    st.session_state.setdefault("label_a", None)
    st.session_state.setdefault("label_b", None)
    st.session_state.setdefault("name_a", "This product")
    st.session_state.setdefault("name_b", "Second product")
    st.session_state.setdefault("comparison_mode", False)


def _editable_nutrient_field(label_text: str, field: NutrientField, unit: MassUnit, key: str) -> NutrientField:
    cols = st.columns([2, 1, 1])
    present = cols[0].checkbox(f"{label_text} shown on label", value=field.present_on_label, key=f"{key}_present")
    value = field.amount.value if field.amount else 0.0
    new_value = cols[1].number_input(f"{label_text} ({unit.value})", min_value=0.0, value=float(value), step=0.1, key=f"{key}_value", disabled=not present)
    dv = field.percent_daily_value if field.percent_daily_value is not None else 0.0
    new_dv = cols[2].number_input(f"{label_text} %DV", min_value=0.0, value=float(dv), step=1.0, key=f"{key}_dv", disabled=not present)

    if not present:
        return NutrientField(present_on_label=False)
    return NutrientField(
        amount=MassAmount(value=new_value, unit=unit),
        percent_daily_value=new_dv if new_dv else None,
        confidence=1.0,  # user-confirmed values are treated as ground truth
        present_on_label=True,
    )


def confirmation_editor(label: ExtractedLabel, key_prefix: str) -> ExtractedLabel:
    """
    Step 5's human-in-the-loop confirmation: every critical value is shown
    in an editable field, pre-filled from extraction (or demo data), and
    nothing downstream runs until the user has looked at every one.
    """
    st.markdown(f"**Product name**")
    product_name = st.text_input("Product name", value=label.product_name or "", key=f"{key_prefix}_name", label_visibility="collapsed")

    st.markdown("**Serving information**")
    c1, c2 = st.columns(2)
    household = c1.text_input("Household measure (e.g. \"1 bar\")", value=label.serving.household_measure or "", key=f"{key_prefix}_household")
    grams = c2.number_input("Grams per serving", min_value=0.0, value=float(label.serving.grams_per_serving or 0), step=1.0, key=f"{key_prefix}_grams")
    calories = st.number_input("Calories per serving", min_value=0.0, value=float(label.calories or 0), step=1.0, key=f"{key_prefix}_cal")

    st.markdown("**Critical nutrients** — confirm or correct every value before continuing")
    added_sugar = _editable_nutrient_field("Added sugar", label.added_sugar, MassUnit.GRAM, f"{key_prefix}_sugar")
    sodium = _editable_nutrient_field("Sodium", label.sodium, MassUnit.MILLIGRAM, f"{key_prefix}_sodium")
    sat_fat = _editable_nutrient_field("Saturated fat", label.saturated_fat, MassUnit.GRAM, f"{key_prefix}_satfat")
    fibre = _editable_nutrient_field("Fibre", label.fibre, MassUnit.GRAM, f"{key_prefix}_fibre")
    protein = _editable_nutrient_field("Protein", label.protein, MassUnit.GRAM, f"{key_prefix}_protein")

    with st.expander("Ingredients, allergens & front-of-pack claims"):
        ingredient_text = st.text_area("Ingredient list", value=label.allergens.raw_ingredient_text or "", key=f"{key_prefix}_ingredients")
        contains = st.text_input("Declared allergens (comma-separated)", value=", ".join(label.allergens.declared_contains), key=f"{key_prefix}_contains")
        may_contain = st.text_input("\"May contain\" statement (comma-separated)", value=", ".join(label.allergens.may_contain_statement), key=f"{key_prefix}_maycontain")
        claims_text = st.text_input("Front-of-pack claims (comma-separated)", value=", ".join(c.raw_text for c in label.front_claims), key=f"{key_prefix}_claims")

    confirmed = ExtractedLabel(
        product_name=product_name or None,
        serving=ServingInfo(household_measure=household or None, grams_per_serving=grams or None, servings_per_container=label.serving.servings_per_container, net_weight_grams=label.serving.net_weight_grams),
        calories=calories or None,
        added_sugar=added_sugar,
        sodium=sodium,
        saturated_fat=sat_fat,
        fibre=fibre,
        protein=protein,
        allergens=AllergenInfo(
            raw_ingredient_text=ingredient_text or None,
            declared_contains=[s.strip() for s in contains.split(",") if s.strip()],
            may_contain_statement=[s.strip() for s in may_contain.split(",") if s.strip()],
        ),
        front_claims=[FrontOfPackClaim(raw_text=s.strip()) for s in claims_text.split(",") if s.strip()],
        user_confirmed=True,
    )

    if confirmed.missing_fields:
        st.caption(f"⚠️ Not on label / unconfirmed: {', '.join(confirmed.missing_fields)}")

    return confirmed


def portion_visualizer(result_map, servings_consumed: float):
    """
    The 'winning strategy' portion visualizer: renders each nutrient's
    %DV at the user's actual portion as a colored progress bar, so the
    deterministic recalculation in src/nutrition_rules.py is something a
    viewer watches change, not just a number in a table.
    """
    st.markdown(f"**Your actual portion: {servings_consumed:g} serving(s)**")
    for name, label_text in NUTRIENT_LABELS.items():
        res = result_map.get(name)
        if res is None or res.per_actual_portion is None:
            st.caption(f"{label_text}: not on label")
            continue
        dv = res.per_actual_portion_dv or 0
        level = res.per_actual_portion_dv_level
        amount = res.per_actual_portion
        pct_for_bar = min(dv / 100.0, 1.0)
        col1, col2 = st.columns([3, 1])
        col1.progress(pct_for_bar, text=f"{label_text}: {amount.value:g} {amount.unit.value} ({dv:g}% DV — {level.value})")


def render_trace(trace: list[str]):
    with st.expander("🔍 Workflow trace — what the agent actually did", expanded=False):
        for i, line in enumerate(trace, start=1):
            st.markdown(f"{i}. {line}")


def render_citations(citations):
    if not citations:
        return
    st.markdown("**Sources**")
    for c in citations:
        st.markdown(f"- *{c.title}* — {c.section}. [{c.url}]({c.url})")


def render_evidence_card(card: dict, trace: list[str]):
    if card.get("refused"):
        st.error(card["message"])
        render_trace(trace)
        return

    st.subheader(f"Evidence Card — {card.get('product_name') or 'Confirmed product'}")

    calc = card.get("calculation")
    if calc:
        portion_visualizer(calc.results, calc.servings_consumed)

    if card.get("missing_fields"):
        st.warning(f"Missing or unconfirmed on this label: {', '.join(card['missing_fields'])}")

    claim_verdicts = card.get("claim_verdicts") or []
    if claim_verdicts:
        st.markdown("**Front-of-pack claims vs. the evidence**")
        for v in claim_verdicts:
            icon = {"supported": "✅", "not_supported": "❌", "insufficient_evidence": "❔"}[v.verdict]
            st.markdown(f"{icon} **\"{v.claim_text}\"** — {v.rationale}")

    delta_flags = card.get("delta_flags") or []
    if delta_flags:
        st.markdown("**Barcode delta-check**")
        for f in delta_flags:
            st.markdown(
                f"- ⚠️ {NUTRIENT_LABELS.get(f.nutrient, f.nutrient)}: photographed {f.photographed_per_100g:g} vs "
                f"historical {f.historical_per_100g:g} per 100g ({f.percent_difference:g}% difference). "
                "The current photograph is treated as primary evidence."
            )

    comparison = card.get("comparison")
    if comparison:
        st.markdown("**Comparison**")
        if not comparison.per_100g_available:
            st.caption(comparison.per_100g_unavailable_reason)
        for nc in comparison.nutrient_comparisons:
            st.markdown(f"- **{NUTRIENT_LABELS.get(nc.nutrient, nc.nutrient)}** — {nc.per_100g_note or nc.per_actual_portion_note}")

    render_citations(card.get("citations"))
    render_trace(trace)


# --------------------------------------------------------------------------
# Main app
# --------------------------------------------------------------------------

def main():
    _init_state()

    st.title("🏷️ FoodProof")
    st.caption("A guided packaged-food label reader — not a diagnosis tool, not a health score.")

    if not HAS_API_KEY:
        st.info(
            "No ANTHROPIC_API_KEY detected — running in **demo mode** with the roadmap's three "
            "sample scenarios. Add a real key to .env to switch to live photo extraction. "
            "Photos are only ever used to extract the values shown below; nothing is stored after this session."
        )

    with st.sidebar:
        st.header("Your goal")
        goal = st.selectbox(
            "What are you trying to check?",
            options=[g.value for g in NutritionGoal],
            format_func=lambda v: v.replace("_", " ").title(),
        )
        st.session_state["comparison_mode"] = st.checkbox(
            "Compare two products", value=st.session_state["comparison_mode"], key="comparison_mode_widget"
        )
        st.divider()
        st.caption(
            "FoodProof explains what a label says. It does not diagnose conditions, "
            "recommend treatment, or guarantee a product is safe for an allergy."
        )

    tab_input, tab_result = st.tabs(["1. Product input", "2. Evidence Card"])

    with tab_input:
        st.subheader("Product A")
        if HAS_API_KEY:
            st.session_state["name_a"] = st.text_input("Product name (for display)", value=st.session_state["name_a"], key="display_name_a")
            front = st.file_uploader("Front of package photo", type=["jpg", "jpeg", "png"], key="front_a")
            nutrition = st.file_uploader("Nutrition Facts photo", type=["jpg", "jpeg", "png"], key="nutrition_a")
            ingredients = st.file_uploader("Ingredients & allergens photo", type=["jpg", "jpeg", "png"], key="ingredients_a")
            barcode = st.text_input("Barcode (optional)", key="barcode_a")

            if st.button("Run image quality check + extraction", key="extract_a"):
                images = [(f, f.type) for f in (front, nutrition, ingredients) if f is not None]
                if not images:
                    st.warning("Upload at least one photo first.")
                else:
                    with st.spinner("Checking image quality..."):
                        problems = []
                        for f, media_type in images:
                            gate = run_quality_gate(f.getvalue(), media_type=media_type)
                            if not gate.accepted:
                                problems.append(gate.retake_instruction)
                    if problems:
                        for p in problems:
                            st.error(p)
                    else:
                        with st.spinner("Extracting label data..."):
                            try:
                                extracted = extract_label([(f.getvalue(), mt) for f, mt in images])
                                st.session_state["label_a"] = extracted
                                st.success("Extraction complete — confirm the values below.")
                            except ExtractionError as exc:
                                st.error(str(exc))
        else:
            scenario_name = st.selectbox("Demo scenario", options=list(SCENARIOS.keys()), key="scenario_a")
            if st.button("Load demo scenario", key="load_a"):
                st.session_state["label_a"] = SCENARIOS[scenario_name]()
                st.session_state["name_a"] = scenario_name

        if st.session_state["label_a"] is not None:
            st.markdown("---")
            st.markdown("### Confirm Product A values")
            st.session_state["label_a"] = confirmation_editor(st.session_state["label_a"], "a")
            servings_a = st.number_input("Servings you actually eat — Product A", min_value=0.1, value=1.0, step=0.5, key="servings_a")

        if st.session_state["comparison_mode"]:
            st.markdown("---")
            st.subheader("Product B")
            if HAS_API_KEY:
                st.session_state["name_b"] = st.text_input("Product name (for display)", value=st.session_state["name_b"], key="display_name_b")
                front_b = st.file_uploader("Front of package photo", type=["jpg", "jpeg", "png"], key="front_b")
                nutrition_b = st.file_uploader("Nutrition Facts photo", type=["jpg", "jpeg", "png"], key="nutrition_b")
                ingredients_b = st.file_uploader("Ingredients & allergens photo", type=["jpg", "jpeg", "png"], key="ingredients_b")

                if st.button("Run image quality check + extraction", key="extract_b"):
                    images_b = [(f, f.type) for f in (front_b, nutrition_b, ingredients_b) if f is not None]
                    if not images_b:
                        st.warning("Upload at least one photo first.")
                    else:
                        with st.spinner("Extracting label data..."):
                            try:
                                extracted_b = extract_label([(f.getvalue(), mt) for f, mt in images_b])
                                st.session_state["label_b"] = extracted_b
                                st.success("Extraction complete — confirm the values below.")
                            except ExtractionError as exc:
                                st.error(str(exc))
            else:
                scenario_name_b = st.selectbox("Demo scenario", options=list(SCENARIOS.keys()), key="scenario_b", index=min(2, len(SCENARIOS) - 1))
                if st.button("Load demo scenario", key="load_b"):
                    st.session_state["label_b"] = SCENARIOS[scenario_name_b]()
                    st.session_state["name_b"] = scenario_name_b

            if st.session_state["label_b"] is not None:
                st.markdown("### Confirm Product B values")
                st.session_state["label_b"] = confirmation_editor(st.session_state["label_b"], "b")
                servings_b = st.number_input("Servings you actually eat — Product B", min_value=0.1, value=1.0, step=0.5, key="servings_b")

        st.markdown("---")
        question = st.text_area("Optional question (e.g. \"how much sodium is in this?\")", key="question")
        barcode_lookup_input = st.text_input("Barcode to check against Open Food Facts (optional)", key="barcode_check")

        can_run = st.session_state["label_a"] is not None and (
            not st.session_state["comparison_mode"] or st.session_state["label_b"] is not None
        )
        if st.button("Generate Evidence Card", type="primary", disabled=not can_run):
            with st.spinner("Running the controlled workflow..."):
                result = run_workflow(
                    label=st.session_state["label_a"],
                    portion=PortionSelection(servings_consumed=st.session_state.get("servings_a", 1.0)),
                    goal=goal,
                    question=question or None,
                    barcode=barcode_lookup_input or None,
                    second_label=st.session_state["label_b"] if st.session_state["comparison_mode"] else None,
                    second_portion=PortionSelection(servings_consumed=st.session_state.get("servings_b", 1.0)) if st.session_state["comparison_mode"] else None,
                    first_name=st.session_state["name_a"],
                    second_name=st.session_state["name_b"] if st.session_state["comparison_mode"] else None,
                )
                st.session_state["last_result"] = result
            st.success("Evidence Card ready — see the '2. Evidence Card' tab.")

    with tab_result:
        result = st.session_state.get("last_result")
        if result is None:
            st.info("Fill in Product A (and Product B, if comparing) and click **Generate Evidence Card**.")
        else:
            render_evidence_card(result["evidence_card"], result["trace"])


if __name__ == "__main__":
    main()
