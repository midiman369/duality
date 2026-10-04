"""Write "The Hint Line", an original ~4 minute adventure-game story medley for Duality Voodoo.

    python tests/make_voodoo_demo3.py [out.mid]     (default tests/midi/the_hint_line.mid)

The third Voodoo demo (after make_voodoo_demo.py and make_voodoo_demo2.py). A GM file (GM System
On, GM capitals) told as a call to a game hint line: the phone rings, the operator answers, and the
hold music is the Wanderer, one original tune that then travels through five worlds, each with its
own key, metre, groove and orchestration. Between worlds the hold music comes back for two bars
under that world's sound effects; the finale hands the tune to all 15 melody channels, and the
phone rings again.

   The Hint Line      F   100/130  telephone, the operator (voice), bossa hold music (E.Piano 2, vibes)
   Monkey Island      D   126 6/8  pirate hornpipe: fiddle, banjo, accordion, tin whistle, bodhran
   Sam & Max          A   164      rockabilly road trip: twangy guitar, slap bass, boogie piano, a
                                   honking tenor sax
   King's Quest       Bb   76      royal procession: trumpet fanfare, French horn, brass, church
                                   organ, choir, timpani, a snare roll
   Space Quest        Cm  160      action chase: synth bass, string ostinato, saw lead, brass and
                                   orch hits (dominant V, the leading tone raised)
   Leisure Suit Larry G   124      cha-cha: piano montuno, tumbao bass, congas, cowbell, guiro, alto
                                   sax, flute, mambo brass
   Finale             C   108-80   the Wanderer triumphant on every channel, bells, a broad ending,
                                   then the phone rings again and someone laughs

Sound effects are CM-32L rhythm keys on ch10 (82-108; 24-29 for the six Duality moves there under
Voodoo); plain MT-32s hear the hold music alone (the build checks no effect is ever the only
sound). Format 1. The build fails if a note leaves its section's key, a program change lands
under a held note, or on a silence over 1.5 s.
"""
import os
import random
import sys

import mido

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common  # noqa: E402

TPB = 480
rng = random.Random(1993)
events = []
tempos, sigs, allow, names = [], [], [], []

C1, C2, C3, C4, C5, C6, C7, C8, C9, DR, C11, C12, C13, C14, C15, C16 = range(16)

LAUGH, SCREAM, PUNCH, HEARTBEAT, STEPS1, STEPS2 = 24, 25, 26, 27, 28, 29
(APPLAUSE, CREAK, DOOR, SCRATCH, WINDCHIME, ENGINE, CARSTOP, CARPASS, CRASHFX, SIREN, TRAIN, JET,
 HELI, STARSHIP, PISTOL, MGUN, LASER, EXPLOSION, DOG, HORSE, BIRDS, RAIN, THUNDER, WIND, WAVES,
 STREAM, BUBBLE) = range(82, 109)
SFX = set(range(24, 30)) | set(range(82, 109))

KICK, STICK, SNARE, CLAP, CHH, PHH, OHH, CRASH, RIDE, TAMB, COWBELL = 36, 37, 38, 39, 42, 44, 46, 49, 51, 54, 56
LFTOM, LTOM, MTOM, HTOM = 41, 45, 47, 50
HBONGO, LBONGO, MCONGA, OCONGA, LCONGA, HTIMB, LTIMB, CABASA, SGUIRO, LGUIRO = 60, 61, 62, 63, 64, 65, 66, 69, 73, 74

MODES = {"major": [0, 2, 4, 5, 7, 9, 11], "minor": [0, 2, 3, 5, 7, 8, 10]}


class Key:
    def __init__(self, tonic, mode="major"):
        self.tonic, self.mode, self.m = tonic, mode, MODES[mode]

    def __call__(self, d, acc=0):
        o, i = divmod(int(d), 7)
        return self.tonic + 12 * o + self.m[i] + acc

    def at(self, tonic):
        return Key(tonic, self.mode)

    def pcs(self):
        return {(self.tonic + x) % 12 for x in self.m}

    @property
    def minorish(self):
        return self.mode != "major"


# --------------------------------------------------------------------------------------
pos = TPB * 4
BPB = 4.0
SWING = False


def section(bpm, key, name, beats=4, den=4, swing=False, extra=()):
    """beats = quarter notes a bar (6/8 = 3)."""
    global BPB, SWING
    BPB, SWING = float(beats), swing
    tempos.append((pos, bpm))
    sigs.append((pos, 6 if den == 8 else int(beats), den))
    ex = {x % 12 for x in extra}
    if key.minorish:
        ex.add((key.tonic - 1) % 12)
    allow.append((pos, key.pcs(), ex, name))
    names.append((pos, name))


def tempo(bar, bpm):
    tempos.append((t(bar), bpm))


def t(bar, beat=0.0):
    if SWING:
        whole = int(beat)
        if abs(beat - whole - 0.5) < 1e-6:
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
    """Program + mix just before tick (the channel must be silent there)."""
    tick = max(0, tick - 12)
    events.append((tick, 1, mido.Message("program_change", channel=ch, program=program)))
    cc(ch, tick + 1, 7, vol)
    cc(ch, tick + 1, 10, pan)
    cc(ch, tick + 1, 11, expr)


def drum(tick, n, vel, jitter=3):
    note(DR, tick, n, 0.25, vel, jitter=jitter, gate=1.0)


def sfx(bar, beat, n, vel=110):
    note(DR, t(bar, beat), n, 1.0, vel, jitter=0, gate=1.0)


def line(ch, bar0, key, bars, vel=100, shift=0, gate=0.9):
    """Melody bars of 'degree/beats' tokens ('r' rests, # / b alter). A bar given as (string, V)
    with V true sits on a dominant: in a minor key the leading tone is raised (harmony lines too)."""
    for i, bar in enumerate(bars):
        lt = False
        if isinstance(bar, tuple):
            bar, onv = bar
            lt = key.minorish and onv
        beat = 0.0
        for tok in bar.split():
            d, ln = tok.split("/")
            ln = float(ln)
            if d != "r":
                acc = 1 if d.endswith("#") else (-1 if d.endswith("b") else 0)
                deg = int(d.rstrip("#b")) + shift
                if lt and deg % 7 == 6:
                    acc += 1
                tk = t(bar0 + i, beat)
                end = t(bar0 + i, beat + ln)
                note(ch, tk, key(deg, acc), (end - tk) / TPB, vel + rng.randint(-4, 4), gate=gate)
            beat += ln
        assert abs(beat - BPB) < 1e-6, f"bar {i}: {beat} beats in {bar!r}"


# --------------------------------------------------------------------------------------
# the Wanderer: 8 bars over I IV V I vi IV ii-V I (chord list per bar: (degree, beats))
# --------------------------------------------------------------------------------------
WANDER = ["4/1 2/.5 4/.5 7/1.5 6/.5", "5/1 3/1 0/2", "1/.5 2/.5 4/1 6/1 4/1", "2/3 r/1",
          "5/1 7/.5 9/.5 8/1.5 7/.5", "7/1 5/1 3/1 5/1", "1/1 3/1 4/.5 5/.5 6/1", "7/3 r/1"]
# the same tune as a hornpipe in 6/8 (bars of three quarter beats)
WANDER68 = ["4/1 2/.5 7/1 6/.5", "5/1 3/.5 0/1.5", "1/.5 2/.5 4/.5 6/1 4/.5", "2/1.5 0/.5 2/.5 4/.5",
            "5/1 7/.5 9/1 8/.5", "7/1 5/.5 3/1 5/.5", "1/1 3/.5 4/.5 5/.5 6/.5", "7/1.5 r/1.5"]
ONV = [False, False, True, False, False, False, True, False]     # bars that end on the V
# minor keys: bar 5 sits on VI (Ab in C minor), where the long 7th degree (D) would rub its Eb
WANDER_MINOR = WANDER[:4] + ["5/1 7/.5 9/.5 10/1.5 9/.5"] + WANDER[5:]


def chords_44():
    return [[(0, 4)], [(3, 4)], [(4, 4)], [(0, 4)], [(5, 4)], [(3, 4)], [(1, 2), (4, 2)], [(0, 4)]]


def chords_68():
    return [[(0, 3)], [(3, 3)], [(4, 3)], [(0, 3)], [(5, 3)], [(3, 3)], [(1, 1.5), (4, 1.5)], [(0, 3)]]


def tagged(bars, idx=range(8)):
    return [(bars[i], ONV[i]) for i in idx]


def harmony(key, d, seventh=False):
    dom = key.minorish and d == 4
    ns = [key(d), key(d + 2) + (1 if dom else 0), key(d + 4)]
    if seventh:
        ns.append(key(d + 6))
    return [n % 12 for n in ns]


def voice(pcs, low, n=3):
    out, x = [], low
    while len(out) < n:
        if x % 12 in pcs:
            out.append(x)
        x += 1
    return out


def low_root(pcs, low=36):
    return low + (pcs[0] - low) % 12


def fifth(pcs):
    return (pcs[2] - pcs[0]) % 12


def segs(bar_chords):
    """(start beat, beats, degree) for each chord of a bar."""
    out, b = [], 0.0
    for d, ln in bar_chords:
        out.append((b, ln, d))
        b += ln
    return out


# ======================================================================================
# hold music: bossa on E.Piano 2 + vibes over the pad (also the 2-bar bridges between worlds)
# ======================================================================================
def bossa_bar(b, key, d, drums=True, vel=88):
    pcs = harmony(key, d, seventh=d not in (0, 3))   # 7ths on ii / V / vi (I and IV hold the tune's roots)
    chord(C13, t(b, 0), voice(pcs, 57, 4), 1.4, 64)                 # vibes: bossa comp
    chord(C13, t(b, 1.5), voice(pcs, 57, 4), 1.0, 58)
    chord(C13, t(b, 3), voice(pcs, 57, 4), 0.9, 60)
    chord(C9, t(b), voice(pcs, 55, 3), 4, 58, gate=1.0)              # pad
    root = low_root(pcs, 36)
    note(C9, t(b, 0), root, 1.5, 60)
    note(C9, t(b, 2), root + fifth(pcs), 1.5, 56)
    if drums:
        for off in (0, 1.5, 3):
            drum(t(b, off), STICK, 60)
        for k in range(8):
            drum(t(b, k * 0.5), CHH, 44 + (8 if k % 2 == 0 else 0))
        drum(t(b, 0), KICK, 62)
        drum(t(b, 2.5), KICK, 56)


def hold_bridge(key, sounds):
    """Two bars of hold music in the next world's key, its sound effects on top."""
    line(C12, 0, key.at(key.tonic % 12 + 60), tagged(WANDER, range(2)), 84)
    for b, d in enumerate((0, 3)):                      # the tune's own I and IV
        bossa_bar(b, key, d)
    for bar, beat, n, v in sounds:
        sfx(bar, beat, n, v)


# ======================================================================================
# setup burst
# ======================================================================================
FIRST = {
    C1: (110, 100, 64),  # fiddle (the Wanderer in Monkey Island)
    C2: (61, 92, 44),    # brass section
    C3: (105, 86, 34),   # banjo
    C4: (32, 104, 64),   # acoustic bass
    C5: (21, 84, 92),    # accordion
    C6: (48, 90, 48),    # strings
    C7: (72, 86, 80),    # piccolo (tin whistle)
    C8: (53, 96, 64),    # voice oohs (the operator)
    C9: (89, 74, 64),    # warm pad (hold music)
    C11: (47, 100, 64),  # timpani
    C12: (5, 96, 60),    # E.Piano 2 (hold music)
    C13: (11, 80, 76),   # vibes (hold music)
    C14: (51, 78, 30),   # synth strings 2
    C15: (57, 90, 70),   # trombone
    C16: (124, 100, 64),  # telephone
}
for ch, (p, v, pan) in FIRST.items():
    prog(ch, 12, p, v, pan)
cc(DR, 13, 7, 110)

KF = Key(65)
KD = Key(62)
KA = Key(57)
KBb = Key(58)
KCm = Key(60, "minor")
KG = Key(55)
KC = Key(60)


def ring(bar, beat, n=2):
    for k in range(n):
        note(C16, t(bar, beat + k * 2), 72, 1.4, 104, jitter=0)


# ======================================================================================
# The Hint Line: the phone rings, the operator answers, please hold
# ======================================================================================
section(100, KF, "The Hint Line")
ring(0, 0, 2)
chord(C9, t(0), voice(harmony(KF, 0), 53, 3), 8, 52, gate=1.0)        # the line hums
note(C9, t(0), 41, 8, 52, gate=1.0)
line(C8, 2, KF.at(65), ["4/1 2/.5 4/.5 7/2", "5/1 3/1 4/2"], 96)      # "you've reached the Hint Line"
chord(C9, t(2), voice(harmony(KF, 0), 53, 3), 4, 56, gate=1.0)
chord(C9, t(3), voice(harmony(KF, 4), 53, 3), 4, 56, gate=1.0)
note(C9, t(2), 41, 4, 56, gate=1.0)
note(C9, t(3), 48, 4, 56, gate=1.0)
advance(4)
section(130, KF, "Please hold (bossa)")
for b in range(8):
    for st, ln, d in segs(chords_44()[b]):
        if st == 0:
            bossa_bar(b, KF, d)
line(C12, 0, KF.at(65), tagged(WANDER), 92)                           # E.Piano 2: the Wanderer
advance(8)

# ======================================================================================
# hint 1 -> Monkey Island: waves, wind, thunder
# ======================================================================================
section(100, KD, "Hint 1: the sea")
hold_bridge(KD, [(0, 0, WAVES, 104), (0, 2, WIND, 96), (1, 1, THUNDER, 112)])
advance(2)

# ======================================================================================
# Monkey Island: pirate hornpipe, D major, 6/8 at 126 (dotted quarter = 84)
# ======================================================================================
section(126, KD, "Monkey Island (hornpipe)", beats=3, den=8)


def hornpipe_bar(b, bar_chords, full):
    for st, ln, d in segs(bar_chords):
        pcs = harmony(KD, d)
        root = low_root(pcs, 38)
        note(C4, t(b, st), root, 1.0, 98)                            # bass: root, fifth
        note(C4, t(b, st + 1.0), root + fifth(pcs), 0.5, 86)
        for k in range(int(ln / 0.5)):                               # banjo: 8th-note chords
            n = voice(pcs, 62, 3)[k % 3]
            note(C3, t(b, st + k * 0.5), n, 0.45, 76 + (10 if k % 3 == 0 else 0))
        if full:
            chord(C5, t(b, st), voice(pcs, 57, 3), ln, 66, gate=0.96)   # accordion
    drum(t(b, 0), KICK, 96)                                          # bodhran: boom on 1 and 4
    drum(t(b, 1.5), KICK, 84)
    for k in range(6):
        drum(t(b, k * 0.5), LTOM, 64 + (18 if k % 3 == 0 else 0))
    drum(t(b, 1.5), TAMB, 70)


MI = chords_68()
for b in range(24):
    hornpipe_bar(b, MI[b % 8], full=b >= 8)
line(C1, 0, KD.at(74), tagged(WANDER68), 100)                       # fiddle: the Wanderer
line(C1, 8, KD.at(74), tagged(WANDER68), 104)
line(C7, 8, KD.at(86), tagged(WANDER68), 82)                        # tin whistle an octave up
line(C1, 16, KD.at(74), tagged(WANDER68), 106)
line(C7, 16, KD.at(86), tagged(WANDER68), 88)
line(C5, 16, KD.at(62), tagged(WANDER68), 74, shift=-2)              # accordion a third below
drum(t(23, 1.5), CRASH, 96)
advance(24)

# ======================================================================================
# hint 2 -> Sam & Max: an engine, a car passing, brakes
# ======================================================================================
section(100, KA, "Hint 2: the road")
prog(C1, pos, 26, 98, 56)       # fiddle -> jazz guitar (twang)
prog(C3, pos, 0, 90, 40)        # banjo -> piano
prog(C4, pos, 36, 106, 64)      # acoustic -> slap bass
prog(C5, pos, 66, 98, 76)       # accordion -> tenor sax
hold_bridge(KA, [(0, 0, ENGINE, 100), (0, 2, CARPASS, 104), (1, 2, CARSTOP, 110)])
advance(2)

# ======================================================================================
# Sam & Max: rockabilly road trip, A major, 164 shuffle
# ======================================================================================
section(164, KA, "Sam & Max (rockabilly)", swing=True)


def rockabilly_bar(b, bar_chords, sax):
    for st, ln, d in segs(bar_chords):
        pcs = harmony(KA, d)
        root = low_root(pcs, 33)
        up = [root + KA(d + k) - KA(d) for k in (0, 2, 4, 5)]       # root, 3rd, 5th, 6th (in key)
        walk = up + [up[2], up[1], up[0], up[2]]
        for k in range(int(ln / 0.5)):                               # slap bass boogie in 8ths
            note(C4, t(b, st + k * 0.5), walk[k % len(walk)], 0.45 if k % 2 == 0 else 0.3, 100 if k % 2 == 0 else 86)
        for k in range(int(ln)):                                     # boogie piano: shuffle chords
            chord(C3, t(b, st + k), voice(pcs, 57, 3), 0.4, 70)
            chord(C3, t(b, st + k + 0.5), voice(pcs, 57, 3), 0.3, 62)
    drum(t(b, 0), KICK, 100)
    drum(t(b, 2), KICK, 96)
    drum(t(b, 1), SNARE, 104)
    drum(t(b, 3), SNARE, 108)
    for k in range(8):
        drum(t(b, k * 0.5), CHH, 66 if k % 2 == 0 else 54)
    if sax and b % 2 == 1:                                           # tenor honks
        pcs = harmony(KA, bar_chords[-1][0])
        for off in (2.5, 3.5):
            note(C5, t(b, off), voice(pcs, 52, 3)[0], 0.4, 104)


SM = chords_44()
for b in range(16):
    rockabilly_bar(b, SM[b % 8], sax=b < 8)
line(C1, 0, KA.at(69), tagged(WANDER), 104)                          # twangy guitar
line(C1, 8, KA.at(69), tagged(WANDER), 106)
line(C5, 8, KA.at(57), tagged(WANDER), 96)                           # tenor sax an octave down
drum(t(15, 3), CRASH, 104)
advance(16)

# ======================================================================================
# hint 3 -> King's Quest: a horse, birds, a windchime
# ======================================================================================
section(100, KBb, "Hint 3: the kingdom")
prog(C1, pos, 60, 98, 60)       # jazz guitar -> French horn
prog(C3, pos, 6, 84, 30)        # piano -> harpsichord
prog(C4, pos, 43, 100, 64)      # slap bass -> contrabass
prog(C5, pos, 19, 82, 90)       # tenor sax -> church organ
prog(C7, pos, 56, 100, 80)      # piccolo -> trumpet
prog(C8, pos, 52, 88, 60)       # voice oohs -> choir aahs
hold_bridge(KBb, [(0, 0, HORSE, 104), (0, 2, BIRDS, 100), (1, 2, WINDCHIME, 96)])
advance(2)

# ======================================================================================
# King's Quest: royal procession, Bb major, 76
# ======================================================================================
section(76, KBb, "King's Quest (royal procession)")
# fanfare: trumpets on the tonic triad, timpani, a snare roll
line(C7, 0, KBb.at(70), ["0/.5 0/.25 0/.25 4/1 2/.5 4/.5 7/1", "7/.5 7/.25 7/.25 6/1 4/1 r/1"], 108)
line(C2, 0, KBb.at(58), ["4/.5 4/.25 4/.25 7/1 4/.5 7/.5 9/1", "9/.5 9/.25 9/.25 8/1 6/1 r/1"], 100)
for b in range(2):
    pcs = harmony(KBb, 0 if b == 0 else 4)
    note(C11, t(b, 0), low_root(pcs, 46), 1, 104)
    note(C11, t(b, 2), low_root(pcs, 46), 1, 96)
    chord(C5, t(b), voice(pcs, 53, 4), 4, 72, gate=0.98)
    note(C4, t(b), low_root(pcs, 34), 4, 90, gate=0.97)
for k in range(16):
    drum(t(1, 2 + k / 8), SNARE, 60 + 3 * k)
drum(t(2), CRASH, 110)
KQ = chords_44()


def royal_bar(b, bar_chords, full):
    for st, ln, d in segs(bar_chords):
        pcs = harmony(KBb, d)
        root = low_root(pcs, 34)
        note(C4, t(b, st), root, ln, 92, gate=0.96)
        chord(C5, t(b, st), voice(pcs, 53, 4), ln, 70, gate=0.98)   # church organ
        chord(C6, t(b, st), voice(pcs, 58, 4), ln, 76, gate=0.99)   # strings
        for k in range(int(ln / 0.5)):                              # harpsichord broken chords
            note(C3, t(b, st + k * 0.5), voice(pcs, 65, 3)[k % 3], 0.5, 64)
        note(C11, t(b, st), low_root(pcs, 46), 1, 92)
        if full:
            chord(C8, t(b, st), voice(pcs, 58, 3), ln, 76, gate=0.98)
    drum(t(b, 0), KICK, 84)
    drum(t(b, 2), KICK, 76)
    for off in (1, 3, 3.5):
        drum(t(b, off), SNARE, 70)


for b in range(8):
    royal_bar(2 + b, KQ[b], full=b >= 4)
line(C1, 2, KBb.at(58), tagged(WANDER), 104)                         # French horn: the Wanderer
line(C2, 6, KBb.at(58), tagged(WANDER, range(4, 8)), 96, shift=-2)   # brass a third below
line(C7, 6, KBb.at(70), tagged(WANDER, range(4, 8)), 98)             # trumpet an octave up
drum(t(9, 3), CRASH, 100)
advance(10)

# ======================================================================================
# hint 4 -> Space Quest: lasers, a starship, an explosion
# ======================================================================================
section(100, KCm, "Hint 4: the stars")
prog(C1, pos, 81, 96, 60)       # French horn -> saw lead
prog(C4, pos, 38, 104, 64)      # contrabass -> synth bass
prog(C5, pos, 90, 80, 92)       # church organ -> polysynth
prog(C11, pos, 55, 100, 20)     # timpani -> orch hit
hold_bridge(KCm, [(0, 0, LASER, 104), (0, 0.5, LASER, 104), (0, 1, LASER, 104),
                  (0, 2, STARSHIP, 106), (1, 2, EXPLOSION, 120)])
advance(2)

# ======================================================================================
# Space Quest: action chase, C minor, 160
# ======================================================================================
section(160, KCm, "Space Quest (the chase)")
SQ = chords_44()


def chase_bar(b, bar_chords, full):
    for st, ln, d in segs(bar_chords):
        pcs = harmony(KCm, d)
        root = low_root(pcs, 36)
        for k in range(int(ln / 0.25)):                             # synth bass 16ths
            note(C4, t(b, st + k * 0.25), root + (12 if k % 4 == 2 else 0), 0.22, 96 if k % 4 == 0 else 80)
        for k in range(int(ln / 0.5)):                              # string ostinato in octaves
            n = voice(pcs, 60, 3)[(k // 2) % 3]
            note(C14, t(b, st + k * 0.5), n, 0.45, 74)
            note(C14, t(b, st + k * 0.5), n + 12, 0.45, 66)
        chord(C5, t(b, st), voice(pcs, 60, 4), 0.6, 72)
        if full:
            chord(C6, t(b, st), voice(pcs, 55, 4), ln, 76, gate=0.99)
            chord(C8, t(b, st), voice(pcs, 60, 3), ln, 70, gate=0.99)
            chord(C2, t(b, st), voice(pcs, 58, 3), 0.5, 104)        # brass hits
            note(C11, t(b, st), root + 24, 0.5, 104)                # orch hit
    for off in (0, 1.75, 2.5):
        drum(t(b, off), KICK, 104)
    drum(t(b, 1), SNARE, 104)
    drum(t(b, 3), SNARE, 108)
    for k in range(16):
        drum(t(b, k * 0.25), CHH, 50 + (16 if k % 2 == 0 else 0))
    if b % 4 == 3:
        for k, n in enumerate((HTOM, HTOM, MTOM, MTOM, LTOM, LTOM, LFTOM, LFTOM)):
            drum(t(b, 2 + k * 0.25), n, 90 + 2 * k)


for b in range(16):
    chase_bar(b, SQ[b % 8], full=b >= 8)
    if b >= 8:
        cc(C11, t(b) - 4, 10, 10 if b % 2 == 0 else 117)            # orch hits ping-pong
line(C1, 4, KCm.at(72), tagged(WANDER_MINOR), 104)                   # saw lead
line(C6, 12, KCm.at(72), tagged(WANDER_MINOR, range(4, 8)), 90)      # strings join on top
ramp(C14, 10, t(0), t(8), 10, 117, 32)                               # the ostinato sweeps across
ramp(C14, 10, t(8), t(16) - 8, 117, 30, 32)
drum(t(4), CRASH, 104)
drum(t(12), CRASH, 108)
advance(16)

# ======================================================================================
# hint 5 -> Leisure Suit Larry: a door, footsteps, a heartbeat, a laugh
# ======================================================================================
section(100, KG, "Hint 5: the casino")
prog(C1, pos, 65, 100, 60)      # saw lead -> alto sax
prog(C3, pos, 0, 90, 36)        # harpsichord -> piano (montuno)
prog(C4, pos, 32, 104, 64)      # synth bass -> acoustic bass
prog(C5, pos, 73, 84, 90)       # polysynth -> flute
prog(C14, pos, 11, 76, 20)      # synth strings 2 -> vibes
cc(C11, pos, 10, 64)
hold_bridge(KG, [(0, 0, DOOR, 108), (0, 1, STEPS1, 96), (0, 2, STEPS2, 96),
                 (1, 0, HEARTBEAT, 100), (1, 1, HEARTBEAT, 100), (1, 2, LAUGH, 108)])
advance(2)

# ======================================================================================
# Leisure Suit Larry: cha-cha, G major, 124
# ======================================================================================
section(124, KG, "Leisure Suit Larry (cha-cha)")
LS = chords_44()


def chacha_bar(b, bar_chords, mambo):
    for st, ln, d in segs(bar_chords):
        pcs = harmony(KG, d)
        root = low_root(pcs, 36)
        for off, n, ln_ in ((1.5, root, 1.4), (3.0, root + fifth(pcs), 0.9)):   # tumbao: the and of 2, 4
            if st <= off < st + ln:
                note(C4, t(b, off), n, ln_, 100)
        for k in (0, 1, 1.5, 2.5, 3, 3.5):                          # piano montuno
            if st <= k < st + ln:
                chord(C3, t(b, k), voice(pcs, 67, 3), 0.4, 74)
    for k in range(4):
        drum(t(b, k), COWBELL, 76 if k % 2 == 0 else 64)
    drum(t(b, 0), LGUIRO, 60)
    drum(t(b, 2), SGUIRO, 60)
    for off, n in ((0, MCONGA), (1, OCONGA), (1.5, OCONGA), (2, MCONGA), (3, LCONGA), (3.5, LCONGA)):
        drum(t(b, off), n, 82)
    drum(t(b, 3), KICK, 86)                                          # cha-cha-cha on 4 and
    drum(t(b, 3.5), KICK, 80)
    if b % 4 == 3:
        for k in range(4):
            drum(t(b, 2 + k * 0.5), HTIMB if k % 2 == 0 else LTIMB, 94)
    if mambo:
        pcs = harmony(KG, bar_chords[0][0])
        for off in (0.5, 1.5, 3.5):
            chord(C2, t(b, off), voice(pcs, 62, 3), 0.4, 100)        # mambo brass
        chord(C14, t(b, 0), voice(pcs, 67, 3), 2, 62, roll=20)       # vibes


for b in range(16):
    chacha_bar(b, LS[b % 8], mambo=b >= 8)
line(C1, 4, KG.at(67), tagged(WANDER), 106)                          # alto sax: the Wanderer
line(C5, 8, KG.at(79), tagged(WANDER, range(4, 8)), 80)              # flute obligato, up high
line(C1, 12, KG.at(67), tagged(WANDER, range(4, 8)), 108)
line(C15, 12, KG.at(55), tagged(WANDER, range(4, 8)), 92, shift=-2)  # trombone a third below
drum(t(15, 3), CRASH, 104)
advance(16)

# ======================================================================================
# Finale: the Wanderer on every channel, C major 108, broadening to 80; the phone rings again
# ======================================================================================
section(108, KC, "Finale")
prog(C1, pos, 56, 104, 64)      # alto sax -> trumpet
prog(C3, pos, 0, 90, 40)
prog(C4, pos, 33, 106, 64)      # acoustic -> fingered bass
prog(C5, pos, 16, 76, 92)       # flute -> organ
prog(C7, pos, 72, 84, 80)       # trumpet -> piccolo
prog(C12, pos, 9, 86, 70)       # E.Piano 2 -> glockenspiel
prog(C14, pos, 46, 82, 24)      # vibes -> harp
prog(C16, pos, 14, 90, 100)     # telephone -> tubular bells
FN = chords_44()


def finale_bar(b, bar_chords):
    for st, ln, d in segs(bar_chords):
        pcs = harmony(KC, d)
        root = low_root(pcs, 36)
        note(C4, t(b, st), root, ln * 0.5, 100)
        note(C4, t(b, st + ln / 2), root + fifth(pcs), ln * 0.5, 92)
        chord(C3, t(b, st), voice(pcs, 55, 4), ln, 74, gate=0.96)
        chord(C5, t(b, st), voice(pcs, 55, 4), ln, 62, gate=0.98)
        chord(C6, t(b, st), voice(pcs, 60, 4), ln, 76, gate=0.99)
        chord(C8, t(b, st), voice(pcs, 60, 3), ln, 72, gate=0.99)
        chord(C9, t(b, st), voice(pcs, 52, 3), ln, 58, gate=1.0)
        chord(C13, t(b, st), voice(pcs, 64, 3), 1, 60)
        chord(C2, t(b, st + 1.5), voice(pcs, 58, 3), 0.4, 94)
        note(C11, t(b, st), root + 24, 0.5, 100)
        for k in range(int(ln / 0.5)):
            note(C14, t(b, st + k * 0.5), voice(pcs, 67, 4)[k % 4], 0.5, 56)
    note(C16, t(b), KC(7 if b % 2 == 0 else 4), 2, 80)               # bells
    drum(t(b, 0), KICK, 104)
    drum(t(b, 2), KICK, 98)
    drum(t(b, 1), SNARE, 96)
    drum(t(b, 3), SNARE, 100)
    for k in range(8):
        drum(t(b, k * 0.5), RIDE, 66 if k % 2 == 0 else 54)


for b in range(8):
    finale_bar(b, FN[b])
line(C1, 0, KC.at(72), tagged(WANDER), 106)                          # trumpet
line(C12, 0, KC.at(84), tagged(WANDER), 86)                          # glockenspiel
line(C7, 0, KC.at(84), tagged(WANDER), 80)                           # piccolo
line(C15, 0, KC.at(48), tagged(WANDER), 92, shift=-2)                # trombone a third (and octave) below
drum(t(0), CRASH, 110)
advance(8)

section(96, KC, "Finale: broad ending")
coda = [[(5, 4)], [(3, 4)], [(1, 2), (4, 2)], [(0, 4)]]
for b, bc in enumerate(coda):
    finale_bar(b, bc)
tempo(2, 88)
tempo(3, 80)
line(C1, 0, KC.at(72), [("5/1 7/.5 9/.5 8/1.5 7/.5", False), ("7/1 5/1 3/1 5/1", False),
                        ("1/1 3/1 4/.5 5/.5 6/1", True), ("7/4", False)], 110)
line(C15, 0, KC.at(48), [("3/2 5/2", False), ("5/2 3/2", False), ("3/2 4/2", True), ("2/4", False)], 96)
drum(t(3), CRASH, 116)
advance(4)
section(80, KC, "Finale: the phone rings again")
end = t(0)
chord(C3, end, [36, 48, 55, 60, 64, 67, 72], 6, 96, gate=1.0)
chord(C6, end, [48, 55, 60, 64, 67], 6, 86, gate=1.0)
chord(C8, end, [60, 64, 67], 6, 80, gate=1.0)
chord(C2, end, [55, 60, 64, 67], 6, 96, gate=1.0)
chord(C5, end, [48, 55, 64, 67], 6, 66, gate=1.0)
chord(C9, end, [48, 55, 64], 8, 60, gate=1.0)
note(C1, end, 84, 6, 100, gate=1.0)
note(C4, end, 36, 6, 100, gate=1.0)
note(C11, end, 60, 1, 110)
note(C12, end, 96, 3, 84)
note(C7, end, 96, 4, 76)
note(C13, end, 76, 3, 70)
note(C14, end, 84, 3, 60)
note(C15, end, 48, 6, 90, gate=1.0)
note(C16, end, 72, 4, 90)
drum(end, CRASH, 116)
drum(end, KICK, 116)
for c_ in (C1, C2, C3, C4, C5, C6, C8, C15):
    ramp(c_, 7, t(1), t(1, 3.5), 100, 0, 12)
prog(C16, t(2), 124, 100, 64)   # bells -> telephone
ring(2, 0, 2)
sfx(3, 0, LAUGH, 108)
sfx(3, 2, APPLAUSE, 100)
end_tick = t(4) + TPB * 2

# ======================================================================================
# checks (as in make_voodoo_demo.py)
# ======================================================================================
allow.sort(key=lambda a: a[0])
bad = []
for tk, _o, m in events:
    if m.type != "note_on" or not m.velocity or m.channel == DR:
        continue
    t0, pcs, extra, name = [a for a in allow if a[0] <= tk + 30][-1]
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
tr.append(mido.MetaMessage("track_name", name="The Hint Line", time=0))
tr.append(mido.Message("sysex", data=[0x7E, 0x7F, 0x09, 0x01], time=0))       # GM System On
last = 0
for tk, _o, m in allev:
    tk += TPB
    tr.append(m.copy(time=max(0, tk - last)))
    last = max(last, tk)
tr.append(mido.MetaMessage("end_of_track", time=max(0, end_tick + TPB - last)))

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
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "midi", "the_hint_line.mid")
os.makedirs(os.path.dirname(out), exist_ok=True)
mf.save(out)
n_on = sum(1 for m in tr if m.type == "note_on" and m.velocity)
n_fx = sum(1 for m in tr if m.type == "note_on" and m.velocity and m.channel == DR and m.note in SFX)
chs = sorted({m.channel + 1 for m in tr if m.type == "note_on" and m.channel != DR})
print(f"{out}: Format 1, {len(mf.tracks)} tracks, {mf.length:.1f} s ({int(mf.length // 60)}:"
      f"{int(mf.length % 60):02d}), {n_on} notes ({n_fx} sound effects), "
      f"{sum(1 for m in tr if m.type == 'program_change')} program changes, melody channels {chs}, all in key")
