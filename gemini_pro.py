"""Step 2 of the pipeline: narration and dialogue for every panel (the "Pro" model)."""
from app import config
from app.gemini_client import generate_text


def _build_prompt(outline: list) -> str:
    formatted_outline = "\n".join(
        f"{p.get('panel', i + 1)}. {p.get('title', '')}: {p.get('scene_description', '')}"
        for i, p in enumerate(outline)
    )
    return f"""
You're a comic book writer.

Given the following panel breakdown, write a comic-style story with engaging narration and character dialogues for each panel.

Panel Outline:
{formatted_outline}

Guidelines:
- Use a fun and engaging tone, like an actual comic book.
- Include narration and clearly marked character lines.
- Keep each panel self-contained but part of a cohesive story.
- Write exactly {len(outline)} panels, in order.

Format EXACTLY like this for every panel (plain text, no other markdown, no emojis):

**Panel 1: <title>**
Caption: <one short line describing the environment or sound>
Narration: <1-3 sentences of narration>
Dialogue:
<Character name>: "<line>"
<Character name>: "<line>"

**Panel 2: <title>**
...
""".strip()


def generate_story(outline: list) -> str:
    """Expand panel outlines into a full comic story with narration and dialogue.

    Args:
        outline: list of panel dicts produced by generate_outline().

    Returns:
        One formatted text containing every panel's story.

    Raises:
        GeminiError: if the API call fails.
    """
    return generate_text(config.GEMINI_PRO_MODEL, _build_prompt(outline), temperature=0.9)
