"""Write "Anima Metal Test", an original heavy metal piece for hearing distorted-guitar EFX.

    python tests/make_metal_test.py [out.mid]      (default tests/midi/anima_metal_test.mid)

Original composition (no copyright issue; generated, so it can be rebuilt anywhere).
Sabbath doom meets a Priest gallop meets a Van Halen solo, E minor, GM/GS:

  ch1  Rhythm guitar L  Distortion Gt, hard left     (dirt types that keep its pan)
  ch2  Rhythm guitar R  Overdrive Gt, hard right
  ch3  Lead guitar      Distortion Gt, centre        (eligible for GTR Multi 1-3: wah on Control 1)
  ch4  Bass             Picked Bass
  ch10 Drums            Rock kit: double kick, china, toms

Sections: Doom intro 8 bars (72 BPM), Gallop 8, Twin lead 8, Solo 16 (runs, tapping,
whammy vibrato, two dive bombs), Riff reprise 8 (168 BPM), Doom outro 4 (72 BPM) with a
final dive bomb. The lead's pitch-bend range is one octave (RPN 0 = 12).
"""
import os
import random
import sys

import mido

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

TPB = 480
STEP = TPB // 4           # 16th
BAR = 16 * STEP
rng = random.Random(1978)
events = []               # (tick, order, message)
RL, RR, LEAD, BASS, DRUM = 0, 1, 2, 3, 9


def note(ch, tick, n, dur, vel, jitter=4):
    j = rng.randint(-jitter, jitter) if jitter else 0
    v = max(1, min(127, vel + rng.randint(-4, 4)))
    t = max(0, tick + j)
    events.append((t, 2, mido.Message("note_on", channel=ch, note=n, velocity=v)))
    events.append((t + max(12, dur), 0, mido.Message("note_off", channel=ch, note=n, velocity=0)))


def power(ch, tick, root, dur, vel, oct_=True):
    for n in ([root, root + 7, root + 12] if oct_ else [root, root + 7]):
        note(ch, tick, n, dur, vel, jitter=2)


def cc(ch, tick, c, v, order=1):
    events.append((tick, order, mido.Message("control_change", channel=ch, control=c, value=v)))


def bend(ch, tick, value):
    events.append((tick, 1, mido.Message("pitchwheel", channel=ch, pitch=max(-8192, min(8191, int(value))))))


def tempo(tick, bpm):
    events.append((tick, -1, mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm))))


# --- setup ------------------------------------------------------------------------
for ch, prog, vol, pan, rev in ((RL, 30, 100, 0, 30), (RR, 29, 100, 127, 30), (LEAD, 30, 108, 64, 45),
                                 (BASS, 34, 112, 64, 10), (DRUM, 16, 118, 64, 30)):
    cc(ch, 0, 0, 0)
    cc(ch, 0, 32, 0)
    events.append((1, 1, mido.Message("program_change", channel=ch, program=prog)))
    cc(ch, 2, 7, vol)
    cc(ch, 2, 10, pan)
    cc(ch, 2, 91, rev)
    cc(ch, 2, 11, 127)
for c_, v_ in ((101, 0), (100, 0), (6, 12), (38, 0), (101, 127), (100, 127)):   # bend range 12
    cc(LEAD, 3, c_, v_)
T0 = TPB * 2
tempo(0, 72)


def kick(t, v=112): note(DRUM, t, 36, STEP, v, jitter=2)
def snare(t, v=118): note(DRUM, t, 38, STEP, v, jitter=2)
def crash(t, v=110): note(DRUM, t, 49, BAR // 2, v, jitter=0)
def china(t, v=100): note(DRUM, t, 52, BAR // 4, v, jitter=0)
def hat(t, v=80): note(DRUM, t, 42, STEP // 2, v, jitter=2)
def ride(t, v=86): note(DRUM, t, 51, STEP, v, jitter=2)


def tom_fill(b):
    for s, n in ((8, 50), (9, 50), (10, 48), (11, 48), (12, 45), (13, 45), (14, 43), (15, 41)):
        note(DRUM, b + s * STEP, n, STEP, 108)


def doom_bar(b, k, last=False):
    """Iommi-style: E5 (held), G5, Bb5 (tritone) slide, back to E; half-time drums."""
    riff = [(0, 40, 6), (6, 43, 2), (8, 46, 4), (12, 45, 2), (14, 43, 2)] if k % 2 == 0 else \
           [(0, 40, 8), (8, 38, 2), (10, 40, 6)]
    for s, root, d in riff:
        for ch in (RL, RR):
            power(ch, b + s * STEP, root, d * STEP - 20, 112 if s == 0 else 100)
        note(BASS, b + s * STEP, root - 12, d * STEP - 20, 112)
    kick(b)
    kick(b + 10 * STEP, 100)
    snare(b + 8 * STEP)
    for s in range(0, 16, 4):
        ride(b + s * STEP)
    if k == 0:
        crash(b)
    if last:
        tom_fill(b)


GALLOP_ROOTS = [40, 40, 40, 40, 36 + 12, 38 + 12, 40, 47]     # E E E E C D E B (two-bar pattern per root pair)


def gallop_bar(b, root, accent_last=False, drums=True):
    """Priest gallop: 8th + two 16ths, palm-muted (short), power chord accents on 1."""
    for beat in range(4):
        t = b + beat * 4 * STEP
        for s, d in ((0, 2), (2, 1), (3, 1)):
            for ch in (RL, RR):
                if beat == 0 and s == 0:
                    power(ch, t, root, 2 * STEP - 10, 118)
                else:
                    note(ch, t + s * STEP, root, d * STEP - 25, 92 if s else 104, jitter=2)
            note(BASS, t + s * STEP, root - 12, d * STEP - 20, 108 if s == 0 else 96)
    if accent_last:
        for ch in (RL, RR):
            power(ch, b + 14 * STEP, root + 2, 2 * STEP, 118)
    if drums:
        for s in range(16):
            kick(b + s * STEP, 104 if s % 4 == 0 else 88)          # double kick
        snare(b + 4 * STEP)
        snare(b + 12 * STEP)
        for s in range(0, 16, 2):
            hat(b + s * STEP, 88 if s % 4 == 0 else 64)


def vibrato(ch, t0, dur, depth=380, rate_steps=3):
    """Whammy / finger vibrato: bend wiggles over the held note, then back to 0."""
    k, t = 0, t0
    while t < t0 + dur:
        bend(ch, t, depth if k % 2 == 0 else -depth // 3)
        t += rate_steps * STEP // 2
        k += 1
    bend(ch, t0 + dur, 0)


def dive(ch, t0, dur, deep=-8192, back=True):
    """Dive bomb: bend smoothly down to the bottom, then (optionally) come back up."""
    n = 24
    for i in range(n + 1):
        bend(ch, t0 + i * dur // n, deep * (i / n) ** 1.6)
    if back:
        for i in range(1, 9):
            bend(ch, t0 + dur + i * STEP // 2, deep * (1 - i / 8))


# --- Doom intro, 72 BPM -------------------------------------------------------------
bar = 0
for k in range(8):
    b = T0 + bar * BAR
    doom_bar(b, k, last=(k == 7))
    if k in (5, 7):     # lead enters with a slow bluesy moan and vibrato
        note(LEAD, b + 8 * STEP, 76 if k == 5 else 79, 8 * STEP, 104)
        vibrato(LEAD, b + 10 * STEP, 6 * STEP)
    bar += 1

# --- Gallop, 168 BPM ------------------------------------------------------------------
tempo(T0 + bar * BAR, 168)
for k in range(8):
    b = T0 + bar * BAR
    gallop_bar(b, GALLOP_ROOTS[k], accent_last=(k % 2 == 1))
    if k == 0:
        crash(b); china(b + 8 * STEP)
    if k == 7:
        tom_fill(b)
    bar += 1

# --- Twin lead in thirds (Priest), rhythm keeps galloping ------------------------------
TWIN = [  # (step, lead note, length) over 2-bar cells; harmony a diatonic third below on RR
    [(0, 76, 4), (4, 74, 2), (6, 72, 2), (8, 71, 4), (12, 72, 2), (14, 74, 2)],
    [(0, 76, 6), (6, 79, 2), (8, 78, 4), (12, 76, 4)],
]
THIRD = {76: 72, 74: 71, 72: 69, 71: 67, 79: 76, 78: 74, 81: 78, 83: 79, 84: 81, 86: 83, 88: 84}
for k in range(8):
    b = T0 + bar * BAR
    gallop_bar(b, GALLOP_ROOTS[k], accent_last=(k % 2 == 1))
    for s, n, d in TWIN[k % 2]:
        n2 = n + (5 if k >= 4 else 0) if n + (5 if k >= 4 else 0) in THIRD else n
        note(LEAD, b + s * STEP, n2, d * STEP - 15, 110)
        note(RR, b + s * STEP, THIRD[n2], d * STEP - 15, 100)
    if k == 0:
        crash(b)
    bar += 1

# --- Solo, 16 bars: runs, tapping, vibrato, dive bombs ---------------------------------
SOLO_ROOTS = [40, 40, 36 + 12, 38 + 12] * 4
TAPS = {40: [88, 83, 79], 48: [88, 84, 79], 50: [86, 81, 78], 47: [87, 83, 78]}
solo_start = bar
for k in range(16):
    b = T0 + bar * BAR
    root = SOLO_ROOTS[k]
    gallop_bar(b, root, accent_last=(k % 4 == 3))
    if k == 0:
        crash(b)
        note(LEAD, b, 83, 12 * STEP, 118)                     # screaming entry note
        vibrato(LEAD, b + 4 * STEP, 8 * STEP, depth=520)
        for i, n in enumerate([81, 79, 78, 76]):
            note(LEAD, b + (12 + i) * STEP, n, STEP - 10, 104)
    elif k in (1, 2, 3):                                      # E minor pentatonic runs, 16ths then sextuplets
        scale = [64, 67, 69, 71, 74, 76, 79, 81, 83, 86, 88]
        cnt = 16 if k < 3 else 24
        for i in range(cnt):
            idx = (i + k * 3) % len(scale) if (i // 6) % 2 == 0 else len(scale) - 1 - (i + k) % len(scale)
            note(LEAD, b + i * BAR // cnt, scale[idx], BAR // cnt - 8, 100 + (i % 3) * 6, jitter=1)
    elif k == 4:                                              # dive bomb #1 from the open E harmonic
        note(LEAD, b, 88, 16 * STEP, 124)
        dive(LEAD, b + 2 * STEP, 10 * STEP, back=True)
    elif 5 <= k <= 10:                                        # two-handed tapping: triplets of 16ths
        cell = TAPS[root if root in TAPS else 40]
        n_notes = 24
        for i in range(n_notes):
            n = cell[i % 3] - (12 if (k == 8 and i % 6 >= 3) else 0)
            note(LEAD, b + i * BAR // n_notes, n, BAR // n_notes - 6, 112 if i % 3 == 0 else 96, jitter=0)
    elif k == 11:                                             # chromatic climb to the high B
        for i, n in enumerate(range(76, 92)):
            note(LEAD, b + i * STEP, n, STEP - 8, 100 + i, jitter=1)
    elif k in (12, 13):                                       # held high note, wide vibrato
        if k == 12:
            note(LEAD, b, 91, 2 * BAR - 40, 124)
            vibrato(LEAD, b + 2 * STEP, 2 * BAR - 4 * STEP, depth=700, rate_steps=2)
    elif k == 14:                                             # dive bomb #2, all the way, slow return
        note(LEAD, b, 88, 16 * STEP, 124)
        dive(LEAD, b + STEP, 12 * STEP, back=True)
    elif k == 15:
        tom_fill(b)
        for i, n in enumerate([76, 79, 81, 83, 86, 88, 91, 88]):
            note(LEAD, b + i * 2 * STEP, n, 2 * STEP - 10, 116)
    bar += 1

# --- Riff reprise ----------------------------------------------------------------------
for k in range(8):
    b = T0 + bar * BAR
    gallop_bar(b, GALLOP_ROOTS[k], accent_last=(k % 2 == 1))
    if k % 2 == 0:
        crash(b)
    if k in (1, 3, 5, 7):                                     # lead answers with bent stabs
        note(LEAD, b + 8 * STEP, 83, 6 * STEP, 112)
        bend(LEAD, b + 8 * STEP, -1365)                       # pre-bent a tone below, release up
        bend(LEAD, b + 10 * STEP, 0)
    if k == 7:
        tom_fill(b)
    bar += 1

# --- Doom outro, 72 BPM, final dive ------------------------------------------------------
tempo(T0 + bar * BAR, 72)
for k in range(4):
    b = T0 + bar * BAR
    if k < 3:
        doom_bar(b, k)
    else:
        crash(b, 120)
        kick(b, 120)
        for ch in (RL, RR):
            power(ch, b, 40, 2 * BAR, 124)
        note(BASS, b, 28, 2 * BAR, 118)
        note(LEAD, b, 76, 2 * BAR - 60, 124)
        vibrato(LEAD, b + 2 * STEP, 6 * STEP, depth=500)
        dive(LEAD, b + 8 * STEP, 20 * STEP, back=False)
    bar += 1
bend(LEAD, T0 + (bar + 1) * BAR, 0)
end_tick = T0 + (bar + 2) * BAR

# --- write -------------------------------------------------------------------------------
events.sort(key=lambda e: (e[0], e[1]))
mf = mido.MidiFile(ticks_per_beat=TPB)
tr = mido.MidiTrack()
mf.tracks.append(tr)
tr.append(mido.MetaMessage("track_name", name="Anima Metal Test", time=0))
tr.append(mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0))
tr.append(mido.Message("sysex", data=[0x41, 0x10, 0x42, 0x12, 0x40, 0x00, 0x7F, 0x00, 0x41], time=0))
last = 0
for t, _o, m in events:
    t += TPB
    tr.append(m.copy(time=t - last))
    last = t
tr.append(mido.MetaMessage("end_of_track", time=max(0, end_tick + TPB - last)))
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                            "midi", "anima_metal_test.mid")
os.makedirs(os.path.dirname(out), exist_ok=True)
mf = common.format1(mf)   # conductor + one named track per channel
mf.save(out)
print(f"{out}: Format 1, {len(mf.tracks)} tracks, {mf.length:.1f} s, {sum(1 for m in tr if m.type == 'note_on' and m.velocity)} notes, "
      f"{sum(1 for m in tr if m.type == 'pitchwheel')} bends")
