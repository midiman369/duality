"""Offline ONESTOP regression for Anima GS insert EFX (no MIDI hardware)."""
import sys, random, time as _time
import common  # repo on sys.path, MIDI paths
import mido

CLOCK = [1000.0]
_time.monotonic = lambda: CLOCK[0]
_time.time = lambda: CLOCK[0]

REC = []
FOLEY_PROG = {}  # (port, ch) -> last program sent  # (t, port, msg)

class FakeOut:
    def __init__(self, idx): self.idx = idx; self.name = f"P{idx+1}"; self.closed = False
    def send(self, msg): REC.append((CLOCK[0], self.idx, msg))
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
    i = len(_outs); _outs[name] = FakeOut(i); return _outs[name]
mido.open_output = open_output
mido.open_input = lambda *a, **k: FakeIn()
mido.get_output_names = lambda: [f"P{i+1}" for i in range(6)]
mido.get_input_names = lambda: ["in"]

import duality as D
D.mido.open_output = open_output
D.mido.open_input = lambda *a, **k: FakeIn()
names = [f"P{i+1}" for i in range(6)]
fmts = [frozenset({"gs"})] * 4 + [frozenset({"xg"}), frozenset({"mt32"})]
d = D.Duality("in", names, anima=True, show_status=False, out_formats=fmts,
              anima_seed=0x6BA1, poly_limits=[64] * 6)

def at(t): CLOCK[0] = 1000.0 + t
events = []  # (t, msg)
def ev(t, msg): events.append((t, msg))
def note(t, ch, n, dur, v=90):
    ev(t, mido.Message("note_on", channel=ch, note=n, velocity=v))
    ev(t + dur, mido.Message("note_off", channel=ch, note=n, velocity=0))

IN = common.midi("onestop-in-222922.mid")
_mf = mido.MidiFile(IN)
_t = 0.0
for _m in mido.merge_tracks(_mf.tracks):
    if _m.time:
        _t += mido.tick2second(_m.time, _mf.ticks_per_beat, 500000)
    if _m.is_meta:
        continue
    ev(_t, _m)
events.sort(key=lambda e: e[0])
_fb = d._anima_feedback
def _fb2(kind, text, status=False):
    if kind in ("efx", "efx-pan"):
        print(f"FB {CLOCK[0]-1000:8.2f} {text}")
    return _fb(kind, text, status=status)
d._anima_feedback = _fb2

# Wire truth, per port.
part_on = [[False] * 16 for _ in range(6)]
sounding = [[set() for _ in range(16)] for _ in range(6)]
fails = []
type_writes = []

def part_mid_to_ch(mid):
    if mid == 0x40: return 9
    if 0x41 <= mid <= 0x49: return mid - 0x41
    if 0x4A <= mid <= 0x4F: return mid - 0x4A + 10
    return None

GS_NAMES = getattr(D, "GS_EFX_TYPES", {})
last_type = {}
last_on = {}
hitches = []
seen = 0
def scan():
    global seen
    for t, p, m in REC[seen:]:
        if m.type == "sysex":
            dd = list(m.data)
            # 41 10 42 12 aa bb cc val...
            if len(dd) >= 8 and dd[:4] == [0x41, 0x10, 0x42, 0x12]:
                a = dd[4:7]; val = dd[7:-1]
                if a == [0x40, 0x03, 0x00] and len(val) >= 2:
                    typ = (val[0], val[1])
                    last_type[p] = t
                    type_writes.append((t - 1000, p, typ))
                    live = [c for c in range(16) if part_on[p][c] and sounding[p][c]]
                    if live:
                        fails.append(f"t={t-1000:.3f} P{p+1} type {typ[0]:02X} {typ[1]:02X} "
                                     f"({GS_NAMES.get(typ,'?')}) under sounding EFX players "
                                     f"{[c+1 for c in live]}")
                elif a[0] == 0x40 and a[2] == 0x22 and val:
                    c = part_mid_to_ch(a[1])
                    if c is not None:
                        if val[0] and not part_on[p][c]:
                            last_on[(p, c)] = t
                        part_on[p][c] = bool(val[0])
        elif m.type == "program_change":
            FOLEY_PROG[(p, m.channel)] = m.program

        elif m.type == "note_on" and m.velocity > 0:
            sounding[p][m.channel].add(m.note)
            # Foley (8850 SFX PC 121/122) joins its host's insert on purpose.
            if part_on[p][m.channel] and FOLEY_PROG.get((p, m.channel)) not in (120, 121):
                ref = max(last_type.get(p, -9), last_on.get((p, m.channel), -9))
                if t - ref < 0.1:
                    hitches.append(f"t={t-1000:.3f} P{p+1} ch{m.channel+1} note {t-ref:.3f}s after type/Part On")
        elif m.type in ("note_off", "note_on"):
            sounding[p][m.channel].discard(m.note)
    seen = len(REC)

owner_hist = [[] for _ in range(6)]
prev_slots = [dict() for _ in range(6)]
PRI = {f: i for i, f in enumerate(D.ANIMA_EFX_PRIORITY)}
down_bad = []
def snap():
    now = CLOCK[0]
    for p in range(4):
        sl = dict(d._anima_slots[p] or {})
        f = sl.get("fam")
        h = owner_hist[p]
        if not h or h[-1][1] != f:
            h.append((now - 1000, f))
            old = prev_slots[p]
            of = old.get("fam")
            same_owner = set(sl.get("chs") or []) <= set(old.get("chs") or [])
            if of and f and of != "file_park" and not same_owner and PRI.get(f, 99) > PRI.get(of, 99):
                heard = float(old.get("heard_t") or 0)
                if heard:
                    ok = now - heard >= D.ANIMA_EFX_IDLE_SEC
                else:
                    ok = now - float(old.get("t") or 0) >= float(old.get("grace") or D.ANIMA_EFX_DUMP_SEC)
                if not ok:
                    down_bad.append(f"t={now-1000:.2f} P{p+1} {of} → lower {f} before stale")
        prev_slots[p] = sl

pinned_dry = 0
first_note = {}
pinned_at = {}
i = 0
tt = 0.0
end = events[-1][0] + 1.0 if events else 0
while tt <= end:
    at(tt)
    while i < len(events) and events[i][0] <= tt + 1e-9:
        msg = events[i][1]
        if msg.type == "note_on" and msg.velocity > 0:
            c = msg.channel
            first_note.setdefault(c, tt)
            n0 = len(REC)
            d.process(msg)
            if d._anima_ch_port.get(c) is not None:
                pinned_at.setdefault(c, tt)
            scan()
            pin = d._anima_ch_port.get(c)
            for _t, p, m in REC[n0:]:
                if m.type == "note_on" and m.channel == c and m.velocity > 0 and p == pin:
                    if not part_on[p][c]:
                        pinned_dry += 1
                        if pinned_dry <= 5:
                            fails.append(f"t={tt:.3f} ch{c+1} pinned P{p+1} but Part EFX Off (dry)")
        else:
            d.process(msg)
        i += 1
    try:
        d._anima_tick()
    except Exception:
        pass
    d._check_anima_session_idle()
    scan()
    snap()
    tt = round(tt + 0.005, 3)

setup_writes = {}
for t, p, typ in type_writes:
    if t < 1.0:
        setup_writes[p] = setup_writes.get(p, 0) + 1
for p, n in setup_writes.items():
    if n > 1:
        fails.append(f"setup second: P{p+1} got {n} type writes")

flips = []
for p in range(4):
    h = owner_hist[p]
    for a in range(len(h) - 2):
        if (h[a][1] and h[a+1][1] and h[a][1] == h[a + 2][1]
                and PRI.get(h[a][1], 99) > PRI.get(h[a+1][1], 99)
                and h[a + 2][0] - h[a][0] < D.ANIMA_EFX_IDLE_SEC):
            flips.append(f"P{p+1} {h[a][1]}→{h[a+1][1]}→{h[a+2][1]} within {h[a+2][0]-h[a][0]:.1f}s")
fails += flips
fails += down_bad
last_w = {}
for t, p, typ in type_writes:
    if t >= 1.0 and p in last_w and t - last_w[p] < D.ANIMA_EFX_SWITCH_SEC:
        fails.append(f"P{p+1} two type writes {t - last_w[p]:.3f}s apart at {t:.2f}")
    last_w[p] = t
fails += hitches[:10]
for c in ():   # (real replay: reported, not asserted) must get a box soon after they play
    fn_ = first_note.get(c)
    pa = pinned_at.get(c)
    if fn_ is None:
        continue
    if pa is None or pa - fn_ > 4.0:
        fails.append(f"ch{c+1} ({D.Duality._anima_efx_family(d, c)}) first note {fn_:.2f}s, box at {pa}")
print("pin latency:", {c + 1: (round(first_note[c], 2), pinned_at.get(c)) for c in sorted(first_note)})

print("VERSION", D.VERSION)
print("hitch-candidates:", len(hitches))
print("type writes:")
for t, p, typ in type_writes:
    print(f"  {t:7.3f} P{p+1} {typ[0]:02X} {typ[1]:02X} {GS_NAMES.get(typ, '?')}")
print("owners:")
for p in range(4):
    print(f"  P{p+1}: " + " | ".join(f"{t:.2f} {f}" for t, f in owner_hist[p]))
print("final pins:", {c + 1: p + 1 for c, p in sorted(d._anima_ch_port.items())})
print("pinned-dry note-ons:", pinned_dry)
print("FAILS:" if fails else "PASS")
for f in fails[:40]:
    print("  ", f)


# ---- wire checks for 0.19.006
import collections
from tables_gs import GS_EFX_TYPES as T
ports = collections.defaultdict(list)
for t, p, m in REC:
    ports[p].append((t - 1000, m))
print("== CC1 still raised on a unit at a program change:")
bad = 0
for p in range(4):
    cc1 = [0] * 16
    for t, m in ports[p]:
        if m.type == "control_change" and m.control == 1:
            cc1[m.channel] = m.value
        if m.type == "program_change" and cc1[m.channel] > 0:
            bad += 1
            print(f"   P{p+1} {t:7.2f} ch{m.channel+1} PC{m.program+1} CC1={cc1[m.channel]}")
print("   count", bad)
hi = [(round(t,2), p+1, m.channel+1, m.note) for p in range(4) for t, m in ports[p]
      if m.type == "note_on" and m.velocity and m.note > 96]
print("== note-ons above 96:", len(hi), hi[:10])
for p in range(4):
    for t, m in ports[p]:
        if m.type == "sysex":
            d = list(m.data)
            if d[4:7] == [0x40, 0x03, 0x00] and T.get((d[7], d[8]), "").lower().find("delay") >= 0:
                print(f"   delay type P{p+1} {t:7.2f} {T.get((d[7],d[8]))}")

sys.exit(1 if fails else 0)
