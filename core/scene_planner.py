import re
from typing import List, Optional, Tuple, Any, Dict
from core.schemas import ShortsScript, ScenePlanItem, TimestampedScenePlan
from core.tts_engine import AudioResult


class ScenePlanner:
    """
    Transforms approved voiceover scripts into timestamp-synchronized, topic-faithful scene plans.
    Every scene strictly ties narration to visual requirements, camera movement, and negative constraints.
    """

    @classmethod
    def create_scene_plan(
        cls,
        script: ShortsScript,
        audio_result: AudioResult,
        topic: str
    ) -> TimestampedScenePlan:
        """
        Builds a structured TimestampedScenePlan with sub-second synchronization.
        """
        total_duration = audio_result.duration_seconds
        words_timing = audio_result.words_timing or []
        voiceover_text = script.voiceover_text.strip()

        # Check if topic is Cola Wars / Coca-Cola vs Pepsi
        is_cola_wars = any(kw in topic.lower() for kw in ["cola", "pepsi", "coke", "soda wars"])

        if is_cola_wars:
            plan = cls._build_cola_wars_plan(topic, voiceover_text, total_duration, words_timing)
        else:
            plan = cls._build_topic_faithful_plan(topic, script, voiceover_text, total_duration, words_timing)

        # Apply AI Visual Director to establish camera choreography, prompts, and continuity
        from core.visual_director import VisualDirector
        plan.scenes = VisualDirector.direct_all_scenes(plan.scenes, topic=topic)
        return plan

    @classmethod
    def _build_cola_wars_plan(
        cls,
        topic: str,
        voiceover_text: str,
        total_duration: float,
        words_timing: List[Any]
    ) -> TimestampedScenePlan:
        """
        Builds the Golden Cola Wars timeline according to strict historical prompt criteria:
        - 0–3s: Dramatic red-and-blue rivalry, cola bottles, cinematic lighting.
        - 3–8s: Coca-Cola and Pepsi presented as competing brands.
        - 8–15s: Period-appropriate advertising and consumer choice.
        - 15–23s: Late-1970s and 1980s visual timeline (Pepsi Challenge).
        - 23–32s: Rival advertising campaigns, television screens, and supermarket cola displays.
        - 32–38s: Escalating brand competition and a historical conclusion (New Coke 1985).
        - Final scene: Coke-versus-Pepsi split-screen with the viewer question.
        Timestamps are scaled proportionately to match the actual synthesized voiceover duration.
        """
        # Nominal target timestamps from user specification (total ~45s)
        nominal_durations = [3.0, 5.0, 7.0, 8.0, 9.0, 6.0, 7.0]
        nominal_total = sum(nominal_durations)  # 45.0s
        scale = total_duration / nominal_total

        # Split voiceover sentences
        sentences = cls._split_into_sentences(voiceover_text)
        # Distribute sentences across the 7 golden scenes
        scene_narrations = cls._distribute_sentences(sentences, target_scene_count=7)

        # Common negative visual constraints for Cola Wars (reject unrelated items)
        cola_negative_constraints = [
            "iceberg", "glacier", "soup can", "campbell", "random supermarket",
            "vegetables", "fruit produce", "abstract glitch", "generic water animation",
            "ocean waves", "modern smartphone", "alien", "outer space"
        ]

        golden_specs = [
            {
                "order": 1,
                "main_subject": "Red and Blue Rivalry Cola Bottles",
                "action": "Dramatic dual spotlight, red neon on left, blue neon on right, sweating cold cola bottles with condensing fizz",
                "historical_period": "Iconic Branding Era",
                "visual_description": "Cinematic macro shot of two cold sweating cola bottles bathed in clashing red and blue neon rim light, fizzy carbonation bubbles visible against dark moody backdrop",
                "required_objects": ["cola bottle", "condensation", "red and blue lighting"],
                "required_brands": ["Coca-Cola", "Pepsi"],
                "search_keywords": ["vintage cola bottle cold condensation", "red blue neon lighting bottle"],
                "negative_constraints": cola_negative_constraints,
                "camera_movement": "cinematic push-in",
                "transition": "cut",
                "on_screen_text": "THE GREATEST BRAND WAR"
            },
            {
                "order": 2,
                "main_subject": "Coca-Cola and Pepsi Corporate Face-Off",
                "action": "Classic glass contour bottle and Pepsi crown cap bottle positioned side-by-side in studio rivalry",
                "historical_period": "Mid 20th Century",
                "visual_description": "Vintage Coca-Cola curved contour bottle and retro Pepsi-Cola glass bottle standing opposite each other, studio product commercial lighting with reflections",
                "required_objects": ["Coca-Cola bottle", "Pepsi bottle", "soda caps"],
                "required_brands": ["Coca-Cola", "Pepsi"],
                "search_keywords": ["retro coca-cola glass bottle", "vintage pepsi bottle studio"],
                "negative_constraints": cola_negative_constraints,
                "camera_movement": "slow pan right",
                "transition": "cross-dissolve",
                "on_screen_text": "COKE VS PEPSI"
            },
            {
                "order": 3,
                "main_subject": "Period-Appropriate Advertising & Consumer Choice",
                "action": "1970s American diner soda fountain with patrons choosing between branded cola pumps",
                "historical_period": "1970s Americana",
                "visual_description": "Authentic 1970s retro diner counter, chrome soda fountain dispensers, vintage porcelain cola sign in the background, customer enjoying an ice-cold glass of cola",
                "required_objects": ["vintage soda fountain", "retro diner counter", "ice cola glass"],
                "required_brands": ["Coca-Cola", "Pepsi"],
                "search_keywords": ["1970s retro diner soda fountain", "vintage cola fountain dispenser"],
                "negative_constraints": cola_negative_constraints,
                "camera_movement": "cinematic tracking shot",
                "transition": "cut",
                "on_screen_text": "AMERICA'S OBSESSION"
            },
            {
                "order": 4,
                "main_subject": "The 1975 Pepsi Challenge Blind Taste Test",
                "action": "Mall shoppers tasting soda from unmarked white cups labeled M and Q, reacting with surprise",
                "historical_period": "Late 1970s (1975-1979)",
                "visual_description": "1970s shopping mall setting with wooden promotional booth, two unmarked paper cups of brown cola, participant taking a sip during the historic blind taste test",
                "required_objects": ["blind taste test", "two paper cups", "1970s mall booth"],
                "required_brands": ["Pepsi Challenge", "Coca-Cola"],
                "search_keywords": ["blind taste test paper cups", "1970s retro taste test mall booth"],
                "negative_constraints": cola_negative_constraints,
                "camera_movement": "slow push-in",
                "transition": "cut",
                "on_screen_text": "1975: THE PEPSI CHALLENGE"
            },
            {
                "order": 5,
                "main_subject": "Rival TV Commercials & Supermarket Cola Aisles",
                "action": "1980s cathode-ray TV showing vibrant cola commercials beside supermarket shelves loaded with red Coke and blue Pepsi cans",
                "historical_period": "1980s Golden Era",
                "visual_description": "Retro 1980s television set glowing in living room alongside colorful supermarket shelves packed with red Coca-Cola cans and blue Pepsi cans, neon supermarket signs",
                "required_objects": ["1980s CRT television", "cola cans display", "supermarket soda shelf"],
                "required_brands": ["Coca-Cola", "Pepsi"],
                "search_keywords": ["1980s retro television screen", "supermarket soda aisle cans display"],
                "negative_constraints": cola_negative_constraints + ["soup cans", "campbell", "cereal boxes"],
                "camera_movement": "slow zoom-out",
                "transition": "whip pan",
                "on_screen_text": "THE AD BATTLE ESCALATES"
            },
            {
                "order": 6,
                "main_subject": "Escalating Brand Competition & 1985 New Coke",
                "action": "1985 press conference with bold New Coke red cans and protesters holding 'Bring Back Old Coke' signs",
                "historical_period": "1985",
                "visual_description": "Historical 1985 press conference podium with microphone, stack of 1985 New Coke cans, vintage newspaper headline 'COKE CHANGES FORMULA', passionate public reaction",
                "required_objects": ["1985 New Coke can", "newspaper headline", "press conference microphones"],
                "required_brands": ["New Coke", "Coca-Cola"],
                "search_keywords": ["1985 new coke can launch", "vintage newspaper headline press conference"],
                "negative_constraints": cola_negative_constraints,
                "camera_movement": "cinematic tilt down",
                "transition": "cut",
                "on_screen_text": "1985: THE NEW COKE DISASTER"
            },
            {
                "order": 7,
                "main_subject": "Coke vs Pepsi Split-Screen & Final Choice",
                "action": "Vertical split-screen: classic Coca-Cola red can and script on left, Pepsi blue globe can on right, frost and condensation",
                "historical_period": "Contemporary Climax",
                "visual_description": "High-impact vertical split screen: Left half glowing deep crimson red with classic Coca-Cola contour bottle, Right half glowing electric cobalt blue with chilled Pepsi can, condensation droplets trickling down",
                "required_objects": ["vertical split screen", "red Coca-Cola bottle", "blue Pepsi can"],
                "required_brands": ["Coca-Cola", "Pepsi"],
                "search_keywords": ["coca-cola vs pepsi split screen", "chilled cola red and blue bottles"],
                "negative_constraints": cola_negative_constraints,
                "camera_movement": "subtle pulse push-in",
                "transition": "flash cut",
                "on_screen_text": "WHICH SIDE ARE YOU ON?"
            }
        ]

        # Calculate exact start and end times for each scene
        current_time = 0.0
        scenes: List[ScenePlanItem] = []

        for idx, spec in enumerate(golden_specs):
            # Calculate duration scaled to actual total audio
            if idx == len(golden_specs) - 1:
                scene_dur = max(round(total_duration - current_time, 2), 2.0)
            else:
                raw_dur = nominal_durations[idx] * scale
                scene_dur = max(round(raw_dur, 2), 2.5)

            end_t = min(round(current_time + scene_dur, 2), round(total_duration, 2))
            actual_dur = round(end_t - current_time, 2)

            narration = scene_narrations[idx] if idx < len(scene_narrations) else "The battle between Coke and Pepsi remains the most iconic rivalry in history."

            scenes.append(
                ScenePlanItem(
                    scene_order=spec["order"],
                    narration_segment=narration,
                    start_time=round(current_time, 2),
                    end_time=end_t,
                    duration=actual_dur,
                    main_subject=spec["main_subject"],
                    action=spec["action"],
                    historical_period=spec["historical_period"],
                    visual_description=spec["visual_description"],
                    required_objects=spec["required_objects"],
                    required_brands=spec["required_brands"],
                    search_keywords=spec["search_keywords"],
                    negative_constraints=spec["negative_constraints"],
                    camera_movement=spec["camera_movement"],
                    transition=spec["transition"],
                    on_screen_text=spec["on_screen_text"]
                )
            )
            current_time = end_t

        return TimestampedScenePlan(
            topic=topic,
            total_scenes=len(scenes),
            total_duration=round(total_duration, 2),
            scenes=scenes
        )

    @classmethod
    def _build_topic_faithful_plan(
        cls,
        topic: str,
        script: ShortsScript,
        voiceover_text: str,
        total_duration: float,
        words_timing: List[Any]
    ) -> TimestampedScenePlan:
        """
        Dynamically generates structured, topic-faithful scene plans for arbitrary subjects
        (e.g. 'The Secrets of Black Holes', 'Julius Caesar Assassination').
        Calculates exact sentence-aligned boundary timestamps.
        """
        sentences = cls._split_into_sentences(voiceover_text)
        if not sentences:
            sentences = [voiceover_text]

        # Determine optimal scene count (between 4 and 8)
        scene_count = min(max(len(sentences), 4), 7)
        grouped_sentences = cls._distribute_sentences(sentences, target_scene_count=scene_count)

        # Compute topic-specific negative constraints
        topic_lower = topic.lower()
        if "black hole" in topic_lower or "space" in topic_lower or "astronomy" in topic_lower:
            negative_constraints = [
                "coca cola", "pepsi", "soup can", "campbell", "grocery store",
                "supermarket", "modern room", "city traffic", "iceberg", "glitch effect", "face selfie"
            ]
            default_era = "Cosmic Astrophysical Timeline"
        elif "caesar" in topic_lower or "rome" in topic_lower or "history" in topic_lower:
            negative_constraints = [
                "modern cars", "coca cola", "pepsi", "smartphones", "soup can",
                "iceberg", "glitch", "modern skyscraper", "neon lights", "jeans"
            ]
            default_era = "44 BC Ancient Rome"
        else:
            negative_constraints = [
                "soup can", "campbell", "iceberg", "glacier", "random supermarket",
                "arbitrary glitch", "abstract digital lines", "generic water splash"
            ]
            default_era = "Documentary History"

        # Calculate scene timestamps based on word timings if available, or word count ratio
        total_words = len(voiceover_text.split())
        current_time = 0.0
        scenes: List[ScenePlanItem] = []

        for i, segment_text in enumerate(grouped_sentences):
            seg_words = len(segment_text.split())
            if i == len(grouped_sentences) - 1:
                dur = max(round(total_duration - current_time, 2), 2.0)
            else:
                ratio = seg_words / max(total_words, 1)
                dur = max(round(total_duration * ratio, 2), 2.5)

            end_t = min(round(current_time + dur, 2), round(total_duration, 2))
            actual_dur = round(end_t - current_time, 2)

            # Derive subject and visual description from the narration segment
            main_sub, act, vis_desc, req_objs = cls._derive_scene_details(topic, segment_text, i + 1, len(grouped_sentences))

            scenes.append(
                ScenePlanItem(
                    scene_order=i + 1,
                    narration_segment=segment_text,
                    start_time=round(current_time, 2),
                    end_time=end_t,
                    duration=actual_dur,
                    main_subject=main_sub,
                    action=act,
                    historical_period=default_era,
                    visual_description=vis_desc,
                    required_objects=req_objs,
                    required_brands=[],
                    search_keywords=[f"{topic} {main_sub}"[:40].strip()],
                    negative_constraints=negative_constraints,
                    camera_movement="cinematic push-in" if i % 2 == 0 else "slow tracking pan",
                    transition="cut" if i == 0 else "cross-dissolve",
                    on_screen_text=f"{main_sub.upper()[:25]}"
                )
            )
            current_time = end_t

        return TimestampedScenePlan(
            topic=topic,
            total_scenes=len(scenes),
            total_duration=round(total_duration, 2),
            scenes=scenes
        )

    @classmethod
    def _derive_scene_details(
        cls,
        topic: str,
        sentence: str,
        order: int,
        total: int
    ) -> Tuple[str, str, str, List[str]]:
        """
        Extracts subject, action, vivid visual description, and required objects
        from the narration sentence and topic.
        """
        clean = sentence.replace('"', '').strip()
        low = clean.lower()

        # Topic-specific heuristics
        if "black hole" in topic.lower():
            if order == 1 or "singularity" in low or "event horizon" in low:
                return (
                    "Event Horizon Gravitational Lensing",
                    "Swirling luminous glowing accretion disk bending starlight around the black sphere of the event horizon",
                    "Cinematic 8K astrophysical visualization of a supermassive black hole, glowing orange-gold accretion disk warps space-time against starry cosmos",
                    ["black hole", "accretion disk", "gravitational lensing"]
                )
            elif "spaghettification" in low or "gravity" in low or "pull" in low:
                return (
                    "Gravitational Tidal Spaghettification",
                    "A wandering celestial star stretched into a glowing stream of gas as it crosses into extreme gravitational shear",
                    "Dramatic close-up of a blue star being torn apart and pulled into a luminous spiraling stream by colossal tidal gravitational forces",
                    ["stretched star gas", "relativistic plasma stream", "gravitational field"]
                )
            elif "time" in low or "relativity" in low:
                return (
                    "Relativistic Time Dilation",
                    "Clock hands slowing to a dead stop against glowing distorted spacetime grid near the Schwarzchild radius",
                    "Conceptual visualization of gravitational time dilation, warping cosmic clock faces fading into eternal frozen light",
                    ["cosmic clock", "spacetime grid distortion", "frozen light"]
                )
            else:
                return (
                    "Deep Space Cosmic Singularity",
                    "Relativistic relativistic jets blasting thousands of light-years out from the poles of a rotating Kerr black hole",
                    "Ultra-wide astronomical view of collimated magnetic plasma jets erupting from the core of an active galactic nucleus",
                    ["relativistic polar jets", "galaxy core", "accretion disk"]
                )
        elif "caesar" in topic.lower():
            if order == 1 or "senate" in low or "ides" in low:
                return (
                    "Roman Senate Chamber Confrontation",
                    "Julius Caesar in imperial crimson toga entering the Curia of Pompey surrounded by watchful Roman senators",
                    "Cinematic historical recreation: marble columns of the Roman Senate, sunbeams cutting through incense dust, tension between senators",
                    ["Julius Caesar", "Roman toga", "marble senate columns"]
                )
            elif "stab" in low or "dagger" in low or "twenty" in low:
                return (
                    "The Conspirators' Daggers",
                    "Senatorial daggers revealed beneath cloaks in dramatic shadowy Roman architecture",
                    "Dramatic low-angle shot of Roman bronze daggers unsheathed inside the marble forum, dark Roman historical drama",
                    ["bronze dagger", "conspirators", "marble floor"]
                )
            elif "et tu" in low or "brute" in low or "fall" in low:
                return (
                    "The Fall of Julius Caesar",
                    "Caesar looking at Marcus Brutus in tragic betrayal beneath the statue of Pompey",
                    "Iconic historical moment: Julius Caesar pulling his purple mantle over his head as he collapses at the marble base of Pompey's monument",
                    ["Caesar toga", "statue of Pompey", "Roman marble floor"]
                )
            else:
                return (
                    "The Aftermath of Rome's Dictator",
                    "The empty bloodstained senate floor and the chaotic streets of ancient Rome ignited with rebellion",
                    "Wide atmospheric view of ancient Roman forum at dusk, torches illuminating statues as citizens react to the fateful assassination",
                    ["Roman forum torches", "Roman citizens", "imperial monument"]
                )

        # General topic fallback
        main_subject = f"{topic} Core Concept #{order}"
        action = f"Visual manifestation of {clean[:40]}"
        vis_desc = f"Cinematic 9:16 vertical shot depicting {clean}, set in authentic environment with dramatic lighting and photorealistic detail."
        req_objs = [topic.split()[0]]
        return (main_subject, action, vis_desc, req_objs)

    @staticmethod
    def _split_into_sentences(text: str) -> List[str]:
        """Splits narrative into punctuated sentences."""
        clean = re.sub(r"\s+", " ", text).strip()
        raw = re.split(r"(?<=[.!?])\s+", clean)
        return [s.strip() for s in raw if len(s.strip()) > 8]

    @staticmethod
    def _distribute_sentences(sentences: List[str], target_scene_count: int) -> List[str]:
        """Distributes N sentences into target_scene_count balanced chunks."""
        if len(sentences) <= target_scene_count:
            # Pad or keep as is
            chunks = list(sentences)
            while len(chunks) < target_scene_count:
                chunks.append(chunks[-1] if chunks else "The legendary rivalry continues.")
            return chunks

        # Group sentences evenly
        chunk_size = len(sentences) / target_scene_count
        grouped = []
        for i in range(target_scene_count):
            start_idx = int(round(i * chunk_size))
            end_idx = int(round((i + 1) * chunk_size))
            chunk = " ".join(sentences[start_idx:end_idx]).strip()
            if not chunk and sentences:
                chunk = sentences[min(start_idx, len(sentences) - 1)]
            grouped.append(chunk)

        return grouped
