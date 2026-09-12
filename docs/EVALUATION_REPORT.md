# FoodProof Fit — Evaluation Report

## Current automated release gate

**52 of 52 golden cases pass.** This is a count of defined, versioned test cases—not a claim that the application is universally accurate.

| Evaluation surface | Result | What it measures |
| --- | ---: | --- |
| Unsafe requests correctly refused | 16/16 | Direct and adversarial diagnosis, treatment, disease-suitability, and allergy-guarantee requests |
| Answerable requests correctly allowed | 10/10 | Ordinary label questions are not incorrectly blocked |
| Portion calculations exact | 6/6 | Calories and nutrient amounts for different portion sizes |
| Expected FDA source ranked first | 4/4 | Goal-specific retrieval over the curated local FDA corpus |
| Personalization outcomes correct | 6/6 | Declared allergens, advisory allergens, no-match outcomes, and vegetarian/vegan checks |
| Fair-comparison rules correct | 3/3 | Same-basis normalization and refusal when serving-weight evidence is missing |
| Barcode cross-check rules correct | 2/2 | Tolerance for normal variation and flagging differences of 20% or more |
| Alternative-finder rules correct | 5/5 | Same-category relevance, allergen-conflict exclusion, missing evidence, added-sugar refusal, and deterministic ranking |

## Vision evidence status

Four photographed products have completed the full photo → extraction → confirmation → calculation → Evidence Card journey. A fifth product correctly triggered a retake because its Nutrition Facts image was below the minimum resolution. The fourth successful case also verifies that a sufficiently detailed panoramic ingredients panel can proceed to the vision-readability gate without weakening the stricter Nutrition Facts threshold.

This is **not enough evidence to report a general extraction-accuracy percentage**. The set is small and non-random. A credible vision benchmark still requires more products and deliberately difficult images covering blur, glare, crop, darkness, unusual layouts, and missing panels.

## Failure taxonomy

- Blurred, cropped, dark, or reflective images
- Missing serving weight or nutrient values
- Allergen aliases and ambiguous ingredient names
- Unsafe medical or allergy-safety requests
- Irrelevant or unresolved evidence citations
- Irrelevant, incomplete, or unsafe alternative-product candidates

## Reproduce the report

Run `python scripts/run_evals.py` from the repository root. The command writes the detailed machine-readable report to `eval_results/latest.json` and refreshes the dashboard data at `web/public/eval-report.json`.

The golden inputs are versioned in `tests/golden_cases.json` and `evals/golden_set.json`. The report generator contains no model call, so its scoring is deterministic and reproducible.
