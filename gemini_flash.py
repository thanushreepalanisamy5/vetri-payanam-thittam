"""Step 1 of the pipeline: a structured 5-panel comic outline using Gemini Flash."""
import json
import re

from app import config
from app.gemini_client import GeminiError, generate_text

REQUIRED_KEYS = ("panel", "title", "scene_description", "image_prompt")


def _build_prompt(user_prompt: str) -> str:
    n = config.NUM_PANELS
    return f"""
You are a professional AI comic planner.

Your task is to generate a *strictly formatted* JSON array containing exactly {n} panel descriptions for a comic based on the story idea below.

STORY: "{user_prompt}"

Each JSON object must include:
- "panel" (integer, starting at 1)
- "title" (string)
- "scene_description" (string, 1-2 sentences)
- "image_prompt" (string)

Rules for "image_prompt":
- It is sent to Stable Diffusion, so keep it under 40 words and make it purely visual.
- Put the art style first, then describe the main character's appearance (keep it identical in every panel), the action and the setting.
- Do not include speech, text, captions or panel numbers in the image prompt.

Respond ONLY in this valid JSON format, without any explanations or markdown:
[
  {{
    "panel": 1,
    "title": "Title here",
    "scene_description": "Scene description here",
    "image_prompt": "Image prompt for Stable Diffusion"
  }}
]
""".strip()


def _extract_json(text: str):
    """Parse JSON even if the model wrapped it in markdown fences or added chatter."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.I).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("["), cleaned.rfind("]")
        if start != -1 and end > start:
            return json.loads(cleaned[start : end + 1])
        raise


def parse_outline(raw_text: str) -> list:
    """Turn raw model text into a validated list of panel dicts."""
    try:
        data = _extract_json(raw_text)
    except json.JSONDecodeError as exc:
        raise GeminiError(f"Could not parse the outline returned by Gemini as JSON: {exc}") from exc

    if isinstance(data, dict):  # tolerate {"panels": [...]}
        data = data.get("panels") or next((v for v in data.values() if isinstance(v, list)), data)
    if not isinstance(data, list) or not data:
        raise GeminiError("Gemini outline was not a non-empty list of panels.")

    panels = []
    for i, item in enumerate(data[: config.NUM_PANELS], start=1):
        if not isinstance(item, dict) or not all(k in item for k in REQUIRED_KEYS):
            raise GeminiError(f"Invalid panel format or missing keys in panel {i}: {item}")
        panels.append(
            {
                "panel": i,  # renumber so panels are always 1..N
                "title": str(item["title"]).strip() or f"Panel {i}",
                "scene_description": str(item["scene_description"]).strip(),
                "image_prompt": str(item["image_prompt"]).strip(),
            }
        )
    return panels


def generate_outline(user_prompt: str) -> list:
    """Generate a 5-panel comic outline.

    Args:
        user_prompt: the combined user story idea (prompt + character + setting + tone + style).

    Returns:
        A list of dicts with keys: panel, title, scene_description, image_prompt.

    Raises:
        GeminiError: on API failure or an unparseable / invalid response.
    """
    raw = generate_text(config.GEMINI_FLASH_MODEL, _build_prompt(user_prompt), json_mode=True, temperature=0.8)
    return parse_outline(raw)
