# FoodProof

FoodProof turns photographs of a US packaged-food label into a clear, evidence-backed nutrition explanation. It reads the front, Nutrition Facts, and ingredients panels; asks the user to confirm extracted values; recalculates them for the portion eaten; checks marketing claims; and refuses medical or allergy guarantees it cannot safely make.

## Current status

- **Consumer web app:** responsive Scan → Confirm → Understand experience in `web/`, including nutrition goals, editable confirmation, portion recalculation, allergen/missing-evidence summaries, and an expandable workflow trace.
- **Analysis API:** FastAPI boundary in `api.py` with upload validation, image-quality checks, vision extraction, and confirmed-label analysis.
- **Nutrition engine:** tested modules in `src/` for calculations, FDA retrieval, claim evidence, comparisons, barcode checks, and safety routing.
- **Legacy prototype:** the original Streamlit interface remains in `app.py`.
- **Hosted preview:** [foodproof.iyer-vignesh2.chatgpt.site](https://foodproof.iyer-vignesh2.chatgpt.site) (private access).

The hosted interface uses the demonstration label until a deployed API URL and `ANTHROPIC_API_KEY` are configured. It is a production-design preview until that connection is live.

## Architecture

```text
Consumer web app (web/)
       │ three validated image uploads
       ▼
FastAPI service (api.py)
       ├─ file type and 10 MB limit
       ├─ blur, glare, darkness, and resolution checks
       └─ vision extraction into validated Pydantic schemas
       ▼
Human confirmation
       ▼
LangGraph workflow
       ├─ safety gate and portion calculations
       ├─ FDA evidence retrieval
       ├─ marketing-claim checks
       └─ evidence card
```

## Run locally

Python 3.10+ and Node.js 22.13+ are recommended.

### API

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
cp .env.example .env
```

Add `ANTHROPIC_API_KEY` to `.env`, then start the service:

```bash
uvicorn api:app --reload --port 8000
```

### Consumer web app

In a second terminal:

```bash
cd web
npm install
cp .env.example .env.local
npm run dev
```

Open `http://localhost:3000`. Three photos call the extraction API; uploading no photos and selecting **Try with a demo label** runs the UI without an API call.

### Validation

```bash
source .venv/bin/activate
pytest tests/ -q
cd web && npm run build
```

### Legacy Streamlit prototype

```bash
source .venv/bin/activate
streamlit run app.py
```

## Environment variables

| Variable | Used by | Purpose |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | Python API | Server-side vision extraction credential |
| `FOODPROOF_VISION_MODEL` | Python API | Vision model override |
| `FOODPROOF_ALLOWED_ORIGINS` | Python API | Comma-separated permitted web origins |
| `OFF_API_BASE` | Python API | Open Food Facts endpoint |
| `FOODPROOF_API_URL` | Web server | URL of the deployed Python API |

Never expose `ANTHROPIC_API_KEY` to browser code or commit a populated `.env` file.

## Safety and privacy boundaries

- US packaged-food Nutrition Facts labels only.
- Images must be JPEG, PNG, or WebP and no larger than 10 MB each.
- Users must confirm extracted values before downstream calculations.
- FoodProof provides label information, not diagnosis, treatment advice, or allergy-safety guarantees.
- Production still requires an explicit retention policy, automatic image deletion, rate limiting, monitoring, legal review, and real-device evaluation.

## Project structure

```text
web/                         Consumer web app and Sites deployment
api.py                       FastAPI upload and analysis boundary
app.py                       Legacy Streamlit prototype
src/                         Extraction, calculations, evidence, and safety logic
knowledge/fda_sources/       Curated FDA evidence corpus
tests/                       Unit, workflow, safety, and API tests
```

## Remaining production work

1. Deploy the Python API and configure `FOODPROOF_API_URL` for the hosted web app.
2. Add the two-product comparison and optional barcode workflow to the consumer interface.
3. Store user-owned scan history in D1 and short-lived images in R2.
4. Add authentication-aware history, deletion, and privacy controls.
5. Add rate limits, request authentication, structured logs, monitoring, and cost alerts.
6. Evaluate clear, blurred, cropped, reflective, and unusual labels on real devices.
7. Add repository screenshots, the final architecture diagram, and the 90–120 second demonstration.
8. Complete accessibility, privacy, legal, nutrition-safety, and regulatory review.
