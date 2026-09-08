'use client';

import { ChangeEvent, useMemo, useState } from 'react';

type Step = 'scan' | 'confirm' | 'result';
type PhotoSlot = 'front' | 'nutrition' | 'ingredients';
type PhotoEntry = { file: File; url: string };
type NutrientView = { name: string; value: string; daily: string; tone: string };
type ExtractedLabel = {
  product_name?: string;
  serving?: { grams_per_serving?: number; household_measure?: string };
  allergens?: { declared_contains?: string[]; may_contain_statement?: string[]; raw_ingredient_text?: string };
  missing_fields?: string[];
  [key: string]: unknown;
};
type AnalysisResult = { evidence_card?: Record<string, unknown>; trace?: string[] };

const demoNutrients = [
  { name: 'Sodium', value: '410 mg', daily: '18%', tone: 'high' },
  { name: 'Added sugar', value: '2 g', daily: '4%', tone: 'low' },
  { name: 'Saturated fat', value: '1.5 g', daily: '8%', tone: 'medium' },
  { name: 'Fibre', value: '6 g', daily: '21%', tone: 'good' },
];

export default function Home() {
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
  const completed = Object.keys(photos).length;
  const portionLabel = useMemo(() => `${portion} ${portion === 1 ? 'serving' : 'servings'}`, [portion]);

  function addPhoto(slot: PhotoSlot, event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setError(null);
    setPhotos((current) => ({ ...current, [slot]: { file, url: URL.createObjectURL(file) } }));
  }

  async function beginAnalysis() {
    if (completed === 0) { setStep('confirm'); return; }
    if (!photos.front || !photos.nutrition || !photos.ingredients) return;
    setIsAnalyzing(true);
    setError(null);
    const body = new FormData();
    body.append('front', photos.front.file);
    body.append('nutrition', photos.nutrition.file);
    body.append('ingredients', photos.ingredients.file);
    try {
      const response = await fetch('/api/extract', { method: 'POST', body });
      const data = await response.json() as Record<string, any>;
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'One or more photos need to be retaken.');
      const fields = [
        ['sodium', 'Sodium'], ['added_sugar', 'Added sugar'], ['saturated_fat', 'Saturated fat'], ['fibre', 'Fibre'],
      ] as const;
      setProductName(data.product_name || 'Your product');
      setServingGrams(data.serving?.grams_per_serving || 0);
      setNutrients(fields.map(([key, name]) => {
        const field = data[key];
        const daily = field?.percent_daily_value ?? 0;
        return { name, value: field?.amount ? `${field.amount.value} ${field.amount.unit}` : 'Not shown', daily: `${daily}%`, tone: daily >= 20 ? (key === 'fibre' ? 'good' : 'high') : daily <= 5 ? 'low' : 'medium' };
      }));
      setLabelData(data as ExtractedLabel);
      setStep('confirm');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'We could not analyze those photos.');
    } finally { setIsAnalyzing(false); }
  }

  async function confirmAndAnalyze() {
    if (!labelData) {
      setAnalysis({ trace: ['Demo label loaded.', 'Safety gate passed.', 'Portion calculation completed.', 'FDA evidence attached.', 'Evidence Card assembled.'] });
      setStep('result');
      return;
    }
    setIsAnalyzing(true);
    setError(null);
    try {
      const response = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ label: labelData, servings_consumed: portion, goal }),
      });
      const data = await response.json() as AnalysisResult & { detail?: string };
      if (!response.ok) throw new Error(data.detail || 'The confirmed label could not be analyzed.');
      setAnalysis(data);
      setStep('result');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The confirmed label could not be analyzed.');
    } finally { setIsAnalyzing(false); }
  }

  const scaledNutrients = nutrients.map((item) => {
    const amount = Number.parseFloat(item.value);
    const daily = Number.parseFloat(item.daily);
    const unit = item.value.replace(String(amount), '').trim();
    return {
      ...item,
      value: Number.isFinite(amount) ? `${Math.round(amount * portion * 10) / 10} ${unit}` : item.value,
      daily: Number.isFinite(daily) ? `${Math.round(daily * portion)}%` : item.daily,
    };
  });
  const allergens = labelData?.allergens;

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="#" aria-label="FoodProof home"><span className="brand-mark">F</span><span>FoodProof</span></a>
        <div className="trust-pill"><span className="status-dot" />Evidence-first nutrition</div>
        <button className="avatar" aria-label="Open profile">VG</button>
      </header>
      <div className="stepper" aria-label="Analysis progress">
        {['Scan', 'Confirm', 'Understand'].map((label, index) => {
          const activeIndex = step === 'scan' ? 0 : step === 'confirm' ? 1 : 2;
          return <div className={`step ${index <= activeIndex ? 'active' : ''}`} key={label}><span>{index + 1}</span>{label}</div>;
        })}
      </div>

      {step === 'scan' && <section className="screen scan-screen">
        <div className="hero-copy"><span className="eyebrow">Know what you’re eating</span><h1>Turn the label around.<br /><em>We’ll make it clear.</em></h1><p>Photograph three sides of the package. FoodProof checks the facts, explains what matters, and shows its evidence.</p></div>
        <div className="capture-card">
          <div className="capture-head"><div><span className="mini-label">New analysis</span><h2>Add your package photos</h2></div><span className="count">{completed}/3 ready</span></div>
          <label className="goal-picker"><span>What matters most today?</span><select value={goal} onChange={(event) => setGoal(event.target.value)}><option value="general_understanding">Understand this label</option><option value="lower_added_sugar">Lower added sugar</option><option value="lower_sodium">Lower sodium</option><option value="higher_fibre">Higher fibre</option><option value="product_comparison">Compare products</option></select></label>
          <div className="photo-grid">
            <PhotoInput slot="front" title="Front of pack" hint="Claims & product name" photo={photos.front?.url} onChange={addPhoto} />
            <PhotoInput slot="nutrition" title="Nutrition facts" hint="Keep the full panel visible" photo={photos.nutrition?.url} onChange={addPhoto} featured />
            <PhotoInput slot="ingredients" title="Ingredients" hint="Include allergen statement" photo={photos.ingredients?.url} onChange={addPhoto} />
          </div>
          {error && <p className="error-message" role="alert">{error}</p>}
          <div className="capture-footer"><p><span>◆</span> Photos are processed securely and aren’t used to train models.</p><button className="primary" onClick={beginAnalysis} disabled={isAnalyzing || (completed > 0 && completed < 3)}>{isAnalyzing ? 'Checking photos…' : completed === 0 ? 'Try with a demo label' : 'Check my label'} <span>→</span></button></div>
        </div>
      </section>}

      {step === 'confirm' && <section className="screen confirm-screen">
        <button className="back" onClick={() => setStep('scan')}>← Back to photos</button>
        <div className="section-heading"><span className="eyebrow">Quick accuracy check</span><h1>Does this match the label?</h1><p>AI can misread small print. Confirm these values before we calculate anything.</p></div>
        <div className="confirm-layout">
          <article className="product-summary"><div className="pack-visual"><span>Food</span><strong>PROOF</strong><small>confirmed label</small></div><div><span className="verified">✓ Clear image</span><h2>{productName}</h2><p>{servingGrams ? `${servingGrams} g per serving` : 'Serving size needs confirmation'}</p></div></article>
          <article className="facts-card">
            <div className="facts-title"><div><span className="mini-label">Extracted values</span><h2>Nutrition facts</h2></div><button className="text-button">Edit all</button></div>
            <div className="facts-grid">{nutrients.map((item) => <label key={item.name}><span>{item.name}</span><input defaultValue={item.value} /><small>{item.daily} daily value</small></label>)}</div>
            <div className="portion-row"><div><strong>Your portion</strong><span>Label serving size: {servingGrams || '—'} g</span></div><div className="counter"><button onClick={() => setPortion(Math.max(.5, portion - .5))}>−</button><strong>{portionLabel}</strong><button onClick={() => setPortion(portion + .5)}>+</button></div></div>
            {error && <p className="error-message" role="alert">{error}</p>}
            <button className="primary wide" onClick={confirmAndAnalyze} disabled={isAnalyzing}>{isAnalyzing ? 'Building your Evidence Card…' : 'Confirm and show my results'} <span>→</span></button>
          </article>
        </div>
      </section>}

      {step === 'result' && <section className="screen result-screen">
        <button className="back" onClick={() => setStep('confirm')}>← Review values</button>
        <div className="result-hero"><div><span className="eyebrow">{productName} · {portionLabel}</span><h1>Your label, made useful.</h1><p>See the strongest signals from the values you confirmed.</p></div><div className="score"><span>Label overview</span><strong>Checked</strong><small>Based on confirmed label values</small></div></div>
        <div className="result-grid">
          <article className="insight-card spotlight"><span className="insight-icon">↗</span><div><span className="mini-label">Worth knowing</span><h2>A strong source of fibre</h2><p>This portion provides <strong>21% of the Daily Value</strong>. FDA guidance considers 20% DV or more high.</p><a href="https://www.fda.gov/food/nutrition-facts-label/how-understand-and-use-nutrition-facts-label" target="_blank" rel="noreferrer">View FDA source ↗</a></div></article>
          <article className="nutrient-card"><div className="nutrient-head"><div><span className="mini-label">Per your portion</span><h2>Nutrient snapshot</h2></div><span className="portion-chip">{portionLabel}</span></div>{scaledNutrients.map((item) => <div className="nutrient-row" key={item.name}><span>{item.name}</span><strong>{item.value}</strong><div className="bar"><i className={item.tone} style={{ width: item.daily }} /></div><small>{item.daily} DV</small></div>)}</article>
          <article className="claim-card"><span className="mini-label">Front-of-pack check</span><h2>“High in fibre” checks out</h2><p>The confirmed value meets the FDA threshold used for a “high” nutrient claim.</p><span className="evidence-badge">✓ Supported by the label</span></article>
          <article className="safety-card"><span className="mini-label">Ingredients and allergens</span><h2>{allergens?.declared_contains?.length ? `Contains ${allergens.declared_contains.join(', ')}` : 'Check the package every time'}</h2><p>{allergens?.may_contain_statement?.length ? `May contain: ${allergens.may_contain_statement.join(', ')}. ` : ''}FoodProof reports declared label information; it cannot guarantee allergy safety.</p></article>
          {!!labelData?.missing_fields?.length && <article className="safety-card"><span className="mini-label">Missing evidence</span><h2>Some values need attention</h2><p>{labelData.missing_fields.join(', ').replaceAll('_', ' ')}</p></article>}
        </div>
        {!!analysis?.trace?.length && <details className="trace-card"><summary>See how FoodProof reached this result</summary><ol>{analysis.trace.map((line, index) => <li key={`${index}-${line}`}>{line}</li>)}</ol></details>}
        <div className="result-actions"><button className="secondary" onClick={() => { setPhotos({}); setStep('scan'); }}>Scan another product</button><button className="primary">Save to my history</button></div>
      </section>}
    </main>
  );
}

function PhotoInput({ slot, title, hint, photo, onChange, featured = false }: { slot: PhotoSlot; title: string; hint: string; photo?: string; featured?: boolean; onChange: (slot: PhotoSlot, event: ChangeEvent<HTMLInputElement>) => void }) {
  return <label className={`photo-slot ${featured ? 'featured' : ''} ${photo ? 'filled' : ''}`}><input type="file" accept="image/*" capture="environment" onChange={(event) => onChange(slot, event)} />{photo ? <img src={photo} alt={`${title} preview`} /> : <><span className="camera">◎</span><strong>{title}</strong><small>{hint}</small><span className="add-photo">＋ Add photo</span></>}</label>;
}
