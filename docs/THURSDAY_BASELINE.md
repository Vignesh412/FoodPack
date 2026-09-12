# FoodProof Fit — Thursday baseline

## Purpose of this segment

Prove that the inherited FoodPack project is a working foundation before adding personalization. This prevents us from building new features on top of an unknown or broken baseline.

## Frozen MVP scope

- Geography: United States only.
- Product type: packaged foods with a US Nutrition Facts label.
- Required photos: front of pack, Nutrition Facts panel, and ingredients/allergen panel.
- Personalized inputs planned next: declared allergens, dietary preference, daily calorie goal, protein goal, fibre goal, sodium limit, and added-sugar limit.
- Output: cited label explanation, allergen matching, and contribution to daily goals.
- Safety boundary: informational support only; no diagnosis, treatment advice, allergy-safety guarantee, or universal "healthy/unhealthy" verdict.

## Baseline verification completed

- Python environment created in `.venv`.
- Python dependencies installed.
- Web dependencies installed.
- All 84 backend and evaluation tests pass.
- Production web build passes.
- Backend health endpoint returns `{ "status": "ok" }`.
- Local web interface opens at `http://localhost:3000`.
- Demo scan → confirm → result journey opens successfully.
- Nature Valley, Campbell's and CLIF Bar photo sets completed the extract → confirm → analyze API journey successfully; a low-resolution Doritos panel correctly triggered a retake.

## Important gaps found in the inherited version

1. **Fixed:** Editing a nutrient value now updates the structured label sent for analysis.
2. **Fixed:** The backend now rejects an unconfirmed label instead of silently marking it confirmed.
3. **Fixed:** Main insight, nutrient, claim, citation, missing-evidence, and refusal cards now render the backend Evidence Card instead of fixed fibre/demo claims.
4. Comparison, history, save-history, and privacy controls are presentation-only demonstrations.
5. No personal allergy profile or daily nutrition-goal profile exists yet.
6. **Fixed:** The first true photo-to-result test now passes with three real package photographs.

## Completion gate for this segment

The software baseline, first live-photo gate, and dynamic Evidence Card rendering are verified. Two different confirmed labels now return different product and sodium values, and this is covered by an automated API test. Claim checks also refuse when the available fields cannot support the complete FDA reference rule.

## Personalization segment completed

- Added an optional user profile for allergens, vegetarian/vegan preference, and daily calorie, protein, fibre, sodium, and added-sugar targets.
- Added a deterministic LangGraph personalization node after portion calculation.
- Added separate declared-allergen, “may contain,” ingredient-term, dietary-preference, and no-match states without providing allergy clearance.
- Added exact portion-to-target contribution calculations; missing product values remain unknown instead of becoming zero.
- Added a clearly labelled example profile and sample demo pathway without treating the example values as recommendations.
- Added automated coverage for allergen aliases, custom allergen terms, actual-portion calculations, dietary conflicts, missing nutrients, and the API response.

## Evaluation segment completed

- Added a reproducible 47-case golden evaluation spanning safe refusal, false refusal, portion arithmetic, FDA retrieval, personalization outcomes, comparison rules, and barcode delta checks.
- Added explicit release gates with visible numerators and denominators instead of an opaque combined score.
- Added a separate real-photo evidence status that clearly says one successful product is not enough for a general vision-accuracy claim.
- Added a visible Evals dashboard, failure taxonomy, generated JSON report, and automated tests for the evaluation runner itself.

## Demo-readiness segment completed

- Added three clearly labelled, one-click synthetic scenarios for daily-goal contribution, a declared-allergen match, and an allergy-safety refusal.
- Preserved the human confirmation step in every non-live demo journey.
- Added a visible architecture map to the Evals page and a reusable repository architecture diagram.
- Added a 90-second presentation script, an API-failure fallback, and a submission checklist.
- Kept synthetic presentation cases separate from vision evidence; the real-photo readiness claim remains limited to one completed product.

The remaining presentation work is to capture final interface screenshots, record the 90–120 second video, and connect the deployed Python service if a public live demo is required. The real-photo set should continue to expand before any general accuracy claim is made.

## Session-history segment completed

- Completed real-label analyses are saved as structured session records and can be searched and reopened without rescanning.
- Synthetic presentation scenarios are excluded from history.
- Original photographs and personal profile inputs are excluded from saved records.
- History clears when the browser tab closes; durable multi-device storage remains a production enhancement.
