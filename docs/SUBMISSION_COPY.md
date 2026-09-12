# FoodProof Fit — Final submission copy

## One-line pitch

FoodProof Fit turns three photographs of a US packaged-food label into a human-confirmed, personalized Evidence Card—and can then surface better-aligned same-category alternatives without declaring any product universally healthy or allergy-safe.

## Problem

Nutrition labels provide the same dense information to everyone, although people eat different portions and care about different allergens and dietary targets. Existing scanners can also create false confidence when data is incomplete, old, or compared across inconsistent serving sizes. In high-stakes situations, a confident answer can be more dangerous than a clear refusal.

## What we built

The user photographs the front, Nutrition Facts, and ingredients panels. FoodProof Fit checks image quality, extracts structured facts with vision AI, and requires the user to confirm or correct them. A bounded LangGraph workflow then performs deterministic portion calculations, checks user-entered allergens and daily goals, retrieves FDA evidence, audits marketing claims, and assembles a cited Evidence Card. Separate post-analysis tools provide normalized product comparison, barcode cross-checking, session-only history, and live Open Food Facts alternatives for one chosen nutrient priority.

## Responsible-agent design

- Human confirmation before calculations or comparisons
- Deterministic mathematics and profile matching
- FDA-grounded retrieval with visible citations
- Explicit medical and allergy-guarantee refusal paths
- Missing data remains unknown
- Alternatives restricted by geography, category, evidence and profile conflicts
- Server-to-server protection for paid API routes
- No application-level storage of original photographs or personal profiles

## Evaluation evidence

- 52/52 versioned golden cases passed across eight separate risk surfaces
- 100 automated Python tests passed
- Four real photographed product sets completed the full path
- One weak Nutrition Facts image correctly triggered a retake
- Frontend lint and production build passed

The photographed set is small and non-random, so we deliberately do not publish a general vision-accuracy percentage.

## Demo links

- Live application: `[ADD FINAL CLOUD URL]`
- GitHub repository: `[ADD FINAL REPOSITORY OR PULL REQUEST URL]`
- 120-second demonstration: `[ADD VIDEO URL]`

## Closing statement

FoodProof Fit demonstrates a production pattern for responsible consumer AI: use AI for perception and explanation, deterministic tools for calculation, people for confirmation, authoritative sources for grounding, and explicit boundaries when the evidence does not justify an answer.
