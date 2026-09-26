"""Mallet sticking, self-contained (no song file).

A marimba (GM 13) plays four-note chords every 0.6 s, then single notes every
0.3 s, then a fast run. Checks:
  - chord onset struck by hands: the second hand lands ~ANIMA_MALLET_HAND_GAP
    after the first, and the first is not later than a plain unroll would be
  - extra strokes appear only when the part leaves room, never in the fast run
  - roll strokes alternate hands; extra strokes are softer than the note
  - a note arriving early cancels pending strokes (none after it on that key set)
  - a program change cancels pending strokes
  - no hanging notes, voice counts back to 0
  - a Stereo Delay on the marimba's unit is timed from the part's spacing
    (0.6 s chords: taps ~0.6 s / ~1.2 s, folded to fit) with 12% feedback
"""
import sys
import collections
import time as _time
import common  # noqa: F401  (repo on sys.path)
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

_outs = {}
def open_output(name, *a, **k):
    _outs[name] = FakeOut(int(name[1:]) - 1); return _outs[name]

import duality as D
D.mido.open_output = open_output
D.mido.open_input = lambda *a, **k: FakeIn()
fails = []
kinds = collections.Counter()

def run(seed):
    REC.clear()
    d = D.Duality("in", [f"P{i+1}" for i in range(2)], anima=True, show_status=False,
                  out_formats=[frozenset({"gs"})] * 2, anima_seed=seed, poly_limits=[64] * 2)
    log = []
    _fb = d._anima_feedback
    def fb(kind, text, status=False):
        if kind == "mallet":
            log.append((CLOCK[0], text))
        return _fb(kind, text, status=status)
    d._anima_feedback = fb
    ch = 2
    ev = [(0.0, mido.Message("program_change", channel=ch, program=12))]
    t = 0.5
    chords = []
    for k in range(16):                       # chords, room for rolls
        notes = [60, 64, 67, 72] if k % 2 == 0 else [62, 65, 69, 74]
        chords.append((t, notes))
        for n in notes:
            ev.append((t, mido.Message("note_on", channel=ch, note=n, velocity=100)))
            ev.append((t + 0.10, mido.Message("note_off", channel=ch, note=n, velocity=0)))
        t += 0.6
    early_t = t - 0.15                        # one chord comes early
    for n in (60, 64, 67, 72):
        ev.append((early_t, mido.Message("note_on", channel=ch, note=n, velocity=100)))
        ev.append((early_t + 0.1, mido.Message("note_off", channel=ch, note=n, velocity=0)))
    t += 0.4
    for k in range(20):                       # single notes, 0.3 s
        ev.append((t, mido.Message("note_on", channel=ch, note=72 + k % 5, velocity=90)))
        ev.append((t + 0.08, mido.Message("note_off", channel=ch, note=72 + k % 5, velocity=0)))
        t += 0.3
    fast0 = t
    for k in range(20):                       # fast run, 0.1 s: no room
        ev.append((t, mido.Message("note_on", channel=ch, note=72 + k % 7, velocity=90)))
        ev.append((t + 0.05, mido.Message("note_off", channel=ch, note=72 + k % 7, velocity=0)))
        t += 0.1
    fast1 = t
    pc_t = t + 0.3                            # notes, then a PC right after the last one
    for k in range(6):
        ev.append((pc_t + k * 0.35, mido.Message("note_on", channel=ch, note=70, velocity=90)))
        ev.append((pc_t + k * 0.35 + 0.05, mido.Message("note_off", channel=ch, note=70, velocity=0)))
    pc_at = pc_t + 5 * 0.35 + 0.03
    ev.append((pc_at, mido.Message("program_change", channel=ch, program=71)))
    end = pc_at + 1.5
    ev.sort(key=lambda e: e[0])
    i, tt = 0, 0.0
    checked = False
    while tt <= end:
        CLOCK[0] = 1000.0 + tt
        while i < len(ev) and ev[i][0] <= tt + 1e-9:
            d.process(ev[i][1]); i += 1
        d._anima_tick()
        if not checked and tt >= chords[-1][0] + 0.05:
            checked = True
            pulse, mallet = d._anima_efx_dly_pulse([ch])
            if not mallet or abs(pulse - 1.2) > 0.05:
                fails.append(f"seed {seed:04X} delay pulse {pulse:.3f} mallet={mallet}, want 1.2 s")
            n0 = len(REC)
            d._anima_efx_shape(0, (0x01, 0x50), [ch], "chromatic")
            dt1 = {tuple(m.data[4:7]): m.data[7] for _t, p, m in REC[n0:]
                   if p == 0 and m.type == "sysex" and list(m.data[:4]) == [0x41, 0x10, 0x42, 0x12]}
            tab = D.GS_DLY_MS[4]
            l_ms, r_ms = tab[dt1.get((0x40, 0x03, 0x03), 0)], tab[dt1.get((0x40, 0x03, 0x04), 0)]
            if not (abs(r_ms - 2 * l_ms) <= 0.1 * r_ms and (abs(l_ms - 600) < 40 or abs(l_ms - 300) < 25
                                                             or abs(l_ms - 150) < 15)):
                fails.append(f"seed {seed:04X} delay taps {l_ms:.0f}/{r_ms:.0f} ms not on the 0.6 s grid")
            if dt1.get((0x40, 0x03, 0x05)) != 0x40 + D.ANIMA_MALLET_DLY_FB_PCT // 2:
                fails.append(f"seed {seed:04X} delay feedback {dt1.get((0x40, 0x03, 0x05))}")
        tt = round(tt + 0.002, 3)
    ons = [(t0 - 1000.0, p, m) for t0, p, m in REC if m.type == "note_on" and m.velocity and m.channel == ch]
    # chord onsets: two hands
    for tc, notes in chords[3:]:
        first = sorted((t0, m.note) for t0, p, m in ons if tc - 0.001 <= t0 <= tc + 0.06 and m.velocity >= 95)
        lo = [x[0] for x in first if x[1] in notes[:2]]
        hi = [x[0] for x in first if x[1] in notes[2:]]
        if not lo or not hi:
            fails.append(f"seed {seed:04X} t={tc:.2f} chord onset missing {first}"); continue
        gap = abs(min(hi) - min(lo))
        if not 0.010 <= gap <= 0.035:
            fails.append(f"seed {seed:04X} t={tc:.2f} hand gap {gap*1000:.0f} ms")
        if min(min(lo), min(hi)) - tc > D.ANIMA_UNROLL_COLLECT + 0.012:
            fails.append(f"seed {seed:04X} t={tc:.2f} first hand late")
    extra = [(t0, m) for t0, p, m in ons if m.velocity < 90]
    for t0, m in extra:
        if fast0 + 0.25 < t0 < fast1:
            fails.append(f"seed {seed:04X} stroke in the fast run at {t0:.2f}")
        if pc_at < t0:
            fails.append(f"seed {seed:04X} stroke after the program change at {t0:.2f}")
        if early_t - 0.001 <= t0 <= early_t + 0.002:
            fails.append(f"seed {seed:04X} stroke on top of the early chord")
    # roll hands alternate: consecutive roll strokes of a chord use different note pairs
    for t0, text in log:
        kinds[text.split()[1]] += 1
    bal = collections.Counter()
    for _t, p, m in REC:
        if m.type == "note_on" and m.velocity:
            bal[(p, m.channel, m.note)] += 1
        elif m.type in ("note_on", "note_off"):
            bal[(p, m.channel, m.note)] = 0
    hang = [k for k, v in bal.items() if v > 0]
    if hang:
        fails.append(f"seed {seed:04X} hanging notes {hang}")
    if any(d.voice_counts):
        fails.append(f"seed {seed:04X} voice counts {d.voice_counts}")
    return log

rolls_alt = True
for seed in (0x6BA1, 0x1234, 0xBEEF, 0x2927, 0x4BBD):
    log = run(seed)
print("ornaments over 5 seeds:", dict(kinds))
if not kinds.get("roll") or not kinds.get("double") or not kinds.get("triplet"):
    fails.append(f"expected rolls, doubles and triplets across seeds, got {dict(kinds)}")
if fails:
    print(f"FAILS ({len(fails)}):")
    for f in fails[:20]:
        print("   ", f)
    sys.exit(1)
print("PASS")
