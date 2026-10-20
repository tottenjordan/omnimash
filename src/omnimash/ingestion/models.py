from __future__ import annotations

from dataclasses import dataclass, field

KEYFRAME_WIDTH: int = 1280
KEYFRAME_HEIGHT: int = 720
JPEG_QUALITY: int = 90


@dataclass
class ExtractedReference:
    is_valid: bool
    source_url: str | None = None
    keyframes: list[str] = field(default_factory=list)
    audio_track_path: str | None = None
    description: str | None = None
    gcs_uri: str | None = None


@dataclass
class KeyframeAnnotation:
    timestamp: str
    image_url: str
    usage_annotation: str


@dataclass
class ParodyResearchResult:
    synopsis: str
    suggested_props: list[str]
    suggested_vibe: str
    vibe_intensity: int
    suggested_audio: str
    suggested_dialogue: str


@dataclass
class ReferenceAnalysisReport:
    video_title: str
    duration_seconds: int
    detected_bpm: int
    dominant_colors: list[str]
    extracted_keyframes: list[KeyframeAnnotation]


@dataclass(frozen=True)
class KeyframeSpec:
    filename: str
    timestamp: str
    color_hex: str
    canvas_label: str
    usage_annotation: str


DEFAULT_KEYFRAME_SPECS: tuple[KeyframeSpec, ...] = (
    KeyframeSpec(
        filename="frame_1.jpg",
        timestamp="00:02",
        color_hex="#DE5FE9",
        canvas_label="🎯 [SUBJECT ANCHOR]: Facial Likeness & Hair Conditioning",
        usage_annotation="🎯 [SUBJECT ANCHOR]: Conditioning facial likeness, expression, and hair baseline.",
    ),
    KeyframeSpec(
        filename="frame_2.jpg",
        timestamp="00:15",
        color_hex="#38BDF8",
        canvas_label="🧥 [AESTHETIC BASELINE]: High-Fashion Trap Wardrobe & Lighting",
        usage_annotation="🧥 [AESTHETIC BASELINE]: Reference for lighting contrast and initial character wardrobe.",
    ),
    KeyframeSpec(
        filename="frame_3.jpg",
        timestamp="00:30",
        color_hex="#34A853",
        canvas_label="🎵 [ACOUSTIC STEM]: Tempo Reference & Spectral Analysis",
        usage_annotation="🎵 [ACOUSTIC STEM]: Tempo reference extracted for 120 BPM audio track synchronization.",
    ),
)


def build_parody_research_result(subject: str, aesthetic: str) -> ParodyResearchResult:
    """Synthesizes parody clash research tailored to the requested subject and aesthetic."""
    subj_clean = (subject or "").strip() or "Harry Potter and Draco Malfoy"
    aes_clean = (aesthetic or "").strip() or "Atlanta Trap Disstrack"

    is_default_hogwarts = (
        "harry" in subj_clean.lower()
        or "draco" in subj_clean.lower()
        or "hogwarts" in subj_clean.lower()
    ) and ("trap" in aes_clean.lower() or "atlanta" in aes_clean.lower())

    if is_default_hogwarts:
        return ParodyResearchResult(
            synopsis="Dripwarts: Harry & The Brick Factory - A high-fashion parody mashup blending Hogwarts wizard rivalry with 2010s Atlanta trap music beef (Gucci vs. Jeezy).",
            suggested_props=[
                "Diamond Lightning Bolt Chain",
                "Vintage Gucci Tracksuit",
                "Slytherin Snowman Pendant",
                "Microphone Wand",
                "Shutter Shades",
            ],
            suggested_vibe="Dark moody 808 bass lighting, laser smoke, and high-gloss neon reflections",
            vibe_intensity=75,
            suggested_audio="140 BPM Heavy 808 Trap",
            suggested_dialogue='Harry: "I been cooking potions since first year. Burrr!" / Draco: "This is Trap or Die, Potter!"',
        )

    return ParodyResearchResult(
        synopsis=f"{subj_clean} x {aes_clean} — A stylized cinematic parody mashup fusing {subj_clean} iconography with {aes_clean} visual and sonic motifs.",
        suggested_props=[
            f"Custom {aes_clean} Chain & Emblem",
            f"Tailored {aes_clean} Signature Wardrobe",
            f"Hero Prop Inspired by {subj_clean}",
            "Studio Condenser Microphone",
            "High-Contrast Designer Eyewear",
        ],
        suggested_vibe=f"High-contrast {aes_clean} lighting, atmospheric haze, and dynamic anamorphic reflections",
        vibe_intensity=80,
        suggested_audio=f"130 BPM {aes_clean} Instrumental Stem (Heavy 808 & Synth Layer)",
        suggested_dialogue=f'Lead ({subj_clean}): "We run this whole {aes_clean} arena now!"',
    )
