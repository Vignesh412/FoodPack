'use client';

import { ChangeEvent, useMemo, useState } from 'react';

type Step = 'scan' | 'confirm' | 'result';
type PhotoSlot = 'front' | 'nutrition' | 'ingredients';

const demoNutrients = [
  { name: 'Sodium', value: '410 mg', daily: '18%', tone: 'high' },
  { name: 'Added sugar', value: '2 g', daily: '4%', tone: 'low' },
  { name: 'Saturated fat', value: '1.5 g', daily: '8%', tone: 'medium' },
  { name: 'Fibre', value: '6 g', daily: '21%', tone: 'good' },
];

export default function Home() {
  const [step, setStep] = useState<Step>('scan');
  const [photos, setPhotos] = useState<Partial<Record<PhotoSlot, string>>>({});
  const [portion, setPortion] = useState(1);
  const completed = Object.keys(photos).length;
  const portionLabel = useMemo(() => `${portion} ${portion === 1 ? 'serving' : 'servings'}`, [portion]);

  function addPhoto(slot: PhotoSlot, event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setPhotos((current) => ({ ...current, [slot]: URL.createObjectURL(file) }));
  }

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
          <div className="photo-grid">
            <PhotoInput slot="front" title="Front of pack" hint="Claims & product name" photo={photos.front} onChange={addPhoto} />
            <PhotoInput slot="nutrition" title="Nutrition facts" hint="Keep the full panel visible" photo={photos.nutrition} onChange={addPhoto} featured />
            <PhotoInput slot="ingredients" title="Ingredients" hint="Include allergen statement" photo={photos.ingredients} onChange={addPhoto} />
          </div>
          <div className="capture-footer"><p><span>◆</span> Photos are processed securely and aren’t used to train models.</p><button className="primary" onClick={() => setStep('confirm')} disabled={completed > 0 && completed < 3}>{completed === 0 ? 'Try with a demo label' : 'Check my label'} <span>→</span></button></div>
        </div>
      </section>}

      {step === 'confirm' && <section className="screen confirm-screen">
        <button className="back" onClick={() => setStep('scan')}>← Back to photos</button>
        <div className="section-heading"><span className="eyebrow">Quick accuracy check</span><h1>Does this match the label?</h1><p>AI can misread small print. Confirm these values before we calculate anything.</p></div>
        <div className="confirm-layout">
          <article className="product-summary"><div className="pack-visual"><span>Harvest</span><strong>CRUNCH</strong><small>seeded oat clusters</small></div><div><span className="verified">✓ Clear image</span><h2>Harvest Crunch</h2><p>Seeded oat clusters · 8 servings</p></div></article>
          <article className="facts-card">
            <div className="facts-title"><div><span className="mini-label">Extracted values</span><h2>Nutrition facts</h2></div><button className="text-button">Edit all</button></div>
            <div className="facts-grid">{demoNutrients.map((item) => <label key={item.name}><span>{item.name}</span><input defaultValue={item.value} /><small>{item.daily} daily value</small></label>)}</div>
            <div className="portion-row"><div><strong>Your portion</strong><span>Label serving size: 45 g</span></div><div className="counter"><button onClick={() => setPortion(Math.max(.5, portion - .5))}>−</button><strong>{portionLabel}</strong><button onClick={() => setPortion(portion + .5)}>+</button></div></div>
            <button className="primary wide" onClick={() => setStep('result')}>Confirm and show my results <span>→</span></button>
          </article>
        </div>
      </section>}

      {step === 'result' && <section className="screen result-screen">
        <button className="back" onClick={() => setStep('confirm')}>← Review values</button>
        <div className="result-hero"><div><span className="eyebrow">Harvest Crunch · {portionLabel}</span><h1>Your label, made useful.</h1><p>The strongest signal is fibre. Sodium is the main thing to watch for this portion.</p></div><div className="score"><span>Overall balance</span><strong>Good</strong><small>Based on confirmed label values</small></div></div>
        <div className="result-grid">
          <article className="insight-card spotlight"><span className="insight-icon">↗</span><div><span className="mini-label">Worth knowing</span><h2>A strong source of fibre</h2><p>This portion provides <strong>21% of the Daily Value</strong>. FDA guidance considers 20% DV or more high.</p><a href="https://www.fda.gov/food/nutrition-facts-label/how-understand-and-use-nutrition-facts-label" target="_blank" rel="noreferrer">View FDA source ↗</a></div></article>
          <article className="nutrient-card"><div className="nutrient-head"><div><span className="mini-label">Per your portion</span><h2>Nutrient snapshot</h2></div><span className="portion-chip">{portionLabel}</span></div>{demoNutrients.map((item) => <div className="nutrient-row" key={item.name}><span>{item.name}</span><strong>{item.value}</strong><div className="bar"><i className={item.tone} style={{ width: item.daily }} /></div><small>{item.daily} DV</small></div>)}</article>
          <article className="claim-card"><span className="mini-label">Front-of-pack check</span><h2>“High in fibre” checks out</h2><p>The confirmed value meets the FDA threshold used for a “high” nutrient claim.</p><span className="evidence-badge">✓ Supported by the label</span></article>
          <article className="safety-card"><span className="mini-label">FoodProof boundary</span><h2>Facts, not medical advice</h2><p>We explain this label and flag uncertainty. For allergies, conditions, or treatment decisions, check with a qualified professional.</p></article>
        </div>
        <div className="result-actions"><button className="secondary" onClick={() => { setPhotos({}); setStep('scan'); }}>Scan another product</button><button className="primary">Save to my history</button></div>
      </section>}
    </main>
  );
}

function PhotoInput({ slot, title, hint, photo, onChange, featured = false }: { slot: PhotoSlot; title: string; hint: string; photo?: string; featured?: boolean; onChange: (slot: PhotoSlot, event: ChangeEvent<HTMLInputElement>) => void }) {
  return <label className={`photo-slot ${featured ? 'featured' : ''} ${photo ? 'filled' : ''}`}><input type="file" accept="image/*" capture="environment" onChange={(event) => onChange(slot, event)} />{photo ? <img src={photo} alt={`${title} preview`} /> : <><span className="camera">◎</span><strong>{title}</strong><small>{hint}</small><span className="add-photo">＋ Add photo</span></>}</label>;
}
