"""Game mode: a new cue plans only its own channels, and the reroll places it at once.

A DOOM take in game mode (DosBox, four SC-VA units + an XG unit):
  - E1M1 (38-81 s) plays two distortion guitars (ch1/ch2), bass and drums, after a title
    cue and a menu cue that used ch4-ch12. Each guitar must get a unit of its own: no
    OD1/OD2 pair while units sit free, and no seat unit for a channel this cue never uses.
  - At 103.5 s a new cue (ch1-5, a strings drone starting with its PCs) arrives just before
    the reroll runs: the reroll places the cue's parts at once instead of leaving every unit
    to seat Gate Reverb.
  - Never an insert type write under a sounding EFX player.
"""
import sys, time as _time
import common
import mido
CLOCK = [1000.0]
_time.monotonic = lambda: CLOCK[0]
_time.time = lambda: CLOCK[0]
REC = []
class FakeOut:
    def __init__(s, n, i): s.name = n; s.i = i; s.closed = False
    def send(s, m): REC.append((CLOCK[0] - 1000.0, s.i, m))
    def close(s): pass
    def reset(s): pass
    def panic(s): pass
class FakeIn:
    name = "duality"; closed = False
    def poll(s): return None
    def iter_pending(s): return iter(())
    def close(s): pass
import duality as D
from rich.console import Console
D.console = Console(file=open("/dev/null", "w"))
names = ["Roland Sound Canvas VA", "SCVA2", "SCVA3", "SCVA4", "S-MU2000"]
idx = {n: i for i, n in enumerate(names)}
D.mido.open_output = lambda n, *a, **k: FakeOut(n, idx[n])
D.mido.open_input = lambda *a, **k: FakeIn()
fmts = [frozenset({"gm2", "gs8850"})] * 4 + [frozenset({"xg"})]
d = D.Duality("duality", names, anima=True, anima_game=True, show_status=False, out_formats=fmts,
              anima_seed=0x44A4, poly_limits=[64] * 5, crucible=True, crucible_gm_wide=True)
fb = []
_o = d._anima_feedback
d._anima_feedback = lambda k, t, status=False: (fb.append((round(CLOCK[0] - 1000, 2), k, t)), _o(k, t, status=status))
mf = common.load(common.midi("doom-game-223128.mid"))
ev = []; t = 0.0
for m in mf:
    t += m.time
    if not m.is_meta: ev.append((t, m))
CHECK = {60.0: None, 112.0: None}
i = 0; tt = 0.0
while tt < ev[-1][0] + 1:
    CLOCK[0] = 1000.0 + tt
    while i < len(ev) and ev[i][0] <= tt:
        d.process(ev[i][1]); i += 1
    d._anima_tick()
    d._check_anima_session_idle()
    for ck in CHECK:
        if CHECK[ck] is None and tt >= ck:
            CHECK[ck] = [dict(s) for s in d._anima_slots]
    tt = round(tt + 0.005, 3)

T = D.GS_EFX_TYPES
def tname(s): return T.get(tuple(s.get("typ") or ()), "-")
for ck, slots in CHECK.items():
    print(f"== slots at {ck:.0f}s")
    for p, s in enumerate(slots[:4]):
        print(f"  P{p + 1} {s.get('fam')!s:14} chs {[c + 1 for c in s.get('chs') or []]} {tname(s)}{' split' if s.get('split') else ''}")
for x in fb:
    if x[1] in ("efx", "game"):
        print("  ", x)

fails = []
# E1M1: each guitar on its own unit, no split, no seat for silent channels
s60 = CHECK[60.0][:4]
gt = {c: p for p, s in enumerate(s60) if s.get("fam") == "guitar_dist" for c in (s.get("chs") or [])}
if set(gt) != {0, 1} or gt[0] == gt[1]:
    fails.append(f"E1M1 guitars not on a unit each: {{ch: P}} = { {c + 1: p + 1 for c, p in gt.items()} }")
if any(s.get("split") for s in s60):
    fails.append("E1M1 uses an OD1/OD2 split")
live = {0, 1, 2}
for p, s in enumerate(s60):
    if s.get("fam") == "seat" and set(s.get("chs") or []) - live:
        fails.append(f"E1M1 P{p + 1} seat for channels the cue does not use: {[c + 1 for c in s['chs']]}")
# notes per unit: each guitar's notes on its own unit
def notes(lo, hi, ch):
    out = {}
    for tt_, p, m in REC:
        if lo <= tt_ < hi and m.type == "note_on" and m.velocity and m.channel == ch and p < 4:
            out[p + 1] = out.get(p + 1, 0) + 1
    return out
n1, n2 = notes(45, 80, 0), notes(45, 80, 1)
print("E1M1 guitar notes per unit: ch1", n1, "ch2", n2)
if set(n1) & set(n2):
    fails.append(f"E1M1 guitars share a unit: ch1 {n1} ch2 {n2}")
# the cue after the tally (PCs ch1-5 at 103.5 s, a strings drone that starts with its PC):
# the reroll places the cue's other parts at once (no seat Gate Reverb on every unit).
# The drone itself plays dry: its note arrived 2 ms after its PC, so it skipped the
# unit typed for it (notes are never delayed), and no unit is retyped under it.
s112 = CHECK[112.0][:4]
for c in (2, 3, 4):
    fam = [s.get("fam") for s in s112 if c in (s.get("chs") or [])]
    if not fam or all(f == "seat" for f in fam):
        fails.append(f"112 s: ch{c + 1} of the new cue is not placed (slots {fam})")
seats = [p + 1 for p, s in enumerate(s112) if s.get("fam") == "seat"]
if len(seats) > 1:
    fails.append(f"112 s: {len(seats)} seat units (P{seats}) while the cue has parts to place")
# rule 1: no type write under a sounding EFX player
held, on, viol = {}, {}, []
for tt_, p, m in REC:
    if p >= 4:
        continue
    if m.type == "sysex" and list(m.data[:4]) == [0x41, 0x10, 0x42, 0x12]:
        x = list(m.data)
        if x[4] == 0x40 and x[6] == 0x22 and (x[5] & 0xF0) == 0x40:
            part = D.Duality._gs_mid_to_part(x[5])
            if part is not None:
                on[(p, part)] = bool(x[7])
        elif x[4:7] == [0x40, 0x03, 0x00]:
            for (pp, c), v in on.items():
                if pp == p and v and held.get((pp, c)):
                    viol.append((round(tt_, 2), p + 1, c + 1))
    elif m.type == "control_change" and m.control in (120, 123):
        held.pop((p, m.channel), None)               # the game stops its music this way
    elif m.type == "note_on" and m.velocity:
        held.setdefault((p, m.channel), set()).add(m.note)
    elif m.type in ("note_on", "note_off"):
        held.get((p, m.channel), set()).discard(m.note)
if viol:
    fails.append(f"type write under a sounding player: {viol[:5]}")
print("FAILS:" if fails else "PASS")
for f in fails:
    print("  ", f)
sys.exit(1 if fails else 0)
