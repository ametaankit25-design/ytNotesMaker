"""
pdf_generator.py
----------------
Converts a NotesOutput Pydantic object into three styled PDF files:
  • Summary PDF
  • Cheatsheet PDF (key concepts + bullet points)
  • Flashcards PDF (Q&A pairs)

Uses fpdf2 for PDF generation.
Note: Helvetica supports Latin-1 only — all text is sanitised via _safe().
"""

import os
import re
import tempfile
from fpdf import FPDF
from notes_schema import NotesOutput


# ──────────────────────────────────────────────
# Colour palette
# ──────────────────────────────────────────────

BRAND_COLOR   = (79, 70, 229)    # indigo-600
ACCENT_COLOR  = (16, 185, 129)   # emerald-500
DARK_BG       = (15, 23, 42)     # slate-900
LIGHT_TEXT    = (248, 250, 252)  # slate-50
MUTED_TEXT    = (100, 116, 139)  # slate-500
CARD_BG       = (30, 41, 59)     # slate-800


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _safe(text: str) -> str:
    """
    Strip any character outside the Latin-1 range (U+0000–U+00FF).
    Helvetica only supports Latin-1; anything beyond causes a crash.
    Emoji and other Unicode symbols are silently removed.
    """
    return re.sub(r'[^\x00-\xff]', '', str(text)).strip()


def _tmp_path(prefix: str) -> str:
    """Return a temp file path that persists (not auto-deleted)."""
    fd, path = tempfile.mkstemp(prefix=prefix, suffix=".pdf")
    os.close(fd)
    return path


# ──────────────────────────────────────────────
# Base PDF class
# ──────────────────────────────────────────────

class BasePDF(FPDF):
    """Common styling for all PDFs."""

    def __init__(self, title: str):
        super().__init__()
        self.doc_title = _safe(title)
        self.set_auto_page_break(auto=True, margin=20)
        self.add_page()
        self._draw_header()

    def _draw_header(self):
        # Dark header bar
        self.set_fill_color(*DARK_BG)
        self.rect(0, 0, 210, 40, "F")

        # Brand accent line
        self.set_fill_color(*BRAND_COLOR)
        self.rect(0, 38, 210, 3, "F")

        # App name
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*MUTED_TEXT)
        self.set_xy(10, 6)
        self.cell(0, 8, "YT NOTES MAKER", ln=False)

        # Document title
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(*LIGHT_TEXT)
        self.set_xy(10, 18)
        self.multi_cell(190, 8, self.doc_title, align="L")
        self.ln(10)

    def section_header(self, text: str, color=BRAND_COLOR):
        """Renders a coloured section header (plain ASCII label)."""
        self.set_fill_color(*color)
        self.set_text_color(*LIGHT_TEXT)
        self.set_font("Helvetica", "B", 12)
        self.set_x(10)
        self.cell(190, 9, f"  {_safe(text)}", fill=True, ln=True)
        self.ln(3)
        self.set_text_color(30, 30, 30)

    def body_text(self, text: str, indent: int = 10):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 30, 30)
        self.set_x(indent)
        self.multi_cell(190 - indent, 6, _safe(text))
        self.ln(2)

    def bullet(self, text: str):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 30, 30)
        self.set_x(14)
        self.cell(6, 6, "-")          # plain hyphen — safe in all fonts
        self.set_x(22)
        self.multi_cell(178, 6, _safe(text))

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*MUTED_TEXT)
        self.cell(0, 10, f"Page {self.page_no()} - YT Notes Maker", align="C")


# ──────────────────────────────────────────────
# 1.  Summary PDF
# ──────────────────────────────────────────────

def generate_summary_pdf(notes: NotesOutput) -> str:
    pdf = BasePDF(notes.title)

    pdf.section_header("SUMMARY")
    pdf.body_text(notes.summary)
    pdf.ln(4)

    if notes.important_quotes:
        pdf.section_header("NOTABLE QUOTES", color=ACCENT_COLOR)
        for quote in notes.important_quotes:
            pdf.set_font("Helvetica", "I", 10)
            pdf.set_text_color(50, 50, 50)
            pdf.set_x(14)
            pdf.multi_cell(182, 6, f'"{_safe(quote)}"')
            pdf.ln(2)

    path = _tmp_path("yt_summary_")
    pdf.output(path)
    return path


# ──────────────────────────────────────────────
# 2.  Cheatsheet PDF
# ──────────────────────────────────────────────

def generate_cheatsheet_pdf(notes: NotesOutput) -> str:
    pdf = BasePDF(f"Cheatsheet - {notes.title}")

    # Key concepts — two-column layout
    pdf.section_header("KEY CONCEPTS")
    concepts = notes.key_concepts
    for i in range(0, len(concepts), 2):
        left  = _safe(concepts[i])
        right = _safe(concepts[i + 1]) if i + 1 < len(concepts) else ""
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(*BRAND_COLOR)
        pdf.set_text_color(*LIGHT_TEXT)
        pdf.set_x(10)
        pdf.cell(90, 8, f"  {left}", fill=True, border=0)
        pdf.set_x(105)
        if right:
            pdf.cell(90, 8, f"  {right}", fill=True, border=0)
        pdf.ln(10)

    pdf.ln(4)

    # Bullet-point notes
    pdf.section_header("NOTES", color=ACCENT_COLOR)
    for bp in notes.bullet_points:
        pdf.bullet(bp)
        pdf.ln(1)

    path = _tmp_path("yt_cheatsheet_")
    pdf.output(path)
    return path


# ──────────────────────────────────────────────
# 3.  Flashcards PDF
# ──────────────────────────────────────────────

def generate_flashcards_pdf(notes: NotesOutput) -> str:
    pdf = BasePDF(f"Flashcards - {notes.title}")

    pdf.section_header("STUDY FLASHCARDS")
    pdf.body_text("Use these Q&A pairs to test your understanding of the video.")
    pdf.ln(4)

    for idx, card in enumerate(notes.flashcards, 1):
        # Question
        pdf.set_fill_color(*CARD_BG)
        pdf.set_text_color(*LIGHT_TEXT)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_x(10)
        pdf.cell(190, 8, f"  Q{idx}: {_safe(card.question)}", fill=True, ln=True)

        # Answer
        pdf.set_fill_color(240, 253, 244)   # light green
        pdf.set_text_color(22, 101, 52)      # dark green
        pdf.set_font("Helvetica", "", 10)
        pdf.set_x(10)
        pdf.multi_cell(190, 7, f"  Ans: {_safe(card.answer)}", fill=True)
        pdf.ln(4)

    path = _tmp_path("yt_flashcards_")
    pdf.output(path)
    return path


# ──────────────────────────────────────────────
# 4.  Convenience wrapper
# ──────────────────────────────────────────────

def generate_all_pdfs(notes: NotesOutput) -> dict:
    """
    Generates all three PDFs and returns a dict of file paths:
        {"summary": ..., "cheatsheet": ..., "flashcards": ...}
    """
    result = {}
    
    try:
        print("[PDF] Generating summary PDF...")
        result["summary"] = generate_summary_pdf(notes)
        print(f"[PDF] Summary PDF created: {result['summary']}")
    except Exception as e:
        print(f"[PDF ERROR] Summary PDF failed: {e}")
        import traceback
        traceback.print_exc()
        result["summary"] = None
    
    try:
        print("[PDF] Generating cheatsheet PDF...")
        result["cheatsheet"] = generate_cheatsheet_pdf(notes)
        print(f"[PDF] Cheatsheet PDF created: {result['cheatsheet']}")
    except Exception as e:
        print(f"[PDF ERROR] Cheatsheet PDF failed: {e}")
        import traceback
        traceback.print_exc()
        result["cheatsheet"] = None
    
    try:
        print("[PDF] Generating flashcards PDF...")
        result["flashcards"] = generate_flashcards_pdf(notes)
        print(f"[PDF] Flashcards PDF created: {result['flashcards']}")
    except Exception as e:
        print(f"[PDF ERROR] Flashcards PDF failed: {e}")
        import traceback
        traceback.print_exc()
        result["flashcards"] = None
    
    return result
