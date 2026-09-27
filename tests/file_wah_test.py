"""A file's own wah insert: play it only when the file set it and left it.

Built-in cases (always run), each a GS file that sets GTR Multi 3 on the file's
home unit with Part EFX On for a lead guitar (ch3):
  1. set and left (Wah Sw On, Control Source Off): adopted - C.Src1 = CC16 at
     +100%, Manual written ANIMA_FILE_WAH_REST below the file's, CC16 on ch3 to
     that unit, silence = the file's Manual; the file's Peak is never written
  2. same, but the file writes Wah Man at 12 s: handed back at once - Manual,
     C.Src1 and depth restored to the file's values, no CC16 after
  3. Wah Sw Off in the file: left alone
  4. the file routes C.Src1 itself: left alone
Songs (if present, tests/README.md): Phobos Anomaly (bulk-dump GTR Multi 3, set
and left) is adopted; Rose in the Gun Sight (performs its own wah) never is.
"""
import os
import sys
import time as _time
import common
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
LEAD = 2


def dt1(addr, val):
    s = (-(sum(addr) + sum(val))) & 0x7F
    return mido.Message("sysex", data=[0x41, 0x10, 0x42, 0x12, *addr, *val, s])


def run(events, end):
    REC.clear()
    CLOCK[0] = 1000.0
    d = D.Duality("in", [f"P{i+1}" for i in range(4)], anima=True, show_status=False,
                  out_formats=[frozenset({"gs"})] * 4, anima_seed=0x6BA1, poly_limits=[64] * 4)
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


def song(extra=(), wah_sw=1, csrc=0x00, man=74, peak=64):
    ev = [(0.0, dt1([0x40, 0x00, 0x7F], [0x00])),                 # GS reset
          (0.3, dt1([0x40, 0x03, 0x00], [0x04, 0x02])),           # GTR Multi 3
          (0.32, dt1([0x40, 0x03, 0x04], [man])),                 # Wah Man
          (0.34, dt1([0x40, 0x03, 0x05], [peak])),                # Wah Peak
          (0.36, dt1([0x40, 0x03, 0x06], [wah_sw])),              # Wah Sw
          (0.38, dt1([0x40, 0x03, 0x1B], [csrc])),                # C.Src1
          (0.40, dt1([0x40, 0x43, 0x22], [0x01])),                # Part EFX On, ch3
          (0.5, mido.Message("program_change", channel=LEAD, program=30)),
          (0.5, mido.Message("program_change", channel=1, program=33))]
    t = 1.5
    while t < 20.0:
        for k, n in enumerate([76, 79, 81, 83, 81, 79]):
            ev += [(t + k * 0.25, mido.Message("note_on", channel=LEAD, note=n, velocity=110)),
                   (t + k * 0.25 + 0.22, mido.Message("note_off", channel=LEAD, note=n, velocity=0))]
        ev += [(t + 1.5, mido.Message("note_on", channel=LEAD, note=88, velocity=120)),
               (t + 2.7, mido.Message("note_off", channel=LEAD, note=88, velocity=0))]
        ev += [(t, mido.Message("note_on", channel=1, note=40, velocity=100)),
               (t + 2.9, mido.Message("note_off", channel=1, note=40, velocity=0))]
        t += 3.0
    return ev + list(extra)


def writes(home, addr):
    return [(t, m.data[7]) for t, p, m in REC if p == home and m.type == "sysex"
            and list(m.data[:4]) == [0x41, 0x10, 0x42, 0x12] and list(m.data[4:7]) == [0x40, 0x03, addr]]


def cc16(home, after=0.0):
    return [(t, m.value) for t, p, m in REC if p == home and m.type == "control_change"
            and m.control == D.ANIMA_EFX_CTRL_CC and m.channel == LEAD and t > after]


# 1. set and left: adopted
d = run(song(), 24.0)
home = d._anima_file_home_port()
ours_man = [v for t, v in writes(home, 0x04) if t > 0.45]
if not d._anima_file_wah or not d._anima_file_wah.get("on"):
    fails.append("1: a set-and-left file wah was not adopted")
if ours_man[:1] != [74 - D.ANIMA_FILE_WAH_REST]:
    fails.append(f"1: Manual written {ours_man[:1]}, want {74 - D.ANIMA_FILE_WAH_REST}")
if [v for t, v in writes(home, 0x1B) if t > 0.45][:1] != [D.ANIMA_EFX_CTRL_CC]:
    fails.append("1: C.Src1 not set to CC16")
if [v for t, v in writes(home, 0x05) if t > 0.45]:
    fails.append("1: the file's Peak was overwritten")
c = cc16(home)
if len(c) < 50:
    fails.append(f"1: little CC16 on the lead ({len(c)})")
silent = [v for t, v in c if 22.5 < t]
if silent and abs(silent[-1] - D.ANIMA_FILE_WAH_REST) > 3:
    fails.append(f"1: after the lead stops CC16 {silent[-1]}, want the rest {D.ANIMA_FILE_WAH_REST} (= file's Manual)")
print(f"1 set and left: adopted, Manual {ours_man[:1]}, CC16 {len(c)} msgs")

# 2. the file writes Wah Man at 12 s: handed back
d = run(song(extra=[(12.0, dt1([0x40, 0x03, 0x04], [90]))]), 16.0)
home = d._anima_file_home_port()
back = [v for t, v in writes(home, 0x04) if 12.0 <= t < 12.1]
src = [v for t, v in writes(home, 0x1B) if 12.0 <= t < 12.1]
if d._anima_file_wah:
    fails.append("2: still adopted after the file wrote its own Wah Man")
if 74 not in back or 0 not in src:
    fails.append(f"2: not handed back (Manual {back}, C.Src1 {src})")
if cc16(home, after=12.2):
    fails.append("2: CC16 kept going after the hand-back")
print(f"2 file writes later: handed back, Manual {back}, C.Src1 {src}")

# 3. Wah Sw Off: left alone;  4. file routes C.Src1: left alone
for name, kw in (("3 wah switched off", {"wah_sw": 0}), ("4 file routes C.Src1", {"csrc": 0x01})):
    d = run(song(**kw), 8.0)
    home = d._anima_file_home_port()
    if d._anima_file_wah or cc16(home) or [v for t, v in writes(home, 0x1B) if t > 0.45]:
        fails.append(f"{name}: adopted anyway")
    print(f"{name}: left alone")

# Songs, if present
for fname, want in (("phobos-8850.mid", True), ("rose-gun-sight.mid", False)):
    path = next((os.path.join(f, n) for f in common.SEARCH for n in (fname, common.ORIGINAL[fname])
                 if os.path.exists(os.path.join(f, n))), None)
    if not path:
        print(f"{fname} not found: skipped")
        continue
    mf = common.load(path)
    ev, t = [], 0.0
    limit = 30.0 if want else 420.0
    for m in mf:
        t += m.time
        if not m.is_meta and t <= limit:
            ev.append((t, m))
    d = run(ev, limit)
    home = d._anima_file_home_port()
    got = bool(d._anima_file_wah) or bool(cc16(home) or [1 for _t, p, m in REC if p == home and m.type == "control_change"
                                                          and m.control == D.ANIMA_EFX_CTRL_CC])
    if got != want:
        fails.append(f"{fname}: adopted={got}, want {want}")
    print(f"{fname}: adopted={got} (want {want})")

if fails:
    print(f"FAILS ({len(fails)}):")
    for f in fails:
        print("   ", f)
    sys.exit(1)
print("PASS")
