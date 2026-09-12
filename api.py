"""Production HTTP boundary for the FoodProof analysis engine."""

from __future__ import annotations

import os
import json
import logging
import secrets
import time
import uuid
from typing import Annotated, Optional

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

from src.image_quality import deterministic_precheck
from src.label_extractor import ExtractionError, extract_label
from src.alternatives import (
    AlternativeCategory,
    AlternativeGoal,
    AlternativeSearchResult,
    find_live_alternatives,
)
from src.comparison import ComparisonResult, compare_products
from src.schemas import ExtractedLabel, NutritionGoal, PanelType, PersonalizationProfile, PortionSelection
from src.workflow import run_workflow

MAX_IMAGE_BYTES = 10 * 1024 * 1024
ALLOWED_MEDIA_TYPES = {"image/jpeg", "image/png", "image/webp"}
API_TOKEN = os.getenv("FOODPROOF_API_TOKEN", "").strip()
logger = logging.getLogger("foodproof.api")

app = FastAPI(title="FoodProof Fit API", version="1.2.0", docs_url=None, redoc_url=None)
origins = [value.strip() for value in os.getenv("FOODPROOF_ALLOWED_ORIGINS", "http://localhost:3000").split(",") if value.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.middleware("http")
async def protect_and_observe_api(request: Request, call_next):
    """Protect paid endpoints in cloud while keeping local setup frictionless.

    When FOODPROOF_API_TOKEN is unset, local development behaves exactly as
    before. In a hosted environment the frontend proxy sends this shared token
    server-to-server; it is never exposed to browser JavaScript.
    """

    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    started = time.perf_counter()
    if request.method != "OPTIONS" and request.url.path.startswith("/v1/") and API_TOKEN:
        supplied = request.headers.get("authorization", "")
        expected = f"Bearer {API_TOKEN}"
        if not secrets.compare_digest(supplied, expected):
            response = JSONResponse(
                status_code=401,
                content={"detail": "The analysis service could not authenticate this request."},
            )
        else:
            response = await call_next(request)
    else:
        response = await call_next(request)

    response.headers["X-Request-ID"] = request_id
    logger.info(
        json.dumps(
            {
                "event": "http_request",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            }
        )
    )
    return response


class AnalysisRequest(BaseModel):
    label: ExtractedLabel
    servings_consumed: float = 1.0
    goal: NutritionGoal = NutritionGoal.GENERAL_UNDERSTANDING
    question: Optional[str] = None
    profile: Optional[PersonalizationProfile] = None
    barcode: Optional[str] = Field(default=None, pattern=r"^\d{8,14}$")


class ComparisonProductRequest(BaseModel):
    label: ExtractedLabel
    name: str
    servings_consumed: float = 1.0


class ComparisonRequest(BaseModel):
    product_a: ComparisonProductRequest
    product_b: ComparisonProductRequest


class AlternativeRequest(BaseModel):
    label: ExtractedLabel
    category: AlternativeCategory
    goal: AlternativeGoal
    profile: Optional[PersonalizationProfile] = None
    current_barcode: Optional[str] = Field(default=None, pattern=r"^\d{8,14}$")
    limit: int = Field(default=3, ge=1, le=5)


async def _read_image(upload: UploadFile, panel: PanelType) -> tuple[bytes, str]:
    media_type = upload.content_type or ""
    if media_type not in ALLOWED_MEDIA_TYPES:
        raise HTTPException(415, f"{panel.value}: upload a JPEG, PNG, or WebP image.")
    payload = await upload.read(MAX_IMAGE_BYTES + 1)
    if len(payload) > MAX_IMAGE_BYTES:
        raise HTTPException(413, f"{panel.value}: image exceeds the 10 MB limit.")
    check = deterministic_precheck(payload, expected_panel=panel)
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
    if not request.label.user_confirmed:
        raise HTTPException(
            status_code=422,
            detail="Confirm the extracted label values before requesting analysis.",
        )
    state = run_workflow(
        label=request.label,
        portion=PortionSelection(servings_consumed=request.servings_consumed),
        goal=request.goal.value,
        question=request.question,
        barcode=request.barcode,
        profile=request.profile,
    )
    return {
        "evidence_card": state.get("evidence_card"),
        "trace": state.get("trace", []),
    }


@app.post("/v1/compare", response_model=ComparisonResult)
def compare(request: ComparisonRequest) -> ComparisonResult:
    for product in (request.product_a, request.product_b):
        if not product.label.user_confirmed:
            raise HTTPException(
                status_code=422,
                detail=f"Confirm the label values for {product.name} before comparing products.",
            )

    return compare_products(
        request.product_a.label,
        PortionSelection(servings_consumed=request.product_a.servings_consumed),
        request.product_a.name,
        request.product_b.label,
        PortionSelection(servings_consumed=request.product_b.servings_consumed),
        request.product_b.name,
    )


@app.post("/v1/alternatives", response_model=AlternativeSearchResult)
def alternatives(request: AlternativeRequest) -> AlternativeSearchResult:
    if not request.label.user_confirmed:
        raise HTTPException(
            status_code=422,
            detail="Confirm the current product label before searching for alternatives.",
        )
    return find_live_alternatives(
        current_label=request.label,
        category=request.category,
        goal=request.goal,
        profile=request.profile,
        current_barcode=request.current_barcode,
        limit=request.limit,
    )
