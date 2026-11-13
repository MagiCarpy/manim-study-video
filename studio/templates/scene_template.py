"""Scenes for lessons/<slug>. Copy to lessons/<slug>/scenes.py.

Rules: inherit StudyScene, narrate with `with self.voiceover(text=...) as t:`,
Text/MarkupText only (no MathTex/Tex -- no LaTeX installed), reuse studio.cslib.
"""

from pathlib import Path

from manim import DOWN, LEFT, RIGHT, UP, Create, FadeIn, FadeOut, Write

from studio import style
from studio.base import StudyScene
from studio.cslib import (Gantt, MemoryTable, Node, Packet, Queue, SequenceDiagram, SlideImage,
                          bullets, label, packet_flight)

SLIDES = Path(__file__).parent / "source" / "slides"   # slide-001.png, ...


class Hook(StudyScene):
    def construct(self):
        title = self.section_title("Why this matters", "one-line framing")
        with self.voiceover(text="Open with a concrete question the viewer should care about.") as t:
            q = label("What happens when ... ?", size=style.BODY_SIZE).next_to(title, DOWN, buff=1.0)
            self.play(Write(q), run_time=min(2, t.duration))
        self.clear_all()


class CoreIdea(StudyScene):
    def construct(self):
        slide = SlideImage(SLIDES / "slide-002.png", height=5.5)
        with self.voiceover(text="Here is how the slides put it.") as t:
            self.play(FadeIn(slide))
        # Highlight a region using fractions of the slide (0,0)=top-left, (1,1)=bottom-right.
        box = slide.highlight(0.05, 0.3, 0.95, 0.45)
        with self.voiceover(text="Focus on this line.<bookmark mark='hl'/> It is the key definition.") as t:
            self.wait_until_bookmark("hl")
            self.play(Create(box))
        self.play(FadeOut(slide), FadeOut(box))

        a, b = Node("Host A").move_to(LEFT * 4), Node("Host B", kind="server").move_to(RIGHT * 4)
        with self.voiceover(text="Now let's animate the mechanism itself.") as t:
            self.play(FadeIn(a), FadeIn(b))
            self.play(packet_flight(Packet("DATA"), a, b, run_time=2))
        self.clear_all()


class WorkedExample(StudyScene):
    def construct(self):
        self.section_title("Worked example")
        with self.voiceover(text="Walk through the verified event sequence from notes dot md.") as t:
            self.wait(t.duration)
        self.clear_all()


class Misconceptions(StudyScene):
    def construct(self):
        self.section_title("Common pitfalls")
        with self.voiceover(text="A common misconception is ...") as t:
            self.play(FadeIn(bullets(["Misconception 1 → why it's wrong"])))
        self.clear_all()


class Recap(StudyScene):
    def construct(self):
        title = self.section_title("Recap")
        pts = bullets(["Point one", "Point two", "Point three"]).next_to(title, DOWN, buff=0.8)
        with self.voiceover(text="To recap: point one, point two, and point three.") as t:
            self.play(FadeIn(pts, lag_ratio=0.3), run_time=min(3, t.duration))
        self.wait(1)
