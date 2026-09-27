"""EFX Control via CC16, per unit (no song file).

Three families on three GS units plus a seat unit written last (the case the
old single "last insert" driver got wrong): a drawbar organ on Rotary /
Rotary Multi, a clean guitar forced onto Auto Wah, strings. Checks:
  - each wah/rotary unit has Control Source = CC16 (40 03 1B/1D = 10) and
    +100% depth on the control that carries the knob (OM p.217-223), 0% on
    the other
  - the organ's unit gets a speed CC16 on the organ channel, which flips
    while a chord is held and flips back after it
  - the guitar's unit gets a wah that follows the playing: Manual set to the
    low base (CC16 adds to it) and GTR Multi 3's Peak raised; picks move it,
    held notes open it more than fast notes; after the guitar stops it falls
    back to the heel and goes quiet
  - a muted guitar forced onto GTR Multi 3 playing power chords is heard as
    rhythm: its Peak drops to ANIMA_WAH_PEAK_RHYTHM and the screamer stays off
  - one channel going from chords to a lead line opens up (Peak 127) within
    ANIMA_WAH_ROLE_LEAD_SEC-ish, and drops back to rhythm only after the chords
    have been back a while (one-sided glide)
  - no CC16 to units without a wah/rotary insert
"""
import sys
import collections
import time as _time
import common  # noqa: F401
import mido

CLOCK = [1000.0]
_time.monotonic = lambda: CLOCK[0]
_time.time = lambda: CLOCK[0]
REC = []

class FakeOut:
    def __init__(self, i): self.idx = i; self.name = f"P{i+1}"; self.closed = False
    def send(self, m): REC.append((CLOCK[0], self.idx, m))
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
# Force the clean guitar onto Auto Wah so the wah path is always exercised.
D.ANIMA_EFX_GS["guitar_clean"] = [(0x01, 0x21, "Auto Wah", 2)]
D.ANIMA_EFX_GS["guitar_mute"] = [(0x04, 0x02, "GTR Multi 3", 2)]

fails = []
d = D.Duality("in", [f"P{i+1}" for i in range(4)], anima=True, show_status=False,
              out_formats=[frozenset({"gs"})] * 4, anima_seed=0x6BA1, poly_limits=[64] * 4)
ev = []
def msg(t, m): ev.append((t, m))
ORGAN, GTR, STR, CHUG = 0, 2, 4, 6
for ch, prog in ((ORGAN, 16), (GTR, 27), (STR, 48), (CHUG, 28)):
    msg(0.0, mido.Message("program_change", channel=ch, program=prog))
    msg(0.01, mido.Message("control_change", channel=ch, control=7, value=100))
chord_t = []
t = 1.0
for k in range(4):                       # organ: short stabs, then a long held chord
    held = 2.0 if k == 2 else 0.3
    for n in (60, 64, 67):
        msg(t, mido.Message("note_on", channel=ORGAN, note=n, velocity=90))
        msg(t + held, mido.Message("note_off", channel=ORGAN, note=n, velocity=0))
    if held > 1:
        chord_t = [t, t + held]
    for n in (48, 55):
        msg(t, mido.Message("note_on", channel=STR, note=n, velocity=80))
        msg(t + 1.8, mido.Message("note_off", channel=STR, note=n, velocity=0))
    t += 2.5
gtr_end = t
for k in range(int((t - 1.0) / 0.25)):   # rhythm: power chords on 8ths
    tk = 1.0 + k * 0.25
    for n in (40, 47):
        msg(tk, mido.Message("note_on", channel=CHUG, note=n + (5 if (k // 8) % 2 else 0), velocity=105))
        msg(tk + 0.18, mido.Message("note_off", channel=CHUG, note=n + (5 if (k // 8) % 2 else 0), velocity=0))
held_t = []
k, tk = 0, 1.0
while tk < t:                            # guitar: fast 8ths, every 4th bar one long held note
    if k % 16 == 12:
        msg(tk, mido.Message("note_on", channel=GTR, note=76, velocity=100))
        msg(tk + 1.6, mido.Message("note_off", channel=GTR, note=76, velocity=0))
        held_t.append((tk + 0.9, tk + 1.6))
        tk += 2.0
    else:
        msg(tk, mido.Message("note_on", channel=GTR, note=64 + (k % 5), velocity=85))
        msg(tk + 0.2, mido.Message("note_off", channel=GTR, note=64 + (k % 5), velocity=0))
        tk += 0.25
    k += 1
end = t + 2.0
ev.sort(key=lambda e: e[0])
i, tt = 0, 0.0
while tt <= end:
    CLOCK[0] = 1000.0 + tt
    while i < len(ev) and ev[i][0] <= tt + 1e-9:
        d.process(ev[i][1]); i += 1
    d._anima_tick()
    d._check_anima_session_idle()
    tt = round(tt + 0.005, 3)

def port_of(ch):
    for p, sl in enumerate(d._anima_slots):
        if ch in (sl.get("chs") or []) and sl.get("fam") not in ("seat", None):
            return p, tuple(sl.get("typ") or ())
    return None, None
po, to = port_of(ORGAN)
pg, tg = port_of(GTR)
print(f"organ P{po+1 if po is not None else '?'} {to}, guitar P{pg+1 if pg is not None else '?'} {tg}, "
      f"slots {[ (s.get('fam'), s.get('typ')) for s in d._anima_slots]}")
if to not in D.ANIMA_EFX_ROTARY:
    fails.append(f"organ unit type {to} is not a rotary type")
if tg not in D.ANIMA_EFX_WAH:
    fails.append(f"guitar unit type {tg} is not a wah type")

def dt1(port):
    out = {}
    for _t, p, m in REC:
        if p == port and m.type == "sysex" and list(m.data[:4]) == [0x41, 0x10, 0x42, 0x12] \
                and list(m.data[4:6]) == [0x40, 0x03]:
            out[m.data[6]] = m.data[7]
    return out
for p, typ in ((po, to), (pg, tg)):
    if p is None:
        continue
    r = dt1(p)
    on2 = typ in D.ANIMA_EFX_CTRL2
    want = {0x1B: 0x10, 0x1D: 0x10, 0x1C: 0x40 if on2 else 0x7F, 0x1E: 0x7F if on2 else 0x40}
    got = {a: r.get(a) for a in want}
    if got != want:
        fails.append(f"P{p+1} {typ} control routing {got}, want {want}")

cc16 = collections.defaultdict(list)
for t0, p, m in REC:
    if m.type == "control_change" and m.control == D.ANIMA_EFX_CTRL_CC:
        cc16[p].append((t0 - 1000.0, m.channel, m.value))
pc, tc = port_of(CHUG)
for p in range(4):
    if p not in (po, pg, pc) and cc16.get(p):
        fails.append(f"CC16 sent to P{p+1}, which has no wah/rotary insert: {cc16[p][:3]}")
if po is not None:
    org = [(t0, v) for t0, c, v in cc16.get(po, []) if c == ORGAN]
    base = org[0][1] if org else None
    during = [v for t0, v in org if chord_t and chord_t[0] + 0.5 < t0 < chord_t[1]]
    after = [v for t0, v in org if chord_t and t0 >= chord_t[1] - 1e-6]
    if base is None:
        fails.append("organ unit never got a rotary speed CC16")
    elif not during or during[-1] == base:
        fails.append(f"rotary did not flip during the held chord (base {base}, during {during})")
    elif not after or after[-1] != base:
        fails.append(f"rotary did not return after the chord (after {after})")
    print(f"rotary CC16 on ch{ORGAN+1}: {[(round(t0, 2), v) for t0, v in org][:6]}")
if pg is not None:
    g = [(t0, v) for t0, c, v in cc16.get(pg, []) if c == GTR]
    vals = {v for t0, v in g if t0 < gtr_end}
    late = [t0 for t0, v in g if t0 > gtr_end + 1.5]
    if len(vals) < 10:
        fails.append(f"wah CC16 barely moved while the guitar played ({len(vals)} values)")
    if late:
        fails.append(f"wah CC16 kept running after the guitar stopped ({late[:3]})")
    if g and g[-1][1] > D.ANIMA_WAH_REST + 6:
        fails.append(f"wah did not fall back to the heel: last CC16 {g[-1][1]}")
    held = [v for t0, v in g if any(a <= t0 <= b for a, b in held_t)]
    fastv = [v for t0, v in g if t0 < gtr_end and not any(a - 0.9 <= t0 <= b + 0.3 for a, b in held_t)]
    if held and fastv and max(held) <= sum(fastv) / len(fastv) + 15:
        fails.append(f"held notes do not open the wah (held max {max(held)}, fast mean {sum(fastv)/len(fastv):.0f})")
    r = dt1(pg)
    man = D.ANIMA_EFX_WAH_MAN.get(tg)
    if man is not None and r.get(man) not in (D.ANIMA_WAH_MAN_BASE, D.ANIMA_WAH_MAN_SCREAM):
        fails.append(f"wah Manual {r.get(man)}, want the base {D.ANIMA_WAH_MAN_BASE}")
    pk = D.ANIMA_EFX_WAH_PEAK.get(tg)
    if pk and r.get(pk[0]) != pk[1]:
        fails.append(f"wah Peak {r.get(pk[0])}, want {pk[1]}")
    print(f"wah CC16 on ch{GTR+1}: {len(g)} messages, {len(vals)} distinct values, "
          f"held max {max(held) if held else '-'}, fast mean {sum(fastv)/len(fastv) if fastv else 0:.0f}")
pc, tc = port_of(CHUG)
if tc != (0x04, 0x02):
    fails.append(f"rhythm guitar unit type {tc}, want GTR Multi 3 (forced)")
else:
    r = dt1(pc)
    if r.get(0x05) != D.ANIMA_WAH_PEAK_RHYTHM:
        fails.append(f"rhythm GTR Multi 3 Peak {r.get(0x05)}, want {D.ANIMA_WAH_PEAK_RHYTHM}")
    if r.get(0x04) != D.ANIMA_WAH_MAN_BASE:
        fails.append(f"rhythm wah screamed: Manual {r.get(0x04)}")
    print(f"rhythm guitar P{pc+1} GTR Multi 3: Peak {r.get(0x05)}, Manual {r.get(0x04)}")
# --- one channel: chords -> lead line -> chords (fresh instance) ---------------------
REC.clear()
CLOCK[0] = 1000.0
D.ANIMA_EFX_GS["guitar_dist"] = [(0x04, 0x02, "GTR Multi 3", 2)]
d = D.Duality("in", [f"P{i+1}" for i in range(4)], anima=True, show_status=False,
              out_formats=[frozenset({"gs"})] * 4, anima_seed=0x6BA1, poly_limits=[64] * 4)
ev = [(0.0, mido.Message("program_change", channel=1, program=30)),
      (0.01, mido.Message("control_change", channel=1, control=10, value=64))]
t = 1.0
while t < 6.0:
    for n in (40, 47):
        ev += [(t, mido.Message("note_on", channel=1, note=n, velocity=105)),
               (t + 0.2, mido.Message("note_off", channel=1, note=n, velocity=0))]
    t += 0.25
lead_t = t
for n in [76, 79, 81, 83, 84, 83, 81, 79] * 2:
    ev += [(t, mido.Message("note_on", channel=1, note=n, velocity=110)),
           (t + 0.3, mido.Message("note_off", channel=1, note=n, velocity=0))]
    t += 0.33
chords_t = t
while t < chords_t + 4.0:
    for n in (40, 47):
        ev += [(t, mido.Message("note_on", channel=1, note=n, velocity=105)),
               (t + 0.2, mido.Message("note_off", channel=1, note=n, velocity=0))]
    t += 0.25
ev.sort(key=lambda e: e[0])
i, tt = 0, 0.0
while tt <= t + 1.0:
    CLOCK[0] = 1000.0 + tt
    while i < len(ev) and ev[i][0] <= tt + 1e-9:
        d.process(ev[i][1]); i += 1
    d._anima_tick()
    d._check_anima_session_idle()
    tt = round(tt + 0.005, 3)
ps = [q for q, sl in enumerate(d._anima_slots) if 1 in (sl.get("chs") or [])]
peaks = [(t0 - 1000.0, m.data[7]) for t0, p, m in REC if ps and p == ps[0] and m.type == "sysex"
         and list(m.data[4:7]) == [0x40, 0x03, 0x05] and t0 - 1000.0 > 0.5]
up = [t0 for t0, v in peaks if v == 127 and t0 >= lead_t]
down = [t0 for t0, v in peaks if v == D.ANIMA_WAH_PEAK_RHYTHM and t0 >= chords_t]
if not up or up[0] - lead_t > 0.6:
    fails.append(f"lead line did not open the wah quickly (Peak 127 at {up[:1]}, lead at {lead_t:.2f})")
if not down or down[0] - chords_t < 0.5:
    fails.append(f"back to chords: rhythm Peak at {down[:1]}, chords at {chords_t:.2f} (want a slower glide)")
print(f"switch: lead at {lead_t:.2f}s -> Peak 127 at {up[0] if up else '-'}; "
      f"chords at {chords_t:.2f}s -> Peak {D.ANIMA_WAH_PEAK_RHYTHM} at {down[0] if down else '-'}")
if fails:
    print(f"FAILS ({len(fails)}):")
    for f in fails:
        print("   ", f)
    sys.exit(1)
print("PASS")
