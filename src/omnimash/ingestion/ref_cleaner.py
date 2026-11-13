"""Single-portrait reference extraction and facial landmark hygiene for character turnaround sheets."""

from __future__ import annotations

import io
import logging
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

try:
    from PIL import Image

    HAS_PIL = True
except ImportError:
    Image: Any = None
    HAS_PIL = False


class FacialLandmarkLock(BaseModel):
    """Positive physical landmark locks preventing lens-tattoo bleed and ear-drip hallucinations."""

    eyewear_spec: str = Field(
        default="",
        description="Positive eyewear clarity lock, e.g. 'blue-tinted wire-frame aviator sunglasses with completely clear lens glass'",
    )
    tattoo_spec: str = Field(
        default="",
        description="Positive flat-ink tattoo geometry lock, e.g. 'a small teardrop tattoo on the cheekbone strictly below the bottom metal sunglass frame, a larger flat black-ink teardrop tattoo on the cheek in front of and below the ear'",
    )
    wardrobe_spec: str = Field(
        default="",
        description="Canonical wardrobe specification",
    )
    signature_prop_spec: str = Field(
        default="",
        description="Canonical hand-locked prop specification, e.g. 'holds a white double-stacked styrofoam cup in his right hand at stomach height; left arm hangs relaxed at his side'",
    )

    def to_fixed_character_clause(self, character_name: str, ref_index: int = 1) -> str:
        """Compiles the verbatim FixedCharacterBlock pasted identically across all shots."""
        parts = [f"{character_name}, the exact person from reference image {ref_index}:"]
        details = [
            s.strip().rstrip(".")
            for s in (self.eyewear_spec, self.tattoo_spec, self.wardrobe_spec)
            if s and s.strip()
        ]
        if details:
            parts.append(", ".join(details) + ".")
        if self.signature_prop_spec and self.signature_prop_spec.strip():
            parts.append(self.signature_prop_spec.strip().rstrip(".") + ".")
        return " ".join(parts)


class ReferenceHygieneProcessor:
    """Detects multi-panel turnaround divider grids and extracts a borderless single portrait."""

    @staticmethod
    def _find_vertical_gutter_columns(img: Any, variance_threshold: float = 12.0) -> list[int]:
        """Scans image columns to find solid black/white vertical panel dividers."""
        width, height = img.size
        rgb = img.convert("RGB")
        pixels = rgb.load()
        if pixels is None:
            return []
        gutter_cols: list[int] = []
        # Scan interior 15%..85% width for uniform divider columns
        start_x = int(width * 0.15)
        end_x = int(width * 0.85)
        step_y = max(1, height // 64)
        for x in range(start_x, end_x):
            samples = [pixels[x, y] for y in range(0, height, step_y)]
            r_vals = [int(p[0]) for p in samples]
            g_vals = [int(p[1]) for p in samples]
            b_vals = [int(p[2]) for p in samples]
            spread = max(
                max(r_vals) - min(r_vals),
                max(g_vals) - min(g_vals),
                max(b_vals) - min(b_vals),
            )
            mean_luma = (sum(r_vals) + sum(g_vals) + sum(b_vals)) / (3.0 * len(samples))
            if spread <= variance_threshold and (mean_luma <= 25.0 or mean_luma >= 235.0):
                gutter_cols.append(x)
        return gutter_cols

    @classmethod
    def extract_clean_single_portrait(
        cls,
        image_bytes: bytes,
        border_inset_px: int = 8,
    ) -> tuple[bytes, bool]:
        """Crops the primary left/hero portrait panel from a multi-panel turnaround sheet.

        Returns:
            (cleaned_png_bytes, was_cropped_from_multi_panel)
        """
        if not HAS_PIL or not image_bytes:
            return image_bytes, False

        try:
            with Image.open(io.BytesIO(image_bytes)) as img:
                width, height = img.size
                if width < 200 or height < 200:
                    return image_bytes, False

                gutter_cols = cls._find_vertical_gutter_columns(img)
                was_multi_panel = False
                crop_right = width

                # If a vertical divider gutter exists in the left-to-middle region (20%..65% of width),
                # crop the primary hero portrait panel to the left of the first gutter.
                valid_gutters = [
                    x for x in gutter_cols if int(width * 0.20) <= x <= int(width * 0.65)
                ]
                if valid_gutters:
                    crop_right = valid_gutters[0]
                    was_multi_panel = True
                elif width / float(height) >= 1.65:
                    # Wide 16:9 turnaround sheet without hard gutter line: extract primary hero third
                    crop_right = int(width * 0.38)
                    was_multi_panel = True

                if not was_multi_panel:
                    return image_bytes, False

                inset_x = min(border_inset_px, crop_right // 10)
                inset_y = min(border_inset_px, height // 10)
                box = (
                    inset_x,
                    inset_y,
                    max(inset_x + 64, crop_right - inset_x),
                    max(inset_y + 64, height - inset_y),
                )
                cropped = img.convert("RGB").crop(box)
                out_buf = io.BytesIO()
                cropped.save(out_buf, format="PNG")
                return out_buf.getvalue(), True
        except Exception as exc:
            logger.warning("ReferenceHygieneProcessor failed to inspect/crop image bytes: %s", exc)
            return image_bytes, False


__all__ = [
    "FacialLandmarkLock",
    "ReferenceHygieneProcessor",
]
