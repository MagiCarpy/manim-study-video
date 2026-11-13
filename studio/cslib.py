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

from pathlib import Path

import numpy as np
from manim import (
    DOWN, LEFT, PI, RIGHT, UP,
    AnimationGroup, Arrow, Circle, Create, DashedLine, FadeIn, FadeOut, GrowArrow,
    GrowFromEdge, Group, ImageMobject, Indicate, Line, MoveAlongPath,
    Rectangle, RoundedRectangle, Succession, Text, Transform, VGroup, VMobject,
)

from studio import style


def label(text: str, size: int = style.LABEL_SIZE, color=style.FG, mono: bool = False, **kw) -> Text:
    return Text(text, font=style.MONO if mono else style.FONT, font_size=size, color=color, **kw)


def bullets(items: list[str], size: int = style.BODY_SIZE, color=style.FG, buff: float = 0.35) -> VGroup:
    rows = VGroup(*[label(f"•  {t}", size=size, color=color) for t in items])
    return rows.arrange(DOWN, aligned_edge=LEFT, buff=buff)


def source_tag(text: str, corner=None, size: int = style.SMALL_SIZE, color=style.DIM) -> Text:
    """Small on-screen citation in a quiet corner (default: bottom-right of the safe area).

        tag = source_tag("IP Forwarding · slide 14")
        self.play(FadeIn(tag))                       # with the claim it cites
        self.play(Transform(tag, source_tag("Added example · based on slide 14")))
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
        return Transform(self[0], self._make(text))


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
