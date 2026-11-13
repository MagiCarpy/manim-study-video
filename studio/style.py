"""3Blue1Brown-flavoured theme.

No LaTeX is installed, so use Text / MarkupText / Paragraph only.
Never use MathTex, Tex, Matrix, DecimalNumber, or NumberLine/Axes with
`include_numbers=True` -- they all shell out to latex and will crash.
For math-ish text use Unicode in Text: "O(n²)", "x + 1", "≤", "→", "λ".
"""

from manim import config, ManimColor

# --- palette (close to 3b1b) -------------------------------------------------
BG = ManimColor("#1C1C1C")
FG = ManimColor("#ECECEC")       # main text
DIM = ManimColor("#8A8A8A")      # secondary text, axes, lifelines
BLUE = ManimColor("#58C4DD")
TEAL = ManimColor("#5CD0B3")
YELLOW = ManimColor("#FFFF00")
GOLD = ManimColor("#F0AC5F")
RED = ManimColor("#FC6255")
GREEN = ManimColor("#83C167")
PURPLE = ManimColor("#9A72AC")
PANEL = ManimColor("#2A2A2A")    # box fill

ACCENTS = [BLUE, TEAL, GOLD, PURPLE, GREEN, RED]

# --- typography ----------------------------------------------------------------
FONT = "Avenir Next"   # ships with macOS
MONO = "Menlo"

# Font sizes (Manim frame is ~14.2 x 8 units). Keep body >= 24 for legibility.
TITLE_SIZE = 56
HEADING_SIZE = 40
BODY_SIZE = 30
LABEL_SIZE = 24
SMALL_SIZE = 20


def apply_theme() -> None:
    config.background_color = BG
