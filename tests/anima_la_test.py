"""Anima on LA outs (0.19.061), no song.

  1. CM-64 pool under Voodoo, Anima on: a piano on a PCM part goes through the normal note path,
     so it counts in Duality's display (active notes, the unit's voice count) and in Anima: a
     quick repeat of the same note at the same velocity reaches the part humanized
  2. Anima's expression swell (CC11) on a held PCM string chord reaches the part's channel
  3. a PCM nylon guitar chord is strummed: its notes reach the part spread out, not at once
  4. one CM-64 on seats: a seat's notes count in the display too
  5. the status panel shows [Voodoo] and [CM-64 LA+PCM] with CM-64 PCM parts, [MT-32] without
  6. native MT-32 stream: MT-32 organs (PC 9-16) are not taken for mallets (no unroll, no
     sticking); MT-32 Marimba (PC 105) and Harp (PC 58) are; GM equivalents from MT32_TO_GM
  7. native CM-64 stream: a PCM part on ch11 with PC 24 (FINGERED 1) is a bass for Anima, not
     the LA patch 24 (Celesta 2); the LA part on ch2 with the same PC stays a celesta
  8. mixed rig (two SC-8850s + a CM-64), 0.19.063: under Voodoo, and with a native MT-32 stream
     routed to the CM-64 only, Anima plans nothing on the idle GS units (no inserts, seats or
     GS SysEx, no EFX messages); a GS stream on the same rig still gets its inserts
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


def fresh(specs, fmt="gm", voodoo=True):
    REC.clear()
    CLOCK[0] = 1000.0
    tags = [D.parse_out_spec(f"P{i+1}:{s}")[1] for i, s in enumerate(specs)]
    d = D.Duality("in", [f"P{i+1}" for i in range(len(specs))], show_status=False, out_formats=tags,
                  crucible=True, input_format=fmt, poly_limits=[32] * len(specs), anima=True, anima_seed=0x2222)
    if voodoo:
        d._voodoo_begin("test")
        while d.voodoo_loading:
            CLOCK[0] += 0.5
            d._voodoo_tick()
    REC.clear()
    return d


def step(d, secs, dt=0.001):
    end = CLOCK[0] + secs
    while CLOCK[0] < end:
        CLOCK[0] += dt
        d._anima_tick()
        d._anima_strum_drain()


def send(d, m):
    d.process(m)
    step(d, 0.002)


def on(d, ch, n, v=100):
    send(d, mido.Message("note_on", channel=ch, note=n, velocity=v))


def off(d, ch, n):
    send(d, mido.Message("note_off", channel=ch, note=n, velocity=0))


def pc(d, ch, p):
    send(d, mido.Message("program_change", channel=ch, program=p))


def at(port, ch, kind="note_on"):
    return [(t, m) for t, p, m in REC if p == port and m.type == kind and m.channel == ch
            and (kind != "note_on" or m.velocity > 0)]


# 1. PCM piano in the display and humanized
d = fresh(["cm64", "cm64", "cm64"])
pc(d, 0, 0)
part = d._cm64v_owned(0)
if part is None:
    fails.append("1: the piano claimed no PCM part")
else:
    on(d, 0, 60, 90)
    if (0, 60) not in d.active or d.voice_counts[part["port"]] < 2:
        fails.append(f"1: PCM note not in the display (active {sorted(d.active)}, voices {d.voice_counts})")
    if at(part["port"], 0) or not at(part["port"], part["rx"]):
        fails.append("1: the note did not go to the PCM part only")
    off(d, 0, 60)
    vels = []
    for k in range(4):
        REC.clear()
        on(d, 0, 62, 90)
        vels += [m.velocity for _t, m in at(part["port"], part["rx"])]
        step(d, 0.04)
        off(d, 0, 62)
        step(d, 0.04)                                   # repeats 0.08 s apart (window 0.11 s)
    if not vels or all(v == 90 for v in vels):
        fails.append(f"1: repeats on the PCM part were not humanized: {vels}")
    if d._cm64v_active or any(k[0] == 0 for k in d.active):
        fails.append("1: notes left hanging after the note-offs")

# 2. expression swell reaches the PCM strings
pc(d, 1, 48)
sp = d._cm64v_owned(1)
REC.clear()
for n in (55, 59, 62):
    on(d, 1, n, 80)
step(d, 3.0, dt=0.01)
if sp is None or not at(sp["port"], sp["rx"], "control_change"):
    fails.append("2: no Anima CC on the PCM strings' channel")
elif not [m for _t, m in at(sp["port"], sp["rx"], "control_change") if m.control in (1, 11)]:
    fails.append("2: no CC1 / CC11 swell on the PCM strings")
for n in (55, 59, 62):
    off(d, 1, n)

# 3. strummed PCM nylon guitar
pc(d, 2, 24)
gp = d._cm64v_owned(2)
REC.clear()
for n in (52, 55, 59, 64):
    d.process(mido.Message("note_on", channel=2, note=n, velocity=96))
step(d, 0.4)
times = sorted(t for t, _m in at(gp["port"], gp["rx"])) if gp else []
if len(times) != 4 or times[-1] - times[0] < 0.008:
    fails.append(f"3: guitar chord on the PCM part not strummed: {times}")
for n in (52, 55, 59, 64):
    off(d, 2, n)

# 5. badge
from rich.console import Console


def panel_text(dd):
    import io
    c = Console(record=True, width=220, file=io.StringIO())
    c.print(dd._make_status_panel())
    return c.export_text()


txt = panel_text(d)
if "[Voodoo]" not in txt or "[CM-64 LA+PCM]" not in txt:
    fails.append("5: CM-64 Voodoo badges missing")
d._voodoo_exit("test")

# 4. seats
d = fresh(["cm64"])
pc(d, 8, 0)
on(d, 8, 60, 90)
seat = d._cm64v_owned(8)
if seat is None or (8, 60) not in d.active or d.voice_counts[0] < 1:
    fails.append(f"4: seat note not in the display (seat {seat and seat['rx']}, voices {d.voice_counts})")
off(d, 8, 60)
d._voodoo_exit("test")
d = fresh(["mt32", "mt32"], fmt="mt32", voodoo=False)
d.detected_format = "MT-32"
if "[CM-64 LA+PCM]" in panel_text(d) or "[MT-32]" not in panel_text(d):
    fails.append("5: plain MT-32 session lost its [MT-32] badge")

# 6. native MT-32 programs
for p_ in range(8, 16):
    pc(d, 1, p_)
    if d._anima_roll_mode(1) is not None or d._anima_gm_pc(1) in D.ANIMA_MALLET_PCS:
        fails.append(f"6: MT-32 PC {p_ + 1} ({d._anima_gm_pc(1)}) treated as a mallet / unrolled")
for p_, nm in ((104, "Marimba"), (57, "Harp 1")):
    pc(d, 2, p_)
    if d._anima_roll_mode(2) != "unroll":
        fails.append(f"6: MT-32 {nm} (PC {p_ + 1}) not unrolled")
pc(d, 2, 104)
if d._anima_gm_pc(2) not in D.ANIMA_MALLET_PCS:
    fails.append("6: MT-32 Marimba not in the mallet set")

# 7. native CM-64 PCM channel
d = fresh(["cm64"], fmt="mt32", voodoo=False)
d.detected_format = "MT-32"
pc(d, 10, 23)
pc(d, 1, 23)
if d._anima_category(10) != "bass":
    fails.append(f"7: PCM ch11 PC 24 is '{d._anima_category(10)}', want bass")
if d._anima_category(1) == "bass":
    fails.append("7: LA ch2 PC 24 (Celesta 2) taken for a bass")

# 8. mixed rig: idle GS units get no Anima EFX
def mixed(fmt, voodoo):
    REC.clear()
    CLOCK[0] = 1000.0
    tags = [D.parse_out_spec(f"P{i+1}:{s}")[1] for i, s in enumerate(["8850", "8850", "cm64"])]
    dd = D.Duality("in", ["P1", "P2", "P3"], show_status=False, out_formats=tags, crucible=True,
                   input_format=fmt, poly_limits=[32] * 3, anima=True, anima_seed=0x2222)
    msgs = []
    _fb = dd._anima_feedback
    dd._anima_feedback = lambda kind, text, status=False: (msgs.append(kind), _fb(kind, text, status=status))[1]
    if voodoo:
        dd.format_locked = True
        dd._voodoo_begin("test")
        while dd.voodoo_loading:
            CLOCK[0] += 0.5
            dd._voodoo_tick()
    REC.clear()
    for c, p_ in ((0, 0), (1, 48), (2, 29), (3, 61), (4, 89), (5, 24)):
        pc(dd, c, p_)
    for k in range(8):
        for c in range(6):
            on(dd, c, 52 + c * 3 + k % 3, 96)
        step(dd, 0.25, dt=0.01)
        for c in range(6):
            off(dd, c, 52 + c * 3 + k % 3)
    gs_sx = [m for _t, p_, m in REC if p_ in (0, 1) and m.type == "sysex" and m.data[0] == 0x41 and m.data[2] == 0x42]
    return dd, gs_sx, msgs


for fmt, voodoo, label in (("gm", True, "Voodoo"), ("mt32", False, "native MT-32")):
    dd, gs_sx, msgs = mixed(fmt, voodoo)
    if dd._anima_gs_ports() or gs_sx or "efx" in msgs:
        fails.append(f"8: {label}: GS units {dd._anima_gs_ports()}, {len(gs_sx)} GS SysEx, efx messages {msgs.count('efx')}")
    if voodoo:
        dd._voodoo_exit("test")
dd, gs_sx, msgs = mixed("gs", False)
if dd._anima_gs_ports() != [0, 1] or not gs_sx:
    fails.append(f"8: a GS stream lost its inserts (GS units {dd._anima_gs_ports()}, {len(gs_sx)} GS SysEx)")

if fails:
    print("FAILS")
    for f in fails:
        print("   " + f)
    sys.exit(1)
print("PASS")
