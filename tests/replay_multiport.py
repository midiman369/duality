"""Multi-port playback on Roland's SC-8850 demo "Space Flight" (05ORCHE.MID, 32 channels on ports A / B).

Through Duality's own player (fake ports, fake clock):
  - one unit: port A plays, port B is dropped (no unit for it);
  - two units: A on unit 1, B on unit 2, each port's programs only on its unit;
  - six units with Anima: A on units 1-3, B on 4-6;
  - no hanging notes, no drops, and port A's GS reset / reverb settings reach port B's units.
"""
import os
import sys
import time as _time

import common
import mido

CLOCK = [1000.0]
_time.monotonic = lambda: CLOCK[0]
_time.time = lambda: CLOCK[0]
import duality as D
from rich.console import Console
D.console = Console(file=open(os.devnull, "w"))

song = common.midi("05orche.mid")
REC = []


class FakeOut:
    def __init__(s, i): s.i = i; s.name = f"U{i + 1}"; s.closed = False
    def send(s, m): REC.append((round(CLOCK[0] - 1000.0, 3), s.i, m))
    def close(s): pass
    reset = panic = close


D.mido.open_output = lambda n, *a, **k: FakeOut(int(n[1:]) - 1)
fails = []


def play(n_units, anima):
    REC.clear()
    names = [f"U{i + 1}" for i in range(n_units)]
    d = D.Duality(None, names, show_status=False, out_formats=[frozenset({"gm2", "gs8850"})] * n_units,
                  poly_limits=[64] * n_units, anima=anima, anima_seed=0x5150, play=[song])
    d.player.threaded = False
    plans = []
    CLOCK[0] = 1000.0
    while d.player.state != "done":
        d._service()
        if d._lanes and not plans:
            plans.append({p: list(o) for p, o in d._lane_outs.items()})
        p = d.player
        nxt = CLOCK[0] + 0.01
        if p.state == "playing" and p.song and p.pos < len(p.song.events):
            nxt = min(nxt, max(CLOCK[0] + 0.0005, p.t0 + p.song.events[p.pos][0]))
        CLOCK[0] = nxt
    for _ in range(300):
        CLOCK[0] += 0.01
        d._service()
    held = {}
    for t, i, m in REC:
        if m.type == "note_on" and m.velocity:
            held[(i, m.channel, m.note)] = held.get((i, m.channel, m.note), 0) + 1
        elif m.type in ("note_on", "note_off"):
            k = (i, m.channel, m.note)
            if held.get(k):
                held[k] -= 1
    hang = [k for k, v in held.items() if v > 0 and k[1] != 9]
    ons = {}
    for t, i, m in REC:
        if m.type == "note_on" and m.velocity:
            ons[i] = ons.get(i, 0) + 1
    print(f"{n_units} unit(s){' anima' if anima else ''}: lanes {plans}, notes per unit {dict(sorted(ons.items()))}, "
          f"hang {len(hang)}, drops {d.drop_count}")
    return d, plans, hang


d, plans, hang = play(1, False)
if plans or hang:
    fails.append(f"one unit: lanes {plans}, hang {hang}")
d, plans, hang = play(2, False)
if plans != [{0: [0], 1: [1]}] or hang:
    fails.append(f"two units: lanes {plans}, hang {hang}")
# the first program each unit gets on ch1: port A's violin (Strings) on unit 1, port B's piccolo on unit 2
first = {}
for t, i, m in REC:
    if m.type == "program_change" and m.channel == 0 and i not in first:
        first[i] = m.program
if first.get(0) == first.get(1):
    fails.append(f"ch1 programs per unit {first}: ports A and B should differ")
gs_reset_units = {i for t, i, m in REC if m.type == "sysex" and list(m.data[:7]) == [0x41, 0x10, 0x42, 0x12, 0x40, 0x00, 0x7F]}
if gs_reset_units != {0, 1}:
    fails.append(f"GS reset reached units {gs_reset_units}, want both")
d, plans, hang = play(6, True)
if plans != [{0: [0, 1, 2], 1: [3, 4, 5]}] or hang or d.drop_count:
    fails.append(f"six units: lanes {plans}, hang {hang}, drops {d.drop_count}")
print("FAILS:" if fails else "PASS")
for f in fails:
    print("  ", f)
sys.exit(1 if fails else 0)
