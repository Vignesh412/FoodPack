"""
Step 4: image quality gate.

Deterministic-first by design: cheap, offline checks (resolution, glare,
blur) run before any API call and can reject an obviously unusable photo
for free. Only an image that clears those checks is sent to the vision
model, and only for the genuinely judgment-based question — "which panel
is this, and is the text actually readable?" — that a pixel-level check
can't answer on its own.
"""

from __future__ import annotations

import base64
import io
import json
import os
from typing import Optional

import numpy as np
from PIL import Image

from src.schemas import PanelType, RetakeInstruction

MIN_SHORT_EDGE_PX = 600
MAX_GLARE_FRACTION = 0.15       # share of pixels that are near-blown-out white
MAX_DARK_FRACTION = 0.35        # share of pixels that are near-black (underexposed)
MIN_LAPLACIAN_VARIANCE = 40.0   # below this, the image reads as out of focus


def _load_grayscale_array(image_bytes: bytes) -> np.ndarray:
    img = Image.open(io.BytesIO(image_bytes)).convert("L")
    return np.asarray(img, dtype=np.float64)


def _laplacian_variance(gray: np.ndarray) -> float:
    """Vectorized discrete Laplacian, no OpenCV/SciPy dependency."""
    center = gray[1:-1, 1:-1]
    up = gray[:-2, 1:-1]
    down = gray[2:, 1:-1]
    left = gray[1:-1, :-2]
    right = gray[1:-1, 2:]
    laplacian = up + down + left + right - 4 * center
    return float(laplacian.var())


class DeterministicCheckResult:
    def __init__(self, passed: bool, issues: list[str]):
        self.passed = passed
        self.issues = issues


def deterministic_precheck(image_bytes: bytes) -> DeterministicCheckResult:
    issues: list[str] = []

    try:
        img = Image.open(io.BytesIO(image_bytes))
        width, height = img.size
    except Exception:
        return DeterministicCheckResult(passed=False, issues=["File could not be read as an image."])

    if min(width, height) < MIN_SHORT_EDGE_PX:
        issues.append(
            f"Image resolution is too low ({width}x{height}). Move closer or use a higher-resolution camera."
        )

    gray = _load_grayscale_array(image_bytes)
    total_pixels = gray.size

    glare_fraction = float((gray > 245).sum()) / total_pixels
    if glare_fraction > MAX_GLARE_FRACTION:
        issues.append("Glare is covering part of the label. Retake at an angle away from direct light.")

    dark_fraction = float((gray < 20).sum()) / total_pixels
    if dark_fraction > MAX_DARK_FRACTION:
        issues.append("The photo is too dark to read reliably. Retake with better lighting.")

    blur_variance = _laplacian_variance(gray)
    if blur_variance < MIN_LAPLACIAN_VARIANCE:
        issues.append("The photo looks out of focus. Hold the camera steady and retake.")

    return DeterministicCheckResult(passed=len(issues) == 0, issues=issues)


_PANEL_CLASSIFICATION_PROMPT = """You are a quality checker for photographs of US packaged food labels.
Look at this single image and respond with ONLY a JSON object, no other text:
{
  "panel": one of "front_of_pack", "nutrition_facts", "ingredients_allergens", "unknown",
  "readable": true or false,
  "reason": short string explaining any readability problem, or null if readable
}
Mark readable=false if the panel is cropped so that required text is cut off,
if text is too blurry or small to read confidently, or if it doesn't match
any of the three expected panel types."""


def classify_panel_with_vision(image_bytes: bytes, media_type: str = "image/jpeg") -> dict:
    """
    Calls Claude's vision API to classify the panel and judge readability.
    Requires ANTHROPIC_API_KEY. Raises RuntimeError with a clear message if
    the key is missing, so callers (and tests) can handle that explicitly
    rather than getting an opaque SDK exception.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add a real key "
            "before running vision-dependent steps."
        )

    import anthropic  # lazy import so unit tests never need this installed at import time

    client = anthropic.Anthropic(api_key=api_key)
    model = os.environ.get("FOODPROOF_VISION_MODEL", "claude-opus-4-1-20250805")
    b64_image = base64.b64encode(image_bytes).decode("utf-8")

    response = client.messages.create(
        model=model,
        max_tokens=300,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64_image}},
                    {"type": "text", "text": _PANEL_CLASSIFICATION_PROMPT},
                ],
            }
        ],
    )
    text = response.content[0].text.strip()
    # Strip accidental markdown code fences before parsing.
    if text.startswith("```"):
        text = text.strip("`")
        text = text.split("\n", 1)[-1] if "\n" in text else text
    return json.loads(text)


def run_quality_gate(
    image_bytes: bytes,
    expected_panel: Optional[PanelType] = None,
    media_type: str = "image/jpeg",
    skip_vision_call: bool = False,
) -> RetakeInstruction:
    """
    Full gate: deterministic checks first (free, instant). Only calls the
    vision model if those pass. skip_vision_call=True lets tests and offline
    demos exercise the deterministic layer alone.
    """
    det = deterministic_precheck(image_bytes)
    if not det.passed:
        return RetakeInstruction(
            panel=expected_panel or PanelType.UNKNOWN,
            accepted=False,
            reason="; ".join(det.issues),
            retake_instruction=det.issues[0],
        )

    if skip_vision_call:
        return RetakeInstruction(panel=expected_panel or PanelType.UNKNOWN, accepted=True)

    try:
        result = classify_panel_with_vision(image_bytes, media_type=media_type)
    except RuntimeError as exc:
        return RetakeInstruction(
            panel=expected_panel or PanelType.UNKNOWN,
            accepted=False,
            reason=str(exc),
            retake_instruction="Vision check unavailable — confirm ANTHROPIC_API_KEY is configured.",
        )

    panel = PanelType(result.get("panel", "unknown"))
    readable = bool(result.get("readable", False))
    reason = result.get("reason")

    accepted = readable and (expected_panel is None or panel == expected_panel)
    retake = None
    if not accepted:
        if expected_panel is not None and panel != PanelType.UNKNOWN and panel != expected_panel:
            retake = f"This looks like the {panel.value.replace('_', ' ')} panel, not the {expected_panel.value.replace('_', ' ')} panel. Please upload the correct photo."
        else:
            retake = reason or "Please retake this photo so the required text is fully visible."

    return RetakeInstruction(panel=panel, accepted=accepted, reason=reason, retake_instruction=retake)
