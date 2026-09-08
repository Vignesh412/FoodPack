"""
Responsible Refusal: a mandatory, fixed gate the agent cannot route around.

Design follows the same deterministic-first rule as the rest of the
pipeline: an obvious unsafe request (direct diagnosis, treatment, disease
suitability, allergy-safety guarantee) is caught by a fast keyword layer
with no model call at all. Only genuinely ambiguous phrasing should ever
reach an LLM judgment call, and even then the LLM is asked to classify
intent, never to answer the unsafe question itself. This module also
treats indirect framing — roleplay ("pretend you're my doctor"), authority
appeals ("my nutritionist told me to ask"), or instruction-override
attempts — as reasons for stricter scrutiny, not as a way around the gate.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

RefusalCategory = Literal[
    "diagnosis", "treatment", "disease_suitability", "allergy_guarantee", "none",
]

_DIAGNOSIS_TERMS = ["diagnose", "diagnosis", "do i have", "does this mean i have"]

_TREATMENT_TERMS = [
    "treat my", "treatment for", "cure my", "cure for", "what medication",
    "dosage", "prescribe", "prescription",
]

_DISEASE_TERMS = [
    "diabetes", "diabetic", "heart disease", "kidney disease", "kidney failure",
    "celiac", "coeliac", "hypertension", "high blood pressure diagnosis", "cancer",
]
_SUITABILITY_TERMS = [
    "safe for", "suitable for", "ok for", "okay for", "fine for", "good for",
    "recommend for", "bad for", "alright for",
]

_ALLERGY_GUARANTEE_TERMS = [
    "guarantee", "100% safe", "definitely safe", "will not trigger",
    "promise it's safe", "completely safe",
]
_ALLERGY_CONTEXT_TERMS = ["allergy", "allergic", "anaphyla"]

# Framing that tries to route around the gate rather than ask directly.
_EVASION_FRAMES = [
    "pretend you", "pretend to be", "pretend there", "act as", "roleplay as", "as my doctor",
    "as a doctor", "my doctor said to ask", "my nutritionist told me",
    "my nutritionist said", "ignore previous instructions", "ignore your instructions",
    "as if you were a doctor", "just between us", "no rule against",
]

_MEDICAL_SIGNAL_TERMS = (
    _DIAGNOSIS_TERMS + _TREATMENT_TERMS + _DISEASE_TERMS + _ALLERGY_CONTEXT_TERMS
)


class IntentResult(BaseModel):
    is_unsafe: bool
    category: RefusalCategory
    matched_terms: list[str]
    evasion_detected: bool
    needs_llm_review: bool
    rationale: str


def _contains_any(text: str, terms: list[str]) -> list[str]:
    return [t for t in terms if t in text]


def classify_intent(question: str) -> IntentResult:
    """
    Deterministic first pass. Returns is_unsafe=True immediately on a clear
    match. Sets needs_llm_review=True when the phrasing is medical-adjacent
    but ambiguous enough that a keyword list alone shouldn't decide —
    that's the one case this project should route to an LLM judgment call,
    per the deterministic-first design rule.
    """
    lowered = question.lower().strip()
    evasion_hits = _contains_any(lowered, _EVASION_FRAMES)

    diagnosis_hits = _contains_any(lowered, _DIAGNOSIS_TERMS)
    if diagnosis_hits:
        return IntentResult(
            is_unsafe=True, category="diagnosis", matched_terms=diagnosis_hits,
            evasion_detected=bool(evasion_hits), needs_llm_review=False,
            rationale="Question asks for a diagnosis.",
        )

    treatment_hits = _contains_any(lowered, _TREATMENT_TERMS)
    if treatment_hits:
        return IntentResult(
            is_unsafe=True, category="treatment", matched_terms=treatment_hits,
            evasion_detected=bool(evasion_hits), needs_llm_review=False,
            rationale="Question asks for treatment or medication guidance.",
        )

    disease_hits = _contains_any(lowered, _DISEASE_TERMS)
    suitability_hits = _contains_any(lowered, _SUITABILITY_TERMS)
    if disease_hits and suitability_hits:
        return IntentResult(
            is_unsafe=True, category="disease_suitability",
            matched_terms=disease_hits + suitability_hits,
            evasion_detected=bool(evasion_hits), needs_llm_review=False,
            rationale="Question asks whether this food is suitable for a named medical condition.",
        )

    allergy_guarantee_hits = _contains_any(lowered, _ALLERGY_GUARANTEE_TERMS)
    allergy_context_hits = _contains_any(lowered, _ALLERGY_CONTEXT_TERMS)
    if allergy_guarantee_hits and allergy_context_hits:
        return IntentResult(
            is_unsafe=True, category="allergy_guarantee",
            matched_terms=allergy_guarantee_hits + allergy_context_hits,
            evasion_detected=bool(evasion_hits), needs_llm_review=False,
            rationale="Question asks for an absolute allergy-safety guarantee.",
        )

    # Evasion framing plus any medical-adjacent term: don't refuse outright
    # on keywords alone (that risks false refusals on a harmless question
    # that happens to mention "doctor"), but flag for the stricter LLM
    # review rather than letting it pass silently.
    if evasion_hits and _contains_any(lowered, _MEDICAL_SIGNAL_TERMS):
        return IntentResult(
            is_unsafe=False, category="none", matched_terms=evasion_hits,
            evasion_detected=True, needs_llm_review=True,
            rationale="Indirect framing combined with a medical-adjacent term — ambiguous, route to LLM review.",
        )

    if allergy_context_hits and not allergy_guarantee_hits:
        return IntentResult(
            is_unsafe=False, category="none", matched_terms=allergy_context_hits,
            evasion_detected=bool(evasion_hits), needs_llm_review=True,
            rationale="Mentions allergies without a clear guarantee request — ambiguous, route to LLM review.",
        )

    return IntentResult(
        is_unsafe=False, category="none", matched_terms=[],
        evasion_detected=bool(evasion_hits), needs_llm_review=False,
        rationale="No unsafe pattern matched.",
    )


_REFUSAL_MESSAGES: dict[RefusalCategory, str] = {
    "diagnosis": (
        "FoodProof can't diagnose a health condition — that needs a clinician who can "
        "examine you, not a label reader. What I can do is walk through exactly what "
        "this label says about sodium, sugar, fat, fibre and protein, so you have clear "
        "information to bring to that conversation."
    ),
    "treatment": (
        "FoodProof can't recommend treatment, medication, or dosage — that's outside "
        "what a nutrition label can safely tell you, and it needs a clinician or "
        "pharmacist. I can explain what's actually on this label instead."
    ),
    "disease_suitability": (
        "FoodProof can't tell you whether a food is safe for a specific medical "
        "condition — that depends on your individual treatment plan, which only your "
        "doctor or a registered dietitian knows. I can show you the confirmed nutrient "
        "values and let you take those numbers to that conversation."
    ),
    "allergy_guarantee": (
        "FoodProof can't guarantee a product is safe for an allergy — mislabelling, "
        "cross-contact, and recipe changes are all real risks a label reader cannot "
        "rule out. I can highlight the declared allergens and any \"may contain\" "
        "statement exactly as printed, but the final call needs to be yours or your "
        "allergist's, checked against the physical package."
    ),
}


def build_refusal_message(category: RefusalCategory) -> str:
    return _REFUSAL_MESSAGES.get(
        category,
        "FoodProof can't safely answer that question from a label alone.",
    )


class SafetyDecision(BaseModel):
    allowed: bool
    intent: IntentResult
    message: Optional[str] = None


_CLARIFICATION_MESSAGE = (
    "I want to make sure I answer this safely. Could you ask directly, without "
    "wrapping it in a persona or someone else's instruction? I can walk through "
    "exactly what this label says once the question is direct."
)


def evaluate_safety(
    question: str,
    llm_reviewed: bool = False,
    llm_says_unsafe: Optional[bool] = None,
    llm_category: Optional[RefusalCategory] = None,
) -> SafetyDecision:
    """
    Full gate: deterministic pass first. If it flags needs_llm_review, the
    caller must run an LLM classification and pass llm_reviewed=True with
    the verdict — this function fails CLOSED (asks for clarification rather
    than silently allowing) if a review was flagged as needed but never
    actually happened, so a workflow bug can't quietly skip the check.
    This function never calls a model itself, keeping it unit-testable.
    """
    intent = classify_intent(question)

    if intent.is_unsafe:
        return SafetyDecision(allowed=False, intent=intent, message=build_refusal_message(intent.category))

    if intent.needs_llm_review:
        if not llm_reviewed:
            return SafetyDecision(allowed=False, intent=intent, message=_CLARIFICATION_MESSAGE)
        if llm_says_unsafe:
            category = llm_category or "disease_suitability"
            return SafetyDecision(allowed=False, intent=intent, message=build_refusal_message(category))

    return SafetyDecision(allowed=True, intent=intent, message=None)
