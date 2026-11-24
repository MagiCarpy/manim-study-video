"""Reusable Manim building blocks for CS explainers (networking, OS, systems).

Everything here is LaTeX-free. Mobjects are plain VGroups/Groups so you can
position them with .move_to / .next_to / .arrange as usual. Methods that
change state return Animations for the caller to `self.play(...)`.

    Node         labeled box (host / server / router / process ...)
    Packet       small labeled envelope; packet_flight() moves it A -> B
    Queue        FIFO slots with enqueue()/dequeue() animations
    MemoryTable  grid with headers; highlight cells/rows, update values
                 (page tables, TLBs, state tables, routing tables)
    Gantt        CPU-scheduling timeline built from (label, start, end)
    SequenceDiagram  lifelines + message arrows (protocol exchanges)
    Timeline     two-or-more vertical lifelines with travelling, lost (✗), old-duplicate
                 (dashed) and resent messages, state notes and a legend (preferred)
    cross_fade() replace text in place by fading (never a letter morph)
    beat()       seconds until a bookmark or the end of the narration, with a floor
    SlideImage   a source slide PNG with highlight boxes in slide coords
    FieldBar     horizontal bar of labeled fields (bit layouts, header stacks)
    PrefixTrie   binary (unibit) trie of prefixes, for lookup walks
    packet_route()  move a mobject along a polyline (via waypoints)
    bullets()    simple left-aligned bullet list
    source_tag() small corner citation ("IP Forwarding · slide 14")
    flow_flash() pulse along an existing line/arrow (data flow)
    focus()/unfocus()  dim everything but the focal objects, then restore
    TermEquation LaTeX-free equation revealed term by term (dim-and-reveal)
    pulse()      emphasis using the object's own border (no new outline)
    identify()   animated outline around important text; use sparingly
    SlideImage.highlight() snaps rough regions to whole slide objects (snap=False to keep exact)
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from manim import (
    DOWN, LEFT, PI, RIGHT, UP,
    Animation, AnimationGroup, Arrow, Circle, Create, DashedLine, FadeIn, FadeOut, GrowArrow,
    GrowFromEdge, Group, ImageMobject, Indicate, Line, Mobject, MoveAlongPath, Polygon,
    Rectangle, RoundedRectangle, Succession, Text, Transform, VGroup, VMobject, Wait, linear,
)

from studio import style


def label(text: str, size: int = style.LABEL_SIZE, color=style.FG, mono: bool = False, **kw) -> Text:
    return Text(text, font=style.MONO if mono else style.FONT, font_size=size, color=color, **kw)


def bullets(items: list[str], size: int = style.BODY_SIZE, color=style.FG, buff: float = 0.35) -> VGroup:
    rows = VGroup(*[label(f"•  {t}", size=size, color=color) for t in items])
    return rows.arrange(DOWN, aligned_edge=LEFT, buff=buff)


# --- layout primitives (import these; do not redefine them per section) --------------------
def _min_size(size):
    if size < 20:
        raise ValueError(f"text size {size} is below 20; enlarge the container instead of shrinking text")


def P(x: float, y: float) -> np.ndarray:
    """Scene point: P(-3, 1.5)."""
    return np.array([float(x), float(y), 0.0])


def panel(w: float, h: float, color=style.DIM, fill=style.PANEL, opacity: float = 1.0,
          radius: float = 0.12, stroke: float = 2) -> RoundedRectangle:
    """Rounded box in the house style (opaque PANEL fill, so arrows behind it stay hidden)."""
    return RoundedRectangle(width=w, height=h, corner_radius=radius, stroke_color=color, stroke_width=stroke,
                            fill_color=fill, fill_opacity=opacity)


def text_at(text: str, x: float, y: float, size: int = style.LABEL_SIZE, color=style.FG, mono: bool = False,
            align=LEFT, **kw) -> Text:
    """Text whose `align` edge (LEFT by default, or RIGHT) sits at (x, y)."""
    _min_size(size)
    t = label(text, size=size, color=color, mono=mono, **kw).move_to(P(x, y))
    return t.align_to(P(x, y), align)


def rich_text(parts, size: int = 22, mono: bool = False, color=style.FG) -> Text:
    """One Text coloured by part: rich_text([("SYN", GOLD), ("seq 1000", FG)]) → "SYN seq 1000".
    A single Text keeps one baseline and normal spacing (separate Texts drift)."""
    _min_size(size)
    if isinstance(parts, str):
        return label(parts, size=size, color=color, mono=mono)
    joined, t2c, pos = "", {}, 0
    for i, (s, c) in enumerate(parts):
        if i:
            joined += " "
            pos += 1
        t2c[f"[{pos}:{pos + len(s)}]"] = c
        joined += s
        pos += len(s)
    return label(joined, size=size, color=color, mono=mono, t2c=t2c)


def boxed(text: str, w: float, h: float, color=style.DIM, size: int = 22, mono: bool = False,
          text_color=style.FG) -> VGroup:
    """VGroup(box, text) with centred text. The box widens to fit; the text never shrinks."""
    _min_size(size)
    t = label(text, size=size, color=text_color, mono=mono)
    box = panel(max(w, t.width + 0.3), max(h, t.height + 0.2), color)
    return VGroup(box, t.move_to(box))


def card(text: str, width: float, color=style.DIM, size: int = 24, text_color=style.FG,
         mono: bool = False) -> VGroup:
    """VGroup(box, lines): text wrapped to `width`, box sized to the text, no one-word last line."""
    _min_size(size)
    inner = width - 0.4
    fits = lambda s: label(s, size=size, mono=mono).width <= inner
    lines: list[list[str]] = []
    for word in str(text).split():
        if lines and fits(" ".join(lines[-1] + [word])):
            lines[-1].append(word)
        else:
            if not fits(word):
                raise ValueError(f"Unbreakable word exceeds card width: {word!r}")
            lines.append([word])
    if len(lines) > 1 and len(lines[-1]) == 1 and len(lines[-2]) > 2:
        if fits(" ".join([lines[-2][-1]] + lines[-1])):
            lines[-1].insert(0, lines[-2].pop())  # no orphan word
    body = VGroup(*[label(" ".join(ws), size=size, color=text_color, mono=mono) for ws in lines])
    body.arrange(DOWN, aligned_edge=LEFT, buff=0.12)
    box = panel(width, body.height + 0.4, color)
    return VGroup(box, body.move_to(box))


def host(name: str, sub: str | None = None, color=style.BLUE, w: float = 2.4, h: float = 1.2,
         name_size: int = 26, sub_size: int = 22) -> VGroup:
    """VGroup(box, name[, sub]): an endpoint box (host, server, socket) with an optional address line."""
    parts = [label(name, size=name_size, color=color)]
    if sub:
        parts.append(label(sub, size=sub_size, color=style.FG, mono=True))
    text = VGroup(*parts).arrange(DOWN, buff=0.08)
    box = panel(max(w, text.width + 0.3), max(h, text.height + 0.3), color, stroke=3)
    text.move_to(box)
    return VGroup(box, *parts)


def pill(text: str, color=style.GOLD, size: int = 22, mono: bool = False) -> VGroup:
    """VGroup(rounded tag, text): a compact state or flag badge (SYN, ESTABLISHED, TIME_WAIT)."""
    _min_size(size)
    t = label(text, size=size, color=color, mono=mono)
    r = RoundedRectangle(width=t.width + 0.34, height=t.height + 0.22, corner_radius=0.14, stroke_color=color,
                         stroke_width=2, fill_color=style.PANEL, fill_opacity=1)
    return VGroup(r, t.move_to(r))


def mark(ok: bool, size: int = 44) -> Text:
    """Green ✓ or red ✗."""
    return label("✓" if ok else "✗", size=size, color=style.GREEN if ok else style.RED)


class _Arrow(VGroup):
    def __init__(self, a, b, color, dashed, both, tip, stroke):
        super().__init__()
        a, b = np.array(a, dtype=float), np.array(b, dtype=float)
        d = (b - a) / np.linalg.norm(b - a)
        n = np.array([-d[1], d[0], 0.0])

        def head(tip_pt, back):
            base = tip_pt - back * tip
            return Polygon(tip_pt, base + 0.5 * tip * n, base - 0.5 * tip * n, color=color, stroke_width=1,
                           fill_color=color, fill_opacity=1)

        start = a + d * tip if both else a
        end = b - d * tip
        self.shaft = (DashedLine(start, end, dash_length=0.14, dashed_ratio=0.55, color=color, stroke_width=stroke - 1)
                      if dashed else Line(start, end, color=color, stroke_width=stroke))
        self.head = head(b, d)
        self.add(self.shaft, self.head)
        self.tail_head = head(a, -d) if both else None
        if both:
            self.add(self.tail_head)


def arrow(a, b, color=style.FG, dashed: bool = False, both: bool = False, tip: float = 0.2,
          stroke: float = 4) -> VGroup:
    """Arrow whose tip lands exactly on `b` with a fixed head size at any length
    (Manim's Arrow rescales its tip on short arrows). .shaft, .head, .tail_head (both=True)."""
    return _Arrow(a, b, color, dashed, both, tip, stroke)


def bracket(x: float, y0: float, y1: float, side=LEFT, color=style.FG, tick: float = 0.15,
            stroke: float = 3) -> VMobject:
    """Vertical bracket at x from y0 to y1. `side` is where it sits relative to what it groups
    (LEFT: ticks point right, back toward the content)."""
    s = 1 if np.allclose(np.array(side, dtype=float), LEFT) else -1
    v = VMobject(stroke_color=color, stroke_width=stroke)
    v.set_points_as_corners([P(x + s * tick, y0), P(x, y0), P(x, y1), P(x + s * tick, y1)])
    return v


def later(delay: float, *anims) -> Succession:
    """Start `anims` after `delay` seconds, inside one self.play()."""
    return Succession(Wait(delay), *anims) if delay > 0.01 else Succession(*anims)


def appear(mob, run_time: float = 0.15):
    """Hide `mob` now and fade it in when this animation runs (for Succession/LaggedStart members)."""
    mob.set_opacity(0)
    return mob.animate(run_time=run_time).set_opacity(1)


def source_tag(text: str, corner=None, size: int = style.SMALL_SIZE, color=style.DIM) -> Text:
    """Small on-screen citation in a quiet corner (default: bottom-right of the safe area).

        tag = source_tag("IP Forwarding · slide 14")
        self.play(FadeIn(tag))                       # with the claim it cites
        self.play(cross_fade(tag, source_tag("Added example · based on slide 14")))
    Wording/provenance rules: SKILL.md "Source citations in the video". Keep diagrams clear
    of the bottom ~0.6 units on the right while a tag is shown.
    """
    corner = DOWN + RIGHT if corner is None else corner
    tag = label(text, size=max(size, style.SMALL_SIZE), color=color).to_corner(corner, buff=0.35)
    tag._studio_source_tag = True
    return fit_to_frame(tag)


# --------------------------------------------------------------------------- #
class Node(VGroup):
    """Labeled rounded box. kind only changes the default color."""

    KIND_COLORS = {"host": style.BLUE, "server": style.TEAL, "router": style.GOLD,
                   "process": style.PURPLE, "disk": style.GREEN}

    def __init__(self, name: str, sublabel: str | None = None, kind: str = "host",
                 color=None, width: float = 2.4, height: float = 1.1, **kw):
        super().__init__(**kw)
        self.color_ = color or self.KIND_COLORS.get(kind, style.BLUE)
        self.box = RoundedRectangle(corner_radius=0.15, width=width, height=height,
                                    stroke_color=self.color_, stroke_width=3,
                                    fill_color=style.PANEL, fill_opacity=1)
        self.title = label(name, size=style.LABEL_SIZE + 4, weight="BOLD")
        self.add(self.box, self.title)
        if sublabel:
            self.sub = label(sublabel, size=style.SMALL_SIZE, color=style.DIM)
            VGroup(self.title, self.sub).arrange(DOWN, buff=0.08).move_to(self.box)
            self.add(self.sub)
        else:
            self.title.move_to(self.box)

    def flash(self, color=style.YELLOW) -> Indicate:
        return Indicate(self.box, color=color, scale_factor=1.06)


# --------------------------------------------------------------------------- #
class Packet(VGroup):
    """Small labeled packet. Use packet_flight() to animate it between points."""

    def __init__(self, text: str, color=style.YELLOW, size: int = style.SMALL_SIZE, **kw):
        super().__init__(**kw)
        self.text = label(text, size=size, color=style.BG, weight="BOLD")
        self.body = RoundedRectangle(corner_radius=0.08, width=self.text.width + 0.3,
                                     height=self.text.height + 0.22, fill_color=color,
                                     fill_opacity=1, stroke_width=0)
        self.text.move_to(self.body)
        self.add(self.body, self.text)


def _point(x):
    return x.get_center() if hasattr(x, "get_center") else np.array(x, dtype=float)


def packet_flight(packet: Packet, start, end, run_time: float = 1.5, fade: bool = True) -> Succession:
    """FadeIn at `start`, travel along a straight line to `end`, optionally FadeOut.
    `run_time` is the total duration. `start`/`end` may be points or mobjects."""
    a, b = _point(start), _point(end)
    packet.move_to(a)
    path = Line(a, b)
    fade_t = 0.2
    move_t = max(run_time - fade_t * (2 if fade else 1), 0.3)
    steps = [FadeIn(packet, scale=0.6, run_time=fade_t), MoveAlongPath(packet, path, run_time=move_t)]
    if fade:
        steps.append(FadeOut(packet, run_time=fade_t))
    return Succession(*steps)


# --------------------------------------------------------------------------- #
class Queue(VGroup):
    """Horizontal FIFO with `capacity` slots. Front is the left end.

    q = Queue(4, title="Ready queue")
    self.play(q.enqueue("P1"))
    anim, item = q.dequeue(); self.play(anim)   # item is removed from q
    """

    def __init__(self, capacity: int = 5, title: str | None = None, slot: float = 0.9,
                 color=style.DIM, item_color=style.BLUE, **kw):
        super().__init__(**kw)
        self.item_color = item_color
        self.slots = VGroup(*[Rectangle(width=slot, height=slot, stroke_color=color, stroke_width=2)
                              for _ in range(capacity)]).arrange(RIGHT, buff=0)
        self.add(self.slots)
        if title:
            self.title = label(title, size=style.LABEL_SIZE, color=style.DIM)
            self.title.next_to(self.slots, UP, buff=0.2)
            self.add(self.title)
        self.items: list[VGroup] = []

    def make_item(self, text: str, color=None) -> VGroup:
        s = self.slots[0].width * 0.8
        box = RoundedRectangle(corner_radius=0.08, width=s, height=s,
                               fill_color=color or self.item_color, fill_opacity=0.9, stroke_width=0)
        return VGroup(box, label(text, size=style.SMALL_SIZE + 2, color=style.BG, weight="BOLD").move_to(box))

    def enqueue(self, text_or_item, color=None):
        """Pass a string to create a new item (fades in at the tail), or an
        existing on-screen item (e.g. one returned by dequeue) to slide it back in."""
        if len(self.items) >= len(self.slots):
            raise ValueError("Queue is full")
        target = self.slots[len(self.items)].get_center()
        if isinstance(text_or_item, str):
            item = self.make_item(text_or_item, color).move_to(target)
            self.items.append(item)
            return FadeIn(item, shift=LEFT * 0.5)
        self.items.append(text_or_item)
        return text_or_item.animate.move_to(target)

    def dequeue(self):
        """Returns (animation, item). The front item moves up out of the queue;
        remaining items shift left. The item stays on screen for reuse."""
        if not self.items:
            raise ValueError("Queue is empty")
        item = self.items.pop(0)
        anims = [item.animate.shift(UP * (self.slots[0].height * 1.3))]
        for i, it in enumerate(self.items):
            anims.append(it.animate.move_to(self.slots[i].get_center()))
        return AnimationGroup(*anims), item


# --------------------------------------------------------------------------- #
class MemoryTable(VGroup):
    """Grid of text cells with an optional header row.

    t = MemoryTable([["0", "5", "1"], ["1", "—", "0"]], headers=["VPN", "PFN", "Valid"])
    self.play(t.highlight_row(1)); self.play(t.set_cell(1, 1, "9"))
    """

    def __init__(self, rows: list[list[str]], headers: list[str] | None = None,
                 col_width: float | list[float] = 1.6, row_height: float = 0.6,
                 size: int = style.LABEL_SIZE, mono: bool = True, **kw):
        super().__init__(**kw)
        ncols = len(headers or rows[0])
        widths = col_width if isinstance(col_width, list) else [col_width] * ncols
        self.size, self.mono = size, mono
        self.cells: list[list[VGroup]] = []
        all_rows = ([headers] if headers else []) + rows
        self.has_header = headers is not None
        grid = VGroup()
        for r, row in enumerate(all_rows):
            is_head = self.has_header and r == 0
            cells = []
            for c, val in enumerate(row):
                rect = Rectangle(width=widths[c], height=row_height, stroke_color=style.DIM, stroke_width=2,
                                 fill_color=style.PANEL if is_head else style.BG, fill_opacity=1)
                txt = label(str(val), size=size, color=style.BLUE if is_head else style.FG,
                            mono=mono and not is_head, weight="BOLD" if is_head else "NORMAL")
                cells.append(VGroup(rect, txt))
            row_g = VGroup(*cells).arrange(RIGHT, buff=0)
            for cell in cells:
                cell[1].move_to(cell[0])
            grid.add(row_g)
            if not is_head:
                self.cells.append(cells)
        grid.arrange(DOWN, buff=0)
        self.grid = grid
        self.add(grid)

    def cell(self, r: int, c: int) -> VGroup:
        return self.cells[r][c]

    def highlight_cell(self, r: int, c: int, color=style.YELLOW, opacity: float = 0.35):
        return self.cells[r][c][0].animate.set_fill(color, opacity=opacity)

    def highlight_row(self, r: int, color=style.YELLOW, opacity: float = 0.35):
        return AnimationGroup(*[cell[0].animate.set_fill(color, opacity=opacity) for cell in self.cells[r]])

    def clear_highlight(self, r: int | None = None):
        rows = [self.cells[r]] if r is not None else self.cells
        # Animated rectangles may be promoted above their sibling text by Manim.
        # Clearing to transparent keeps labels visible regardless of draw order.
        return AnimationGroup(*[cell[0].animate.set_fill(style.BG, opacity=0) for row in rows for cell in row])

    def set_cell(self, r: int, c: int, value: str, color=style.YELLOW):
        old = self.cells[r][c][1]
        new = label(str(value), size=self.size, color=color, mono=self.mono).move_to(old)
        return Transform(old, new)

    def fill_from(self, r: int, c: int, value: str, sources, color=style.YELLOW):
        """Copies of the `sources` cells' text fly into cell (r, c), which becomes `value`.

            self.play(t.fill_from(2, 1, "1", [(0, 1), (1, 1)]))   # C = M xor K, one column
        Keeps the table's own text object (unlike ReplacementTransform onto a loose label)."""
        from manim import FadeOut
        old = self.cells[r][c][1]
        new = label(str(value), size=self.size, color=color, mono=self.mono).move_to(old)
        copies = [self.cells[sr][sc][1].copy() for sr, sc in sources]
        return AnimationGroup(Transform(old, new), *[FadeOut(cp, target_position=old) for cp in copies])


# --------------------------------------------------------------------------- #
class Gantt(VGroup):
    """CPU-scheduling Gantt chart.

    g = Gantt([("P1", 0, 2), ("P2", 2, 4)], unit=0.9)
    self.play(g.axis_animation()); for a in g.block_animations(): self.play(a)
    """

    def __init__(self, segments: list[tuple[str, float, float]], unit: float = 0.8, height: float = 0.8,
                 colors: dict[str, object] | None = None, title: str | None = None, **kw):
        super().__init__(**kw)
        names = list(dict.fromkeys(s[0] for s in segments))
        self.colors = colors or {n: style.ACCENTS[i % len(style.ACCENTS)] for i, n in enumerate(names)}
        t_end = max(s[2] for s in segments)
        self.unit = unit
        origin = LEFT * t_end * unit / 2
        self.blocks = VGroup()
        for name, t0, t1 in segments:
            rect = Rectangle(width=(t1 - t0) * unit, height=height, fill_color=self.colors[name],
                             fill_opacity=0.85, stroke_color=style.BG, stroke_width=2)
            rect.move_to(origin + RIGHT * (t0 + t1) / 2 * unit)
            txt = label(name, size=style.LABEL_SIZE, color=style.BG, weight="BOLD").move_to(rect)
            self.blocks.add(VGroup(rect, txt))
        y = DOWN * (height / 2)
        self.axis = Line(origin + y, origin + RIGHT * t_end * unit + y, color=style.DIM, stroke_width=2)
        ticks = sorted({s[1] for s in segments} | {s[2] for s in segments})
        self.ticks = VGroup()
        for t in ticks:
            p = origin + RIGHT * t * unit + y
            self.ticks.add(VGroup(Line(p, p + DOWN * 0.12, color=style.DIM, stroke_width=2),
                                  label(f"{t:g}", size=style.SMALL_SIZE, color=style.DIM).next_to(p, DOWN, buff=0.18)))
        self.add(self.axis, self.ticks, self.blocks)
        if title:
            self.title = label(title, size=style.LABEL_SIZE, color=style.DIM).next_to(self.blocks, UP, buff=0.3)
            self.title.set_x(self.axis.get_center()[0])
            self.add(self.title)

    def axis_animation(self):
        anims = [Create(self.axis), FadeIn(self.ticks)]
        if hasattr(self, "title"):
            anims.append(FadeIn(self.title))
        return AnimationGroup(*anims)

    def block_animations(self, run_time_per_unit: float = 0.35) -> list:
        return [GrowFromEdge(b, LEFT, run_time=max(0.3, b[0].width / self.unit * run_time_per_unit))
                for b in self.blocks]

    def build(self) -> Succession:
        return Succession(self.axis_animation(), *self.block_animations())


# --------------------------------------------------------------------------- #
class SequenceDiagram(VGroup):
    """Lifelines for participants plus message arrows added top to bottom.

    sd = SequenceDiagram(["Client", "Server"])
    self.play(sd.create())
    arrow_anim, arrow = sd.message("Client", "Server", "SYN seq=x")
    self.play(arrow_anim)
    """

    def __init__(self, participants: list[str], width: float = 8.0, height: float = 5.5,
                 step: float = 0.9, kinds: list[str] | None = None, **kw):
        super().__init__(**kw)
        self.step = step
        self.heads = VGroup(*[Node(p, kind=(kinds[i] if kinds else ("host", "server")[i % 2]),
                                   width=2.2, height=0.8) for i, p in enumerate(participants)])
        n = len(participants)
        for i, h in enumerate(self.heads):
            h.move_to(RIGHT * (-width / 2 + i * width / max(n - 1, 1)) + UP * height / 2)
        self.lifelines = VGroup(*[DashedLine(h.get_bottom(), h.get_bottom() + DOWN * height,
                                             color=style.DIM, stroke_width=2) for h in self.heads])
        self.index = {p: i for i, p in enumerate(participants)}
        self.messages = VGroup()
        self.notes = VGroup()
        # Offsets are distances below the participant boxes, so the diagram
        # can be moved (e.g. sd.next_to(title, DOWN)) before adding messages.
        self.cursor = 0.9                              # where the next message starts
        self.last = {p: 0.3 for p in participants}     # each lifeline's latest event
        self.add(self.lifelines, self.heads, self.messages, self.notes)

    def create(self):
        return AnimationGroup(FadeIn(self.heads), *[Create(l) for l in self.lifelines], lag_ratio=0.1)

    def x_of(self, p: str) -> float:
        return self.lifelines[self.index[p]].get_center()[0]

    def y_at(self, offset: float) -> float:
        return self.heads[0].get_bottom()[1] - offset

    def message(self, src: str, dst: str, text: str, color=style.YELLOW, packet: bool = True,
                run_time: float = 1.5, slant: float = 0.35):
        """Arrow from src to dst at the next row; label sits above it, always upright.
        With packet=True a Packet (labeled with the first word) rides the arrow.
        Returns (animation, VGroup(arrow, label))."""
        y0, y1 = self.cursor, self.cursor + self.step * slant
        self.last[src], self.last[dst] = y0, y1
        self.cursor += self.step
        a = np.array([self.x_of(src), self.y_at(y0), 0])
        b = np.array([self.x_of(dst), self.y_at(y1), 0])
        arrow = Arrow(a, b, buff=0.05, color=color, stroke_width=4, max_tip_length_to_length_ratio=0.06)
        txt = label(text, size=style.SMALL_SIZE + 2, color=color, mono=True)
        angle = arrow.get_angle()
        if abs(angle) > PI / 2:  # right-to-left arrow: keep text upright
            angle -= PI if angle > 0 else -PI
        txt.next_to(arrow.get_center(), UP, buff=0.12).rotate(angle, about_point=arrow.get_center())
        group = VGroup(arrow, txt)
        self.messages.add(group)
        anims = [GrowArrow(arrow, run_time=run_time)]
        if packet:
            anims.append(packet_flight(Packet(text.split()[0], color=color), a, b, run_time=run_time))
        return AnimationGroup(AnimationGroup(*anims), FadeIn(txt, run_time=0.4), lag_ratio=0.85), group

    def note(self, participant: str, text: str, color=style.TEAL, side=None, below: float = 0.0):
        """State label beside a lifeline at that participant's latest event
        (call it right after the message that caused the state change), or at
        the top if nothing happened yet. `below` nudges it down (units).
        Default side: LEFT of the first lifeline, RIGHT of the others.
        Returns (animation, text_mobject)."""
        i = self.index[participant]
        side = side if side is not None else (LEFT if i == 0 else RIGHT)
        t = label(text, size=style.SMALL_SIZE, color=color, mono=True)
        y = self.y_at(self.last[participant] + below)
        t.next_to(np.array([self.x_of(participant), y, 0]), side, buff=0.25)
        self.notes.add(t)
        return FadeIn(t, shift=-side * 0.2), t


def cross_fade(mob, new, run_time: float = 0.6):
    """Fade `mob` out, turn it into `new`, fade it back in, keeping the object itself.

    self.play(cross_fade(count, label("1,000 free"), run_time=0.6))
    Use this to change text in place. Transform between two different strings
    morphs letters into garbled shapes; this never does. Opacities return to the
    new content's own values, so outlined (unfilled) shapes stay unfilled.
    """
    return _CrossFade(mob, new, run_time=run_time)


class _CrossFade(Animation):
    def __init__(self, mobject, new, **kw):
        kw.setdefault("rate_func", linear)
        super().__init__(mobject, **kw)
        self.new = new.copy()
        self.old_ref = mobject.copy()
        self._swapped = False

    @staticmethod
    def _fade(target, ref, f):
        for m, r in zip(target.get_family(), ref.get_family()):
            if hasattr(m, "set_fill") and hasattr(r, "get_fill_opacity"):
                m.set_fill(opacity=r.get_fill_opacity() * f, family=False)
                m.set_stroke(opacity=r.get_stroke_opacity() * f, family=False)

    def interpolate_mobject(self, alpha):
        if alpha < 0.5:
            self._fade(self.mobject, self.old_ref, 1 - 2 * alpha)
            return
        if not self._swapped:
            self.mobject.become(self.new.copy())
            # become() copies geometry, not Text metadata; without this a Text keeps its old
            # string and reports a wrong font size (its initial height belongs to the old text).
            for m, r in zip(self.mobject.get_family(), self.new.get_family()):
                for attr in ("text", "original_text", "initial_height", "_font_size", "_studio_source_tag"):
                    if hasattr(r, attr):
                        setattr(m, attr, getattr(r, attr))
            self._swapped = True
        self._fade(self.mobject, self.new, 2 * alpha - 1)


def beat(t, mark: str | None = None, floor: float = 0.3) -> float:
    """Seconds from now until bookmark `mark` (or the end of the narration), at least `floor`.

    with self.voiceover(text="Then <bookmark mark='ack'/>the server replies.") as t:
        self.play(syn.travel(run_time=beat(t, "ack")))
        self.play(ack.travel(run_time=beat(t)))
    """
    d = t.time_until_bookmark(mark) if mark else t.get_remaining_duration()
    return max(d, floor)


class TimelineMessage(VGroup):
    """One arrow of a Timeline: body (shaft + head), label plate, optional loss ✗.

    Not added to the scene until travel() introduces it. travel() can stop part-way
    (upto=0.6) and resume later (start=0.6) so arrival lands on its spoken beat.
    """

    HEAD = 0.22

    def __init__(self, a, b, text, color, dashed=False, lost_at=None, label_at=0.25,
                 size=22, mono=True, **kw):
        super().__init__(**kw)
        self.start = np.array(a, dtype=float)
        self.full_end = np.array(b, dtype=float)
        self.lost_at = lost_at
        frac = 1.0 if lost_at is None else float(lost_at)
        self.end = self.start + (self.full_end - self.start) * frac
        self.direction = (self.full_end - self.start) / np.linalg.norm(self.full_end - self.start)
        self.color, self.size, self.mono = color, size, mono
        shaft_end = self.end - self.direction * self.HEAD * 0.6
        total = float(np.linalg.norm(shaft_end - self.start))
        if dashed:
            dash, gap = 0.14, 0.11
            n = max(int(total // (dash + gap)), 4)
            step = total / n
            self._segs = [(i * step / total, min((i * step + step * dash / (dash + gap)) / total, 1.0))
                          for i in range(n)]
        else:
            self._segs = [(0.0, 1.0)]
        self._shaft = (self.start, shaft_end)
        self.dashes = VGroup(*[Line(self.start, shaft_end, color=color, stroke_width=4) for _ in self._segs])
        n_vec = np.array([-self.direction[1], self.direction[0], 0.0])
        base = self.end - self.HEAD * self.direction
        self.head = Polygon(self.end, base + 0.5 * self.HEAD * n_vec, base - 0.5 * self.HEAD * n_vec,
                            color=color, stroke_width=1, fill_color=color, fill_opacity=1)
        self._tip = self.end.copy()
        self.body = VGroup(self.dashes, self.head)
        self.label = self._make_label(text, color)
        anchor = self.start + (self.end - self.start) * label_at
        self.label.move_to(anchor + UP * (0.1 + self.label.height / 2))
        self.cross = None
        if lost_at is not None:
            self.cross = Text("✗", font=style.FONT, font_size=40, color=style.RED)
            self.cross.move_to(self.end + self.direction * 0.32)
        self.add(self.body)
        self._progress = 0.0
        self.set_progress(0.0)

    @property
    def text(self):
        return self.label[1]

    def _make_label(self, text, color):
        if not text:
            return VGroup(Rectangle(width=0.01, height=0.01, stroke_width=0, fill_opacity=0), VGroup())
        if isinstance(text, str):
            body = label(text, size=self.size, color=color, mono=self.mono)
        else:  # one Text coloured by ranges keeps a shared baseline and spacing
            body = rich_text(text, size=self.size, mono=self.mono, color=color)
        plate = Rectangle(width=body.width + 0.16, height=body.height + 0.1, stroke_width=0,
                          fill_color=style.BG, fill_opacity=1).move_to(body)
        plate.set_z_index(1)
        body.set_z_index(2)
        return VGroup(plate, body)

    def head_tip(self):
        return self._tip

    def set_progress(self, p: float):
        """Show the first fraction p (0..1) of the visible path; the head rides the tip."""
        p = min(max(float(p), 0.0), 1.0)
        s, e = self._shaft
        path = float(np.linalg.norm(self.end - self.start))
        shaft = float(np.linalg.norm(e - s))
        q = min(max((p * path - (path - shaft)) / shaft, 0.0), 1.0) if p < 1.0 else 1.0  # shaft trails the head
        for (s0, s1), line in zip(self._segs, self.dashes):
            v = min(max((q - s0) / max(s1 - s0, 1e-9), 0.0), 1.0)
            a = s + (e - s) * s0
            b = s + (e - s) * (s0 + (s1 - s0) * max(v, 1e-4))
            line.set_points_as_corners([a, b])
            line.set_stroke(opacity=1.0 if v > 0 else 0.0)
        tip = self.start + (self.end - self.start) * p
        self.head.shift(tip - self._tip)
        self._tip = tip
        shown = 1.0 if p > 0.03 else 0.0
        self.head.set_fill(opacity=shown).set_stroke(opacity=shown)
        self._progress = p

    def travel(self, run_time: float = 1.0, upto: float = 1.0, start: float | None = None,
               delay: float = 0.0, label: bool = True):
        """Animate the arrow from `start` (default: where it stopped) to `upto` of its path.
        The label fades in with the first travel; a lost message's ✗ appears on arrival."""
        f0 = self._progress if start is None else start
        anims = [_Travel(self, f0, upto, run_time=run_time)]
        if label:
            anims.append(FadeIn(self.label, run_time=min(0.4, run_time)))
        if self.cross is not None and upto >= 1.0:
            anims.append(Succession(Wait(run_time * 0.8), FadeIn(self.cross, run_time=run_time * 0.2)))
        group = AnimationGroup(*anims) if len(anims) > 1 else anims[0]
        return Succession(Wait(delay), group) if delay > 0 else group

    def relabel(self, text, color=None, run_time: float = 0.6):
        """Cross-fade the label to new text in place (same centre)."""
        new = self._make_label(text, color or self.text.get_color()).move_to(self.label)
        return cross_fade(self.label, new, run_time=run_time)

    def retint(self, color):
        """Animations recolouring the arrow (e.g. genuine → retransmit)."""
        self.color = color
        return [self.dashes.animate.set_color(color), self.head.animate.set_color(color)]

    def parts(self):
        return [m for m in (self.body, self.label, self.cross) if m is not None]


class _Travel(Animation):
    def __init__(self, message, f0, f1, **kw):
        kw.setdefault("rate_func", linear)
        kw.setdefault("introducer", True)
        super().__init__(message.body, **kw)
        self.message, self.f0, self.f1 = message, f0, f1

    def interpolate_mobject(self, alpha):
        self.message.set_progress(self.f0 + (self.f1 - self.f0) * alpha)


class Timeline(VGroup):
    """Vertical lifelines (time flows down) with messages that travel on cue.

    tl = Timeline(("Client", "Server"))              # BLUE left, TEAL right
    self.play(tl.create())
    syn = tl.message(0, "Client", "Server", [("SYN", style.GOLD), ("seq 1000", style.FG)])
    self.play(syn.travel(run_time=beat(t, "reply")))
    ack = tl.message(1, "Server", "Client", "ACK 1101", lost_at=0.55)   # stops short + ✗
    old = tl.message(2, "Client", "Server", "Hi, 13", kind="old")       # DIM dashed
    resent = tl.message(3, "Client", "Server", "Data 2", kind="retransmit")  # YELLOW
    self.play(FadeIn(tl.note(1, "Server", "SYN_RCVD")), FadeIn(tl.legend()))
    self.play(*tl.clear(syn, ack))                    # make room before rows run out

    Rows are fixed slots `row` units apart, so row i always sits at the same height.
    A row whose arrival falls below `bottom` raises ValueError instead of leaving
    the frame. Labels sit above their arrow on a background plate and never rotate.
    Prefer this over SequenceDiagram for protocol exchanges.
    """

    KINDS = {"genuine": (style.FG, False), "old": (style.DIM, True), "retransmit": (style.YELLOW, False)}
    LEGEND = {"old": "old duplicate", "genuine": "genuine", "retransmit": "resent"}

    def __init__(self, participants, x=None, top: float = 2.6, bottom: float = -3.0, row: float = 0.85,
                 slant: float = 0.3, colors=None, subtitles=None, name_size: int = 26,
                 first_row: float = 0.45, **kw):
        super().__init__(**kw)
        n = len(participants)
        if n < 2:
            raise ValueError("Timeline needs at least two participants")
        span = 6.0 if n == 2 else 9.0
        xs = [float(v) for v in x] if x is not None else list(np.linspace(-span / 2, span / 2, n))
        if len(xs) != n:
            raise ValueError("x must give one position per participant")
        palette = colors or [style.BLUE, style.TEAL, style.PURPLE, style.GOLD, style.GREEN]
        self.slant, self.row, self.bottom = slant, row, bottom
        self.index = {p: i for i, p in enumerate(participants)}
        self.xs = xs
        self.heads = VGroup()
        self.subtitles = VGroup()
        line_top = top - 0.35
        for i, p in enumerate(participants):
            col = palette[i % len(palette)]
            head = label(p, size=name_size, color=col).move_to(np.array([xs[i], top, 0.0]))
            self.heads.add(head)
            if subtitles and subtitles[i]:
                sub = label(subtitles[i], size=style.SMALL_SIZE, color=style.DIM).next_to(head, DOWN, buff=0.06)
                self.subtitles.add(sub)
                line_top = min(line_top, sub.get_bottom()[1] - 0.12)
        self.lifelines = VGroup(*[
            Line(np.array([xs[i], line_top, 0.0]), np.array([xs[i], bottom, 0.0]),
                 color=palette[i % len(palette)], stroke_width=3, stroke_opacity=0.55)
            for i in range(n)])
        self.y0 = line_top - first_row
        self.add(self.lifelines, self.heads, self.subtitles)

    def create(self):
        return AnimationGroup(FadeIn(self.heads), FadeIn(self.subtitles),
                              *[Create(l) for l in self.lifelines], lag_ratio=0.1)

    def x_of(self, participant: str) -> float:
        return self.xs[self.index[participant]]

    def y(self, row: float) -> float:
        """Height where a message in this row leaves its sender."""
        return self.y0 - row * self.row

    def message(self, row: float, src: str, dst: str, text, kind: str = "genuine", color=None,
                lost_at: float | None = None, label_at: float = 0.25, size: int = 22,
                mono: bool = True, slant: float | None = None) -> TimelineMessage:
        """Build (not show) a message arrow in `row`. text: str or [(text, colour), ...].
        kind: genuine (FG solid) | old (DIM dashed) | retransmit (YELLOW solid).
        lost_at: fraction of the way at which it stops, with a RED ✗."""
        if kind not in self.KINDS:
            raise ValueError(f"kind must be one of {sorted(self.KINDS)}")
        base, dashed = self.KINDS[kind]
        sl = self.slant if slant is None else slant
        a = np.array([self.x_of(src), self.y(row), 0.0])
        b = np.array([self.x_of(dst), self.y(row) - sl, 0.0])
        if b[1] < self.bottom - 1e-6:
            raise ValueError(f"row {row} arrives below the lifelines; clear() earlier rows or raise bottom")
        return TimelineMessage(a, b, text, color or base, dashed=dashed, lost_at=lost_at,
                               label_at=label_at, size=size, mono=mono)

    def note(self, row: float, participant: str, text: str, color=style.GOLD, size: int = 22,
             at: str = "end", side=None):
        """State or side label just outside a lifeline, level with a message's arrival
        (at="end") or departure (at="start"). Default side: left of the leftmost lifeline,
        right of the others. Returns the Text (FadeIn it yourself)."""
        i = self.index[participant]
        right = (i != 0) if side is None else bool(np.allclose(np.array(side, dtype=float), RIGHT))
        y = self.y(row) - (self.slant if at == "end" else 0.0)
        t = label(text, size=size, color=color, mono=True)
        x = self.xs[i] + (0.2 if right else -0.2)
        t.move_to(np.array([x, y, 0.0]))
        t.align_to(np.array([x, y, 0.0]), LEFT if right else RIGHT)
        return t

    def legend(self, kinds=("old", "genuine"), top_right=(6.3, 3.3)):
        """Sample arrows with their meaning, e.g. dashed = 'old duplicate'."""
        rows = VGroup()
        for k in kinds:
            col, dashed = self.KINDS[k]
            a, b = np.array([0.0, 0.0, 0.0]), np.array([0.7, 0.0, 0.0])
            sample = TimelineMessage(a, b, None, col, dashed=dashed, label_at=0.0)
            sample.set_progress(1.0)
            text = label(self.LEGEND[k], size=style.SMALL_SIZE, color=col)
            rows.add(VGroup(sample.body, text.next_to(sample.body, RIGHT, buff=0.15)))
        rows.arrange(DOWN, aligned_edge=LEFT, buff=0.18)
        rows.shift(np.array([top_right[0] - rows.get_right()[0], top_right[1] - rows.get_top()[1], 0.0]))
        return rows

    def clear(self, *messages, run_time: float = 0.4):
        """FadeOut animations for these messages (body, label and ✗)."""
        return [FadeOut(p, run_time=run_time) for m in messages for p in m.parts()]


# --------------------------------------------------------------------------- #
class SlideImage(Group):
    """A source slide PNG with a thin border; highlight regions in slide coords.

    s = SlideImage(Path(__file__).parent / "source/slides/slide-003.png", height=6)  # in scenes.py
    self.play(FadeIn(s)); self.play(Create(s.highlight(0.1, 0.3, 0.9, 0.45)))
    Coordinates are fractions of the slide: (0,0)=top-left, (1,1)=bottom-right.
    """

    def __init__(self, path: str | Path, height: float = 6.0, border_color=style.DIM, **kw):
        super().__init__(**kw)
        from PIL import Image  # RGB PNGs (e.g. from pymupdf) crash Manim; force RGBA
        rgba = np.array(Image.open(path).convert("RGBA"))
        self._rgb = rgba[..., :3].astype(np.int16)
        self.image = ImageMobject(rgba).set_height(height)
        self.border = Rectangle(width=self.image.width, height=self.image.height,
                                stroke_color=border_color, stroke_width=2)
        self.add(self.image, self.border)

    def region_point(self, fx: float, fy: float):
        ul = self.border.get_corner(UP + LEFT)
        return ul + RIGHT * fx * self.border.width + DOWN * fy * self.border.height

    def _blobs(self):
        """Connected content regions of the slide (cached): (label image, per-label bbox and size)."""
        if getattr(self, "_blob_cache", None) is None:
            from scipy import ndimage
            rgb = self._rgb
            h, w = rgb.shape[:2]
            m = max(2, int(0.01 * min(w, h)))
            edge = np.concatenate([rgb[:m].reshape(-1, 3), rgb[-m:].reshape(-1, 3),
                                   rgb[:, :m].reshape(-1, 3), rgb[:, -m:].reshape(-1, 3)])
            mask = np.abs(rgb - np.median(edge, axis=0)).max(axis=2) > 40
            r = max(1, int(0.004 * w))  # join letters into words/lines, not separate pictures
            joined = ndimage.binary_dilation(mask, iterations=r)
            labels, n = ndimage.label(joined)
            labels[~mask] = 0  # measure real content pixels only
            objs = ndimage.find_objects(labels)
            sizes = np.bincount(labels.ravel(), minlength=n + 1)
            self._blob_cache = (labels, objs, sizes)
        return self._blob_cache

    @staticmethod
    def _pieces(blob, gutter: float = 0.12):
        """Split one object's pixel mask at thin joins (an arrow between two pictures): runs of
        columns, then rows, whose content density is below `gutter`. Yields (r0, r1, c0, c1)."""
        def runs(profile, span):
            solid = profile >= gutter * span
            idx = np.flatnonzero(np.diff(np.r_[0, solid.astype(int), 0]))
            return list(zip(idx[::2], idx[1::2]))
        h, w = blob.shape
        for c0, c1 in runs(blob.sum(0), h) or [(0, w)]:
            part = blob[:, c0:c1]
            for r0, r1 in runs(part.sum(1), c1 - c0) or [(0, h)]:
                if part[r0:r1].any():
                    yield r0, r1, c0, c1

    def snap(self, x0: float, y0: float, x1: float, y1: float, pad: float = 0.012, keep: float = 0.5):
        """Tighten a rough region to whole slide objects (photos, text lines, shapes): the box covers
        every object with at least `keep` of its pixels inside the region. Objects mostly outside
        (a title rule, a neighbor the region clips) are left out, so the box never cuts through one.
        Objects joined by a thin connector (picture → arrow → picture) are judged piece by piece;
        thin full-width rules are ignored. If nothing is mostly inside, the single object the region
        covers best (>= 25%) is used, else the region itself. Returns slide fractions."""
        labels, objs, sizes = self._blobs()
        h, w = labels.shape
        X0, X1 = sorted((int(x0 * w), int(round(x1 * w))))
        Y0, Y1 = sorted((int(y0 * h), int(round(y1 * h))))
        inside = np.bincount(labels[Y0:Y1, X0:X1].ravel(), minlength=len(sizes))
        min_px = 0.0005 * w * h  # ignore specks
        boxes, partial = [], []  # partial: (inside share, box) of objects below `keep`

        def consider(box, share):
            r0, r1, c0, c1 = box
            region = labels[r0:r1, c0:c1] > 0
            if r1 - r0 < 0.03 * h and c1 - c0 > 0.3 * w and region.mean() > 0.6:
                return  # a solid decorative rule (under a title); text lines are much sparser
            (boxes if share >= keep else partial).append((share, box) if share < keep else box)
        for i in np.flatnonzero(inside):
            if not i or sizes[i] < min_px:
                continue
            rs, cs = objs[i - 1]
            if inside[i] >= keep * sizes[i]:
                consider((rs.start, rs.stop, cs.start, cs.stop), 1.0)
                continue
            blob = labels[rs, cs] == i
            for r0, r1, c0, c1 in self._pieces(blob):
                piece = blob[r0:r1, c0:c1]
                tot = piece.sum()
                if tot < min_px:
                    continue
                gr0, gr1, gc0, gc1 = rs.start + r0, rs.start + r1, cs.start + c0, cs.start + c1
                ir0, ir1, ic0, ic1 = max(gr0, Y0), min(gr1, Y1), max(gc0, X0), min(gc1, X1)
                ins = piece[ir0 - gr0:max(ir1 - gr0, 0), ic0 - gc0:max(ic1 - gc0, 0)].sum() if ir1 > ir0 and ic1 > ic0 else 0
                if ins:
                    sub = np.argwhere(piece)
                    consider((gr0 + sub[:, 0].min(), gr0 + sub[:, 0].max() + 1,
                              gc0 + sub[:, 1].min(), gc0 + sub[:, 1].max() + 1), ins / tot)
        if not boxes:  # nothing mostly inside: take the object the region covers best, if any
            best = max(partial, default=None)
            if best is None or best[0] < 0.25:
                return x0, y0, x1, y1
            boxes = [best[1]]
        top = min(b[0] for b in boxes); bot = max(b[1] for b in boxes)
        left = min(b[2] for b in boxes); right = max(b[3] for b in boxes)
        return (max(left / w - pad, 0), max(top / h - pad, 0), min(right / w + pad, 1), min(bot / h + pad, 1))

    def highlight(self, x0: float, y0: float, x1: float, y1: float, color=style.YELLOW,
                  snap: bool = True) -> Rectangle:
        """Box a slide region. Rough fractions are fine: with snap=True (default) the box hugs the
        content inside the region and never cuts through a photo or text line. Don't Indicate or
        scale the returned box (it would no longer match the slide); FadeOut/Create it instead."""
        if snap:
            x0, y0, x1, y1 = self.snap(x0, y0, x1, y1)
        p0, p1 = self.region_point(x0, y0), self.region_point(x1, y1)
        r = Rectangle(width=abs(p1[0] - p0[0]), height=abs(p1[1] - p0[1]), stroke_color=color, stroke_width=4)
        return r.move_to((p0 + p1) / 2)


# --------------------------------------------------------------------------- #
def packet_route(mob, points, run_time: float = 2.0):
    """Move `mob` along a polyline through `points` (points or mobjects), e.g.
    host -> down to a LAN bus -> along the bus -> up to a router:

        self.play(packet_route(pkt, [e1, bus_pt(e1), bus_pt(r1), r1], run_time=2))
    The mobject jumps to the first point; use FadeIn/FadeOut around it as needed."""
    pts = [_point(p) for p in points]
    path = VMobject().set_points_as_corners(pts)
    mob.move_to(pts[0])
    return MoveAlongPath(mob, path, run_time=run_time)


# --------------------------------------------------------------------------- #
class FieldBar(VGroup):
    """Horizontal bar split into labeled fields: address bit layouts, header
    stacks (DH|NH|TH|AH), header rows, fragment bars.

    bar = FieldBar([("0", 1), ("net", 7), ("host", 24)], unit=0.28,
                   colors=[style.GOLD, style.BLUE, style.TEAL],
                   captions=["", "1 byte", "3 bytes"])          # captions sit above
    self.play(FadeIn(bar)); self.play(bar.highlight(1)); self.play(bar.set_text(2, "169.32"))
    bar.field(2) -> VGroup(rect, text); bar.rects / bar.texts / bar.captions
    Each field is (text, width) or (text, width, color); width is in `unit`s.
    """

    def __init__(self, fields, unit: float = 0.3, height: float = 0.6, colors=None,
                 size: int = style.LABEL_SIZE, mono: bool = True, fill_opacity: float = 0.25,
                 captions: list[str] | None = None, caption_size: int = style.SMALL_SIZE,
                 text_color=style.FG, **kw):
        super().__init__(**kw)
        self.size, self.mono, self.text_color = size, mono, text_color
        self.rects, self.texts, self.fields_ = VGroup(), VGroup(), VGroup()
        for i, f in enumerate(fields):
            text, w = f[0], f[1]
            color = f[2] if len(f) > 2 else (colors[i % len(colors)] if colors else style.BLUE)
            rect = Rectangle(width=w * unit, height=height, stroke_color=color, stroke_width=2.5,
                             fill_color=color, fill_opacity=fill_opacity)
            self.rects.add(rect)
        self.rects.arrange(RIGHT, buff=0)
        for rect, f in zip(self.rects, fields):
            t = label(str(f[0]), size=size, color=text_color, mono=mono).move_to(rect)
            self.texts.add(t)
            self.fields_.add(VGroup(rect, t))
        self.add(self.fields_)
        self.captions = VGroup()
        if captions:
            for rect, c in zip(self.rects, captions):
                if c:
                    self.captions.add(label(c, size=caption_size, color=style.DIM).next_to(rect, UP, buff=0.12))
            self.add(self.captions)

    def field(self, i: int) -> VGroup:
        return self.fields_[i]

    def highlight(self, i: int, color=style.YELLOW, opacity: float = 0.6):
        return self.rects[i].animate.set_fill(color, opacity=opacity).set_stroke(color)

    def set_text(self, i: int, value: str, color=None):
        old = self.texts[i]
        new = label(str(value), size=self.size, color=color or self.text_color, mono=self.mono).move_to(old)
        return Transform(old, new)


# --------------------------------------------------------------------------- #
class PrefixTrie(VGroup):
    """Binary (unibit) trie built from {name: bitstring} prefixes ("" = root / *).
    Nodes on the path to a prefix are created automatically; a node storing a
    prefix shows its name. Edge bit labels: 0 goes left, 1 goes right.

    trie = PrefixTrie({"P1": "", "P2": "1", "P3": "00", "P6": "1000"}, x_unit=1.2, y_unit=0.7)
    self.play(FadeIn(trie))
    self.play(trie.visit("10"))            # light the edge "1"->"10" and node "10"
    trie.node("1000") -> VGroup(circle, name?) ; trie.edge("10") -> VGroup(line, bit)
    """

    def __init__(self, prefixes: dict[str, str], x_unit: float = 1.2, y_unit: float = 0.75,
                 radius: float = 0.28, color=style.DIM, prefix_color=style.TEAL, **kw):
        super().__init__(**kw)
        names = {bits: name for name, bits in prefixes.items()}
        keys = {""}
        for bits in prefixes.values():
            keys |= {bits[:k] for k in range(len(bits) + 1)}
        self.keys = keys
        # layout: leaves get consecutive slots (in order); parents centre over children
        xs: dict[str, float] = {}
        slot = [0.0]

        def place(b: str) -> float:
            kids = [b + c for c in "01" if b + c in keys]
            if not kids:
                xs[b] = slot[0]; slot[0] += 1
            elif len(kids) == 2:
                xs[b] = (place(kids[0]) + place(kids[1])) / 2
            else:
                k = kids[0]
                xs[b] = place(k) + (0.5 if k.endswith("0") else -0.5)
            return xs[b]

        place("")
        xmid = (min(xs.values()) + max(xs.values())) / 2
        depth = max(len(k) for k in keys)
        self.nodes: dict[str, VGroup] = {}
        self.edges: dict[str, VGroup] = {}
        node_layer, edge_layer = VGroup(), VGroup()
        for b in sorted(keys, key=lambda k: (len(k), k)):
            pos = np.array([(xs[b] - xmid) * x_unit, (depth / 2 - len(b)) * y_unit, 0])
            has = b in names
            circ = Circle(radius=radius, stroke_color=prefix_color if has else color, stroke_width=2.5,
                          fill_color=style.PANEL, fill_opacity=1).move_to(pos)
            g = VGroup(circ)
            if has:
                # Keep the stored prefix visible when visit() animates its circle.
                g.add(label(names[b], size=style.SMALL_SIZE, color=style.FG).move_to(pos).set_z_index(2))
            self.nodes[b] = g
            node_layer.add(g)
            if b:
                parent = self.nodes[b[:-1]][0]
                line = Line(parent.get_center(), circ.get_center(), buff=radius, color=color, stroke_width=2.5)
                side = LEFT if b.endswith("0") else RIGHT
                bit = label(b[-1], size=style.SMALL_SIZE, color=style.GOLD).next_to(line.get_center(), side + UP * 0.3, buff=0.08)
                e = VGroup(line, bit)
                self.edges[b] = e
                edge_layer.add(e)
        self.add(edge_layer, node_layer)

    def node(self, bits: str) -> VGroup:
        return self.nodes[bits]

    def edge(self, bits: str) -> VGroup:
        return self.edges[bits]

    def visit(self, bits: str, color=style.YELLOW):
        """Highlight the node for `bits` (and the edge into it, if not the root)."""
        anims = [self.nodes[bits][0].animate.set_stroke(color, width=5)]
        if bits:
            anims.append(self.edges[bits][0].animate.set_stroke(color, width=5))
        return AnimationGroup(*anims)


# High-level layouts. Geometry is measured, never estimated from character counts.
def _text_floor(mob, factor=1.0):
    return all(float(t.font_size) * factor >= 19.99
               for t in mob.get_family() if isinstance(t, Text))


def fit_to_frame(mobject, margin: float = 0.15):
    """Mutate/return a mob inside the centered 13×7 safe area.

    fit_to_frame(table, margin=.2); self.play(FadeIn(table))
    Oversized text layouts raise ValueError instead of shrinking below 20 pt;
    split those layouts across beats. Call again after any manual positioning.
    """
    if not 0 <= margin < 3.5:
        raise ValueError('margin must be between 0 and 3.5')
    w, h = 13 - 2 * margin, 7 - 2 * margin
    factor = min(1, w / max(mobject.width, .001), h / max(mobject.height, .001))
    if not _text_floor(mobject, factor):
        raise ValueError('Layout needs text below 20 pt; split it across beats')
    mobject.scale(factor)
    x, y, _ = mobject.get_center()
    mobject.shift(RIGHT * (np.clip(x, -w/2 + mobject.width/2, w/2 - mobject.width/2) - x)
                 + UP * (np.clip(y, -h/2 + mobject.height/2, h/2 - mobject.height/2) - y))
    return mobject


def _overlaps(a, b, gap=0.0):
    return (a.get_left()[0] < b.get_right()[0] + gap
            and a.get_right()[0] > b.get_left()[0] - gap
            and a.get_bottom()[1] < b.get_top()[1] + gap
            and a.get_top()[1] > b.get_bottom()[1] - gap)


def keep_clear_of_tag(mobject, tag, gap: float = .18, margin: float = .15):
    """Move content above (or left of) tag, preserving ≥20 pt; raise if impossible.

    keep_clear_of_tag(diagram, tag); self.play(FadeIn(diagram))
    Uses bounding boxes, including rotated labels. Reapply after transforms.
    """
    fit_to_frame(mobject, margin)
    if not _overlaps(mobject, tag, gap):
        return mobject
    for delta in (UP * (tag.get_top()[1] + gap - mobject.get_bottom()[1]),
                  LEFT * (mobject.get_right()[0] - tag.get_left()[0] + gap)):
        candidate = mobject.copy().shift(delta)
        fit_to_frame(candidate, margin)
        if not _overlaps(candidate, tag, gap):
            return mobject.shift(candidate.get_center() - mobject.get_center())
    raise ValueError('No readable space clear of source tag; split the beat')


def _wrapped(text, width, size=24, color=style.FG, mono=False):
    if width <= 0 or size < 20:
        raise ValueError('Text needs positive width and size >= 20')
    lines = []
    for paragraph in str(text).split('\n'):
        line = ''
        for word in paragraph.split():
            trial = f'{line} {word}'.strip()
            if label(trial, size=size, mono=mono).width <= width:
                line = trial
            else:
                if line:
                    lines.append(line)
                if label(word, size=size, mono=mono).width > width:
                    raise ValueError(f'Unbreakable word exceeds width: {word!r}')
                line = word
        lines.append(line)
    # One Text preserves Transform semantics and exposes its effective font size.
    return label('\n'.join(lines), size=size, color=color, mono=mono, line_spacing=.8)


def definition_card(term, meaning, width: float = 7, size: int = 26, color=style.BLUE):
    """Return VGroup(panel, term, meaning), wrapped without shrinking text.

    card = definition_card('Next hop', 'The neighbor receiving this packet next.')
    with self.voiceover(text='A next hop is the neighbor receiving this packet next.'):
        self.play(FadeIn(card))
    self.play(FadeOut(card))  # then demonstrate it on the relevant topology
    """
    title = _wrapped(term, width - .6, max(size, 28), color)
    body = _wrapped(meaning, width - .6, size)
    content = VGroup(title, body).arrange(DOWN, aligned_edge=LEFT, buff=.25)
    panel = RoundedRectangle(width=width, height=content.height + .6, corner_radius=.15,
                             fill_color=style.PANEL, fill_opacity=1, stroke_color=color)
    content.move_to(panel)
    return fit_to_frame(VGroup(panel, title, body))


class SourceTag(VGroup):
    """A persistent citation. self.play(tag.set('Added explanation')).

    tag = SourceTag('IP Forwarding · slide 16'); self.add(tag)
    self.play(tag.set('Added example · based on slide 16'))
    Re-run keep_clear_of_tag(content, tag) after a longer citation is set.
    """
    def __init__(self, text, **kw):
        super().__init__(**kw)
        self.add(self._make(text))
        self._studio_source_tag = True

    @staticmethod
    def _make(text):
        mob = _wrapped(text, 6, 20, style.DIM)
        mob._studio_source_tag = True
        mob.shift(RIGHT * (6.35 - mob.get_right()[0]) + UP * (-3.35 - mob.get_bottom()[1]))
        return fit_to_frame(mob)

    def set(self, text):
        """Cross-fade to a new citation (a Transform would morph the letters)."""
        return cross_fade(self[0], self._make(text), run_time=0.5)


def slide_excerpt(scene, path, regions, tag_text, hold: float = 1.0):
    """Play a short slide beat and remove only its own objects (returns None).

    slide_excerpt(self, SRC/'slide-001.png', [(.1,.2,.8,.4)], 'Deck · slide 1')
    regions use SlideImage fractions; hold is seconds per region (or slide).
    Place this inside a voiceover block; the caller owns the narration.
    """
    if hold < 0:
        raise ValueError('hold must be nonnegative')
    regions = list(regions)
    for r in regions:
        if len(r) != 4 or not (0 <= r[0] < r[2] <= 1 and 0 <= r[1] < r[3] <= 1):
            raise ValueError('regions must be ordered fractions in [0,1]')
    tag = SourceTag(tag_text)
    slide = keep_clear_of_tag(SlideImage(path, height=5.5), tag)
    scene.play(FadeIn(slide), FadeIn(tag), run_time=.4)
    box = None
    for region in regions:
        new = slide.highlight(*region)
        scene.play(*([FadeOut(box)] if box is not None else []), Create(new), run_time=.3)
        scene.wait(hold)
        box = new
    if not regions:
        scene.wait(hold)
    scene.play(FadeOut(slide), FadeOut(tag), *([FadeOut(box)] if box is not None else []), run_time=.4)


class FlowSteps(VGroup):
    """Numbered, wrapped steps; self.play(flow.highlight(1)) selects step two.

    flow = FlowSteps(['Read destination', 'Find longest matching prefix', 'Forward'])
    self.play(FadeIn(flow)); self.play(flow.highlight(0))
    Raises for too many steps; split them into separate beats. Zero-based API.
    """
    def __init__(self, steps, width=9, size=26, numbered=True, mono=False, **kw):
        super().__init__(**kw)
        if not steps:
            raise ValueError('steps must not be empty')
        self.rows = VGroup()
        for i, text in enumerate(steps):
            txt = _wrapped(f'{i+1}. {text}' if numbered else text, width-.5, size, mono=mono)
            box = RoundedRectangle(width=width, height=txt.height+.3, corner_radius=.08,
                                   stroke_color=style.DIM, fill_color=style.PANEL, fill_opacity=1)
            txt.move_to(box).align_to(box, LEFT).shift(RIGHT*.25).set_z_index(2)
            self.rows.add(VGroup(box, txt))
        self.rows.arrange(DOWN, buff=.14)
        self.add(self.rows)
        fit_to_frame(self)

    def highlight(self, i, color=style.YELLOW):
        if not 0 <= i < len(self.rows):
            raise IndexError(i)
        return AnimationGroup(*[row[0].animate.set_stroke(color if j == i else style.DIM)
                                 .set_fill(color if j == i else style.PANEL, opacity=.25 if j == i else 1)
                                 for j, row in enumerate(self.rows)])


class Pseudocode(FlowSteps):
    """Monospace numbered stepper. Pseudocode(['p = lookup(dst)', 'send(p)'])."""
    def __init__(self, lines, **kw):
        super().__init__(lines, mono=True, **kw)


class PrefixTable(MemoryTable):
    """LPM table for binary prefixes ('100*', '*') OR IP CIDR rows.

    table = PrefixTable([('100*','link 6'), ('1*','link 2'), ('*','default')])
    self.play(table.highlight_matches('1001'))
    self.play(table.show_winner('1001')); winner = table.winner('1001')
    winner is a zero-based row or None; equal lengths choose the first row.
    Never mix binary and CIDR rows. No implicit default route is invented.
    """
    def __init__(self, rows, headers=None, size=24, **kw):
        from ipaddress import ip_network
        rows = [list(r) for r in rows]
        if not rows or any(len(r) != 2 for r in rows) or size < 20:
            raise ValueError('Use nonempty (prefix, output) rows and size >=20')
        self.prefixes = [str(r[0]) for r in rows]
        self.cidr = any('/' in p for p in self.prefixes)
        if self.cidr:
            self.networks = [ip_network(p, strict=False) for p in self.prefixes]
            if len({n.version for n in self.networks}) != 1:
                raise ValueError('Use a single IP version')
            self.lengths = [n.prefixlen for n in self.networks]
        else:
            if any(not p or any(c not in '01' for c in p.removesuffix('*')) for p in self.prefixes):
                raise ValueError('Binary prefixes contain 0/1 with an optional trailing *')
            self.lengths = [len(p.removesuffix('*')) for p in self.prefixes]
        heads = headers or ['prefix', 'output']
        widths = [max(label(str(r[c]), size=size, mono=True).width for r in rows + [heads])+.45
                  for c in range(2)]
        kw.setdefault('col_width', widths)
        super().__init__(rows, headers=heads, size=size, **kw)
        for row in self.grid:
            for cell in row:
                if cell[1].width > cell[0].width-.15 or cell[1].height > cell[0].height-.08:
                    raise ValueError('Cell too small; increase col_width/row_height')
                cell[1].set_z_index(2)
        fit_to_frame(self)

    def matching_rows(self, destination):
        if self.cidr:
            from ipaddress import ip_address
            address = ip_address(destination)
            return [i for i, n in enumerate(self.networks) if address in n]
        if not destination or any(c not in '01' for c in destination):
            raise ValueError('destination must be a nonempty binary string')
        return [i for i, p in enumerate(self.prefixes) if destination.startswith(p.removesuffix('*'))]

    def winner(self, destination):
        return max(self.matching_rows(destination), key=lambda i: self.lengths[i], default=None)

    def highlight_matches(self, destination, color=style.YELLOW):
        matches = self.matching_rows(destination)
        return AnimationGroup(*[self.highlight_row(i, color if i in matches else style.BG,
                                                   opacity=.3 if i in matches else 0)
                                for i in range(len(self.cells))])

    def show_winner(self, destination, color=style.GREEN):
        winner = self.winner(destination)
        return AnimationGroup(*[self.highlight_row(i, color if i == winner else style.BG,
                                                   opacity=.4 if i == winner else 0)
                                for i in range(len(self.cells))])


ForwardingTable = PrefixTable


class TernaryTable(PrefixTable):
    """Fixed-width 0/1/* parallel comparator; priority is explicit row order.

    t = TernaryTable([('10**','A'), ('1*0*','B'), ('****','default')])
    self.play(t.highlight_matches('1001'))  # every matching row, simultaneously
    self.play(t.show_winner('1001'))       # first match; sort LPM rows longest first
    Arbitrary ternary masks do not imply longest-prefix semantics.
    """
    def __init__(self, rows, **kw):
        rows = list(rows)
        if not rows or len({len(r[0]) for r in rows}) != 1 or not rows[0][0]:
            raise ValueError('Ternary patterns need equal nonzero widths')
        if any(any(c not in '01*' for c in r[0]) for r in rows):
            raise ValueError('Use only 0, 1, *')
        patterns = [r[0] for r in rows]
        size = kw.get('size', 24)
        kw.setdefault('col_width', [max(label(p, size=size, mono=True).width for p in patterns)+.5,
                                    max(label(str(r[1]), size=size, mono=True).width for r in rows)+1.2])
        # Use the validated MemoryTable layout without binary prefix parsing.
        super().__init__([('*', r[1]) for r in rows], **kw)
        self.patterns = patterns
        for i, pattern in enumerate(patterns):
            cell = self.cell(i, 0)
            text = label(pattern, size=self.size, mono=True).move_to(cell)
            if text.width > cell[0].width-.15:
                raise ValueError('Increase col_width for ternary patterns')
            cell[1].become(text).set_z_index(2)
        self.lengths = [0]*len(rows)

    def matching_rows(self, destination):
        if len(destination) != len(self.patterns[0]) or any(c not in '01' for c in destination):
            raise ValueError('Destination must have the ternary pattern width and only 0/1')
        return [i for i,p in enumerate(self.patterns)
                if all(a == '*' or a == b for a,b in zip(p,destination))]


class BitString(FieldBar):
    """Readable prefix/host split. BitString('10010011', prefix=3).

    bits = BitString('10010011', 3); self.play(bits.highlight(0))
    Widths grow to fit labels even for a one-bit field; this is not to scale.
    """
    def __init__(self, bits, prefix, size=24, **kw):
        if not bits or any(c not in '01' for c in bits) or not 0 <= prefix <= len(bits) or size < 20:
            raise ValueError('Use binary bits, valid prefix length and size >=20')
        fields, captions = [], []
        for text, caption, color in [(bits[:prefix], f'prefix /{prefix}', style.BLUE),
                                     (bits[prefix:], 'remaining bits', style.TEAL)]:
            if text:
                width = max(label(text, size=size, mono=True).width,
                            label(caption, size=20).width)+.45
                fields.append((text, width, color)); captions.append(caption)
        super().__init__(fields, unit=1, size=size, captions=captions, **kw)
        fit_to_frame(self)


class Topology(VGroup):
    """Small graph from node positions and (src,dst[,label]) links.

    net = Topology({'A':(-4,0), 'R':(0,0), 'B':(4,0)}, [('A','R','LAN'), ('R','B')])
    self.play(FadeIn(net)); self.play(net.hop_path(Packet('data'), ['A','R','B']))
    Positions are (x,y); node names sit inside their boxes. Link labels are
    placed off all links/nodes/earlier labels; impossible specs raise ValueError.
    Links are static: move the complete topology, not individual nodes afterward.
    """
    def __init__(self, nodes, links, **kw):
        super().__init__(**kw)
        if not nodes:
            raise ValueError('Topology needs nodes')
        self.nodes = {name: Node(name, width=max(1.5, label(name, size=28).width+.4), height=.8)
                      .move_to([pos[0], pos[1], 0]) for name,pos in nodes.items()}
        boxes = list(self.nodes.values())
        if any(_overlaps(a,b,.1) for i,a in enumerate(boxes) for b in boxes[i+1:]):
            raise ValueError('Node positions overlap')
        self.links = VGroup()
        self.link_labels = VGroup()
        self.edges = set()
        specs = list(links)
        for spec in specs:
            a,b = spec[:2]
            if a == b:
                raise ValueError('Self-links are not supported')
            self.edges.add(frozenset((a,b)))
            self.links.add(Line(self.nodes[a].get_center(), self.nodes[b].get_center(), color=style.DIM))
        for line,spec in zip(self.links,specs):
            if len(spec) < 3 or not spec[2]:
                continue
            text = label(spec[2], size=20)
            d = line.get_end()-line.get_start(); normal = np.array([-d[1],d[0],0])/np.linalg.norm(d)
            placed = False
            for dist in (.4,.7,1.,1.3):
                for sign in (1,-1):
                    text.move_to(line.get_center()+normal*dist*sign)
                    # Sample each segment densely against the expanded label box.
                    obstacles = boxes + list(self.link_labels)
                    hit = any(_overlaps(text,o,.12) for o in obstacles)
                    for edge in self.links:
                        points = np.linspace(edge.get_start(),edge.get_end(),101)
                        hit |= any(text.get_left()[0]-.1 < p[0] < text.get_right()[0]+.1
                                   and text.get_bottom()[1]-.1 < p[1] < text.get_top()[1]+.1 for p in points)
                    if not hit:
                        placed = True; break
                if placed:
                    break
            if not placed:
                raise ValueError('No clear link-label position; spread nodes apart')
            self.link_labels.add(text)
        self.add(self.links, *boxes, self.link_labels)
        fit_to_frame(self)

    def hop_path(self, packet, nodes, run_time=2):
        if len(nodes) < 2 or any(frozenset((a,b)) not in self.edges for a,b in zip(nodes,nodes[1:])):
            raise ValueError('Every hop must follow an installed link')
        return packet_route(packet, [self.nodes[n] for n in nodes], run_time)

    def rewrite_header(self, bar, src, dst, field=0):
        """Return animation rewriting only the selected DL FieldBar field.

        self.play(net.rewrite_header(headers, 'R', 'B'))  # IP field stays intact
        """
        if frozenset((src,dst)) not in self.edges:
            raise ValueError('Header must describe an installed link')
        text = f'{src} → {dst}'
        if label(text, size=bar.size, mono=bar.mono).width > bar.rects[field].width-.15:
            raise ValueError('Header label exceeds field width')
        return bar.set_text(field, text)


# --------------------------------------------------------------------------- #
class RoutingGraph(VGroup):
    """Weighted router graph: circle routers, boxed prefixes, per-node state tags.

    g = RoutingGraph({'R1': (-3, 0), 'R2': (0, 1), 'ece': (-5, 0, 'net')},
                     [('ece', 'R1', 1), ('R1', 'R2', 5)], tag_dirs={'R1': DOWN})
    self.play(FadeIn(g)); self.play(g.set_tag('R1', 'ece,1'))
    self.play(g.send('R1', 'R2', 'ece,1'))     # packet flies along the link
    self.play(g.fail_link('R1', 'R2'))         # red dashed link + cross
    self.play(g.highlight_link('R1', 'R2'))    # e.g. a shortest-path tree edge
    Positions are (x, y) or (x, y, 'net'). Weights sit beside the link midpoint
    (`weight_sides={('R1','R2'): -1}` flips a label). Move the whole graph only.
    """
    def __init__(self, nodes, links, radius=0.36, tag_dirs=None, weight_sides=None,
                 tag_size=style.SMALL_SIZE, **kw):
        super().__init__(**kw)
        self.radius, self.tag_size = radius, tag_size
        self.tag_dirs = dict(tag_dirs or {})
        self.nodes, self.kinds = {}, {}
        for name, pos in nodes.items():
            kind = pos[2] if len(pos) > 2 else 'router'
            txt = label(name, size=22 if kind == 'router' else 20, color=style.FG, weight="BOLD")
            if kind == 'router':
                shape = Circle(radius=radius, color=style.BLUE, stroke_width=3,
                               fill_color=style.PANEL, fill_opacity=1)
            else:
                shape = RoundedRectangle(corner_radius=0.1, width=txt.width + 0.35, height=0.6,
                                         color=style.TEAL, stroke_width=2,
                                         fill_color=style.PANEL, fill_opacity=1)
            node = VGroup(shape, txt.move_to(shape)).move_to([pos[0], pos[1], 0])
            self.nodes[name], self.kinds[name] = node, kind
        self.links, self.weights = {}, {}
        sides = {frozenset(k): v for k, v in (weight_sides or {}).items()}
        for spec in links:
            a, b = spec[:2]
            key = frozenset((a, b))
            line = Line(self.nodes[a].get_center(), self.nodes[b].get_center(),
                        color=style.DIM, stroke_width=3)
            self.links[key] = line
            if len(spec) > 2 and spec[2] is not None:
                d = line.get_end() - line.get_start()
                normal = np.array([-d[1], d[0], 0]) / np.linalg.norm(d)
                if normal[1] < 0 or (abs(normal[1]) < 1e-6 and normal[0] < 0):
                    normal = -normal
                w = label(str(spec[2]), size=20, color=style.GOLD)
                w.move_to(line.get_center() + normal * sides.get(key, 1) * 0.28)
                self.weights[key] = w
        self.tags = {}
        self.add(VGroup(*self.links.values()), *self.nodes.values(), *self.weights.values())

    def link(self, a, b):
        return self.links[frozenset((a, b))]

    def _tag_pos(self, name, mob):
        d = np.array(self.tag_dirs.get(name, UP), dtype=float)
        node = self.nodes[name]
        return node.get_center() + d * (max(node.width, node.height) / 2 + (0.18 if abs(d[0]) > 0.5 else 0.08)) \
            + d * np.array([mob.width / 2, mob.height / 2, 0]) * np.abs(d).clip(0, 1)

    def set_tag(self, name, text, color=style.YELLOW):
        """FadeIn or Transform the state label next to `name` (direction from tag_dirs)."""
        new = label(text, size=self.tag_size, color=color, mono=True)
        new.move_to(self._tag_pos(name, new))
        old = self.tags.get(name)
        if old is None:
            self.tags[name] = new
            self.add(new)
            return FadeIn(new, scale=0.8)
        return Transform(old, new)

    def clear_tag(self, name):
        old = self.tags.pop(name)
        self.remove(old)
        return FadeOut(old)

    def send(self, a, b, text, color=style.YELLOW, run_time=1.2):
        """Packet labeled `text` travels from node a to node b along their link."""
        if frozenset((a, b)) not in self.links:
            raise ValueError('send() must follow an installed link')
        pkt = Packet(text, color=color)
        return packet_flight(pkt, self.nodes[a], self.nodes[b], run_time=run_time)

    def fail_link(self, a, b):
        line = self.link(a, b)
        mid = line.get_center()
        cross = VGroup(Line(mid + [-.15, -.15, 0], mid + [.15, .15, 0]),
                       Line(mid + [-.15, .15, 0], mid + [.15, -.15, 0])).set_stroke(style.RED, 6)
        dashed = DashedLine(line.get_start(), line.get_end(), color=style.RED, stroke_width=3)
        self.add(cross)
        return AnimationGroup(Transform(line, dashed), FadeIn(cross, scale=1.5))

    def highlight_link(self, a, b, color=style.GREEN, width=7):
        return self.link(a, b).animate.set_stroke(color, width)

    def highlight_node(self, name, color=style.YELLOW):
        return self.nodes[name][0].animate.set_stroke(color, 5)


# --- beat helpers: motion while narration explains --------------------------------------
def flow_flash(path, color=style.YELLOW, width: float = 8, time_width: float = 0.4, run_time: float = 1.2):
    """A bright pulse travels along an existing line/arrow/path (data flow, a signal, a request).

        self.play(flow_flash(topo.link("A", "R1")), run_time=t.duration)

    `path` stays untouched; the pulse is a temporary copy removed afterwards. Repeat it with
    `Succession(*[flow_flash(p) for p in paths])` to follow a multi-hop route."""
    from manim import ShowPassingFlash
    pulse = path.copy().set_stroke(color=color, width=width, opacity=1).set_fill(opacity=0)
    return ShowPassingFlash(pulse, time_width=time_width, run_time=run_time)


def _opacity_fade(target, start: float, end: float):
    """Scale every VMobject's stored fill/stroke opacity in `target` from `start` to `end` × original."""
    from manim import UpdateFromAlphaFunc
    orig = target._studio_focus

    def update(_m, alpha):
        f = start + (end - start) * alpha
        for leaf, fill, stroke in orig:
            leaf.set_fill(opacity=fill * f, family=False)
            leaf.set_stroke(opacity=stroke * f, family=False)
    return UpdateFromAlphaFunc(target, update)


def focus(keep, context, opacity: float = 0.3, run_time: float = 0.6):
    """Dim every mobject in `context` except those in `keep`, so one thing holds attention.

        self.play(focus([table.cell(2, 1)], self.mobjects))   # ... explain ...
        self.play(unfocus(self.mobjects))

    Records each dimmed part's fill/stroke opacity; `unfocus` restores exactly those values
    (objects added or recolored meanwhile are left alone). `keep` and source tags stay bright."""
    from manim import AnimationGroup
    kept = set()
    for k in keep:
        kept.update(id(m) for m in k.get_family())
    anims = []

    def targets(m):
        if id(m) in kept or getattr(m, "_studio_source_tag", False):
            return []
        if any(id(x) in kept for x in m.get_family()):  # contains a kept part: dim its other parts
            return [t for s in m.submobjects for t in targets(s)]
        return [m]

    for m in context:
        for t in targets(m):
            if getattr(t, "_studio_focus", None):
                continue
            t._studio_focus = [(leaf, leaf.get_fill_opacity(), leaf.get_stroke_opacity())
                               for leaf in t.get_family() if isinstance(leaf, VMobject)]
            if t._studio_focus:
                anims.append(_opacity_fade(t, 1.0, opacity))
                t._studio_focus_level = opacity
    return AnimationGroup(*anims, run_time=run_time) if anims else AnimationGroup(run_time=0.01)


def unfocus(context, run_time: float = 0.6):
    """Undo `focus`: bring every dimmed part (found in the families of `context`) back to its opacity."""
    from manim import AnimationGroup
    anims = []
    for m in context:
        for t in m.get_family():
            if getattr(t, "_studio_focus", None):
                anims.append(_opacity_fade(t, t._studio_focus_level, 1.0))  # captures the saved values
                t._studio_focus = None
    return AnimationGroup(*anims, run_time=run_time) if anims else AnimationGroup(run_time=0.01)


class TermEquation(VGroup):
    """A LaTeX-free equation whose terms brighten in teaching order (dim-and-reveal).

        eq = TermEquation(["risk", " = ", "likelihood", " × ", "impact"]).dimmed()
        self.play(FadeIn(eq))                                   # whole equation, dimmed
        with self.voiceover(text="Impact is how bad the loss would be.") as t:
            self.play(eq.reveal(4), run_time=min(1.5, t.duration))
        with self.voiceover(text="Likelihood is how often it happens.") as t:
            self.play(eq.reveal(2))                              # 4 drops to context brightness

    One Text keeps natural kerning; `terms[i]` is the glyph group for parts[i]. Reveal in the
    order the viewer needs (often result, inputs, then operators), not left to right."""

    def __init__(self, parts, size: int = style.BODY_SIZE + 6, color=style.FG, mono: bool = False,
                 colors: dict | None = None, **kw):
        super().__init__(**kw)
        self.parts = list(parts)
        self.full = label("".join(self.parts), size=size, color=color, mono=mono)
        counts = [len("".join(p.split())) for p in self.parts]
        if sum(counts) != len(self.full):
            raise ValueError("TermEquation could not map glyphs to parts; simplify the characters")
        self.terms, i = [], 0
        for n in counts:
            self.terms.append(VGroup(*self.full[i:i + n]))
            i += n
        for idx, c in (colors or {}).items():
            self.terms[idx].set_color(c)
        self.add(self.full)
        self._lit: list[int] = []

    def dimmed(self, opacity: float = 0.22):
        self.full.set_fill(opacity=opacity)
        return self

    def reveal(self, *idx, context: float = 0.6, run_time: float = 0.9):
        """Brighten terms `idx`; previously revealed terms drop to `context` opacity."""
        from manim import AnimationGroup
        anims = [self.terms[j].animate.set_fill(opacity=context) for j in self._lit if j not in idx]
        anims += [self.terms[j].animate.set_fill(opacity=1) for j in idx]
        self._lit = list(idx) + [j for j in self._lit if j not in idx]
        return AnimationGroup(*anims, run_time=run_time)

    def reveal_all(self, run_time: float = 0.8):
        from manim import AnimationGroup
        self._lit = list(range(len(self.terms)))
        return AnimationGroup(*[t.animate.set_fill(opacity=1) for t in self.terms], run_time=run_time)


def _own_border(mob):
    """The border a mobject already draws (Node.box, a table cell's rectangle), else None."""
    box = getattr(mob, "box", None)
    if box is not None:
        return box
    if isinstance(mob, VGroup) and len(mob) and isinstance(mob[0], (Rectangle, RoundedRectangle)):
        return mob[0]
    return None


def pulse(mob, color=style.YELLOW, scale: float = 1.06, run_time: float = 1.0):
    """Emphasize an object without adding anything: it swells slightly and, if it already has a
    border (Node, table cell or row), those borders light up in `color` and back; fills and
    labels keep their styles. Unbordered objects swell and tint their fill/stroke separately.
    A bare outline such as a slide highlight box only thickens in place (never scales).

        self.play(pulse(node, style.GOLD), run_time=t.duration)
    Never draws a new outline; use `identify()` for that, sparingly. Prefer it to Indicate on
    filled boxes: Indicate repaints the fill and covers the box's own label while it plays.
    One animation drives the whole object, so a filled border is never re-layered over its label."""
    from manim import UpdateFromAlphaFunc, there_and_back
    from manim.utils.color import ManimColor
    bare = isinstance(mob, (Rectangle, RoundedRectangle)) and mob.get_fill_opacity() == 0
    family = mob.get_family()
    originals = mob.copy().get_family()
    # A row owns several cell borders, not one border at its root. Never use get_color()
    # to restore them: it reports the fill color, which would erase a different stroke.
    borders = {id(b) for sub in family
               if (b := _own_border(sub)) is not None}
    borders.update(id(sub) for sub in family if isinstance(sub, (Rectangle, RoundedRectangle)))
    center = mob.get_center()
    target = ManimColor(color).to_rgb()

    def update(m, alpha):
        f = there_and_back(alpha)
        for sub, original in zip(family, originals):
            # Restore in place: no align_data/become, child replacement or separate child
            # animations that could promote opaque rectangles above their own labels.
            sub.points = original.points.copy()
            if isinstance(sub, VMobject):
                sub.interpolate_color(original, original, 1)
                if id(sub) in borders:
                    sub.stroke_rgbas[:, :3] = (1 - f) * original.stroke_rgbas[:, :3] + f * target
                    sub.stroke_width = original.stroke_width + (4 if bare else 3) * f
                elif not borders:
                    sub.fill_rgbas[:, :3] = (1 - f) * original.fill_rgbas[:, :3] + f * target
                    sub.stroke_rgbas[:, :3] = (1 - f) * original.stroke_rgbas[:, :3] + f * target
        if not bare and f:
            m.scale(1 + (scale - 1) * f, about_point=center)
    return UpdateFromAlphaFunc(mob, update, run_time=run_time)


def identify(mob, color=style.YELLOW, run_time: float = 1.2):
    """Draw an animated outline around important TEXT to single it out ("this term", "this field").

        self.play(identify(eq.terms[2]))
    Use sparingly: at most once or twice per scene. Don't use it on objects that already have a
    border (Node, table cell, slide highlight) unless the point is to pick that one out of several
    identical-looking ones; use `pulse` for plain emphasis."""
    from manim import Circumscribe
    return Circumscribe(mob, color=color, buff=0.08, run_time=run_time)


# --------------------------------------------------------------------------- #
# Code visualization: syntax trees, real source listings, scope environments.
# --------------------------------------------------------------------------- #
AST_COLORS = {
    "fcall": style.BLUE, "qname": style.TEAL,
    "int": style.GOLD, "string": style.GOLD, "bool": style.GOLD, "list": style.GOLD,
}
_FRAME_W, _FRAME_H = 13.0, 7.0

def _req_size(size):
    """Validate (≥20 pt) and return the size."""
    _min_size(size)
    return size



class AST:
    """Plain syntax-tree node for ASTTree: kind, optional value, children, the parent's field name
    for this child (drawn on the edge), and an optional key for lookups.

        AST("fcall", AST("qname", value="print", field="fn"),
                     AST("int", value="40", field="args", key="forty"), key="call")
    """

    def __init__(self, kind: str, *children: "AST", value: str | None = None, field: str | None = None,
                 key: str | None = None):
        self.kind, self.children, self.value, self.field, self.key = kind, list(children), value, field, key


class ASTTree(VGroup):
    """Top-down syntax tree drawn from AST nodes (parents centred over their children).

        tree = ASTTree(AST("fcall", AST("qname", value="+", field="fn"), AST("int", value="2", field="args")))
        self.play(tree.grow())                    # level by level
        self.play(tree.visit("forty"))            # evaluation cursor (restores the previous node)
        pill, anim = tree.result("forty", "40"); self.play(anim)
        self.play(tree.carry(pill, "call"))       # a value returns to its parent
    Node colours by kind: fcall BLUE, qname TEAL, literals GOLD, everything else PURPLE (override
    with colors={kind: colour}). `node(k)` accepts a key or a child-index path tuple (root = ()).
    Raises ValueError if the tree cannot fit 13×7 at ≥20 pt: show a subtree instead."""

    def __init__(self, root: AST, size: int = 20, x_gap: float = 0.3, y_gap: float = 0.72,
                 colors: dict | None = None, max_width: float = _FRAME_W, max_height: float = _FRAME_H, **kw):
        super().__init__(**kw)
        size = _req_size(size)
        self.size, self.colors = size, {**AST_COLORS, **(colors or {})}
        self._nodes: dict = {}
        self._edges: dict = {}
        self._fields: dict = {}
        self._color_of: dict = {}
        self._visited = None
        built = {}

        def build(n: AST, path):
            color = self.colors.get(n.kind, style.PURPLE)
            kind = Text(n.kind, font=style.MONO, font_size=size, color=color)
            parts = [kind]
            if n.value is not None:
                parts.append(Text(str(n.value), font=style.MONO, font_size=size + 2, color=style.FG))
            body = VGroup(*parts).arrange(DOWN, buff=0.08)
            box = RoundedRectangle(width=body.width + 0.3, height=max(body.height + 0.22, 0.55),
                                   corner_radius=0.08, stroke_color=color, stroke_width=3,
                                   fill_color=style.PANEL, fill_opacity=1)
            body.move_to(box)
            node = VGroup(box, *parts)
            built[path] = (n, node)
            for i, c in enumerate(n.children):
                build(c, path + (i,))

        build(root, ())
        # Subtree widths, then x positions (tidy: parent centred over its children's span).
        width = {}

        def measure(path):
            n, node = built[path]
            kids = [path + (i,) for i in range(len(n.children))]
            span = sum(measure(k) for k in kids) + x_gap * max(len(kids) - 1, 0)
            width[path] = max(node.width, span)
            return width[path]

        measure(())
        level_h = max(node.height for _, node in built.values())

        def place(path, left, depth):
            n, node = built[path]
            kids = [path + (i,) for i in range(len(n.children))]
            span = sum(width[k] for k in kids) + x_gap * max(len(kids) - 1, 0)
            x = left + width[path] / 2
            if kids:
                cursor = left + (width[path] - span) / 2
                for k in kids:
                    place(k, cursor, depth + 1)
                    cursor += width[k] + x_gap
                xs = [built[k][1].get_center()[0] for k in kids]
                x = (xs[0] + xs[-1]) / 2
            node.move_to([x, -depth * (level_h + y_gap), 0])

        place((), 0.0, 0)
        edges, labels, boxes = VGroup(), VGroup(), VGroup()
        groups: dict = {}  # (parent path, field) -> [child paths]; siblings sharing a field share one label
        for path, (n, node) in built.items():
            self._nodes[path] = node
            self._color_of[id(node)] = self.colors.get(n.kind, style.PURPLE)
            if n.key is not None:
                if n.key in self._nodes:
                    raise ValueError(f"duplicate AST key {n.key!r}")
                self._nodes[n.key] = node
            boxes.add(node)
            if path:
                parent = built[path[:-1]][1]
                e = Line(parent[0].get_bottom(), node[0].get_top(), color=style.DIM, stroke_width=2.5)
                self._edges[path] = e
                if n.key is not None:
                    self._edges[n.key] = e
                edges.add(e)
                if n.field:
                    groups.setdefault((path[:-1], n.field), []).append(path)
        placed = []
        for (_, field), paths in groups.items():
            lab = Text(field, font=style.MONO, font_size=_req_size(20), color=style.DIM)
            plate = Rectangle(width=lab.width + 0.08, height=lab.height + 0.06, stroke_width=0,
                              fill_color=style.BG, fill_opacity=1)
            tag = VGroup(plate, lab)
            tag.original_text = field
            es = [self._edges[p] for p in paths]
            for prop in (0.55, 0.4, 0.7, 0.3, 0.8):
                pts = [e.point_from_proportion(prop) for e in es]
                tag.move_to([sum(p[0] for p in pts) / len(pts), pts[0][1], 0])
                if not any(_boxes_overlap(tag, o) for o in placed + [b[0] for b in boxes]):
                    break
            else:  # nudge sideways, away from the most recent neighbour, until clear
                for dx in (0.15, -0.15, 0.3, -0.3, 0.45, -0.45, 0.6, -0.6):
                    tag.shift(RIGHT * dx)
                    if not any(_boxes_overlap(tag, o) for o in placed + [b[0] for b in boxes]):
                        break
                    tag.shift(LEFT * dx)
            placed.append(tag)
            labels.add(tag)
            for p in paths:
                self._fields[p] = tag
                if built[p][0].key is not None:
                    self._fields[built[p][0].key] = tag
        self.edges, self.labels, self.box_group = edges, labels, boxes
        self.add(edges, labels, boxes)
        if self.width > max_width + 1e-6 or self.height > max_height + 1e-6:
            raise ValueError(f"AST is {self.width:.1f}×{self.height:.1f}; at ≥20 pt it must fit "
                             f"{max_width}×{max_height}. Show a subtree or split the beat.")
        self.move_to([0, 0, 0])

    def _path(self, key):
        return tuple(key) if isinstance(key, (tuple, list)) else key

    def node(self, key) -> VGroup:
        return self._nodes[self._path(key)]

    def edge(self, key) -> Line:
        return self._edges[self._path(key)]

    def field_label(self, key):
        return self._fields.get(self._path(key))

    def boxes(self) -> list:
        return [n[0] for n in self.box_group]

    def texts(self) -> list:
        return [t for n in self.box_group for t in n[1:]]

    def subtree(self, key) -> VGroup:
        """Node, descendants, their edges and field labels (for focus()/FadeOut)."""
        path = next(p for p, n in self._nodes.items() if isinstance(p, tuple) and n is self.node(key))
        out, seen = VGroup(), set()
        for p, n in self._nodes.items():
            if isinstance(p, tuple) and p[:len(path)] == path:
                out.add(n)
                if p != path and p in self._edges:
                    out.add(self._edges[p])
                    if p in self._fields and id(self._fields[p]) not in seen:
                        seen.add(id(self._fields[p]))
                        out.add(self._fields[p])
        return out

    def grow(self, run_time: float = 2.0, lag: float = 0.6):
        """Reveal the tree level by level (edges and labels arrive with their child)."""
        depth = {}
        for p in self._nodes:
            if isinstance(p, tuple):
                depth.setdefault(len(p), []).append(p)
        levels = [depth[d] for d in sorted(depth)]
        per = run_time / max(len(levels), 1)
        steps, shown = [], set()
        for paths in levels:
            anims = []
            for p in paths:
                if p in self._edges:
                    anims.append(Create(self._edges[p]))
                if p in self._fields and id(self._fields[p]) not in shown:
                    shown.add(id(self._fields[p]))
                    anims.append(FadeIn(self._fields[p]))
                anims.append(FadeIn(self._nodes[p]))
            steps.append(AnimationGroup(*anims, run_time=per))
        return Succession(*steps)

    def visit(self, key, color=style.YELLOW):
        """Move the evaluation cursor: this node's border lights up; the previous one is restored."""
        node = self.node(key)
        anims = []
        if self._visited is not None and self._visited is not node:
            prev = self._visited
            anims.append(_restroke(prev, self._color_of[id(prev)], 3))
        anims.append(_restroke(node, color, 6))
        self._visited = node
        return AnimationGroup(*anims)

    def unvisit(self):
        if self._visited is None:
            return Wait(0.01)
        prev, self._visited = self._visited, None
        return _restroke(prev, self._color_of[id(prev)], 3)

    def _beside(self, mob, node, side=RIGHT):
        """Place mob next to node on the first side (preferred, opposite, below, above) that clears every
        other node box and field label and stays inside the frame; else keep the preferred side."""
        others = [n[0] for n in self.box_group if n is not node] + list(self.labels)
        opposite = LEFT if side is RIGHT else RIGHT
        for direction, buff in ((side, 0.12), (opposite, 0.12), (DOWN, 0.08), (UP, 0.08)):
            mob.next_to(node[0], direction, buff=buff)
            if _inside(mob) and not any(_boxes_overlap(mob, o) for o in others):
                return mob
        mob.next_to(node[0], side, buff=0.12)
        return mob

    def result(self, key, text: str, color=style.GREEN, side=RIGHT):
        """(pill, FadeIn animation): the value this node evaluated to, placed beside it."""
        p = pill(text, color=color, size=max(self.size, 20), mono=True)
        self._beside(p, self.node(key), side)
        return p, FadeIn(p, scale=0.8)

    def carry(self, mob, key, side=RIGHT, run_time: float = 0.8):
        """Move a result pill up to sit beside another node (value returned to the caller)."""
        target = mob.copy()
        self._beside(target, self.node(key), side)
        return mob.animate(run_time=run_time).move_to(target.get_center())


def _restroke(node, color, width, run_time: float = 0.5):
    """Recolour node[0]'s border while animating the whole node (label stays drawn above the box)."""
    from manim import UpdateFromAlphaFunc
    from manim.utils.color import ManimColor
    box = node[0]
    start = box.get_stroke_color().to_rgb()
    w0 = box.get_stroke_width()
    end = ManimColor(color).to_rgb()

    def update(_, alpha):
        box.set_stroke(ManimColor.from_rgb((1 - alpha) * start + alpha * end), width=w0 + (width - w0) * alpha)
    return UpdateFromAlphaFunc(node, update, run_time=run_time)


def _boxes_overlap(a, b, eps=1e-6) -> bool:
    return not (a.get_right()[0] <= b.get_left()[0] + eps or b.get_right()[0] <= a.get_left()[0] + eps
                or a.get_top()[1] <= b.get_bottom()[1] + eps or b.get_top()[1] <= a.get_bottom()[1] + eps)


def _inside(mob, w=_FRAME_W, h=_FRAME_H) -> bool:
    return (mob.get_left()[0] >= -w / 2 - 1e-6 and mob.get_right()[0] <= w / 2 + 1e-6
            and mob.get_bottom()[1] >= -h / 2 - 1e-6 and mob.get_top()[1] <= h / 2 + 1e-6)


_PY_KEYWORDS = {"False", "None", "True", "and", "as", "class", "def", "elif", "else", "except",
                "finally", "for", "from", "if", "import", "in", "is", "lambda", "not", "or", "raise",
                "return", "try", "while", "with", "yield", "pass", "break", "continue", "global"}
_BREWIN_KEYWORDS = {"func", "seq", "if", "lambda"}


def _spans(line: str, language: str | None):
    """[(text, colour)] for one source line: keywords PURPLE, strings/numbers GOLD, comments DIM."""
    import re
    if language is None:
        return [(line, style.FG)]
    if language == "python":
        pat = re.compile(r"(?P<com>#.*$)|(?P<str>[fr]?\"[^\"]*\"|[fr]?'[^']*')|(?P<num>\b\d+\b)"
                         r"|(?P<word>[A-Za-z_]\w*)|(?P<other>.)")
        kw = _PY_KEYWORDS
    elif language == "brewin":
        pat = re.compile(r"(?P<com>$^)|(?P<str>\"[^\"]*\"|#[tf]\b)|(?P<num>-?\b\d+\b)"
                         r"|(?P<word>[A-Za-z_]\w*)|(?P<other>.)")
        kw = _BREWIN_KEYWORDS
    else:
        raise ValueError(f"unknown language {language!r}")
    out = []
    for m in pat.finditer(line):
        kind, tok = m.lastgroup, m.group()
        color = {"com": style.DIM, "str": style.GOLD, "num": style.GOLD}.get(kind, style.FG)
        if kind == "word" and tok in kw:
            color = style.PURPLE
        if out and out[-1][1] == color:
            out[-1] = (out[-1][0] + tok, color)
        else:
            out.append((tok, color))
    return out


def _blank_slot():
    """Invisible non-Text placeholder: blank Text has zero height, which breaks Text.font_size."""
    r = Rectangle(width=0.01, height=0.01, stroke_width=0, fill_opacity=0)
    r.is_blank = True
    return r


def _code_line(text: str, language, size: int):
    if not text.strip():
        return _blank_slot()
    spans = _spans(text, language)
    full = "".join(s for s, _ in spans)
    t = Text(full, font=style.MONO, font_size=size, color=style.FG)
    # Colour visible characters span by span (Text drops whitespace glyphs from its submobjects).
    idx = 0
    for s, color in spans:
        n = sum(1 for c in s if not c.isspace())
        for k in range(idx, idx + n):
            if k < len(t):
                t[k].set_color(color)
        idx += n
    return t


def check_regions(*, gap: float = 0.12, **regions: Mobject) -> None:
    """Fail if simultaneously visible *independent* groups lack a gutter.

    Example: ``check_regions(code=listing, state=stack, note=explanation)``.
    Check after positioning and after geometry changes; include nested labels inside their owner.
    """
    if not math.isfinite(gap) or gap < 0:
        raise ValueError('region gap must be finite and nonnegative')
    bounds = []
    for name, mob in regions.items():
        if not mob.family_members_with_points():
            continue
        left, right, bottom, top = mob.get_left()[0], mob.get_right()[0], mob.get_bottom()[1], mob.get_top()[1]
        for other, x0, x1, y0, y1 in bounds:
            if max(left - x1, x0 - right, bottom - y1, y0 - top) < gap - 1e-6:
                raise ValueError(f'Content regions {other!r} and {name!r} need a {gap:g}-unit gutter; '
                                 'reposition them or reveal them in separate beats.')
        bounds.append((name, left, right, bottom, top))


class CodeListing(VGroup):
    """Real source lines with their original line numbers, light syntax colour and one movable
    highlight bar. Common indentation is removed; lines longer than `max_chars` end in "…".

        code = CodeListing(SRC / "interpreterv3.py", 214, 227, skip=[(217, 221)])
        self.play(FadeIn(code)); self.play(code.highlight(215)); self.play(code.highlight(223, 224))
    `skip=[(a, b)]` replaces those lines by one "⋮" row. `CodeListing.from_text(src, language="brewin")`
    shows a snippet (numbered from 1). Lines are elided further so the listing fits `max_width`
    (default 13; use ~6.5 for a half-screen listing). Raises ValueError if taller than 7 at ≥20 pt."""

    def __init__(self, path=None, start: int = 1, end: int | None = None, *, text: str | None = None,
                 language: str | None = "python", size: int = 20, max_chars: int = 74,
                 numbers: bool = True, skip=(), required_lines=(), line_buff: float = 0.14,
                 max_width: float = _FRAME_W, **kw):
        super().__init__(**kw)
        size = _req_size(size)
        src = text if text is not None else Path(path).read_text(encoding="utf-8")
        all_lines = src.splitlines()
        end = len(all_lines) if end is None else end
        if not (1 <= start <= end <= len(all_lines)):
            raise ValueError(f"line range {start}-{end} outside 1-{len(all_lines)}")
        skipped = {n for a, b in skip for n in range(a, b + 1)}
        required = set(required_lines)
        for line_no in sorted(required):
            if not start <= line_no <= end or line_no in skipped:
                raise ValueError(f'Required code line {line_no} is not displayed; include it in the listing.')
        chosen = [n for n in range(start, end + 1) if n not in skipped]
        body = [all_lines[n - 1] for n in chosen if all_lines[n - 1].strip()]
        indent = min((len(l) - len(l.lstrip(" ")) for l in body), default=0)
        self.size, self.language = size, language
        # Elide long lines so the listing fits max_width (Menlo is fixed-pitch: measure one glyph).
        cw = Text("M" * 40, font=style.MONO, font_size=size).width / 40
        num_cols = (len(str(end)) * cw + 0.35) if numbers else 0
        max_chars = max(8, min(max_chars, int((max_width - num_cols - 0.05) / cw)))
        self._text: dict = {}
        self._rows: dict = {}
        self.numbers: list[int] = []
        rows = VGroup()
        num_w = len(str(end))
        chosen_row: list = []
        n = start
        while n <= end:
            if n in skipped:
                b = next(b for a, b in skip if a <= n <= b)
                row = VGroup(_blank_slot(), Text("⋮", font=style.MONO, font_size=size, color=style.DIM))
                row.is_skip = True
                rows.add(row)
                chosen_row.append(None)
                n = b + 1
                continue
            raw = all_lines[n - 1][indent:].rstrip()
            if len(raw) > max_chars:
                if n in required:
                    raise ValueError(f'Required code line {n} would be elided; widen the listing or use a separate beat.')
                raw = raw[:max_chars - 1].rstrip() + "…"
            self._text[n] = raw
            num = (Text(str(n).rjust(num_w), font=style.MONO, font_size=size, color=style.DIM)
                   if numbers else _blank_slot())
            line = _code_line(raw, language, size)
            row = VGroup(num, line)
            row.is_skip = False
            rows.add(row)
            chosen_row.append(n)
            self._rows[n] = row
            self.numbers.append(n)
            n += 1
        # Fixed pitch so rows line up regardless of glyph heights; code column left-aligned.
        pitch = Text("Ag", font=style.MONO, font_size=size).height + line_buff
        probe = Text("M" * 40, font=style.MONO, font_size=size)
        self.char_width = probe.width / 40
        num_col = max((r[0].width for r in rows if not getattr(r[0], "is_blank", False)), default=0)
        for i, row in enumerate(rows):
            y = -i * pitch
            row[0].move_to([num_col - row[0].width / 2 if numbers and not getattr(row[0], "is_blank", False)
                            else 0, y, 0])
            code_x = (num_col + 0.35) if numbers else 0
            src = self._text.get(chosen_row[i], "") if chosen_row[i] else ""
            lead = len(src) - len(src.lstrip(" "))
            row[1].move_to([code_x + lead * self.char_width + row[1].width / 2, y, 0])
        self.rows = rows
        self.pitch = pitch
        self.bar = None
        self.add(rows)
        if self.height > _FRAME_H + 1e-6:
            raise ValueError(f"listing is {self.height:.1f} tall; at ≥20 pt it must fit 7. "
                             "Show fewer lines (skip=...).")
        self.move_to([0, 0, 0])

    @classmethod
    def from_text(cls, text: str, language: str | None = "brewin", **kw) -> "CodeListing":
        return cls(text=text, language=language, **kw)

    def row(self, n: int) -> VGroup:
        return self._rows[n]

    def source_text(self, n: int) -> str:
        return self._text[n]

    def lines(self, a: int, b: int | None = None) -> VGroup:
        b = a if b is None else b
        return VGroup(*[self._rows[n] for n in self.numbers if a <= n <= b])

    def _bar_for(self, a: int, b: int):
        rows = self.lines(a, b)
        top, bottom = rows.get_top()[1] + 0.06, rows.get_bottom()[1] - 0.06
        left = self.rows.get_left()[0] - 0.1
        right = self.rows.get_right()[0] + 0.1
        bar = Rectangle(width=right - left, height=top - bottom, stroke_width=0,
                        fill_color=style.YELLOW, fill_opacity=0.18)
        bar.move_to([(left + right) / 2, (top + bottom) / 2, 0])
        return bar

    def highlight(self, a: int, b: int | None = None):
        """Move the single highlight bar to lines a..b (creates it on first use, behind the text)."""
        b = a if b is None else b
        target = self._bar_for(a, b)
        if self.bar is None:
            self.bar = target
            self.add_to_back(self.bar)
            return FadeIn(self.bar)
        return Transform(self.bar, target)

    def clear_highlight(self):
        if self.bar is None:
            return Wait(0.01)
        bar, self.bar = self.bar, None
        self.remove(bar)
        return FadeOut(bar)


class ScopeStack(VGroup):
    """Environment as a stack of function frames; each frame holds blocks of name = value bindings
    (outermost block at the bottom, innermost on top; the newest frame is drawn above its caller).

        env = ScopeStack(x=4.2, bottom=-2.9, width=4.2)   # -2.9 clears a one-line SourceTag
        self.play(env.push_frame("main")); self.play(env.define("x", "5"))
        self.play(env.push_block());       self.play(env.define("x", "6"))
        anim, hit = env.lookup("x"); self.play(anim)   # innermost → outer, current frame only
        self.play(env.push_frame("λ", blocks=[[("x", "10")], [("y", "4")]]))
    Every method returns an animation that also re-flows the stack; `state()` mirrors the model."""

    ROW = 0.42

    def __init__(self, x: float = 4.0, bottom: float = -2.9, width: float = 4.2, size: int = 22,
                 top_limit: float = 3.5, compact: bool = False, **kw):
        super().__init__(**kw)
        self.cx, self.bottom, self.w, self.size = x, bottom, width, _req_size(size)
        # compact: tighter rows/paddings (≈1.0 per one-binding frame instead of 1.24) for deep recursion.
        self.ROW, self.PAD, self.GAP, self.HEAD, self.FGAP = ((0.38, 0.1, 0.08, 0.36, 0.1) if compact
                                                             else (0.42, 0.16, 0.12, 0.42, 0.15))
        self.top_limit = top_limit
        self._frames: list = []  # [{"panel", "title", "blocks": [{"box", "rows": [(name, value, mob)]}]}]

    # --- model ---------------------------------------------------------------
    def state(self):
        return [[[(n, v) for n, v, _ in b["rows"]] for b in f["blocks"]] for f in self._frames]

    def frame(self, i: int) -> VGroup:
        return self._frames[i]["panel"]

    def block(self, f: int, b: int) -> VGroup:
        return self._frames[f]["blocks"][b]["box"]

    def binding(self, f: int, b: int, r: int):
        return self._frames[f]["blocks"][b]["rows"][r][2]

    # --- geometry ------------------------------------------------------------
    def _block_h(self, blk):
        return max(len(blk["rows"]), 1) * self.ROW + self.PAD

    def _frame_h(self, fr):
        return sum(self._block_h(b) for b in fr["blocks"]) + self.GAP * (len(fr["blocks"]) + 1) + self.HEAD

    def _layout(self):
        """Target mobjects (box rectangles, panel rectangles, row positions) for the current model."""
        y = self.bottom
        targets = []
        for i, fr in enumerate(self._frames):
            h = self._frame_h(fr)
            top = i == len(self._frames) - 1
            panel = RoundedRectangle(width=self.w, height=h, corner_radius=0.1, stroke_width=3 if top else 2,
                                     stroke_color=style.BLUE if top else style.DIM,
                                     fill_color=style.PANEL, fill_opacity=1)
            panel.move_to([self.cx, y + h / 2, 0])
            title_pos = [self.cx - self.w / 2 + 0.18, y + h - self.HEAD * 0.57, 0]
            by = y + self.GAP
            blocks = []
            for blk in fr["blocks"]:
                bh = self._block_h(blk)
                box = Rectangle(width=self.w - 0.3, height=bh, stroke_width=2, stroke_color=style.DIM,
                                fill_color=style.BG, fill_opacity=1)
                box.move_to([self.cx, by + bh / 2, 0])
                rows = []
                for i in range(len(blk["rows"])):
                    rows.append([self.cx - self.w / 2 + 0.35, by + bh - self.PAD / 2 - (i + 0.5) * self.ROW, 0])
                blocks.append((box, rows))
                by += bh + self.GAP
            targets.append((panel, title_pos, blocks))
            y += h + self.FGAP
        if y - self.FGAP > self.top_limit + 1e-6:
            raise ValueError("ScopeStack is taller than the frame; pop frames/blocks or lower `bottom`.")
        return targets

    def _reflow(self, new=()):
        anims = []
        for fr, (panel, title_pos, blocks) in zip(self._frames, self._layout()):
            if fr["panel"] in new:
                fr["panel"].become(panel)
            else:
                anims.append(Transform(fr["panel"], panel))
            title_xy = [title_pos[0] + fr["title"].width / 2, title_pos[1], 0]
            if fr["title"] in new:
                fr["title"].move_to(title_xy)
            else:
                anims.append(fr["title"].animate.move_to(title_xy))
            for blk, (box, rows) in zip(fr["blocks"], blocks):
                if blk["box"] in new:
                    blk["box"].become(box)
                else:
                    anims.append(Transform(blk["box"], box))
                for (name, value, mob), pos in zip(blk["rows"], rows):
                    target = [pos[0] + mob.width / 2, pos[1], 0]
                    if mob in new:
                        mob.move_to(target)
                    else:
                        anims.append(mob.animate.move_to(target))
        return anims

    def _binding_mob(self, name, value):
        return rich_text([(f"{name} = ", style.FG), (str(value), style.GOLD)], size=self.size, mono=True)

    def _new_block(self, rows=()):
        box = Rectangle(width=self.w - 0.3, height=0.5, stroke_width=2, stroke_color=style.DIM,
                        fill_color=style.BG, fill_opacity=1)
        return {"box": box, "rows": [(n, str(v), self._binding_mob(n, v)) for n, v in rows]}

    # --- operations ----------------------------------------------------------
    def push_frame(self, title: str, blocks=None):
        """New frame on top: one empty block, or the given [[(name, value), ...], ...] blocks."""
        panel = RoundedRectangle(width=self.w, height=1, corner_radius=0.1)
        ttl = Text(title, font=style.MONO, font_size=_req_size(20), color=style.BLUE)
        fr = {"panel": panel, "title": ttl,
              "blocks": [self._new_block(b) for b in (blocks if blocks is not None else [[]])]}
        self._frames.append(fr)
        new = [panel, ttl] + [b["box"] for b in fr["blocks"]] + [m for b in fr["blocks"] for *_, m in b["rows"]]
        anims = self._reflow(new)
        group = VGroup(panel, ttl, *[VGroup(b["box"], *[m for *_, m in b["rows"]]) for b in fr["blocks"]])
        self.add(group)
        fr["group"] = group
        self._highlight_top()
        return AnimationGroup(*anims, FadeIn(group))

    def pop_frame(self):
        fr = self._frames.pop()
        self.remove(fr["group"])
        self._highlight_top()
        return AnimationGroup(FadeOut(fr["group"]), *self._reflow())

    def push_block(self):
        fr = self._frames[-1]
        blk = self._new_block()
        fr["blocks"].append(blk)
        anims = self._reflow([blk["box"]])
        fr["group"].add(blk["box"])
        return AnimationGroup(*anims, FadeIn(blk["box"]))

    def pop_block(self):
        fr = self._frames[-1]
        blk = fr["blocks"].pop()
        parts = VGroup(blk["box"], *[m for *_, m in blk["rows"]])
        fr["group"].remove(blk["box"], *[m for *_, m in blk["rows"]])
        return AnimationGroup(FadeOut(parts), *self._reflow())

    def define(self, name: str, value):
        """Bind name = value in the innermost block of the current frame."""
        blk = self._frames[-1]["blocks"][-1]
        mob = self._binding_mob(name, value)
        blk["rows"].append((name, str(value), mob))
        anims = self._reflow([mob])
        self._frames[-1]["group"].add(mob)
        return AnimationGroup(*anims, FadeIn(mob, shift=0.1 * DOWN))

    def lookup(self, name: str, color=style.YELLOW, hit=style.GREEN, miss=style.RED):
        """(animation, (frame, block, row) or None): search the current frame only, innermost block
        first; flash each searched block, then the binding found (green) or the frame (red)."""
        f = len(self._frames) - 1
        fr = self._frames[f]
        steps, found = [], None
        for b in range(len(fr["blocks"]) - 1, -1, -1):
            blk = fr["blocks"][b]
            steps.append(pulse(blk["box"], color, scale=1.0, run_time=0.5))
            for r, (n, _, mob) in enumerate(blk["rows"]):
                if n == name:
                    found = (f, b, r)
                    break
            if found:
                steps.append(pulse(blk["rows"][found[2]][2], hit, run_time=0.6))
                break
        if found is None:
            steps.append(pulse(fr["panel"], miss, scale=1.0, run_time=0.6))
        return Succession(*steps), found

    def _highlight_top(self):
        for i, fr in enumerate(self._frames):
            top = i == len(self._frames) - 1
            fr["panel"].set_stroke(style.BLUE if top else style.DIM, width=3 if top else 2)
            fr["title"].set_color(style.BLUE if top else style.DIM)
