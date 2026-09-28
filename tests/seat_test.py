"""Seat units: harmony ghosts on a spare GS unit with mirrored pan.

Built-in tune (always): four GS units, three families (flute ch1 pan 30,
horn ch6 pan 64, strings ch12 pan 96), so one unit is spare. Checks:
  - every harmony ghost plays on the spare unit, none on the heroes' units
  - on the spare, each harmonised channel's CC10 is the mirror of its file
    pan (centred: ANIMA_SEAT_CENTRE_SPREAD to a side) within ANIMA_SEAT_JITTER
  - a file pan move later in the song is mirrored on the spare too
  - no real (file) note of a seated channel plays on the spare
  - panic() gives the spare unit the file's pans back
  - a seat's Space D gets Balance D>50E (40 03 12 = 0x20); a family's does not
  - the spare gets the gentle "seat" insert with the harmony channels wired
    in; when a guitar arrives mid-song it takes the unit over, never with a
    type write while seat harmony is sounding there, and harmony then goes
    back to the heroes' units
LotR medley (if present, tests/README.md): five GS units, two spares, each
family's harmony keeps to one spare and families are shared out.
"""
import os
import sys
import collections
import time as _time
import common
import mido

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

def open_output(name, *a, **k):
    return FakeOut(int(name[1:]) - 1)

import duality as D
D.mido.open_output = open_output
D.mido.open_input = lambda *a, **k: FakeIn()
fails = []
JIT = int(round(127 * D.ANIMA_SEAT_JITTER))

def make(n):
    REC.clear()
    return D.Duality("in", [f"P{i+1}" for i in range(n)], anima=True, show_status=False,
                     out_formats=[frozenset({"gs"})] * n, anima_seed=0x6BA1, poly_limits=[64] * n)

def play(d, events, end):
    ghosts = []
    log = []
    og = d._anima_ghost_log
    d._anima_ghost_log = lambda text: (log.append(text), og(text))
    events.sort(key=lambda e: e[0])
    i, tt = 0, 0.0
    real = []
    while tt <= end:
        CLOCK[0] = 1000.0 + tt
        while i < len(events) and events[i][0] <= tt + 1e-9:
            m = events[i][1]; i += 1
            n0 = len(REC)
            d.process(m)
            if m.type == "note_on" and m.velocity:
                for _t, p, x in REC[n0:]:
                    if x.type == "note_on" and x.velocity and x.channel == m.channel:
                        (real if x.note == m.note else ghosts).append((tt, p, x.channel, x.note))
        d._anima_tick()
        d._check_anima_session_idle()
        tt = round(tt + 0.005, 3)
    return real, ghosts, log

def want(d, ch, file_pan):
    if abs(file_pan - 64) <= D.ANIMA_SEAT_CENTRE:
        return None
    return 128 - file_pan

def last_pan(port, ch):
    v = None
    for _t, p, m in REC:
        if p == port and m.type == "control_change" and m.control == 10 and m.channel == ch:
            v = m.value
    return v

# --- built-in tune -----------------------------------------------------------
d = make(4)
ev = []
def cc(t, ch, c, v): ev.append((t, mido.Message("control_change", channel=ch, control=c, value=v)))
def pc(t, ch, p): ev.append((t, mido.Message("program_change", channel=ch, program=p)))
def note(t, ch, n, dur, v=90):
    ev.append((t, mido.Message("note_on", channel=ch, note=n, velocity=v)))
    ev.append((t + dur, mido.Message("note_off", channel=ch, note=n, velocity=0)))
for ch, prog, pan in ((0, 73, 30), (5, 60, 64), (11, 48, 96)):
    pc(0.0, ch, prog); cc(0.01, ch, 7, 100); cc(0.01, ch, 10, pan)
t = 1.0
tune = [72, 74, 76, 77, 79, 77, 76, 74]
for bar in range(8):
    root = (60, 65, 67, 60)[bar % 4]
    for n in (root - 12, root - 5, root - 8 + 12):
        note(t, 11, n, 1.9, 80)              # strings chord, held
    note(t, 5, root - 5, 1.9, 85)            # horn, held
    for k, n in enumerate(tune):
        note(t + k * 0.25, 0, n, 0.22, 95)  # flute line
    t += 2.0
move_t = t
cc(move_t, 0, 10, 20)                        # flute pans further left
for k, n in enumerate(tune):
    for q in (60, 64, 67):
        note(move_t + 0.1, 11, q, 1.9, 80)
    note(move_t + 0.1 + k * 0.25, 0, n, 0.22, 95)
end = move_t + 3.0
real, ghosts, log = play(d, ev, end)
seats = sorted({p for p, c in d._anima_seat_pan})
if seats != [3]:
    fails.append(f"seat units {[s + 1 for s in seats]}, want [P4]")
gports = collections.Counter(p for _t, p, c, n in ghosts)
if not ghosts:
    fails.append("no harmony ghosts in the built-in tune")
elif set(gports) != {3}:
    fails.append(f"harmony ghosts on {dict((f'P{p+1}', n) for p, n in gports.items())}, want only P4")
if any(p == 3 for _t, p, c, n in real):
    fails.append("a file note played on the seat unit")
for ch in sorted({c for p, c in d._anima_seat_pan}):
    fp = int(d.pan[ch])
    got = last_pan(3, ch)
    w = want(d, ch, fp)
    if w is None:
        ok = got is not None and abs(abs(got - 64) - D.ANIMA_SEAT_CENTRE_SPREAD) <= JIT
    else:
        ok = got is not None and abs(got - w) <= JIT
    if not ok:
        fails.append(f"ch{ch+1} file pan {fp}: seat pan {got}, want {w if w is not None else 'a side'} ±{JIT}")
if (3, 0) in d._anima_seat_pan and abs(last_pan(3, 0) - (128 - 20)) > JIT:
    fails.append(f"flute pan move not mirrored: {last_pan(3, 0)}")
sl4 = d._anima_slots[3]
if sl4.get("fam") != "seat" or not sl4.get("typ"):
    fails.append(f"P4 slot {sl4.get('fam')} {sl4.get('typ')}, want a seat insert")
elif not all(d._anima_efx_on[3][c] for c in (0, 5, 11)):
    fails.append("seat insert: harmony channels not wired (Part EFX) on P4")

def dt1_to(port, n0):
    return [(list(m.data[4:7]), list(m.data[7:-1])) for _t, p, m in REC[n0:]
            if p == port and m.type == "sysex" and list(m.data[:4]) == [0x41, 0x10, 0x42, 0x12]]
n0 = len(REC)
d._anima_efx_shape(3, (0x01, 0x43), [0, 5, 11], "seat")
if ([0x40, 0x03, 0x12], [0x20]) not in dt1_to(3, n0):
    fails.append(f"seat Space D: no Balance D>50E write, got {dt1_to(3, n0)}")
n0 = len(REC)
d._anima_efx_shape(3, (0x01, 0x43), [0], "strings")
if any(a == [0x40, 0x03, 0x12] for a, v in dt1_to(3, n0)):
    fails.append("a family's Space D got the seat Balance")
typ4 = tuple(d._anima_slots[3].get("typ") or ())
if typ4 in D.ANIMA_SEAT_BALANCE:
    sent = [v for _t, p, m in REC if p == 3 and m.type == "sysex"
            for v in [list(m.data[4:8])] if v[:3] == [0x40, 0x03, 0x12]]
    if [0x40, 0x03, 0x12, 0x20] not in sent:
        fails.append("seat insert Space D committed without its Balance")

# A guitar arrives: the seat must hand P4 over, quietly.
t0 = end + 0.5
pc_t = t0 + 2.02                 # while seat harmony is sounding
ev2 = [(pc_t, mido.Message("program_change", channel=2, program=25)),
       (pc_t + 0.01, mido.Message("control_change", channel=2, control=10, value=64))]
for k in range(40):
    tk = t0 + 0.5 + k * 0.25
    if tk >= pc_t + 0.4:
        for n in (52, 59, 64):
            ev2.append((tk, mido.Message("note_on", channel=2, note=n, velocity=80)))
            ev2.append((tk + 0.2, mido.Message("note_off", channel=2, note=n, velocity=0)))
    if k < 30:
        ev2.append((tk, mido.Message("note_on", channel=0, note=tune[k % 8], velocity=95)))
        ev2.append((tk + 0.22, mido.Message("note_off", channel=0, note=tune[k % 8], velocity=0)))
        if k % 8 == 0:
            for q in (48, 55, 64):
                ev2.append((tk, mido.Message("note_on", channel=11, note=q, velocity=80)))
                ev2.append((tk + 1.9, mido.Message("note_off", channel=11, note=q, velocity=0)))
n0 = len(REC)
ev2.sort(key=lambda e: e[0])
i, tt = 0, end
sound4 = collections.Counter()
late_flute = set()
bad_type = []
handover_t = None
while tt <= t0 + 12.0:
    CLOCK[0] = 1000.0 + tt
    while i < len(ev2) and ev2[i][0] <= tt + 1e-9:
        d.process(ev2[i][1]); i += 1
    d._anima_tick()
    d._check_anima_session_idle()
    for _t, p, m in REC[n0:]:
        if p != 3:
            continue
        if m.type == "note_on" and m.velocity:
            sound4[(m.channel, m.note)] += 1
        elif m.type in ("note_on", "note_off"):
            sound4[(m.channel, m.note)] = 0
        elif m.type == "sysex" and list(m.data[4:7]) == [0x40, 0x03, 0x00]:
            live = [k for k, v in sound4.items() if v > 0 and d._anima_efx_on[3][k[0]]]
            if live:
                bad_type.append(f"t={tt:.2f} P4 type write under sounding {live}")
    n0 = len(REC)
    if handover_t is None and d._anima_slots[3].get("fam") not in ("seat", None):
        handover_t = tt
    if handover_t is not None and tt > handover_t + 0.5:
        for _t, p, m in REC[-50:]:
            if p == 3 and _t >= 1000.0 + handover_t + 0.5 and m.type == "note_on" and m.velocity \
                    and m.channel == 0:
                late_flute.add(round(_t - 1000.0, 2))
    tt = round(tt + 0.005, 3)
fails += bad_type[:5]
if handover_t is None:
    fails.append(f"guitar never took P4 over (P4 {d._anima_slots[3].get('fam')})")
else:
    print(f"handover: P4 → {d._anima_slots[3].get('fam')} {handover_t - pc_t:.2f}s after the guitar's PC")
    if late_flute:
        fails.append(f"flute harmony still on P4 after the handover at {sorted(late_flute)[:4]}")
d.panic()
for (p, ch) in [(3, 0), (3, 5), (3, 11)]:
    lp = last_pan(p, ch)
    if lp is not None and lp != int(d.pan[ch]):
        fails.append(f"after panic P{p+1} ch{ch+1} pan {lp}, file {d.pan[ch]}")
print(f"built-in: {len(ghosts)} harmony ghosts {dict((f'P{p+1}', n) for p, n in gports.items())}")

# --- LotR, five units ----------------------------------------------------------
path = None
for folder in common.SEARCH:
    cand = os.path.join(folder, "LotR_8850.mid")
    if os.path.exists(cand):
        path = cand
if path:
    d = make(5)
    mf = common.load(path)
    ev, t = [], 0.0
    for m in mf:
        t += m.time
        if not m.is_meta and t <= 90.0:
            ev.append((t, m))
    real, ghosts, log = play(d, ev, 90.0)
    fam_ports = collections.defaultdict(set)
    for _t, p, c, n in ghosts:
        fam_ports[d._anima_efx_family(c) or d._anima_category(c)].add(p)
    split = {f: sorted(p + 1 for p in ps) for f, ps in fam_ports.items()}
    print(f"LotR x5: {len(ghosts)} ghosts, family -> seat {split}")
    for f, ps in fam_ports.items():
        if len(ps) != 1 or not ps <= {3, 4}:
            fails.append(f"LotR family {f} ghosts on {sorted(p + 1 for p in ps)}, want one spare")
    if len({p for ps in fam_ports.values() for p in ps}) < 2:
        fails.append("LotR: families not shared out over both spares")
else:
    print("LotR_8850.mid not found: five-unit check skipped")

if fails:
    print(f"FAILS ({len(fails)}):")
    for f in fails[:20]:
        print("   ", f)
    sys.exit(1)
print("PASS")
