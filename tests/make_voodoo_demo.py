"""Write "Point & Click Overture", an original ~4.5 minute adventure-game medley for Duality Voodoo.

    python tests/make_voodoo_demo.py [out.mid]     (default tests/midi/point_and_click_overture.mid)

A GM file (GM System On, GM capitals only) written for Voodoo: MT-32 / CM-32L units play it all on
LA, and CM-64s add their PCM half (tables_cm64 picks). Five scenes in the style of LucasArts and
Sierra adventure games, with original tunes (no quotes), joined by sound-effect scene changes:

   Overture           C    80   waves, wind, thunder under the "cursor" motif (music box + pad)
   Monkey Island      C   112   calypso: steel drums and calliope, marimba, nylon guitar, accordion
   (scene change)     Dm   80   car-pass, siren, car-stop, door, footsteps, two pistol shots
   Sam & Max          Dm  132   noir swing: muted trumpet, tenor sax, vibes, trombone, fretless walk,
                                big two-hand piano voicings (the PCM partial-count passage)
   (scene change)     G    80   birds, stream, horse, windchime
   King's Quest       G   108   3/4 storybook: recorder, harpsichord, harp, bassoon, strings, choir,
                                then a brass fanfare with timpani
   (scene change)     Am   80   lasergun, starship, explosion
   Space Quest        Am  120   camp sci-fi march: square + saw leads, synth bass, polysynth, orch
                                hits panned hard left / right, a sci-fi pad sweeping across (pan test)
   (scene change)     F    80   car-stop, creaking door, heartbeat, laughing, applause
   Leisure Suit Larry F   100   lounge swing: alto sax, Rhodes, slap bass, chicken-scratch guitar,
                                organ, brass stabs, a trombone "wah-wah" tag
   Finale             C   112   every scene's motif on all 15 melody channels, applause, a laugh

Voodoo showcase: channel counts grow to all 15 melody channels (one, two and three units); program
changes move channels between LA- and PCM-friendly sounds (ch5 marimba -> vibes -> harp -> polysynth
-> Rhodes -> marimba; ch11 timpani -> orch hit), for live seats vs --cm64-seats fixed; the pan
ping-pong in Space Quest checks the reversed pan on both halves.

Sound effects are CM-32L rhythm keys on ch10: 82-108 as the CM-64 manual lists them (p.11), and the
six that GM percussion covers (76-81) on keys 24-29 (Duality moves them there for CM outs under
Voodoo). Plain MT-32s have none of these; every scene change keeps a melodic bridge, so the build
fails if a sound effect is ever the only thing sounding. Format 1. The build also fails if a note
leaves its section's key, a program change lands under a held note, or on a silence over 1.5 s.
"""
import os
import random
import sys

import mido

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common  # noqa: E402

TPB = 480
rng = random.Random(1990)
events = []          # (tick, order, message)
tempos, sigs, allow, names = [], [], [], []

C1, C2, C3, C4, C5, C6, C7, C8, C9, DR, C11, C12, C13, C14, C15, C16 = range(16)

# CM-32L sound effects (rhythm part). 76-81 move to 24-29 under Duality Voodoo on CM outs.
LAUGH, SCREAM, PUNCH, HEARTBEAT, STEPS1, STEPS2 = 24, 25, 26, 27, 28, 29
(APPLAUSE, CREAK, DOOR, SCRATCH, WINDCHIME, ENGINE, CARSTOP, CARPASS, CRASHFX, SIREN, TRAIN, JET,
 HELI, STARSHIP, PISTOL, MGUN, LASER, EXPLOSION, DOG, HORSE, BIRDS, RAIN, THUNDER, WIND, WAVES,
 STREAM, BUBBLE) = range(82, 109)
SFX = set(range(24, 30)) | set(range(82, 109))

# GM drum keys
KICK, STICK, SNARE, CLAP, CHH, PHH, OHH, CRASH, RIDE, BELL, TAMB, COWBELL = 36, 37, 38, 39, 42, 44, 46, 49, 51, 53, 54, 56
LTOM, MTOM, HTOM, HBONGO, LBONGO, MCONGA, OCONGA, LCONGA, CABASA, MARACAS, CLAVES = 45, 47, 50, 60, 61, 62, 63, 64, 69, 70, 75

MODES = {"major": [0, 2, 4, 5, 7, 9, 11], "minor": [0, 2, 3, 5, 7, 8, 10], "dorian": [0, 2, 3, 5, 7, 9, 10]}
PC_NAMES = {"C": 0, "C#": 1, "Db": 1, "D": 2, "Eb": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "Ab": 8, "A": 9,
            "Bb": 10, "B": 11}
QUAL = {"": [0, 4, 7], "m": [0, 3, 7], "7": [0, 4, 7, 10], "m7": [0, 3, 7, 10], "maj7": [0, 4, 7, 11],
        "6": [0, 4, 7, 9]}


class Key:
    def __init__(self, tonic, mode):
        self.tonic, self.m = tonic, MODES[mode]

    def __call__(self, d, acc=0):
        o, i = divmod(int(d), 7)
        return self.tonic + 12 * o + self.m[i] + acc

    def pcs(self):
        return {(self.tonic + x) % 12 for x in self.m}


def chord_pcs(name):
    root = name[:2] if len(name) > 1 and name[1] in "#b" else name[:1]
    return PC_NAMES[root], QUAL[name[len(root):]]


def voicing(name, low, n=3):
    """Chord tones from `low` upward (close position, n notes). A maj7 leaves its root to the
    bass: a close maj7 puts the 7th a semitone under the root."""
    r, q = chord_pcs(name)
    if name.endswith("maj7"):
        q = [i for i in q if i != 0]
    out, x = [], low
    while len(out) < n:
        if (x - r) % 12 in q:
            out.append(x)
        x += 1
    return out


def bass_root(name, low=36):
    r, _q = chord_pcs(name)
    return low + (r - low) % 12


# --------------------------------------------------------------------------------------
pos = TPB * 4
BPB = 4.0
SWING = False


def section(bpm, key, name, beats=4, extra=(), swing=False):
    global BPB, SWING
    BPB, SWING = float(beats), swing
    tempos.append((pos, bpm))
    sigs.append((pos, int(beats), 4))
    allow.append((pos, key.pcs(), {x % 12 for x in extra}, name))
    names.append((pos, name))


def t(bar, beat=0.0):
    if SWING:
        whole = int(beat)
        frac = beat - whole
        if abs(frac - 0.5) < 1e-6:
            beat = whole + 2 / 3
    return pos + int(round((bar * BPB + beat) * TPB))


def advance(bars):
    global pos
    pos = pos + int(round(bars * BPB * TPB))


def note(ch, tick, n, beats, vel, jitter=3, gate=0.9):
    j = rng.randint(-jitter, jitter) if jitter else 0
    v = max(1, min(127, int(vel) + rng.randint(-3, 3)))
    tk = max(0, tick + j)
    d = max(20, int(beats * TPB * gate))
    events.append((tk, 2, mido.Message("note_on", channel=ch, note=int(n), velocity=v)))
    events.append((tk + d, 0, mido.Message("note_off", channel=ch, note=int(n), velocity=0)))


def chord(ch, tick, notes, beats, vel, roll=0, gate=0.92):
    for i, n in enumerate(notes):
        note(ch, tick + i * roll, n, beats, vel - 2 * i, gate=gate)


def cc(ch, tick, c, v):
    events.append((tick, 1, mido.Message("control_change", channel=ch, control=c, value=max(0, min(127, int(v))))))


def ramp(ch, c, t0, t1, v0, v1, steps=24):
    for k in range(steps + 1):
        cc(ch, t0 + (t1 - t0) * k // steps, c, v0 + (v1 - v0) * k / steps)


def prog(ch, tick, program, vol=100, pan=64, expr=127):
    """Program + mix just before tick (the channel must be silent there; a note on the downbeat
    may be played up to a few ticks early)."""
    tick = max(0, tick - 12)
    events.append((tick, 1, mido.Message("program_change", channel=ch, program=program)))
    cc(ch, tick + 1, 7, vol)
    cc(ch, tick + 1, 10, pan)
    cc(ch, tick + 1, 11, expr)


def drum(tick, n, vel, jitter=3):
    note(DR, tick, n, 0.25, vel, jitter=jitter, gate=1.0)


def sfx(bar, beat, n, vel=110):
    note(DR, t(bar, beat), n, 1.0, vel, jitter=0, gate=1.0)


def line(ch, bar0, key, bars, vel=100, shift=0, octv=0, gate=0.9, legato=False):
    """Melody: one string per bar of 'degree/beats' tokens; 'r' rests, a trailing # or b alters."""
    for i, bar in enumerate(bars):
        beat = 0.0
        for tok in bar.split():
            d, ln = tok.split("/")
            ln = float(ln)
            if d != "r":
                acc = 1 if d.endswith("#") else (-1 if d.endswith("b") else 0)
                deg = int(d.rstrip("#b")) + shift
                n = key(deg, acc) + 12 * octv
                tk = t(bar0 + i, beat)
                end = t(bar0 + i, beat + ln)
                note(ch, tk, n, (end - tk) / TPB, vel + rng.randint(-4, 4), gate=0.98 if legato else gate)
            beat += ln
        assert abs(beat - BPB) < 1e-6, f"bar {i} of a line has {beat} beats: {bar}"


def bridge(key, chords, vel=84):
    """The scene-change 'cursor' motif on the music box over the pad: 4 bars, the next scene's key.
    Plain MT-32s hear this alone; CM units add the sound effects."""
    line(C13, 0, key, ["0/.5 2/.5 4/.5 7/1.5 6/1", "4/.5 2/.5 1/1 0/2", "0/.5 2/.5 4/.5 9/1.5 8/1", "7/4"], vel)
    for b, name in enumerate(chords):
        chord(C9, t(b), voicing(name, 55, 4), 4, 70, gate=1.0)
        note(C9, t(b), bass_root(name, 36), 4, 64, gate=1.0)


# ======================================================================================
# setup burst: every channel's first program at the start (like a game's MIDI file)
# ======================================================================================
FIRST = {
    C1: (82, 96, 70),    # calliope lead
    C2: (114, 104, 52),  # steel drums
    C3: (24, 92, 40),    # nylon guitar
    C4: (32, 104, 64),   # acoustic bass
    C5: (12, 90, 84),    # marimba
    C6: (48, 92, 50),    # strings
    C7: (61, 96, 76),    # brass section
    C8: (52, 88, 60),    # choir aahs
    C9: (89, 78, 64),    # warm pad (bridges)
    C11: (47, 100, 64),  # timpani
    C12: (24, 88, 90),   # nylon guitar 2
    C13: (10, 100, 64),  # music box (bridges)
    C14: (98, 82, 64),   # crystal / sci-fi
    C15: (57, 92, 44),   # trombone
    C16: (21, 86, 96),   # accordion
}
for ch, (p, v, pan) in FIRST.items():
    prog(ch, 0, p, v, pan)
cc(DR, 1, 7, 110)

KC = Key(60, "major")
KCm = Key(72, "major")          # steel drums / calliope register
KD = Key(62, "dorian")
KDl = Key(50, "dorian")
KG = Key(67, "major")
KGl = Key(55, "major")
KA = Key(69, "minor")
KAl = Key(57, "minor")
KF = Key(65, "major")

# ======================================================================================
# Overture: waves, wind, thunder
# ======================================================================================
section(80, KC, "Overture", extra=())
bridge(KC, ["C", "F", "G", "C"])
sfx(0, 0, WAVES, 104)
sfx(1, 0, WIND, 96)
sfx(2, 0, WAVES, 108)
sfx(3, 0, THUNDER, 112)
advance(4)

# ======================================================================================
# Monkey Island: calypso, C major, 112
# ======================================================================================
section(112, KC, "Monkey Island (calypso)")
MI = ["C", "F", "G", "C", "Am", "F", "G", "C"]
MI_A = ["4/.5 4/.5 5/.5 4/1 2/.5 0/1", "3/.5 5/.5 7/1 5/.5 3/.5 2/1",
        "4/.5 6/.5 8/1.5 6/.5 4/1", "7/1.5 4/.5 2/2"]
MI_B = ["5/.5 7/.5 9/1 7/.5 5/.5 4/1", "3/.5 5/.5 7/.5 8/.5 7/1 5/1",
        "4/1 6/.5 8/.5 11/1 8/1", "7/3 r/1"]


def calypso_bar(b, name, full=True):
    root = bass_root(name, 36)
    note(C4, t(b, 0), root, 1.5, 100)
    note(C4, t(b, 1.5), root + 7, 1.0, 92)
    note(C4, t(b, 2.5), root + 12 if b % 2 else root, 1.5, 96)
    for off in (0.5, 1.5, 2.5, 3.5):                       # marimba offbeats
        chord(C5, t(b, off), voicing(name, 64, 3), 0.4, 78)
    for off, v in ((0, 86), (1, 70), (1.5, 74), (2.5, 80), (3, 70), (3.5, 74)):   # guitar strum
        chord(C3, t(b, off), voicing(name, 52, 4), 0.38, v, roll=12)
    # drums: kick 1 + 3, side stick, son clave, congas, maracas
    drum(t(b, 0), KICK, 98)
    drum(t(b, 2), KICK, 90)
    for off in ((0, 1.5, 3) if b % 2 == 0 else (1, 2)):
        drum(t(b, off), CLAVES, 92)
    drum(t(b, 1), STICK, 76)
    drum(t(b, 3), STICK, 80)
    for off, n in ((0.5, MCONGA), (1, OCONGA), (2.5, MCONGA), (3, LCONGA), (3.5, OCONGA)):
        drum(t(b, off), n, 84)
    for k in range(8):
        drum(t(b, k * 0.5), MARACAS, 58 + (12 if k % 2 == 0 else 0))
    if full and b % 4 == 0:
        chord(C16, t(b), voicing(name, 60, 3), 4, 66, gate=0.98)


for b in range(20):
    calypso_bar(b, MI[b % 8], full=b >= 12)
line(C2, 4, KCm, MI_A + MI_B, 104)                         # steel drums: the tune
line(C1, 12, KCm, MI_A + MI_B, 92, octv=0)                  # calliope takes it ...
line(C2, 12, KCm, MI_A + MI_B, 90, shift=-2)                # ... steel drums a third below
drum(t(19, 3), CRASH, 100)
advance(20)

# ======================================================================================
# scene change -> Sam & Max: car, siren, door, footsteps, pistol
# ======================================================================================
section(80, KD, "Scene change: the street", extra=(1,))
prog(C3, pos, 0, 96, 40)        # nylon guitar -> piano
prog(C4, pos, 35, 104, 64)      # acoustic -> fretless bass
prog(C5, pos, 11, 84, 90)       # marimba -> vibes
prog(C1, pos, 59, 100, 70)      # calliope -> muted trumpet
prog(C2, pos, 66, 98, 50)       # steel drums -> tenor sax
bridge(KD, ["Dm", "G", "Em", "Dm"])
sfx(0, 0, CARPASS)
sfx(0, 2, SIREN, 100)
sfx(1, 1, CARSTOP)
sfx(2, 0, DOOR)
sfx(2, 1, STEPS1, 96)
sfx(2, 2, STEPS2, 96)
sfx(2, 3, STEPS1, 96)
sfx(3, 2, PISTOL, 118)
sfx(3, 3, PISTOL, 118)
advance(4)

# ======================================================================================
# Sam & Max: noir swing, D dorian, 132
# ======================================================================================
section(132, KD, "Sam & Max (noir swing)", extra=(1,), swing=True)    # C# in the A7
SM = ["Dm7", "G7", "Dm7", "G7", "Em7", "A7", "Dm7", "A7"]
SM_T = ["r/1 4/.5 6/.5 7/1 6/.5 4/.5", "3/1.5 5/.5 4/1 2/1", "0/.5 2/.5 4/.5 7/1.5 6/1", "5/2 r/2",
        "1/.5 3/.5 5/.5 8/1.5 7/1", "4/.5 6#/.5 8/1 6#/1 4/1", "7/1.5 5/.5 4/1 2/1", "1/2 -1#/1 r/1"]
WALK = {"Dm7": [38, 41, 45, 48], "G7": [43, 47, 50, 41], "Em7": [40, 43, 47, 50], "A7": [45, 49, 52, 43]}
BIG = {   # two-hand piano voicings (A.PIANO 1 on PCM is 2 partials a note)
    # chord tones only, below the tune (the first cut packed 9ths / 13ths into the middle,
    # where the tenor played the tune, and sounded atonal)
    "Dm7": [38, 45, 50, 53, 57, 60], "G7": [43, 50, 53, 55, 59, 62],
    "Em7": [40, 47, 50, 55, 59, 62], "A7": [45, 52, 55, 57, 61, 64],
}


def swing_bar(b, name, big=False):
    for k, n in enumerate(WALK[name]):
        note(C4, t(b, k), n, 1, 96 if k == 0 else 86, gate=0.95)
    if big:
        chord(C3, t(b, 0), BIG[name], 1.5, 84, roll=6)
        chord(C3, t(b, 1.5), BIG[name], 2.0, 76, roll=6)
    else:
        chord(C3, t(b, 0), voicing(name, 53, 4), 1.0, 72)
        chord(C3, t(b, 1.5), voicing(name, 53, 4), 0.5, 66)
    for off, v in ((0, 74), (1, 70), (1.5, 58), (2, 74), (3, 70), (3.5, 58)):
        drum(t(b, off), RIDE, v)
    drum(t(b, 1), PHH, 60)
    drum(t(b, 3), PHH, 60)
    drum(t(b, 0), KICK, 54)
    drum(t(b, 2.5), SNARE, 40)
    drum(t(b, 3.5), SNARE, 34)


for b in range(20):
    swing_bar(b, SM[b % 8], big=b >= 12)
    if 4 <= b < 12 and b % 2 == 0:
        chord(C5, t(b, 0), voicing(SM[b % 8], 65, 4), 2, 70, roll=40)    # vibes (first half)
line(C1, 4, KD, SM_T, 104)                                    # muted trumpet
line(C2, 12, KD, SM_T, 98)                                     # tenor sax takes the tune, above the piano
for b in range(12, 20):                                        # trombone guide tones
    r, q = chord_pcs(SM[b % 8])
    note(C15, t(b), 48 + (r + q[1] - 48) % 12, 4, 76, gate=0.97)
drum(t(19, 3), CRASH, 92)
advance(20)

# ======================================================================================
# scene change -> King's Quest: birds, stream, horse, windchime
# ======================================================================================
section(80, KG, "Scene change: the meadow")
prog(C1, pos, 74, 100, 64)      # muted trumpet -> recorder
prog(C2, pos, 73, 90, 50)       # tenor sax -> flute
prog(C3, pos, 6, 92, 40)        # piano -> harpsichord
prog(C4, pos, 70, 96, 64)       # fretless -> bassoon
prog(C5, pos, 46, 92, 84)       # vibes -> harp
bridge(KG, ["G", "C", "D", "G"])
sfx(0, 0, BIRDS, 100)
sfx(0, 2, STREAM, 90)
sfx(1, 1, HORSE, 104)
sfx(2, 0, BIRDS, 104)
sfx(2, 2, STREAM, 90)
sfx(3, 0, WINDCHIME, 96)
advance(4)

# ======================================================================================
# King's Quest: storybook, G major, 3/4 at 108
# ======================================================================================
section(108, KG, "King's Quest (storybook)", beats=3)
KQ = ["G", "C", "D", "G", "Em", "C", "D", "G"]
KQ_T = ["4/1 2/.5 3/.5 4/1", "5/1.5 4/.5 3/1", "1/.5 2/.5 3/1 -1/1", "0/2 r/1",
        "2/1 4/.5 5/.5 7/1", "5/.5 4/.5 3/1 2/1", "1/1 4/1 6/1", "7/2 r/1"]


def kq_bar(b, name, part):
    lo = voicing(name, 55, 3)
    arp = lo + [lo[1] + 12, lo[2] + 12, lo[1] + 12]
    for k, n in enumerate(arp):
        note(C3, t(b, k * 0.5), n, 0.5, 74 + (8 if k == 0 else 0))
    note(C4, t(b, 0), bass_root(name, 43), 2, 90)
    note(C4, t(b, 2), bass_root(name, 43) + 7, 1, 80)
    if b % 2 == 0:
        chord(C5, t(b, 0), voicing(name, 60, 4), 3, 74, roll=30)        # harp roll
    drum(t(b, 0), LTOM, 70)
    drum(t(b, 1.5), SNARE, 46)
    drum(t(b, 2), TAMB, 56)
    if part >= 1:
        chord(C6, t(b), voicing(name, 55, 4), 3, 74, gate=0.99)          # strings
        if b % 2 == 0:
            chord(C8, t(b), voicing(name, 60, 3), 6, 70, gate=0.98)      # choir
    if part >= 2:
        note(C11, t(b, 0), bass_root(name, 43), 1, 96)                  # timpani
        if b % 8 == 7:
            for k in range(6):
                note(C11, t(b, 1 + k / 3), bass_root(name, 43), 1 / 3, 70 + 6 * k)


for b in range(24):
    kq_bar(b, KQ[b % 8], b // 8)
line(C1, 0, KG, KQ_T, 98)                                     # recorder
line(C1, 8, KG, KQ_T, 100)
line(C2, 8, KG, KQ_T, 82, shift=-2)                           # flute a third below
for i in range(8):                                            # brass fanfare: the tune in triads
    bar = KQ_T[i]
    line(C7, 16 + i, KGl, [bar], 104)
    line(C7, 16 + i, KGl, [bar], 96, shift=-2)
line(C1, 16, KG, KQ_T, 104, octv=1)
advance(24)

# ======================================================================================
# scene change -> Space Quest: lasers, a starship, an explosion
# ======================================================================================
section(80, KA, "Scene change: orbit", extra=(8,))
prog(C1, pos, 80, 96, 64)       # recorder -> square lead
prog(C2, pos, 81, 90, 50)       # flute -> saw lead
prog(C4, pos, 38, 104, 64)      # bassoon -> synth bass
prog(C5, pos, 90, 86, 84)       # harp -> polysynth
prog(C11, pos, 55, 100, 20)     # timpani -> orch hit
prog(C14, pos, 103, 84, 0)      # crystal -> sci-fi
prog(C16, pos, 62, 88, 96)      # accordion -> synth brass
bridge(KA, ["Am", "F", "G", "E"])
sfx(0, 0, LASER, 104)
sfx(0, 1, LASER, 104)
sfx(0, 1.5, LASER, 104)
sfx(1, 0, STARSHIP, 108)
sfx(3, 0, EXPLOSION, 120)
advance(4)

# ======================================================================================
# Space Quest: camp sci-fi march, A minor, 120
# ======================================================================================
section(120, KA, "Space Quest (sci-fi march)", extra=(8,))   # G# in the E chord
SQ = ["Am", "F", "G", "E", "Am", "F", "Dm", "E"]
SQ_T = ["0/.75 0/.25 4/1 2/1 0/1", "5/.75 5/.25 7/1 5/1 2/1", "6/.75 4/.25 1/1 4/1 6/1",
        "4/2 6#/1 4/1", "7/.75 7/.25 9/1 7/1 4/1", "8/.75 7/.25 5/1 2/1 5/1",
        "3/1 5/1 7/.5 8/.5 10/1", "4/1.5 3/.5 1/1 -1#/1"]


def march_bar(b, name, tutti):
    root = bass_root(name, 33)
    for k in range(8):
        note(C4, t(b, k * 0.5), root + (12 if k % 2 else 0), 0.5, 92)
    chord(C5, t(b, 0), voicing(name, 60, 4), 0.9, 78)
    chord(C5, t(b, 2), voicing(name, 60, 4), 0.9, 74)
    drum(t(b, 0), KICK, 100)
    drum(t(b, 2), KICK, 96)
    for k in range(4):
        drum(t(b, k + 0.5), SNARE, 70)
    for k in range(4):
        drum(t(b, 3 + k * 0.25), SNARE, 64 + 8 * k)
    note(C11, t(b, 0), root + 24, 0.5, 104)                     # orch hit
    if tutti:
        note(C11, t(b, 1.5), root + 24, 0.5, 92)
        chord(C6, t(b), voicing(name, 57, 4), 4, 76, gate=0.99)  # strings
        chord(C8, t(b), voicing(name, 57, 3), 4, 70, gate=0.99)  # choir
        chord(C7, t(b, 0), voicing(name, 55, 3), 0.5, 100)       # brass stabs
        chord(C7, t(b, 1.5), voicing(name, 55, 3), 0.5, 94)
        note(C16, t(b), voicing(name, 60, 3)[2], 4, 80, gate=0.98)   # synth brass top note


for b in range(20):
    march_bar(b, SQ[b % 8], b >= 12)
    # pan ping-pong: orch hits hard left / right every bar (both halves pan reversed on LA/PCM)
    cc(C11, t(b) - 4, 10, 10 if b % 2 == 0 else 117)
line(C1, 4, KA, SQ_T, 102)                                    # square lead
line(C1, 12, KA, SQ_T, 104)
line(C2, 12, KA, SQ_T, 92, shift=-2)                          # saw lead a third below
for b in range(0, 20, 4):                                     # sci-fi pad, sweeping across
    note(C14, t(b), bass_root(SQ[b % 8], 57), 16, 72, gate=0.99)
    note(C14, t(b), bass_root(SQ[b % 8], 57) + 7, 16, 66, gate=0.99)
ramp(C14, 10, t(0), t(8), 0, 127, 32)
ramp(C14, 10, t(8), t(16), 127, 0, 32)
ramp(C14, 10, t(16), t(20) - 8, 0, 64, 16)
drum(t(19, 3), CRASH, 104)
advance(20)

# ======================================================================================
# scene change -> Leisure Suit Larry: car-stop, creaking door, heartbeat, a laugh, applause
# ======================================================================================
section(80, KF, "Scene change: the lounge")
prog(C1, pos, 65, 100, 64)      # square lead -> alto sax
prog(C4, pos, 36, 104, 64)      # synth bass -> slap bass
prog(C5, pos, 4, 92, 84)        # polysynth -> Rhodes
prog(C12, pos, 27, 84, 100)     # nylon guitar 2 -> clean guitar
prog(C16, pos, 16, 84, 30)      # synth brass -> organ
cc(C11, pos + 2, 10, 64)
bridge(KF, ["F", "Dm", "Gm", "C"])
sfx(0, 0, CARSTOP)
sfx(1, 0, CREAK, 100)
sfx(1, 2, DOOR)
sfx(2, 0, HEARTBEAT, 100)
sfx(2, 1, HEARTBEAT, 100)
sfx(2, 2, LAUGH, 108)
sfx(3, 1, APPLAUSE, 96)
advance(4)

# ======================================================================================
# Leisure Suit Larry: lounge swing, F major, 100
# ======================================================================================
section(100, KF, "Leisure Suit Larry (lounge)", swing=True)
LS = ["Fmaj7", "Dm7", "Gm7", "C7"]
LS_T = ["r/.5 4/.5 2/.5 4/1.5 6/1", "5/.5 4/.5 2/1 0/2", "1/.5 3/.5 5/1.5 4/.5 3/1", "2/1 4/.5 6/.5 1/2",
        "7/1.5 6/.5 4/1 2/1", "5/.5 7/.5 9/1 7/1 5/1", "8/1.5 7/.5 5/1 3/1", "4/3 r/1"]


def lounge_bar(b, name, tag):
    r, q = chord_pcs(name)
    root = 36 + (r - 36) % 12
    for off, n, v in ((0, root, 100), (1.5, root + 12, 92), (2, root + 7, 90), (3.5, root + 12, 92)):
        note(C4, t(b, off), n, 0.45, v)
    chord(C5, t(b, 0), voicing(name, 57, 4), 1.2, 76)            # Rhodes Charleston
    chord(C5, t(b, 1.5), voicing(name, 57, 4), 0.6, 70)
    chord(C12, t(b, 1), voicing(name, 64, 3), 0.2, 72)           # chicken scratch on 2 and 4
    chord(C12, t(b, 3), voicing(name, 64, 3), 0.2, 72)
    for off, v in ((0, 70), (1, 66), (1.5, 52), (2, 70), (3, 66), (3.5, 52)):
        drum(t(b, off), CHH, v)
    drum(t(b, 0), KICK, 86)
    drum(t(b, 2), KICK, 80)
    drum(t(b, 1), STICK, 78)
    drum(t(b, 3), STICK, 82)
    if tag:
        chord(C16, t(b), voicing(name, 55, 4), 4, 72, gate=0.99)    # organ
        chord(C7, t(b, 3.5), voicing(name, 58, 3), 0.4, 96)         # brass stab
        note(C15, t(b), 48 + (r + q[1] - 48) % 12, 3.5, 74)


for b in range(16):
    lounge_bar(b, LS[b % 4], b >= 8)
line(C1, 4, KF, LS_T, 104)                                    # alto sax
line(C1, 12, KF, LS_T[:4], 108)
advance(16)
section(100, KF, "Larry tag (wah-wah)", extra=(11,))   # the trombone slides down C, B, Bb, A
for k, n in enumerate((60, 59, 58)):
    note(C15, t(0, k * 1.0), n, 0.9, 100, jitter=0)
    cc(C15, t(0, k * 1.0), 11, 127)
    ramp(C15, 11, t(0, k + 0.3), t(0, k + 0.85), 127, 70, 6)
note(C15, t(0, 3), 57, 3.9, 104, jitter=0)
cc(C15, t(0, 3), 11, 127)
ramp(C15, 11, t(1), t(1, 3), 127, 40, 12)
chord(C5, t(1), voicing("Fmaj7", 57, 4), 3.5, 70)
note(C4, t(1), 41, 3.5, 92)
drum(t(1, 0), CRASH, 70)
cc(C15, t(2), 11, 127)
advance(2)

# ======================================================================================
# Finale: every scene's motif, all 15 melody channels, C major 112
# ======================================================================================
section(112, KC, "Finale", extra=())
prog(C1, pos, 80, 96, 64)       # alto sax -> square lead (Space Quest)
prog(C2, pos, 114, 100, 52)     # flute -> steel drums (Monkey Island)
prog(C3, pos, 0, 92, 40)        # harpsichord -> piano
prog(C4, pos, 32, 104, 64)      # slap -> acoustic bass
prog(C5, pos, 12, 88, 84)       # Rhodes -> marimba
prog(C12, pos, 24, 86, 100)     # clean -> nylon guitar
prog(C13, pos, 9, 92, 70)       # music box -> glockenspiel (King's Quest)
prog(C14, pos, 98, 80, 40)      # sci-fi -> crystal
prog(C15, pos, 59, 98, 80)      # trombone -> muted trumpet (Sam & Max)
prog(C16, pos, 65, 96, 30)      # organ -> alto sax (Larry)
FN = ["C", "F", "G", "C"] * 3
for b in range(12):
    name = FN[b]
    calypso_bar(b, name, full=False)
    chord(C3, t(b), voicing(name, 55, 4), 4, 70, gate=0.98)
    chord(C12, t(b, 0), voicing(name, 52, 4), 1.9, 66, roll=10)
    chord(C12, t(b, 2), voicing(name, 52, 4), 1.9, 62, roll=10)
    chord(C9, t(b), voicing(name, 55, 4), 4, 62, gate=1.0)
    if b >= 4:
        chord(C6, t(b), voicing(name, 55, 4), 4, 72, gate=0.99)
        chord(C8, t(b), voicing(name, 60, 3), 4, 66, gate=0.99)
        chord(C7, t(b, 0), voicing(name, 55, 3), 0.5, 92)
        note(C11, t(b, 0), bass_root(name, 36) + 24, 0.5, 96)
    for k in range(8):
        note(C14, t(b, k * 0.5), voicing(name, 72, 3)[k % 3], 0.5, 58)
line(C2, 0, KCm, MI_A, 104)                                   # Monkey Island
line(C15, 4, KC, ["r/1 4/.5 6/.5 7/1 6/.5 4/.5", "3/1.5 5/.5 4/1 2/1"], 100)       # Sam & Max
line(C16, 6, KC, ["r/.5 4/.5 2/.5 4/1.5 6/1", "5/.5 4/.5 2/1 0/2"], 100)            # Larry
line(C13, 8, KCm, [b_ + " r/1" for b_ in KQ_T[:4]], 96)       # King's Quest, a beat longer in 4/4
advance(12)
section(112, KC, "Finale: last chord")
end = t(0)
chord(C3, end, [36, 48, 55, 60, 64, 67, 72], 8, 100, gate=1.0)
chord(C6, end, [48, 55, 60, 64, 67], 8, 90, gate=1.0)
chord(C8, end, [60, 64, 67], 8, 84, gate=1.0)
chord(C7, end, [55, 60, 64, 67], 8, 100, gate=1.0)
chord(C9, end, [48, 55, 64, 67], 8, 70, gate=1.0)
chord(C16, end, [64, 67, 72], 8, 90, gate=1.0)
note(C1, end, 84, 8, 100, gate=1.0)
note(C2, end, 84, 2, 100)
note(C15, end, 76, 8, 92, gate=1.0)
note(C4, end, 36, 8, 104, gate=1.0)
note(C11, end, 60, 1, 110)
note(C13, end, 84, 4, 90)
note(C5, end, 72, 2, 90)
note(C12, end, 52, 6, 80, gate=1.0)
note(C14, end, 96, 4, 60)
drum(end, CRASH, 116)
drum(end, KICK, 116)
sfx(0, 2, APPLAUSE, 104)
sfx(1, 0, APPLAUSE, 110)
sfx(1, 2, LAUGH, 108)
for c_ in (C1, C3, C4, C6, C7, C8, C9, C12, C15, C16):
    ramp(c_, 7, t(1), t(2), 100, 0, 16)
end_tick = t(2) + TPB * 2

# ======================================================================================
# checks
# ======================================================================================
allow.sort(key=lambda a: a[0])
bad = []
for tk, _o, m in events:
    if m.type != "note_on" or not m.velocity or m.channel == DR:
        continue
    sec = [a for a in allow if a[0] <= tk + 30]
    t0, pcs, extra, name = sec[-1]
    if m.note % 12 not in pcs | extra:
        bad.append((name, m.channel + 1, m.note, tk))
if bad:
    PCN = "C C# D D# E F F# G G# A A# B".split()
    seen = {}
    for name, ch_, n_, tk in bad:
        seen.setdefault(name, {}).setdefault((ch_, PCN[n_ % 12]), tk)
    for name, hits in seen.items():
        print("out of key", name + ":", ", ".join(f"ch{c} {p} @{tk}" for (c, p), tk in sorted(hits.items())))
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
pc_bad = [(m.channel + 1, m.program, tk) for tk, _o, m in events if m.type == "program_change"
          for s0, s1, n in spans.get(m.channel, []) if s0 < tk < (s1 or 1 << 30)]
if pc_bad:
    print("program change under a held note:", pc_bad[:10])
    sys.exit(1)

meta = [(tk, 0, mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm))) for tk, bpm in tempos]
meta += [(tk, 0, mido.MetaMessage("time_signature", numerator=n, denominator=d)) for tk, n, d in sigs]
meta += [(tk, 0, mido.MetaMessage("marker", text=nm)) for tk, nm in names]
allev = sorted(meta + events, key=lambda e: (e[0], e[1]))
mf = mido.MidiFile(ticks_per_beat=TPB)
tr = mido.MidiTrack()
mf.tracks.append(tr)
tr.append(mido.MetaMessage("track_name", name="Point & Click Overture", time=0))
tr.append(mido.Message("sysex", data=[0x7E, 0x7F, 0x09, 0x01], time=0))       # GM System On
last = 0
for tk, _o, m in allev:
    tk += TPB
    tr.append(m.copy(time=max(0, tk - last)))
    last = max(last, tk)
tr.append(mido.MetaMessage("end_of_track", time=max(0, end_tick + TPB - last)))

# silences (plain MT-32s: sound effects do not count, they have none)
secs, cur_tempo, quiet_from, gaps, held = 0.0, 500000, 0.0, [], set()
for m in tr:
    secs += mido.tick2second(m.time, TPB, cur_tempo)
    if m.type == "set_tempo":
        cur_tempo = m.tempo
    if m.type not in ("note_on", "note_off") or (m.channel == DR and m.note in SFX):
        continue
    if m.type == "note_on" and m.velocity:
        if not held and secs - quiet_from > 1.5 and secs > 3:
            gaps.append((round(quiet_from, 1), round(secs - quiet_from, 1)))
        held.add((m.channel, m.note))
    else:
        held.discard((m.channel, m.note))
        if not held:
            quiet_from = secs
if gaps:
    print("silences longer than 1.5 s (without the sound effects) at", gaps)
    sys.exit(1)

mf = common.format1(mf)
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "midi", "point_and_click_overture.mid")
os.makedirs(os.path.dirname(out), exist_ok=True)
mf.save(out)
n_on = sum(1 for m in tr if m.type == "note_on" and m.velocity)
n_fx = sum(1 for m in tr if m.type == "note_on" and m.velocity and m.channel == DR and m.note in SFX)
chs = sorted({m.channel + 1 for m in tr if m.type == "note_on" and m.channel != DR})
print(f"{out}: Format 1, {len(mf.tracks)} tracks, {mf.length:.1f} s ({int(mf.length // 60)}:"
      f"{int(mf.length % 60):02d}), {n_on} notes ({n_fx} sound effects), "
      f"{sum(1 for m in tr if m.type == 'program_change')} program changes, melody channels {chs}, all in key")
