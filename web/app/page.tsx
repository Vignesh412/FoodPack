'use client';

import { ChangeEvent, useEffect, useMemo, useState } from 'react';
import Image from 'next/image';
import evaluationReport from '../public/eval-report.json';

type Step = 'scan' | 'confirm' | 'result';
type View = 'analyze' | 'compare' | 'history' | 'evals' | 'privacy';
type DemoScenarioId = 'daily_goals' | 'allergen_alert' | 'safe_refusal';
type AlternativeGoalId = 'lower_sodium' | 'lower_added_sugar' | 'higher_fibre';
type AlternativeCategoryId = 'snack_bars' | 'breakfast_cereals' | 'canned_soups' | 'crackers';
type PhotoSlot = 'front' | 'nutrition' | 'ingredients';
type PhotoEntry = { file: File; url: string };
type NutrientKey = 'sodium' | 'added_sugar' | 'saturated_fat' | 'fibre';
type NutrientView = { key: NutrientKey; name: string; value: string; daily: string; tone: string };
type MassAmount = { value: number; unit: 'g' | 'mg' | 'mcg' };
type NutrientField = {
  amount?: MassAmount | null;
  percent_daily_value?: number | null;
  confidence?: number;
  present_on_label?: boolean;
};
type ExtractedLabel = {
  product_name?: string;
  serving?: { grams_per_serving?: number; household_measure?: string };
  allergens?: { declared_contains?: string[]; may_contain_statement?: string[]; raw_ingredient_text?: string };
  missing_fields?: string[];
  user_confirmed?: boolean;
  sodium?: NutrientField;
  added_sugar?: NutrientField;
  saturated_fat?: NutrientField;
  fibre?: NutrientField;
  [key: string]: unknown;
};
type EvidenceNutrient = {
  nutrient: string;
  per_actual_portion: MassAmount | null;
  per_actual_portion_dv: number | null;
  per_actual_portion_dv_level: 'low' | 'moderate' | 'high' | 'unknown';
  per_100g_unavailable_reason?: string | null;
};
type EvidenceCalculation = {
  servings_consumed: number;
  results: Record<string, EvidenceNutrient>;
  calories_per_actual_portion: number | null;
};
type EvidenceSource = { id: string; title: string; section: string; url: string; text: string; score?: number };
type ClaimVerdict = {
  claim_text: string;
  claim_type: string | null;
  verdict: 'supported' | 'not_supported' | 'insufficient_evidence';
  rationale: string;
  citation_ids: string[];
};
type ProfilePayload = {
  declared_allergens: string[];
  dietary_preference: 'none' | 'vegetarian' | 'vegan';
  daily_calorie_goal: number | null;
  daily_protein_goal_g: number | null;
  daily_fibre_goal_g: number | null;
  daily_sodium_limit_mg: number | null;
  daily_added_sugar_limit_g: number | null;
};
type ProfileForm = {
  allergens: string;
  dietaryPreference: ProfilePayload['dietary_preference'];
  calories: string;
  protein: string;
  fibre: string;
  sodium: string;
  addedSugar: string;
};
type GoalContribution = {
  key: string;
  label: string;
  consumed: number;
  target: number;
  unit: string;
  percent_of_target: number;
  target_type: 'goal' | 'limit';
};
type PersonalizationResult = {
  allergen_match: {
    status: 'profile_not_provided' | 'declared_match' | 'advisory_match' | 'ingredient_match' | 'no_match_found';
    declared_matches: string[];
    advisory_matches: string[];
    ingredient_matches: string[];
    message: string;
  };
  dietary_preference: {
    preference: string;
    status: 'not_requested' | 'possible_conflict' | 'not_verified';
    matched_terms: string[];
    message: string;
  };
  goal_contributions: GoalContribution[];
  disclaimer: string;
};
type BarcodeLookupResult = {
  found: boolean;
  product_name?: string | null;
};
type BarcodeDeltaFlag = {
  nutrient: string;
  photographed_per_100g: number;
  historical_per_100g: number;
  percent_difference: number;
};
type EvidenceCard = {
  refused: boolean;
  message?: string;
  category?: string;
  product_name?: string;
  missing_fields?: string[];
  calculation?: EvidenceCalculation | null;
  citations?: EvidenceSource[];
  claim_verdicts?: ClaimVerdict[];
  claim_sources?: EvidenceSource[];
  personalization?: PersonalizationResult | null;
  barcode_lookup?: BarcodeLookupResult | null;
  delta_flags?: BarcodeDeltaFlag[];
};
type AnalysisResult = { evidence_card?: EvidenceCard; trace?: string[] };
type ResultNutrient = { key: string; name: string; value: string; daily: string; dailyValue: number | null; tone: string; missing: boolean };
type ComparisonProduct = {
  label: ExtractedLabel;
  name: string;
  servings_consumed: number;
  source: 'confirmed' | 'demo';
};
type ComparisonNutrient = {
  nutrient: string;
  per_serving: MassAmount | null;
  per_actual_portion: MassAmount | null;
  per_100g: MassAmount | null;
};
type ComparisonResult = {
  product_a: { label: string; calculation: { results: Record<string, ComparisonNutrient> } };
  product_b: { label: string; calculation: { results: Record<string, ComparisonNutrient> } };
  per_100g_available: boolean;
  per_100g_unavailable_reason?: string | null;
};
type HistoryEntry = {
  id: string;
  created_at: string;
  product_name: string;
  portion: number;
  goal: string;
  barcode: string;
  label: ExtractedLabel;
  analysis: AnalysisResult;
  note: string;
};
type AlternativeCandidate = {
  barcode: string;
  product_name: string;
  brands: string[];
  value_per_100g: number;
  current_value_per_100g: number;
  unit: string;
  improvement_percent: number;
  reason: string;
  allergen_status: 'not_requested' | 'no_declared_match' | 'not_verified';
  allergen_note: string;
  dietary_status: 'not_requested' | 'matches' | 'not_verified';
  dietary_note: string;
  completeness?: number | null;
  source_url: string;
  availability_note: string;
};
type AlternativeSearchResult = {
  status: 'ready' | 'unsupported_goal' | 'current_evidence_missing' | 'no_reliable_candidates' | 'search_unavailable';
  message: string;
  category_label: string;
  goal_label: string;
  candidates_searched: number;
  alternatives: AlternativeCandidate[];
  source_name: string;
  source_url: string;
  evidence_note: string;
};

const HISTORY_STORAGE_KEY = 'foodproof-fit-session-history-v1';

const demoNutrients = [
  { key: 'sodium' as const, name: 'Sodium', value: '410 mg', daily: '18%', tone: 'high' },
  { key: 'added_sugar' as const, name: 'Added sugar', value: '2 g', daily: '4%', tone: 'low' },
  { key: 'saturated_fat' as const, name: 'Saturated fat', value: '1.5 g', daily: '8%', tone: 'medium' },
  { key: 'fibre' as const, name: 'Fibre', value: '6 g', daily: '21%', tone: 'good' },
];

const emptyProfile: ProfileForm = {
  allergens: '',
  dietaryPreference: 'none',
  calories: '',
  protein: '',
  fibre: '',
  sodium: '',
  addedSugar: '',
};

const exampleProfile: ProfileForm = {
  allergens: 'peanuts, milk',
  dietaryPreference: 'vegan',
  calories: '2000',
  protein: '50',
  fibre: '28',
  sodium: '2300',
  addedSugar: '50',
};

function confirmedNutrient(value: number, unit: MassAmount['unit'], percentDailyValue: number | null): NutrientField {
  return { amount: { value, unit }, percent_daily_value: percentDailyValue, confidence: 1, present_on_label: true };
}

const comparisonDemoProducts: ComparisonProduct[] = [
  {
    name: 'Golden Flakes (demo)',
    servings_consumed: 1,
    source: 'demo',
    label: {
      product_name: 'Golden Flakes (demo)', user_confirmed: true, calories: 110,
      serving: { grams_per_serving: 30, household_measure: '3/4 cup' },
      added_sugar: confirmedNutrient(9, 'g', 18), sodium: confirmedNutrient(160, 'mg', 7),
      saturated_fat: confirmedNutrient(0, 'g', 0), fibre: confirmedNutrient(1, 'g', 4), protein: confirmedNutrient(2, 'g', null),
      allergens: { declared_contains: [], may_contain_statement: [], raw_ingredient_text: '' }, missing_fields: [],
    },
  },
  {
    name: 'Morning Crunch (demo)',
    servings_consumed: 1,
    source: 'demo',
    label: {
      product_name: 'Morning Crunch (demo)', user_confirmed: true, calories: 150,
      serving: { grams_per_serving: 55, household_measure: '1 cup' },
      added_sugar: confirmedNutrient(10, 'g', 20), sodium: confirmedNutrient(190, 'mg', 8),
      saturated_fat: confirmedNutrient(0, 'g', 0), fibre: confirmedNutrient(2, 'g', 7), protein: confirmedNutrient(3, 'g', null),
      allergens: { declared_contains: [], may_contain_statement: [], raw_ingredient_text: '' }, missing_fields: [],
    },
  },
];

type DemoNutrientDatum = { value: number; unit: 'g' | 'mg' | 'mcg'; dv: number | null };
type DemoScenario = {
  id: DemoScenarioId;
  label: string;
  title: string;
  summary: string;
  request: string;
  productName: string;
  servingGrams: number;
  portion: number;
  goal: string;
  profile: ProfileForm;
  nutrients: Record<string, DemoNutrientDatum>;
  calories: number;
  allergens: { declared_contains: string[]; may_contain_statement: string[]; raw_ingredient_text: string };
  dietaryConflictTerms: string[];
  refusalMessage?: string;
};

const demoScenarios: Record<DemoScenarioId, DemoScenario> = {
  daily_goals: {
    id: 'daily_goals',
    label: 'Demo 1',
    title: 'Daily-goal contribution',
    summary: 'See how one serving contributes to calorie, fibre, protein, sodium and sugar targets.',
    request: 'Help me understand how this snack fits the daily targets I entered.',
    productName: 'Harvest Crunch (demo)',
    servingGrams: 45,
    portion: 1,
    goal: 'higher_fibre',
    profile: { ...exampleProfile, allergens: '', dietaryPreference: 'none' },
    nutrients: {
      sodium: { value: 410, unit: 'mg', dv: 18 },
      added_sugar: { value: 2, unit: 'g', dv: 4 },
      saturated_fat: { value: 1.5, unit: 'g', dv: 8 },
      fibre: { value: 6, unit: 'g', dv: 21 },
      protein: { value: 5, unit: 'g', dv: null },
    },
    calories: 210,
    allergens: { declared_contains: ['milk'], may_contain_statement: ['peanuts'], raw_ingredient_text: 'whole grains, oats, milk powder, sunflower oil' },
    dietaryConflictTerms: ['milk'],
  },
  allergen_alert: {
    id: 'allergen_alert',
    label: 'Demo 2',
    title: 'Personal allergen alert',
    summary: 'Match a user-entered milk allergy with the package’s declared allergen statement.',
    request: 'Check this label against the allergens I asked you to watch.',
    productName: 'Cocoa Protein Bites (demo)',
    servingGrams: 36,
    portion: 1.5,
    goal: 'general_understanding',
    profile: { ...exampleProfile, allergens: 'milk', dietaryPreference: 'none' },
    nutrients: {
      sodium: { value: 160, unit: 'mg', dv: 7 },
      added_sugar: { value: 8, unit: 'g', dv: 16 },
      saturated_fat: { value: 3, unit: 'g', dv: 15 },
      fibre: { value: 3, unit: 'g', dv: 11 },
      protein: { value: 10, unit: 'g', dv: null },
    },
    calories: 180,
    allergens: { declared_contains: ['milk'], may_contain_statement: ['peanuts', 'tree nuts'], raw_ingredient_text: 'pea protein, cocoa, milk protein, dates' },
    dietaryConflictTerms: ['milk'],
  },
  safe_refusal: {
    id: 'safe_refusal',
    label: 'Demo 3',
    title: 'Safety-boundary refusal',
    summary: 'Show that relevant label text is not permission to guarantee allergy safety.',
    request: 'Is this definitely safe for my child with a severe peanut allergy?',
    productName: 'Trail Mix Bar (demo)',
    servingGrams: 40,
    portion: 1,
    goal: 'general_understanding',
    profile: { ...exampleProfile, allergens: 'peanuts', dietaryPreference: 'none' },
    nutrients: {
      sodium: { value: 120, unit: 'mg', dv: 5 },
      added_sugar: { value: 7, unit: 'g', dv: 14 },
      saturated_fat: { value: 2, unit: 'g', dv: 10 },
      fibre: { value: 4, unit: 'g', dv: 14 },
      protein: { value: 6, unit: 'g', dv: null },
    },
    calories: 190,
    allergens: { declared_contains: ['almonds'], may_contain_statement: ['peanuts'], raw_ingredient_text: 'oats, almonds, raisins, sunflower oil' },
    dietaryConflictTerms: [],
    refusalMessage: 'FoodProof Fit cannot guarantee that a product is safe for a person with a food allergy. The package says “may contain peanuts.” Review the original label and contact the manufacturer or a qualified clinician for case-specific guidance.',
  },
};

function demoNutrientViews(scenario: DemoScenario): NutrientView[] {
  return ['sodium', 'added_sugar', 'saturated_fat', 'fibre'].map((key) => {
    const item = scenario.nutrients[key];
    const daily = item.dv ?? 0;
    return {
      key: key as NutrientKey,
      name: nutrientNames[key],
      value: `${formatNumber(item.value)} ${item.unit}`,
      daily: `${daily}%`,
      tone: daily >= 20 ? (key === 'fibre' ? 'good' : 'high') : daily <= 5 ? 'low' : 'medium',
    };
  });
}

function demoConfirmedLabel(scenario: DemoScenario): ExtractedLabel {
  return {
    product_name: scenario.productName,
    serving: { grams_per_serving: scenario.servingGrams, household_measure: '1 serving' },
    calories: scenario.calories,
    sodium: confirmedNutrient(scenario.nutrients.sodium.value, scenario.nutrients.sodium.unit, scenario.nutrients.sodium.dv),
    added_sugar: confirmedNutrient(scenario.nutrients.added_sugar.value, scenario.nutrients.added_sugar.unit, scenario.nutrients.added_sugar.dv),
    saturated_fat: confirmedNutrient(scenario.nutrients.saturated_fat.value, scenario.nutrients.saturated_fat.unit, scenario.nutrients.saturated_fat.dv),
    fibre: confirmedNutrient(scenario.nutrients.fibre.value, scenario.nutrients.fibre.unit, scenario.nutrients.fibre.dv),
    protein: confirmedNutrient(scenario.nutrients.protein.value, scenario.nutrients.protein.unit, scenario.nutrients.protein.dv),
    allergens: scenario.allergens,
    missing_fields: [],
    user_confirmed: true,
  };
}

const nutrientNames: Record<string, string> = {
  sodium: 'Sodium',
  added_sugar: 'Added sugar',
  saturated_fat: 'Saturated fat',
  fibre: 'Fibre',
  protein: 'Protein',
};

function formatNumber(value: number): string {
  return Number.isInteger(value) ? String(value) : String(Math.round(value * 10) / 10);
}

function formatMass(amount: MassAmount | null): string {
  return amount ? `${formatNumber(amount.value)} ${amount.unit}` : 'Not available';
}

function evidenceNutrients(card?: EvidenceCard): ResultNutrient[] {
  if (!card?.calculation) return [];
  return ['sodium', 'added_sugar', 'saturated_fat', 'fibre', 'protein'].map((key) => {
    const result = card.calculation?.results[key];
    const dailyValue = result?.per_actual_portion_dv ?? null;
    const level = result?.per_actual_portion_dv_level ?? 'unknown';
    return {
      key,
      name: nutrientNames[key],
      value: formatMass(result?.per_actual_portion ?? null),
      daily: dailyValue === null ? 'No %DV' : `${formatNumber(dailyValue)}%`,
      dailyValue,
      tone: key === 'fibre' && level === 'high' ? 'good' : level,
      missing: !result?.per_actual_portion,
    };
  });
}

function nutrientViewsFromLabel(label: ExtractedLabel): NutrientView[] {
  return [
    ['sodium', 'Sodium'], ['added_sugar', 'Added sugar'], ['saturated_fat', 'Saturated fat'], ['fibre', 'Fibre'],
  ].map(([key, name]) => {
    const field = label[key] as NutrientField | undefined;
    const daily = field?.percent_daily_value ?? 0;
    return {
      key: key as NutrientKey,
      name,
      value: field?.amount ? `${field.amount.value} ${field.amount.unit}` : 'Not shown',
      daily: `${daily}%`,
      tone: daily >= 20 ? (key === 'fibre' ? 'good' : 'high') : daily <= 5 ? 'low' : 'medium',
    };
  });
}

function historySnapshot(analysis: AnalysisResult): AnalysisResult {
  if (!analysis.evidence_card) return analysis;
  return {
    evidence_card: { ...analysis.evidence_card, personalization: null },
    trace: (analysis.trace ?? []).filter((line) => !line.toLowerCase().includes('personalization')),
  };
}

function historyNote(analysis: AnalysisResult): string {
  const card = analysis.evidence_card;
  const calories = card?.calculation?.calories_per_actual_portion;
  const sodiumDv = card?.calculation?.results.sodium?.per_actual_portion_dv;
  const parts = [
    calories == null ? null : `${formatNumber(calories)} kcal`,
    sodiumDv == null ? null : `${formatNumber(sodiumDv)}% sodium DV`,
    card?.barcode_lookup?.found ? 'barcode checked' : null,
  ].filter(Boolean);
  return parts.length ? parts.join(' · ') : 'Confirmed label evidence';
}

function positiveNumber(value: string): number | null {
  const parsed = Number(value);
  return value.trim() && Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function buildProfilePayload(profile: ProfileForm): ProfilePayload {
  return {
    declared_allergens: profile.allergens.split(',').map((item) => item.trim()).filter(Boolean),
    dietary_preference: profile.dietaryPreference,
    daily_calorie_goal: positiveNumber(profile.calories),
    daily_protein_goal_g: positiveNumber(profile.protein),
    daily_fibre_goal_g: positiveNumber(profile.fibre),
    daily_sodium_limit_mg: positiveNumber(profile.sodium),
    daily_added_sugar_limit_g: positiveNumber(profile.addedSugar),
  };
}

function buildDemoAnalysis(scenarioId: DemoScenarioId, portion: number, profileForm: ProfileForm): AnalysisResult {
  const scenario = demoScenarios[scenarioId];
  if (scenario.refusalMessage) {
    return {
      evidence_card: {
        refused: true,
        message: scenario.refusalMessage,
        category: 'allergy_safety_guarantee',
        product_name: scenario.productName,
        missing_fields: [],
      },
      trace: ['Safety gate: refused an allergy-safety guarantee before generating a nutrition answer.'],
    };
  }
  const profile = buildProfilePayload(profileForm);
  const results = Object.fromEntries(Object.entries(scenario.nutrients).map(([key, item]) => {
    const dailyValue = item.dv === null ? null : item.dv * portion;
    const level: EvidenceNutrient['per_actual_portion_dv_level'] = dailyValue === null ? 'unknown' : dailyValue <= 5 ? 'low' : dailyValue >= 20 ? 'high' : 'moderate';
    return [key, {
    nutrient: key,
    per_actual_portion: { value: item.value * portion, unit: item.unit },
    per_actual_portion_dv: dailyValue,
    per_actual_portion_dv_level: level,
  } satisfies EvidenceNutrient];
  })) as Record<string, EvidenceNutrient>;
  const contribution = (key: string, label: string, consumed: number, target: number | null, unit: string, targetType: 'goal' | 'limit'): GoalContribution | null => target ? ({ key, label, consumed, target, unit, percent_of_target: Math.round(consumed / target * 1000) / 10, target_type: targetType }) : null;
  const watched = profile.declared_allergens.map((item) => item.toLowerCase().replace(/s$/, ''));
  const declaredMatches = scenario.allergens.declared_contains.filter((item) => watched.includes(item.toLowerCase().replace(/s$/, '')));
  const advisoryMatches = scenario.allergens.may_contain_statement.filter((item) => watched.includes(item.toLowerCase().replace(/s$/, '')));
  const allergyStatus = declaredMatches.length ? 'declared_match' : advisoryMatches.length ? 'advisory_match' : profile.declared_allergens.length ? 'no_match_found' : 'profile_not_provided';
  const allergyMessage = allergyStatus === 'declared_match'
    ? 'Stop and review: the demo package’s declared allergen statement matches your profile. This is not an allergy-safety decision.'
    : allergyStatus === 'advisory_match'
      ? 'Caution: the demo package’s “may contain” statement matches your profile. This is not an allergy-safety decision.'
      : allergyStatus === 'no_match_found'
        ? 'No matching allergen term was found in the demo text. This does not mean the product is allergy-safe.'
        : 'No personal allergens were entered. FoodProof Fit can only repeat the package allergen statement.';
  const goalContributions = [
    contribution('calories', 'Calories', scenario.calories * portion, profile.daily_calorie_goal, 'kcal', 'goal'),
    contribution('protein', 'Protein', scenario.nutrients.protein.value * portion, profile.daily_protein_goal_g, 'g', 'goal'),
    contribution('fibre', 'Fibre', scenario.nutrients.fibre.value * portion, profile.daily_fibre_goal_g, 'g', 'goal'),
    contribution('sodium', 'Sodium', scenario.nutrients.sodium.value * portion, profile.daily_sodium_limit_mg, 'mg', 'limit'),
    contribution('added_sugar', 'Added sugar', scenario.nutrients.added_sugar.value * portion, profile.daily_added_sugar_limit_g, 'g', 'limit'),
  ].filter((item): item is GoalContribution => item !== null);
  return {
    evidence_card: {
      refused: false,
      product_name: scenario.productName,
      missing_fields: [],
      calculation: { servings_consumed: portion, results, calories_per_actual_portion: scenario.calories * portion },
      citations: [{ id: 'fda-label-guide', title: 'U.S. Food and Drug Administration', section: 'How to understand and use the Nutrition Facts label', url: 'https://www.fda.gov/food/nutrition-facts-label/how-understand-and-use-nutrition-facts-label', text: 'The Nutrition Facts label supports informed food choices by showing serving and Daily Value information.' }],
      claim_verdicts: [],
      claim_sources: [],
      personalization: {
        allergen_match: { status: allergyStatus, declared_matches: declaredMatches, advisory_matches: advisoryMatches, ingredient_matches: [], message: allergyMessage },
        dietary_preference: profile.dietary_preference === 'none'
          ? { preference: 'none', status: 'not_requested', matched_terms: [], message: 'No dietary preference was selected.' }
          : scenario.dietaryConflictTerms.length
            ? { preference: profile.dietary_preference, status: 'possible_conflict', matched_terms: scenario.dietaryConflictTerms, message: `Possible ${profile.dietary_preference} conflict found in the demo ingredients. Review the original package.` }
            : { preference: profile.dietary_preference, status: 'not_verified', matched_terms: [], message: `FoodProof Fit did not find an obvious ${profile.dietary_preference} conflict, but it cannot verify the full supply chain.` },
        goal_contributions: goalContributions,
        disclaimer: 'Personalized comparisons use goals entered by the user and do not replace medical or dietetic advice.',
      },
    },
    trace: ['Safety gate: allowed an informational label request.', 'Calculation: recomputed the confirmed values for the selected portion.', 'Personalization: demo profile checked against the sample package.', 'FDA retrieval: matched the request with the FDA Nutrition Facts label guide.', 'Evidence card: assembled the explanation with its source and limitations.'],
  };
}

function parseNutrientAmount(text: string): NutrientField['amount'] {
  if (text.trim().toLowerCase() === 'not shown') return null;
  const match = text.trim().match(/^(\d+(?:\.\d+)?)\s*(g|mg|mcg)$/i);
  if (!match) throw new Error('Enter nutrient values like “140 mg” or “2 g”, or use “Not shown”.');
  return { value: Number(match[1]), unit: match[2].toLowerCase() as 'g' | 'mg' | 'mcg' };
}

function buildConfirmedLabel(label: ExtractedLabel, nutrients: NutrientView[]): ExtractedLabel {
  const confirmed: ExtractedLabel = { ...label, user_confirmed: true };
  const missing = new Set(label.missing_fields ?? []);
  for (const nutrient of nutrients) {
    const amount = parseNutrientAmount(nutrient.value);
    const current = label[nutrient.key] as NutrientField | undefined;
    confirmed[nutrient.key] = {
      ...current,
      amount,
      confidence: amount ? 1 : current?.confidence ?? 0,
      present_on_label: amount !== null,
    };
    if (amount) missing.delete(nutrient.key);
    else missing.add(nutrient.key);
  }
  confirmed.missing_fields = [...missing].sort();
  return confirmed;
}

export default function Home() {
  const [view, setView] = useState<View>('analyze');
  const [step, setStep] = useState<Step>('scan');
  const [photos, setPhotos] = useState<Partial<Record<PhotoSlot, PhotoEntry>>>({});
  const [portion, setPortion] = useState(1);
  const [productName, setProductName] = useState('Harvest Crunch');
  const [nutrients, setNutrients] = useState<NutrientView[]>(demoNutrients);
  const [servingGrams, setServingGrams] = useState(45);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [goal, setGoal] = useState('general_understanding');
  const [labelData, setLabelData] = useState<ExtractedLabel | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [barcode, setBarcode] = useState('');
  const [profile, setProfile] = useState<ProfileForm>(emptyProfile);
  const [demoScenarioId, setDemoScenarioId] = useState<DemoScenarioId>('daily_goals');
  const [confirmedProducts, setConfirmedProducts] = useState<ComparisonProduct[]>([]);
  const [historyEntries, setHistoryEntries] = useState<HistoryEntry[]>([]);
  const [historyHydrated, setHistoryHydrated] = useState(false);
  const completed = Object.keys(photos).length;
  const portionLabel = useMemo(() => `${portion} ${portion === 1 ? 'serving' : 'servings'}`, [portion]);
  const activeDemoScenario = demoScenarios[demoScenarioId];

  useEffect(() => {
    const presentationLink = window.setTimeout(() => {
      const params = new URLSearchParams(window.location.search);
      const requestedView = params.get('view');
      if (requestedView && ['analyze', 'compare', 'history', 'evals', 'privacy'].includes(requestedView)) {
        setView(requestedView as View);
      }
      const requestedDemo = params.get('demo');
      if (requestedDemo && ['daily_goals', 'allergen_alert', 'safe_refusal'].includes(requestedDemo)) {
        const demoId = requestedDemo as DemoScenarioId;
        const scenario = demoScenarios[demoId];
        loadDemoScenario(demoId);
        if (params.get('step') === 'result') {
          setAnalysis(buildDemoAnalysis(demoId, scenario.portion, scenario.profile));
          setStep('result');
        }
      }
    }, 0);
    return () => window.clearTimeout(presentationLink);
  }, []);

  useEffect(() => {
    const hydrateHistory = window.setTimeout(() => {
      try {
        const stored = window.sessionStorage.getItem(HISTORY_STORAGE_KEY);
        if (stored) {
          const parsed = JSON.parse(stored) as HistoryEntry[];
          if (Array.isArray(parsed)) setHistoryEntries(parsed.slice(0, 12));
        }
      } catch {
        setHistoryEntries([]);
      } finally {
        setHistoryHydrated(true);
      }
    }, 0);
    return () => window.clearTimeout(hydrateHistory);
  }, []);

  useEffect(() => {
    if (!historyHydrated) return;
    window.sessionStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(historyEntries));
  }, [historyEntries, historyHydrated]);

  function loadDemoScenario(id: DemoScenarioId) {
    const scenario = demoScenarios[id];
    setDemoScenarioId(id);
    setProfile(scenario.profile);
    setGoal(scenario.goal);
    setProductName(scenario.productName);
    setServingGrams(scenario.servingGrams);
    setNutrients(demoNutrientViews(scenario));
    setPortion(scenario.portion);
    setPhotos({});
    setLabelData(null);
    setAnalysis(null);
    setError(null);
    setBarcode('');
  }

  function addPhoto(slot: PhotoSlot, event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setError(null);
    setPhotos((current) => ({ ...current, [slot]: { file, url: URL.createObjectURL(file) } }));
  }

  async function beginAnalysis() {
    if (completed === 0) { loadDemoScenario(demoScenarioId); setStep('confirm'); return; }
    if (!photos.front || !photos.nutrition || !photos.ingredients) return;
    setIsAnalyzing(true);
    setError(null);
    const body = new FormData();
    body.append('front', photos.front.file);
    body.append('nutrition', photos.nutrition.file);
    body.append('ingredients', photos.ingredients.file);
    try {
      const response = await fetch('/api/extract', { method: 'POST', body });
      const data = await response.json() as ExtractedLabel & { detail?: string };
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'One or more photos need to be retaken.');
      setProductName(data.product_name || 'Your product');
      setServingGrams(data.serving?.grams_per_serving || 0);
      setNutrients(nutrientViewsFromLabel(data));
      setLabelData(data as ExtractedLabel);
      setStep('confirm');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'We could not analyze those photos.');
    } finally { setIsAnalyzing(false); }
  }

  async function confirmAndAnalyze() {
    if (!labelData) {
      setAnalysis(buildDemoAnalysis(demoScenarioId, portion, profile));
      setStep('result');
      return;
    }
    if (barcode && !/^\d{8,14}$/.test(barcode)) {
      setError('Enter an 8–14 digit barcode, or leave the barcode field blank.');
      return;
    }
    setIsAnalyzing(true);
    setError(null);
    try {
      const confirmedLabel = buildConfirmedLabel(labelData, nutrients);
      setLabelData(confirmedLabel);
      const response = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ label: confirmedLabel, servings_consumed: portion, goal, barcode: barcode || null, profile: buildProfilePayload(profile) }),
      });
      const data = await response.json() as AnalysisResult & { detail?: string };
      if (!response.ok) throw new Error(data.detail || 'The confirmed label could not be analyzed.');
      setAnalysis(data);
      setConfirmedProducts((current) => [
        ...current.filter((item) => item.name !== (confirmedLabel.product_name || productName)),
        {
          label: confirmedLabel,
          name: confirmedLabel.product_name || productName,
          servings_consumed: portion,
          source: 'confirmed' as const,
        },
      ].slice(-2));
      const storedAnalysis = historySnapshot(data);
      const storedName = confirmedLabel.product_name || productName;
      setHistoryEntries((current) => [{
        id: `${Date.now()}-${storedName}`,
        created_at: new Date().toISOString(),
        product_name: storedName,
        portion,
        goal,
        barcode,
        label: confirmedLabel,
        analysis: storedAnalysis,
        note: historyNote(storedAnalysis),
      }, ...current.filter((item) => item.product_name !== storedName)].slice(0, 12));
      setStep('result');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The confirmed label could not be analyzed.');
    } finally { setIsAnalyzing(false); }
  }

  function openHistoryEntry(entry: HistoryEntry) {
    setPhotos({});
    setLabelData(entry.label);
    setAnalysis(entry.analysis);
    setProductName(entry.product_name);
    setServingGrams(entry.label.serving?.grams_per_serving || 0);
    setNutrients(nutrientViewsFromLabel(entry.label));
    setPortion(entry.portion);
    setGoal(entry.goal);
    setBarcode(entry.barcode);
    setProfile(emptyProfile);
    setError(null);
    setView('analyze');
    setStep('result');
  }

  const fallbackNutrients: ResultNutrient[] = nutrients.map((item) => {
    const amount = Number.parseFloat(item.value);
    const daily = Number.parseFloat(item.daily);
    const unit = item.value.replace(String(amount), '').trim();
    return {
      ...item,
      value: Number.isFinite(amount) ? `${Math.round(amount * portion * 10) / 10} ${unit}` : item.value,
      daily: Number.isFinite(daily) ? `${Math.round(daily * portion)}%` : item.daily,
      dailyValue: Number.isFinite(daily) ? Math.round(daily * portion) : null,
      missing: !Number.isFinite(amount),
    };
  });
  const evidenceCard = analysis?.evidence_card;
  const backendNutrients = evidenceNutrients(evidenceCard);
  const resultNutrients = backendNutrients.length ? backendNutrients : fallbackNutrients;
  const isDemo = !labelData;
  const preferredNutrient = {
    lower_added_sugar: 'added_sugar',
    lower_sodium: 'sodium',
    higher_fibre: 'fibre',
  }[goal];
  const insightNutrient = resultNutrients.find((item) => item.key === preferredNutrient && !item.missing)
    ?? resultNutrients.find((item) => !item.missing);
  const insightTitle = insightNutrient
    ? `${insightNutrient.name}: ${insightNutrient.dailyValue === null ? insightNutrient.value : `${insightNutrient.daily} of Daily Value`}`
    : 'The label is missing key nutrition values';
  const insightText = insightNutrient
    ? `For ${portionLabel}, the confirmed label calculates to ${insightNutrient.value}${insightNutrient.dailyValue === null ? '.' : ` (${insightNutrient.daily} DV).`} This is a factual label calculation, not a health verdict.`
    : 'FoodProof Fit did not invent the missing numbers. Review the package or provide a clearer nutrition-panel photo.';
  const primarySource = evidenceCard?.citations?.[0];
  const primaryClaim = evidenceCard?.claim_verdicts?.[0];
  const claimSource = evidenceCard?.claim_sources?.find((source) => primaryClaim?.citation_ids.includes(source.id));
  const claimHeading = primaryClaim
    ? primaryClaim.verdict === 'supported'
      ? `“${primaryClaim.claim_text}” matches this reference check`
      : primaryClaim.verdict === 'not_supported'
        ? `“${primaryClaim.claim_text}” does not match this reference check`
        : `“${primaryClaim.claim_text}” needs more evidence`
    : 'No front-of-pack claim was checked';
  const claimBadge = primaryClaim?.verdict === 'supported'
    ? '✓ Consistent with the cited reference'
    : primaryClaim?.verdict === 'not_supported'
      ? '! Not consistent with the cited reference'
      : '? Insufficient evidence for a verdict';
  const missingFields = evidenceCard?.missing_fields ?? labelData?.missing_fields ?? [];
  const allergens = labelData?.allergens ?? (isDemo ? activeDemoScenario.allergens : undefined);
  const personalization = evidenceCard?.personalization;
  const barcodeLookup = evidenceCard?.barcode_lookup;
  const barcodeDeltaFlags = evidenceCard?.delta_flags ?? [];
  const personalAllergen = personalization?.allergen_match;
  const allergenMatchNames = personalAllergen?.status === 'declared_match'
    ? personalAllergen.declared_matches
    : personalAllergen?.status === 'advisory_match'
      ? personalAllergen.advisory_matches
      : personalAllergen?.ingredient_matches ?? [];
  const friendlyTrace = (analysis?.trace ?? []).map((line) => {
    const normalized = line.toLowerCase();
    if (normalized.includes('safety gate')) return 'Checked that the request stays within FoodProof Fit’s safety boundaries';
    if (normalized.includes('calculation') && !normalized.includes('skipped')) return `Calculated the nutrition values for ${portionLabel}`;
    if (normalized.includes('personalization') && normalized.includes('skipped')) return 'Personalization was skipped because no profile was provided';
    if (normalized.includes('personalization')) return 'Matched the confirmed portion with your allergen profile and daily targets';
    if ((normalized.includes('retrieval') || normalized.includes('fda')) && normalized.includes('skipped')) return 'FDA guidance lookup was skipped because no goal was selected';
    if (normalized.includes('retrieval') || normalized.includes('fda')) return 'Matched the result with relevant FDA guidance';
    if (normalized.includes('claim') && normalized.includes('skipped')) return 'No front-of-pack claim was available to check';
    if (normalized.includes('claim')) return 'Compared front-of-pack claims with the confirmed label';
    if (normalized.includes('barcode') && normalized.includes('skipped')) return 'Barcode lookup was skipped; the package remained the primary evidence';
    if (normalized.includes('barcode')) return barcode ? 'Checked the barcode as supporting information' : 'Used the package as the primary evidence';
    if (normalized.includes('comparison') && normalized.includes('skipped')) return 'Product comparison was not requested';
    if (normalized.includes('comparison')) return 'Checked whether a fair product comparison was available';
    if (normalized.includes('evidence card')) return 'Assembled the explanation with sources and limitations';
    return line.replace(/^[^:]+:\s*/, '');
  }).filter((line, index, all) => line && all.indexOf(line) === index);

  return (
    <main className="app-shell">
      <header className="topbar">
        <button className="brand brand-button" onClick={() => { setView('analyze'); setStep('scan'); }} aria-label="FoodProof Fit home"><span className="brand-mark">F</span><span>FoodProof Fit</span></button>
        <nav className="main-nav" aria-label="Primary navigation"><button className={view === 'analyze' ? 'selected' : ''} onClick={() => setView('analyze')}>Analyze</button><button className={view === 'compare' ? 'selected' : ''} onClick={() => setView('compare')}>Compare</button><button className={view === 'history' ? 'selected' : ''} onClick={() => setView('history')}>History</button><button className={view === 'evals' ? 'selected' : ''} onClick={() => setView('evals')}>Evals</button></nav>
        <button className="avatar" onClick={() => setView('privacy')} aria-label="Open account and privacy">VG</button>
      </header>
      {view === 'analyze' && <div className="stepper" aria-label="Analysis progress">
        {['Scan', 'Confirm', 'Understand'].map((label, index) => {
          const activeIndex = step === 'scan' ? 0 : step === 'confirm' ? 1 : 2;
          return <div className={`step ${index <= activeIndex ? 'active' : ''}`} key={label}><span>{index + 1}</span>{label}</div>;
        })}
      </div>}

      {view === 'analyze' && step === 'scan' && <section className="screen scan-screen">
        <div className="hero-copy"><span className="eyebrow">Know what you’re eating</span><h1>Turn the label around.<br /><em>Make it personal.</em></h1><p>Photograph three sides of the package. FoodProof Fit checks the facts against the allergens and daily targets you enter.</p></div>
        <div className="capture-card">
          <div className="capture-head"><div><span className="mini-label">New analysis</span><h2>Add your package photos</h2></div><span className="count">{completed}/3 ready</span></div>
          <section className="demo-scenarios" aria-labelledby="demo-scenarios-title">
            <div className="demo-intro"><div><span className="mini-label">Presenter-safe demo</span><h3 id="demo-scenarios-title">Choose a story to demonstrate</h3></div><small>Synthetic label data—kept separate from live-photo evidence</small></div>
            <div className="demo-scenario-grid">{Object.values(demoScenarios).map((scenario) => <button type="button" className={`demo-scenario ${demoScenarioId === scenario.id ? 'selected' : ''}`} aria-pressed={demoScenarioId === scenario.id} onClick={() => loadDemoScenario(scenario.id)} key={scenario.id}><span>{scenario.label}</span><strong>{scenario.title}</strong><small>{scenario.summary}</small><em>{scenario.request}</em></button>)}</div>
          </section>
          <label className="goal-picker"><span>What matters most today?</span><select value={goal} onChange={(event) => setGoal(event.target.value)}><option value="general_understanding">Understand this label</option><option value="lower_added_sugar">Lower added sugar</option><option value="lower_sodium">Lower sodium</option><option value="higher_fibre">Higher fibre</option><option value="product_comparison">Compare products</option></select></label>
          <details className="profile-panel" open>
            <summary><span><b>Personalize this check</b><small>Optional—compare the product with allergens and daily targets you enter</small></span><span>Profile</span></summary>
            <div className="profile-toolbar"><p>These values are not medical recommendations. Enter targets you already use, or load example values for the prototype demo.</p><button type="button" className="text-button" onClick={() => setProfile(exampleProfile)}>Load example profile</button></div>
            <div className="profile-grid">
              <label className="profile-wide"><span>Allergens to watch</span><input value={profile.allergens} onChange={(event) => setProfile((current) => ({ ...current, allergens: event.target.value }))} placeholder="e.g. peanuts, milk" /><small>Separate multiple allergens with commas</small></label>
              <label><span>Dietary preference</span><select value={profile.dietaryPreference} onChange={(event) => setProfile((current) => ({ ...current, dietaryPreference: event.target.value as ProfileForm['dietaryPreference'] }))}><option value="none">No preference</option><option value="vegetarian">Vegetarian</option><option value="vegan">Vegan</option></select></label>
              <ProfileNumber label="Daily calories" unit="kcal" value={profile.calories} onChange={(value) => setProfile((current) => ({ ...current, calories: value }))} />
              <ProfileNumber label="Daily protein goal" unit="g" value={profile.protein} onChange={(value) => setProfile((current) => ({ ...current, protein: value }))} />
              <ProfileNumber label="Daily fibre goal" unit="g" value={profile.fibre} onChange={(value) => setProfile((current) => ({ ...current, fibre: value }))} />
              <ProfileNumber label="Daily sodium limit" unit="mg" value={profile.sodium} onChange={(value) => setProfile((current) => ({ ...current, sodium: value }))} />
              <ProfileNumber label="Daily added-sugar limit" unit="g" value={profile.addedSugar} onChange={(value) => setProfile((current) => ({ ...current, addedSugar: value }))} />
            </div>
          </details>
          <div className="photo-grid">
            <PhotoInput slot="front" title="Front of pack" hint="Claims & product name" photo={photos.front?.url} onChange={addPhoto} />
            <PhotoInput slot="nutrition" title="Nutrition facts" hint="Keep the full panel visible" photo={photos.nutrition?.url} onChange={addPhoto} featured />
            <PhotoInput slot="ingredients" title="Ingredients" hint="Include allergen statement" photo={photos.ingredients?.url} onChange={addPhoto} />
          </div>
          <label className="barcode-field"><span><strong>Barcode</strong><small>Optional supporting check—it never overrides the package.</small></span><input inputMode="numeric" maxLength={14} value={barcode} onChange={(event) => setBarcode(event.target.value.replace(/\D/g, ''))} placeholder="Enter 8–14 digits" aria-label="Product barcode" /></label>
          {error && <p className="error-message" role="alert">{error}</p>}
          <div className="capture-footer"><p><span>◆</span> {completed === 0 ? `${activeDemoScenario.title} is ready. You will still confirm the sample values.` : 'Photos are processed securely and aren’t used to train models.'}</p><button className="primary" onClick={beginAnalysis} disabled={isAnalyzing || (completed > 0 && completed < 3)}>{isAnalyzing ? 'Checking photos…' : completed === 0 ? 'Continue with selected demo' : 'Check my label'} <span>→</span></button></div>
        </div>
      </section>}

      {view === 'analyze' && step === 'confirm' && <section className="screen confirm-screen">
        <button className="back" onClick={() => setStep('scan')}>← Back to photos</button>
        <div className="section-heading"><span className="eyebrow">Quick accuracy check</span><h1>Does this match the label?</h1><p>AI can misread small print. Confirm these values before we calculate anything.</p></div>
        <div className="confirm-layout">
          <article className="product-summary"><div className="pack-visual"><span>Food</span><strong>PROOF</strong><small>confirmed label</small></div><div><span className="verified">✓ Clear image</span><h2>{productName}</h2><p>{servingGrams ? `${servingGrams} g per serving` : 'Serving size needs confirmation'}</p></div></article>
          <article className="facts-card">
            <div className="facts-title"><div><span className="mini-label">Extracted values</span><h2>Nutrition facts</h2></div><button className="text-button">Edit all</button></div>
            <div className="facts-grid">{nutrients.map((item, index) => <label key={item.name}><span>{item.name}</span><input value={item.value} onChange={(event) => setNutrients((current) => current.map((entry, entryIndex) => entryIndex === index ? { ...entry, value: event.target.value } : entry))} /><small>{item.daily} daily value</small></label>)}</div>
            <div className="portion-row"><div><strong>Your portion</strong><span>Label serving size: {servingGrams || '—'} g</span></div><div className="counter"><button onClick={() => setPortion(Math.max(.5, portion - .5))}>−</button><strong>{portionLabel}</strong><button onClick={() => setPortion(portion + .5)}>+</button></div></div>
            {error && <p className="error-message" role="alert">{error}</p>}
            <button className="primary wide" onClick={confirmAndAnalyze} disabled={isAnalyzing}>{isAnalyzing ? 'Building your Evidence Card…' : 'Confirm and show my results'} <span>→</span></button>
          </article>
        </div>
      </section>}

      {view === 'analyze' && step === 'result' && <section className="screen result-screen">
        <button className="back" onClick={() => setStep('confirm')}>← Review values</button>
        <div className="result-hero"><div><span className="eyebrow">{evidenceCard?.product_name || productName} · {portionLabel}{isDemo ? ` · ${activeDemoScenario.label}` : ''}</span><h1>{evidenceCard?.refused ? 'FoodProof Fit stopped safely.' : 'Your label, made personal.'}</h1><p>{evidenceCard?.refused ? 'The request crossed a safety boundary, so no nutrition answer was generated.' : 'Every number below comes from the label values you confirmed and the profile you entered.'}</p>{isDemo && <p className="scenario-request"><strong>Demo request:</strong> “{activeDemoScenario.request}”</p>}</div><div className={`score ${evidenceCard?.refused ? 'refused' : ''}`}><span>Evidence status</span><strong>{evidenceCard?.refused ? 'Stopped' : isDemo ? 'Demo' : 'Ready'}</strong><small>{isDemo ? 'Synthetic case—not vision evidence' : 'Based on confirmed label values'}</small></div></div>
        {evidenceCard?.refused ? <article className="safety-card refusal-card"><span className="mini-label">Safety boundary</span><h2>We cannot answer that request</h2><p>{evidenceCard.message}</p></article> : <div className="result-grid">
          <article className="insight-card spotlight"><span className="insight-icon">↗</span><div><span className="mini-label">Worth knowing</span><h2>{insightTitle}</h2><p>{insightText}</p>{primarySource ? <a href={primarySource.url} target="_blank" rel="noreferrer">View {primarySource.title} — {primarySource.section} ↗</a> : isDemo ? <a href="https://www.fda.gov/food/nutrition-facts-label/how-understand-and-use-nutrition-facts-label" target="_blank" rel="noreferrer">View the FDA label guide ↗</a> : null}</div></article>
          <article className="nutrient-card"><div className="nutrient-head"><div><span className="mini-label">Per your portion</span><h2>Nutrient snapshot</h2>{evidenceCard?.calculation?.calories_per_actual_portion != null && <small className="calorie-note">{formatNumber(evidenceCard.calculation.calories_per_actual_portion)} calories for this portion</small>}</div><span className="portion-chip">{portionLabel}</span></div>{resultNutrients.map((item) => <div className={`nutrient-row ${item.missing ? 'missing' : ''}`} key={item.name}><span>{item.name}</span><strong>{item.value}</strong><div className="bar"><i className={item.tone} style={{ width: `${Math.min(item.dailyValue ?? 0, 100)}%` }} /></div><small>{item.dailyValue === null ? item.daily : `${item.daily} DV`}</small></div>)}</article>
          <article className="claim-card"><span className="mini-label">Front-of-pack check</span><h2>{claimHeading}</h2><p>{primaryClaim?.rationale || 'No recognized claim was captured from the front photo, so FoodProof Fit did not invent a claim verdict.'}</p><span className={`evidence-badge ${primaryClaim?.verdict || 'insufficient_evidence'}`}>{claimBadge}</span>{claimSource && <a className="source-link" href={claimSource.url} target="_blank" rel="noreferrer">View cited claim reference ↗</a>}</article>
          {!!barcode && <article className={`safety-card barcode-result ${!barcodeLookup?.found ? 'unavailable' : barcodeDeltaFlags.length ? 'review' : 'consistent'}`}><span className="mini-label">Supporting barcode check</span><h2>{!barcodeLookup?.found ? 'No supporting record was available' : barcodeDeltaFlags.length ? `${barcodeDeltaFlags.length} meaningful difference${barcodeDeltaFlags.length === 1 ? '' : 's'} flagged` : 'No major mismatch found'}</h2><p>{!barcodeLookup?.found ? 'The barcode lookup could not provide a usable historical record. Your package photos and confirmed values remain the evidence for this result.' : barcodeDeltaFlags.length ? `The current confirmed label differs from the historical Open Food Facts record for ${barcodeLookup.product_name || 'this barcode'}. Review the package; FoodProof Fit did not replace your values.` : `The confirmed label is broadly consistent with the historical Open Food Facts record for ${barcodeLookup.product_name || 'this barcode'}. The package remains the primary evidence.`}</p>{barcodeDeltaFlags.length > 0 && <ul>{barcodeDeltaFlags.map((flag) => <li key={flag.nutrient}><strong>{nutrientNames[flag.nutrient] || flag.nutrient.replaceAll('_', ' ')}</strong><span>{formatNumber(flag.percent_difference)}% difference</span></li>)}</ul>}<small>Barcode {barcode} · Differences of 20% or more are flagged.</small></article>}
          {personalAllergen && <article className={`safety-card personal-alert ${personalAllergen.status}`}><span className="mini-label">Your allergen profile</span><h2>{personalAllergen.status === 'declared_match' ? `Declared match: ${allergenMatchNames.join(', ')}` : personalAllergen.status === 'advisory_match' ? `“May contain” match: ${allergenMatchNames.join(', ')}` : personalAllergen.status === 'ingredient_match' ? `Ingredient match: ${allergenMatchNames.join(', ')}` : personalAllergen.status === 'no_match_found' ? 'No matching term found' : 'No allergens entered'}</h2><p>{personalAllergen.message}</p>{personalization?.dietary_preference.status !== 'not_requested' && <div className={`diet-check ${personalization?.dietary_preference.status}`}><strong>{personalization?.dietary_preference.preference} check</strong><span>{personalization?.dietary_preference.message}</span></div>}</article>}
          {!!personalization?.goal_contributions.length && <article className="claim-card goal-card"><span className="mini-label">Your daily targets</span><h2>What this portion contributes</h2><div className="goal-list">{personalization.goal_contributions.map((item) => <div className="goal-row" key={item.key}><div><strong>{item.label}</strong><small>{formatNumber(item.consumed)} {item.unit} of your {formatNumber(item.target)} {item.unit} {item.target_type}</small></div><b>{formatNumber(item.percent_of_target)}%</b><div className="goal-bar"><i className={item.target_type} style={{ width: `${Math.min(item.percent_of_target, 100)}%` }} /></div></div>)}</div><p className="profile-disclaimer">{personalization.disclaimer}</p></article>}
          <article className="safety-card"><span className="mini-label">Ingredients and allergens</span><h2>{allergens?.declared_contains?.length ? `Label says: contains ${allergens.declared_contains.join(', ')}` : 'No “contains” statement was captured'}</h2><p>{allergens?.may_contain_statement?.length ? `The label also says “may contain”: ${allergens.may_contain_statement.join(', ')}. ` : ''}FoodProof Fit repeats declared package information; it cannot provide allergy clearance or guarantee safety.</p></article>
          {!!missingFields.length && <article className="safety-card"><span className="mini-label">Missing evidence</span><h2>Some values remain unknown</h2><p>{missingFields.join(', ').replaceAll('_', ' ').replaceAll('.', ' → ')}</p></article>}
          {primarySource && <article className="safety-card source-card"><span className="mini-label">Retrieved evidence</span><h2>{primarySource.section}</h2><p>{primarySource.text}</p><a href={primarySource.url} target="_blank" rel="noreferrer">Open original FDA page ↗</a></article>}
        </div>}
        {!evidenceCard?.refused && <AlternativesPanel key={`${productName}-${demoScenarioId}`} currentLabel={labelData || demoConfirmedLabel(activeDemoScenario)} profile={profile} currentBarcode={barcode} initialGoal={(['lower_sodium', 'lower_added_sugar', 'higher_fibre'].includes(goal) ? goal : 'lower_sodium') as AlternativeGoalId} isDemo={isDemo} />}
        {!!labelData && friendlyTrace.length > 0 && <details className="trace-card"><summary><span>How we checked this label</span><small>See the evidence steps behind this result</small></summary><ol>{friendlyTrace.map((line, index) => <li key={`${index}-${line}`}><span className="trace-check">✓</span><span>{line}</span></li>)}</ol></details>}
        <div className="result-actions"><button className="secondary" onClick={() => { setPhotos({}); setLabelData(null); setAnalysis(null); loadDemoScenario('daily_goals'); setStep('scan'); }}>Scan another product</button>{confirmedProducts.length >= 2 && <button className="primary" onClick={() => setView('compare')}>Compare saved products <span>→</span></button>}{isDemo && <button className="primary" onClick={() => { const ids: DemoScenarioId[] = ['daily_goals', 'allergen_alert', 'safe_refusal']; const next = ids[(ids.indexOf(demoScenarioId) + 1) % ids.length]; loadDemoScenario(next); setStep('scan'); }}>Load next demo <span>→</span></button>}</div>
      </section>}
      {view === 'compare' && <ComparisonView confirmedProducts={confirmedProducts} onAnalyze={() => { setView('analyze'); setStep('scan'); }} />}
      {view === 'history' && <HistoryView items={historyEntries} onOpen={openHistoryEntry} onNew={() => { setView('analyze'); setStep('scan'); }} />}
      {view === 'evals' && <EvalsView />}
      {view === 'privacy' && <PrivacyView />}
    </main>
  );
}

function ComparisonView({ confirmedProducts, onAnalyze }: { confirmedProducts: ComparisonProduct[]; onAnalyze: () => void }) {
  const [basis, setBasis] = useState<'serving' | 'portion' | '100g'>('100g');
  const [comparison, setComparison] = useState<ComparisonResult | null>(null);
  const [comparisonError, setComparisonError] = useState<string | null>(null);
  const [isComparing, setIsComparing] = useState(true);
  const products = useMemo(
    () => confirmedProducts.length >= 2 ? confirmedProducts.slice(-2) : comparisonDemoProducts,
    [confirmedProducts],
  );
  const isDemoComparison = confirmedProducts.length < 2;

  useEffect(() => {
    let active = true;
    const compareProducts = window.setTimeout(() => {
      setIsComparing(true);
      setComparisonError(null);
      fetch('/api/compare', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ product_a: products[0], product_b: products[1] }),
      })
        .then(async (response) => {
          const data = await response.json() as ComparisonResult & { detail?: string };
          if (!response.ok) throw new Error(data.detail || 'The products could not be compared.');
          if (active) setComparison(data);
        })
        .catch((caught) => {
          if (active) setComparisonError(caught instanceof Error ? caught.message : 'The products could not be compared.');
        })
        .finally(() => { if (active) setIsComparing(false); });
    }, 0);
    return () => { active = false; window.clearTimeout(compareProducts); };
  }, [products]);

  const basisKey = basis === 'serving' ? 'per_serving' : basis === 'portion' ? 'per_actual_portion' : 'per_100g';
  const nutrientKeys = ['added_sugar', 'sodium', 'saturated_fat', 'fibre', 'protein'];
  const rows = nutrientKeys.map((key) => {
    const a = comparison?.product_a.calculation.results[key]?.[basisKey] ?? null;
    const b = comparison?.product_b.calculation.results[key]?.[basisKey] ?? null;
    const higherIsUseful = key === 'fibre' || key === 'protein';
    let signal = 'Not enough evidence';
    if (a && b) {
      if (a.value === b.value) signal = 'Same value';
      else if ((higherIsUseful && a.value > b.value) || (!higherIsUseful && a.value < b.value)) signal = comparison?.product_a.label || 'Product A';
      else signal = comparison?.product_b.label || 'Product B';
    }
    return { key, name: nutrientNames[key], a, b, signal };
  });

  return <section className="screen feature-screen"><div className="feature-heading"><span className="eyebrow">Fair comparison</span><h1>Same basis. Clearer choice.</h1><p>FoodProof Fit compares confirmed label values on the same basis instead of trusting package serving sizes.</p></div>{isDemoComparison && <p className="comparison-demo-note"><strong>Presenter-safe example:</strong> these are synthetic confirmed labels. Scan and confirm two products to replace them with live results.</p>}<div className="compare-products"><ProductMini product={products[0]} color="gold" /><div className="versus">VS</div><ProductMini product={products[1]} color="green" /></div><div className="basis-toggle"><button className={basis === 'serving' ? 'active' : ''} onClick={() => setBasis('serving')}>Per labelled serving</button><button className={basis === 'portion' ? 'active' : ''} onClick={() => setBasis('portion')}>Per chosen portion</button><button className={basis === '100g' ? 'active' : ''} onClick={() => setBasis('100g')}>Per 100 g</button></div>{comparison && basis === '100g' && !comparison.per_100g_available && <p className="comparison-refusal" role="status"><strong>Comparison stopped for this view.</strong> {comparison.per_100g_unavailable_reason}</p>}{comparisonError && <p className="error-message" role="alert">{comparisonError}</p>}{isComparing ? <article className="comparison-loading">Checking both confirmed labels on the selected basis…</article> : comparison && <article className="comparison-card"><div className="comparison-row header"><span>Nutrient</span><span>{comparison.product_a.label}</span><span>{comparison.product_b.label}</span><span>Comparison signal*</span></div>{rows.map((row) => <div className="comparison-row" key={row.key}><strong>{row.name}</strong><span>{formatMass(row.a)}</span><span>{formatMass(row.b)}</span><span className="winner">{row.signal}</span></div>)}<p className="table-note">*Lower is signalled for added sugar, sodium and saturated fat; higher is signalled for fibre and protein. This is a nutrient-by-nutrient comparison—not a universal “healthier” verdict.</p></article>}<div className="feature-actions"><button className="secondary" onClick={onAnalyze}>Analyze another product</button><button className="primary" onClick={onAnalyze}>{isDemoComparison ? 'Scan two products' : 'Replace a product'}</button></div></section>;
}

function ProductMini({ product, color }: { product: ComparisonProduct; color: string }) {
  const grams = product.label.serving?.grams_per_serving;
  return <article className="product-mini"><span className={`mini-pack ${color}`}>FP</span><div><strong>{product.name}</strong><small>{grams ? `${formatNumber(grams)} g labelled serving` : 'Serving weight unavailable'}</small></div><span className="verified">✓ {product.source === 'demo' ? 'Demo confirmed' : 'User confirmed'}</span></article>;
}

function AlternativesPanel({ currentLabel, profile, currentBarcode, initialGoal, isDemo }: { currentLabel: ExtractedLabel; profile: ProfileForm; currentBarcode: string; initialGoal: AlternativeGoalId; isDemo: boolean }) {
  const [category, setCategory] = useState<AlternativeCategoryId>('snack_bars');
  const [alternativeGoal, setAlternativeGoal] = useState<AlternativeGoalId>(initialGoal);
  const [result, setResult] = useState<AlternativeSearchResult | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  async function findAlternatives() {
    setIsSearching(true);
    setSearchError(null);
    setResult(null);
    try {
      const response = await fetch('/api/alternatives', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          label: currentLabel,
          category,
          goal: alternativeGoal,
          profile: buildProfilePayload(profile),
          current_barcode: currentBarcode || null,
          limit: 3,
        }),
      });
      const data = await response.json() as AlternativeSearchResult & { detail?: string };
      if (!response.ok) throw new Error(data.detail || 'The live catalogue could not be searched.');
      setResult(data);
    } catch (caught) {
      setSearchError(caught instanceof Error ? caught.message : 'The live catalogue could not be searched.');
    } finally {
      setIsSearching(false);
    }
  }

  return <article className="alternatives-card">
    <div className="alternatives-heading"><div><span className="mini-label">Live Open Food Facts catalogue</span><h2>Find a better-aligned alternative</h2><p>Choose one priority. FoodProof Fit searches the same product category, normalizes the available records per 100 g, and explains every candidate without issuing a universal health score.</p></div><span className="live-data-chip">Live data</span></div>
    {isDemo && <p className="alternative-demo-note"><strong>Demonstration mode:</strong> the current product is synthetic; any alternatives returned come from the live catalogue and are clearly separated from the demo label.</p>}
    <div className="alternative-controls">
      <label><span>Product category</span><select value={category} onChange={(event) => { setCategory(event.target.value as AlternativeCategoryId); setResult(null); }}><option value="snack_bars">Snack bars</option><option value="breakfast_cereals">Breakfast cereals</option><option value="canned_soups">Canned soups</option><option value="crackers">Crackers</option></select></label>
      <label><span>Personal priority</span><select value={alternativeGoal} onChange={(event) => { setAlternativeGoal(event.target.value as AlternativeGoalId); setResult(null); }}><option value="lower_sodium">Lower sodium</option><option value="higher_fibre">Higher fibre</option><option value="lower_added_sugar">Lower added sugar</option></select></label>
      <button className="primary" onClick={findAlternatives} disabled={isSearching}>{isSearching ? 'Searching live catalogue…' : 'Find alternatives'} <span>→</span></button>
    </div>
    {searchError && <p className="error-message" role="alert">{searchError}</p>}
    {result && result.status !== 'ready' && <div className="alternative-stop" role="status"><strong>No unsupported recommendation was generated.</strong><p>{result.message}</p><small>{result.evidence_note}</small></div>}
    {result?.status === 'ready' && <>
      <div className="alternative-result-head"><div><span className="mini-label">Evidence-bounded shortlist</span><h3>{result.message}</h3></div><small>{result.candidates_searched} catalogue records checked</small></div>
      <div className="alternative-grid">{result.alternatives.map((candidate, index) => <article className="alternative-candidate" key={candidate.barcode}><div className="candidate-rank">{index + 1}</div><div className="candidate-title"><span>{candidate.brands[0] || 'Brand not listed'}</span><h3>{candidate.product_name}</h3></div><strong className="improvement">{formatNumber(candidate.improvement_percent)}% better aligned</strong><p>{candidate.reason}</p><div className="candidate-values"><span><small>Current product</small><b>{formatNumber(candidate.current_value_per_100g)} {candidate.unit}</b></span><i>→</i><span><small>Candidate record</small><b>{formatNumber(candidate.value_per_100g)} {candidate.unit}</b></span></div><div className={`candidate-evidence ${candidate.allergen_status}`}><strong>{candidate.allergen_status === 'not_verified' ? 'Allergen evidence incomplete' : candidate.allergen_status === 'no_declared_match' ? 'No declared profile match found' : 'Allergen check not requested'}</strong><span>{candidate.allergen_note}</span></div>{candidate.dietary_status !== 'not_requested' && <div className={`candidate-evidence ${candidate.dietary_status}`}><strong>Dietary preference: {candidate.dietary_status.replace('_', ' ')}</strong><span>{candidate.dietary_note}</span></div>}<small className="availability-note">{candidate.availability_note}</small><a href={candidate.source_url} target="_blank" rel="noreferrer">Verify the Open Food Facts record ↗</a></article>)}</div>
      <p className="alternative-source">Source: <a href={result.source_url} target="_blank" rel="noreferrer">{result.source_name}</a>, used under its open-data terms. {result.evidence_note}</p>
    </>}
  </article>;
}

function HistoryView({ items, onOpen, onNew }: { items: HistoryEntry[]; onOpen: (entry: HistoryEntry) => void; onNew: () => void }) {
  const [query, setQuery] = useState('');
  const filtered = items.filter((item) => item.product_name.toLowerCase().includes(query.trim().toLowerCase()));
  const colors = ['gold', 'cream', 'red'];
  return <section className="screen feature-screen"><div className="feature-heading left"><span className="eyebrow">This session</span><h1>Confirmed label checks</h1><p>Reopen the structured facts, calculation and citations from a completed real-label analysis.</p></div><div className="history-toolbar"><label><span className="sr-only">Search history</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search confirmed products" /></label><button className="primary" onClick={onNew}>＋ New analysis</button></div>{filtered.length ? <div className="history-grid">{filtered.map((item, index) => <button className="history-card" onClick={() => onOpen(item)} key={item.id}><span className={`history-thumb ${colors[index % colors.length]}`}>FP</span><span><small>{new Date(item.created_at).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}</small><strong>{item.product_name}</strong><em>{item.note}</em></span><b>→</b></button>)}</div> : <article className="history-empty"><span>◎</span><h2>{items.length ? 'No matching product' : 'No real-label checks saved yet'}</h2><p>{items.length ? 'Try a different product name.' : 'Complete a photo-based analysis and it will appear here for the rest of this browser session.'}</p>{!items.length && <button className="primary" onClick={onNew}>Analyze a product</button>}</article>}<p className="storage-note">Session-only history stores confirmed label facts and results in this browser tab. Original photographs and personal profile inputs are not saved. Closing the tab clears the history.</p></section>;
}

function EvalsView() {
  const report = evaluationReport;
  const suiteCounts = [
    ['Unsafe requests', report.suites.unsafe_requests.length, 'Direct and adversarial medical or allergy-safety requests'],
    ['Answerable requests', report.suites.answerable_requests.length, 'Normal questions that should remain usable'],
    ['Calculations', report.suites.calculations.length, 'Known portion values checked exactly'],
    ['FDA retrieval', report.suites.retrieval.length, 'Expected source required in the top position'],
    ['Personalization', report.suites.personalization.length, 'Allergen and dietary outcomes'],
    ['Fair comparison', report.suites.comparison.length, 'Normalization and missing-weight refusal rules'],
    ['Barcode cross-check', report.suites.barcode.length, 'Tolerance and meaningful-difference flagging'],
    ['Alternative finder', report.suites.alternatives.length, 'Category relevance, evidence gaps, profile conflicts and safe refusal'],
  ] as const;
  return <section className="screen eval-screen">
    <div className="eval-hero">
      <div><span className="eyebrow">Quality evidence</span><h1>Show the tests,<br /><em>not just the demo.</em></h1><p>Each score below comes from a versioned golden case with a known expected result. Different risks remain separate instead of being hidden inside one vague “accuracy” number.</p></div>
      <div className="eval-verdict"><span>Automated release gate</span><strong>{report.summary.automated_gates_pass ? 'PASS' : 'REVIEW'}</strong><b>{report.summary.headline}</b><small>Generated {new Date(report.generated_at).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })}</small></div>
    </div>

    <div className="metric-grid">{report.metrics.map((metric) => <article className="metric-card" key={metric.key}><div><span>{metric.label}</span><b>{metric.gate_passed ? 'Passed' : 'Review'}</b></div><strong>{metric.percent}%</strong><p>{metric.passed} of {metric.total} cases · target {metric.target}</p><div className="metric-bar" aria-label={`${metric.percent}%`}><i style={{ width: `${Math.min(metric.percent, 100)}%` }} /></div></article>)}</div>

    <article className="vision-limit"><div className="limit-mark">!</div><div><span className="mini-label">Real-photo evidence</span><h2>Vision accuracy is not yet a publishable percentage</h2><p>{report.summary.image_note}</p><div className="vision-case-list">{report.vision_evidence.cases.map((item) => <span className={item.outcome} key={item.product}><b>{item.outcome === 'completed' ? '✓' : '↻'}</b><span><strong>{item.product}</strong><small>{item.note}</small></span></span>)}</div></div><span className="limited-chip">4 complete · 1 retake</span></article>

    <div className="eval-details">
      <article className="suite-card"><span className="mini-label">Golden-set design</span><h2>{report.summary.total} cases across eight failure surfaces</h2><div className="suite-list">{suiteCounts.map(([name, count, description]) => <div key={name}><b>{count}</b><span><strong>{name}</strong><small>{description}</small></span><em>All passed</em></div>)}</div></article>
      <article className="failure-card"><span className="mini-label">What we actively test</span><h2>Failure taxonomy</h2><ul>{report.failure_taxonomy.map((failure) => <li key={failure}><span>✓</span>{failure}</li>)}</ul><p>A passing automated gate means these defined cases behaved correctly. It does not prove every package, ingredient, or user question will behave correctly.</p></article>
    </div>
    <article className="architecture-card">
      <div className="architecture-heading"><div><span className="mini-label">Agentic architecture</span><h2>From package photos to a bounded Evidence Card</h2></div><p>AI reads the label; deterministic tools calculate and match; a human confirms before the system makes any comparison.</p></div>
      <div className="architecture-flow" role="img" aria-label="FoodProof Fit architecture from inputs through extraction, confirmation, agent workflow and evidence card">
        <div className="architecture-node input-node"><span>Inputs</span><strong>3 label photos</strong><small>+ portion, goals and allergens</small></div><i>→</i>
        <div className="architecture-node"><span>Vision service</span><strong>Quality + extraction</strong><small>Structured values with uncertainty</small></div><i>→</i>
        <div className="architecture-node human-node"><span>Human gate</span><strong>Confirm or correct</strong><small>No calculation before approval</small></div><i>→</i>
        <div className="architecture-node agent-node"><span>LangGraph workflow</span><strong>Route the evidence</strong><small>Safety · maths · profile · FDA RAG · claims</small></div><i>→</i>
        <div className="architecture-node output-node"><span>Output</span><strong>Evidence Card</strong><small>Citations, limits, alerts or refusal</small></div>
      </div>
      <div className="architecture-extensions"><span><b>Barcode check</b>Supporting historical record; never overrides the package</span><span><b>Fair comparison</b>Serving, chosen portion, or normalized per 100 g</span><span><b>Live alternatives</b>Same-category candidates for one selected nutrient priority</span><span><b>Session history</b>Confirmed structured results only; no photos or profile</span></div>
      <div className="architecture-guardrails"><span><b>1</b> Refuse medical and allergy guarantees</span><span><b>2</b> Ask for better photos when evidence is weak</span><span><b>3</b> Keep missing values unknown</span><span><b>4</b> 52 golden cases across eight risk surfaces</span></div>
    </article>
  </section>;
}

function PrivacyView() {
  return <section className="screen feature-screen narrow"><div className="feature-heading left"><span className="eyebrow">Account and privacy</span><h1>You control your food data.</h1><p>The current prototype keeps history only for this browser session and never stores the original package photographs.</p></div><div className="settings-list"><article><div><strong>Original photographs</strong><p>Used for extraction and not added to session history.</p></div><span className="toggle on" aria-label="Photo retention disabled">●</span></article><article><div><strong>Session history</strong><p>Keep confirmed label facts, calculations and citations until this tab closes.</p></div><span className="toggle on" aria-label="Session history enabled">●</span></article><article><div><strong>Personal profile</strong><p>Allergen and daily-target inputs are excluded from reopened history records.</p></div><span className="toggle on" aria-label="Personal profile retention disabled">●</span></article></div><div className="danger-zone"><div><strong>Production privacy controls</strong><p>Account deletion and retention controls require authenticated storage and are not represented as active in this prototype.</p></div><button disabled>Not connected</button></div><p className="privacy-footnote">FoodProof explains package labels. It does not provide diagnosis, treatment advice, or an allergy-safety guarantee.</p></section>;
}

function ProfileNumber({ label, unit, value, onChange }: { label: string; unit: string; value: string; onChange: (value: string) => void }) {
  return <label><span>{label}</span><span className="number-with-unit"><input type="number" min="0" step="any" value={value} onChange={(event) => onChange(event.target.value)} placeholder="Optional" /><b>{unit}</b></span></label>;
}

function PhotoInput({ slot, title, hint, photo, onChange, featured = false }: { slot: PhotoSlot; title: string; hint: string; photo?: string; featured?: boolean; onChange: (slot: PhotoSlot, event: ChangeEvent<HTMLInputElement>) => void }) {
  return <label className={`photo-slot ${featured ? 'featured' : ''} ${photo ? 'filled' : ''}`}><input type="file" accept="image/*" capture="environment" onChange={(event) => onChange(slot, event)} />{photo ? <Image src={photo} alt={`${title} preview`} width={480} height={420} unoptimized /> : <><span className="camera">◎</span><strong>{title}</strong><small>{hint}</small><span className="add-photo">＋ Add photo</span></>}</label>;
}
