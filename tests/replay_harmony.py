"""Harmony balance on Death Gate (XMI2MID songs; SONG=03|07|97, default 07).

Checks, with the song replayed through Anima at seed 6BA1:
  - every harmony ghost is at most ANIMA_HARM_VEL (or ACC/LOW) of the file's velocity
  - an accompaniment hero is played at ANIMA_HARM_ACC_HERO, its ghost below it
  - no upper ghost of a lower part is left at or over a line that starts above it
  - harmony count stays near its measured level (wall of sound kept)
"""
import os
import sys
import collections
import time as _time
import common
import mido

SONG = os.environ.get("SONG", "07")
FLOOR = {"03": 140, "07": 215, "97": 1050}[SONG]
PATH = common.midi(f"death-gate-{SONG}.mid")

CLOCK = [1000.0]
_time.monotonic = lambda: CLOCK[0]
_time.time = lambda: CLOCK[0]
REC = []

class FakeOut:
    def __init__(self, i): self.idx = i; self.name = f"P{i+1}"; self.closed = False
    def send(self, m): REC.append((CLOCK[0], self.idx, m))
    def close(self): pass
    def reset(self): pass
    def panic(self): pass

class FakeIn:
    name = "in"; closed = False
    def poll(self): return None
    def iter_pending(self): return iter(())
    def close(self): pass

_outs = {}
def open_output(name, *a, **k):
    _outs[name] = FakeOut(len(_outs)); return _outs[name]

import duality as D
D.mido.open_output = open_output
D.mido.open_input = lambda *a, **k: FakeIn()
d = D.Duality("in", [f"P{i+1}" for i in range(4)], anima=True, show_status=False,
              out_formats=[frozenset({"gs"})] * 4, anima_seed=0x6BA1, poly_limits=[64] * 4)
LOG = []
_log = D.Duality._anima_ghost_log
d._anima_ghost_log = lambda text: (LOG.append(text), _log(d, text))

mf = common.load(PATH)
events, t = [], 0.0
for m in mf:
    t += m.time
    if not m.is_meta:
        events.append((t, m))

fails = []
modes = collections.Counter()
i, tt, end = 0, 0.0, events[-1][0] + 1.0
while tt <= end:
    CLOCK[0] = 1000.0 + tt
    while i < len(events) and events[i][0] <= tt + 1e-9:
        m = events[i][1]
        i += 1
        n0, l0 = len(REC), len(LOG)
        d.process(m)
        if not (m.type == "note_on" and m.velocity) or m.channel == 9:
            continue
        harm = [x for x in LOG[l0:] if x.startswith("harm ") and not x.startswith("harm yield")]
        mine = [x for x in harm if f" ch{m.channel + 1} n{m.note} " in x]
        if mine:
            mode = mine[0].split()[1]
            modes[mode] += 1
            outs = [(p, x) for _t, p, x in REC[n0:]
                    if x.type == "note_on" and x.velocity and x.channel == m.channel]
            hero = [x.velocity for p, x in outs if x.note == m.note]
            ghosts = [x for p, x in outs if x.note != m.note]
            cap = {"acc": D.ANIMA_HARM_ACC_VEL}.get(mode, D.ANIMA_HARM_VEL)
            # Humanize may lift a repeated note before harmony scales it.
            lift = max(D.ANIMA_HUMANIZE_UP, D.ANIMA_HUMANIZE_HOT_UP)
            for g in ghosts:
                if g.velocity > (m.velocity + lift) * cap + 1:
                    fails.append(f"t={tt:.2f} ch{m.channel+1} n{m.note} {mode} ghost n{g.note} "
                                 f"v{g.velocity} > {cap:.2f} x v{m.velocity}")
            if mode == "acc" and hero and hero[0] > round((m.velocity + lift) * D.ANIMA_HARM_ACC_HERO) + 1:
                fails.append(f"t={tt:.2f} ch{m.channel+1} n{m.note} acc hero v{hero[0]} not lowered")
        # Upper ghosts of lower parts must not sit on a line that starts above them.
        if d._anima_is_rhythm(m.channel) or d._anima_category(m.channel) in D.ANIMA_HARM_QUIET_CATS:
            continue
        for hkey, gnote in d._anima_harm_up.items():
            if hkey[0] != m.channel and hkey[1] < m.note and gnote >= m.note - 2 \
                    and hkey in d._anima_ghosts:
                fails.append(f"t={tt:.2f} ch{hkey[0]+1} upper ghost n{gnote} left over "
                             f"ch{m.channel+1} n{m.note}")
    d._check_anima_session_idle()
    tt = round(tt + 0.005, 3)

total = sum(modes.values())
print(f"Death Gate {SONG}: harmonised {total} notes {dict(modes)}")
if total < FLOOR:
    fails.append(f"only {total} harmonised notes (floor {FLOOR}): wall of sound thinned")
if fails:
    print(f"FAILS ({len(fails)}):")
    for f in fails[:20]:
        print("   ", f)
    sys.exit(1)
print("PASS")
