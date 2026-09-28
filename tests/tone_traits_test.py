"""Tone Palettes EFX level and notes (tables_8850 ANIMA_TONE_PREFS / ANIMA_TONE_TRAITS), no song.

  1. EFX level: a Piano 1 part marked -1 on a Reverb unit gets Balance 38 (64 x 0.6); a -1 and
     an unmarked part together keep the drier setting; nothing is written for unmarked parts
  2. traits keep inserts off: Perc.Organ 4 (lfo + rotary) never gets a rotary or LFO type,
     MandolinTrem (CC00 18) no delay, MG 5th Bass no pitch shifter
  3. interval: no harmony plan and no bass sub-octave on a tone that plays extra pitches
  4. fallback: Seq Bass held long twice, Slow Tremolo played short and quick, Vcs&Cbs Pizz
     played high each go back to the capital once, at a rest (no note of the part sounding);
     an unmarked tone played the same way stays
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
import tables_gs as T
D.mido.open_output = lambda n, *a, **k: FakeOut(int(n[1:]) - 1)
D.mido.open_input = lambda *a, **k: FakeIn()
fails = []


def fresh(units=2):
    REC.clear()
    CLOCK[0] = 1000.0
    return D.Duality("in", [f"P{i+1}" for i in range(units)], anima=True, show_status=False,
                     out_formats=[frozenset({"gs"})] * units, anima_seed=0x1111, poly_limits=[64] * units)


def balances(port):
    return [m.data[7] for _t, p, m in REC if p == port and m.type == "sysex"
            and list(m.data[:7]) == [0x41, 0x10, 0x42, 0x12, 0x40, 0x03, 0x12]]


# 1. EFX level
d = fresh()
for ch in (0, 1):
    d._file_used_ch[ch] = True
    d._file_pc[ch] = 0
d._anima_tone_slot[0] = (0, 4, 0)     # Piano 1 [8850]: efx -1 in the picks
d._anima_tone_slot[1] = (1, 4, 0)     # UprightPiano: efx -1 too
d._anima_slots[0] = {"fam": "piano_acoustic", "chs": [0], "typ": (0x01, 0x55), "t": 1.0}
d._anima_efx_level_apply(0, fresh=True)
if balances(0)[-1:] != [38]:
    fails.append(f"1: Piano 1 at -1 on Reverb wrote {balances(0)}, want 38")
d._anima_tone_slot[1] = (0, 3, 0)     # Piano 1 [88Pro]: efx -1
d._anima_slots[0]["chs"] = [0, 1]
REC.clear()
d._anima_efx_level_apply(0)
if balances(0):
    fails.append(f"1: same level rewritten {balances(0)}")
d._anima_file_used = None
d._anima_tone_slot[2] = (0, 4, 4)     # E.Piano 1 capital: no efx level
d._file_used_ch[2] = True
d._file_pc[2] = 4
d._anima_slots[1] = {"fam": "ep_rhodes", "chs": [2], "typ": (0x01, 0x42), "t": 1.0}
REC.clear()
d._anima_efx_level_apply(1, fresh=True)
if balances(1):
    fails.append(f"1: an unmarked tone wrote Balance {balances(1)}")
print("1 EFX level: Piano -1 on Reverb -> 38; unmarked left alone")

# 2. traits keep inserts off
d = fresh()
d._anima_ensure_efx_seed()
cases = [
    (17, (35, 4, 17), "organ_rotary", lambda t: t not in T.ANIMA_EFX_ROTARY_TYPES and t not in T.ANIMA_EFX_LFO_TYPES),
    (25, (18, 4, 25), "guitar_acoustic", lambda t: "delay" not in T.GS_EFX_TYPES.get(t, "").lower()),
    (39, (25, 4, 39), "bass_wide", lambda t: t not in T.ANIMA_EFX_PITCH_TYPES),
]
for gm, slot, fam, ok in cases:
    d._file_used_ch[3] = True
    d._file_pc[3] = gm
    d._anima_prog[3] = gm
    d._anima_tone_slot[3] = slot
    for port in range(2):
        for salt in range(40):
            d._anima_efx_pick.clear()
            d._anima_efx_seed = 0x100 + salt * 97
            pick = d._anima_palette_pick(fam, port, [3])
            if pick and not ok((pick[0], pick[1])):
                fails.append(f"2: {slot} on {fam} got {pick[2]}")
                break
print("2 inserts: Perc.Organ 4 no rotary/LFO, MandolinTrem no delay, MG 5th Bass no pitch shifter")

# 3. interval: no harmony
d = fresh()
d._file_used_ch[4] = True
d._file_pc[4] = 16
d._anima_prog[4] = 16
d._anima_tone_slot[4] = (48, 4, 16)   # 5th Organ
if d._anima_harm_plan(4, 60) is not None:
    fails.append("3: harmony planned on 5th Organ")
if d._anima_bass_sub_wanted(4, 0):
    fails.append("3: bass sub-octave wanted on 5th Organ")
print("3 interval: no harmony, no sub-octave")


# 4. fallback at a rest
def run_fallback(gm, slot, notes):
    d = fresh(1)
    real_pick = d._anima_tone_pick
    def pick(ch, pc):
        if ch != 5:
            return real_pick(ch, pc)
        d._anima_tone_slot[ch] = slot
        d._anima_tone_cc0[ch] = slot[0]
        return slot
    d._anima_tone_pick = pick
    ev = [(0.1, mido.Message("program_change", channel=5, program=gm))]
    for t, n, dur in notes:
        ev += [(t, mido.Message("note_on", channel=5, note=n, velocity=96)),
               (t + dur, mido.Message("note_off", channel=5, note=n, velocity=0))]
    ev.sort(key=lambda e: e[0])
    end = max(t + dur for t, n, dur in notes) + 1.0
    i, tt = 0, 0.0
    while tt <= end:
        CLOCK[0] = 1000.0 + tt
        while i < len(ev) and ev[i][0] <= tt + 1e-9:
            d.process(ev[i][1]); i += 1
        d._anima_tick()
        d._check_anima_session_idle()
        tt = round(tt + 0.005, 3)
    pcs = [t for t, p, m in REC if m.type == "program_change" and m.channel == 5 and t > 0.2]
    return d, pcs, ev


def sounding_at(ev, t):
    held = set()
    for te, m in ev:
        if te > t:
            break
        if m.type == "note_on" and m.velocity:
            held.add(m.note)
        elif m.type in ("note_off", "note_on"):
            held.discard(m.note)
    return held


for name, gm, slot, notes, want in (
    ("Seq Bass held", 39, (3, 4, 39), [(1.0 + k * 1.2, 40, 0.9) for k in range(4)], True),
    ("Slow Tremolo quick", 44, (8, 4, 44), [(1.0 + k * 0.2, 60 + k % 5, 0.1) for k in range(10)], True),
    ("Vcs&Cbs Pizz high", 45, (1, 4, 45), [(1.0 + k * 0.5, 72, 0.2) for k in range(5)], True),
    ("unmarked held", 38, (0, 4, 38), [(1.0 + k * 1.2, 40, 0.9) for k in range(4)], False),
):
    gm_real = slot[2]
    d, pcs, ev = run_fallback(gm_real, slot, notes)
    if want and len(pcs) != 1:
        fails.append(f"4: {name}: {len(pcs)} program changes after the start, want one fallback")
    if not want and pcs:
        fails.append(f"4: {name}: fell back although the tone is not marked")
    for t in pcs:
        if sounding_at(ev, t):
            fails.append(f"4: {name}: fallback at {t:.2f}s under a sounding note")
    if want and pcs and d._anima_tone_slot[5] != (0, 4, gm_real):
        fails.append(f"4: {name}: tone now {d._anima_tone_slot[5]}, want the capital")
    print(f"4 {name}: program changes after start at {[round(t, 2) for t in pcs]}")

if fails:
    print(f"FAILS ({len(fails)}):")
    for f in fails:
        print("   ", f)
    sys.exit(1)
print("PASS")
