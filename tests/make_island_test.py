"""Write "Anima Island Test", an original calypso piece for hearing Anima's mallet sticking.

    python tests/make_island_test.py [out.mid]      (default tests/midi/anima_island_test.mid)

Original composition (no copyright issue; the file is generated, so it can be
rebuilt anywhere). Caribbean island feel in C major with a minor-key cove in the
middle, 108 BPM, about 80 s, GM/GS. Every mallet program Anima sticks shows up,
each with the kind of room its ornaments need: held notes and chords (rolls,
doubles, triplets land in the gaps, chords split across the hands) next to busier
runs that leave them alone.

  ch1  Steel Drums     lead melody, chord hits in the intro and the ending (roll family)
  ch2  Marimba         ostinato and off-beat chords (roll family)
  ch3  Vibraphone      cove melody, long notes (vibes: doubles / triplets)
  ch4  Xylophone       cove answers, break solo: runs, then held notes (roll family)
  ch5  Glockenspiel    sparkles over held chords (bell family)
  ch6  Tubular Bells   section bells (bell family)
  ch7  Acoustic Bass   calypso bass
  ch8  Nylon Guitar    off-beat skank
  ch9  Dulcimer        second melody in A2 (roll family)
  ch10 Standard kit    kick / rim, congas, bongos, shaker, claves, timbales

Sections (bars): Intro 4, Beach A 8, Cove B 8, Break 8, Beach A2 8, Ending 3.
"""
import os
import random
import sys

import mido

BPM = 108
TPB = 480
STEP = TPB // 4          # one 16th
BAR = 16 * STEP
rng = random.Random(1990)
events = []              # (tick, order, message)

STEEL, MARIMBA, VIBES, XYLO, GLOCK, TUBULAR, BASS, NYLON, DULC, DRUM = 0, 1, 2, 3, 4, 5, 6, 7, 8, 9


def at(bar, step=0):
    return T0 + bar * BAR + step * STEP


def note(ch, tick, n, dur, vel, jitter=True):
    j = rng.randint(-5, 5) if jitter else 0
    v = max(1, min(127, vel + (rng.randint(-5, 5) if jitter else 0)))
    t = max(0, tick + j)
    events.append((t, 1, mido.Message("note_on", channel=ch, note=n, velocity=v)))
    events.append((t + max(10, dur), 0, mido.Message("note_off", channel=ch, note=n, velocity=0)))


def chord(ch, tick, notes, dur, vel):
    for n in notes:
        note(ch, tick, n, dur, vel)


def cc(ch, tick, c, v):
    events.append((tick, 0, mido.Message("control_change", channel=ch, control=c, value=v)))


def line(ch, bar, phrase, vel=96):
    """phrase: (step, note, length in steps) on the 16th grid; step may run past 16."""
    for s, n, d in phrase:
        if n:
            note(ch, at(bar) + s * STEP, n, d * STEP - 24, vel + (8 if s % 8 == 0 else 0))


# Chords (mid register voicings) and bass roots
C, F, G7, AM, DM, E7, FM = ([60, 64, 67], [60, 65, 69], [59, 62, 65, 67], [57, 60, 64],
                            [57, 62, 65], [56, 59, 62, 64], [60, 65, 68])
BEACH = [(C, 36), (F, 41), (G7, 43), (C, 36), (C, 36), (F, 41), (G7, 43), (C, 36)]
COVE = [(AM, 45), (DM, 38), (E7, 40), (AM, 45), (F, 41), (DM, 38), (E7, 40), (E7, 40)]

# Melodies (steel drums, vibes). Held notes leave room for rolls; the runs do not.
STEEL_A = [
    [(0, 76, 3), (3, 79, 3), (6, 81, 2), (8, 79, 8)],
    [(0, 77, 2), (2, 76, 2), (4, 74, 2), (6, 72, 2), (8, 74, 8)],
    [(0, 71, 3), (3, 74, 3), (6, 79, 2), (8, 77, 4), (12, 74, 4)],
    [(0, 76, 12), (12, 72, 2), (14, 74, 2)],
    [(0, 76, 3), (3, 79, 3), (6, 84, 2), (8, 83, 2), (10, 81, 2), (12, 79, 4)],
    [(0, 81, 4), (4, 77, 4), (8, 72, 8)],
    [(0, 74, 2), (2, 77, 2), (4, 79, 2), (6, 83, 2), (8, 86, 4), (12, 83, 4)],
    [(0, 84, 16)],
]
VIBES_B = [
    [(0, 76, 8), (8, 72, 4), (12, 69, 4)],
    [(0, 74, 12), (12, 77, 4)],
    [(0, 76, 4), (4, 80, 4), (8, 83, 8)],
    [(0, 81, 16)],
    [(0, 77, 6), (6, 76, 2), (8, 74, 4), (12, 72, 4)],
    [(0, 74, 8), (8, 77, 8)],
    [(0, 80, 4), (4, 76, 4), (8, 74, 4), (12, 71, 4)],
    [(0, 76, 16)],
]
DULC_A2 = [   # a third below the steel drums, simpler rhythm
    [(0, 72, 8), (8, 76, 8)],
    [(0, 72, 4), (4, 69, 4), (8, 71, 8)],
    [(0, 67, 8), (8, 74, 8)],
    [(0, 72, 16)],
    [(0, 72, 8), (8, 76, 8)],
    [(0, 77, 8), (8, 69, 8)],
    [(0, 71, 8), (8, 79, 8)],
    [(0, 76, 16)],
]
XYLO_ANSWER = [   # cove answers between vibes phrases: quarters and a held note (room for rolls)
    [(8, 81, 4), (12, 84, 4)],
    [(8, 77, 4), (12, 81, 4)],
    [(8, 83, 4), (12, 80, 4)],
    [(4, 84, 4), (8, 81, 8)],
]
XYLO_BREAK = [
    [(0, 72, 1), (1, 74, 1), (2, 76, 1), (3, 77, 1), (4, 79, 1), (5, 81, 1), (6, 83, 1), (7, 84, 1),
     (8, 83, 1), (9, 81, 1), (10, 79, 1), (11, 77, 1), (12, 76, 4)],
    [(0, 77, 2), (2, 81, 2), (4, 84, 2), (6, 81, 2), (8, 79, 8)],
    [(0, 84, 1), (1, 83, 1), (2, 81, 1), (3, 79, 1), (4, 77, 1), (5, 76, 1), (6, 74, 1), (7, 72, 1),
     (8, 71, 4), (12, 74, 4)],
    [(0, 72, 6), (6, 79, 2), (8, 84, 8)],
    [(0, 76, 4), (4, 79, 4), (8, 84, 4), (12, 79, 4)],
    [(0, 77, 8), (8, 81, 8)],
    [(0, 79, 2), (2, 83, 2), (4, 86, 4), (8, 83, 4), (12, 79, 4)],
    [(0, 84, 16)],
]


def drums(bar, fill=False, light=False):
    b = at(bar)
    for s in range(0, 16, 2):                                 # shaker 8ths, pushed off-beats
        note(DRUM, b + s * STEP, 70, STEP, 58 if s % 4 else 44)
    if light:
        return
    for s in (0, 6, 8, 14):                                    # kick: calypso push
        note(DRUM, b + s * STEP, 36, STEP, 100 if s in (0, 8) else 84)
    for s in (4, 12):
        note(DRUM, b + s * STEP, 37, STEP, 92)                 # side stick
    for s in (0, 3, 6, 10, 12):                                # claves 3-2
        note(DRUM, b + s * STEP, 75, STEP, 80)
    for s, n in ((2, 63), (3, 64), (6, 62), (10, 63), (11, 64), (14, 62)):
        note(DRUM, b + s * STEP, n, STEP, 76)                  # congas
    if fill:
        for s, n in ((8, 65), (10, 65), (12, 66), (13, 66), (14, 66), (15, 66)):
            note(DRUM, b + s * STEP, n, STEP, 96)              # timbales
        note(DRUM, b + 14 * STEP, 61, STEP, 80)


def bass(bar, root, walk=None):
    b = at(bar)
    for s, off, d in ((0, 0, 3), (3, 7, 3), (6, 12, 2), (8, 0, 3), (11, 7, 3), (14, 4, 2)):
        note(BASS, b + s * STEP, root + off, d * STEP - 30, 104 if s in (0, 8) else 88)
    if walk:
        note(BASS, b + 14 * STEP, walk, 2 * STEP - 30, 90)


def skank(bar, v):
    b = at(bar)
    for s in (2, 6, 10, 14):
        chord(NYLON, b + s * STEP, [n - 12 for n in v] + [v[0]], STEP + 20, 70)


def marimba_ostinato(bar, v, root):
    """8ths: root / fifth / chord tones, spacing just above the sticking minimum."""
    b = at(bar)
    pat = [root + 24, v[1], v[2] if len(v) > 2 else v[0], v[1], root + 24, v[-1], v[1], v[0]]
    for k, n in enumerate(pat):
        note(MARIMBA, b + k * 2 * STEP, n, 2 * STEP - 30, 84 if k % 2 == 0 else 72)


def marimba_offbeats(bar, v):
    """Off-beat chords a quarter apart: struck by hands, room for doubles."""
    b = at(bar)
    for s in (4, 12):
        chord(MARIMBA, b + s * STEP, v, 3 * STEP, 86)


def sparkle(bar, notes):
    b = at(bar)
    for k, n in enumerate(notes):
        note(GLOCK, b + (8 + 2 * k) * STEP, n, STEP * 3, 64)


# --- setup --------------------------------------------------------------------
T0 = TPB * 2
for ch, prog, vol, pan, rev, cho in (
    (STEEL, 114, 104, 50, 50, 20), (MARIMBA, 12, 96, 82, 40, 0), (VIBES, 11, 94, 70, 55, 20),
    (XYLO, 13, 96, 58, 40, 0), (GLOCK, 9, 80, 96, 60, 10), (TUBULAR, 14, 86, 40, 70, 0),
    (BASS, 32, 108, 64, 15, 0), (NYLON, 24, 84, 30, 35, 20), (DULC, 15, 90, 88, 50, 10),
    (DRUM, 0, 104, 64, 30, 0),
):
    cc(ch, 0, 0, 0)
    cc(ch, 0, 32, 0)
    events.append((1, 0, mido.Message("program_change", channel=ch, program=prog)))
    cc(ch, 2, 7, vol)
    cc(ch, 2, 10, pan)
    cc(ch, 2, 91, rev)
    cc(ch, 2, 93, cho)
    cc(ch, 2, 11, 127)

bar = 0
# Intro: steel-drum chords with long gaps (hands split, rolls), bell, shaker only
note(TUBULAR, at(0), 72, BAR, 92)
for k, (v, root) in enumerate([(C, 36), (F, 41), (G7, 43), (C, 36)]):
    chord(STEEL, at(bar), [n + 12 for n in v], 6 * STEP, 92)
    chord(STEEL, at(bar, 8), [n + 12 for n in v[1:]], 6 * STEP, 84)
    if k == 3:
        chord(STEEL, at(bar, 14), [76, 79], STEP, 80)
    drums(bar, light=True)
    if k >= 2:
        note(BASS, at(bar), root, 6 * STEP, 96)
    bar += 1
# Beach A: steel-drum melody, marimba ostinato, skank, full percussion
for k, (v, root) in enumerate(BEACH):
    drums(bar, fill=(k == 7))
    bass(bar, root)
    skank(bar, v)
    marimba_ostinato(bar, v, root)
    line(STEEL, bar, STEEL_A[k], vel=98)
    if k in (3, 7):
        sparkle(bar, [84, 88, 91, 96])
    bar += 1
# Cove B: minor, vibes melody with long notes, marimba off-beat chords, softer drums
note(TUBULAR, at(bar), 69, BAR, 88)
for k, (v, root) in enumerate(COVE):
    drums(bar, fill=(k == 7), light=(k < 2))
    bass(bar, root)
    marimba_offbeats(bar, v)
    line(VIBES, bar, VIBES_B[k], vel=92)
    if k in (0, 2, 4, 6):
        line(XYLO, bar, XYLO_ANSWER[k // 2], vel=84)
    if k % 2 == 1:
        sparkle(bar, [v[-1] + 24, v[0] + 36])
    bar += 1
# Break: xylophone solo over bass and congas; runs, then held notes
for k, (v, root) in enumerate([(C, 36), (F, 41), (G7, 43), (C, 36)] * 2):
    drums(bar, light=True)
    for s, n in ((2, 63), (6, 62), (10, 63), (14, 62)):
        note(DRUM, at(bar, s), n, STEP, 70)
    note(BASS, at(bar), root, 6 * STEP, 98)
    note(BASS, at(bar, 8), root + 7, 6 * STEP, 90)
    line(XYLO, bar, XYLO_BREAK[k], vel=100)
    bar += 1
# Beach A2: everyone, dulcimer harmony under the steel drums, marimba doubles up
note(TUBULAR, at(bar), 72, BAR, 96)
for k, (v, root) in enumerate(BEACH):
    drums(bar, fill=(k == 7))
    bass(bar, root)
    skank(bar, v)
    marimba_ostinato(bar, v, root)
    if k % 2 == 1:
        marimba_offbeats(bar, [n + 12 for n in v])
    line(STEEL, bar, STEEL_A[k], vel=102)
    line(DULC, bar, DULC_A2[k], vel=88)
    if k == 7:
        sparkle(bar, [84, 88, 91, 96])
    bar += 1
# Ending: big C chord on every mallet, left ringing (rolls and split hands), last bell
b = at(bar)
note(DRUM, b, 36, STEP, 112)
note(DRUM, b, 49, BAR, 100)
note(BASS, b, 36, 2 * BAR, 104)
chord(STEEL, b, [72, 76, 79, 84], 2 * BAR, 100)
chord(MARIMBA, b, [48, 55, 60, 64], 2 * BAR, 96)
chord(VIBES, b, [64, 67, 72, 76], 2 * BAR, 90)
chord(DULC, b, [60, 67, 72], 2 * BAR, 86)
note(XYLO, b + 8 * STEP, 84, BAR, 90)
note(TUBULAR, b, 60, 2 * BAR, 100)
sparkle(bar, [96, 91, 88, 84])
end_tick = b + 3 * BAR

# --- write ----------------------------------------------------------------------
events.sort(key=lambda e: (e[0], e[1]))
mf = mido.MidiFile(ticks_per_beat=TPB)
tr = mido.MidiTrack()
mf.tracks.append(tr)
tr.append(mido.MetaMessage("track_name", name="Anima Island Test", time=0))
tr.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(BPM), time=0))
tr.append(mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0))
# GS reset first (the file then sets everything it needs)
tr.append(mido.Message("sysex", data=[0x41, 0x10, 0x42, 0x12, 0x40, 0x00, 0x7F, 0x00, 0x41], time=0))
last = 0
for t, _o, m in events:
    t += TPB                      # one beat after the GS reset
    tr.append(m.copy(time=t - last))
    last = t
tr.append(mido.MetaMessage("end_of_track", time=max(0, end_tick + TPB - last)))
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                            "midi", "anima_island_test.mid")
os.makedirs(os.path.dirname(out), exist_ok=True)
mf.save(out)
print(f"{out}: {mf.length:.1f} s, {sum(1 for m in tr if m.type == 'note_on' and m.velocity)} notes")
