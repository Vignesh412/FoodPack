# Live label validation — Premium Original Saltine Crackers

Date: 12 September 2026  
Geography: United States  
Open Food Facts record: `0044000044831`

## Test purpose

Add a fourth successful real-package journey and verify a common edge case: an ingredients photograph that is highly detailed but panoramic. The relaxed deterministic dimension rule applies only to the ingredients panel; Nutrition Facts retains the 600-pixel short-edge requirement, and the vision gate still decides whether text is readable.

## Result

- Three deterministic image checks: passed
- Vision extraction: HTTP 200
- Validated structured schema: passed
- Confirmed-label analysis: HTTP 200
- Workflow refusal: false for the informational walkthrough
- Profile allergen match: `declared_match` for wheat
- Workflow trace: eight bounded steps

## Selected fact comparison

| Label fact | Printed package | Extracted value | Result |
| --- | ---: | ---: | --- |
| Product | Premium Original Saltine Crackers | Same product | Match |
| Serving measure | 5 crackers | 5 crackers | Match |
| Serving weight | 16 g | 16 g | Match |
| Calories | 70 | 70 | Match |
| Added sugar | 0 g, 0% DV | 0 g, 0% DV | Match |
| Sodium | 135 mg, 6% DV | 135 mg, 6% DV | Match |
| Saturated fat | 0 g, 0% DV | 0 g, 0% DV | Match |
| Fibre | 0 g, 0% DV | 0 g, 0% DV | Match |
| Protein | 1 g | 1 g | Match |
| Ingredient profile term | Wheat | Wheat | Match |

The test strengthens integration evidence but does not justify a general vision-accuracy percentage. The five attempted product sets are still small and non-random.

## Source and licence

The package images were retrieved from [Open Food Facts product 0044000044831](https://world.openfoodfacts.org/product/0044000044831). Contributor images are used for local evaluation under CC BY-SA 3.0. Open Food Facts data is community-maintained, so the photographed package remains the primary evidence.
