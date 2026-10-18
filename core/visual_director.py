import re
from typing import List, Optional, Dict, Any
from core.schemas import ScenePlanItem
from core.config import AppConfig


class VisualDirector:
    """
    AI Visual Director that produces scene-specific visual plans, camera choreographies,
    and video-generation prompts, ensuring variety, continuity, and topic fidelity.
    """

    SHOT_TYPES = [
        "dramatic macro close-up",
        "eye-level medium shot",
        "cinematic low-angle hero shot",
        "high-angle dynamic wide shot",
        "tight detail shot",
        "dynamic tracking shot",
        "hero centered portrait"
    ]

    CAMERA_MOVEMENTS = [
        "cinematic slow push-in",
        "smooth tracking right",
        "subtle orbit around subject",
        "dramatic fast push-in",
        "slow cinematic tilt down",
        "gentle pull-back reveal",
        "intense steady push-in"
    ]

    CAMERA_ANGLES = [
        "low-angle heroic",
        "eye-level direct",
        "high-angle dramatic",
        "macro close-up 45-degree",
        "Dutch angle dynamic",
        "straight-on symmetrical"
    ]

    @classmethod
    def direct_scene(
        cls,
        scene: ScenePlanItem,
        topic: str,
        scene_index: int = 0,
        total_scenes: int = 1,
        previous_scene: Optional[ScenePlanItem] = None
    ) -> ScenePlanItem:
        """
        Enriches a ScenePlanItem with director-level camera framing, lighting,
        continuity constraints, positive AI video generation prompt, and negative constraints.
        """
        # 1. Determine shot variety based on sequence index
        shot_idx = scene_index % len(cls.SHOT_TYPES)
        mov_idx = scene_index % len(cls.CAMERA_MOVEMENTS)
        ang_idx = scene_index % len(cls.CAMERA_ANGLES)

        if not scene.shot_type or scene.shot_type == "medium cinematic shot":
            scene.shot_type = cls.SHOT_TYPES[shot_idx]
        if not scene.camera_movement or scene.camera_movement == "cinematic push-in":
            scene.camera_movement = cls.CAMERA_MOVEMENTS[mov_idx]
        if not scene.camera_angle or scene.camera_angle == "eye-level":
            scene.camera_angle = cls.CAMERA_ANGLES[ang_idx]

        # 2. Lighting and atmosphere based on topic domain
        low_topic = topic.lower()
        if any(k in low_topic for k in ["space", "black hole", "galaxy", "astronomy", "star", "physics"]):
            scene.lighting_atmosphere = "deep cosmic rim lighting, gravitational accretion disk glow, high dynamic range, intense starfield backdrop"
            scene.visual_style = "hyper-realistic astrophysical simulation, scientific documentary quality, 8k resolution"
        elif any(k in low_topic for k in ["cola", "pepsi", "coke", "soda", "brand"]):
            scene.lighting_atmosphere = "high-end commercial studio lighting, vibrant red and cobalt blue neon contrast, glistening condensation droplets"
            scene.visual_style = "hyper-detailed commercial product cinematography, 35mm film aesthetic, razor-sharp focus"
        elif any(k in low_topic for k in ["rome", "caesar", "ancient", "history", "war", "empire"]):
            scene.lighting_atmosphere = "natural Mediterranean golden hour sunlight through Roman marble columns, flickering torchlight, dramatic chiaroscuro shadows"
            scene.visual_style = "prestige historical epic cinematography, authentic textured period fabrics, Panavision anamorphic lens"
        else:
            scene.lighting_atmosphere = "cinematic volumetric lighting, strong key-to-fill contrast, immersive atmospheric haze"
            scene.visual_style = "photorealistic cinematic 4k, crisp texture, award-winning cinematography"

        # 3. Composition
        scene.composition = f"vertical 9:16 aspect ratio, subject prominently centered or in lower third, optimized for mobile viewing, {scene.camera_angle}"

        # 4. Synthesize Rich Positive Generation Prompt
        # Avoid generic prompts; tie directly to subject, action, lighting, and camera motion
        positive_prompt_parts = [
            f"A vertical 9:16 video of {scene.main_subject}",
            f"{scene.action}",
            f"Framing: {scene.shot_type}, camera doing a {scene.camera_movement}",
            f"Environment: {scene.setting or scene.historical_period or 'cinematic environment'}",
            f"Lighting: {scene.lighting_atmosphere}",
            f"Aesthetic: {scene.visual_style}, ultra-sharp details, fluid realistic motion, 60fps cinematic feel"
        ]
        scene.positive_prompt = ". ".join([p.strip() for p in positive_prompt_parts if p.strip()])

        # 5. Build Negative Constraints & Prohibited Elements
        # Always forbid low-quality AI artifacts, watermarks, and visible subtitles
        base_negatives = [
            "blurry", "low quality", "distorted text", "watermarks", "subtitles burned into video",
            "glitch artifacts", "mutated hands", "bad anatomy", "overexposed", "plastic skin",
            "choppy motion", "static still frame"
        ]

        # Merge with existing scene negative constraints
        merged_negatives = list(dict.fromkeys(scene.negative_constraints + base_negatives))
        scene.negative_constraints = merged_negatives
        scene.negative_prompt = ", ".join(merged_negatives)

        # 6. Continuity Information
        if previous_scene:
            scene.continuity_info = (
                f"Maintains visual style continuity with Scene #{previous_scene.sequence_number}. "
                f"Consistent color grading ({scene.visual_style}) and coherent subject portrayal."
            )
        else:
            scene.continuity_info = f"Opening master scene establishing visual tone and color palette for {topic}."

        # 7. Expected Elements & Validation Criteria
        if not scene.expected_visual_elements:
            scene.expected_visual_elements = [scene.main_subject] + scene.required_objects
        
        scene.validation_criteria = (
            f"Must visually depict {scene.main_subject} performing {scene.action}. "
            f"Must strictly reject any frame containing: {', '.join(scene.negative_constraints[:5])}."
        )

        # 8. State machine initial state
        scene.generation_status = "PLANNED"
        if not scene.approval_status:
            scene.approval_status = "PENDING"

        return scene

    @classmethod
    def direct_all_scenes(
        cls,
        scenes: List[ScenePlanItem],
        topic: str
    ) -> List[ScenePlanItem]:
        """Directs and enriches all scenes in sequence, establishing visual continuity."""
        directed_scenes: List[ScenePlanItem] = []
        prev = None
        for i, s in enumerate(scenes):
            directed = cls.direct_scene(s, topic=topic, scene_index=i, total_scenes=len(scenes), previous_scene=prev)
            directed_scenes.append(directed)
            prev = directed
        return directed_scenes
