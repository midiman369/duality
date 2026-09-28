"""Write "Anima Funk Test", an original groove for hearing Anima's EFX control.

    python tests/make_funk_test.py [out.mid]      (default tests/midi/anima_funk_test.mid)

Original composition (no copyright issue; the file is generated, so it can be
rebuilt anywhere). E dorian funk, 100 BPM, about 90 s, GM/GS:

  ch1  Drawbar Organ   long held chords (rotary flips), short skanks (no flip)
  ch2  Fingered Bass   syncopated line
  ch3  Muted Guitar    16th-note chops (wah candidate), panned left
  ch4  Clean Guitar    off-beat stabs (wah candidate), panned right
  ch5  E.Piano 1       bridge comping (Rhodes: PH/Rotary, PH/AutoWah candidates)
  ch6  Alto Sax        bridge melody and A2 riffs
  ch10 Standard kit    kick / snare with ghosts / 16th hats

Sections (bars): Intro 4, Groove A 8, Bridge 8, Breakdown 4, Groove A2 8, End 2.
"""
import os
import random
import sys

import mido

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

BPM = 100
TPB = 480
STEP = TPB // 4          # one 16th
BAR = 16 * STEP
rng = random.Random(1969)
events = []              # (tick, order, message)

ORG, BASS, MUTE, CLEAN, EP, SAX, DRUM = 0, 1, 2, 3, 4, 5, 9


def at(bar, step=0):
    return bar * BAR + step * STEP


def note(ch, tick, n, dur, vel, jitter=True):
    j = rng.randint(-6, 6) if jitter else 0
    v = max(1, min(127, vel + (rng.randint(-5, 5) if jitter else 0)))
    t = max(0, tick + j)
    events.append((t, 1, mido.Message("note_on", channel=ch, note=n, velocity=v)))
    events.append((t + max(10, dur), 0, mido.Message("note_off", channel=ch, note=n, velocity=0)))


def chord(ch, tick, notes, dur, vel, spread=0):
    for i, n in enumerate(notes):
        note(ch, tick + i * spread, n, dur, vel)


def cc(ch, tick, c, v):
    events.append((tick, 0, mido.Message("control_change", channel=ch, control=c, value=v)))


# Voicings (organ / guitars / EP share the middle register)
EM9 = [52, 55, 59, 62, 66]      # E G B D F#
A13 = [55, 61, 66, 71]          # G C# F# B  (over A in the bass)
CMAJ9 = [52, 55, 59, 62]        # E G B D    (over C)
BM7 = [54, 57, 59, 62]          # F# A B D
AM9 = [55, 59, 60, 64]          # G B C E
D9 = [54, 57, 60, 64]           # F# A C E
B7S9 = [51, 57, 62]             # D# A D     (B7#9)
BRIDGE = [(CMAJ9, 36), (BM7, 35), (AM9, 33), (D9, 38), (CMAJ9, 36), (BM7, 35), (AM9, 33), (B7S9, 35)]
GROOVE = [(EM9, 28), (EM9, 28), (A13, 33), (A13, 33)]      # 4-bar cycle, bass roots (E1 / A1)

# --- setup --------------------------------------------------------------------
for ch, prog, vol, pan, rev, cho in (
    (ORG, 16, 96, 64, 40, 10), (BASS, 33, 110, 60, 10, 0), (MUTE, 28, 92, 36, 30, 0),
    (CLEAN, 27, 88, 92, 40, 20), (EP, 4, 90, 76, 45, 30), (SAX, 65, 100, 58, 50, 0),
    (DRUM, 0, 110, 64, 25, 0),
):
    cc(ch, 0, 0, 0)
    cc(ch, 0, 32, 0)
    events.append((1, 0, mido.Message("program_change", channel=ch, program=prog)))
    cc(ch, 2, 7, vol)
    cc(ch, 2, 10, pan)
    cc(ch, 2, 91, rev)
    cc(ch, 2, 93, cho)
    cc(ch, 2, 11, 127)
T0 = TPB * 2                                               # two beats of silence first


def drums(bar, fill=False, light=False):
    b = T0 + at(bar)
    kicks = [0, 3, 7, 10] if not light else [0, 10]
    for s in kicks:
        note(DRUM, b + s * STEP, 36, STEP, 112 if s == 0 else 96)
    if not light:
        for s in (4, 12):
            note(DRUM, b + s * STEP, 38, STEP, 115)
        for s in (7, 9, 15):
            note(DRUM, b + s * STEP, 38, STEP, 34)         # ghost notes
    for s in range(16):
        if s == 14 and bar % 2 == 1:
            note(DRUM, b + s * STEP, 46, 2 * STEP, 80)     # open hat into the next bar
        else:
            note(DRUM, b + s * STEP, 42, STEP // 2, 92 if s % 4 == 0 else (70 if s % 2 == 0 else 48))
    if fill:
        for s, n in ((12, 38), (13, 45), (14, 43), (15, 41)):
            note(DRUM, b + s * STEP, n, STEP, 100)


def bass_groove(bar, root):
    b = T0 + at(bar)
    if root == 28:        # E: E1 . . E2 . . D2 . G1 . A1 . B1 . D2 .
        line = [(0, 28, 3), (3, 40, 1), (6, 38, 1), (8, 31, 2), (10, 33, 2), (12, 35, 2), (14, 38, 1)]
    else:                 # A: A1 . . A2 . . G2 . E2 . F#2 . G2 A2 .
        line = [(0, 33, 3), (3, 45, 1), (6, 43, 1), (8, 40, 2), (10, 42, 2), (12, 43, 1), (13, 45, 2)]
    for s, n, d in line:
        note(BASS, b + s * STEP, n, d * STEP - 20, 104 if s == 0 else 90)


def mute_chops(bar, voicing, sparse=False):
    b = T0 + at(bar)
    top = voicing[-2:]
    pattern = [1, 0, 1, 1, 0, 1, 1, 0, 1, 0, 1, 1, 0, 1, 1, 1] if not sparse else [1, 0, 0, 1, 0, 0, 1, 0] * 2
    for s, hit in enumerate(pattern):
        if not hit:
            continue
        accent = s % 4 == 2
        chord(MUTE, b + s * STEP, top, STEP - 25, 100 if accent else 72)


def clean_stabs(bar, voicing):
    b = T0 + at(bar)
    for s in (2, 6, 10, 14):
        chord(CLEAN, b + s * STEP, voicing[1:4], STEP + 40, 92 if s in (6, 14) else 80)


def organ_skanks(bar, voicing):
    b = T0 + at(bar)
    for s in (6, 14):                                       # "and" of 2 and 4, short
        chord(ORG, b + s * STEP, voicing, STEP * 2, 84)


def organ_hold(bar, voicing, bars=1, vel=88, swell=False):
    b = T0 + at(bar)
    chord(ORG, b, voicing, bars * BAR - 30, vel)
    if swell:
        for k in range(17):
            cc(ORG, b + k * (bars * BAR // 16), 11, 70 + k * 3)


def ep_comp(bar, voicing):
    b = T0 + at(bar)
    for s, d in ((0, 3), (5, 2), (10, 3), (14, 2)):
        chord(EP, b + s * STEP, [n + 12 for n in voicing], d * STEP, 78, spread=8)


def sax(bar, phrase):
    b = T0 + at(bar)
    for s, n, d, v in phrase:
        note(SAX, b + s * STEP, n, d * STEP - 15, v)


# Sax phrases (16th steps within the bar, note, length, velocity)
SAX_BRIDGE = [
    [(0, 71, 6, 96), (6, 69, 2, 84), (8, 67, 2, 86), (10, 64, 6, 92)],
    [(2, 66, 2, 84), (4, 69, 4, 92), (8, 71, 2, 86), (10, 74, 6, 100)],
    [(0, 72, 4, 98), (4, 71, 2, 86), (6, 69, 2, 84), (8, 67, 8, 90)],
    [(0, 66, 2, 84), (2, 69, 2, 86), (4, 72, 4, 94), (8, 74, 4, 98), (12, 76, 4, 102)],
    [(0, 79, 8, 108), (8, 76, 2, 92), (10, 74, 2, 90), (12, 71, 4, 94)],
    [(0, 74, 4, 96), (4, 73, 2, 86), (6, 71, 2, 86), (8, 69, 8, 90)],
    [(0, 67, 2, 84), (2, 69, 2, 86), (4, 71, 2, 88), (6, 72, 2, 90), (8, 76, 8, 100)],
    [(0, 75, 6, 104), (6, 74, 2, 90), (8, 69, 8, 92)],
]
SAX_RIFF = [(0, 64, 2, 96), (3, 67, 1, 84), (4, 69, 2, 92), (7, 71, 1, 84), (8, 74, 3, 100),
            (12, 71, 2, 88), (14, 69, 2, 86)]

bar = 0
# Intro: organ holds two bars each (rotary flips), hats only
for k, v in enumerate([EM9, EM9, A13, A13]):
    if k % 2 == 0:
        organ_hold(bar, v, bars=2, vel=86, swell=(k == 0))
    b = T0 + at(bar)
    for s in range(0, 16, 2):
        note(DRUM, b + s * STEP, 42, STEP // 2, 70 if s % 4 == 0 else 50)
    if k >= 2:
        note(BASS, b, 33, 2 * BAR - 30 if k == 2 else 20, 96)
    bar += 1
drums(bar - 1, fill=True, light=True)
# Groove A
for k in range(8):
    v, root = GROOVE[k % 4]
    drums(bar, fill=(k == 7))
    bass_groove(bar, root)
    mute_chops(bar, v)
    clean_stabs(bar, v)
    organ_skanks(bar, v)
    bar += 1
# Bridge: organ pads one bar each (rotary flips), EP comping, sax melody
for k, (v, root) in enumerate(BRIDGE):
    drums(bar, fill=(k == 7))
    b = T0 + at(bar)
    for s, d in ((0, 6), (6, 2), (8, 6), (14, 2)):
        note(BASS, b + s * STEP, root + (12 if s == 14 else 0), d * STEP - 20, 100 if s == 0 else 86)
    organ_hold(bar, v, bars=1, vel=80)
    ep_comp(bar, v)
    mute_chops(bar, v, sparse=True)
    sax(bar, SAX_BRIDGE[k])
    bar += 1
# Breakdown: drums light, muted guitar alone (the wah is in the open), organ swells in on bar 4
for k in range(4):
    v, root = GROOVE[k % 4]
    drums(bar, light=True, fill=(k == 3))
    mute_chops(bar, v)
    if k in (1, 3):
        note(BASS, T0 + at(bar), root, BAR // 2, 92)
    if k == 3:
        organ_hold(bar, EM9, bars=1, vel=90, swell=True)
    bar += 1
# Groove A2 with sax riffs
for k in range(8):
    v, root = GROOVE[k % 4]
    drums(bar, fill=(k == 7))
    bass_groove(bar, root)
    mute_chops(bar, v)
    clean_stabs(bar, v)
    organ_skanks(bar, v)
    if k % 2 == 0:
        sax(bar, SAX_RIFF)
    bar += 1
# Ending: a band hit, then one long held Em9 (last rotary flip and release)
b = T0 + at(bar)
note(DRUM, b, 49, BAR, 118)
note(DRUM, b, 36, STEP, 118)
note(BASS, b, 28, BAR * 2, 108)
chord(CLEAN, b, EM9[1:4], STEP * 2, 104)
chord(MUTE, b, EM9[-2:], STEP, 104)
note(SAX, b, 76, BAR, 100)
organ_hold(bar, EM9, bars=2, vel=94)
for k in range(9):
    cc(ORG, b + BAR + k * (BAR // 8), 11, 127 - k * 10)
end_tick = b + 2 * BAR + TPB * 2

# --- write ----------------------------------------------------------------------
events.sort(key=lambda e: (e[0], e[1]))
mf = mido.MidiFile(ticks_per_beat=TPB)
tr = mido.MidiTrack()
mf.tracks.append(tr)
tr.append(mido.MetaMessage("track_name", name="Anima Funk Test", time=0))
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
                                                            "midi", "anima_funk_test.mid")
os.makedirs(os.path.dirname(out), exist_ok=True)
mf = common.format1(mf)   # conductor + one named track per channel
mf.save(out)
print(f"{out}: Format 1, {len(mf.tracks)} tracks (ties kept in order, <= {mf.max_shift} ticks late), {mf.length:.1f} s, {sum(1 for m in tr if m.type == 'note_on' and m.velocity)} notes")
