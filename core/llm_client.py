import json
import re
from typing import Type, TypeVar, Optional
from pydantic import BaseModel
from core.config import AppConfig

T = TypeVar("T", bound=BaseModel)

class LLMClient:
    """Universal LLM client supporting Gemini and OpenAI with structured JSON outputs."""

    def __init__(self, provider: Optional[str] = None):
        self.provider = (provider or AppConfig.DEFAULT_LLM_PROVIDER).lower()

    def generate_structured(
        self, 
        prompt: str, 
        system_instruction: str, 
        schema_class: Type[T]
    ) -> T:
        """
        Dispatches request to the configured LLM provider and returns a validated Pydantic model instance.
        """
        if self.provider == "gemini":
            return self._call_gemini(prompt, system_instruction, schema_class)
        elif self.provider == "openai":
            return self._call_openai(prompt, system_instruction, schema_class)
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}. Use 'gemini' or 'openai'.")

    def _call_gemini(
        self, 
        prompt: str, 
        system_instruction: str, 
        schema_class: Type[T]
    ) -> T:
        """Call Google Gemini using google.genai Client with structured JSON response."""
        gemini_key = AppConfig.get_gemini_key()
        if not gemini_key:
            raise ValueError(
                "GEMINI_API_KEY is not set. Please add it to your .env file or choose OpenAI."
            )

        try:
            from google import genai
            from google.genai import types
        except ImportError:
            raise ImportError(
                "google-genai package is not installed. Run `pip install google-genai`."
            )

        client = genai.Client(api_key=gemini_key)
        
        # Candidate models to try in order of capability and availability
        candidate_models = [
            "gemini-2.5-pro",
            "gemini-1.5-pro",
            "gemini-3.6-flash",
            "gemini-3.5-flash",
            "gemini-flash-latest",
            AppConfig.get_gemini_model(),
        ]

        last_error = None
        for m_name in candidate_models:
            if not m_name:
                continue
            for use_mime in [True, False]:
                try:
                    kwargs = {"temperature": 0.7}
                    if system_instruction:
                        kwargs["system_instruction"] = system_instruction
                    if use_mime:
                        kwargs["response_mime_type"] = "application/json"
                    config = types.GenerateContentConfig(**kwargs)
                    response = client.models.generate_content(
                        model=m_name,
                        contents=prompt,
                        config=config
                    )
                    raw_text = response.text.strip()
                    return self._parse_json_to_model(raw_text, schema_class)
                except Exception as e:
                    last_error = e
                    continue

        raise RuntimeError(f"All Gemini models failed: {last_error}")

    def _call_openai(
        self, 
        prompt: str, 
        system_instruction: str, 
        schema_class: Type[T]
    ) -> T:
        """Call OpenAI using structured outputs."""
        openai_key = AppConfig.get_openai_key()
        if not openai_key:
            raise ValueError(
                "OPENAI_API_KEY is not set. Please add it to your .env file or choose Gemini."
            )

        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai package is not installed. Run `pip install openai`.")

        client = OpenAI(api_key=openai_key)

        completion = client.beta.chat.completions.parse(
            model=AppConfig.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt},
            ],
            response_format=schema_class,
            temperature=0.7,
        )

        result = completion.choices[0].message.parsed
        if result is None:
            raise RuntimeError("OpenAI returned empty or unparseable structured response.")
        return result

    @staticmethod
    def _parse_json_to_model(raw_json: str, schema_class: Type[T]) -> T:
        """Cleans markdown JSON blocks and parses into the specified Pydantic schema."""
        cleaned = raw_json.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.MULTILINE)
            cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE).strip()

        try:
            data = json.loads(cleaned)
        except Exception:
            m = re.search(r"(\{.*\})", cleaned, re.DOTALL)
            if m:
                data = json.loads(m.group(1))
            else:
                raise ValueError(f"Could not parse valid JSON from: {cleaned[:300]}")

        # Normalize visual_segments so any LLM variation maps to VisualSegment
        if isinstance(data, dict) and "visual_segments" in data and isinstance(data["visual_segments"], list):
            norm_segs = []
            for i, seg in enumerate(data["visual_segments"]):
                if isinstance(seg, dict):
                    raw_q = (
                        seg.get("search_query")
                        or seg.get("query")
                        or seg.get("keyword")
                        or (seg.get("key_visual_elements")[0] if isinstance(seg.get("key_visual_elements"), list) and seg.get("key_visual_elements") else None)
                        or seg.get("title")
                        or seg.get("prompt")
                        or seg.get("scene_description")
                        or seg.get("description")
                        or "cinematic dramatic"
                    )
                    # Clean query: take concise 2-4 keywords
                    clean_q_words = [w for w in str(raw_q).replace("-", " ").replace("_", " ").split() if len(w) > 2]
                    q = " ".join(clean_q_words[:4]) if clean_q_words else "cinematic footage"
                    desc = seg.get("scene_description") or seg.get("description") or str(raw_q)
                    dur = float(seg.get("approx_duration_sec") or seg.get("duration") or 7.0)
                    norm_segs.append({
                        "order": i + 1,
                        "search_query": q,
                        "scene_description": str(desc),
                        "approx_duration_sec": dur
                    })
                elif isinstance(seg, str):
                    clean_q_words = [w for w in str(seg).split() if len(w) > 2]
                    q = " ".join(clean_q_words[:4]) if clean_q_words else str(seg)
                    norm_segs.append({
                        "order": i + 1,
                        "search_query": q,
                        "scene_description": seg,
                        "approx_duration_sec": 7.0
                    })
            data["visual_segments"] = norm_segs

        # Ensure top-level fields have fallbacks
        if "title" not in data or not data["title"]:
            data["title"] = "Untold Secrets ⚡"
        if "hook" not in data or not data["hook"]:
            data["hook"] = "You were never supposed to know this."
        if "voiceover_text" not in data or not data["voiceover_text"]:
            data["voiceover_text"] = data.get("script") or data.get("text") or data["hook"]
        if "description" not in data:
            data["description"] = f"{data['title']} #shorts #viral"
        if "tags" not in data or not data["tags"]:
            data["tags"] = ["#shorts", "#viral"]
        if "estimated_duration_seconds" not in data:
            data["estimated_duration_seconds"] = 50.0

        return schema_class.model_validate(data)
