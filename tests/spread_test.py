"""Family spread and the player's look-ahead (1.0.004).

Built-in (no song files):
  1. live, two GS units, five mallet channels (one family: chromatic) panned left to right: the
     family spreads onto the spare unit, the right-hand channels move, each Part EFX On there comes
     with the Part Off on the old unit, no moved channel plays within 100 ms of its move, and no
     insert type is written on a unit while one of its players sounds
  2. the same, a clean guitar arriving later: it takes the spread unit back once that is quiet, and
     the moved mallets play on their family's unit again (Part EFX On there)
  3. the player, one GS unit: strings until 5 s (the brass's program change at 4 s, under them), then
     brass straight on (no gap) to 7 s, a rest, brass again to 9.6 s; the choir enters at 26 s, once the
     brass's claim has run out. The brass starts dry (no type write at its first note) and gets its
     insert in its rest; the choir's Part EFX On comes ahead of its first note (no type write at it)
"""
import os
import sys
import tempfile
import time as _time
import common  # noqa: F401
import mido

CLOCK = [1000.0]
_time.monotonic = lambda: CLOCK[0]
_time.time = lambda: CLOCK[0]
REC = []


class FakeOut:
    def __init__(self, i): self.idx = i; self.name = f"P{i+1}"; self.closed = False
    def send(self, m): REC.append((CLOCK[0] - 1000.0, self.idx, m))
    def close(self): pass
    reset = panic = close


class FakeIn:
    name = "in"; closed = False
    def poll(self): return None
    def iter_pending(self): return iter(())
    def close(self): pass


import duality as D
from rich.console import Console
D.console = Console(file=open(os.devnull, "w"))
D.mido.open_output = lambda n, *a, **k: FakeOut(int(n[1:]) - 1)
D.mido.open_input = lambda *a, **k: FakeIn()
fails = []
MALLETS = [(0, 12, 20), (1, 11, 40), (2, 13, 70), (3, 9, 96), (4, 14, 112)]   # ch, program, pan
GTR = 5


def run(events, end, units):
    REC.clear()
    CLOCK[0] = 1000.0
    d = D.Duality("in", [f"P{i+1}" for i in range(units)], anima=True, show_status=False,
                  out_formats=[frozenset({"gs"})] * units, anima_seed=0x2B17, poly_limits=[64] * units)
    events = sorted(events, key=lambda e: e[0])
    i, tt = 0, 0.0
    while tt <= end:
        CLOCK[0] = 1000.0 + tt
        while i < len(events) and events[i][0] <= tt + 1e-9:
            d.process(events[i][1]); i += 1
        d._anima_tick()
        d._check_anima_session_idle()
        tt = round(tt + 0.005, 3)
    return d


def on(t, ch, n, dur, vel=90):
    return [(t, mido.Message("note_on", channel=ch, note=n, velocity=vel)),
            (t + dur, mido.Message("note_off", channel=ch, note=n, velocity=0))]


def mallets(end, guitar_at=None):
    ev = []
    for ch, pc, pan in MALLETS:
        ev += [(0.1, mido.Message("program_change", channel=ch, program=pc)),
               (0.1, mido.Message("control_change", channel=ch, control=10, value=pan))]
    t = 1.0
    while t < end - 2:
        for k, (ch, _pc, _pan) in enumerate(MALLETS):     # chords on the beats, each channel resting between
            for b in range(4):
                ev += on(t + b * 0.5 + 0.01 * k, ch, 60 + 2 * k + (b % 2) * 3, 0.25, 80)
        t += 2.5                                           # half a second of rest every bar
    if guitar_at is not None:
        ev.append((guitar_at, mido.Message("program_change", channel=GTR, program=27)))
        g = guitar_at + 0.5
        while g < end - 2:
            ev += on(g, GTR, 64, 0.2, 90)
            g += 0.5
    return ev


def part_toggles(ch):
    """(t, port, on) for Part EFX writes of ch (40 4x 22)."""
    return [(t, p, m.data[7]) for t, p, m in REC if m.type == "sysex" and list(m.data[:4]) == [0x41, 0x10, 0x42, 0x12]
            and m.data[4] == 0x40 and m.data[6] == 0x22 and m.data[5] == D.Duality._gs_efx_part_mid(ch)]


def type_writes():
    return [(t, p, tuple(m.data[7:9])) for t, p, m in REC if m.type == "sysex"
            and list(m.data[:7]) == [0x41, 0x10, 0x42, 0x12, 0x40, 0x03, 0x00]]


def no_type_under_player(tag):
    for tw, p, typ in type_writes():
        for c in range(16):
            tog = [(t, v) for t, pp, v in part_toggles(c) if pp == p and t <= tw]
            if not tog or tog[-1][1] != 1:
                continue
            held = {}
            for t, pp, m in REC:
                if t > tw:
                    break
                if pp == p and getattr(m, "channel", -1) == c and m.type in ("note_on", "note_off"):
                    held[m.note] = m.type == "note_on" and m.velocity > 0
            if any(held.values()):
                fails.append(f"{tag}: type {typ} written on P{p+1} at {tw:.2f}s while ch{c+1} sounds there")


# 1. spread
d = run(mallets(30.0), 30.0, 2)
ports = {ch: d._anima_ch_port.get(ch) for ch, _pc, _pan in MALLETS}
used = set(ports.values())
if len(used) != 2 or None in used:
    fails.append(f"1: the family did not spread over two units: {ports}")
else:
    left = [ports[ch] for ch, _pc, pan in MALLETS if pan < 64]
    if len(set(left)) != 1 or ports[MALLETS[-1][0]] == left[0]:
        fails.append(f"1: not the right-hand channels that moved: {ports}")
    for ch, _pc, _pan in MALLETS:
        tog = part_toggles(ch)
        for t, p, v in tog:
            if v != 1 or p != ports[ch] or not any(pp != p and vv == 0 and abs(tt - t) < 0.001 for tt, pp, vv in tog):
                continue
            near = [tt for tt, pp, m in REC if m.type == "note_on" and m.velocity and m.channel == ch
                    and 0 <= tt - t < 0.100]
            if near:
                fails.append(f"1: ch{ch+1} played {near[0] - t:.3f}s after its move")
    moved = [ch for ch, _pc, _pan in MALLETS if any(
        v == 1 and p == ports[ch] and any(pp != p and vv == 0 and abs(tt - t) < 0.001 for tt, pp, vv in part_toggles(ch))
        for t, p, v in part_toggles(ch))]
    if not moved:
        fails.append("1: no move came with its Part EFX Off on the old unit")
    print(f"1 spread: {ports} (moved {[c + 1 for c in moved]})")
no_type_under_player("1")

# 2. a guitar arriving later takes the spread unit back
d = run(mallets(40.0, guitar_at=20.0), 40.0, 2)
gp = d._anima_ch_port.get(GTR)
mp = {d._anima_ch_port.get(ch) for ch, _pc, _pan in MALLETS}
if gp is None or gp in mp:
    fails.append(f"2: the guitar did not get the spread unit (guitar {gp}, mallets {mp})")
elif len(mp) != 1 or not all(d._anima_efx_on[next(iter(mp))][ch] for ch, _pc, _pan in MALLETS):
    fails.append(f"2: the mallets are not back on their family's unit with Part EFX On ({mp})")
print(f"2 guitar later: guitar P{None if gp is None else gp + 1}, mallets {sorted(p + 1 for p in mp if p is not None)}")
no_type_under_player("2")

# 3. the player's look-ahead
STR, BRS, CHO = 0, 1, 2
mf = mido.MidiFile(type=0, ticks_per_beat=480)
tr = mido.MidiTrack()
mf.tracks.append(tr)
ev = [(0.0, mido.Message("program_change", channel=STR, program=48)),
      (0.0, mido.Message("program_change", channel=CHO, program=52)),
      (4.0, mido.Message("program_change", channel=BRS, program=61))]
for k in range(8):                                   # strings 1.0 - 5.0 s
    ev += on(1.0 + k * 0.5, STR, 60 + (k % 3), 0.5, 80)
for k in range(8):                                   # brass straight on, 5.0 - 7.0 s
    ev += on(5.0 + k * 0.25, BRS, 60, 0.25, 90)
for k in range(8):                                   # a rest, then brass 7.6 - 9.6 s
    ev += on(7.6 + k * 0.25, BRS, 62, 0.25, 90)
for k in range(6):                                   # the choir, from 26 s
    ev += on(26.0 + k * 0.5, CHO, 64, 0.5, 80)
last = 0
for t, m in sorted(ev, key=lambda e: (e[0], e[1].type == "note_on")):
    tk = int(round(t * 960))                        # 120 BPM: 960 ticks a second
    tr.append(m.copy(time=tk - last))
    last = tk
path = os.path.join(tempfile.mkdtemp(prefix="spread-"), "lookahead.mid")
mf.save(path)
REC.clear()
D.mido.open_output = lambda n, *a, **k: FakeOut(int(n[1:]) - 1)
d = D.Duality(None, ["P1"], anima=True, show_status=False, out_formats=[frozenset({"gs"})], anima_seed=0x2B17,
              poly_limits=[64], play=[path], anima_foley=0.0)
d.player.threaded = False
CLOCK[0] = 1000.0
while CLOCK[0] < 1032.0:
    d._service()
    CLOCK[0] = round(CLOCK[0] + 0.005, 3)


def first_on(ch):
    return min(t for t, p, m in REC if m.type == "note_on" and m.velocity and m.channel == ch)


b0, c0 = first_on(BRS), first_on(CHO)
tw = type_writes()
at_brass = [t for t, p, typ in tw if abs(t - b0) < 0.1]
if at_brass:
    fails.append(f"3: an insert type written at the brass's first note ({at_brass[0] - b0:+.3f}s)")
brass_on = [t for t, p, v in part_toggles(BRS) if v == 1]
if not brass_on or not (b0 + 2.0 - 0.01 <= brass_on[0] <= b0 + 2.6):
    fails.append(f"3: the brass's Part EFX On not in its rest (7.0 - 7.6 s of the song): {brass_on[:1]} (first note {b0:.2f})")
cho_type = [t for t, p, typ in tw if abs(t - c0) < 0.1]
cho_on = [t for t, p, v in part_toggles(CHO) if v == 1 and t <= c0]
if cho_type:
    fails.append(f"3: an insert type written at the choir's first note ({cho_type[0] - c0:+.3f}s)")
if not cho_on or c0 - cho_on[-1] < D.ANIMA_EFX_WET_SEC or c0 - cho_on[-1] > D.ANIMA_LOOKAHEAD_PREP + 0.1:
    fails.append(f"3: the choir's Part EFX On not ahead of its first note: {cho_on[-1:]} (note {c0:.2f})")
print(f"3 look-ahead: brass first note {b0:.2f}s, its Part On {brass_on[:1]}; choir first note {c0:.2f}s, "
      f"its Part On {[round(t, 2) for t in cho_on[-1:]]}")
no_type_under_player("3")

if fails:
    print(f"FAILS ({len(fails)}):")
    for f in fails:
        print("   ", f)
    sys.exit(1)
print("PASS")
