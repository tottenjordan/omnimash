"""Unit tests for single-portrait reference hygiene and facial landmark locks."""

from __future__ import annotations

import io

from PIL import Image, ImageDraw

from omnimash.ingestion.ref_cleaner import FacialLandmarkLock, ReferenceHygieneProcessor


def _png_bytes_from_image(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_extract_clean_single_portrait_crops_five_panel_turnaround_at_first_vertical_gutter() -> (
    None
):
    """Verify multi-panel turnaround sheets crop left of the first vertical gutter divider."""
    # Arrange: 1500x600 textured 5-panel turnaround with solid black divider at x=450..456
    img = Image.new("RGB", (1500, 600), (115, 88, 72))
    draw = ImageDraw.Draw(img)
    for y in range(0, 600, 20):
        shade = 70 + (y % 120)
        draw.line([(0, y), (1499, y)], fill=(shade + 35, shade + 10, shade), width=10)
    draw.rectangle([(450, 0), (456, 599)], fill=(0, 0, 0))
    draw.rectangle([(800, 0), (806, 599)], fill=(0, 0, 0))
    draw.rectangle([(1150, 0), (1156, 599)], fill=(0, 0, 0))
    raw_bytes = _png_bytes_from_image(img)

    # Act
    cleaned_bytes, was_cropped = ReferenceHygieneProcessor.extract_clean_single_portrait(raw_bytes)

    # Assert
    assert was_cropped is True
    with Image.open(io.BytesIO(cleaned_bytes)) as cropped:
        assert cropped.width < 450
        assert cropped.height > 550


def test_extract_clean_single_portrait_preserves_single_square_portrait_unchanged() -> None:
    """Verify an 800x1000 single portrait without dividers is preserved without cropping."""
    # Arrange: 800x1000 single portrait with varied vertical color bands and no dividers
    img = Image.new("RGB", (800, 1000), (130, 95, 82))
    draw = ImageDraw.Draw(img)
    for y in range(0, 1000, 25):
        tone = 65 + (y % 100)
        draw.line([(0, y), (799, y)], fill=(tone + 40, tone + 15, tone), width=12)
    raw_bytes = _png_bytes_from_image(img)

    # Act
    cleaned_bytes, was_cropped = ReferenceHygieneProcessor.extract_clean_single_portrait(raw_bytes)

    # Assert
    assert was_cropped is False
    assert cleaned_bytes == raw_bytes
    with Image.open(io.BytesIO(cleaned_bytes)) as preserved:
        assert preserved.size == (800, 1000)


def test_facial_landmark_lock_compiles_positive_flat_ink_and_prop_hand_clause() -> None:
    """Verify FacialLandmarkLock compiles verbatim positive eyewear, flat-ink, and prop clauses."""
    # Arrange
    lock = FacialLandmarkLock(
        eyewear_spec="blue-tinted wire-frame aviator sunglasses with completely clear lens glass",
        tattoo_spec="a small flat black-ink teardrop tattoo strictly below the bottom metal sunglass frame",
        wardrobe_spec="black velvet Hogwarts robes over a crimson hoodie",
        signature_prop_spec="holds a white double-stacked styrofoam cup in his right hand at stomach height; left arm hangs relaxed at his side",
    )

    # Act
    clause = lock.to_fixed_character_clause(character_name="Harry Trap", ref_index=1)

    # Assert
    assert clause.startswith("Harry Trap, the exact person from reference image 1:")
    assert "completely clear lens glass" in clause
    assert "flat black-ink teardrop tattoo" in clause
    assert "black velvet Hogwarts robes over a crimson hoodie" in clause
    assert "white double-stacked styrofoam cup in his right hand" in clause
    assert clause.endswith(".")
