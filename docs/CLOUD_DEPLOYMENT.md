# FoodProof Fit — Cloud deployment runbook

## Deployment architecture

```text
Browser
  → FoodProof Fit Sites frontend
  → server-side proxy with FOODPROOF_API_TOKEN
  → Render FastAPI service
      ├─ Anthropic vision extraction
      ├─ Open Food Facts barcode and alternative search
      └─ curated local FDA evidence corpus
```

The Anthropic key and service token must remain server-side. Never place either value in a `NEXT_PUBLIC_*` variable, committed file, screenshot, video, or chat message.

## 1. Prepare the repository

1. Run the complete Python tests and frontend build.
2. Confirm that `.env` and `web/.env.local` are ignored.
3. Commit the validated source to the intended deployment branch.
4. Confirm that `render.yaml`, `.python-version`, and `web/.openai/hosting.json` are present.

## 2. Deploy the Python API on Render

1. In Render, create a Blueprint from the repository's `render.yaml`.
2. Provide `ANTHROPIC_API_KEY` when prompted.
3. Generate a long random `FOODPROOF_API_TOKEN` and provide it when prompted.
4. Set `FOODPROOF_ALLOWED_ORIGINS` to the final Sites origin. For the first backend-only check, the value may temporarily remain `http://localhost:3000` because the hosted frontend proxies server-side requests.
5. Deploy the service and copy its HTTPS URL.
6. Open `<render-url>/health`; the expected response is `{"status":"ok"}`.

The Blueprint deliberately disables automatic deploys so the demonstration version cannot change unexpectedly. Trigger deployments manually after validation.

## 3. Connect the Sites frontend

Configure these hosted server values for the existing Sites project:

| Variable | Value |
| --- | --- |
| `FOODPROOF_API_URL` | The Render HTTPS service URL, without a trailing slash |
| `FOODPROOF_API_TOKEN` | Exactly the same random token used by Render |

Save and deploy a new private Sites version. Do not add `ANTHROPIC_API_KEY` to the frontend.

## 4. Cloud acceptance test

Run these checks in order:

1. Open the hosted Analyze screen and complete Demo 1.
2. Search for lower-sodium snack-bar alternatives and confirm that live candidates show per-100-g evidence and Open Food Facts links.
3. Select lower added sugar and confirm the evidence-gap refusal.
4. Upload one non-sensitive three-photo product set, confirm the extracted facts, and generate its Evidence Card.
5. Run the declared-allergen demo and confirm it never states that a food is safe.
6. Open Evals and confirm the 52/52 automated release gate.
7. Test one desktop browser and one mobile device.

## 5. Demonstration fallback

If Anthropic or Open Food Facts is temporarily unavailable, use the three clearly labelled synthetic scenarios. Do not describe a demo result as live extraction. A catalogue failure must leave the confirmed label analysis intact and display the safe no-result message.

## Production limitations

The submission prototype has service authentication, upload limits, validation, request IDs, structured logs, safe refusal paths, and no application-level photo persistence. A public commercial release would still require platform rate limiting, centralized monitoring, cost alerts, authenticated user accounts, a formal retention policy, legal and nutrition review, and a much larger real-label evaluation set.
