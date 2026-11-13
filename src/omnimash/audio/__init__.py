"""OmniMash v2.0 3-stem audio engine: Gemini TTS, Lyria 3, Tuned 808s, and EBU R128 mastering."""

from omnimash.audio.lyria_client import LyriaClient, LyriaScoreResult
from omnimash.audio.mastering import (
    AudioGuillotineWindow,
    LoudnessReport,
    SonicMixPreset,
    SonicMixPresetConfig,
    ThreeStemMasteringEngine,
    resolve_sonic_mix_preset_defaults,
)
from omnimash.audio.sub_bass_808 import (
    NOTE_FREQUENCIES_HZ,
    snap_timestamp_to_bpm_grid,
    synthesize_tuned_808_wav,
)
from omnimash.audio.tts_client import (
    CANONICAL_TRAILER_NARRATOR_VOICE_ID,
    DEFAULT_FALLBACK_NARRATOR_VOICE,
    TRAILER_NARRATOR_AF_CHAIN,
    GeminiTTSClient,
    TTSSynthesisResult,
    normalize_tts_transcript,
)

__all__ = [
    "AudioGuillotineWindow",
    "CANONICAL_TRAILER_NARRATOR_VOICE_ID",
    "DEFAULT_FALLBACK_NARRATOR_VOICE",
    "GeminiTTSClient",
    "LoudnessReport",
    "LyriaClient",
    "LyriaScoreResult",
    "NOTE_FREQUENCIES_HZ",
    "SonicMixPreset",
    "SonicMixPresetConfig",
    "TRAILER_NARRATOR_AF_CHAIN",
    "TTSSynthesisResult",
    "ThreeStemMasteringEngine",
    "normalize_tts_transcript",
    "resolve_sonic_mix_preset_defaults",
    "snap_timestamp_to_bpm_grid",
    "synthesize_tuned_808_wav",
]
