from typing import Any
from pydantic import BaseModel, Field


class GenerateCharacterSheetRequest(BaseModel):
    character_name: str | None = None
    description: str | None = None
    source_image_url: str | None = None
    aesthetic_tags: list[str] = Field(default_factory=list)
    aspect_ratio: str = "16:9"
    model: str = "gemini-nano-banana-2.1"
    custom_prompt: str | None = None
    style_preset: str | None = None


class GenerateCharacterSheetResponse(BaseModel):
    success: bool
    character_name: str | None = None
    keyframe_image_url: str
    compiled_prompt: str
    raw_compiled_prompt: str
    aspect_ratio: str
    model: str
    details: str | None = None


class SaveCharacterSheetRequest(BaseModel):
    session_name: str | None = None
    project_name: str | None = None
    image_data: str
    custom_name: str = "character_sheet"
    set_as_active_reference: bool = True
    character_role_id: str | None = None


class SaveCharacterSheetResponse(BaseModel):
    success: bool
    public_url: str
    gcs_uri: str
    storage_path: str = ""
    details: str | None = None


class CharacterRoleModel(BaseModel):
    role_id: str
    name: str = ""
    description: str = ""
    reference_url: str | None = None
    aesthetic_tags: list[str] = Field(default_factory=list)
    voice_style: str = ""
    voice_profile: str = ""
    wardrobe: str = ""
    image_role: str = "Character Reference"
    is_offscreen_narrator: bool = False

    @classmethod
    def from_storage_dict(
        cls, data: dict[str, Any], default_role_id: str = "Role A"
    ) -> "CharacterRoleModel":
        return cls(
            role_id=data.get("role_id", default_role_id),
            name=data.get("name", ""),
            description=data.get("description", ""),
            reference_url=data.get("reference_url"),
            aesthetic_tags=data.get("aesthetic_tags", []),
            voice_style=data.get("voice_style", ""),
            voice_profile=data.get("voice_profile", ""),
            wardrobe=data.get("wardrobe", ""),
            image_role=data.get("image_role", "Character Reference"),
            is_offscreen_narrator=data.get("is_offscreen_narrator", False),
        )


class SaveCharacterRequest(BaseModel):
    session_name: str | None = None
    project_name: str | None = None
    character: CharacterRoleModel
    is_library: bool = True


class SaveCharacterResponse(BaseModel):
    success: bool = True
    gcs_uri: str = ""
    message: str = ""


class ProjectListResponse(BaseModel):
    projects: list[str]


class CreateProjectRequest(BaseModel):
    project_name: str


class CreateProjectResponse(BaseModel):
    success: bool = True
    project_name: str
    gcs_uri: str = ""
    message: str = ""


class CreateSessionRequest(BaseModel):
    session_name: str


class CreateSessionResponse(BaseModel):
    success: bool = True
    project_name: str
    session_name: str
    gcs_uri: str = ""
    message: str = ""


class ReferenceSheetListResponse(BaseModel):
    reference_sheets: list[dict[str, Any]] = Field(default_factory=list)


class SessionListResponse(BaseModel):
    sessions: list[str]


class CharacterListResponse(BaseModel):
    characters: list[CharacterRoleModel] = Field(default_factory=list)


class LoadCharacterRequest(BaseModel):
    slug: str
    session_name: str | None = None


class SaveRosterRequest(BaseModel):
    session_name: str
    characters: list[CharacterRoleModel]


class DeconstructedSceneModel(BaseModel):
    scene_number: int = 1
    active_roles: list[str] = Field(default_factory=lambda: ["Role A"])
    action: str = ""
    dialogue: str = ""
    audio_cues: str = ""
    timecode: str = "0-10s"
    duration_seconds: float = 10.0


class DeconstructResponse(BaseModel):
    characters: list[CharacterRoleModel] = Field(default_factory=list)
    aesthetic_tags: list[str] = Field(default_factory=list)
    environment_tag: str = ""
    camera_lighting_tag: str = ""
    audio_beat: str = ""
    vocal_delivery: str = ""
    keyframe_image_prompt: str = ""
    screenplay_script: str = ""
    scenes: list[DeconstructedSceneModel] = Field(default_factory=list)


class ConceptDeconstructRequest(BaseModel):
    concept: str


class ResearchRequest(BaseModel):
    subject: str
    aesthetic: str


class ExtractReferenceRequest(BaseModel):
    url: str
    session_name: str | None = None


class MotionReferenceRequest(BaseModel):
    input_video_path: str
    start_sec: float = 0.0


class MotionReferenceResponse(BaseModel):
    success: bool = True
    clip_path: str
    message: str | None = None


class GenerateRequest(BaseModel):
    user_id: str = "usr_default"
    project_id: str = "prj_default"
    prompt: str = ""
    clip_index: int = 0
    parent_turn_id: str | None = None
    reference_url: str | None = None
    audio_stem: str | None = None
    voiceover: str | None = None
    is_silent: bool = False
    on_screen_text: str | None = None
    compiled_override: str | None = None
    session_name: str | None = None
    concept: str | None = None
    characters: list[CharacterRoleModel | dict[str, Any]] | None = None
    scenes: list[dict[str, Any]] | None = None
    aesthetic_tags: list[str] | None = None
    environment_tag: str | None = None
    vocal_delivery: str = ""
    optimize_prompt: bool = False
    shot_directive: str | None = None
    enable_safety_sanitization: bool = True
    aspect_ratio: str = "16:9"
    resolution: str = "720p"
    last_frame_image_url: str | None = None


class DiffRequest(GenerateRequest):
    pass


class ScenesRequest(GenerateRequest):
    pass


class CommitRequest(BaseModel):
    user_id: str = "usr_default"
    project_id: str = "prj_default"
    turn_id: str
    next_prompt: str = ""
    session_name: str | None = None


class SaveFinalRequest(BaseModel):
    session_name: str | None = None
    video_url: str
    master_title: str
    is_single_clip: bool = False
    master_audio_path: str | None = None
    master_audio_url: str | None = None


class StoryboardShotModel(BaseModel):
    shot_index: int
    duration_seconds: float
    action: str
    location: str
    style_lighting: str
    framing_motion: str
    audio: str
    dialogue: str = ""
    summary: str = ""
    keyframe_image_url: str = ""
    last_frame_image_url: str | None = None
    resolution: str = "720p"
    video_url: str = ""
    narrative_stage: str = "Rising Action"
    preceding_context: str = ""
    camera_transition: str = "Continuous match cut"
    character_continuity: str = (
        "Maintain subject outfit, posture, and facial expression from preceding shot"
    )
    title_card_text: str | None = None
    title_card_subtitle: str | None = None
    narrator_text: str | None = None


class StoryboardExpandRequest(BaseModel):
    concept: str
    style_tone: str = "Cinematic Trap Parody"
    target_duration: float = 30.0
    characters: list[CharacterRoleModel | dict[str, Any]] | None = None
    screenplay_script: str = ""
    directors_notes: str = ""
    camera_lighting: str | None = None
    aesthetic_tags: list[str] | None = None
    audio_beat: str | None = None
    vocal_delivery: str | None = None
    environment: str | None = None


class StoryboardExpandResponse(BaseModel):
    shots: list[StoryboardShotModel]


class SaveStoryboardRequest(BaseModel):
    name: str
    storyboard_data: dict[str, Any]
    session_name: str | None = None
    is_library: bool = True


class SaveStoryboardResponse(BaseModel):
    success: bool
    gcs_uri: str
    message: str


class DraftBatchShotItem(BaseModel):
    shot_index: int
    action: str
    style_lighting: str | None = None
    audio: str | None = None
    location: str | None = None
    keyframe_image_url: str | None = None


class DraftBatchRequest(BaseModel):
    session_name: str | None = None
    shots: list[DraftBatchShotItem]
    variations_per_shot: int = 2
    resolution: str = "360p"
    aspect_ratio: str = "16:9"


class DraftBatchItem(BaseModel):
    shot_index: int
    variation_index: int
    action: str
    resolution: str = "360p"
    status: str = "COMPLETED"
    video_url: str | None = None
    gcs_uri: str | None = None
    turn_id: str | None = None
    keyframe_image_url: str | None = None


class DraftBatchResponse(BaseModel):
    success: bool
    session_name: str
    resolution: str
    total_drafts: int
    drafts: list[DraftBatchItem]


class StoryboardMetadataModel(BaseModel):
    name: str
    slug: str
    concept: str = ""
    shot_count: int = 0
    updated_at: str = ""


class StoryboardListResponse(BaseModel):
    storyboards: list[StoryboardMetadataModel]


class LoadStoryboardRequest(BaseModel):
    slug: str
    session_name: str | None = None


class DeleteStoryboardRequest(BaseModel):
    slug: str
    session_name: str | None = None


class KeyframeImageRequest(BaseModel):
    shot_index: int = 1
    image_prompt: str | None = None
    action: str = ""
    location: str = ""
    style_lighting: str = ""
    summary: str = ""
    characters: list[CharacterRoleModel | dict[str, Any]] | None = None
    reference_image_urls: list[str] | None = None
    anchor_keyframe_url: str | None = None
    aspect_ratio: str = "16:9"


class KeyframeImageResponse(BaseModel):
    success: bool = True
    keyframe_image_url: str


class GenerateShotRequest(BaseModel):
    session_name: str | None = "parody_session_1"
    shot_index: int = 1
    shot_directive: str = ""
    action: str = ""
    location: str = ""
    framing_motion: str = ""
    audio: str = ""
    dialogue: str = ""
    characters: list[CharacterRoleModel | dict[str, Any]] | None = None
    duration_seconds: float = 10.0
    parent_turn_id: str | None = None
    keyframe_image_url: str | None = None
    last_frame_image_url: str | None = None
    resolution: str = "720p"
    style_lighting: str = ""
    audio_stem: str | None = None
    enable_safety_sanitization: bool = True
    title_card_text: str | None = None
    title_card_subtitle: str | None = None
    narrator_text: str | None = None
    aspect_ratio: str = "16:9"
    motion_reference_clip: str | None = None
    is_seamless_loop: bool = False


class GenerateShotResponse(BaseModel):
    success: bool = True
    video_url: str | None = None
    keyframe_image_url: str | None = None
    turn_id: str | None = None
    status: str = "COMPLETED"
    generation_mode: str = "LIVE_OMNI_FLASH"
    error: str | None = None
    raw_compiled_prompt: str | None = None


class StitchClipsRequest(BaseModel):
    session_name: str
    clip_urls: list[str]
    master_title: str = "custom_stitched_cut"


class StitchMasterRequest(BaseModel):
    session_id: str | None = None
    shot_clips: list[str] = Field(default_factory=list)
    title_cards: list[dict[str, Any]] | None = None
    narrator_audio_paths: list[str] | None = None
    background_music_path: str | None = None
    aspect_ratio: str = "16:9"


class Journey3SetupRequest(BaseModel):
    project_id: str | None = None
    project_name: str | None = None
    session_id: str | None = None
    master_description: str
    aspect_ratio: str = "16:9"
    characters: list[dict[str, Any]] | None = None
    products: list[dict[str, Any]] | None = None
    style_presets: list[str] | None = None
    style_preset: str | None = None
    image_model: str | None = "gemini-nano-banana-2.1"
    enable_safety_sanitization: bool = True


class Journey3KeyframePromptEditRequest(BaseModel):
    session_id: str | None = None
    project_name: str | None = None
    shot_index: int
    image_prompt: str
    aspect_ratio: str = "16:9"
    reference_image_urls: list[str] | None = None
    characters: list[dict[str, Any]] | None = None
    included_character_ids: list[str] | None = None
    style_preset: str | None = None
    image_model: str | None = "gemini-nano-banana-2.1"


class Journey3ShotGenerateRequest(BaseModel):
    session_id: str | None = None
    project_name: str | None = None
    shot_index: int = 1
    action_directive: str = ""
    prompt: str | None = None
    turn_id: str | None = None
    previous_interaction_id: str | None = None
    dialogue_text: str = ""
    keyframe_image_url: str | None = None
    last_frame_image_url: str | None = None
    resolution: str = "720p"
    aspect_ratio: str = "16:9"
    enable_safety_sanitization: bool = True
    compiled_override: str | None = None
    characters: list[dict[str, Any]] | None = None
    included_character_ids: list[str] | None = None
    audio_mode: str = "global"
    audio_stem: str | None = None
    global_audio_beat: str | None = None
    title_card_text: str | None = None
    title_card_subtitle: str | None = None
    narrator_text: str | None = None
    narrator_voice: str | None = None
    style_preset: str | None = None
    model_style: str | None = None
    motion_reference_clip: str | None = None
    is_seamless_loop: bool = False


Journey3GenerateShotRequest = Journey3ShotGenerateRequest


class Journey3StitchMasterRequest(BaseModel):
    session_id: str | None = None
    shot_clips: list[str] = Field(default_factory=list)
    title_cards: list[dict[str, Any]] | None = None
    aspect_ratio: str = "16:9"


class SaveFinalResponse(BaseModel):
    success: bool
    gcs_uri: str
    message: str
    video_url: str | None = None
    share_url: str | None = None
    share_expires_at: str | None = None


class CreateShareLinkRequest(BaseModel):
    session_name: str = Field(..., description="Session identifier or name")
    video_url: str = Field(
        ..., description="GCS URI (gs://...), media-proxy URL, or master filename"
    )
    master_title: str | None = Field(
        default=None, description="Optional title for the master video"
    )
    expiration_days: int = Field(default=7, ge=1, le=7, description="Lifespan in days (1 to 7)")


class CreateShareLinkResponse(BaseModel):
    success: bool
    share_url: str
    download_url: str
    embed_snippet: str
    expires_at: str
    lifespan_days: int = 7
    gcs_uri: str
    filename: str
    message: str


class ExtendSceneRequest(BaseModel):
    session_name: str | None = None
    turn_id: str | None = None
    previous_interaction_id: str | None = None
    next_scene_action: str = ""
    dialogue: str | None = None
    active_roles: list[str] | None = None
    vocal_delivery: str = ""
    resolution: str = "720p"


class GenerateResponse(BaseModel):
    success: bool
    status: str
    video_url: str | None = None
    turn_id: str | None = None
    depth: int = 0
    error: str | None = None
    generation_mode: str = "LIVE_OMNI_FLASH"
    raw_compiled_prompt: str | None = None
    reference_analysis: dict[str, Any] | None = None


# --- Mode 4: Director's Co-Pilot Domain Models ---


class IntentSlotInputs(BaseModel):
    characters: list[str] = Field(
        default_factory=list, description="Explicit character names or roles"
    )
    setting: str | None = Field(default=None, description="Specific location or environment")
    style_tone: str | None = Field(default=None, description="Visual aesthetic and lighting tone")
    audio_beat: str | None = Field(default=None, description="Background music genre and tempo")
    sound_effects: str | None = Field(
        default=None, description="Parenthetical diegetic sound effects"
    )
    dialogue: str | None = Field(default=None, description="Specific spoken dialogue or monologue")


class ClarificationQuestionOption(BaseModel):
    id: str
    label: str
    description: str = ""


class ClarificationQuestion(BaseModel):
    question_id: str
    slot_target: (
        str  # "characters" | "setting" | "style_tone" | "audio_beat" | "sound_effects" | "dialogue"
    )
    title: str
    subtitle: str = ""
    options: list[ClarificationQuestionOption] = Field(default_factory=list)
    allow_custom: bool = True


class AnalyzeIntentGapsRequest(BaseModel):
    intent: str = Field(..., description="Raw user intent or premise")
    optional_inputs: IntentSlotInputs = Field(default_factory=IntentSlotInputs)
    session_name: str | None = None


class AnalyzeIntentGapsResponse(BaseModel):
    success: bool = True
    intent: str
    filled_slots: dict[str, Any] = Field(default_factory=dict)
    missing_slots: list[str] = Field(default_factory=list)
    questions: list[ClarificationQuestion] = Field(default_factory=list)
    can_auto_fill_immediately: bool = True


class AutoFillIntentPlanRequest(BaseModel):
    intent: str
    optional_inputs: IntentSlotInputs = Field(default_factory=IntentSlotInputs)
    question_answers: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of question_id to chosen option or write-in",
    )
    resolution: str = "720p"
    aspect_ratio: str = "16:9"
    enable_safety_sanitization: bool = True
    session_name: str | None = None


class CohesiveProductionPlan(BaseModel):
    intent: str
    style_tone: str
    characters: list[CharacterRoleModel] = Field(default_factory=list)
    environment: str
    camera_lighting: str
    audio_beat: str
    sound_effects: str = ""
    vocal_delivery: str
    screenplay_script: str
    scenes: list[DeconstructedSceneModel] = Field(default_factory=list)
    keyframe_image_prompt: str
    raw_compiled_prompt: str


class AutoFillIntentPlanResponse(BaseModel):
    success: bool = True
    plan: CohesiveProductionPlan
    raw_compiled_prompt: str
    details: str = ""
