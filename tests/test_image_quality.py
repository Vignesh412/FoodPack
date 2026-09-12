import io

from PIL import Image, ImageDraw, ImageFilter

from src.image_quality import deterministic_precheck, run_quality_gate
from src.schemas import PanelType


def _sharp_label_image() -> bytes:
    img = Image.new("L", (900, 1200), color=230)
    draw = ImageDraw.Draw(img)
    for y in range(50, 1150, 40):
        draw.line([(50, y), (850, y)], fill=20, width=3)
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def test_sharp_well_lit_image_passes():
    result = deterministic_precheck(_sharp_label_image())
    assert result.passed is True


def test_blurry_image_is_rejected():
    img = Image.open(io.BytesIO(_sharp_label_image())).filter(ImageFilter.GaussianBlur(radius=8))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    result = deterministic_precheck(buf.getvalue())
    assert result.passed is False
    assert any("out of focus" in issue for issue in result.issues)


def test_low_resolution_image_is_rejected():
    small = Image.open(io.BytesIO(_sharp_label_image())).resize((200, 260))
    buf = io.BytesIO()
    small.save(buf, format="JPEG")
    result = deterministic_precheck(buf.getvalue())
    assert result.passed is False
    assert any("resolution" in issue.lower() for issue in result.issues)


def test_wide_sharp_ingredients_strip_reaches_the_vision_readability_gate():
    image = Image.new("L", (2400, 360), color=225)
    draw = ImageDraw.Draw(image)
    for y in range(25, 340, 24):
        draw.line([(30, y), (2370, y)], fill=25, width=3)
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="JPEG", quality=95)

    ingredients = deterministic_precheck(
        buffer.getvalue(),
        expected_panel=PanelType.INGREDIENTS_ALLERGENS,
    )
    nutrition = deterministic_precheck(
        buffer.getvalue(),
        expected_panel=PanelType.NUTRITION_FACTS,
    )

    assert ingredients.passed is True
    assert nutrition.passed is False
    assert any("resolution" in issue.lower() for issue in nutrition.issues)


def test_blown_out_glare_image_is_rejected():
    glare = Image.new("L", (900, 1200), color=252)
    buf = io.BytesIO()
    glare.convert("RGB").save(buf, format="JPEG")
    result = deterministic_precheck(buf.getvalue())
    assert result.passed is False
    assert any("glare" in issue.lower() for issue in result.issues)


def test_quality_gate_skips_vision_call_when_requested():
    gate = run_quality_gate(_sharp_label_image(), skip_vision_call=True)
    assert gate.accepted is True


def test_quality_gate_fails_gracefully_without_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    gate = run_quality_gate(_sharp_label_image())
    assert gate.accepted is False
    assert "ANTHROPIC_API_KEY" in gate.reason
