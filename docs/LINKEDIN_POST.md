# LinkedIn post draft

What if an AI food-label assistant was judged not only by what it answered—but by whether it knew when the evidence was insufficient?

We built **FoodProof Fit**, an agentic AI prototype that turns photographs of a US packaged-food label into a personalized, cited Evidence Card.

The user uploads the front, Nutrition Facts, and ingredients panels, confirms the extracted facts, and enters an optional portion, allergen profile, and daily nutrition targets. FoodProof Fit then:

- recalculates the actual portion using deterministic tools;
- matches declared allergens without claiming allergy clearance;
- explains contribution to user-entered daily goals;
- grounds explanations in FDA sources;
- audits selected front-of-pack claims;
- compares products on the same basis; and
- searches Open Food Facts for same-category alternatives aligned with one nutrient priority.

The most important part is what the system refuses to do. It will not diagnose, guarantee that a food is allergy-safe, replace missing added-sugar data with total sugar, or declare one product universally “healthy.”

Our current evidence:

✅ 52/52 versioned golden cases across eight risk surfaces  
✅ 100 automated Python tests  
✅ Four real photographed products completed end to end  
✅ One weak image correctly requested a retake  
✅ Human confirmation before downstream calculations  
✅ Server-side API protection and privacy-safe request logging

We also keep the limitation visible: four successful product sets are not enough to claim a general vision-accuracy percentage.

Demo: `[ADD VIDEO URL]`  
Live prototype: `[ADD CLOUD URL]`  
Architecture and code: `[ADD GITHUB URL]`

Team: `[ADD ONLY CONFIRMED CONTRIBUTORS]`

#AgenticAI #ResponsibleAI #HealthTech #FoodTech #RAG #AIEvals #HumanInTheLoop #AIEngineering
