# High-level cslib patterns

All helpers are LaTeX-free. Import from `studio.cslib`. Visuals are ordinary
VGroups, except slide images (Group); state-changing methods return animations.
Font size is at least 20. Layout helpers measure text; they reject impossible
layouts rather than silently shrink text below 20. Split a dense beat when an
exception asks for more space. Position first, then apply clearance checks.
These utilities guarantee their returned geometry, not arbitrary later moves,
animations, newly added text, or collisions with unrelated objects.

## Vocabulary before mechanics

```python
card = definition_card('Next hop', 'The neighbor receiving a packet next.', width=7)
with self.voiceover(text='A next hop is the neighbor receiving a packet next.'):
    self.play(FadeIn(card))
self.play(FadeOut(card))
# Now demonstrate the next hop on a topology.
```

`definition_card(term, meaning, width=7, size=26, color=BLUE)` returns
VGroup(panel, term, meaning). Both text sections wrap at word boundaries.
An oversized word or too much text raises ValueError; choose a shorter definition.
Use it at first mention, with the spoken definition and a concrete demonstration.

## Citations and frame safety

```python
tag = SourceTag('IP Forwarding · slide 16'); self.add(tag)
diagram = keep_clear_of_tag(diagram, tag)
self.play(FadeIn(diagram))
self.play(tag.set('Added example · based on slide 16'))
keep_clear_of_tag(diagram, tag)  # recheck when citation dimensions change
```

`SourceTag(text)` wraps in a bottom-right six-unit column inside the 13×7 area;
`.set(text)` returns Transform, preserving the managed object. `source_tag()`
remains compatible with old lessons. Both carry `_studio_source_tag=True` for
review tooling. `fit_to_frame(mobject, margin=.15)` mutates and returns its input,
scaling only if every Text stays >=20, then clamps its position. `keep_clear_of_tag
(mobject, tag, gap=.18, margin=.15)` first fits, then tries moving above or left
of the tag. It raises if neither can fit. Check individual unrelated diagrams
separately; these functions do not solve all scene-wide collisions.

## Short source beats

```python
with self.voiceover(text='This line states the rule we will demonstrate.'):
    slide_excerpt(self, SRC/'slide-016.png', [(.1,.2,.9,.4), (.1,.5,.9,.7)],
                  'IP Forwarding · slide 16', hold=1)
```

`slide_excerpt(scene, path, regions, tag_text, hold=1)` fits SlideImage away from
the tag, highlights sequential normalized (x0,y0,x1,y1) rectangles, and removes
its image, tag, and final highlight. It leaves preexisting scene objects alone.
Hold is per region, excluding fades; empty regions hold the whole slide.
The caller supplies narration. Keep total excerpts short (normally <10 seconds).

## Forwarding and ternary matching

```python
table = ForwardingTable([('100*','link 6'), ('1*','link 2'), ('*','default')])
self.play(FadeIn(table))
self.play(table.highlight_matches('100100'))
self.play(table.show_winner('100100'))
row = table.winner('100100')  # 0, or None for no match
```

`PrefixTable(rows, headers=None, size=24, **MemoryTable_options)` and its alias
`ForwardingTable` grow columns to measured content. Binary prefixes optionally
end in `*`; `*` alone is the installed default. Alternatively use IP CIDRs and
an IP destination, without mixing modes or IP versions. `.matching_rows(dst)`
returns all row indices; `.winner(dst)` selects the longest, first row on ties.
`.highlight_matches(dst)` resets stale highlights and lights every match in
parallel; `.show_winner(dst)` leaves only the winning row green. No-match clears
all rows. Add an explicit outcome label in narration or by reading `.winner()`.

`TernaryTable(rows, **options)` accepts equal-width 0/1/* patterns and a binary
destination of exactly that width. It uses the same highlight/query methods.
Priority is FIRST matching row, not count of fixed bits: arbitrary ternary masks
have no LPM ordering. For prefix masks, explicitly sort rows longest-prefix-first.

```python
tcam = TernaryTable([('100*','specific'), ('1***','general'), ('****','default')])
self.play(tcam.highlight_matches('1001')); self.play(tcam.show_winner('1001'))
```

## Small topologies and local headers

```python
net = Topology({'A':(-4,1), 'R':(0,1), 'B':(4,1)},
               [('A','R','LAN 1'), ('R','B','LAN 2')])
self.play(FadeIn(net))
pkt = Packet('data'); self.add(pkt)
self.play(net.hop_path(pkt, ['A','R']))
headers = FieldBar([('A → R',3), ('IP: A → B',4)], unit=1)
self.play(net.rewrite_header(headers, 'R','B'))
self.play(net.hop_path(pkt, ['R','B']))
```

`Topology(nodes, links)` takes name → (x,y) positions and (src,dst[,label])
links. Node labels are inside opaque boxes; link labels are searched on both
sides of their link, avoiding all links, nodes and earlier labels. Impossible
label or node arrangements raise. Keep specs small, avoid links through other
nodes, and inspect crossings. `.nodes[name]` exposes the actual Node.
`.hop_path(packet, nodes, run_time=2)` returns a polyline animation over installed
links, without adding/fading the packet. `.rewrite_header(bar, src, dst, field=0)`
changes only the specified FieldBar field and validates its width. It does not
model TTL/checksum/NAT; explain and animate those separately when relevant.
Move the complete topology, not nodes independently, after creation.

## Steppers and bit splits

```python
flow = FlowSteps(['Read destination', 'Find the longest match', 'Send to next hop'])
self.play(FadeIn(flow)); self.play(flow.highlight(1))  # zero-based index
code = Pseudocode(['route = lookup(dst)', 'send(route.next_hop)'])
bits = BitString('10010011', prefix=3)
self.play(bits.highlight(0))
```

`FlowSteps(steps, width=9, size=26, numbered=True, mono=False)` wraps rows and
highlights one current step at a time, resetting the others. `Pseudocode(lines,
**options)` is the monospace variant. Too many steps raise; split the pipeline.
`BitString(bits, prefix, size=24, **FieldBar_options)` creates a colored prefix
and remaining-bit split, including /0 and full-prefix cases. Widths grow to fit
both bits and captions; field widths are explicitly NOT proportional to bits.
Existing `FieldBar` remains unchanged for exact proportional diagrams; allocate
enough width for its labels yourself.

## Estimated reduction versus existing lesson patterns

Counts are estimates of nonblank visual setup/animation lines, excluding narration;
no existing lesson was rewritten. Composing several patterns typically saves
40–90 lines per section, depending on how many beats repeat.

| Existing read-only example | Handwritten | With helper | Saved |
|---|---:|---:|---:|
| `07-endnodes/FourProblems`: slide/tag/highlight lifecycle | 20 | 3 | 17 |
| `01-where-routers-fit/LocalHeaders`: nodes, links, local-header rewrite | 12 | 6 | 6 |
| `ip-forwarding/LongestPrefix`: match selection/reset at 3 destinations | 18 | 6 | 12 |
| `ip-forwarding/FastLookups`: TCAM match highlights | 6 | 3 | 3 |
| `05-longest-prefix`: numbered forwarding rules | 8 | 3 | 5 |
| Vocabulary beat with wrapping + panel + safety checks | 12–18 | 3 | 9–15 |

These are bounded examples inspected directly because graph metadata was stale
for cslib and examples were excluded. They are not an exhaustive repository audit.

## Six-line SKILL.md reference insertion

```text
High-level layouts: see references/cslib-patterns.md for examples and constraints.
- definition_card(term, meaning): wrapped vocabulary beat before mechanics.
- slide_excerpt(scene, path, regions, tag_text, hold=1): cited highlights + cleanup.
- PrefixTable/ForwardingTable, TernaryTable: measured cells and match/winner animations.
- Topology, FlowSteps/Pseudocode, BitString: hops, header rewrites, steps, bit splits.
- fit_to_frame, keep_clear_of_tag, SourceTag.set(): safe-area and citation management.
```

## Helper list (semantic notes) (`from studio.cslib import ...`)
- `definition_card(term, meaning)`: wrapped vocabulary definition before mechanics.
- `slide_excerpt(scene, path, regions, tag_text, hold=1)`: cited highlights with cleanup.
- `PrefixTable` / `ForwardingTable`: measured prefix rows and longest-match animations.
- `TernaryTable`: first-match ternary rows (sort prefix masks explicitly for LPM).
- `Topology`: small networks with `.hop_path()` and local `.rewrite_header()` animations.
- `FlowSteps` / `Pseudocode`: wrapped steps with one active highlight.
- `BitString`: labeled prefix/remainder split; widths are not bit-proportional.
- `SourceTag(text)`: managed citation; `.set(text)` returns an update animation.
- `fit_to_frame(obj)`: fit/clamp inside the safe area without text below size 20.
- `keep_clear_of_tag(obj, tag)`: fit and move above/left of a citation, or raise.
- `label(text, size=24, color=FG, mono=False)` → Text; `bullets(items, size=30)` → VGroup.
- `Node(name, sublabel=None, kind="host"|"server"|"router"|"process"|"disk")`; `.flash()`.
- `Packet(text, color=YELLOW)`; `packet_flight(packet, start, end, run_time=1.5)` → animation.
- `Queue(capacity=5, title=None)`; `.enqueue("P1")` → anim; `anim, item = q.dequeue()`.
- `MemoryTable(rows, headers=None)`; `.highlight_row(r)`, `.highlight_cell(r, c)`,
  `.clear_highlight()`, `.set_cell(r, c, value)` → anims; `.cell(r, c)`.
- `Gantt([(label, start, end), ...], unit=0.8, title=None)`; `.axis_animation()`,
  `.block_animations()`, `.build()`.
- `SequenceDiagram(participants, width=8, height=5.5)`; `.create()`;
  `anim, arrow = .message(src, dst, text)`; `anim, lbl = .note(participant, text)`.
- `SlideImage(path, height=6)`; `.highlight(x0, y0, x1, y1)` → Rectangle; `.region_point(fx, fy)`.
- `source_tag(text, corner=DOWN+RIGHT)` → small DIM citation Text in a safe-area corner.
- `StudyScene` (`studio.base`): `.section_title(title, subtitle=None)`, `.clear_all()`.

## Beat helpers (motion while the narration explains)

```python
with self.voiceover(text="Each request crosses the link to the server.") as t:
    self.play(flow_flash(link), run_time=t.duration)          # pulse along an existing line/arrow
with self.voiceover(text="Only this row matters for the lookup.") as t:
    self.play(focus([table.cell(2, 1)], self.mobjects))         # dim everything else
    self.wait(t.get_remaining_duration())
self.play(unfocus(self.mobjects))                               # restore recorded opacities
eq = TermEquation(["risk", " = ", "likelihood", " × ", "impact"]).dimmed()
self.play(FadeIn(eq)); self.play(eq.reveal(0)); self.play(eq.reveal(2, 4))
```

- `flow_flash(path, color=YELLOW, width=8, time_width=.4, run_time=1.2)`: temporary pulse; path unchanged.
- `focus(keep, context, opacity=.3)` / `unfocus(context)`: records each dimmed part's fill/stroke
  opacity and restores exactly those values; source tags never dim. Recolor after unfocus, not during.
- `TermEquation(parts, size=36, colors={i: color})`: one Text (natural kerning) with `.terms[i]` per
  part; `.dimmed()`, `.reveal(*idx, context=.6)`, `.reveal_all()`. Characters must map 1:1 to glyphs
  (plain text and Unicode math; raises otherwise).
- `pulse(mob, color=YELLOW, scale=1.06)`: emphasis with no new outline: swell + the object's own border
  lights up (Node, cell); text swells and tints; a slide highlight box thickens in place. Use instead
  of `Indicate` on filled boxes (Indicate repaints the fill and covers the box's own label) and on
  highlight boxes (scaling them unmatches the slide).
- `identify(mob)`: animated outline sweep (Circumscribe) to single out important **text**. Sparingly:
  at most once or twice a scene; not on things that already have a border (Node, cell, highlight)
  unless picking one out of several look-alikes.
- `SlideImage.highlight(x0, y0, x1, y1)` snaps by default: rough fractions are tightened to the whole
  slide objects (photos, text lines, shapes) mostly inside, so boxes never cut through an object or
  pick up a title rule. `snap=False` keeps the exact fractions; `slide.snap(...)` returns the
  snapped fractions. Check boxes on the review sheet.
- `MemoryTable.fill_from(r, c, value, sources=[(r, c), ...])`: copies of source cells fly into a cell
  that becomes `value` (XOR columns, routing-table updates); keeps the table's own text object.
- Built-ins worth using: `TransformFromCopy(value, cell)` (value moves into a table/field),
  `FadeTransform(a, b)` for unlike shapes, `rate_func=linear` for constant-speed travel,
  `LaggedStart(..., lag_ratio=.3)` to stretch a build-up over a sentence.
