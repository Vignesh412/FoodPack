"""Run one photographed product through FoodProof Fit's real HTTP boundary."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from api import app


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("prefix", help="Filename prefix inside sample_images, for example doritos")
    parser.add_argument("--allergen", default="", help="Optional allergen term to match")
    args = parser.parse_args()

    paths = {
        panel: ROOT / "sample_images" / f"{args.prefix}_{panel}.jpg"
        for panel in ("front", "nutrition", "ingredients")
    }
    missing = [str(path) for path in paths.values() if not path.exists()]
    if missing:
        print(json.dumps({"status": "missing_files", "files": missing}, indent=2))
        return 2

    files = {
        panel: (path.name, path.read_bytes(), "image/jpeg")
        for panel, path in paths.items()
    }
    client = TestClient(app)
    extraction = client.post("/v1/extract", files=files)
    if extraction.status_code != 200:
        print(json.dumps({
            "status": "retake_requested",
            "http_status": extraction.status_code,
            "detail": extraction.json().get("detail"),
        }, indent=2))
        return 1

    label = extraction.json()
    label["user_confirmed"] = True
    analysis = client.post("/v1/analyze", json={
        "label": label,
        "servings_consumed": 1,
        "goal": "general_understanding",
        "profile": {
            "declared_allergens": [args.allergen] if args.allergen else [],
            "dietary_preference": "none",
            "daily_calorie_goal": 2000,
            "daily_protein_goal_g": 50,
            "daily_fibre_goal_g": 28,
            "daily_sodium_limit_mg": 2300,
            "daily_added_sugar_limit_g": 50,
        },
    })
    if analysis.status_code != 200:
        print(json.dumps({
            "status": "analysis_failed",
            "http_status": analysis.status_code,
            "detail": analysis.json().get("detail"),
        }, indent=2))
        return 1

    result = analysis.json()
    card = result.get("evidence_card") or {}
    personalization = card.get("personalization") or {}
    print(json.dumps({
        "status": "completed",
        "product_name": label.get("product_name"),
        "serving": label.get("serving"),
        "missing_fields": label.get("missing_fields", []),
        "overall_confidence": label.get("overall_confidence"),
        "declared_allergens": (label.get("allergens") or {}).get("declared_contains", []),
        "advisory_allergens": (label.get("allergens") or {}).get("may_contain_statement", []),
        "refused": card.get("refused"),
        "profile_match": (personalization.get("allergen_match") or {}).get("status"),
        "trace": result.get("trace", []),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
