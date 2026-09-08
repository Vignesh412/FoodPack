"""Production HTTP boundary for the FoodProof analysis engine."""

from __future__ import annotations

import os
from typing import Annotated, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.image_quality import deterministic_precheck
from src.label_extractor import ExtractionError, extract_label
from src.schemas import ExtractedLabel, NutritionGoal, PanelType, PortionSelection
from src.workflow import run_workflow

MAX_IMAGE_BYTES = 10 * 1024 * 1024
ALLOWED_MEDIA_TYPES = {"image/jpeg", "image/png", "image/webp"}

app = FastAPI(title="FoodProof API", version="1.0.0", docs_url=None, redoc_url=None)
origins = [value.strip() for value in os.getenv("FOODPROOF_ALLOWED_ORIGINS", "http://localhost:3000").split(",") if value.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)


class AnalysisRequest(BaseModel):
    label: ExtractedLabel
    servings_consumed: float = 1.0
    goal: NutritionGoal = NutritionGoal.GENERAL_UNDERSTANDING
    question: Optional[str] = None


async def _read_image(upload: UploadFile, panel: PanelType) -> tuple[bytes, str]:
    media_type = upload.content_type or ""
    if media_type not in ALLOWED_MEDIA_TYPES:
        raise HTTPException(415, f"{panel.value}: upload a JPEG, PNG, or WebP image.")
    payload = await upload.read(MAX_IMAGE_BYTES + 1)
    if len(payload) > MAX_IMAGE_BYTES:
        raise HTTPException(413, f"{panel.value}: image exceeds the 10 MB limit.")
    check = deterministic_precheck(payload)
    if not check.passed:
        raise HTTPException(422, {"panel": panel.value, "issues": check.issues})
    return payload, media_type


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/extract", response_model=ExtractedLabel)
async def extract(
    front: Annotated[UploadFile, File()],
    nutrition: Annotated[UploadFile, File()],
    ingredients: Annotated[UploadFile, File()],
) -> ExtractedLabel:
    images = [
        await _read_image(front, PanelType.FRONT_OF_PACK),
        await _read_image(nutrition, PanelType.NUTRITION_FACTS),
        await _read_image(ingredients, PanelType.INGREDIENTS_ALLERGENS),
    ]
    try:
        return extract_label(images)
    except ExtractionError as exc:
        raise HTTPException(502, "The label could not be extracted reliably. Please retake the photos.") from exc


@app.post("/v1/analyze")
def analyze(request: AnalysisRequest) -> dict:
    confirmed = request.label.model_copy(update={"user_confirmed": True})
    state = run_workflow(
        label=confirmed,
        portion=PortionSelection(servings_consumed=request.servings_consumed),
        goal=request.goal.value,
        question=request.question,
    )
    return {
        "evidence_card": state.get("evidence_card"),
        "trace": state.get("trace", []),
    }
