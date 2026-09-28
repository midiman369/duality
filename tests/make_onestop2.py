"""Write "ONESTOP2 - A Brief History of Sound", a 5:11 showcase for Duality + Anima.

    python tests/make_onestop2.py [out.mid]      (default tests/midi/onestop2.mid)

Original composition (no copyright issue; generated, so it can be rebuilt anywhere). It plays
complete on a single SC-8850 (GM capitals, GS drum sets, one GS reset at the start, no file
insert EFX), and is laid out for Duality with six GS units: every section change is a program
change burst (Anima places inserts once per burst; game mode rerolls per cue), and each
transition is built to exercise an EFX rule.

Sections (and the transition into the next):
  1 Medieval / Renaissance  88 BPM   recorder + pan flute duet, lute, dulcimer, cello drone,
                                     church-organ drone, harp, tabor & tambourine
      -> the organ drone keeps sounding while the other parts change program (an unheard
         program change must not take a sounding family's unit)
  2 Baroque -> Classical   100 BPM   harpsichord continuo, violin tune (slow featured line),
                                     then 16th runs (fast line), oboe, pizzicato bass, strings,
                                     horns, timpani; pizzicato turns into tremolo strings
  3 Cathedral crescendo     72 BPM   pipe organ + choir + strings swell (CC11), horn tune,
                                     timpani roll, orchestra-hit ending, then a full rest
      -> the rest lets every unit retype; the big-band setup burst lands in the count-off
  4 Big band swing         160 BPM   trumpet, trombone, alto / tenor / baritone sax, walking
                                     upright, piano comping, jazz guitar, jazz kit; sax soli
  5 Proto-synth machine    144 BPM   square lead, xylophone ostinato (mallets), celesta,
                                     muted trumpet; the trombone crosses over from the big band
      -> a drums-only fill carries the rock'n'roll setup burst
  6 Rock'n'roll            168 BPM   boogie piano, twang clean guitar (rhythm, then a lead
                                     chorus: wah rhythm -> lead), honking tenor sax, slapped
                                     upright, bari sax
      -> the sax holds and fades (CC7) while the synths fade in
  7 Analog synths          120 BPM   saw arpeggio (short notes, then held ones), sequenced
                                     bass, square lead with bends, synth brass, poly pad, 808 kit
      -> the pad holds while a drawbar organ chord swells in
  8 Prog / hard rock       132 BPM   drawbar organ (held chords: rotary flips; fast runs),
                                     overdrive guitar, fingered bass, saw lead; a 7/8 passage;
                                     ends on a held power chord fading out (dirt level follows)
  9 Metal                  176 BPM   NWOBHM gallop, guitars hard left / right, twin harmony
                   100 BPM   groove riff, lead solo (runs, tapping, whammy, dive bomb)
                    72 BPM   epic doom finale: pipe organ + choir return, last dive, fade

Channels change programs between sections (the point: families come and go). Pitch-bend range
is one octave on the lead guitar and the synth leads (RPN 0 = 12 / 2).
"""
import os
import random
import sys

import mido

TPB = 480
rng = random.Random(1492)
events = []          # (tick, order, message)
tempos = []          # (tick, bpm)
sigs = []            # (tick, num, den)

C1, C2, C3, C4, C5, C6, C7, C8, C9, DR, C11, C12, C13, C14, C15, C16 = range(16)

# --------------------------------------------------------------------------------------
# timeline helpers
# --------------------------------------------------------------------------------------
pos = TPB * 2        # current section start (ticks); two beats of silence first
BPB = 4.0            # beats per bar in the current section


def section(bpm, beats=4.0, den=4):
    global BPB
    BPB = beats
    tempos.append((pos, bpm))
    num = int(round(beats * den / 4))
    sigs.append((pos, num, den))


def t(bar, beat=0.0):
    return pos + int(round((bar * BPB + beat) * TPB))


def advance(bars):
    global pos
    pos = t(bars)


def note(ch, tick, n, beats, vel, jitter=5, gate=0.92):
    j = rng.randint(-jitter, jitter) if jitter else 0
    v = max(1, min(127, vel + rng.randint(-4, 4)))
    tk = max(0, tick + j)
    d = max(15, int(beats * TPB * gate))
    events.append((tk, 2, mido.Message("note_on", channel=ch, note=int(n), velocity=v)))
    events.append((tk + d, 0, mido.Message("note_off", channel=ch, note=int(n), velocity=0)))


def chord(ch, tick, notes, beats, vel, roll=0, gate=0.95):
    for i, n in enumerate(notes):
        note(ch, tick + i * roll, n, beats, vel - i, jitter=3, gate=gate)


def cc(ch, tick, c, v):
    events.append((tick, 1, mido.Message("control_change", channel=ch, control=c, value=max(0, min(127, int(v))))))


def ramp(ch, c, t0, t1, v0, v1, steps=24):
    for k in range(steps + 1):
        cc(ch, t0 + (t1 - t0) * k // steps, c, v0 + (v1 - v0) * k / steps)


def bend(ch, tick, value):
    events.append((tick, 1, mido.Message("pitchwheel", channel=ch, pitch=max(-8192, min(8191, int(value))))))


def bend_curve(ch, t0, t1, v0, v1, steps=16):
    for k in range(steps + 1):
        bend(ch, t0 + (t1 - t0) * k // steps, v0 + (v1 - v0) * k / steps)


def prog(ch, tick, program, vol=100, pan=64, rev=40, cho=0, expr=127):
    """Bank 0 + program + mix, at tick (the channel must be silent there)."""
    cc(ch, tick, 0, 0)
    cc(ch, tick, 32, 0)
    events.append((tick + 1, 1, mido.Message("program_change", channel=ch, program=program)))
    cc(ch, tick + 2, 7, vol)
    cc(ch, tick + 2, 10, pan)
    cc(ch, tick + 2, 91, rev)
    cc(ch, tick + 2, 93, cho)
    cc(ch, tick + 2, 11, expr)


def bend_range(ch, tick, semis):
    for c_, v_ in ((101, 0), (100, 0), (6, semis), (38, 0), (101, 127), (100, 127)):
        cc(ch, tick, c_, v_)


def line(ch, bar0, spec, vel=96, gate=0.9, octave=0, jitter=5):
    """spec: list of (beat_offset_from_bar0, midi_note or None, length_in_beats)."""
    for b, n, d in spec:
        if n is not None:
            note(ch, t(bar0, b), n + octave, d, vel + (6 if abs(b % 1) < 1e-6 else 0), jitter=jitter, gate=gate)


def seq(start_beat, notes, dur):
    """Evenly spaced notes -> spec rows."""
    return [(start_beat + i * dur, n, dur) for i, n in enumerate(notes)]


def drum(tick, n, vel, jitter=4):
    note(DR, tick, n, 0.25, vel, jitter=jitter, gate=0.5)


# Drum notes (GS)
KICK, SIDE, SNARE, CLAP, SNARE2, LTOM, CHH, LTOM2, PHH, MTOM, OHH, HTOM, CRASH, RIDE, CHINA, \
    RBELL, TAMB, SPLASH, COWB, CRASH2 = 36, 37, 38, 39, 40, 41, 42, 43, 44, 47, 46, 50, 49, 51, 52, \
    53, 54, 55, 56, 57
TRI, SHAKER, WOODH, WOODL, CLAVES, CONGA_H, CONGA_L, TIMP_L = 81, 82, 76, 77, 75, 63, 64, 45


def swing(beat):
    """Swing an 8th grid: the off-beat 8th lands on the triplet."""
    whole, frac = divmod(beat, 1.0)
    return whole + (2 / 3 if abs(frac - 0.5) < 1e-6 else frac)


# --------------------------------------------------------------------------------------
# 1  Medieval / Renaissance - D dorian, 88 BPM, 12 bars
# --------------------------------------------------------------------------------------
section(88)
prog(DR, 0, 48, vol=96, rev=60)                                        # Orchestra kit
prog(C1, 0, 74, vol=100, pan=54, rev=64)                              # Recorder
prog(C2, 0, 75, vol=92, pan=78, rev=64)                               # Pan Flute
prog(C3, 0, 24, vol=96, pan=40, rev=50)                               # Nylon (lute)
prog(C4, 0, 15, vol=90, pan=90, rev=55)                               # Dulcimer
prog(C5, 0, 42, vol=96, pan=52, rev=55)                               # Cello
prog(C6, 0, 19, vol=74, pan=64, rev=80)                               # Church Organ (drone)
prog(C9, 0, 46, vol=86, pan=96, rev=70)                               # Harp
prog(C7, 0, 48, vol=70, pan=70, rev=70, expr=40)                      # Strings (enter late)
D_CH = [("Dm", 50, [62, 65, 69]), ("C", 48, [60, 64, 67]), ("Dm", 50, [62, 65, 69]), ("Am", 45, [60, 64, 69]),
        ("F", 41, [60, 65, 69]), ("G", 43, [62, 67, 71]), ("Dm", 50, [62, 65, 69]), ("A", 45, [61, 64, 69]),
        ("Dm", 50, [62, 65, 69]), ("C", 48, [60, 64, 67]), ("Bb", 46, [62, 65, 70]), ("A", 45, [61, 64, 69])]
REC_TUNE = [
    [(0, 74, 1), (1, 76, 0.5), (1.5, 77, 0.5), (2, 79, 1), (3, 77, 1)],
    [(0, 76, 1.5), (1.5, 74, 0.5), (2, 72, 2)],
    [(0, 74, 0.5), (0.5, 76, 0.5), (1, 77, 1), (2, 81, 1), (3, 79, 0.5), (3.5, 77, 0.5)],
    [(0, 76, 3), (3, 72, 1)],
    [(0, 77, 1), (1, 79, 1), (2, 81, 1.5), (3.5, 79, 0.5)],
    [(0, 83, 1), (1, 81, 0.5), (1.5, 79, 0.5), (2, 81, 2)],
    [(0, 77, 0.5), (0.5, 76, 0.5), (1, 74, 1), (2, 76, 0.5), (2.5, 77, 0.5), (3, 79, 1)],
    [(0, 76, 4)],
    [(0, 81, 1), (1, 79, 0.5), (1.5, 77, 0.5), (2, 76, 1), (3, 74, 1)],
    [(0, 72, 0.5), (0.5, 74, 0.5), (1, 76, 1), (2, 79, 2)],
    [(0, 77, 1), (1, 74, 1), (2, 70, 1), (3, 72, 1)],
    [(0, 73, 2), (2, 76, 2)],
]
for k, (_nm, root, tri) in enumerate(D_CH):
    b = t(k)
    if k % 2 == 0:                                                     # organ drone, 2-bar holds
        chord(C6, b, [root - 12 if root > 47 else root, root + 7 - (12 if root > 47 else 0), tri[0]], 2 * BPB, 70)
    note(C5, b, root - 12 if root > 45 else root, 2, 80)               # cello: root / fifth halves
    note(C5, b + 2 * TPB, root - 5 if root > 45 else root + 7, 2, 72)
    for i in range(8):                                                 # lute: 8th arpeggio
        n = [root, tri[0], tri[1], tri[2], tri[1] + 12, tri[2], tri[1], tri[0]][i]
        note(C3, b + i * TPB // 2, n if n > 40 else n + 12, 0.5, 78 if i % 2 == 0 else 66, gate=1.6)
    if k >= 2:                                                          # dulcimer: rolled chords on 1 and 3
        chord(C4, b, [x + 12 for x in tri], 1.5, 76, roll=18)
        chord(C4, b + 2 * TPB, [x + 12 for x in tri][::-1], 1.5, 70, roll=18)
    line(C1, k, REC_TUNE[k], vel=98, gate=0.95)
    if k >= 4:                                                          # pan flute: a sixth / third below
        line(C2, k, [(bb, n - (8 if n % 12 in (2, 7, 9) else 9), d) for bb, n, d in REC_TUNE[k]], vel=86, gate=0.95)
    drum(b, TIMP_L, 82)                                                 # tabor + tambourine
    drum(b + int(1.5 * TPB), TIMP_L, 64)
    drum(b + 2 * TPB, TIMP_L, 74)
    for s in (1, 3):
        drum(b + s * TPB, TAMB, 60)
    if k % 4 == 3:
        chord(C9, b + 2 * TPB, [tri[0] + 12, tri[1] + 12, tri[2] + 12, tri[0] + 24, tri[1] + 24, tri[2] + 24], 2, 70, roll=40)
    if k >= 8:
        chord(C7, b, [tri[0] - 12, tri[1], tri[2]], BPB, 70)
ramp(C7, 11, t(8), t(12), 40, 110)
drum(t(11, 3), TRI, 70)
advance(12)

# --------------------------------------------------------------------------------------
# 2  Baroque -> Classical - A minor, 100 BPM, 16 bars. The organ drone from section 1 still
#    rings over bar 0 while every other part changes program (unheard PCs).
# --------------------------------------------------------------------------------------
section(100)
chord(C6, t(0), [45, 52, 57, 60], 1.6 * BPB, 66)                      # the drone carries over
ramp(C6, 11, t(0, 2), t(1, 2), 127, 0)
prog(C3, t(0) - 20, 6, vol=90, pan=44, rev=45)                        # Harpsichord
prog(C1, t(0) - 20, 40, vol=104, pan=58, rev=60)                      # Violin
prog(C2, t(0) - 20, 68, vol=90, pan=74, rev=55)                       # Oboe
prog(C4, t(0) - 20, 45, vol=92, pan=80, rev=50)                       # Pizzicato
prog(C5, t(0) - 20, 43, vol=96, pan=56, rev=50)                       # Contrabass
prog(C8, t(0) - 20, 60, vol=86, pan=36, rev=65)                       # French Horn
prog(C9, t(0) - 20, 47, vol=92, pan=64, rev=60)                       # Timpani
cc(C7, t(0), 11, 90)
A_CH = [(45, [57, 60, 64]), (38, [57, 62, 65]), (43, [59, 62, 67]), (36, [55, 60, 64]),
        (41, [57, 60, 65]), (38, [57, 62, 65]), (40, [56, 59, 64]), (45, [57, 60, 64]),
        (45, [57, 60, 64]), (38, [57, 62, 65]), (43, [59, 62, 67]), (36, [55, 60, 64]),
        (41, [57, 60, 65]), (47, [59, 62, 65]), (40, [56, 59, 64]), (40, [56, 59, 62, 64])]
VIOLIN_A = [
    [(0, 76, 2), (2, 72, 1), (3, 69, 1)], [(0, 74, 3), (3, 77, 1)], [(0, 79, 1.5), (1.5, 77, 0.5), (2, 74, 2)],
    [(0, 76, 4)], [(0, 77, 1), (1, 81, 1), (2, 84, 2)], [(0, 83, 1), (1, 81, 1), (2, 77, 2)],
    [(0, 76, 1), (1, 80, 1), (2, 83, 2)], [(0, 81, 4)],
]
for k, (root, tri) in enumerate(A_CH):
    b = t(k)
    for i in range(16):                                                 # harpsichord 16ths
        pat = [root + 12, tri[0], tri[1], tri[2]]
        note(C3, b + i * TPB // 4, pat[i % 4] + (12 if (i // 4) % 2 else 0), 0.25, 74 if i % 4 == 0 else 60, jitter=3)
    if k < 12:                                                          # pizzicato walking 8ths
        walk = [root, root + 7, root + 12, root + 7, root + 3 if k % 2 else root + 4, root + 7, root + 12, root + 10]
        for i, n in enumerate(walk):
            note(C4, b + i * TPB // 2, n + 12, 0.5, 80, gate=0.6)
    note(C5, b, root - 12 if root > 40 else root, 2, 86)
    note(C5, b + 2 * TPB, root - 5 if root > 40 else root + 7, 2, 78)
    chord(C7, b, [tri[0] - 12] + tri, BPB, 72)
    if k < 8:
        line(C1, k, VIOLIN_A[k], vel=100, gate=0.98)                    # slow tune (legato)
        if k >= 2:
            line(C2, k, [(bb, n - 3 if (n % 12) in (0, 5, 7) else n - 4, d) for bb, n, d in VIOLIN_A[k]], vel=84, gate=0.98)
    elif k < 12:                                                        # violin 16th runs (fast line)
        scale = [69, 71, 72, 74, 76, 77, 79, 81, 83, 84]
        run = [scale[(i + k) % len(scale)] + (12 if (i // 8) % 2 else 0) for i in range(16)]
        line(C1, k, seq(0, run, 0.25), vel=96, gate=0.85, jitter=2)
        line(C2, k, [(0, tri[2] + 12, 2), (2, tri[1] + 12, 2)], vel=80)
    if k in (4, 5, 6, 7, 12, 13, 14, 15):
        chord(C8, b, [tri[1], tri[2]], BPB, 82)
    if k % 2 == 0 and k < 12:
        note(C9, b, root + (12 if root < 41 else 0), 1, 94)
        note(C9, b + 3 * TPB, root + 7 + (0 if root + 7 < 53 else -12), 1, 80)
# bars 12-15: pizzicato becomes tremolo strings (program change on a silent channel)
prog(C4, t(12) - 30, 44, vol=96, pan=80, rev=60, expr=50)             # Tremolo Strings
for k in range(12, 16):
    root, tri = A_CH[k]
    chord(C4, t(k), [x + 12 for x in tri], BPB, 90)
    line(C1, k, [(0, tri[2] + 12, 2), (2, tri[1] + 12, 2)], vel=100)
ramp(C4, 11, t(12), t(16), 50, 127)
ramp(C7, 11, t(12), t(16), 90, 127)
for i in range(16):                                                     # timpani roll
    note(C9, t(14) + i * TPB // 2, 40, 0.5, 60 + i * 3, gate=0.5)
advance(16)

# --------------------------------------------------------------------------------------
# 3  Cathedral crescendo - A minor -> A major, 72 BPM, 8 bars; ends on an orchestra hit
# --------------------------------------------------------------------------------------
section(72)
prog(C11, t(0) - 20, 52, vol=100, pan=58, rev=90, expr=40)            # Choir Aahs
prog(C12, t(0) - 20, 53, vol=86, pan=72, rev=90, expr=40)             # Voice Oohs
prog(C13, t(0) - 20, 55, vol=110, pan=64, rev=70)                     # Orchestra Hit
cc(C6, t(0) - 20, 11, 40)
CATH = [(45, [57, 60, 64, 69]), (41, [57, 60, 65, 69]), (36, [55, 60, 64, 67]), (38, [57, 62, 65, 69]),
        (40, [56, 59, 64, 68]), (40, [56, 59, 62, 64])]
HORN = [[(0, 64, 2), (2, 69, 2)], [(0, 72, 3), (3, 71, 1)], [(0, 67, 2), (2, 72, 2)],
        [(0, 77, 3), (3, 76, 1)], [(0, 74, 2), (2, 71, 2)], [(0, 68, 4)]]
for k, (root, ch_) in enumerate(CATH):
    b = t(k)
    chord(C6, b, [root - 12, root] + ch_, BPB, 90)                      # pipe organ, full
    chord(C11, b, ch_, BPB, 92)
    chord(C12, b, [x + 12 for x in ch_[1:]], BPB, 80)
    chord(C7, b, [root] + ch_, BPB, 80)
    note(C5, b, root - 12 if root > 40 else root, BPB, 90)
    line(C8, k, HORN[k], vel=98, gate=0.98)
    line(C1, k, [(0, ch_[-1] + 12, BPB)], vel=90)
    note(C9, b, root if root > 40 else root + 12, 1, 70 + k * 5)
for c_ in (C6, C11, C12, C7):
    ramp(c_, 11, t(0), t(5), 40, 127)
for i in range(32):                                                     # timpani roll into the hit
    note(C9, t(5) + i * TPB // 8, 40, 0.125, 70 + i, gate=0.5, jitter=2)
hit = t(6)
chord(C13, hit, [57, 61, 64, 69], 1.5, 124)
chord(C6, hit, [33, 45, 57, 61, 64, 69], 1.5, 110)
chord(C11, hit, [61, 64, 69], 1.5, 110)
chord(C7, hit, [45, 57, 61, 64], 1.5, 110)
note(C5, hit, 33, 1.5, 110)
note(C9, hit, 45, 1, 120)
drum(hit, CRASH, 120)
drum(hit, 57, 110)
advance(6)
pos += int(1.5 * TPB) + TPB * 2                                          # the hit, then a full rest

# --------------------------------------------------------------------------------------
# 4  Big band swing - Bb, 160 BPM, 16 bars; the setup burst lands in the count-off
# --------------------------------------------------------------------------------------
section(160)
burst = pos - TPB * 2
prog(DR, burst, 32, vol=100, rev=35)                                   # Jazz kit
prog(C1, burst + 3, 56, vol=104, pan=60, rev=45)                       # Trumpet
prog(C8, burst + 6, 57, vol=96, pan=44, rev=45)                        # Trombone
prog(C2, burst + 9, 65, vol=94, pan=76, rev=40)                        # Alto Sax
prog(C7, burst + 12, 66, vol=94, pan=86, rev=40)                       # Tenor Sax
prog(C12, burst + 15, 67, vol=90, pan=30, rev=35)                      # Baritone Sax
prog(C5, burst + 18, 32, vol=104, pan=56, rev=30)                      # Acoustic Bass
prog(C4, burst + 21, 0, vol=92, pan=70, rev=40)                        # Piano
prog(C3, burst + 24, 26, vol=86, pan=36, rev=35)                       # Jazz Guitar
for i in range(4):
    drum(burst + i * TPB // 2, PHH, 70)                                 # count-off on the hats
BB = [(46, [55, 58, 62, 67]), (43, [53, 59, 62, 65]), (48, [55, 58, 62, 63]), (41, [51, 57, 60, 63]),
      (50, [53, 57, 60, 65]), (43, [53, 59, 62, 65]), (48, [55, 58, 62, 63]), (41, [51, 57, 60, 63]),
      (46, [56, 58, 62, 65]), (51, [55, 58, 61, 63]), (46, [55, 58, 62, 67]), (43, [55, 58, 62, 65]),
      (48, [55, 58, 62, 63]), (41, [51, 57, 60, 63]), (46, [55, 58, 62, 67]), (41, [51, 57, 60, 63])]
TPT = [[(0, 70, 1.5), (1.5, 74, 0.5), (2, 77, 1), (3, 74, 1)], [(0, 75, 2), (2.5, 74, 0.5), (3, 72, 1)],
       [(0, 70, 1), (1, 72, 1), (2, 74, 0.5), (2.5, 75, 1.5)], [(0, 77, 3)],
       [(0, 77, 1.5), (1.5, 81, 0.5), (2, 82, 1), (3, 81, 1)], [(0, 79, 2), (2.5, 77, 0.5), (3, 74, 1)],
       [(0, 75, 1), (1, 74, 1), (2, 72, 1), (3, 70, 1)], [(0, 72, 3)]]
for k, (root, v) in enumerate(BB):
    b = t(k)
    walk = [root, root + 4 if k % 3 else root + 3, root + 7, root + 9 if k % 2 else root + 5]
    for i, n in enumerate(walk):                                        # walking bass
        note(C5, b + i * TPB, n - (12 if n > 52 else 0), 1, 94 if i == 0 else 84, gate=0.85)
    for i in range(4):                                                  # Freddie Green quarters
        chord(C3, b + i * TPB, v[:3], 0.6, 70, gate=0.7)
    for bt in ((1.5, 3) if k % 2 == 0 else (0, 2.5)):                  # Charleston comping
        chord(C4, t(k, swing(bt)), [x + 12 for x in v], 0.4, 78, gate=0.7)
    for i in range(8):                                                  # ride, hats 2 & 4
        bt = i * 0.5
        if i % 2 == 0 or i in (3, 7):
            drum(t(k, swing(bt)), RIDE, 76 if i % 4 == 0 else 62)
    drum(t(k, 1), PHH, 70)
    drum(t(k, 3), PHH, 70)
    drum(b, KICK, 50)
    if k % 4 == 3:
        drum(t(k, swing(2.5)), SNARE, 80)
        drum(t(k, 3.5), SNARE, 70)
    if k < 8:                                                           # melody in trumpet, harmony in saxes/bone
        line(C1, k, [(swing(bb), n, d) for bb, n, d in TPT[k]], vel=102, gate=0.85)
        line(C8, k, [(swing(bb), n - 12 - (3 if n % 12 in (2, 7) else 4), d) for bb, n, d in TPT[k]], vel=88, gate=0.85)
        chord(C2, t(k, 0), [v[2] + 12], 2, 70)
        chord(C7, t(k, 0), [v[1] + 12], 2, 66)
        note(C12, b, root, 2, 76)
    elif k < 12:                                                        # sax soli: swung 8th line (fast featured)
        sc = [70, 72, 74, 75, 77, 79, 81, 82, 84]
        runs = [sc[(i * 2 + k) % len(sc)] - (0 if i < 4 else 2) for i in range(8)]
        line(C2, k, [(swing(i * 0.5), n, 0.5) for i, n in enumerate(runs)], vel=96, gate=0.8, jitter=3)
        line(C7, k, [(swing(i * 0.5), n - 4, 0.5) for i, n in enumerate(runs)], vel=86, gate=0.8, jitter=3)
        line(C12, k, [(swing(i * 0.5), n - 24, 0.5) for i, n in enumerate(runs)], vel=80, gate=0.8, jitter=3)
        chord(C1, t(k, 3), [v[3] + 12], 0.5, 90)
    else:                                                               # shout chorus: hits
        for bt in (0, 1.5, 3):
            chord(C1, t(k, swing(bt)), [v[3] + 12, v[3] + 24], 0.6, 110)
            chord(C8, t(k, swing(bt)), [v[0], v[1]], 0.6, 100)
            chord(C2, t(k, swing(bt)), [v[2] + 12], 0.6, 96)
            chord(C7, t(k, swing(bt)), [v[1] + 12], 0.6, 92)
            note(C12, t(k, swing(bt)), root, 0.6, 96)
            drum(t(k, swing(bt)), CRASH if bt == 0 else SNARE, 96)
advance(16)

# --------------------------------------------------------------------------------------
# 5  Proto-synth machine - C mixolydian, 144 BPM, 12 bars; the trombone crosses over
# --------------------------------------------------------------------------------------
section(144)
prog(DR, t(0) - 25, 0, vol=96, rev=30)                                 # Standard kit
prog(C1, t(0) - 25, 80, vol=100, pan=60, rev=45)                       # Square lead
prog(C2, t(0) - 25, 59, vol=92, pan=78, rev=40)                        # Muted Trumpet
prog(C4, t(0) - 25, 13, vol=96, pan=84, rev=45)                        # Xylophone
prog(C3, t(0) - 25, 8, vol=88, pan=40, rev=55)                         # Celesta
prog(C5, t(0) - 25, 38, vol=100, pan=64, rev=20)                       # Synth Bass 1
bend_range(C1, t(0) - 20, 2)
MACH = [72, 76, 79, 76, 70, 74, 77, 74, 72, 76, 79, 84, 82, 79, 76, 74]
SQ = [[(0, 84, 0.5), (0.5, 72, 0.5), (1, 79, 1), (2, 82, 0.5), (2.5, 81, 0.5), (3, 79, 1)],
      [(0, 76, 0.5), (0.5, 88, 0.5), (1, 84, 1), (2, 79, 2)],
      [(0, 82, 0.5), (0.5, 70, 0.5), (1, 77, 1), (2, 81, 0.5), (2.5, 79, 0.5), (3, 77, 1)],
      [(0, 76, 3)]]
for k in range(12):
    b = t(k)
    root = [36, 36, 34, 36, 41, 41, 36, 36, 34, 34, 43, 43][k]
    line(C4, k, seq(0, [n + (root - 36) for n in MACH], 0.25), vel=84, gate=0.7, jitter=2)
    for bt in (0.5, 1.5, 2.5, 3.5):
        note(C3, t(k, bt), 84 + (root - 36) + (7 if bt > 2 else 0), 0.25, 70, gate=0.8)
    for i in range(8):
        note(C5, b + i * TPB // 2, root + (12 if i % 2 else 0), 0.5, 88, gate=0.6)
    line(C1, k, SQ[k % 4], vel=96, octave=(root - 36))
    if k % 4 == 3:
        bend_curve(C1, t(k, 1), t(k, 3), 0, 8191)
        bend(C1, t(k + 1) - 10, 0)
    if k % 2 == 1:
        line(C2, k, [(2, 79 + root - 36, 0.5), (2.5, 76 + root - 36, 0.5), (3, 72 + root - 36, 1)], vel=88)
    if k < 6:                                                           # the trombone from the big band stays on
        chord(C8, b, [root + 12, root + 16], 0.5, 88, gate=0.7)
        chord(C8, t(k, 2.5), [root + 10, root + 14], 0.5, 80, gate=0.7)
    for bt in range(4):
        drum(t(k, bt), KICK if bt % 2 == 0 else SNARE, 90 if bt % 2 == 0 else 80)
        drum(t(k, bt + 0.5), WOODH if bt % 2 else WOODL, 70)
    drum(t(k, 3.75), CLAVES, 70)
advance(12)
# drums-only fill: the rock'n'roll setup burst lands here
section(168)
fill0 = pos
for i in range(8):
    drum(t(0, i * 0.5), [SNARE, SNARE, HTOM, HTOM, MTOM, MTOM, LTOM, LTOM][i], 90 + i * 3)
drum(t(0, 3.5), KICK, 100)
prog(C1, fill0 + 20, 66, vol=102, pan=58, rev=40)                      # Tenor Sax (honk)
prog(C2, fill0 + 23, 27, vol=92, pan=80, rev=40)                       # Clean Gt. (lead chorus)
prog(C3, fill0 + 26, 27, vol=90, pan=34, rev=35)                       # Clean Gt. (rhythm)
prog(C4, fill0 + 29, 3, vol=96, pan=66, rev=35)                        # Honky-tonk (boogie)
prog(C5, fill0 + 32, 32, vol=104, pan=56, rev=25)                      # Acoustic Bass (slap)
prog(C12, fill0 + 35, 67, vol=88, pan=28, rev=30)                      # Baritone Sax
advance(1)

# --------------------------------------------------------------------------------------
# 6  Rock'n'roll - A, 168 BPM, two 12-bar choruses
# --------------------------------------------------------------------------------------
BLUES = [45, 45, 45, 45, 50, 50, 45, 45, 52, 50, 45, 52]
for k in range(24):
    b = t(k)
    r = BLUES[k % 12]
    boog = [r, r + 4, r + 7, r + 9, r + 10, r + 9, r + 7, r + 4]
    for i, n in enumerate(boog):                                         # boogie left hand
        note(C4, b + i * TPB // 2, n - 12, 0.5, 84 if i % 2 == 0 else 72, gate=0.8)
        note(C5, b + i * TPB // 2, n - 24 if n - 24 >= 28 else n - 12, 0.5, 90 if i % 2 == 0 else 76, gate=0.6)
    for bt in (0.5, 1.5, 2.5, 3.5):                                     # right-hand stabs
        chord(C4, t(k, bt), [r + 16, r + 19, r + 22], 0.25, 76, gate=0.7)
    for i in range(8):                                                   # twang rhythm double stops
        chord(C3, b + i * TPB // 2, [r + 12, r + 19 + (2 if i % 4 in (2, 3) else 0)], 0.5, 80, gate=0.55)
    for bt in range(4):
        drum(t(k, bt), KICK if bt % 2 == 0 else SNARE, 96 if bt % 2 == 0 else 90)
        drum(t(k, bt), CHH, 70)
        drum(t(k, bt + 0.5), CHH, 60)
    if k < 12:                                                          # sax riff, bari underneath
        if k % 2 == 0:
            line(C1, k, [(0, r + 24, 1), (1.5, r + 27, 0.5), (2, r + 28, 1), (3, r + 31, 0.75)], vel=106)
        else:
            line(C1, k, [(0.5, r + 31, 0.5), (1, r + 28, 1), (2, r + 24, 1.5)], vel=100)
        note(C12, t(k, 0), r - 12 + 24, 1, 86)
        note(C12, t(k, 2), r - 12 + 24 + 7, 1, 80)
    else:                                                               # guitar lead chorus
        solo = [r + 24, r + 27, r + 28, r + 31, r + 33, r + 31, r + 28, r + 27]
        if k % 4 == 3:
            line(C2, k, [(0, r + 36, 2), (2, r + 33, 2)], vel=104)        # held notes: the wah opens
            bend_curve(C2, t(k, 0.2), t(k, 1), 0, 4096, 8)
            bend(C2, t(k, 1.9), 0)
        else:
            line(C2, k, seq(0, solo, 0.5), vel=100, gate=0.8, jitter=3)
        if k % 2 == 1:
            line(C1, k, [(3, r + 16, 1)], vel=92)                        # sax honk answers
    if k in (11, 23):
        drum(t(k, 3), CRASH, 100)
advance(24)

# --------------------------------------------------------------------------------------
# 7  Analog synths - E minor, 120 BPM, 16 bars; the sax holds and fades while synths fade in
# --------------------------------------------------------------------------------------
section(120)
note(C1, t(0) - TPB * 2, 64 + 12, 6, 98, gate=1.0)                     # the sax holds over the seam
ramp(C1, 7, t(0) - TPB, t(1), 102, 0)
prog(DR, t(0) - 30, 25, vol=100, rev=30)                               # TR-808
prog(C3, t(0) - 30, 81, vol=86, pan=40, rev=45, expr=20)               # Saw (arpeggio)
prog(C5, t(0) - 30, 39, vol=104, pan=64, rev=15, expr=20)              # Synth Bass 2
prog(C6, t(0) - 30, 90, vol=84, pan=64, rev=70, expr=20)               # Polysynth pad
prog(C8, t(0) - 30, 62, vol=92, pan=80, rev=45)                        # Synth Brass 1
prog(C4, t(0) - 30, 80, vol=0, pan=64)                                 # (square, silent until 8)
ramp(C3, 11, t(0), t(2), 20, 120)
ramp(C5, 11, t(0), t(2), 20, 127)
ramp(C6, 11, t(0), t(4), 20, 110)
prog(C1, t(1) + 30, 81, vol=100, pan=58, rev=50)                       # Saw lead (after the sax)
bend_range(C1, t(1) + 40, 2)
EM = [(40, [64, 67, 71]), (36, [64, 67, 72]), (38, [62, 66, 69]), (35, [62, 66, 71]),
      (40, [64, 67, 71]), (36, [64, 67, 72]), (33, [60, 64, 69]), (35, [63, 66, 71])][:4] + \
     [(40, [64, 67, 71]), (36, [64, 67, 72]), (33, [60, 64, 69]), (35, [63, 66, 71])]
LEAD7 = [[(0, 76, 1.5), (1.5, 79, 0.5), (2, 83, 2)], [(0, 84, 1), (1, 83, 1), (2, 79, 2)],
         [(0, 78, 1.5), (1.5, 81, 0.5), (2, 86, 2)], [(0, 83, 4)]]
for k, (root, tri) in enumerate(EM):
    b = t(k)
    if k < 8:                                                           # saw arpeggio: short 16ths
        arp = [tri[0], tri[1], tri[2], tri[0] + 12]
        for i in range(16):
            note(C3, b + i * TPB // 4, arp[i % 4] + (12 if (i // 4) % 2 else 0), 0.25, 80 if i % 4 == 0 else 66, gate=0.45, jitter=1)
    else:                                                               # ... then held chords (a stab tone would fall back)
        chord(C3, b, tri, 1.8, 84)
        chord(C3, t(k, 2), [x + 12 for x in tri], 1.8, 80)
    for i in range(16):                                                 # sequenced bass
        note(C5, b + i * TPB // 4, root + (12 if i % 4 == 2 else 0), 0.25, 92 if i % 4 == 0 else 74, gate=0.5, jitter=1)
    chord(C6, b, [tri[0] - 12] + tri, BPB, 80)
    if 2 <= k:
        line(C1, k, LEAD7[k % 4], vel=100, gate=0.97)
        if k % 4 == 3:
            bend_curve(C1, t(k, 0.5), t(k, 1.5), 0, 4096, 8)             # bend up a tone and hold
            bend_curve(C1, t(k, 3), t(k, 3.8), 4096, 0, 6)
    if k >= 6:
        for bt in (0, 1.5, 3):
            chord(C8, t(k, bt), [tri[0] + 12, tri[1] + 12, tri[2] + 12], 0.4, 96, gate=0.7)
    for bt in range(4):                                                 # 808
        drum(t(k, bt), KICK if bt in (0, 2) else CLAP, 100 if bt in (0, 2) else 90)
        drum(t(k, bt + 0.5), CHH, 70)
    drum(t(k, 3.75), KICK, 80)
advance(12)

# --------------------------------------------------------------------------------------
# 8  Prog / hard rock - A minor, 132 BPM (7/8 passage); the pad holds while the organ swells in
# --------------------------------------------------------------------------------------
section(132)
chord(C6, t(0), [52, 55, 59, 64], 2 * BPB, 80)                         # the pad holds over the seam
ramp(C6, 11, t(0), t(2), 110, 0)
prog(DR, t(0) - 30, 16, vol=104, rev=35)                               # Power kit
prog(C4, t(0) - 30, 16, vol=100, pan=58, rev=40, expr=50)              # Drawbar Organ
prog(C3, t(0) - 30, 29, vol=96, pan=36, rev=30)                        # Overdrive Gt.
prog(C5, t(0) - 30, 33, vol=104, pan=60, rev=20)                       # Fingered Bass
ramp(C4, 11, t(0), t(1, 2), 50, 127)
# bars 0-3: organ holds big chords (rotary flips), guitar and bass enter at bar 2
HOLD = [(45, [57, 60, 64, 69]), (41, [57, 60, 65, 69]), (43, [59, 62, 67, 71]), (40, [56, 59, 64, 68])]
for k, (root, ch_) in enumerate(HOLD):
    chord(C4, t(k), ch_, BPB, 96)
    note(C4, t(k), root + 12, BPB, 90)
    if k >= 2:
        note(C5, t(k), root - 12 if root > 40 else root, BPB, 96)
        chord(C3, t(k), [root, root + 7, root + 12], BPB, 100)
        drum(t(k), CRASH, 100)
        for bt in range(4):
            drum(t(k, bt), KICK if bt % 2 == 0 else SNARE, 104)
advance(4)
# bars 0-7: unison riff (organ + guitar + bass), 8ths
RIFF = [45, 45, 57, 45, 55, 45, 53, 52, 45, 45, 57, 45, 60, 59, 55, 52]
for k in range(4):
    tr = [0, 5, 7, 0][k]
    for i in range(8):
        n = RIFF[(k % 2) * 8 + i] + tr
        note(C3, t(k, i * 0.5), n, 0.5, 100, gate=0.8)
        note(C3, t(k, i * 0.5), n + 7, 0.5, 92, gate=0.8)
        note(C4, t(k, i * 0.5), n + 12, 0.5, 94, gate=0.85)
        note(C5, t(k, i * 0.5), n - 12, 0.5, 100, gate=0.8)
    for bt in range(4):
        drum(t(k, bt), KICK, 106)
        drum(t(k, bt + 0.5), KICK if bt % 2 else CHH, 90)
        if bt % 2:
            drum(t(k, bt), SNARE, 110)
        drum(t(k, bt), RIDE, 72)
advance(4)
# 7/8 passage: 4 bars of 3+2+2 eighths
section(132, beats=3.5, den=8)
for k in range(4):
    r = [45, 45, 43, 41][k]
    for i, (bt, acc) in enumerate(((0, 1), (0.5, 0), (1, 0), (1.5, 1), (2, 0), (2.5, 1), (3, 0))):
        n = r + (12 if i in (3, 5) else 0)
        note(C3, t(k, bt), n, 0.5, 104 if acc else 90, gate=0.75)
        note(C4, t(k, bt), n + 12, 0.5, 100 if acc else 86, gate=0.75)
        note(C5, t(k, bt), n - 12, 0.5, 104, gate=0.75)
        if acc:
            drum(t(k, bt), KICK, 110)
            drum(t(k, bt), CRASH if (k == 0 and i == 0) else CHINA if i == 5 else RIDE, 100)
        else:
            drum(t(k, bt), CHH, 80)
    drum(t(k, 1.5), SNARE, 110)
    drum(t(k, 2.5), SNARE, 110)
advance(4)
# organ solo: fast 16th runs (featured fast line) over power chords; saw lead answers
section(132)
prog(C1, t(0) - 30, 81, vol=98, pan=70, rev=50)                        # Saw lead ("Moog")
bend_range(C1, t(0) - 25, 2)
AMIN = [57, 59, 60, 62, 64, 65, 67, 69, 71, 72, 74, 76, 77, 79, 81]
for k in range(8):
    root, ch_ = [(45, [57, 60, 64]), (41, [57, 60, 65]), (43, [59, 62, 67]), (40, [56, 59, 64])][k % 4]
    run = [AMIN[(i + 3 * k) % len(AMIN)] + (12 if (i // 8) % 2 else 0) for i in range(16)]
    if k % 4 == 3:
        run = [AMIN[len(AMIN) - 1 - (i % len(AMIN))] + 12 for i in range(16)]
    if k < 6:
        line(C4, k, seq(0, run, 0.25), vel=100, gate=0.8, jitter=2)
    else:
        chord(C4, t(k), [x + 12 for x in ch_], BPB, 104)                 # held: rotary flips again
    chord(C3, t(k), [root, root + 7, root + 12], 1.9, 100)
    chord(C3, t(k, 2), [root, root + 7, root + 12], 1.9, 96)
    note(C5, t(k), root - 12 if root > 40 else root, 2, 100)
    note(C5, t(k, 2), root - 12 if root > 40 else root, 2, 96)
    if k % 2 == 1:
        line(C1, k, [(2, ch_[2] + 12, 1), (3, ch_[1] + 12, 1)], vel=100)
        bend_curve(C1, t(k, 2), t(k, 2.5), -2048, 0, 6)
    for bt in range(4):
        drum(t(k, bt), KICK if bt % 2 == 0 else SNARE, 106)
        drum(t(k, bt), RIDE, 70)
advance(8)
# the held power chord, fading (drive level follows the CC7 fade), organ swell under it
chord(C3, t(0), [40, 47, 52], 2 * BPB, 110, gate=1.0)
note(C5, t(0), 28, 2 * BPB, 104, gate=1.0)
chord(C4, t(0), [52, 59, 64, 71], 2 * BPB, 90, gate=1.0)
drum(t(0), CRASH, 116)
drum(t(0), KICK, 116)
ramp(C3, 7, t(0, 1), t(2), 96, 0)
ramp(C4, 7, t(0, 1), t(2), 100, 0)
ramp(C5, 7, t(0, 1), t(2), 104, 0)
advance(2)

# --------------------------------------------------------------------------------------
# 9  Metal - E minor: NWOBHM gallop (176), groove + solo (100), epic doom finale (72)
# --------------------------------------------------------------------------------------
section(176)
prog(DR, t(0) - 60, 16, vol=110, rev=30)                               # Power kit
prog(C3, t(0) - 60, 30, vol=100, pan=0, rev=25)                        # Distortion L
prog(C4, t(0) - 57, 30, vol=100, pan=127, rev=25)                      # Distortion R
prog(C5, t(0) - 54, 34, vol=108, pan=64, rev=15)                       # Picked Bass
prog(C1, t(0) - 51, 30, vol=104, pan=64, rev=45)                       # Lead guitar
prog(C2, t(0) - 48, 30, vol=96, pan=74, rev=45)                        # Twin lead
bend_range(C1, t(0) - 45, 12)
bend_range(C2, t(0) - 45, 2)
for c_ in (C3, C4, C5):
    cc(c_, t(0) - 40, 7, 100 if c_ != C5 else 108)
for i in range(4):
    drum(t(0) - TPB * 4 + i * TPB, CHH, 90)                              # sticks
GAL = [40, 40, 40, 40, 43, 43, 45, 47, 40, 40, 40, 40, 38, 38, 36, 35]
TWIN = [[(0, 71, 1), (1, 74, 1), (2, 76, 1.5), (3.5, 74, 0.5)], [(0, 72, 1), (1, 71, 1), (2, 69, 2)],
        [(0, 67, 1), (1, 71, 1), (2, 74, 1.5), (3.5, 72, 0.5)], [(0, 71, 3), (3, 67, 1)]]
for k in range(16):
    r = GAL[k]
    for bt in range(4):                                                 # gallop: 8th + two 16ths
        for off, vel in ((0, 110), (0.5, 96), (0.75, 98)):
            for c_ in (C3, C4):
                chord(c_, t(k, bt + off), [r, r + 7], 0.25 if off else 0.5, vel, gate=0.7)
            note(C5, t(k, bt + off), r - 12 if r - 12 >= 28 else r, 0.25 if off else 0.5, vel, gate=0.7)
            drum(t(k, bt + off), KICK, 100)
        drum(t(k, bt), SNARE if bt % 2 else CHH, 112 if bt % 2 else 84)
        drum(t(k, bt), CRASH if (bt == 0 and k % 4 == 0) else RIDE, 96 if bt == 0 else 76)
    if k >= 8:                                                           # twin harmony lead
        line(C1, k, TWIN[k % 4], vel=106, gate=0.95)
        line(C2, k, [(bb, n - (3 if n % 12 in (2, 7, 11) else 4), d) for bb, n, d in TWIN[k % 4]], vel=98, gate=0.95)
advance(16)
# groove + solo, 100 BPM half-time feel
section(100)
GROOVE = [(0, 28, 0.75), (0.75, 28, 0.25), (1, 31, 0.5), (1.5, 28, 0.25), (2, 34, 0.5), (2.5, 33, 0.25),
          (2.75, 28, 0.5), (3.5, 38, 0.5)]
for k in range(8):
    for bb, n, d in GROOVE:
        for c_ in (C3, C4):
            chord(c_, t(k, bb), [n + 12, n + 19], d, 112, gate=0.8)
        note(C5, t(k, bb), n, d, 112, gate=0.8)
    drum(t(k, 0), KICK, 120)
    drum(t(k, 0.75), KICK, 110)
    drum(t(k, 2), SNARE, 122)
    drum(t(k, 2.75), KICK, 110)
    for i in range(8):
        drum(t(k, i * 0.5), CHH if i % 4 else CHINA, 86)
    # the solo
    if k in (0, 1):
        line(C1, k, [(0, 76, 1.5), (1.5, 79, 0.5), (2, 81, 2)], vel=110)
        bend_curve(C1, t(k, 2.2), t(k, 3), 0, 1365, 6)                   # one-tone bend (range 12)
        for i in range(8):
            bend(C1, t(k, 3) + i * TPB // 8, 1365 + (200 if i % 2 else -200))
        bend(C1, t(k, 3.95), 0)
    elif k in (2, 3):                                                   # runs
        sc = [64, 67, 69, 71, 74, 76, 79, 81, 83, 86, 88]
        line(C1, k, seq(0, [sc[(i + k) % len(sc)] + (12 if i > 11 else 0) for i in range(16)], 0.25), vel=104, gate=0.8, jitter=2)
    elif k in (4, 5):                                                   # two-hand tapping triplets
        tap = [88, 83, 79, 88, 83, 79, 86, 81, 78, 86, 81, 78]
        line(C1, k, seq(0, tap, 1 / 3), vel=100, gate=0.8, jitter=2)
    elif k == 6:
        line(C1, k, [(0, 88, 4)], vel=112)                              # dive bomb
        bend_curve(C1, t(k, 0.5), t(k, 3.5), 0, -8192, 24)
        bend(C1, t(k + 1) - 5, 0)
    else:
        line(C1, k, [(0, 76, 1), (1, 79, 1), (2, 76, 2)], vel=104)
advance(8)
# epic doom finale, 72 BPM: pipe organ + choir return, last dive, fade
section(72)
prog(C6, t(0) - 30, 19, vol=100, pan=64, rev=90, expr=40)              # Church Organ
prog(C11, t(0) - 30, 52, vol=100, pan=58, rev=90, expr=40)             # Choir Aahs
DOOM = [(40, [64, 67, 71]), (36, [64, 67, 72]), (38, [62, 66, 69]), (35, [63, 66, 71]),
        (36, [64, 67, 72]), (35, [63, 66, 71])]
for k, (root, tri) in enumerate(DOOM):
    b = t(k)
    for c_ in (C3, C4):
        chord(c_, b, [root, root + 7, root + 12], 2, 114, gate=0.97)
        chord(c_, t(k, 2), [root, root + 7, root + 12], 1.5, 108, gate=0.9)
        chord(c_, t(k, 3.5), [root + 3, root + 10], 0.5, 100, gate=0.9)
    note(C5, b, root - 12 if root - 12 >= 28 else root, 3.5, 112)
    chord(C6, b, [root, root + 12] + tri, BPB, 96)
    chord(C11, b, tri, BPB, 96)
    line(C1, k, [(0, tri[2] + 12, 2), (2, tri[1] + 12, 2)], vel=104)
    drum(b, CRASH if k % 2 == 0 else CHINA, 110)
    drum(b, KICK, 120)
    drum(t(k, 2), SNARE, 120)
    drum(t(k, 3), KICK, 110)
    drum(t(k, 3.5), KICK, 100)
for c_ in (C6, C11):
    ramp(c_, 11, t(0), t(5), 40, 127)
advance(6)
end = t(0)
for c_ in (C3, C4):
    chord(c_, end, [40, 47, 52], 3 * BPB, 118, gate=1.0)
note(C5, end, 28, 3 * BPB, 116, gate=1.0)
chord(C6, end, [28, 40, 52, 59, 64, 67, 71], 3 * BPB, 110, gate=1.0)
chord(C11, end, [64, 67, 71, 76], 3 * BPB, 108, gate=1.0)
note(C1, end, 76, 3 * BPB, 112, gate=1.0)
bend_curve(C1, t(0, 2), t(2), 0, -8192, 32)                             # the last dive
drum(end, CRASH, 124)
drum(end, 57, 118)
drum(end, KICK, 124)
for c_ in (C1, C3, C4, C5, C6, C11):
    ramp(c_, 7, t(1, 2), t(3), 110, 0)
end_tick = t(3) + TPB * 2

# --------------------------------------------------------------------------------------
# write
# --------------------------------------------------------------------------------------
meta = [(tk, 0, mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm))) for tk, bpm in tempos]
meta += [(tk, 0, mido.MetaMessage("time_signature", numerator=n, denominator=d)) for tk, n, d in sigs]
allev = sorted(meta + events, key=lambda e: (e[0], e[1]))
mf = mido.MidiFile(ticks_per_beat=TPB)
tr = mido.MidiTrack()
mf.tracks.append(tr)
tr.append(mido.MetaMessage("track_name", name="ONESTOP2 - A Brief History of Sound", time=0))
tr.append(mido.Message("sysex", data=[0x41, 0x10, 0x42, 0x12, 0x40, 0x00, 0x7F, 0x00, 0x41], time=0))
last = 0
for tk, _o, m in allev:
    tk += TPB                     # one beat after the GS reset
    tr.append(m.copy(time=max(0, tk - last)))
    last = max(last, tk)
tr.append(mido.MetaMessage("end_of_track", time=max(0, end_tick + TPB - last)))
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                            "midi", "onestop2.mid")
os.makedirs(os.path.dirname(out), exist_ok=True)
mf.save(out)
n_on = sum(1 for m in tr if m.type == "note_on" and m.velocity)
print(f"{out}: {mf.length:.1f} s ({int(mf.length // 60)}:{int(mf.length % 60):02d}), {n_on} notes, "
      f"{sum(1 for m in tr if m.type == 'program_change')} program changes")
