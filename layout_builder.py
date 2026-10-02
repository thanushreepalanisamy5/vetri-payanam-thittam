"""Step 4 of the pipeline: bind images, outline data and story text into panels."""
import re

from app import config

# Matches story headers like "**Panel 2: Into the Woods**", "Panel 2 - ...", "## Panel 2"
_PANEL_HEADER = re.compile(r"^[ \t>#*_]*panel[ \t]*(\d+)\b[^\n]*$", re.IGNORECASE | re.MULTILINE)


def _clean(text: str) -> str:
    """Strip markdown emphasis so the text reads well in HTML and in the PDF."""
    text = text.replace("**", "").replace("__", "")
    text = re.sub(r"^[ \t]*#+[ \t]*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_story(full_story: str) -> dict:
    """Split the full story into {panel_number: text}, without the header line."""
    matches = list(_PANEL_HEADER.finditer(full_story or ""))
    panels = {}
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_story)
        body = _clean(full_story[match.end() : end])
        panels.setdefault(int(match.group(1)), body)
    return panels


def build_comic_layout(image_paths: list, full_story: str, outline: list) -> list:
    """Organise generated images and story into a list of panel dictionaries.

    Returns a list of dicts with: panel, title, image_path (file system path),
    image_url (web path), text, scene_description, image_prompt.
    """
    if len(image_paths) != len(outline):
        raise ValueError(f"Got {len(image_paths)} images for {len(outline)} panels.")

    story_by_panel = split_story(full_story)
    layout = []
    for idx, (image, panel_info) in enumerate(zip(image_paths, outline), start=1):
        number = int(panel_info.get("panel", idx))
        scene = panel_info.get("scene_description", "")
        text = story_by_panel.get(number) or story_by_panel.get(idx) or ""
        if not text:  # story missing this panel: fall back to the scene description
            text = scene
        layout.append(
            {
                "panel": idx,
                "title": panel_info.get("title", f"Panel {idx}"),
                "image_path": str(image),
                "image_url": config.to_web_path(image),
                "text": text,
                "scene_description": scene,
                "image_prompt": panel_info.get("image_prompt", ""),
            }
        )
    return layout
