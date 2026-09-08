from io import BytesIO

from PIL import Image
from fastapi.testclient import TestClient

from api import app


client = TestClient(app)


def _small_png() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (80, 80), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_extract_rejects_low_resolution_before_model_call():
    image = _small_png()
    files = {
        "front": ("front.png", image, "image/png"),
        "nutrition": ("nutrition.png", image, "image/png"),
        "ingredients": ("ingredients.png", image, "image/png"),
    }
    response = client.post("/v1/extract", files=files)
    assert response.status_code == 422
