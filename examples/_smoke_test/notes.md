# Notes: smoke test

Source: `source/slides.md` (2 synthetic slides). Purpose: pipeline test, not a real lesson.

## Event sequences (verified before animating)

TCP three-way handshake (client active open, server passive open):
1. Client CLOSED -> sends SYN(seq=x) -> SYN_SENT.            [slide 1]
2. Server LISTEN receives SYN -> sends SYN-ACK(seq=y, ack=x+1) -> SYN_RCVD.  [added: seq/ack values]
3. Client receives SYN-ACK -> sends ACK(ack=y+1) -> ESTABLISHED.
4. Server receives ACK -> ESTABLISHED.

Round robin, q = 2, all arrive at t=0 in order P1(4), P2(3), P3(1):
- 0-2 P1 (rem 2) | queue after: P2 P3 P1
- 2-4 P2 (rem 1) | queue after: P3 P1 P2
- 4-5 P3 done    | queue after: P1 P2
- 5-7 P1 done    | queue after: P2
- 7-8 P2 done
Waiting = finish - burst (arrival 0): P1 7-4=3, P2 8-3=5, P3 5-1=4; average 4.

## Coverage
| Slide | Scene | Notes |
|---|---|---|
| 1 TCP Connection Setup | Intro, Handshake, Recap | ISN detail covered via seq=x / seq=y |
| 2 Round Robin | RoundRobin, Recap | quantum trade-off mentioned only in recap |
