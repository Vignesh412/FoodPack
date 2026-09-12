# Live label validation — Nature Valley Oats 'N Honey

Date: 11 September 2026  
Geography: United States  
Product barcode: `0016000264694`

## Test purpose

Verify one complete real-photo journey through the HTTP boundary: three package photographs → structured vision extraction → explicit user confirmation → LangGraph analysis → evidence trace.

## Result

- Extraction endpoint: HTTP 200
- Analysis endpoint: HTTP 200
- Workflow refusal: false for the informational walkthrough
- Barcode cross-check: supporting Open Food Facts record found; no 20%+ nutrient difference flags
- Approximate end-to-end local run time: 13 seconds
- Model input-image size reduced from 4,097,758 bytes to 1,198,579 bytes before transmission (70.8% reduction)

## Selected fact comparison

| Label fact | Printed package | Extracted value | Result |
|---|---:|---:|---|
| Product | Nature Valley Crunchy Oats 'N Honey Granola Bars | Same | Match |
| Serving measure | 2 bars | 2 bars | Match |
| Serving weight | 42 g | 42 g | Match |
| Calories | 190 | 190 | Match |
| Added sugar | 11 g, 23% DV | 11 g, 23% DV | Match |
| Sodium | 140 mg, 6% DV | 140 mg, 6% DV | Match |
| Saturated fat | 1 g, 4% DV | 1 g, 4% DV | Match |
| Fibre | 2 g, 8% DV | 2 g, 8% DV | Match |
| Protein | 3 g | 3 g | Match |
| Declared allergen | Soy | Soy | Match |
| Advisory allergens | Peanut, almond, pecan | Peanut, almond, pecan | Match |

All selected facts matched in this one product case. This is a successful integration test, not a general accuracy claim. More products, difficult images and negative cases are required before reporting a reliable extraction rate.

## Executed workflow trace

1. Safety gate allowed an informational label walkthrough.
2. Deterministic calculation recomputed five nutrients for the selected portion.
3. FDA retrieval returned a relevant passage.
4. Claim evidence checked two front-of-pack claims.
5. Barcode lookup found the supporting Open Food Facts record and reported no meaningful nutrient mismatch; confirmed package values remained primary.
6. Product comparison was correctly reported as skipped.
7. The Evidence Card was assembled with citations and uncertainty notes.
