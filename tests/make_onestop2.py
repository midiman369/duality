"""Write "ONESTOP2 - A Brief History of Sound", an ~8 minute showcase for Duality + Anima.

    python tests/make_onestop2.py [out.mid]      (default tests/midi/onestop2.mid)

Original composition (no copyright issue; generated, so it can be rebuilt anywhere). It plays
complete on a single SC-8850 (GM capitals, GS drum sets, one GS reset at the start, no file
insert EFX; channel 16 is left free for Anima's foley) and is laid out for Duality with six GS
units: every section change is a program change burst (Anima places inserts once per burst;
game mode rerolls per cue) and each seam is built to exercise an EFX rule.

Every pitched part is written in scale degrees of its section's key (a key + chord per bar),
so written harmony stays in key by construction; Anima's harmony adds on top. The build fails
if a note leaves its section's allowed pitch classes (the scale plus the few chromatic notes a
style calls for, listed per section), if nothing sounds for longer than 1.5 s outside the one
intended rest, or if a program change lands on a channel that is still holding a note.

   1 Medieval               D dorian     88   recorder / pan flute counterpoint, fingerpicked lute
                                              (runs, turns, hammer-ons, strums), dulcimer,
                                              cello, organ drone, harp, bells; a full reprise with
                                              bagpipe drone
     -> the organ drone rings on while every other part changes program
   2 Baroque -> Classical   A minor     100   harpsichord, violin tune, runs, violin + oboe duet
                                              with flute, pizzicato walk into tremolo strings
   3 Cathedral              A min->maj   72   organ-led crescendo (pedal, manuals building),
                                              choir, brass section, horn tune, orchestra hit
     -> a full rest; the big-band burst lands in the count-off
   4 Big band swing         Bb          160   head, sax soli, trumpet solo over sax backgrounds,
                                              shout chorus with the brass section
   5 Boogie -> rock'n'roll  A blues  150/168  solo boogie piano (bass and drums join), then an
                                              overdrive guitar intro lick, sax chorus, overdrive
                                              lead chorus, stop-time piano chorus, a stop
   6 Proto-synth machine    A mixolyd.  132   calliope synth picks up the lick; square lead, synth brass
                                              answers, Fantasia pad, celesta, synth bass, woodblocks
     -> same tempo: the analog sequence fades in under the machine on shared chords
   7 Analog synths          E minor     132   saw sequence, poly + halo pads, synth strings, synth
                                              brass fanfares, bending lead; the organ takes over
   8 Prog / hard rock       A minor     132   rotary crescendo (held organ chords, two bars each,
                                              swelling), twin-guitar riff, 7/8, organ vs Moog,
                                              a second rotary crescendo, slowing into ...
   9 Metal                  E minor           Dio-style epic (96) with arpeggio guitar and pads;
                                              power groove (96): stop-start chugs, squeals;
                                              screaming solo (100): long high notes, bends, vibrato;
                                              NWOBHM gallop (176): twin leads, a flowing solo;
                                              Priest-style ending: anthem over organ + choir (72),
                                              a closing charge (184), final chord
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
allow = []           # (tick0, pitch classes, extra pcs, name)
rests = []           # (tick0, tick1) intended silences

C1, C2, C3, C4, C5, C6, C7, C8, C9, DR, C11, C12, C13, C14, C15, C16 = range(16)
TONE, SEMI = 1365, 683          # pitch-bend steps with a 12-semitone range
TONE2 = 8191                    # a tone with a 2-semitone range

MODES = {
    "major": [0, 2, 4, 5, 7, 9, 11], "dorian": [0, 2, 3, 5, 7, 9, 10], "minor": [0, 2, 3, 5, 7, 8, 10],
    "harm": [0, 2, 3, 5, 7, 8, 11], "mixo": [0, 2, 4, 5, 7, 9, 10],
}


class Key:
    """Scale degrees -> MIDI notes. Degree 0 = tonic at `tonic`; 7 = an octave up."""

    def __init__(self, tonic, mode):
        self.tonic, self.mode, self.m = tonic, mode, MODES[mode]

    def __call__(self, d):
        o, i = divmod(int(d), 7)
        return self.tonic + 12 * o + self.m[i]

    def tri(self, d, add=()):
        return [self(d), self(d + 2), self(d + 4)] + [self(d + a) for a in add]

    def pcs(self):
        return {(self.tonic + x) % 12 for x in self.m}


# --------------------------------------------------------------------------------------
# timeline helpers
# --------------------------------------------------------------------------------------
pos = TPB * 2
BPB = 4.0


def section(bpm, beats=4.0, den=4, key=None, extra=(), name=""):
    global BPB
    BPB = beats
    tempos.append((pos, bpm))
    sigs.append((pos, int(round(beats * den / 4)), den))
    if key is not None:
        allow.append((pos, key.pcs() if isinstance(key, Key) else set(key), set(extra), name))


def tempo_at(tick, bpm):
    tempos.append((tick, bpm))


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


def vib(ch, t0, t1, base=0, depth=220, step=TPB // 10):
    """Finger vibrato around `base` (the bend a note sits at), ending back on it."""
    k, tk = 0, t0
    while tk < t1:
        bend(ch, tk, base + (depth if k % 2 else -depth) * min(1.0, (tk - t0) / max(1, (t1 - t0) / 3)))
        tk += step
        k += 1
    bend(ch, t1, base)


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


def mel(ch, bar, key, spec, vel=96, shift=0, gate=0.92, jitter=5, oct_=0):
    """spec rows: (beat, degree or None, beats). shift moves every degree (diatonic harmony)."""
    for b, d, ln in spec:
        if d is not None:
            note(ch, t(bar, b), key(d + shift) + 12 * oct_, ln, vel + (6 if abs(b % 1) < 1e-6 else 0), jitter=jitter, gate=gate)


def drum(tick, n, vel, jitter=4):
    note(DR, tick, n, 0.25, vel, jitter=jitter, gate=0.5)


def swing(beat):
    whole, frac = divmod(beat, 1.0)
    return whole + (2 / 3 if abs(frac - 0.5) < 1e-6 else frac)


KICK, SIDE, SNARE, CLAP, SNARE2, LTOM, CHH, LTOM2, PHH, MTOM, OHH, MTOM2, HTOM, CRASH, RIDE, CHINA = \
    36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 50, 49, 51, 52
RBELL, TAMB, SPLASH, CRASH2, TRI, CLAVES, WOODH, WOODL, SHAKER = 53, 54, 55, 57, 81, 75, 76, 77, 82
TOMS = [HTOM, MTOM2, MTOM, LTOM2, LTOM]


def fill(bar, beat0, kind, vel=100):
    """Tom / snare fills from beat0 to the bar's end; kind picks the shape."""
    n = int(round((BPB - beat0) * 4))
    for i in range(n):
        bt = beat0 + i * 0.25
        if kind == "down":
            drum(t(bar, bt), TOMS[min(4, i * 5 // max(1, n))], vel + i)
        elif kind == "snare":
            drum(t(bar, bt), SNARE, vel - 10 + i * 2)
        elif kind == "triplet" and i % 4 != 3:
            drum(t(bar, beat0 + (i // 4) + (i % 4) / 3), TOMS[(i // 2) % 5], vel)
        elif kind == "kicks":
            drum(t(bar, bt), KICK, vel)
            if i % 2:
                drum(t(bar, bt), TOMS[i % 5], vel - 6)
        elif kind == "flams":
            if i % 2 == 0:
                drum(t(bar, bt), SNARE, vel)
                drum(t(bar, bt) + 20, TOMS[(i // 2) % 5], vel - 10)


def power(key, d):
    """Root + fifth + octave power chord on degree d (fifth = +7 semitones)."""
    r = key(d)
    return [r, r + 7, r + 12]


# ======================================================================================
# 1  Medieval - D dorian, 88 BPM, 16 bars (12 + a full reprise)
# ======================================================================================
KD = Key(62, "dorian")
section(88, key=KD, name="medieval")
prog(DR, 0, 48, vol=96, rev=60)                                        # Orchestra kit
prog(C1, 0, 74, vol=100, pan=54, rev=64)                              # Recorder
prog(C2, 0, 75, vol=94, pan=78, rev=64)                               # Pan Flute
prog(C3, 0, 24, vol=118, pan=40, rev=50)                              # Nylon (lute)
prog(C4, 0, 15, vol=90, pan=90, rev=55)                               # Dulcimer
prog(C5, 0, 42, vol=96, pan=52, rev=55)                               # Cello
prog(C6, 0, 19, vol=80, pan=64, rev=80)                               # Church Organ (drone)
prog(C9, 0, 46, vol=86, pan=96, rev=70)                               # Harp
prog(C7, 0, 48, vol=76, pan=70, rev=70, expr=40)                      # Strings
prog(C13, 0, 14, vol=80, pan=30, rev=90)                              # Tubular Bells
prog(C14, 0, 109, vol=70, pan=20, rev=60)                             # Bagpipe (reprise drone)
ROOTS1 = [0, -1, 0, 4, 2, 3, 0, 4, 0, -1, 3, 4, 0, -1, 2, 4]
REC1 = [
    [(0, 7, 1), (1, 8, .5), (1.5, 9, .5), (2, 11, 1), (3, 9, 1)],
    [(0, 8, 1.5), (1.5, 7, .5), (2, 6, 2)],
    [(0, 7, .5), (.5, 8, .5), (1, 9, 1), (2, 11, 1), (3, 10, .5), (3.5, 9, .5)],
    [(0, 8, 3), (3, 6, 1)],
    [(0, 9, 1), (1, 10, 1), (2, 11, 1.5), (3.5, 10, .5)],
    [(0, 12, 1), (1, 11, .5), (1.5, 10, .5), (2, 11, 2)],
    [(0, 9, .5), (.5, 8, .5), (1, 7, 1), (2, 8, .5), (2.5, 9, .5), (3, 10, 1)],
    [(0, 8, 4)],
    [(0, 11, 1), (1, 10, .5), (1.5, 9, .5), (2, 8, 1), (3, 7, 1)],
    [(0, 6, .5), (.5, 7, .5), (1, 8, 1), (2, 10, 2)],
    [(0, 10, 1), (1, 12, 1), (2, 11, 1), (3, 10, 1)],
    [(0, 8, 2), (2, 11, 2)],
    # reprise: the opening tune an octave up, a new cadence
    [(0, 14, 1), (1, 15, .5), (1.5, 16, .5), (2, 18, 1), (3, 16, 1)],
    [(0, 15, 1.5), (1.5, 14, .5), (2, 13, 2)],
    [(0, 16, .5), (.5, 15, .5), (1, 14, 1), (2, 13, .5), (2.5, 14, .5), (3, 16, 1)],
    [(0, 15, 4)],
]
FLUTE1 = {k: [(b, d - (5 if ln >= 2 else 2), ln) for b, d, ln in REC1[k]] for k in range(4, 16)}
# The lute (nylon guitar): fingerpicked sixteenths, the thumb on the beat (root / fifth, an octave
# under the chord), fingers above; scale runs close each phrase, a triplet turn now and then,
# hammer-ons, and strummed chords in the reprise. Degrees count up from the chord root, low octave.
LUTE_FING = [[9, 11, 9], [7, 9, 11], [11, 9, 7], [9, 14, 11], [7, 11, 9], [11, 14, 9]]
LUTE_RUN_UP = [0, 1, 2, 3, 4, 5, 6, 7]
LUTE_RUN_DN = [11, 10, 9, 8, 7, 6, 5, 4]
LUTE_TURN = [9, 10, 9, 8, 9, 11]                                          # six to a beat


def lute(k, r):
    b = t(k)
    big = k >= 12
    run = None
    if k in (3, 11):
        run = LUTE_RUN_UP
    elif k in (7, 14):
        run = LUTE_RUN_DN
    for st in range(16):
        tk = b + st * TPB // 4
        if run is not None and st >= 8:                                  # the run takes beats 3-4
            d = run[st - 8]
            note(C3, tk, KD(r - 7 + d), 0.25, 82 + (st - 8) * 2, gate=0.95, jitter=3)
            continue
        if k in (5, 9) and st >= 12:                                     # a triplet turn on beat 4
            if st == 12:
                for i, d in enumerate(LUTE_TURN):
                    note(C3, b + 3 * TPB + i * TPB // 6, KD(r - 7 + d), 1 / 6, 84 - (i % 3) * 3, gate=1.0, jitter=2)
            continue
        if st % 4 == 0:
            if big and st in (0, 8):                                      # strum on beats 1 and 3
                chord(C3, tk, [KD(r - 7 + d) for d in (0, 4, 7, 9, 11)], 1.0, 96, roll=12, gate=0.9)
            else:
                note(C3, tk, KD(r - 7 + (0, 4, 0, 4)[st // 4]), 0.5, 94, gate=1.0)
            continue
        d = LUTE_FING[(k + st // 4) % len(LUTE_FING)][st % 4 - 1]
        if st in (2, 10) and k % 2 == 1 and not big:                     # hammer-on from a step below
            note(C3, tk - 34, KD(r - 7 + d - 1), 0.07, 68, jitter=0)
        note(C3, tk, KD(r - 7 + d), 0.25, 80 if st % 2 == 0 else 72, gate=1.3)
FLUTE1[7] = [(0, 4, 2), (2, 6, 2)]
FLUTE1[11] = [(0, 4, 2), (2, 6, 2)]
FLUTE1[15] = [(0, 9, 2), (2, 11, 2)]
for k, r in enumerate(ROOTS1):
    b = t(k)
    big = k >= 12
    if k % 2 == 0:
        chord(C6, b, [KD(r - 14), KD(r - 10), KD(r - 7)] + (KD.tri(r) if big else []), 2 * BPB, 76 if big else 70)
    note(C5, b, KD(r - 14), 2, 84)
    note(C5, b + 2 * TPB, KD(r - 10), 2, 76)
    if k < 15:
        lute(k, r)
    else:                                                                # the last bar: a run down, a final strum
        for i, d in enumerate([11, 10, 9, 8, 7, 6, 5, 4]):
            note(C3, b + i * TPB // 4, KD(r - 7 + d), 0.25, 90 - i * 2, gate=0.95, jitter=3)
        chord(C3, b + 2 * TPB, [KD(r - 7 + d) for d in (0, 4, 7, 9, 11)], 1.5, 98, roll=14, gate=0.85)
    if k >= 2:
        chord(C4, b, KD.tri(r + 7), 1.5, 78, roll=18)
        chord(C4, b + 2 * TPB, KD.tri(r + 7)[::-1], 1.5, 70, roll=18)
        if big:
            chord(C4, b + TPB, KD.tri(r + 7), 1, 64, roll=14)
            chord(C4, b + 3 * TPB, KD.tri(r + 7)[::-1], 1 if k < 15 else 0.75, 60, roll=14)
    mel(C1, k, KD, REC1[k], vel=98, gate=0.95)
    if k in FLUTE1:
        mel(C2, k, KD, FLUTE1[k], vel=88, gate=0.95)
    drum(b, 45, 82)
    drum(b + int(1.5 * TPB), 45, 64)
    drum(b + 2 * TPB, 45, 76)
    for s in (1, 3) if not big else (0.5, 1, 1.5, 2.5, 3, 3.5):
        drum(b + int(s * TPB), TAMB, 60 if s % 1 == 0 else 44)
    if k % 4 == 3 or big:
        chord(C9, b + 2 * TPB, KD.tri(r + 7) + KD.tri(r + 14), 2 if k < 15 else 1.4, 72, roll=40)
    if k >= 4:
        chord(C7, b, [KD(r - 7)] + KD.tri(r), BPB, 60 if k < 8 else 74)
    if k in (0, 8, 12, 15):
        note(C13, b, KD(r + 7), 3, 84)
    if big:
        chord(C14, b, [KD(-7), KD(-3)], BPB, 76)                         # bagpipe drone D + A
ramp(C7, 11, t(4), t(12), 40, 112)
drum(t(11, 3), TRI, 70)
drum(t(15, 3), TRI, 80)
advance(16)

# ======================================================================================
# 2  Baroque -> Classical - A minor (harmonic on E), 100 BPM, 20 bars
# ======================================================================================
KA, KAh = Key(57, "minor"), Key(57, "harm")
section(100, key=KA, extra={8}, name="baroque")                        # G# on E chords
chord(C6, t(0), [KA(-14), KA(-10), KA(-7)], 1.6 * BPB, 68)             # the drone carries over
ramp(C6, 11, t(0, 2), t(1, 2), 127, 0)
prog(C3, t(0) - 20, 6, vol=90, pan=44, rev=45)                        # Harpsichord
prog(C1, t(0) - 20, 40, vol=104, pan=58, rev=60)                      # Violin
prog(C2, t(0) - 20, 68, vol=92, pan=74, rev=55)                       # Oboe
prog(C4, t(0) - 20, 45, vol=92, pan=80, rev=50)                       # Pizzicato
prog(C5, t(0) - 20, 43, vol=96, pan=56, rev=50)                       # Contrabass
prog(C8, t(0) - 20, 60, vol=88, pan=36, rev=65)                       # French Horn
prog(C9, t(0) - 20, 47, vol=92, pan=64, rev=60)                       # Timpani
prog(C14, t(0) - 20, 73, vol=86, pan=90, rev=60)                      # Flute
cc(C7, t(0), 11, 90)
ROOTS2 = [0, 3, 6, 2, 5, 3, 4, 0, 0, 3, 6, 2, 3, 6, 2, 5, 5, 1, 4, 4]
VN = [
    [(0, 11, 2), (2, 9, 1), (3, 7, 1)], [(0, 10, 3), (3, 12, 1)], [(0, 13, 1.5), (1.5, 12, .5), (2, 10, 2)],
    [(0, 11, 4)], [(0, 12, 1), (1, 14, 1), (2, 16, 2)], [(0, 14, 1), (1, 12, 1), (2, 10, 2)],
    [(0, 11, 1), (1, 13, 1), (2, 15, 2)], [(0, 14, 4)],
]
DUET = [[(0, 10, 1), (1, 12, 1), (2, 14, 1), (3, 12, 1)], [(0, 13, 1.5), (1.5, 11, .5), (2, 8, 2)],
        [(0, 11, 1), (1, 9, 1), (2, 11, 1), (3, 13, 1)], [(0, 12, 2), (2, 14, 2)]]
for k, r in enumerate(ROOTS2):
    K = KAh if r == 4 else KA
    b = t(k)
    for i in range(16):
        dd = [0, 2, 4, 7][i % 4] + (7 if (i // 4) % 2 else 0)
        note(C3, b + i * TPB // 4, K(r + dd), 0.25, 74 if i % 4 == 0 else 60, jitter=3)
    if k < 16:
        for i, dd in enumerate([0, 2, 4, 7, 4, 2, 4, 2]):
            note(C4, b + i * TPB // 2, K(r - 7 + dd), 0.5, 80, gate=0.6)
    note(C5, b, K(r - 14) if K(r - 14) >= 28 else K(r - 7), 2, 86)
    note(C5, b + 2 * TPB, K(r - 10) if K(r - 10) >= 28 else K(r - 3), 2, 78)
    chord(C7, b, [K(r - 7)] + K.tri(r), BPB, 72)
    if k < 8:
        mel(C1, k, K, VN[k], vel=100, gate=0.98)
        if k >= 2:
            mel(C2, k, K, VN[k], vel=84, shift=-2, gate=0.98)            # oboe: diatonic third below
    elif k < 12:
        up = k % 2 == 0
        run = [r + 7 + (i if up else 7 - i) for i in range(8)] + [r + 14 - (i if up else 7 - i) for i in range(8)]
        mel(C1, k, K, [(i * 0.25, dd, 0.25) for i, dd in enumerate(run)], vel=96, gate=0.85, jitter=2)
        mel(C2, k, K, [(0, r + 9, 2), (2, r + 11, 2)], vel=80)
        mel(C14, k, K, [(0, r + 16, 2), (2, r + 18, 2)], vel=78)
    elif k < 16:                                                       # violin + oboe duet, flute above
        mel(C1, k, K, DUET[k - 12], vel=100, gate=0.96)
        mel(C2, k, K, DUET[k - 12], vel=86, shift=-2, gate=0.96)
        mel(C14, k, K, DUET[k - 12], vel=80, shift=2, gate=0.96, oct_=1)
    if k in (4, 5, 6, 7, 12, 13, 14, 15, 16, 17, 18, 19):
        chord(C8, b, [K(r + 2), K(r + 4)], BPB, 84)
    if k % 2 == 0 and k < 16:
        note(C9, b, K(r - 7) if K(r - 7) >= 40 else K(r), 1, 94)
        note(C9, b + 3 * TPB, K(r - 3) if K(r - 3) <= 55 else K(r - 10), 1, 80)
prog(C4, t(16) - 30, 44, vol=96, pan=80, rev=60, expr=50)             # Tremolo Strings
for k in range(16, 20):
    r = ROOTS2[k]
    K = KAh if r == 4 else KA
    chord(C4, t(k), K.tri(r + 7), BPB, 90)
    mel(C1, k, K, [(0, r + 11, 2), (2, r + 9, 2)], vel=100)
    mel(C14, k, K, [(0, r + 16, 4)], vel=84)
ramp(C4, 11, t(16), t(20), 50, 127)
ramp(C7, 11, t(16), t(20), 90, 127)
for i in range(16):
    note(C9, t(18) + i * TPB // 2, KA(-10), 0.5, 60 + i * 3, gate=0.5)
advance(20)

# ======================================================================================
# 3  Cathedral - A minor -> A major, 72 BPM, 8 bars + the hit: the organ leads
# ======================================================================================
section(72, key=KA, extra={8, 1}, name="cathedral")                    # G# on E, C# in the last chord
KAM = Key(57, "major")
prog(C11, t(0) - 20, 52, vol=92, pan=58, rev=90, expr=60)             # Choir Aahs
prog(C13, t(0) - 20, 55, vol=110, pan=64, rev=70)                     # Orchestra Hit
prog(C14, t(0) - 20, 61, vol=92, pan=80, rev=70, expr=60)             # Brass Section
cc(C6, t(0) - 20, 7, 118)
cc(C6, t(0) - 20, 11, 70)
cc(C7, t(0) - 20, 11, 70)
ROOTS3 = [0, 5, 2, 6, 3, 5, 4, 4]
HORN3 = [None, [(0, 9, 2), (2, 11, 2)], [(0, 11, 3), (3, 13, 1)], [(0, 13, 2), (2, 11, 2)],
         [(0, 12, 3), (3, 10, 1)], [(0, 12, 2), (2, 14, 2)], [(0, 15, 3), (3, 13, 1)], [(0, 11, 4)]]
for k, r in enumerate(ROOTS3):
    K = KAh if r == 4 else KA
    b = t(k)
    layers = [K(r - 14)] + K.tri(r - 7)                                  # pedal + tenor manual
    if k >= 1:
        layers += K.tri(r)
    if k >= 3:
        layers += K.tri(r + 7)
    if k >= 5:
        layers += [K(r + 14)]
    chord(C6, b, layers, BPB, 100)
    if k >= 2:
        chord(C11, b, K.tri(r + 7) if k >= 4 else K.tri(r), BPB, 88)
    chord(C7, b, K.tri(r), BPB, 60 if k >= 3 else 70)
    note(C5, b, K(r - 14) if K(r - 14) >= 28 else K(r - 7), BPB, 88)
    if k >= 5:
        chord(C14, b, K.tri(r), BPB, 88)
    if HORN3[k]:
        mel(C8, k, K, HORN3[k], vel=96, gate=0.98)
ramp(C6, 11, t(0), t(7, 3), 70, 127)
ramp(C11, 11, t(2), t(7, 3), 60, 127)
ramp(C14, 11, t(5), t(7, 3), 60, 127)
for i in range(32):
    note(C9, t(7) + i * TPB // 8, KA(-10), 0.125, 70 + i, gate=0.5, jitter=2)
hit = t(8)
chord(C13, hit, KAM.tri(0) + [KAM(7)], 1.5, 124)
chord(C6, hit, [KAM(-21), KAM(-14)] + KAM.tri(-7) + KAM.tri(0) + KAM.tri(7), 3, 116)
chord(C11, hit, KAM.tri(7), 3, 110)
chord(C14, hit, KAM.tri(0), 2, 112)
chord(C8, hit, [KAM(2), KAM(4)], 2, 104)
note(C5, hit, KAM(-14), 2, 110)
note(C9, hit, KAM(-7), 1, 120)
drum(hit, CRASH, 120)
drum(hit, CRASH2, 110)
advance(8)
rest0 = pos + 3 * TPB
pos += 3 * TPB + TPB * 2                                                  # the organ tail, then a rest
rests.append((rest0, pos))

# ======================================================================================
# 4  Big band swing - Bb, 160 BPM, 24 bars: head, soli, trumpet solo, shout
# ======================================================================================
KB = Key(58, "major")
section(160, key=KB, extra={8}, name="bigband")                        # Ab in the Bb7 bar
burst = pos - TPB * 2
prog(DR, burst, 32, vol=100, rev=35)                                   # Jazz kit
prog(C1, burst + 3, 56, vol=104, pan=60, rev=45)                       # Trumpet
prog(C8, burst + 6, 57, vol=96, pan=44, rev=45)                        # Trombone
prog(C2, burst + 9, 65, vol=92, pan=76, rev=40)                        # Alto Sax
prog(C7, burst + 12, 66, vol=90, pan=86, rev=40)                       # Tenor Sax
prog(C12, burst + 15, 67, vol=90, pan=30, rev=35)                      # Baritone Sax
prog(C5, burst + 18, 32, vol=104, pan=56, rev=30)                      # Acoustic Bass
prog(C4, burst + 21, 0, vol=90, pan=70, rev=40)                        # Piano
prog(C3, burst + 24, 26, vol=84, pan=36, rev=35)                       # Jazz Guitar
for i in range(4):
    drum(burst + i * TPB // 2, PHH, 70)
ROOTS4 = [0, 5, 1, 4, 2, 5, 1, 4, 0, 3, 0, 5, 1, 4, 2, 5, 1, 4, 0, 4, 1, 4, 0, 4]
TPT = [[(0, 9, 1.5), (1.5, 11, .5), (2, 12, 1), (3, 11, 1)], [(0, 11, 2), (2.5, 10, .5), (3, 9, 1)],
       [(0, 8, 1), (1, 9, 1), (2, 10, .5), (2.5, 11, 1.5)], [(0, 10, 3)],
       [(0, 9, 1.5), (1.5, 11, .5), (2, 13, 1), (3, 12, 1)], [(0, 12, 2), (2.5, 11, .5), (3, 9, 1)],
       [(0, 10, 1), (1, 9, 1), (2, 8, 1), (3, 7, 1)], [(0, 9, 3)]]
SOLO4 = [[(0.5, 11, .5), (1, 12, .5), (1.5, 13, .5), (2, 14, 1.5), (3.5, 13, .5)],
         [(0, 12, .5), (.5, 11, .5), (1, 10, .5), (1.5, 9, .5), (2, 8, 2)],
         [(0.5, 9, .5), (1, 10, .5), (1.5, 11, .5), (2, 12, .5), (2.5, 13, .5), (3, 14, 1)],
         [(0, 15, 2), (2.5, 14, .5), (3, 13, 1)],
         [(0, 12, 1), (1, 14, .5), (1.5, 12, .5), (2, 11, 1), (3, 9, 1)],
         [(0, 10, 1.5), (1.5, 9, .5), (2, 11, 1), (3, 13, 1)],
         [(0, 14, .5), (.5, 13, .5), (1, 12, .5), (1.5, 11, .5), (2, 10, .5), (2.5, 9, .5), (3, 8, 1)],
         [(0, 7, 2), (2.5, 9, .5), (3, 11, 1)]]


def vox4(K, r, k):
    """Four-note jazz voicing (diatonic 7th; I gets the 6th; the Bb7 bar gets Ab)."""
    if k == 8:
        return [K(r), K(r + 2), K(r + 4), K(r) + 10]
    return [K(r), K(r + 2), K(r + 4), K(r + (5 if r == 0 else 6))]


for k, r in enumerate(ROOTS4):
    b = t(k)
    v = vox4(KB, r, k)
    walk = [KB(r - 7), KB(r - 5), KB(r - 3), KB(r - 2 if k % 2 else r - 6)]
    for i, n in enumerate(walk):
        note(C5, b + i * TPB, n - (12 if n > 52 else 0), 1, 94 if i == 0 else 84, gate=0.85)
    for i in range(4):
        chord(C3, b + i * TPB, v[:3], 0.6, 70, gate=0.7)
    for bt in ((1.5, 3) if k % 2 == 0 else (0, 2.5)):
        chord(C4, t(k, swing(bt)), [x + 12 for x in v], 0.4, 78, gate=0.7)
    for i in range(8):
        if i % 2 == 0 or i in (3, 7):
            drum(t(k, swing(i * 0.5)), RIDE, 76 if i % 4 == 0 else 62)
    drum(t(k, 1), PHH, 70)
    drum(t(k, 3), PHH, 70)
    drum(b, KICK, 50)
    if k % 4 == 3:
        fill(k, 2, "snare", 86)
    if k < 8:                                                            # head
        mel(C1, k, KB, [(swing(bb), d, ln) for bb, d, ln in TPT[k]], vel=102, gate=0.85)
        mel(C2, k, KB, [(swing(bb), d, ln) for bb, d, ln in TPT[k]], vel=86, shift=-2, gate=0.85)
        mel(C7, k, KB, [(swing(bb), d, ln) for bb, d, ln in TPT[k]], vel=82, shift=-4, gate=0.85)
        note(C12, b, KB(r - 7), 2, 76)
        chord(C8, t(k, 0), [KB(r), KB(r + 4)], 2, 70)
    elif k < 12:                                                         # sax soli
        runs = [r + 7 + [0, 2, 4, 5, 4, 2, 1, 2][i] for i in range(8)]
        spec = [(swing(i * 0.5), d, 0.5) for i, d in enumerate(runs)]
        mel(C2, k, KB, spec, vel=96, gate=0.8, jitter=3)
        mel(C7, k, KB, spec, vel=86, shift=-2, gate=0.8, jitter=3)
        mel(C12, k, KB, spec, vel=80, shift=-7, gate=0.8, jitter=3)
        chord(C1, t(k, 3), [v[3] + 12], 0.5, 90)
        chord(C8, b, [v[0], v[2]], 2, 74)
    elif k < 20:                                                         # trumpet solo, sax backgrounds
        mel(C1, k, KB, [(swing(bb), d, ln) for bb, d, ln in SOLO4[k - 12]], vel=104, gate=0.85, jitter=3)
        for bt, ln in ((0, 1.5), (2.5, 1.5)):
            chord(C2, t(k, swing(bt)), [v[2] + 12], ln, 70)
            chord(C7, t(k, swing(bt)), [v[1] + 12], ln, 66)
            note(C12, t(k, swing(bt)), KB(r - 7), ln, 70)
        chord(C8, b, [v[0], v[3]], 3.5, 64)
    else:                                                                # shout chorus, brass section on top
        for bt in (0, 1.5, 3):
            chord(C1, t(k, swing(bt)), [v[3] + 12, v[1] + 24], 0.6, 110)
            chord(C8, t(k, swing(bt)), [v[0], v[1]], 0.6, 100)
            chord(C2, t(k, swing(bt)), [v[2] + 12], 0.6, 96)
            chord(C7, t(k, swing(bt)), [v[1] + 12], 0.6, 92)
            chord(C14, t(k, swing(bt)), [x + 12 for x in v[:3]], 0.6, 104)
            note(C12, t(k, swing(bt)), KB(r - 7), 0.6, 96)
            drum(t(k, swing(bt)), CRASH if bt == 0 else SNARE, 96)
advance(24)

# ======================================================================================
# 5  Boogie-woogie -> rock'n'roll - A blues, 150 then 168 BPM
# ======================================================================================
KAm = Key(57, "mixo")
BLUE = {0, 7}                                                            # C (blue third), G (b7)


def blue(r, off):
    """The blue third (+15) only over A; over D it would be F (out of the key)."""
    return 16 if off == 15 and r % 12 == 2 else off


section(150, key=Key(57, "major"), extra=BLUE, name="boogie")
prog(DR, t(0) - 20, 0, vol=98, rev=30)                                  # Standard kit
prog(C4, t(0) - 20, 0, vol=104, pan=60, rev=35)                         # Piano (boogie)
BL = [0, 0, 0, 0, 3, 3, 0, 0, 4, 3, 0, 4]
for k in range(12):
    r = KAm(BL[k])
    for i, off in enumerate([0, 4, 7, 9, 10, 9, 7, 4]):                   # boogie left hand
        note(C4, t(k, swing(i * 0.5)), r - 24 + off + (12 if r - 24 + off < 33 else 0), 0.5, 88 if i % 2 == 0 else 74, gate=0.8)
    lick = [(0, 16, 0.5), (0.5, 19, 0.5), (1, 22, 0.5), (1.5, 19, 0.5), (2, 15, 0.25), (2.25, 16, 0.75), (3, 12, 1)]
    if k % 4 == 3:
        lick = [(0, 22, 0.25), (0.25, 19, 0.25), (0.5, 16, 0.5), (1, 12, 1), (2, 16, 2)]
    for bb, off, ln in lick:
        note(C4, t(k, swing(bb)), r + blue(r, off), ln, 92, gate=0.85)
    if k >= 4:                                                           # bass and drums join
        for i, off in enumerate([0, 4, 7, 9]):
            note(C5, t(k, i), r - 24 + off if r - 24 + off >= 28 else r - 12 + off, 1, 90, gate=0.8)
        for bt in range(4):
            drum(t(k, bt), SNARE if bt % 2 else KICK, 70 if bt % 2 else 80)
            drum(t(k, swing(bt + 0.5)), CHH, 60)
            drum(t(k, bt), CHH, 66)
            if k >= 8:
                drum(t(k, bt), TAMB, 56)
fill(11, 3, "snare", 90)
advance(12)
section(168, key=Key(57, "major"), extra=BLUE, name="rocknroll")
prog(C1, t(0) - 20, 66, vol=100, pan=58, rev=40)                        # Tenor Sax
prog(C3, t(0) - 20, 27, vol=92, pan=36, rev=35)                         # Clean Gt. (rhythm)
prog(C2, t(0) - 20, 29, vol=100, pan=74, rev=40)                        # Overdrive Gt. (intro lick, lead)
prog(C12, t(0) - 20, 67, vol=88, pan=28, rev=30)                        # Baritone Sax
bend_range(C2, t(0) - 15, 2)
# intro: the overdrive guitar's double-stop lick, band hit on the last beat
for i in range(8):
    chord(C2, t(0, i * 0.5), [69 + (3 if i % 4 == 2 else 4 if i % 4 == 3 else 0), 72 + (4 if i % 4 >= 2 else 0)], 0.5, 106, gate=0.8)
bend_curve(C2, t(0, 0.1), t(0, 0.4), 0, TONE2 // 2, 4)
bend(C2, t(0, 0.95), 0)
for bb, a, b_ in ((0, 76, 81), (0.5, 76, 81), (1, 74, 79), (1.5, 73, 76), (2, 72, 76), (2.5, 69, 73), (3, 69, 72)):
    chord(C2, t(1, bb), [a, b_], 0.5, 104, gate=0.85)
drum(t(1, 3), CRASH, 104)
drum(t(1, 3), KICK, 104)
advance(2)
for k in range(36):
    r = KAm(BL[k % 12])
    stop = 24 <= k < 28                                                  # stop-time: hits on 1, piano answers
    for i, off in enumerate([0, 4, 7, 9, 10, 9, 7, 4]):
        if stop and i:
            break
        note(C4, t(k, i * 0.5), r - 12 + off, 0.5, 84 if i % 2 == 0 else 72, gate=0.8)
        note(C5, t(k, i * 0.5), r - 24 + off if r - 24 + off >= 28 else r - 12 + off, 0.5, 90 if i % 2 == 0 else 76, gate=0.6)
        chord(C3, t(k, i * 0.5), [r - 12, r - 12 + (9 if i % 4 >= 2 else 7)], 0.5, 84, gate=0.55)
    if not stop:
        for i in range(12):
            chord(C4, t(k, i / 3), [r + 16, r + 19], 1 / 3, 70 if i % 3 else 80, gate=0.7)
    for bt in range(4):
        if stop and bt:
            continue
        drum(t(k, bt), KICK if bt % 2 == 0 else SNARE, 96 if bt % 2 == 0 else 90)
        drum(t(k, bt), RIDE if 12 <= k < 24 else CHH, 70)
        drum(t(k, bt + 0.5), RIDE if 12 <= k < 24 else CHH, 60)
        if bt % 2:
            drum(t(k, bt), TAMB, 64)
    if stop:
        drum(t(k), CRASH, 104)
    if k % 4 == 3 and not stop:
        fill(k, 3, "down" if k % 8 == 7 else "snare", 96)
    if k < 12:                                                           # sax chorus, tenor + bari
        spec = [(0, 19, 1), (1.5, 17, 0.5), (2, 16, 1), (3, 19, 0.75)] if k % 2 == 0 else [(0.5, 19, 0.5), (1, 16, 1), (2, 12, 1.5)]
        for bb, off, ln in spec:
            note(C1, t(k, bb), r + off - 12, ln, 104)
            note(C7, t(k, bb), r + off - 24, ln, 90)
        note(C12, t(k, 0), r - 12, 1, 86)
        note(C12, t(k, 2), r - 5, 1, 80)
    elif k < 24:                                                         # overdrive lead chorus
        if k % 4 == 3:
            chord(C2, t(k), [r + 12, r + 16], 2, 108)
            bend_curve(C2, t(k, 0.2), t(k, 1), 0, TONE2 // 2, 8)
            bend(C2, t(k, 1.9), 0)
            chord(C2, t(k, 2), [r + 7, r + 12], 2, 104)
        else:
            for i, (a, b_) in enumerate([(12, 16), (12, 16), (10, 15), (10, 15), (7, 12), (7, 12), (4, 7), (0, 4)]):
                chord(C2, t(k, i * 0.5), [r + a, r + blue(r, b_)], 0.5, 104 if i % 2 == 0 else 92, gate=0.8)
        if k % 2 == 1:
            note(C1, t(k, 3), r + 7, 1, 92)
    else:                                                                # stop-time, then the piano chorus
        if stop:
            for i in range(9):
                chord(C4, t(k, 1 + i / 3), [r + 12 + [4, 7, 9, 12, 9, 7, 4, 7, 12][i]], 1 / 3, 96, gate=0.8)
            chord(C2, t(k, 2.5), [r + 12, r + 16], 1.5, 100)
        else:
            for i in range(8):
                chord(C4, t(k, i * 0.5), [r + 24 + [0, 4, 7, 10, 12, 10, 7, 4][i]], 0.5, 96, gate=0.8)
            chord(C2, t(k), [r + 7, r + 12], 1, 96)
            note(C1, t(k, 2), r + 7, 2, 94)
            note(C7, t(k, 2), r - 5, 2, 86)
advance(36)
chord(C3, t(0), [45, 52, 57], 1, 110)
chord(C4, t(0), [45, 57, 61, 64], 1, 108)
chord(C2, t(0), [57, 64, 69], 1, 110)
note(C5, t(0), 33, 1, 110)
note(C1, t(0), 69, 1, 106)
drum(t(0), CRASH, 116)
drum(t(0), KICK, 116)

# ======================================================================================
# 6  Proto-synth machine - A mixolydian, 132 BPM, 16 bars (a calliope synth picks up the lick)
# ======================================================================================
section(132, key=KAm, name="machine")
prog(C8, t(0, 0.5), 82, vol=100, pan=84, rev=45)                        # Syn. Calliope (the machine)
prog(C1, t(0, 1) + 10, 80, vol=98, pan=60, rev=45)                      # Square lead
prog(C2, t(0, 1) + 10, 63, vol=90, pan=76, rev=45)                      # Synth Brass 2 (answers)
prog(C9, t(0, 1) + 10, 8, vol=86, pan=40, rev=55)                       # Celesta
prog(C5, t(0, 1) + 10, 38, vol=98, pan=64, rev=20)                      # Synth Bass 1
prog(C13, t(0, 1) + 10, 88, vol=86, pan=64, rev=80, expr=30)            # Fantasia pad
prog(C14, t(0, 1) + 10, 87, vol=84, pan=40, rev=45)                     # Bass & Lead
bend_range(C1, t(0, 1) + 20, 2)
LICK = [(1, 7, .5), (1.5, 9, .5), (2, 11, .5), (2.5, 9, .5), (3, 7, .5), (3.5, 6, .5)]
mel(C8, 0, KAm, LICK, vel=92, gate=0.8)
MACH = [7, 9, 11, 9, 7, 6, 4, 6]
SQ = [[(0, 14, .5), (.5, 7, .5), (1, 11, 1), (2, 13, .5), (2.5, 12, .5), (3, 11, 1)],
      [(0, 9, .5), (.5, 16, .5), (1, 14, 1), (2, 11, 2)],
      [(0, 13, .5), (.5, 6, .5), (1, 10, 1), (2, 12, .5), (2.5, 11, .5), (3, 10, 1)],
      [(0, 9, 3)]]
ROOTS6 = [0, 0, 6, 0, 3, 3, 0, 0, 0, 0, 6, 0, 6, 6, 3, 3]
ramp(C13, 11, t(2), t(6), 30, 100)
for k in range(1, 16):
    r = ROOTS6[k]
    mel(C8, k, KAm, [(i * 0.25, r + MACH[i % 8] + (7 if (i // 8) % 2 else 0) - 7, 0.25) for i in range(16)],
        vel=84, gate=0.7, jitter=2)
    for bt in (0.5, 1.5, 2.5, 3.5):
        note(C9, t(k, bt), KAm(r + 14 + (4 if bt > 2 else 2)), 0.25, 70, gate=0.8)
    for i in range(8):
        note(C5, t(k, i * 0.5), KAm(r - 14 + (7 if i % 2 else 0)) if KAm(r - 14) >= 28 else KAm(r - 7 + (7 if i % 2 else 0)), 0.5, 88, gate=0.6)
    if k >= 2:
        chord(C13, t(k), KAm.tri(r), BPB, 76)
    if k < 14:
        mel(C1, k, KAm, SQ[k % 4], vel=96, shift=r if r < 5 else r - 7)
        if k % 4 == 3:
            bend_curve(C1, t(k, 1), t(k, 2.5), 0, 8191)
            bend(C1, t(k + 1) - 10, 0)
    if k % 2 == 1:                                                       # synth brass answers + stabs
        mel(C2, k, KAm, [(2, r + 11, .5), (2.5, r + 9, .5), (3, r + 7, 1)], vel=92)
    else:
        for bt in (0.5, 2.5):
            chord(C2, t(k, bt), KAm.tri(r + 7), 0.4, 88, gate=0.7)
    if 4 <= k < 12:                                                      # bass & lead counter-line
        mel(C14, k, KAm, [(0, r + 4, 1.5), (1.5, r + 2, .5), (2, r, 1), (3, r + 2, 1)], vel=86)
    for bt in range(4):
        drum(t(k, bt), KICK if bt % 2 == 0 else CLAVES, 86 if bt % 2 == 0 else 74)
        drum(t(k, bt + 0.5), WOODH if bt % 2 else WOODL, 72)
        if k >= 8:
            drum(t(k, bt + 0.25), SHAKER, 50)
            drum(t(k, bt + 0.75), SHAKER, 46)
    if k % 4 == 3:
        drum(t(k, 3.5), TRI, 70)
KE = Key(52, "minor")
prog(C3, t(12) - 30, 81, vol=86, pan=40, rev=45, expr=10)               # Saw (sequence)
prog(C6, t(12) - 30, 90, vol=84, pan=64, rev=70, expr=10)               # Polysynth pad
ramp(C3, 11, t(12), t(16), 10, 115)
ramp(C6, 11, t(14), t(16), 10, 100)
ramp(C13, 11, t(13), t(16), 100, 40)
for k in range(12, 16):
    r6 = ROOTS6[k]
    e_root = 2 if r6 == 6 else 6
    for i in range(16):
        note(C3, t(k, i * 0.25), KE(e_root + [0, 2, 4, 7][i % 4] + (7 if (i // 4) % 2 else 0)), 0.25, 80 if i % 4 == 0 else 64, gate=0.45, jitter=1)
    if k >= 14:
        chord(C6, t(k), [KE(e_root - 7)] + KE.tri(e_root), BPB, 76)
advance(16)

# ======================================================================================
# 7  Analog synths - E minor, 132 BPM, 16 bars; the organ takes the sequence over
# ======================================================================================
section(132, key=KE, name="analog")
prog(DR, t(0) - 30, 25, vol=100, rev=30)                                # TR-808
prog(C5, t(0) - 30, 39, vol=104, pan=64, rev=15)                        # Synth Bass 2
prog(C8, t(0) - 30, 62, vol=92, pan=80, rev=45)                         # Synth Brass 1
prog(C7, t(0) - 30, 50, vol=84, pan=30, rev=60)                         # Synth Strings 1
prog(C1, t(0) - 30, 81, vol=100, pan=58, rev=50)                        # Saw lead
prog(C12, t(0) - 30, 94, vol=82, pan=96, rev=80, expr=40)               # Halo Pad
bend_range(C1, t(0) - 25, 2)
ROOTS7 = [0, 5, 6, 4, 0, 5, 2, 6, 3, 5, 6, 4, 0, 5, 6, 3]
LEAD7 = [[(0, 11, 1.5), (1.5, 13, .5), (2, 14, 2)], [(0, 14, 1), (1, 13, 1), (2, 12, 2)],
         [(0, 13, 1.5), (1.5, 15, .5), (2, 17, 2)], [(0, 15, 4)]]
ramp(C12, 11, t(0), t(4), 40, 100)
for k, r in enumerate(ROOTS7):
    b = t(k)
    if k < 12:
        for i in range(16):
            note(C3, b + i * TPB // 4, KE(r + [0, 2, 4, 7][i % 4] + (7 if (i // 4) % 2 else 0)), 0.25,
                 82 if i % 4 == 0 else 64, gate=0.45, jitter=1)
    else:                                                               # the sequence holds (a stab tone falls back)
        chord(C3, b, KE.tri(r), 1.8, 84)
        chord(C3, t(k, 2), KE.tri(r + 7), 1.8, 80)
    for i in range(16):
        note(C5, b + i * TPB // 4, KE(r - 7 if KE(r - 7) >= 36 else r) + (12 if i % 4 == 2 else 0), 0.25, 92 if i % 4 == 0 else 74, gate=0.5, jitter=1)
    chord(C6, b, [KE(r - 7)] + KE.tri(r), BPB, 80)
    chord(C7, b, KE.tri(r + 7), BPB, 70)
    chord(C12, b, KE.tri(r + 7) + [KE(r + 14)], BPB, 66)
    if 2 <= k < 12:
        mel(C1, k, KE, LEAD7[k % 4], vel=100, gate=0.97)
        if k % 4 == 3:
            bend_curve(C1, t(k, 0.5), t(k, 1.5), 0, 4096, 8)
            bend_curve(C1, t(k, 3), t(k, 3.8), 4096, 0, 6)
    if 8 <= k < 12:                                                     # synth brass 2 counter-line
        mel(C2, k, KE, [(0, r + 9, 2), (2, r + 11, 1), (3, r + 9, 1)], vel=88)
    if 4 <= k < 8 or 12 <= k < 16:                                      # brass fanfares
        for bt in (0, 1.5, 3):
            chord(C8, t(k, bt), KE.tri(r + 7), 0.45, 98, gate=0.7)
    for bt in range(4):
        drum(t(k, bt), KICK if bt in (0, 2) else CLAP, 100 if bt in (0, 2) else 90)
        drum(t(k, bt + 0.5), CHH, 70)
        drum(t(k, bt + 0.25), CHH, 44)
    drum(t(k, 3.75), KICK, 80)
    if k % 4 == 3:
        drum(t(k, 3.5), OHH, 80)
prog(C4, t(12) - 30, 16, vol=100, pan=58, rev=40, expr=30)              # Drawbar Organ
ramp(C4, 11, t(12), t(16), 30, 127)
for k in range(12, 16):
    r = ROOTS7[k]
    for i in range(16):
        note(C4, t(k, i * 0.25), KE(r + 7 + [0, 2, 4, 7][i % 4]), 0.25, 80, gate=0.6, jitter=1)
ramp(C12, 11, t(14), t(16), 100, 30)
advance(16)

# ======================================================================================
# 8  Prog / hard rock - A minor, 132 BPM
# ======================================================================================
section(132, key=KA, extra={8}, name="prog")
prog(DR, t(0) - 30, 16, vol=104, rev=35)                                # Power kit
prog(C3, t(0) - 30, 29, vol=40, pan=30, rev=30)                         # Overdrive Gt. L (swells in)
prog(C12, t(0) - 30, 29, vol=40, pan=100, rev=30)                       # Overdrive Gt. R
prog(C5, t(0) - 30, 33, vol=104, pan=60, rev=20)                        # Fingered Bass
prog(C1, t(0) - 30, 81, vol=98, pan=70, rev=50)                         # Saw lead ("Moog")
cc(C4, t(0), 11, 50)
cc(C6, t(0), 11, 30)
# a) rotary crescendo: held organ chords two bars each, swelling; guitars and drums build under it
HOLD = [0, 5, 6, 4]
for j, r in enumerate(HOLD):
    K = KAh if r == 4 else KA
    k = 2 * j
    chord(C4, t(k), K.tri(r) + [K(r + 7), K(r - 7)], 2 * BPB, 96 + j * 6, gate=0.98)
    chord(C6, t(k), K.tri(r + 7), 2 * BPB, 70)
    if j >= 1:
        chord(C3, t(k), [K(r - 7), K(r - 7) + 7, K(r)], 2 * BPB, 104, gate=0.98)
        ramp(C3, 7, t(k), t(k, 3), 40, 100)
    if j >= 2:
        chord(C12, t(k), [K(r - 7) + 7, K(r), K(r) + 7], 2 * BPB, 100, gate=0.98)
        ramp(C12, 7, t(k), t(k, 3), 40, 96)
        note(C5, t(k), K(r - 14) if K(r - 14) >= 28 else K(r - 7), 2 * BPB, 100, gate=0.98)
ramp(C4, 11, t(0), t(7, 2), 50, 127)
ramp(C6, 11, t(0), t(8), 30, 90)
for i in range(8):                                                      # cymbal swells, then toms, then a roll
    drum(t(0, i), RIDE, 50 + i * 4)
drum(t(2), CRASH, 96)
for bt in range(8):
    drum(t(2, bt), KICK if bt % 2 == 0 else RIDE, 80 + bt * 2)
for i in range(16):
    drum(t(4, i * 0.5), TOMS[(i // 3) % 5], 78 + i * 2)
for i in range(32):
    drum(t(6, i * 0.25), SNARE, 60 + i * 2)
advance(8)
# b) the riff: organ + two guitars + bass in unison, 8 bars (the second four add harmony)
RIFF = [0, 0, 7, 0, 6, 0, 5, 4, 0, 0, 7, 0, 9, 8, 6, 4]
drum(t(0), CRASH, 116)
for k in range(8):
    tr = [0, 3, 5, 0][k % 4]
    for i in range(8):
        d = RIFF[(k % 2) * 8 + i] + tr
        note(C3, t(k, i * 0.5), KA(d - 7), 0.5, 100, gate=0.8)
        note(C3, t(k, i * 0.5), KA(d - 3), 0.5, 92, gate=0.8)
        note(C12, t(k, i * 0.5), KA(d - 7 + (2 if k >= 4 else 0)) + 12, 0.5, 90, gate=0.8)
        note(C4, t(k, i * 0.5), KA(d - 7) + 12, 0.5, 94, gate=0.85)
        if k >= 4:
            note(C4, t(k, i * 0.5), KA(d - 5) + 12, 0.5, 86, gate=0.85)
        note(C5, t(k, i * 0.5), KA(d - 7) - 12, 0.5, 100, gate=0.8)
    for bt in range(4):
        drum(t(k, bt), KICK, 106)
        drum(t(k, bt + 0.5), KICK if bt % 2 else CHH, 90)
        if bt % 2:
            drum(t(k, bt), SNARE, 110)
        drum(t(k, bt), RIDE, 72)
    if k in (3, 7):
        fill(k, 3, "snare" if k == 3 else "flams", 104)
advance(8)
# c) 7/8
section(132, beats=3.5, den=8, key=KA, extra={8}, name="prog 7/8")
for k in range(4):
    r = [0, 0, 6, 5][k]
    for i, (bt, acc) in enumerate(((0, 1), (0.5, 0), (1, 0), (1.5, 1), (2, 0), (2.5, 1), (3, 0))):
        n = KA(r - 7) + (12 if i in (3, 5) else 0)
        note(C3, t(k, bt), n, 0.5, 104 if acc else 90, gate=0.75)
        note(C12, t(k, bt), n + 7, 0.5, 100 if acc else 86, gate=0.75)
        note(C4, t(k, bt), n + 12, 0.5, 100 if acc else 86, gate=0.75)
        note(C5, t(k, bt), n - 12, 0.5, 104, gate=0.75)
        if acc:
            drum(t(k, bt), KICK, 110)
            drum(t(k, bt), CRASH if (k == 0 and i == 0) else CHINA if i == 5 else RIDE, 100)
        else:
            drum(t(k, bt), CHH, 80)
    drum(t(k, 1.5), SNARE, 110)
    drum(t(k, 2.5), SNARE, 110)
    chord(C6, t(k), KA.tri(r + 7), 3.5, 70)
advance(4)
# d) organ vs Moog, two bars each
section(132, key=KA, extra={8}, name="prog solos")
for k in range(8):
    r = [0, 5, 6, 4, 0, 5, 3, 4][k]
    K = KAh if r == 4 else KA
    if (k // 2) % 2 == 0:
        run = [r + 7 + [0, 1, 2, 3, 4, 3, 2, 1][i % 8] + (2 if i >= 8 else 0) for i in range(16)]
        mel(C4, k, K, [(i * 0.25, d, 0.25) for i, d in enumerate(run)], vel=100, gate=0.8, jitter=2)
    else:
        chord(C4, t(k), K.tri(r + 7), BPB, 96)                           # held: rotary flips again
        mel(C1, k, K, [(0, r + 11, 1.5), (1.5, r + 13, 0.5), (2, r + 14, 1), (3, r + 11, 1)], vel=102)
        bend_curve(C1, t(k, 2), t(k, 2.5), -TONE2 // 2, 0, 6)
    chord(C3, t(k), [K(r - 7), K(r - 7) + 7, K(r)], 1.9, 100)
    chord(C3, t(k, 2), [K(r - 7), K(r - 7) + 7, K(r)], 1.9, 96)
    chord(C12, t(k, 0.5), [K(r), K(r) + 7], 1.4, 90)
    chord(C12, t(k, 2.5), [K(r), K(r) + 7], 1.4, 86)
    note(C5, t(k), K(r - 14) if K(r - 14) >= 28 else K(r - 7), 2, 100)
    note(C5, t(k, 2), K(r - 10) if K(r - 10) >= 28 else K(r - 3), 2, 96)
    chord(C6, t(k), K.tri(r + 7), BPB, 72)
    for bt in range(4):
        drum(t(k, bt), KICK if bt % 2 == 0 else SNARE, 106)
        drum(t(k, bt), RIDE, 70)
    if k % 2 == 1:
        fill(k, 3, ["down", "snare", "triplet", "kicks"][k // 2], 102)
advance(8)
# e) second rotary crescendo: two held chords, two bars each, everything swelling
for j, r in enumerate((5, 4)):
    K = KAh if r == 4 else KA
    k = 2 * j
    chord(C4, t(k), K.tri(r) + [K(r + 7), K(r - 7), K(r + 9)], 2 * BPB, 108, gate=0.98)
    chord(C3, t(k), [K(r - 7), K(r - 7) + 7, K(r)], 2 * BPB, 110, gate=0.98)
    chord(C12, t(k), [K(r - 7) + 7, K(r), K(r) + 7], 2 * BPB, 106, gate=0.98)
    chord(C6, t(k), K.tri(r + 7), 2 * BPB, 80)
    note(C5, t(k), K(r - 14) if K(r - 14) >= 28 else K(r - 7), 2 * BPB, 104, gate=0.98)
    mel(C1, k, K, [(0, r + 14, 4), (4, r + 16, 4)], vel=100, gate=0.98)
cc(C4, t(0), 11, 70)
ramp(C4, 11, t(0), t(3, 2), 70, 127)
ramp(C6, 11, t(0), t(4), 60, 110)
drum(t(0), CRASH, 110)
for i in range(16):
    drum(t(0, i * 0.5), RIDE, 60 + i * 2)
for i in range(16):
    drum(t(2, i * 0.5), TOMS[i % 5] if i < 8 else SNARE, 80 + i * 2)
advance(4)
# f) the ritardando into the metal (E minor v chord)
KEm = Key(52, "minor")
tempo_at(t(0, 2), 120)
tempo_at(t(1), 108)
tempo_at(t(1, 2), 100)
chord(C3, t(0), [KEm(-7), KEm(-7) + 7, KEm(0)], 2 * BPB, 110, gate=1.0)
chord(C12, t(0), [KEm(-7) + 7, KEm(0), KEm(0) + 7], 2 * BPB, 106, gate=1.0)
note(C5, t(0), KEm(-14) if KEm(-14) >= 28 else KEm(-7), 2 * BPB, 104, gate=0.96)
chord(C4, t(0), KEm.tri(0) + [KEm(7)], 2 * BPB, 96, gate=1.0)
drum(t(0), CRASH, 116)
drum(t(0), KICK, 116)
for i in range(8):
    drum(t(1, i * 0.5), TOMS[i % 5], 90 + i * 3)
advance(2)

# ======================================================================================
# 9a Dio-style epic - E minor, 96 BPM, 12 bars: synth wash, huge power chords, arpeggios
# ======================================================================================
section(96, key=KEm, name="dio")
prog(C3, t(0, 1), 30, vol=102, pan=0, rev=30)                           # Distortion L
prog(C8, t(0, 1), 30, vol=102, pan=127, rev=30)                         # Distortion R
prog(C2, t(0, 1), 30, vol=96, pan=72, rev=45)                           # Twin lead
prog(C1, t(0, 1), 30, vol=104, pan=62, rev=45)                          # Lead guitar
prog(C5, t(0) - 20, 34, vol=108, pan=64, rev=15)                        # Picked Bass
prog(C11, t(0, 1), 52, vol=90, pan=58, rev=90, expr=50)                 # Choir Aahs
prog(C6, t(2) - 30, 19, vol=110, pan=64, rev=90, expr=40)               # Church Organ (for the ending)
prog(C12, t(2) - 30, 29, vol=86, pan=40, rev=45)                        # Overdrive: arpeggios
bend_range(C1, t(0, 1) + 10, 12)
bend_range(C2, t(0, 1) + 10, 2)
ramp(C4, 7, t(0), t(2), 100, 0)
chord(C4, t(0), KEm.tri(0), 2 * BPB, 80)
prog(C7, t(0) - 20, 89, vol=90, pan=64, rev=80, expr=30)                # Warm pad (wash)
ramp(C7, 11, t(0), t(2), 30, 110)
chord(C7, t(0), [KEm(-7)] + KEm.tri(0), 2 * BPB, 80)
ROOTS9 = [0, 0, 0, 5, 6, 0, 0, 5, 6, 4, 5, 6]
DIOL = [[(0, 11, 2), (2, 10, 1), (3, 9, 1)], [(0, 12, 3), (3, 14, 1)], [(0, 13, 2), (2, 11, 2)], [(0, 11, 4)],
        [(0, 14, 1.5), (1.5, 13, .5), (2, 12, 1), (3, 11, 1)], [(0, 12, 2), (2, 14, 2)], [(0, 13, 4)],
        [(0, 15, 2), (2, 13, 2)]]
for k, r in enumerate(ROOTS9):
    if k < 2:
        note(C5, t(k), KEm(-7), BPB, 90)
        drum(t(k, 3), MTOM, 80 + k * 20)
        if k == 1:
            for i in range(8):
                drum(t(k, i * 0.5), RIDE, 50 + i * 6)
        continue
    pw = [KEm(r - 7), KEm(r - 7) + 7, KEm(r)]
    for c_ in (C3, C8):
        chord(c_, t(k), pw, 2.5, 116, gate=0.97)
        chord(c_, t(k, 3), pw, 0.5, 108, gate=0.8)
        chord(c_, t(k, 3.5), pw, 0.5, 110, gate=0.8)
    for i, dd in enumerate([0, 2, 4, 7, 9, 7, 4, 2]):                    # arpeggio guitar
        note(C12, t(k, i * 0.5), KEm(r + dd), 0.5, 84, gate=1.2)
    note(C5, t(k), KEm(r - 14) if KEm(r - 14) >= 28 else KEm(r - 7), 2.5, 112)
    note(C5, t(k, 3), KEm(r - 14) if KEm(r - 14) >= 28 else KEm(r - 7), 1, 108)
    chord(C7, t(k), KEm.tri(r), BPB, 70)
    if k >= 6:
        chord(C11, t(k), KEm.tri(r), BPB, 76)
    drum(t(k), CRASH, 110)
    drum(t(k), KICK, 116)
    drum(t(k, 2), SNARE, 118)
    drum(t(k, 3), KICK, 108)
    drum(t(k, 3.5), KICK, 104)
    for bt in range(4):
        drum(t(k, bt), RIDE, 74)
    if k in (3, 7, 11):
        fill(k, 2, ["down", "flams", "triplet"][k // 4], 108)
    if k >= 4:
        mel(C1, k, KEm, DIOL[k - 4], vel=108, gate=0.97)
        if k in (7, 10):
            bend_curve(C1, t(k, 1), t(k, 1.5), 0, TONE, 6)
            vib(C1, t(k, 1.5), t(k, 3.8), TONE)
            bend(C1, t(k, 3.9), 0)
ramp(C11, 11, t(6), t(12), 50, 100)
advance(12)

# ======================================================================================
# 9b Power groove - E minor with F / Bb, 96 BPM, 12 bars: stop-start chugs, pinch squeals
# ======================================================================================
section(96, key=KEm, extra={5, 10}, name="groove")                      # F (b2) and Bb (b5)
E2 = 40
GROOVE = [(0, 0, 0.5), (0.75, 0, 0.25), (1, 0, 0.25), (1.5, 1, 0.5), (2.25, 0, 0.25), (2.5, 3, 0.5),
          (3.25, 6, 0.25), (3.5, 5, 0.5)]                               # semitones over E: E E E F E G Bb A
GROOVE2 = [(0, 0, 0.25), (0.25, 0, 0.25), (0.5, 3, 0.5), (1, 0, 0.25), (1.25, 0, 0.25), (1.5, 5, 0.5),
           (2, 0, 0.25), (2.25, 0, 0.25), (2.5, 6, 0.5), (3, 7, 0.5), (3.5, 5, 0.5)]   # E E G E E A E E Bb B A
ramp(C7, 11, t(0), t(1), 70, 0)
for k in range(12):
    var = k % 4
    riff = GROOVE2 if k >= 8 else GROOVE
    for bb, s, ln in riff:
        if var == 3 and bb >= 2 and k < 8:
            continue                                                     # the stop: silence after beat 2
        pw = [E2 + s, E2 + s + 7] if s else [E2, E2 + 7, E2 + 12]
        if (E2 + s + 7) % 12 not in KEm.pcs() | {5, 10}:
            pw = [E2 + s, E2 + s + 12]                                   # octaves where a fifth would leave the key
        for c_ in (C3, C8):
            chord(c_, t(k, bb), pw, ln, 114, gate=0.8)
        note(C5, t(k, bb), E2 + s - 12 if E2 + s - 12 >= 28 else E2 + s, ln, 112, gate=0.8)
        drum(t(k, bb), KICK, 116 if bb == 0 else 106)
    drum(t(k, 2), SNARE, 124)
    for i in range(8):
        drum(t(k, i * 0.5), CHINA if i == 0 else (CHH if k < 8 else RIDE), 90 if i == 0 else 74)
    if var == 3 and k < 8:
        note(C1, t(k, 2.25), 88, 1, 112)                                  # pinch squeal in the stop
        bend_curve(C1, t(k, 2.3), t(k, 3), 0, TONE, 8)
        vib(C1, t(k, 3), t(k, 3.4), TONE)
        bend(C1, t(k, 3.5), 0)
        for i in range(6):
            drum(t(k, 3.25 + i / 8), KICK, 110)
    elif var == 1:
        note(C1, t(k, 1.5), 83, 0.5, 108)
        bend_curve(C1, t(k, 1.55), t(k, 1.9), 0, SEMI, 4)
        bend(C1, t(k, 2), 0)
    if k >= 8:                                                           # the twin harmonises the riff tops
        note(C2, t(k, 1.5), [81, 79, 81, 83][k - 8], 0.5, 100)
        note(C2, t(k, 3), [83, 81, 83, 86][k - 8], 1, 104)
    if k in (7, 11):
        fill(k, 2, "kicks", 112)
advance(12)

# ======================================================================================
# 9c Screaming solo - E minor, 100 BPM, 12 bars: long high notes, bends, vibrato, breaths
# ======================================================================================
section(100, key=KEm, name="solo")
ROOTSS = [0, 5, 2, 6, 0, 5, 2, 6, 3, 5, 6, 6]                           # Em C G D  Em C G D  Am C D D
cc(C7, t(0), 11, 60)
ramp(C7, 11, t(0), t(2), 60, 96)
cc(C11, t(0), 11, 60)
# (beat, degree, beats); degree 21 = E6, 24 = A6
SOLO = [
    [(0, 18, .5), (.5, 20, .5), (1, 21, 3)],
    [(0, 21, .5), (.5, 20, .5), (1, 19, 1), (2, 18, .5), (2.5, 16, .5), (3, 17, 1)],
    [(0, 17, 2), (2.5, 16, .5), (3, 14, 1)],
    [(0, 13, .5), (.5, 14, .5), (1, 16, .5), (1.5, 17, .5), (2, 20, 2)],
    [(0, 21, 1 / 3), (1 / 3, 20, 1 / 3), (2 / 3, 18, 1 / 3), (1, 20, 1 / 3), (4 / 3, 18, 1 / 3), (5 / 3, 17, 1 / 3), (2, 16, 2)],
    [(0, 19, 1.5), (1.5, 18, .5), (2, 17, 1), (3, 14, 1)],
    [(0, 16, .25), (.25, 17, .25), (.5, 18, .25), (.75, 20, .25), (1, 21, 3)],
    [(0, 20, 1), (1, 18, .5), (1.5, 17, .5), (2, 16, .5), (2.5, 14, .5), (3, 13, 1)],
    [(0, 17, .5), (.5, 19, .5), (1, 21, 1), (2, 24, 2)],
    [(0, 23, 1.5), (1.5, 21, .5), (2, 19, 1), (3, 17, 1)],
    [(i * 0.25, 13 + i, 0.25) for i in range(8)] + [(2, 20, 2)],
    [(0, 21, 4)],
]
BENDS = {  # bar -> (start beat, end beat, bend) held-note bends (a tone up = TONE; all land in key)
    0: (1.5, 2.0, TONE), 2: (0.25, 0.75, TONE), 3: (2.3, 2.8, TONE), 4: (2.3, 2.8, TONE),
    5: (0.2, 0.6, TONE), 6: (2.0, 2.6, TONE), 8: (2.2, 2.6, TONE), 10: (2.3, 2.8, TONE),
}
for k, r in enumerate(ROOTSS):
    pw = power(KEm, r - 7)
    for c_ in (C3, C8):
        chord(c_, t(k), pw, 3.5, 106, gate=0.97)                           # ringing chords, a push at the end
        chord(c_, t(k, 3.5), pw, 0.5, 104, gate=0.8)
    for i, dd in enumerate([0, 4, 7, 9, 7, 4, 2, 4]):
        note(C12, t(k, i * 0.5), KEm(r + dd), 0.5, 76, gate=1.3)
    note(C5, t(k), KEm(r - 14) if KEm(r - 14) >= 28 else KEm(r - 7), 3, 108)
    note(C5, t(k, 3), KEm(r - 10) if KEm(r - 10) >= 28 else KEm(r - 3), 1, 100)
    chord(C7, t(k), [KEm(r - 7)] + KEm.tri(r), BPB, 72)
    chord(C11, t(k), KEm.tri(r + 7), BPB, 70)
    chord(C6, t(k), [KEm(r - 14)] + KEm.tri(r), BPB, 70)
    drum(t(k), KICK, 116)
    drum(t(k, 1.5), KICK, 104)
    drum(t(k, 2), SNARE, 118)
    drum(t(k, 3.5), KICK, 100)
    for i in range(8):
        drum(t(k, i * 0.5), RIDE if i % 2 == 0 else CHH, 76 if i % 2 == 0 else 60)
    if k % 2 == 0:
        drum(t(k), CRASH, 104)
    if k in (3, 7, 11):
        fill(k, 3, ["down", "triplet", "flams"][k // 4], 106)
    mel(C1, k, KEm, SOLO[k], vel=116, gate=0.98, jitter=3)
    if k in BENDS:
        b0, b1, amt = BENDS[k]
        bend_curve(C1, t(k, b0), t(k, b1), 0, amt, 6)
        vib(C1, t(k, b1), t(k, 3.8 if b1 < 3 else 3.95), amt)
        bend(C1, t(k, 3.97), 0)
    elif SOLO[k][-1][2] >= 2:                                            # vibrato on the other long notes
        vib(C1, t(k, SOLO[k][-1][0] + 0.4), t(k, 3.9), 0, depth=260)
        bend(C1, t(k, 3.97), 0)
bend_curve(C1, t(11, 1), t(11, 2), 0, TONE, 6)                           # the last one: up, hold, then dive
vib(C1, t(11, 2), t(11, 3), TONE, depth=320)
bend_curve(C1, t(11, 3), t(11, 3.95), TONE, -8192, 12)
ramp(C6, 11, t(0), t(12), 40, 90)
ramp(C11, 11, t(4), t(12), 60, 100)
advance(12)
bend(C1, t(0) - 5, 0)

# ======================================================================================
# 9d NWOBHM gallop - E minor, 176 BPM, 16 bars: twin leads in thirds, a flowing solo
# ======================================================================================
section(176, key=KEm, name="gallop")
ROOTS9c = [0, 0, 5, 6, 0, 0, 5, 4, 5, 6, 0, 0, 5, 6, 4, 4]
TWIN = [[(0, 11, 1), (1, 12, 1), (2, 14, 1.5), (3.5, 12, .5)], [(0, 13, 1), (1, 12, 1), (2, 11, 2)],
        [(0, 9, 1), (1, 11, 1), (2, 12, 1.5), (3.5, 11, .5)], [(0, 11, 3), (3, 9, 1)]]
FLOW = [[(0, 14, .5), (.5, 16, .5), (1, 18, 1), (2, 17, .5), (2.5, 16, .5), (3, 14, 1)],
        [(0, 21, 1 / 3), (1 / 3, 20, 1 / 3), (2 / 3, 18, 1 / 3), (1, 20, 1 / 3), (4 / 3, 18, 1 / 3), (5 / 3, 17, 1 / 3), (2, 16, 2)],
        [(0, 18, 2), (2, 20, 1), (3, 18, 1)],
        [(0, 22, 2.5), (3, 21, 1)]]
cc(C6, t(0), 11, 40)
for k, r in enumerate(ROOTS9c):
    root = KEm(r - 7) if KEm(r - 7) >= 40 else KEm(r)
    for bt in range(4):
        for off, vel in ((0, 110), (0.5, 96), (0.75, 98)):
            for c_ in (C3, C8):
                chord(c_, t(k, bt + off), [root, root + 7], 0.25 if off else 0.5, vel, gate=0.7)
            note(C5, t(k, bt + off), root - 12, 0.25 if off else 0.5, vel, gate=0.7)
            drum(t(k, bt + off), KICK, 100)
        drum(t(k, bt), SNARE if bt % 2 else CHH, 112 if bt % 2 else 84)
        drum(t(k, bt), CRASH if (bt == 0 and k % 4 == 0) else (RIDE if k < 8 else CHH), 96 if bt == 0 else 76)
    chord(C7, t(k), KEm.tri(r), BPB, 64)
    if k >= 8:
        chord(C11, t(k), KEm.tri(r + 7), BPB, 70)
    if k % 4 == 3:
        fill(k, 2, ["down", "triplet", "snare", "kicks"][k // 4], 106)
    if 4 <= k < 12:
        mel(C1, k, KEm, TWIN[k % 4], vel=106, gate=0.95)
        mel(C2, k, KEm, TWIN[k % 4], vel=98, shift=-2, gate=0.95)
    elif k >= 12:
        mel(C1, k, KEm, FLOW[k - 12], vel=112, gate=0.96, jitter=3)
        if k == 12:
            bend_curve(C1, t(k, 1.2), t(k, 1.6), 0, SEMI, 4)             # B -> C
            bend(C1, t(k, 1.95), 0)
        elif k == 13:
            bend_curve(C1, t(k, 2.2), t(k, 2.6), 0, TONE, 5)
            vib(C1, t(k, 2.6), t(k, 3.9), TONE)
            bend(C1, t(k, 3.97), 0)
        elif k == 14:
            vib(C1, t(k, 0.4), t(k, 1.95), 0, depth=280)
            bend(C1, t(k, 1.98), 0)
        else:
            vib(C1, t(k, 0.3), t(k, 1.5), 0, depth=300)
            bend_curve(C1, t(k, 1.5), t(k, 2.8), 0, -8192, 16)            # the dive into the anthem
            bend(C1, t(k, 3.95), 0)
ramp(C11, 11, t(8), t(16), 50, 90)
advance(16)

# ======================================================================================
# 9e Priest-style ending - anthem over organ + choir (72), a closing charge (184), final chord
# ======================================================================================
section(72, key=KEm, extra={8}, name="anthem")                          # G# in the final E major chord
KEM = Key(52, "major")
cc(C6, t(0) - 20, 7, 118)
cc(C6, t(0) - 20, 11, 60)
cc(C11, t(0) - 20, 7, 100)
cc(C11, t(0) - 20, 11, 50)
ANTHEM = [[(0, 7, 2), (2, 9, 1), (3, 11, 1)], [(0, 12, 3), (3, 11, 1)], [(0, 13, 2), (2, 14, 2)],
          [(0, 11, 4)], [(0, 12, 2), (2, 13, 1), (3, 14, 1)], [(0, 15, 3), (3, 14, 1)],
          [(0, 13, 2), (2, 12, 1), (3, 13, 1)], [(0, 11, 4)]]
ROOTS9d = [0, 5, 6, 2, 5, 6, 3, 4]
for k, r in enumerate(ROOTS9d):
    pw = [KEm(r - 7), KEm(r - 7) + 7, KEm(r)]
    for c_ in (C3, C8):
        chord(c_, t(k), pw, BPB, 100, gate=0.98)
        cc(c_, t(k), 7, 88)
    note(C5, t(k), KEm(r - 14) if KEm(r - 14) >= 28 else KEm(r - 7), BPB, 104)
    layers = [KEm(r - 14)] + KEm.tri(r - 7) + (KEm.tri(r) if k >= 1 else []) + (KEm.tri(r + 7) if k >= 3 else [])
    if k >= 5:
        layers += [KEm(r + 14)]
    chord(C6, t(k), layers, BPB, 104)
    if k >= 1:
        chord(C11, t(k), KEm.tri(r + 7) if k >= 3 else KEm.tri(r), BPB, 92)
    chord(C7, t(k), KEm.tri(r), BPB, 70)
    mel(C1, k, KEm, ANTHEM[k], vel=108, gate=0.98)
    mel(C2, k, KEm, ANTHEM[k], vel=100, shift=-2, gate=0.98)
    for i, dd in enumerate([0, 2, 4, 7, 4, 2]):
        note(C12, t(k, i * 2 / 3), KEm(r + 7 + dd), 2 / 3, 72, gate=1.2)
    drum(t(k), CRASH if k % 2 == 0 else RIDE, 104)
    drum(t(k), KICK, 112)
    drum(t(k, 2), SNARE, 112)
    for i in range(4):
        drum(t(k, 3 + i * 0.25), TOMS[i % 5] if k % 2 else KICK, 96 + i * 4)
ramp(C6, 11, t(0), t(7), 60, 127)
ramp(C11, 11, t(1), t(7), 50, 127)
advance(8)
section(184, key=KEm, extra={8}, name="charge")
for c_ in (C3, C8):
    cc(c_, t(0), 7, 104)
CHARGE = [0, 0, 5, 6, 0, 0, 5, 4, 3, 5, 6, 4]
for k, r in enumerate(CHARGE):
    root = KEm(r - 7) if KEm(r - 7) >= 40 else KEm(r)
    for i in range(8):
        for c_ in (C3, C8):
            chord(c_, t(k, i * 0.5), [root, root + 7], 0.5, 112 if i % 2 == 0 else 100, gate=0.75)
        note(C5, t(k, i * 0.5), root - 12, 0.5, 108, gate=0.75)
        drum(t(k, i * 0.5), KICK, 104)
        drum(t(k, i * 0.5), CRASH if (i == 0 and k % 2 == 0) else RIDE, 84)
        if k >= 8:
            drum(t(k, i * 0.5 + 0.25), SNARE, 70 + (k - 8) * 8)
    drum(t(k, 1), SNARE, 116)
    drum(t(k, 3), SNARE, 116)
    chord(C6, t(k), [KEm(r - 14)] + KEm.tri(r - 7) + KEm.tri(r) + KEm.tri(r + 7), BPB, 110)
    chord(C11, t(k), KEm.tri(r + 7), BPB, 104)
    chord(C7, t(k), KEm.tri(r), BPB, 76)
    if k < 8:
        mel(C1, k, KEm, [(0, r + 14, 2), (2, r + 11, 2)], vel=108)
        mel(C2, k, KEm, [(0, r + 12, 2), (2, r + 9, 2)], vel=100)
    else:                                                                # a rising unison line into the end
        mel(C1, k, KEm, [(i * 0.5, r + 7 + i, 0.5) for i in range(8)], vel=110)
        mel(C2, k, KEm, [(i * 0.5, r + 5 + i, 0.5) for i in range(8)], vel=102)
    if k == 11:
        fill(k, 2, "down", 116)
advance(12)
section(72, key=KEm, extra={8}, name="final")
end = t(0)
for c_ in (C3, C8):
    chord(c_, end, [40, 47, 52], 3 * BPB, 118, gate=1.0)
note(C5, end, 28, 3 * BPB, 116, gate=1.0)
chord(C6, end, [KEM(-21), KEM(-14)] + KEM.tri(-7) + KEM.tri(0) + KEM.tri(7), 3 * BPB, 116, gate=1.0)
chord(C11, end, KEM.tri(7) + [KEM(14)], 3 * BPB, 110, gate=1.0)
chord(C7, end, KEM.tri(0), 3 * BPB, 90, gate=1.0)
note(C1, end, 76, 3 * BPB, 112, gate=1.0)
note(C2, end, 71, 3 * BPB, 104, gate=1.0)
bend_curve(C1, t(0, 2), t(2), 0, -8192, 32)
drum(end, CRASH, 124)
drum(end, CRASH2, 118)
drum(end, KICK, 124)
for c_ in (C1, C2, C3, C8, C5, C6, C11, C7):
    ramp(c_, 7, t(1, 2), t(3), 110, 0)
end_tick = t(3) + TPB * 2

# ======================================================================================
# checks: notes in key, no program change under a held note, no unintended silence
# ======================================================================================
allow.sort(key=lambda a: a[0])
bad = []
for tk, _o, m in events:
    if m.type != "note_on" or not m.velocity or m.channel == DR:
        continue
    sec = [a for a in allow if a[0] <= tk + 30]
    if not sec:
        continue
    t0, pcs, extra, name = sec[-1]
    if m.note % 12 not in pcs | extra:
        bad.append((name, m.channel + 1, m.note, tk))
if bad:
    print(f"{len(bad)} notes out of key:")
    for b_ in bad[:25]:
        print("   ", b_)
    sys.exit(1)

spans = {}
for tk, _o, m in sorted(events, key=lambda e: (e[0], e[1])):
    if m.type == "note_on" and m.velocity:
        spans.setdefault(m.channel, []).append([tk, None, m.note])
    elif m.type in ("note_on", "note_off"):
        for s_ in spans.get(m.channel, []):
            if s_[1] is None and s_[2] == m.note:
                s_[1] = tk
                break
pc_bad = []
for tk, _o, m in events:
    if m.type == "program_change" and m.channel != DR:
        for s0, s1, n in spans.get(m.channel, []):
            if s0 < tk < (s1 or 1 << 30):
                pc_bad.append((m.channel + 1, m.program, tk, n))
if pc_bad:
    print("program change under a held note:", pc_bad[:10])
    sys.exit(1)

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
    tk += TPB
    tr.append(m.copy(time=max(0, tk - last)))
    last = max(last, tk)
tr.append(mido.MetaMessage("end_of_track", time=max(0, end_tick + TPB - last)))

secs, abs_tick, cur_tempo, quiet_from, gaps, held = 0.0, 0, 500000, 0.0, [], set()
for m in tr:
    secs += mido.tick2second(m.time, TPB, cur_tempo)
    abs_tick += m.time
    if m.type == "set_tempo":
        cur_tempo = m.tempo
    for r0, r1 in rests:
        if r0 + TPB <= abs_tick <= r1 + TPB:
            quiet_from = secs
    if m.type == "note_on" and m.velocity:
        if not held and secs - quiet_from > 1.5 and secs > 3:
            gaps.append((round(quiet_from, 1), round(secs - quiet_from, 1)))
        held.add((m.channel, m.note))
    elif m.type in ("note_off", "note_on"):
        held.discard((m.channel, m.note))
        if not held:
            quiet_from = secs
if gaps:
    print("silences longer than 1.5 s at", gaps)
    sys.exit(1)

# Format 1 for editors: a conductor track (title, GS reset, tempo, meter), then one track per
# channel named after the programs it plays (checked to play exactly what the single track does).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402
mf = common.format1(mf)

out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                            "midi", "onestop2.mid")
os.makedirs(os.path.dirname(out), exist_ok=True)
mf.save(out)
n_on = sum(1 for m in tr if m.type == "note_on" and m.velocity)
print(f"{out}: Format 1, {len(mf.tracks)} tracks (ties kept in order, <= {mf.max_shift} ticks late), {mf.length:.1f} s ({int(mf.length // 60)}:{int(mf.length % 60):02d}), {n_on} notes, "
      f"{sum(1 for m in tr if m.type == 'program_change')} program changes, all in key")
