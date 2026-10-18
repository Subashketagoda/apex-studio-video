import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class VisualSegment(BaseModel):
    """Specifies visual cues, shot type, camera motion, and stock video queries for a scene."""
    order: int = Field(..., description="Sequential order of the clip (1 to N)")
    search_query: str = Field(
        ..., 
        description="Primary concise 2-4 word stock search keyword (e.g. 'vintage coca cola glass bottle')"
    )
    pexels_keywords: List[str] = Field(
        default_factory=list,
        description="Targeted Pexels video search terms for this specific scene"
    )
    scene_description: str = Field(
        ..., 
        description="Detailed description of what should be visually depicted in this scene"
    )
    shot_type: str = Field(
        default="medium cinematic shot",
        description="Suggested shot framing (e.g. 'aerial wide shot', 'macro close-up', 'eye-level tracking')"
    )
    camera_movement: str = Field(
        default="slow push-in",
        description="Suggested camera motion (e.g. 'cinematic push-in', 'orbit right', 'static tripod', 'slow tilt down')"
    )
    on_screen_text: str = Field(
        default="",
        description="Bold on-screen takeaway text / key metric overlay for the scene"
    )
    approx_duration_sec: float = Field(
        default=6.0, 
        description="Approximate duration of this segment in seconds"
    )
    narration_text: Optional[str] = Field(
        default=None,
        description="The corresponding portion of voiceover spoken during this scene"
    )

    @field_validator("search_query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("search_query cannot be empty.")
        # Reject generic filler search terms
        generic = {"generic stock", "cool video", "cinematic footage", "abstract motion", "something cool"}
        if clean.lower() in generic:
            raise ValueError(f"Generic search query '{clean}' rejected. Must specify topic-relevant visual keywords.")
        return clean


class FactualClaim(BaseModel):
    """Factual claim extracted from the script, supported by primary sources."""
    claim: str = Field(..., description="The empirical claim or factual statement")
    source_name: str = Field(..., description="Primary source title or organization")
    source_url: str = Field(..., description="URL to the primary verifying source")
    verification_status: str = Field(
        default="verified", 
        description="'verified', 'for_review', or 'creative_narration'"
    )
    is_creative_narration: bool = Field(
        default=False,
        description="True if this is stylistic/rhetorical hook or transition rather than an empirical claim"
    )
    corroboration_notes: Optional[str] = Field(
        default=None,
        description="Evidence or notes supporting the factual claim"
    )


class SubtitleSegment(BaseModel):
    """Timing and text for an individual subtitle block."""
    start: float = Field(..., description="Start time in seconds")
    end: float = Field(..., description="End time in seconds")
    text: str = Field(..., description="Clean displayed text for this subtitle block")
    words: List[Dict[str, Any]] = Field(default_factory=list, description="Word-level timings within this block")


class ShortsScript(BaseModel):
    """
    Complete structured viral YouTube Shorts script with verified factual claims,
    retention-engineered narrative beats, and scene-by-scene visual camera directions.
    """
    topic: str = Field(..., description="Target video subject")
    language: str = Field(default="en", description="Script language code (e.g. 'en', 'si')")
    title: str = Field(
        ..., 
        description="High CTR YouTube Short title under 60 characters with an emoji"
    )
    hook: str = Field(
        ..., 
        description="Opening 0-3 second pattern-interrupt hook stopping the scroll immediately"
    )
    voiceover_text: str = Field(
        ..., 
        description="Natural, fast-paced voiceover script (~2.4 words/sec matching target duration)"
    )
    closing_cta: str = Field(
        default="What do you think? Drop your take in the comments.",
        description="Closing question or call to action driving viewer comments"
    )
    description: str = Field(
        ..., 
        description="Engaging YouTube description with keywords, sources, and hashtags"
    )
    tags: List[str] = Field(
        default_factory=lambda: ["#shorts", "#facts", "#viral"], 
        description="List of hashtags including #shorts"
    )
    target_duration_seconds: float = Field(
        default=50.0,
        description="Requested video duration in seconds (30.0 to 60.0)"
    )
    estimated_speaking_duration: float = Field(
        default=50.0,
        description="Calculated expected spoken duration based on word count (words / 2.4 wps)"
    )
    visual_segments: List[VisualSegment] = Field(
        ..., 
        description="List of 3 to 8 sequential visual scenes with camera movement and stock queries"
    )
    factual_claims: List[FactualClaim] = Field(
        default_factory=list,
        description="List of empirical claims verified with primary sources"
    )
    research_sources: List[Dict[str, str]] = Field(
        default_factory=list,
        description="List of source URLs and titles cited in the research"
    )
    subtitle_segments: List[SubtitleSegment] = Field(
        default_factory=list,
        description="Estimated or transcribed subtitle blocks"
    )

    # Backwards-compatibility alias for older code referencing 'estimated_duration_seconds'
    @property
    def estimated_duration_seconds(self) -> float:
        return self.estimated_speaking_duration

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Video title cannot be empty.")
        if len(clean) > 100:
            return clean[:97] + "..."
        return clean

    @field_validator("hook")
    @classmethod
    def validate_hook(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Opening hook cannot be empty.")
        # Reject generic clickbait cliches
        low = clean.lower()
        banned = ["did you know", "hey guys", "in this video", "today we are going to talk about", "welcome back to my channel"]
        for b in banned:
            if b in low:
                raise ValueError(f"Hook contains banned generic filler '{b}'. Must open with immediate insight.")
        return clean

    @field_validator("voiceover_text")
    @classmethod
    def validate_voiceover(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Voiceover script cannot be empty.")
        words = clean.split()
        if len(words) < 20:
            raise ValueError(f"Voiceover too short ({len(words)} words). Minimum 20 words required for a Short.")
        return clean

    @field_validator("visual_segments")
    @classmethod
    def validate_segments(cls, v: List[VisualSegment]) -> List[VisualSegment]:
        if not v or len(v) < 3:
            raise ValueError(f"A YouTube Short requires at least 3 visual scenes. Provided: {len(v)}.")
        return v

    @model_validator(mode="after")
    def compute_durations_and_sync(self) -> "ShortsScript":
        # Calculate expected speaking duration based on actual spoken word count
        # Professional voiceover pacing for high-retention Shorts is 2.3 - 2.5 words per second
        words_count = len(self.voiceover_text.split())
        self.estimated_speaking_duration = round(words_count / 2.4, 1)

        # Ensure visual segment duration sums match target duration
        if self.visual_segments:
            seg_count = len(self.visual_segments)
            calculated_seg_dur = round(self.estimated_speaking_duration / seg_count, 1)
            for i, seg in enumerate(self.visual_segments):
                seg.order = i + 1
                if not seg.pexels_keywords:
                    seg.pexels_keywords = [seg.search_query]
                if seg.approx_duration_sec <= 0:
                    seg.approx_duration_sec = calculated_seg_dur

        return self


class ScenePlanItem(BaseModel):
    """
    Detailed, timestamp-synchronized scene plan item defining exactly what must be visually
    depicted for a specific spoken narration segment, including full camera direction,
    AI generation prompts, visual validation criteria, and approval state tracking.
    """
    scene_id: str = Field(default="", description="Stable unique scene identifier (e.g. 'scene_01')")
    sequence_number: int = Field(default=1, description="1-indexed sequence order of the scene")
    scene_order: int = Field(default=1, description="Backward-compatible sequence order")
    narration_segment: str = Field(..., description="Exact voiceover sentence or phrase spoken during this scene")
    start_time: float = Field(..., description="Start timestamp in seconds")
    end_time: float = Field(..., description="End timestamp in seconds")
    duration: float = Field(..., description="Duration in seconds (end_time - start_time)")
    main_subject: str = Field(..., description="Dominant subject matter of this scene")
    action: str = Field(..., description="Physical or visual action occurring in the scene")
    setting: Optional[str] = Field(default=None, description="Physical setting or environment")
    historical_period: Optional[str] = Field(default=None, description="Historical period or era if relevant")
    camera_movement: str = Field(default="cinematic push-in", description="Camera movement direction")
    camera_angle: str = Field(default="eye-level", description="Camera angle (eye-level, low-angle, high-angle, Dutch tilt)")
    shot_type: str = Field(default="medium cinematic shot", description="Framing (macro close-up, medium shot, extreme wide)")
    lighting_atmosphere: str = Field(default="dramatic commercial lighting", description="Lighting, mood, and atmosphere")
    composition: str = Field(default="rule-of-thirds, 9:16 vertical composition", description="Framing and composition guidelines")
    visual_style: str = Field(default="photorealistic cinematic 4k", description="Visual aesthetic style")
    positive_prompt: str = Field(default="", description="Detailed positive generation prompt tailored for AI video models")
    negative_prompt: str = Field(default="", description="Negative constraints / prohibited visual elements string")
    negative_constraints: List[str] = Field(default_factory=list, description="Strictly forbidden visual elements that trigger rejection")
    continuity_info: str = Field(default="", description="Visual continuity details across preceding/subsequent scenes")
    expected_visual_elements: List[str] = Field(default_factory=list, description="Mandatory elements expected in generated footage")
    validation_criteria: str = Field(default="", description="Specific criteria required for automated visual validation")
    visual_description: str = Field(default="", description="Specific, vivid visual description of what appears on screen")
    required_objects: List[str] = Field(default_factory=list, description="Mandatory visual objects that must be present")
    required_brands: List[str] = Field(default_factory=list, description="Mandatory brand logos/elements if applicable")
    search_keywords: List[str] = Field(default_factory=list, description="Targeted keywords for visual asset retrieval")
    transition: str = Field(default="hard cut", description="Transition into this scene")
    on_screen_text: Optional[str] = Field(default=None, description="Key takeaway text overlay")
    selected_asset_path: Optional[str] = Field(default=None, description="Path to the approved visual asset file")
    selected_asset_source: Optional[str] = Field(default=None, description="Source tier or provider name")
    validation_status: Optional[str] = Field(default="pending", description="'passed', 'rejected', 'fallback', 'pending'")
    validation_confidence: Optional[float] = Field(default=None, description="Relevance confidence score (0.0 to 1.0)")
    validation_notes: Optional[str] = Field(default=None, description="Notes from the visual relevance validator")

    # State machine and human approval tracking
    generation_status: str = Field(
        default="DRAFT", 
        description="DRAFT, PLANNED, QUEUED, GENERATING, GENERATED, REVIEWED, APPROVED, REJECTED, FAILED, CANCELLED"
    )
    approval_status: str = Field(default="PENDING", description="PENDING, APPROVED, REJECTED")
    approval_notes: Optional[str] = Field(default=None, description="Reviewer feedback or rejection reason")
    prompt_version: int = Field(default=1, description="Version of the visual prompt, incremented upon editing")
    clip_replacement_history: List[Dict[str, Any]] = Field(default_factory=list, description="Log of clip replacements")

    @model_validator(mode="after")
    def sync_scene_identifiers(self) -> "ScenePlanItem":
        # Keep sequence_number and scene_order in sync
        if self.sequence_number and not self.scene_order:
            self.scene_order = self.sequence_number
        elif self.scene_order and not self.sequence_number:
            self.sequence_number = self.scene_order
        else:
            self.sequence_number = self.scene_order

        # Auto-assign scene_id if blank
        if not self.scene_id:
            self.scene_id = f"scene_{self.sequence_number:02d}"

        # Sync duration
        if self.duration <= 0 and self.end_time > self.start_time:
            self.duration = round(self.end_time - self.start_time, 2)

        # Fallback visual_description from positive_prompt or vice versa
        if not self.visual_description and self.positive_prompt:
            self.visual_description = self.positive_prompt
        elif not self.positive_prompt and self.visual_description:
            self.positive_prompt = self.visual_description

        # Sync negative_prompt and negative_constraints
        if not self.negative_prompt and self.negative_constraints:
            self.negative_prompt = ", ".join(self.negative_constraints)
        elif self.negative_prompt and not self.negative_constraints:
            self.negative_constraints = [c.strip() for c in self.negative_prompt.split(",") if c.strip()]

        return self


class TimestampedScenePlan(BaseModel):
    """
    Structured scene plan generated before rendering, validated against voiceover timestamps.
    """
    topic: str = Field(..., description="Video topic")
    total_scenes: int = Field(..., description="Total count of scenes")
    total_duration: float = Field(..., description="Total spoken duration matching voiceover audio")
    scenes: List[ScenePlanItem] = Field(..., description="Ordered list of timestamped scenes")
    all_approved: bool = Field(default=False, description="True only when all scenes have approval_status=='APPROVED'")

    @model_validator(mode="after")
    def update_approval_summary(self) -> "TimestampedScenePlan":
        if self.scenes:
            self.all_approved = all(s.approval_status == "APPROVED" for s in self.scenes)
            self.total_scenes = len(self.scenes)
        return self


class AssetRejectionRecord(BaseModel):
    """Record of an asset candidate rejected by the visual relevance validator."""
    scene_order: int
    candidate_source: str
    candidate_identifier: str
    rejection_reason: str
    confidence_score: float
    detected_dominant_subject: str


class ValidationResult(BaseModel):
    """Result of visual relevance validation on a candidate asset."""
    is_relevant: bool
    confidence: float
    rejection_reason: str = ""
    dominant_subject: str = ""
    detected_forbidden_items: List[str] = Field(default_factory=list)


class QualityControlReport(BaseModel):
    """Complete quality control and asset provenance report for a rendered video."""
    job_id: str
    topic: str
    total_scenes: int
    passed_scenes: int
    rejections: List[AssetRejectionRecord] = Field(default_factory=list)
    scene_asset_sources: Dict[int, str] = Field(default_factory=dict)
    frame_inspection: Optional[Dict[str, Any]] = None
    overall_pass: bool = False

