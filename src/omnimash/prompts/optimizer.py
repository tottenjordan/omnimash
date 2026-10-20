"""Prompt optimization and refinement engine for Gemini Omni Flash directives."""

from __future__ import annotations

import logging
from typing import Any

from omnimash.config import settings

logger = logging.getLogger("omnimash.prompts.optimizer")


class PromptOptimizer:
    """Optimizes compiled storyboards into cohesive Gemini Omni Flash directives."""

    def __init__(self, compiler: Any = None) -> None:
        self.compiler = compiler

    def optimize(self, compiled_prompt: str, use_llm: bool = False) -> str:
        """Synthesizes structured block prompts into dense, qualitative directives."""
        if not compiled_prompt or not compiled_prompt.strip():
            return compiled_prompt

        # Tier 1: Normalize quantitative audio mixing terms to qualitative descriptors
        optimized = compiled_prompt.replace(
            "(ducked at 15% volume under dialogue)",
            "(subtly ducked in the background beneath dialogue)",
        ).replace(
            "is quietly ducked at 15% volume in the background",
            "is subtly ducked in the background beneath dialogue",
        )

        # Tier 2: LLM Optimization Pass via Gemini Flash (if requested and client available)
        if use_llm and self.compiler:
            client = getattr(self.compiler, "_flash_regional_client", None) or getattr(
                self.compiler, "_pro_global_client", None
            )
            if client:
                try:
                    from google.genai import types

                    system_instruction = (
                        "You are an expert multimodal prompt engineer for Gemini Omni Flash. "
                        "Refine and condense the following structured storyboard prompt into a clear, "
                        "vivid, single-pass generation directive. "
                        "CRITICAL: Keep all [IMAGE ROLES] and [ROLE DEFINITIONS] blocks intact."
                    )
                    # Pass system_instruction via types.GenerateContentConfig per google-genai SDK docs
                    # Source: https://googleapis.github.io/python-genai/genai.html#google.genai.types.GenerateContentConfig
                    config = types.GenerateContentConfig(
                        system_instruction=system_instruction,
                    )
                    response = client.models.generate_content(
                        model=getattr(settings, "flash_model_id", "gemini-3.8-flash"),
                        contents=f"[PROMPT TO OPTIMIZE]:\n{optimized}",
                        config=config,
                    )
                    if response and getattr(response, "text", None):
                        llm_out = response.text.strip()
                        if llm_out and "[ROLE DEFINITIONS]" in llm_out:
                            return llm_out
                except Exception as exc:
                    logger.warning(
                        "PromptOptimizer LLM pass failed, using Tier 1 prompt: %s",
                        exc,
                    )

        return optimized


__all__ = ["PromptOptimizer"]
