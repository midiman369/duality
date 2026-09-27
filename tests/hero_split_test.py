"""Hero split: a featured line whose family shares one unit gets a spare unit with another type.

Built-in (no song), three GS units, marimba chords (ch1) + vibraphone tune (ch2), both
chromatic, so they share one unit and two are spare:
  1. the vibes line moves to a spare unit with a different type of the family, in a breath:
     no ch2 note within 100 ms after its Part EFX On there, Part Off on the old unit at the
     same moment, no insert type write on a unit while one of its players sounds
  2. the same song with strings (ch4, a harmony part): no split (seat units keep the spares)
  3. two units and a clean guitar (ch5) arriving later: the guitar takes the hero's unit
     once it is quiet, and the vibes play on the family's unit again (Part EFX On there)
"""
import sys
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
D.mido.open_output = lambda n, *a, **k: FakeOut(int(n[1:]) - 1)
D.mido.open_input = lambda *a, **k: FakeIn()
fails = []
MAR, VIB, STR, GTR = 0, 1, 3, 4


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


def on(t, ch, n, dur, vel=96):
    return [(t, mido.Message("note_on", channel=ch, note=n, velocity=vel)),
            (t + dur, mido.Message("note_off", channel=ch, note=n, velocity=0))]


def song(strings=False, guitar_at=None, end=30.0):
    ev = [(0.1, mido.Message("program_change", channel=MAR, program=12)),
          (0.1, mido.Message("program_change", channel=VIB, program=11))]
    if strings:
        ev.append((0.1, mido.Message("program_change", channel=STR, program=48)))
    t = 1.0
    tune = [72, 74, 76, 79, 77, 76, 74, 72]
    while t < end - 2:
        for k in range(4):                       # marimba chords on the beats
            for n in (60, 64, 67):
                ev += on(t + k * 0.5, MAR, n, 0.3, 80)
        k = int(t) % len(tune)                   # vibes: a slow tune, a breath each 2 s
        for j in range(3):
            ev += on(t + j * 0.5, VIB, tune[(k + j) % len(tune)], 0.45)
        if strings:
            ev += on(t, STR, 55, 1.9, 70)
        t += 2.0
    if guitar_at is not None:
        ev.append((guitar_at, mido.Message("program_change", channel=GTR, program=27)))
        g = guitar_at + 0.5
        while g < end - 2:
            ev += on(g, GTR, 64, 0.2, 90)
            g += 0.5
    return ev


def part_toggles(ch):
    """(t, port, on) for Part EFX writes of ch (40 4x 22)."""
    out = []
    for t, p, m in REC:
        if m.type == "sysex" and list(m.data[:4]) == [0x41, 0x10, 0x42, 0x12] and m.data[4] == 0x40 \
                and m.data[6] == 0x22 and m.data[5] == D.Duality._gs_efx_part_mid(ch):
            out.append((t, p, m.data[7]))
    return out


def type_writes():
    return [(t, p, tuple(m.data[7:9])) for t, p, m in REC if m.type == "sysex"
            and list(m.data[:7]) == [0x41, 0x10, 0x42, 0x12, 0x40, 0x03, 0x00]]


# 1. split
d = run(song(), 30.0, 3)
home = {c: d._anima_ch_port.get(c) for c in (MAR, VIB)}
if home[VIB] is None or home[VIB] == home[MAR]:
    fails.append(f"1: vibes not split (ports {home})")
else:
    tv = tuple(d._anima_slots[home[VIB]].get("typ") or ())
    tm = tuple(d._anima_slots[home[MAR]].get("typ") or ())
    if tv == tm:
        fails.append(f"1: hero unit has the family's type {tv}")
    moves = [(t, p) for t, p, v in part_toggles(VIB) if p == home[VIB] and v == 1]
    offs = [(t, p) for t, p, v in part_toggles(VIB) if p == home[MAR] and v == 0]
    if not moves:
        fails.append("1: no Part EFX On for the vibes on its new unit")
    else:
        tmove = moves[0][0]
        if not any(abs(t - tmove) < 0.001 for t, _p in offs):
            fails.append("1: Part EFX Off on the old unit did not come with the move")
        near = [t for t, p, m in REC if m.type == "note_on" and m.velocity and m.channel == VIB
                and 0 <= t - tmove < 0.100]
        if near:
            fails.append(f"1: a vibes note {near[0] - tmove:.3f}s after the move (hitch)")
        print(f"1 split: vibes P{home[VIB]+1} {D.GS_EFX_TYPES.get(tv)} vs family P{home[MAR]+1} "
              f"{D.GS_EFX_TYPES.get(tm)}, moved at {tmove:.2f}s")
# no type write under a sounding player (Part On there and a note held on that unit)
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
            fails.append(f"1: type {typ} written on P{p+1} at {tw:.2f}s while ch{c+1} sounds there")

# 2. harmony present: no split
d = run(song(strings=True), 20.0, 3)
if d._anima_ch_port.get(VIB) != d._anima_ch_port.get(MAR) or any(s.get("hero") for s in d._anima_slots):
    fails.append("2: split although a harmony part wants the spare units")
print("2 with strings: no split" if "2:" not in " ".join(fails) else "2 with strings: SPLIT")

# 3. a guitar arriving later takes the hero unit back
d = run(song(guitar_at=16.0, end=34.0), 34.0, 2)
gp, vp, mp = (d._anima_ch_port.get(c) for c in (GTR, VIB, MAR))
if gp is None or gp == mp:
    fails.append(f"3: the guitar did not get a unit (ports gtr {gp}, marimba {mp})")
if vp != mp:
    fails.append(f"3: vibes still apart (P{vp and vp+1}) after the guitar took the unit")
elif not d._anima_efx_on[mp][VIB]:
    fails.append("3: vibes back on the family unit without Part EFX On")
print(f"3 guitar later: guitar P{None if gp is None else gp+1}, vibes P{None if vp is None else vp+1}, marimba P{None if mp is None else mp+1}")

if fails:
    print(f"FAILS ({len(fails)}):")
    for f in fails:
        print("   ", f)
    sys.exit(1)
print("PASS")
