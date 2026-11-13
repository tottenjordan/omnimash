"""Gemini 3.8 TTS voiceover synthesis, phonetic normalization, fit-rule timing, and trailer narrator DSP."""

from __future__ import annotations

import base64
import logging
import os
import re
import subprocess
from typing import Any

from pydantic import BaseModel

from omnimash.audio.sub_bass_808 import write_mock_tone_wav
from omnimash.config import settings

logger = logging.getLogger(__name__)

try:
    from google import genai
except ImportError:
    genai: Any = None

CANONICAL_TRAILER_NARRATOR_VOICE_ID = "voice_9fb52507-bd89-4d3f-88e3-c8acd432fbb0"
DEFAULT_FALLBACK_NARRATOR_VOICE = "Orus"

TRAILER_NARRATOR_AF_CHAIN = (
    "silenceremove=start_periods=1:start_threshold=-50dB,"
    "areverse,silenceremove=start_periods=1:start_threshold=-50dB,areverse,"
    "aresample=24000,asetrate=24000*0.91,aresample=48000,"
    "highpass=f=65,"
    "equalizer=f=85:t=q:w=1.5:g=3.5,"
    "equalizer=f=140:t=q:w=1.4:g=2.5,"
    "equalizer=f=2800:t=q:w=1.4:g=2.0,"
    "acompressor=threshold=-18dB:ratio=3:attack=10:release=120:makeup=2,"
    "aformat=sample_rates=48000:channel_layouts=stereo"
)

_PHONETIC_SUBSTITUTIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b1017\b"), "Ten-Seventeen"),
)
_INLINE_PAUSE_RE = re.compile(r"(?:<\s*(?:short|long)?\s*pause\s*>|\.{3,}|…)", re.IGNORECASE)


class TTSSynthesisResult(BaseModel):
    """Structured result from GeminiTTSClient synthesis and post-processing."""

    audio_path: str
    duration_seconds: float
    transcript_used: str
    voice_name: str
    fit_ratio: float = 1.0
    stripped_pause_tags: bool = False


def normalize_tts_transcript(text: str, strip_pause_tags: bool = False) -> str:
    """Applies phonetic number expansions ('1017' -> 'Ten-Seventeen') and optional pause-tag removal."""
    cleaned = (text or "").strip()
    for pattern, repl in _PHONETIC_SUBSTITUTIONS:
        cleaned = pattern.sub(repl, cleaned)
    if strip_pause_tags:
        cleaned = _INLINE_PAUSE_RE.sub(", ", cleaned)
        cleaned = re.sub(r"\s*,\s*,+", ",", cleaned)
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned


def _truncate_style_words(style: str, max_words: int = 12) -> str:
    """Caps style direction to at most max_words words per Gemini TTS style guidance."""
    words = (style or "").strip().split()
    if len(words) <= max_words:
        return " ".join(words)
    return " ".join(words[:max_words])


def build_audio_genai_clients(
    *,
    project_id: str,
    location: str,
    api_key: str | None = None,
    genai_client: Any | None = None,
    mock_mode: bool = False,
) -> tuple[Any | None, Any | None, Any | None]:
    """Initializes Developer API and Vertex AI global GenAI clients for audio interactions."""
    if genai_client is not None:
        return genai_client, None, None
    if mock_mode or genai is None:
        return None, None, None

    effective_key = (
        api_key
        if api_key is not None
        else (
            os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
            or getattr(settings, "gemini_api_key", None)
            or getattr(settings, "google_api_key", None)
        )
    )
    dev_client: Any | None = None
    vertex_client: Any | None = None

    if effective_key:
        try:
            dev_client = genai.Client(api_key=effective_key, vertexai=False)
        except Exception as exc:
            logger.warning("Failed to initialize Developer API GenAI client: %s", exc)

    try:
        vertex_client = genai.Client(
            vertexai=True,
            project=project_id,
            location=location,
        )
    except Exception as exc:
        logger.warning("Failed to initialize Vertex AI GenAI client: %s", exc)

    active = dev_client or vertex_client
    return active, dev_client, vertex_client


def _decode_audio_item(item: Any, client: Any) -> bytes | None:
    """Decodes raw or base64 audio bytes from an Interaction audio content item."""
    if item is None:
        return None
    data = getattr(item, "data", None)
    if data is None and isinstance(item, dict):
        data = item.get("data")
    if data:
        if isinstance(data, bytes):
            return data
        if isinstance(data, str):
            return base64.b64decode(data)

    uri = getattr(item, "uri", None)
    if uri is None and isinstance(item, dict):
        uri = item.get("uri")
    if uri and client is not None and hasattr(client, "files"):
        downloaded = client.files.download(file=uri)
        if isinstance(downloaded, bytes):
            return downloaded
    return None


def extract_interaction_audio_bytes(interaction: Any, client: Any = None) -> bytes:
    """Extracts audio bytes from Interaction.output_audio, steps, or legacy outputs."""
    output_audio = getattr(interaction, "output_audio", None)
    decoded = _decode_audio_item(output_audio, client)
    if decoded:
        return decoded

    steps = getattr(interaction, "steps", None)
    if isinstance(steps, list):
        for step in reversed(steps):
            content = getattr(step, "content", None)
            if content is None and isinstance(step, dict):
                content = step.get("content")
            if not isinstance(content, list):
                continue
            for item in reversed(content):
                item_type = getattr(item, "type", None) or (
                    item.get("type") if isinstance(item, dict) else None
                )
                if item_type == "audio":
                    decoded = _decode_audio_item(item, client)
                    if decoded:
                        return decoded

    outputs = getattr(interaction, "outputs", None)
    if isinstance(outputs, list):
        for item in reversed(outputs):
            decoded = _decode_audio_item(item, client)
            if decoded:
                return decoded

    raise RuntimeError("Interaction response did not contain audio output bytes")


def create_interaction_with_client_fallback(
    *,
    active_client: Any,
    dev_client: Any | None,
    vertex_client: Any | None,
    kwargs: dict[str, Any],
) -> tuple[Any, Any]:
    """Calls interactions.create on active_client, switching to alternate client on 401/404."""
    if active_client is None or not hasattr(active_client, "interactions"):
        raise RuntimeError("GenAI client with interactions API is not initialized")

    try:
        return active_client.interactions.create(**kwargs), active_client
    except Exception as exc:
        exc_str = str(exc)
        alt_client = vertex_client if active_client is dev_client else dev_client
        if alt_client is not None and (
            "401" in exc_str or "404" in exc_str or "UNAUTHENTICATED" in exc_str
        ):
            logger.warning(
                "Primary GenAI audio client failed (%s); switching to alternate client",
                exc,
            )
            return alt_client.interactions.create(**kwargs), alt_client
        raise


class GeminiTTSClient:
    """Client for Gemini 3.8 Flash TTS via Interactions API with fit-rule enforcement and baritone DSP."""

    def __init__(
        self,
        project_id: str | None = None,
        location: str | None = None,
        model_id: str | None = None,
        api_key: str | None = None,
        mock_mode: bool | None = None,
        genai_client: Any | None = None,
    ) -> None:
        self.project_id = project_id or getattr(settings, "google_cloud_project", "hybrid-vertex")
        self.location = (
            location
            or os.environ.get("GEMINI_LOCATION")
            or getattr(settings, "gemini_location", "global")
        )
        self.model_id = model_id or getattr(settings, "tts_model_id", "gemini-3.8-flash-tts")
        self.mock_mode = (
            mock_mode if mock_mode is not None else getattr(settings, "mock_mode", False)
        )
        self._genai_client, self._dev_client, self._vertex_client = build_audio_genai_clients(
            project_id=self.project_id,
            location=self.location,
            api_key=api_key,
            genai_client=genai_client,
            mock_mode=self.mock_mode,
        )

    @staticmethod
    def probe_audio_duration(audio_path: str) -> float:
        """Measures exact audio duration in seconds via ffprobe."""
        try:
            out = subprocess.check_output(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "csv=p=0",
                    audio_path,
                ],
                text=True,
                timeout=15.0,
            ).strip()
            return float(out)
        except Exception as exc:
            logger.warning("Failed to probe duration for %s: %s", audio_path, exc)
            return 0.0

    def _call_tts_interaction(self, text: str, voice_name: str, style: str = "") -> bytes:
        """Calls Gemini Interactions API for TTS (never sends temperature or system_instruction)."""
        if self._genai_client is None or not hasattr(self._genai_client, "interactions"):
            raise RuntimeError("GenAI client with interactions API is not initialized for TTS")

        text_part: dict[str, Any] = {"type": "text", "text": text}
        concise_style = _truncate_style_words(style, max_words=12)
        if concise_style:
            text_part["annotations"] = [{"type": "speech_metadata", "style": concise_style}]

        kwargs: dict[str, Any] = {
            "model": self.model_id,
            "input": [text_part],
            "generation_config": {
                "speech_config": [{"voice": voice_name}],
            },
            "response_format": {
                "type": "audio",
                "mime_type": "audio/wav",
            },
        }

        interaction, self._genai_client = create_interaction_with_client_fallback(
            active_client=self._genai_client,
            dev_client=self._dev_client,
            vertex_client=self._vertex_client,
            kwargs=kwargs,
        )
        return extract_interaction_audio_bytes(interaction, client=self._genai_client)

    def _synthesize_with_voice_fallback(
        self,
        text: str,
        voice_name: str,
        style: str = "",
    ) -> tuple[bytes, str]:
        """Synthesizes TTS bytes, falling back to DEFAULT_FALLBACK_NARRATOR_VOICE if custom voice fails."""
        try:
            return self._call_tts_interaction(text, voice_name=voice_name, style=style), voice_name
        except Exception as exc:
            if voice_name == DEFAULT_FALLBACK_NARRATOR_VOICE:
                raise
            logger.warning(
                "Custom TTS voice '%s' failed (%s); falling back to prebuilt voice '%s'",
                voice_name,
                exc,
                DEFAULT_FALLBACK_NARRATOR_VOICE,
            )
            audio_bytes = self._call_tts_interaction(
                text,
                voice_name=DEFAULT_FALLBACK_NARRATOR_VOICE,
                style=style,
            )
            return audio_bytes, DEFAULT_FALLBACK_NARRATOR_VOICE

    @staticmethod
    def _apply_dsp_to_wav(raw_path: str, output_path: str, af_chain: str) -> None:
        """Applies FFmpeg DSP filter chain and outputs 48kHz stereo PCM WAV."""
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                raw_path,
                "-af",
                af_chain,
                "-ar",
                "48000",
                "-ac",
                "2",
                output_path,
            ],
            check=True,
            capture_output=True,
            timeout=60.0,
        )

    def synthesize_narrator_stem(
        self,
        text: str,
        output_path: str,
        voice_name: str = CANONICAL_TRAILER_NARRATOR_VOICE_ID,
        style: str = "",
        target_window_sec: float | None = 3.8,
        apply_baritone_dsp: bool = True,
    ) -> TTSSynthesisResult:
        """Synthesizes a narrator stem, enforces the duration fit rule, and applies the baritone DSP chain."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        norm_text = normalize_tts_transcript(text, strip_pause_tags=False)

        if self.mock_mode:
            mock_dur = (
                3.62 if target_window_sec is None else min(3.62, max(0.5, target_window_sec * 0.95))
            )
            write_mock_tone_wav(output_path, duration_sec=mock_dur, freq_hz=110.0, amplitude=0.06)
            fit_ratio = (
                (mock_dur / target_window_sec)
                if (target_window_sec and target_window_sec > 0)
                else 1.0
            )
            return TTSSynthesisResult(
                audio_path=output_path,
                duration_seconds=mock_dur,
                transcript_used=norm_text,
                voice_name=voice_name,
                fit_ratio=fit_ratio,
                stripped_pause_tags=False,
            )

        raw_path = f"{output_path}.raw.wav"
        stripped = False
        af_chain = (
            TRAILER_NARRATOR_AF_CHAIN
            if apply_baritone_dsp
            else "silenceremove=start_periods=1:start_threshold=-45dB,aformat=sample_rates=48000:channel_layouts=stereo"
        )

        try:
            raw_bytes, active_voice = self._synthesize_with_voice_fallback(
                norm_text,
                voice_name=voice_name,
                style=style,
            )
            with open(raw_path, "wb") as f:
                f.write(raw_bytes)

            self._apply_dsp_to_wav(raw_path, output_path, af_chain)
            dur = self.probe_audio_duration(output_path)

            if (
                target_window_sec
                and dur > target_window_sec * 1.08
                and _INLINE_PAUSE_RE.search(norm_text)
            ):
                norm_text = normalize_tts_transcript(text, strip_pause_tags=True)
                stripped = True
                raw_bytes, active_voice = self._synthesize_with_voice_fallback(
                    norm_text,
                    voice_name=active_voice,
                    style=style,
                )
                with open(raw_path, "wb") as f:
                    f.write(raw_bytes)
                self._apply_dsp_to_wav(raw_path, output_path, af_chain)
                dur = self.probe_audio_duration(output_path)

            fit_ratio = (
                (dur / target_window_sec) if (target_window_sec and target_window_sec > 0) else 1.0
            )
            if target_window_sec and 0.93 <= fit_ratio <= 1.08 and abs(fit_ratio - 1.0) > 0.02:
                stretched_path = f"{output_path}.fit.wav"
                try:
                    subprocess.run(
                        [
                            "ffmpeg",
                            "-y",
                            "-i",
                            output_path,
                            "-af",
                            f"atempo={fit_ratio:.4f},aformat=sample_rates=48000:channel_layouts=stereo",
                            "-ar",
                            "48000",
                            "-ac",
                            "2",
                            stretched_path,
                        ],
                        check=True,
                        capture_output=True,
                        timeout=60.0,
                    )
                    os.replace(stretched_path, output_path)
                    dur = self.probe_audio_duration(output_path)
                finally:
                    if os.path.exists(stretched_path):
                        os.remove(stretched_path)
        finally:
            if os.path.exists(raw_path):
                os.remove(raw_path)

        return TTSSynthesisResult(
            audio_path=output_path,
            duration_seconds=dur,
            transcript_used=norm_text,
            voice_name=active_voice,
            fit_ratio=fit_ratio,
            stripped_pause_tags=stripped,
        )
