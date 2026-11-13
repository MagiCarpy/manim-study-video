"""Smoke-test lesson: exercises StudyScene + every cslib helper."""

from contextlib import nullcontext
from pathlib import Path

from manim import DOWN, LEFT, RIGHT, UP, Create, FadeIn, FadeOut, Write

from studio import style
from studio.base import StudyScene
from studio.cslib import (Gantt, MemoryTable, Node, Queue, SequenceDiagram, SlideImage,
                          bullets, label)

SRC = Path(__file__).parent / "source" / "slides"


class Intro(StudyScene):
    def construct(self):
        slide = SlideImage(SRC / "slide-001.png", height=5.6)
        with self.voiceover(text="Here's the slide we're starting from: TCP connection setup.") as t:
            self.play(FadeIn(slide), run_time=min(1.5, t.duration))
        box = slide.highlight(0.07, 0.49, 0.66, 0.58)
        with self.voiceover(text="The key idea is this line: a three-way handshake of SYN, SYN-ACK, and ACK.") as t:
            self.play(Create(box), run_time=1.0)
        self.play(FadeOut(slide), FadeOut(box))


class Handshake(StudyScene):
    def construct(self):
        title = self.section_title("TCP three-way handshake")
        sd = SequenceDiagram(["Client", "Server"], width=6.5, height=5.2, step=1.15)
        sd.next_to(title, DOWN, buff=0.35)
        with self.voiceover(text="Two hosts: a client, which starts closed, and a server, listening.") as t:
            self.play(sd.create(), run_time=1.5)
            a1, _ = sd.note("Client", "CLOSED", color=style.DIM)
            a2, _ = sd.note("Server", "LISTEN", color=style.DIM)
            self.play(a1, a2)

        # Event order (verified in notes.md): a state label goes at the event that causes it.
        with self.voiceover(text="First, the client sends a SYN carrying its initial sequence number, x. "
                                 "It is now in the SYN-sent state.") as t:
            anim, _ = sd.message("Client", "Server", "SYN seq=x", color=style.YELLOW)
            self.play(anim)
            note, _ = sd.note("Client", "SYN_SENT")
            self.play(note)

        with self.voiceover(text="When the SYN arrives, the server answers with a SYN-ACK: its own sequence "
                                 "number y, and an acknowledgment of x plus one.") as t:
            note, _ = sd.note("Server", "SYN_RCVD")      # at the SYN's arrival
            self.play(note)
            anim, _ = sd.message("Server", "Client", "SYN-ACK seq=y ack=x+1", color=style.BLUE)
            self.play(anim)

        with self.voiceover(text="The client is now established, and acknowledges y plus one. "
                                 "When that ACK arrives, the server is established too.") as t:
            n1, _ = sd.note("Client", "ESTABLISHED", color=style.GREEN)   # at SYN-ACK arrival
            self.play(n1)
            anim, _ = sd.message("Client", "Server", "ACK ack=y+1", color=style.GREEN)
            self.play(anim)
            n2, _ = sd.note("Server", "ESTABLISHED", color=style.GREEN)   # at ACK arrival
            self.play(n2)
        self.clear_all()


class RoundRobin(StudyScene):
    # (process, start, end) -- see notes.md for the verified trace
    SCHEDULE = [("P1", 0, 2), ("P2", 2, 4), ("P3", 4, 5), ("P1", 5, 7), ("P2", 7, 8)]
    REMAINING = {"P1": 4, "P2": 3, "P3": 1}

    def construct(self):
        title = self.section_title("Round robin", "quantum q = 2, all arrive at t = 0")
        colors = {"P1": style.BLUE, "P2": style.TEAL, "P3": style.GOLD}
        queue = Queue(4, title="Ready queue").move_to(LEFT * 3.2 + UP * 0.9)
        cpu = Node("CPU", kind="process", width=1.8, height=1.2).move_to(RIGHT * 3.2 + UP * 0.9)
        gantt = Gantt(self.SCHEDULE, unit=0.9, colors=colors).move_to(DOWN * 2.2)

        with self.voiceover(text="Now round robin. Three processes wait in the ready queue, "
                                 "and each may run for at most two time units.") as t:
            self.play(FadeIn(queue), FadeIn(cpu), gantt.axis_animation())
            self.play(*[queue.enqueue(p, colors[p]) for p in ("P1", "P2", "P3")])

        remaining = dict(self.REMAINING)
        texts = {
            0: "P1 runs for one quantum, then goes to the back of the queue.",
            1: "P2 does the same.",
            2: "P3 needs only one unit, so it finishes early.",
            3: "P1 finishes its last two units, and P2 wraps up at time eight.",
        }
        blocks = gantt.block_animations()
        for i, (proc, t0, t1) in enumerate(self.SCHEDULE):
            narration = texts.get(i)
            with self.voiceover(text=narration) if narration else nullcontext():
                anim, item = queue.dequeue()
                self.play(anim, run_time=0.5)
                self.play(item.animate.move_to(cpu.box), run_time=0.5)
                self.play(blocks[i])
                remaining[proc] -= t1 - t0
                if remaining[proc] > 0:
                    self.play(queue.enqueue(item), run_time=0.6)
                else:
                    self.play(FadeOut(item), run_time=0.4)

        with self.voiceover(text="Average waiting time: three, five and four, so four time units.") as t:
            avg = label("avg wait = (3 + 5 + 4) / 3 = 4", size=style.BODY_SIZE, color=style.YELLOW)
            avg.next_to(gantt, UP, buff=0.5)
            self.play(Write(avg))
        self.clear_all()


class Recap(StudyScene):
    def construct(self):
        title = self.section_title("Recap")
        table = MemoryTable(
            [["SYN", "SYN_SENT", "SYN_RCVD"],
             ["SYN-ACK", "ESTABLISHED", "SYN_RCVD"],
             ["ACK", "ESTABLISHED", "ESTABLISHED"]],
            headers=["After", "Client", "Server"], col_width=[2.0, 2.9, 2.9], size=style.SMALL_SIZE + 2,
        ).next_to(title, DOWN, buff=0.5)
        points = bullets(["Handshake: 3 segments, both sides learn the other's ISN",
                          "Round robin: fair time slices; quantum size is a trade-off"],
                         size=style.LABEL_SIZE + 2).next_to(table, DOWN, buff=0.6)
        with self.voiceover(text="To recap: the state table after each handshake segment.") as t:
            self.play(FadeIn(table))
            self.play(table.highlight_row(2, color=style.GREEN))
        with self.voiceover(text="And round robin trades responsiveness against context-switch overhead.") as t:
            self.play(FadeIn(points, shift=UP * 0.2))
        self.wait(0.5)


class HighLevel(StudyScene):
    """Short independent beats covering every new high-level helper."""
    def construct(self):
        from studio.cslib import (BitString, FieldBar, FlowSteps, ForwardingTable,
                                  Packet, PrefixTable, Pseudocode, SourceTag, TernaryTable,
                                  Topology, definition_card, fit_to_frame, keep_clear_of_tag,
                                  slide_excerpt)
        tag = SourceTag('Added explanation')
        card = keep_clear_of_tag(definition_card('Next hop', 'The neighbor receiving a packet next.'), tag)
        with self.voiceover(text='A next hop is the neighbor receiving a packet next.'):
            self.play(FadeIn(card), FadeIn(tag))
        self.play(FadeOut(card), tag.set('Added example · forwarding'))
        table = ForwardingTable([('100*', 'link 6'), ('1*', 'link 2'), ('*', 'default')])
        bits = BitString('10010011', 3).next_to(table, UP, buff=.6)
        fit_to_frame(bits)
        with self.voiceover(text='This address matches three rows. The longest prefix wins, choosing link six.'):
            self.play(FadeIn(table), FadeIn(bits))
            self.play(table.highlight_matches('10010011'))
            self.play(table.show_winner('10010011'))
        self.play(FadeOut(table), FadeOut(bits))
        ternary = TernaryTable([('10**','A'), ('1*0*','B'), ('****','default')])
        with self.voiceover(text='Ternary rows compare in parallel. A star accepts either bit. Priority selects the first matching row.'):
            self.play(FadeIn(ternary), tag.set('Added example · ternary matching'))
            self.play(ternary.highlight_matches('1001'))
            self.play(ternary.show_winner('1001'))
        self.play(FadeOut(ternary))
        net = Topology({'A':(-4,1), 'R':(0,1), 'B':(4,1)}, [('A','R','LAN 1'), ('R','B','LAN 2')])
        bar = FieldBar([('A → R', 3), ('IP: A → B', 4)], unit=1).move_to(DOWN)
        packet = Packet('data').move_to(net.nodes['A'])
        with self.voiceover(text='The packet crosses two links. The local header changes at the router. The IP endpoints stay fixed.'):
            self.play(FadeIn(net), FadeIn(bar), FadeIn(packet),
                      tag.set('Added example · local headers'))
            self.play(net.hop_path(packet, ['A','R']))
            self.play(net.rewrite_header(bar, 'R','B'))
            self.play(net.hop_path(packet, ['R','B']))
        self.play(FadeOut(net), FadeOut(bar), FadeOut(packet))
        steps = FlowSteps(['Read destination', 'Find the longest matching prefix', 'Send to next hop'])
        with self.voiceover(text='Read the destination, find the longest match, then send to the next hop.'):
            self.play(FadeIn(steps), tag.set('Added explanation'))
            for i in range(3):
                self.play(steps.highlight(i), run_time=.4)
        self.play(FadeOut(steps))
        code = Pseudocode(['route = lookup(destination)', 'send(route.next_hop)'])
        self.play(FadeIn(code)); self.play(code.highlight(0), run_time=.4)
        self.play(FadeOut(code), FadeOut(tag))
        with self.voiceover(text='A short excerpt ties the explanation back to its source.'):
            slide_excerpt(self, SRC/'slide-001.png', [(.07,.49,.66,.58), (.07,.6,.9,.75)],
                          'Smoke-test slides · slide 1', hold=.5)


class QuickLegacy(StudyScene):
    def construct(self):
        from studio.cslib import Packet, PrefixTrie, packet_flight
        queue = Queue(3).move_to(LEFT*3)
        cpu = Node('CPU', kind='process').move_to(RIGHT*3)
        with self.voiceover(text='The original building blocks still work: a queue, a processor, and a scheduling timeline.'):
            self.play(FadeIn(queue), FadeIn(cpu))
            self.play(queue.enqueue('P1'))
            anim, item = queue.dequeue(); self.play(anim)
            self.play(packet_flight(Packet('P1'), queue, cpu, run_time=.8))
        self.clear_all()
        gantt = Gantt([('P1',0,2), ('P2',2,3)])
        self.play(gantt.build()); self.clear_all()
        sd = SequenceDiagram(['A','B'], width=5, height=3)
        self.play(sd.create())
        anim, _ = sd.message('A','B','SYN', run_time=.6); self.play(anim)
        anim, _ = sd.note('B','received'); self.play(anim)
        self.clear_all()
        table = MemoryTable([['0','1'], ['1','2']], headers=['key','value'])
        points = bullets(['Plain text, no LaTeX'], size=24).next_to(table, DOWN)
        trie = PrefixTrie({'root':'', 'one':'1'}).move_to(RIGHT*4)
        table.shift(LEFT*2)
        self.play(FadeIn(table), FadeIn(points), FadeIn(trie))
        self.play(table.highlight_cell(0,1), trie.visit('1'))
        self.play(table.set_cell(0,1,'3')); self.play(table.clear_highlight())
        self.clear_all()


class Beats(StudyScene):
    """Beat helpers: flow_flash, focus/unfocus, TermEquation, bookmark-synced motion."""
    def construct(self):
        from manim import LaggedStart, Line
        from studio.cslib import Packet, SourceTag, TermEquation, flow_flash, focus, packet_flight, unfocus
        tag = SourceTag('Added example · beats'); self.add(tag)
        a = Node('Host A').move_to(LEFT * 4 + UP)
        b = Node('Router', kind='router').move_to(RIGHT * 4 + UP)
        link = Line(a.get_right(), b.get_left(), color=style.DIM)
        with self.voiceover(text='Host A is connected to a router.') as t:
            self.play(LaggedStart(FadeIn(a), Create(link), FadeIn(b), lag_ratio=.4), run_time=t.duration)
        with self.voiceover(text="Its packet travels <bookmark mark='go'/>across the link, "
                                 "<bookmark mark='in'/>and the router reads its header.") as t:
            self.wait_until_bookmark('go')
            self.play(flow_flash(link), run_time=max(t.time_until_bookmark('in'), .5))
            self.play(packet_flight(Packet('DATA'), a, b, run_time=max(t.get_remaining_duration(), .5)))
        with self.voiceover(text='Only the router matters for the next step.') as t:
            self.play(focus([b], self.mobjects), run_time=min(1, t.duration))
        self.play(unfocus(self.mobjects))
        self.play(FadeOut(a), FadeOut(b), FadeOut(link))
        eq = TermEquation(['risk', ' = ', 'likelihood', ' × ', 'impact'], colors={0: style.YELLOW}).dimmed()
        self.play(FadeIn(eq))
        with self.voiceover(text='Risk is what we want to estimate.') as t:
            self.play(eq.reveal(0), run_time=min(1, t.duration))
        with self.voiceover(text='It grows with how likely an attack is, and with how bad its impact would be.') as t:
            self.play(eq.reveal(2), run_time=t.duration / 2)
            self.play(eq.reveal(4), run_time=t.duration / 2)
        self.play(eq.reveal_all())
        self.clear_all()
