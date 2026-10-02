"""Step 5 of the pipeline: export the comic layout to a multi-page PDF (FPDF)."""
import os
import re
import uuid
from datetime import datetime

from fpdf import FPDF
from PIL import Image

from app import config

FONT_FAMILY = "DejaVu"


def _pdf_safe(text: str) -> str:
    """Remove characters the DejaVu font cannot draw (emoji, variation selectors)."""
    text = re.sub(r"[\U00010000-\U0010FFFF\uFE0F\u200D]", "", text or "")
    return text.replace("\t", "    ")


class ComicPDF(FPDF):
    """A4 PDF with a page-number footer."""

    def footer(self):
        self.set_y(-12)
        self.set_font(FONT_FAMILY, "", 9)
        self.cell(0, 8, f"Page {self.page_no()}", align="C")


def _register_fonts(pdf: FPDF) -> bool:
    """Register DejaVu (regular + italic). Returns True if an italic face is available."""
    if not config.FONT_PATH.exists():
        raise FileNotFoundError(
            f"Font not found: {config.FONT_PATH}. Place DejaVuSans.ttf in static/fonts/."
        )
    pdf.add_font(FONT_FAMILY, "", str(config.FONT_PATH))
    if config.FONT_ITALIC_PATH.exists():
        pdf.add_font(FONT_FAMILY, "I", str(config.FONT_ITALIC_PATH))
        return True
    return False


def save_pdf(layout: list) -> str:
    """Compile the comic into a PDF, one panel per page.

    Args:
        layout: list of panel dicts from build_comic_layout().

    Returns:
        Absolute path of the PDF saved in static/exports (timestamped file name).
    """
    pdf = ComicPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    has_italic = _register_fonts(pdf)
    italic = "I" if has_italic else ""

    for panel in layout:
        pdf.add_page()

        # Panel title
        pdf.set_font(FONT_FAMILY, "", 15)
        pdf.multi_cell(0, 10, _pdf_safe(f"Panel {panel['panel']}: {panel['title']}"),
                       align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        # Image (keep aspect ratio, fit into 190 x 110 mm box, centred)
        image_path = panel["image_path"]
        if os.path.exists(image_path):
            with Image.open(image_path) as im:
                px_w, px_h = im.size
            max_w, max_h = pdf.epw, 110
            scale = min(max_w / px_w, max_h / px_h)
            w_mm, h_mm = px_w * scale, px_h * scale
            y = pdf.get_y()
            pdf.image(image_path, x=(pdf.w - w_mm) / 2, y=y, w=w_mm, h=h_mm)
            pdf.set_y(y + h_mm + 6)
        else:
            pdf.set_font(FONT_FAMILY, "", 12)
            pdf.multi_cell(0, 10, _pdf_safe(f"Image missing: {image_path}"), align="L",
                           new_x="LMARGIN", new_y="NEXT")

        # Scene description (italic)
        if panel.get("scene_description"):
            pdf.set_font(FONT_FAMILY, italic, 11)
            pdf.multi_cell(0, 6, _pdf_safe(panel["scene_description"]), align="L",
                           new_x="LMARGIN", new_y="NEXT")
            pdf.ln(3)

        # Caption / narration / dialogue
        if panel.get("text"):
            pdf.set_font(FONT_FAMILY, "", 12)
            pdf.multi_cell(0, 7, _pdf_safe(panel["text"]), align="L", new_x="LMARGIN", new_y="NEXT")

    # Save with timestamp (short random suffix avoids clashes within the same second)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    filename = f"comic_{timestamp}_{uuid.uuid4().hex[:4]}.pdf"
    pdf_path = config.EXPORT_FOLDER / filename
    pdf.output(str(pdf_path))
    return str(pdf_path)
