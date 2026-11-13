"""Self-authored, asset-free example; macOS say is used only for this draft."""
from manim import Arrow, Create, Dot, FadeIn, LEFT, RIGHT, RoundedRectangle, Text, VGroup
from studio import style
from studio.base import StudyScene
from studio.cslib import source_tag

class PacketJourney(StudyScene):
    def construct(self):
        title = Text("A packet journey", font=style.FONT, font_size=40).move_to([0, 2.7, 0])
        source = source_tag("Added example")
        sender = VGroup(RoundedRectangle(width=2.4, height=1.1, color=style.BLUE),
                        Text("Sender", font=style.FONT, font_size=30)).move_to([-3.3, 0, 0])
        receiver = VGroup(RoundedRectangle(width=2.4, height=1.1, color=style.TEAL),
                          Text("Receiver", font=style.FONT, font_size=30)).move_to([3.3, 0, 0])
        packet = Dot(sender.get_right()+RIGHT*0.3, radius=0.16, color=style.GOLD)
        connection = Arrow(sender.get_right(), receiver.get_left(), buff=0.18)
        with self.voiceover(text="A packet is a small unit of data sent between devices.") as t:
            self.play(FadeIn(title), FadeIn(source), FadeIn(sender), FadeIn(receiver),
                      FadeIn(packet), run_time=min(1.5, t.duration))
        with self.voiceover(text="We show it moving from the sender to the receiver.") as t:
            self.play(Create(connection), run_time=0.5)
            self.play(packet.animate.move_to(receiver.get_left()+LEFT*0.3),
                      run_time=max(0.1, min(3.0, t.duration-0.5)))
        self.clear_all()
