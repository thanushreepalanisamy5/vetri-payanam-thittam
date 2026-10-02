"""Step 3 of the pipeline: comic-style panel illustrations.

Backends (set IMAGE_BACKEND in .env):
  * "diffusers"   - real Stable Diffusion via Hugging Face Diffusers (default)
  * "placeholder" - instant gradient images with the prompt text; no model needed,
                    ideal for testing the whole app on a laptop.

The Stable Diffusion pipeline is loaded lazily on the first request (not at import
time), so the server starts instantly and a missing model never crashes startup.
"""
import hashlib
import logging
import os
import re
import textwrap
import threading
import uuid

from PIL import Image, ImageDraw, ImageFont

from app import config

logger = logging.getLogger("comiccraft.image")


class ImageGenerationError(RuntimeError):
    """Raised when an image cannot be generated."""


STYLE_PRESETS = {
    "anime": "anime style, vibrant colors, cel shading, clean line art",
    "pixel art": "pixel art, 16-bit retro game style, crisp pixels",
    "comic book": "classic comic book style, bold ink outlines, halftone shading, vivid colors",
    "realistic": "realistic digital painting, cinematic lighting, highly detailed",
}
NEGATIVE_PROMPT = "blurry, low quality, deformed, disfigured, extra limbs, text, watermark, signature, logo"

_pipe = None
_device = None
_load_lock = threading.Lock()   # only one thread loads the model
_gen_lock = threading.Lock()    # only one generation at a time (protects GPU/CPU memory)


def sanitize_filename(prompt: str, max_len: int = 40) -> str:
    """Make a safe, unique PNG filename from a prompt."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", prompt or "").strip("_").lower()[:max_len] or "panel"
    return f"{slug}_{uuid.uuid4().hex[:8]}.png"


def _styled_prompt(prompt: str, style: str | None) -> str:
    """Prepend style keywords (CLIP only reads ~77 tokens, so the start matters most)."""
    preset = STYLE_PRESETS.get((style or "").strip().lower())
    return f"{preset}, {prompt}" if preset else prompt


def _get_pipeline():
    global _pipe, _device
    if _pipe is not None:
        return _pipe, _device
    with _load_lock:
        if _pipe is None:
            try:
                import torch
                from diffusers import StableDiffusionPipeline
            except ImportError as exc:
                raise ImageGenerationError(
                    "torch/diffusers are not installed. Run `pip install -r requirements.txt`, "
                    "or set IMAGE_BACKEND=placeholder in .env to test without Stable Diffusion."
                ) from exc

            if torch.cuda.is_available():
                device, dtype = "cuda", torch.float16
            elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
                device, dtype = "mps", torch.float32
            else:
                device, dtype = "cpu", torch.float32

            logger.info("Loading %s on %s (first run downloads ~4 GB)...", config.SD_MODEL_ID, device)
            kwargs = {"torch_dtype": dtype}
            if config.HF_API_KEY:
                kwargs["token"] = config.HF_API_KEY
            try:
                pipe = StableDiffusionPipeline.from_pretrained(config.SD_MODEL_ID, **kwargs).to(device)
            except Exception as exc:
                raise ImageGenerationError(
                    f"Could not load Stable Diffusion model '{config.SD_MODEL_ID}': {exc}"
                ) from exc
            if device != "cuda":
                pipe.enable_attention_slicing()
            _pipe, _device = pipe, device
            logger.info("Stable Diffusion ready.")
    return _pipe, _device


def _placeholder_image(prompt: str) -> Image.Image:
    """Deterministic gradient image that shows the prompt text."""
    size = config.SD_SIZE
    digest = hashlib.md5(prompt.encode("utf-8")).digest()
    top = tuple(60 + digest[i] % 150 for i in range(3))
    bottom = tuple(40 + digest[i + 3] % 150 for i in range(3))
    img = Image.new("RGB", (size, size))
    draw = ImageDraw.Draw(img)
    for y in range(size):
        t = y / max(size - 1, 1)
        draw.line([(0, y), (size, y)], fill=tuple(int(top[c] * (1 - t) + bottom[c] * t) for c in range(3)))
    try:
        font = ImageFont.truetype(str(config.FONT_PATH), max(14, size // 26))
    except OSError:
        font = ImageFont.load_default()
    text = "PLACEHOLDER IMAGE\n\n" + "\n".join(textwrap.wrap(prompt, width=38)[:12])
    draw.multiline_text((size * 0.06, size * 0.08), text, fill=(255, 255, 255), font=font, spacing=6)
    return img


def generate_image(prompt: str, filename: str | None = None, style: str | None = None) -> str:
    """Create one comic-style image and save it to static/panels.

    Args:
        prompt: the image prompt for the panel.
        filename: optional file name; a safe unique one is generated if omitted.
        style: optional art style name (anime, pixel art, comic book, realistic).

    Returns:
        Absolute path of the saved PNG file.
    """
    if not prompt or not prompt.strip():
        raise ImageGenerationError("Image prompt is empty.")

    filename = os.path.basename(filename) if filename else sanitize_filename(prompt)
    if not filename.lower().endswith(".png"):
        filename += ".png"
    path = config.PANEL_FOLDER / filename
    os.makedirs(path.parent, exist_ok=True)

    full_prompt = _styled_prompt(prompt.strip(), style)

    if config.IMAGE_BACKEND == "placeholder":
        image = _placeholder_image(full_prompt)
    elif config.IMAGE_BACKEND == "diffusers":
        pipe, device = _get_pipeline()
        steps = config.SD_STEPS or (30 if device == "cuda" else 20)
        try:
            with _gen_lock:
                result = pipe(
                    full_prompt,
                    negative_prompt=NEGATIVE_PROMPT,
                    num_inference_steps=steps,
                    guidance_scale=7.5,
                    width=config.SD_SIZE,
                    height=config.SD_SIZE,
                )
        except Exception as exc:
            raise ImageGenerationError(f"Stable Diffusion failed: {exc}") from exc
        image = result.images[0]
        if any(getattr(result, "nsfw_content_detected", None) or []):
            logger.warning("Safety checker flagged an image; it may appear black. Try rewording the prompt.")
    else:
        raise ImageGenerationError(f"Unknown IMAGE_BACKEND '{config.IMAGE_BACKEND}' (use 'diffusers' or 'placeholder').")

    image.save(path)
    return str(path)
