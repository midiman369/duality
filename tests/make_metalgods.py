"""Write "A Tribute to the Metal Gods", an original ~10 minute heavy metal epic for Duality + Anima.

    python tests/make_metalgods.py [out.mid]      (default tests/midi/metal_gods.mid)

The user's own song (lyric sheet: NWOBHM, iconic riffs, a stereo-wide guitar duo), composed here
from scratch (an earlier Suno MIDI export was too muddy to use). The lead guitar sings the vocal
melody and takes every solo. The tribute sections are written in the style of the bands the
lyrics name: their tempo, tuning, groove, harmony (tritones, phrygian, harmonic minor) and
arrangement tricks, with original riffs and melodies (no quotes).

   Black Sabbath storm      E    60   rain, thunder, a tolling bell, a tritone doom crawl
   Vocal intro              E    80   "Feel the power!" hook, choir hits
   Virtuoso intro           E   160   twin-guitar harmony over a gallop, then runs
   Verse 1 (Birmingham)     E    80   lumbering stomp
   Chorus                   E   160   anthem
   Bridge                   E    92   sustained chord hits, ticking hi-hat
   Hook                     E   172   full gallop, "Eddie's watching", then a becalmed sea
   Bridge 2                 E   112   bass-driven mid-tempo
   Riff break               E   140   syncopated heavy riff
   Soaring solo             E   112   long bends (the GTR Multi 3 showcase)
   Verse 2 (drop D)         D  70/170 doom crawl that takes flight into a gallop
   Verse 3 (twin guitars)   A   150   open-string pedal riff, harmonised twin leads, "SKYYY"
   Verse 4 (Dio / Rainbow)  E    96   synth intro, an Eastern march, clean arpeggios, heavy riff
   Verse 5 (power groove)   D 100/200 stop-start chugs, pinch squeals, a thrash burst
   Verse 6 (thrash)         E  84/216 ominous intro, tremolo riffs, "witness" scream, whammy chaos
   Verse 7 (rock'n'roll)    E   160   relentless drive with bass chords, then a shuffle
   Chorus, Big Finish x2    E 160/144 organ + choir crescendo
   Face-melting solo        E   176   sweeps, runs, tapping, bends
   King Diamond interlude   E  80/150 church organ + harpsichord, harmonic-minor twin leads
   Drum solo + refrain      E   160   the tribute riffs as a medley
   Final solo               E   144   the hook, an octave up
   Black Horsemen closer    E    72   acoustic intro, slow epic build, the last chord

Mostly GM: GM capitals, a GS reset at the start, the SC-88Pro map's Standard 1 kit on ch10 and
the SC rain / thunder / wind SFX on ch13-14 (a plain GM synth plays Seashore there). No file EFX;
channel 16 is left for Anima's foley. Format 1. The build fails if a note leaves its section's
key, if a program change lands under a held note, or on a silence over 1.5 s.
"""
import math
import os
import random
import sys

import mido

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common  # noqa: E402

TPB = 480
rng = random.Random(1980)
events = []          # (tick, order, message)
tempos = []          # (tick, bpm)
sigs = []            # (tick, num, den)
allow = []           # (tick0, pitch classes, extra pcs, name)
names = []           # (tick0, name) for the section list
nocheck = []         # (channel, tick0, tick1): sound effects, not pitched parts

C1, C2, C3, C4, C5, C6, C7, C8, C9, DR, C11, C12, C13, C14, C15, C16 = range(16)
TONE, SEMI = 1365, 683          # pitch-bend steps with a 12-semitone range (the lead)

MODES = {
    "minor": [0, 2, 3, 5, 7, 8, 10], "harm": [0, 2, 3, 5, 7, 8, 11], "mixo": [0, 2, 4, 5, 7, 9, 10],
    "phrdom": [0, 1, 4, 5, 7, 8, 10],
}


class Key:
    """Scale degrees -> MIDI notes. Degree 0 = tonic at `tonic`; 7 = an octave up."""

    def __init__(self, tonic, mode):
        self.tonic, self.m = tonic, MODES[mode]

    def __call__(self, d):
        o, i = divmod(int(d), 7)
        return self.tonic + 12 * o + self.m[i]

    def tri(self, d):
        return [self(d), self(d + 2), self(d + 4)]

    def pcs(self):
        return {(self.tonic + x) % 12 for x in self.m}


KE = Key(64, "minor")            # E minor, degree 0 = E4
KEh = Key(64, "harm")            # E harmonic minor
KEx = Key(64, "mixo")            # E mixolydian
KEp = Key(64, "phrdom")          # E phrygian dominant
KD = Key(62, "minor")            # D minor (drop-D sections)
KA = Key(57, "minor")            # A minor, degree 0 = A3

# guitar roots (standard tuning; drop D adds D2 = 38)
E2, F2, Fs2, G2, Gs2, A2, As2, B2, Cn3, Cs3, D3, Ds3, E3 = range(40, 53)
D2, Eb2 = 38, 39

# --------------------------------------------------------------------------------------
# timeline + note helpers
# --------------------------------------------------------------------------------------
pos = TPB * 2
BPB = 4.0


def section(bpm, key, extra=(), name="", beats=4.0):
    global BPB
    BPB = beats
    tempos.append((pos, bpm))
    sigs.append((pos, int(beats), 4))
    allow.append((pos, key.pcs(), set(extra), name))
    names.append((pos, name))


def t(bar, beat=0.0):
    return pos + int(round((bar * BPB + beat) * TPB))


def advance(bars):
    global pos
    pos = t(bars)


def note(ch, tick, n, beats, vel, jitter=4, gate=0.92):
    j = rng.randint(-jitter, jitter) if jitter else 0
    v = max(1, min(127, int(vel) + rng.randint(-3, 3)))
    tk = max(0, tick + j)
    d = max(15, int(beats * TPB * gate))
    events.append((tk, 2, mido.Message("note_on", channel=ch, note=int(n), velocity=v)))
    events.append((tk + d, 0, mido.Message("note_off", channel=ch, note=int(n), velocity=0)))


def chord(ch, tick, notes, beats, vel, roll=0, gate=0.95, jitter=3):
    for i, n in enumerate(notes):
        note(ch, tick + i * roll, n, beats, vel - i, jitter=jitter, gate=gate)


def cc(ch, tick, c, v):
    events.append((tick, 1, mido.Message("control_change", channel=ch, control=c, value=max(0, min(127, int(v))))))


def ramp(ch, c, t0, t1, v0, v1, steps=24):
    for k in range(steps + 1):
        cc(ch, t0 + (t1 - t0) * k // steps, c, v0 + (v1 - v0) * k / steps)


def bend(ch, tick, value):
    events.append((tick, 1, mido.Message("pitchwheel", channel=ch, pitch=max(-8192, min(8191, int(value))))))


def bend_curve(ch, t0, t1, v0, v1, steps=12):
    for k in range(steps + 1):
        bend(ch, t0 + (t1 - t0) * k // steps, v0 + (v1 - v0) * k / steps)


def vib(ch, t0, t1, base=0, depth=170, step=40):
    """Finger vibrato around `base`, easing in, ending back on it."""
    k, tk = 0, t0
    while tk < t1 - step:
        ease = min(1.0, (tk - t0) / max(1, (t1 - t0) / 3))
        bend(ch, tk, base + depth * ease * math.sin(k * math.pi / 3))
        tk += step
        k += 1
    bend(ch, t1, base)


def prog(ch, tick, program, vol=100, pan=64, rev=40, cho=0, expr=127, msb=0, lsb=0):
    """Bank + program + mix at tick (the channel must be silent there)."""
    cc(ch, tick, 0, msb)
    cc(ch, tick, 32, lsb)
    events.append((tick + 1, 1, mido.Message("program_change", channel=ch, program=program)))
    cc(ch, tick + 2, 7, vol)
    cc(ch, tick + 2, 10, pan)
    cc(ch, tick + 2, 91, rev)
    cc(ch, tick + 2, 93, cho)
    cc(ch, tick + 2, 11, expr)


def bend_range(ch, tick, semis):
    for c_, v_ in ((101, 0), (100, 0), (6, semis), (38, 0), (101, 127), (100, 127)):
        cc(ch, tick, c_, v_)


def mel(ch, bar, key, spec, vel=100, shift=0, gate=0.95, jitter=3, stretch=1, oct_=0):
    """spec rows: (beat, degree, beats); stretch 2 = the same line at half speed."""
    for b, d, ln in spec:
        note(ch, t(bar, b * stretch), key(d + shift) + 12 * oct_, ln * stretch,
             vel + (5 if abs(b % 1) < 1e-6 else 0), jitter=jitter, gate=gate)


def sing(bar, tpl, key, vel=108, stretch=1, shift=0, harmony=None, depth=170):
    """The lead guitar sings a phrase (a list of bars); long notes get vibrato.
    harmony: a channel that doubles it a diatonic third below (twin guitars)."""
    for i, spec in enumerate(tpl):
        b0 = bar + i * stretch
        mel(C1, b0, key, spec, vel, shift=shift, stretch=stretch)
        if harmony is not None:
            mel(harmony, b0, key, spec, vel - 8, shift=shift - 2, stretch=stretch)
        for b, d, ln in spec:
            if ln * stretch >= 1.5:
                t0 = t(b0, (b + 0.4) * stretch if stretch > 1 else b + 0.4)
                t1 = t(b0, (b + ln) * stretch) - 40
                vib(C1, t0, t1, 0, depth)


def scream(bar, beat, n, beats, vel=124, up=TONE):
    """A held high note bent up and shaken (the screamed words)."""
    note(C1, t(bar, beat), n, beats, vel, jitter=0, gate=0.97)
    bend_curve(C1, t(bar, beat + 0.15), t(bar, beat + 0.6), 0, up, 6)
    vib(C1, t(bar, beat + 0.6), t(bar, beat + beats - 0.1), up, 320)
    bend(C1, t(bar, beat + beats) - 10, 0)


def ring(arp, i, most, step=.5):
    """How long arpeggio note i (8ths) may ring: up to `most` beats, but not into its own next repeat."""
    for j in range(i + 1, len(arp)):
        if arp[j] == arp[i]:
            return min(most, (j - i) * step * 0.98)
    return most


def pw(root):
    return [root, root + 7, root + 12]


def riff(chs, bar, spec, vel=104, gate=0.82, bass=True, bvel=None):
    """spec rows: (beat, root, beats, kind): 'p' power chord, '5' root + fifth, 'n' one note.
    The bass plays each root an octave (or two) down."""
    for b, r, ln, kind in spec:
        notes = pw(r) if kind == "p" else ([r, r + 7] if kind == "5" else [r])
        for ch in chs:
            chord(ch, t(bar, b), notes, ln, vel + (6 if abs(b % 1) < 1e-6 else 0), gate=gate, jitter=3)
        if bass:
            bn = r - 12 if r - 12 >= 26 else r
            while bn > 45:
                bn -= 12
            note(C5, t(bar, b), bn, ln, (bvel or vel) + (4 if abs(b % 1) < 1e-6 else 0), jitter=3, gate=gate)


def gallop(chs, bar, root, beats=4, vel=102, bass=True, start=0.0):
    spec = []
    for i in range(int(beats)):
        b = start + i
        spec += [(b, root, .5, "p"), (b + .5, root, .25, "p"), (b + .75, root, .25, "p")]
    riff(chs, bar, spec, vel, gate=0.7, bass=bass)


def eighths(chs, bar, roots, vel=104, kind="p", gate=0.8, bass=True):
    """Eight 8th-note strums; roots: one per bar or a list of 8."""
    rs = roots if isinstance(roots, list) else [roots] * 8
    riff(chs, bar, [(i * .5, r, .5, kind) for i, r in enumerate(rs)], vel, gate=gate, bass=bass)


# --------------------------------------------------------------------------------------
# drums (SC-88Pro map Standard 1 kit)
# --------------------------------------------------------------------------------------
KICK, SNARE, LTOM, CHH, LTOM2, PHH, MTOM, OHH, MTOM2, HTOM, CRASH, RIDE, CHINA = \
    36, 38, 41, 42, 43, 44, 45, 46, 47, 50, 49, 51, 52
RBELL, SPLASH, CRASH2 = 53, 55, 57
TOMS = [HTOM, MTOM2, MTOM, LTOM2, LTOM]


def drum(tick, n, vel, jitter=3):
    note(DR, tick, n, 0.25, vel, jitter=jitter, gate=0.5)


def kit(bar, kicks=(), snares=(), hats=(), hat=CHH, crash=False, vel=104, hv=72):
    for b in kicks:
        drum(t(bar, b), KICK, vel)
    for b in snares:
        drum(t(bar, b), SNARE, vel + 8)
    for b in hats:
        drum(t(bar, b), hat, hv + (8 if abs(b % 1) < 1e-6 else 0))
    if crash:
        drum(t(bar), CRASH, vel + 10)


def fill(bar, beat0, kind="down", vel=100):
    n = int(round((BPB - beat0) * 4))
    for i in range(n):
        bt = beat0 + i * 0.25
        if kind == "down":
            drum(t(bar, bt), TOMS[min(4, i * 5 // max(1, n))], vel + i)
        elif kind == "snare":
            drum(t(bar, bt), SNARE, vel - 10 + i * 2)
        elif kind == "kicks":
            drum(t(bar, bt), KICK, vel)
            if i % 2:
                drum(t(bar, bt), TOMS[i % 5], vel - 6)


def gallop_kit(bar, vel=100, crash=False):
    for b in range(4):
        for off in (0, .5, .75):
            drum(t(bar, b + off), KICK, vel - (0 if off == 0 else 8))
        drum(t(bar, b), SNARE if b % 2 else RIDE, vel + (10 if b % 2 else -24))
    if crash:
        drum(t(bar), CRASH, vel + 12)


def rock_kit(bar, vel=102, crash=False, hat=OHH):
    kit(bar, kicks=(0, 2, 2.5), snares=(1, 3), hats=[i * .5 for i in range(8)], hat=hat, crash=crash, vel=vel)


def half_kit(bar, vel=100, crash=False):
    kit(bar, kicks=(0, 1.5, 3.5), snares=(2,), hats=(0, 1, 2, 3), hat=RIDE, crash=crash, vel=vel, hv=76)


def skank_kit(bar, vel=104, crash=False):
    for i in range(8):
        drum(t(bar, i * .5), KICK if i % 2 == 0 else SNARE, vel - (0 if i % 2 == 0 else 2))
        drum(t(bar, i * .5), RIDE, 74)
    if crash:
        drum(t(bar), CRASH, vel + 12)


def dkick_kit(bar, vel=104, crash=False):
    for i in range(16):
        drum(t(bar, i * .25), KICK, vel - (0 if i % 4 == 0 else 10))
    for b in (1, 3):
        drum(t(bar, b), SNARE, vel + 10)
    for b in range(4):
        drum(t(bar, b), CHINA if b == 0 and crash else RIDE, 90 if b == 0 and crash else 72)


# ======================================================================================
# setup (the channels heard from the start; the others join at their sections)
# ======================================================================================
prog(C1, 0, 30, vol=110, pan=64, rev=50)                       # Lead guitar (Distortion)
bend_range(C1, 3, 12)
prog(C3, 0, 30, vol=100, pan=0, rev=30)                        # Rhythm guitar L
prog(C8, 0, 30, vol=100, pan=127, rev=30)                      # Rhythm guitar R
prog(C5, 0, 34, vol=108, pan=64, rev=10)                       # Picked bass
prog(DR, 0, 0, vol=110, rev=35, lsb=3)                         # Standard 1, SC-88Pro map
prog(C9, 0, 14, vol=100, pan=40, rev=90)                       # Tubular bells
prog(C11, 0, 52, vol=96, pan=88, rev=90)                       # Choir Aahs
prog(C15, 0, 47, vol=104, pan=64, rev=60)                      # Timpani
prog(C13, 0, 122, vol=100, pan=64, rev=40, expr=0, msb=1)      # Rain (SC SFX; GM: Seashore)
prog(C14, 0, 122, vol=110, pan=64, rev=60, msb=2)              # Thunder

# ======================================================================================
# 1  Black Sabbath storm - E, 60 BPM, 8 bars: rain, thunder, a bell, a tritone doom crawl
# ======================================================================================
section(60, KE, extra={5, 10}, name="storm (Black Sabbath)")    # F (b2) and A# (the tritone)
note(C13, t(0), 60, 10 * 4, 100, jitter=0, gate=1.0)
ramp(C13, 11, t(0), t(1), 0, 110)
nocheck.append((C13, t(0), t(11)))
for bar, beat in ((0, 1.5), (3, 2), (6, 0.5)):
    note(C14, t(bar, beat), 48, 3.5, 112, jitter=0)
nocheck.append((C14, t(0), t(8)))
for b in (1, 3, 5, 7):
    note(C9, t(b), 64, 4, 104 - b * 2, jitter=0)
DOOM = [[(0, E2, 2, "p"), (2, F2, 1, "p"), (3, As2, 2.5, "p")],
        [(1.5, A2, .5, "p"), (2, G2, 1, "p"), (3, F2, .5, "p"), (3.5, E2, .5, "p")]]
for k in range(2, 8):
    riff([C3, C8], k, DOOM[k % 2], 108, gate=0.97)
    kit(k, kicks=(0,), snares=(2,), hats=(0, 1, 2, 3), hat=RIDE, crash=(k % 2 == 0), vel=104)
    if k % 2 == 0:
        note(C15, t(k), E2, 2, 112)
fill(7, 2, "down", 96)
sing(4, [[(2, 7, 2)], [(0, 6, 1), (1, 5, 1), (2, 4, 2)], [(0, 7, 3)], [(0, 9, .5), (.5, 8, .5), (1, 7, 3)]], KE, 100)
advance(8)

# ======================================================================================
# 2  "Feel the power!" - E, 80 BPM, 4 bars: the hook over held chords and choir hits
# ======================================================================================
section(80, KE, name="vocal intro")
HOOK = [[(0, 4, 1), (1, 4, .5), (1.5, 6, .5), (2, 7, 2)],
        [(0, 4, 1), (1, 4, .5), (1.5, 6, .5), (2, 9, 2)],
        [(0, 7, .5), (.5, 6, .5), (1, 4, .5), (1.5, 3, .5), (2, 2, 1), (3, 3, 1)],
        [(0, 4, 4)]]
ramp(C13, 11, t(0), t(2, 3), 110, 0)
for k, (r, tri) in enumerate(((E2, 0), (Cn3, 5), (D3, 6), (B2, 4))):
    riff([C3, C8], k, [(0, r, 3.5, "p")], 112, gate=0.97)
    chord(C11, t(k), KE.tri(tri - 7 if tri > 3 else tri), 2, 100)
    drum(t(k), CRASH, 116)
    drum(t(k), KICK, 116)
sing(0, HOOK[:3], KE, 112)
scream(3, 0, KE(4), 3.8)
for i in range(16):
    note(C15, t(3, 2) + i * TPB // 8, E2, 0.125, 70 + i * 3, jitter=0)
fill(3, 2, "snare", 100)
advance(4)

# ======================================================================================
# 3  Virtuoso intro - E, 160 BPM, 16 bars: twin guitars in thirds over a gallop, then runs
# ======================================================================================
section(160, KE, name="virtuoso intro (Maiden)")
ROOTS3 = [E2, E2, Cn3, D3, E2, E2, Cn3, B2] * 2
TWIN3 = [[(0, 7, 1), (1, 8, .5), (1.5, 9, .5), (2, 11, 1.5), (3.5, 9, .5)],
         [(0, 8, 1), (1, 7, 1), (2, 6, 2)],
         [(0, 5, 1), (1, 6, .5), (1.5, 7, .5), (2, 9, 1.5), (3.5, 8, .5)],
         [(0, 8, 2), (2, 6, 2)],
         [(0, 7, .5), (.5, 9, .5), (1, 11, .5), (1.5, 12, .5), (2, 14, 2)],
         [(0, 13, 1), (1, 12, 1), (2, 11, 1), (3, 9, 1)],
         [(0, 10, 1), (1, 9, .5), (1.5, 8, .5), (2, 7, 1), (3, 5, 1)],
         [(0, 6, 2), (2, 4, 2)]]
BASE = {E2: 7, Cn3: 5, D3: 6, B2: 4, G2: 9, A2: 3}
for k, r in enumerate(ROOTS3):
    gallop([C3] if k < 8 else [C3, C8], k, r, vel=100 if k < 8 else 106)
    gallop_kit(k, 100, crash=(k % 4 == 0))
    if k >= 8 and k < 15:
        b0 = BASE[r]
        run = [b0 + x for x in (0, 1, 2, 0, 1, 2, 3, 1, 2, 3, 4, 2, 3, 4, 5, 3)]
        mel(C1, k, KE, [(i * .25, d, .25) for i, d in enumerate(run)], 104, gate=0.85, jitter=2)
sing(0, TWIN3, KE, 110, harmony=C8)
sing(15, [[(0, 14, 4)]], KE, 116)
bend_curve(C1, t(15, 1.5), t(15, 2), 0, TONE, 5)
vib(C1, t(15, 2), t(15, 3.8), TONE, 300)
bend(C1, t(16) - 10, 0)
fill(15, 2, "down", 104)
advance(16)

# ======================================================================================
# 4  Verse 1 (Birmingham factories) - E, 80 BPM, 8 bars: a lumbering stomp
# ======================================================================================
section(80, KE, extra={1, 5, 10}, name="verse 1 (Iron Man stomp)")   # F#5 and A#5 power chords
STOMP = [[(0, E2, 1.5, "p"), (1.5, G2, .5, "p"), (2, A2, 1, "p"), (3, As2, .5, "p"), (3.5, A2, .5, "p")],
         [(0, G2, 1, "p"), (1, Fs2, .5, "p"), (1.5, E2, 1.5, "p"), (3, D3, .5, "p"), (3.5, E2, .5, "p")]]
VA = [[(0, 4, .5), (.5, 4, .5), (1, 4, .5), (1.5, 6, .5), (2, 7, 1), (3, 6, .5), (3.5, 4, .5)], [(0, 3, 1), (1, 4, 3)]]
VB = [[(0, 7, .5), (.5, 7, .5), (1, 6, .5), (1.5, 4, .5), (2, 6, 1), (3, 7, 1)], [(0, 9, 1.5), (1.5, 7, .5), (2, 6, 2)]]
VC = [[(0, 9, .5), (.5, 9, .5), (1, 8, .5), (1.5, 7, .5), (2, 6, 1), (3, 4, 1)], [(0, 3, 1), (1, 2, 1), (2, 4, 2)]]
VD = [[(0, 4, .5), (.5, 6, .5), (1, 7, .5), (1.5, 9, .5), (2, 11, 1), (3, 9, 1)], [(0, 11, 4)]]
for k in range(8):
    riff([C3, C8], k, STOMP[k % 2], 108, gate=0.9)
    half_kit(k, 106, crash=(k % 2 == 0))
for i, ph in enumerate((VA, VB, VC, VD)):
    sing(i * 2, ph, KE, 110)
fill(7, 2, "snare", 100)
advance(8)

# ======================================================================================
# 5  Chorus - E, 160 BPM, 16 bars: the anthem
# ======================================================================================
CHR = [E2, Cn3, D3, E2, E2, Cn3, D3, B2, E2, Cn3, D3, E2, Cn3, D3, B2, B2]
CHA = [[(0, 7, 1.5), (1.5, 7, .5), (2, 9, 1), (3, 7, 1)], [(0, 9, 1), (1, 9, .5), (1.5, 10, .5), (2, 11, 1), (3, 9, 1)],
       [(0, 7, 3), (3, 6, 1)], [(0, 7, 4)]]
CHB = [[(0, 9, .5), (.5, 9, .5), (1, 9, 1), (2, 11, 2)], [(0, 9, .5), (.5, 10, .5), (1, 11, .5), (1.5, 10, .5), (2, 9, 1), (3, 7, 1)],
       [(0, 8, 2), (2, 6, 2)], [(0, 4, 2), (2, 6, 2)]]
CHC = CHA[:3] + [[(0, 7, 2), (2, 9, 2)]]
CHD = [[(0, 7, 1.5), (1.5, 7, .5), (2, 9, 1), (3, 7, 1)], [(0, 9, 1), (1, 11, 1), (2, 12, 2)], [], [(0, 14, 2), (2, 11, 2)]]
TRI = {E2: 0, Cn3: 5, D3: 6, B2: 4, G2: 2, A2: 3}


def chorus(organ=False, choir_from=8):
    section(160, KE, name="chorus" + (" 2" if organ else ""))
    for k, r in enumerate(CHR):
        eighths([C3, C8], k, r, 108)
        rock_kit(k, 104, crash=(k % 4 == 0))
        if k >= choir_from:
            chord(C11, t(k), KE.tri(TRI[r] + (7 if TRI[r] < 3 else 0)), 4, 92)
        if organ:
            chord(C4, t(k), [x - 12 for x in KE.tri(TRI[r] + (7 if TRI[r] < 3 else 0))], 4, 88, gate=0.98)
        if k % 4 == 0:
            note(C15, t(k), E2 if r == E2 else (B2 - 12 + 12 if r == B2 else E2), 2, 108)
    for i, ph in enumerate((CHA, CHB, CHC, CHD)):
        sing(i * 4, ph, KE, 112)
    scream(14, 0, KE(14), 3.8)
    fill(15, 2, "down", 104)
    advance(16)


chorus()

# ======================================================================================
# 6  Bridge - E, 92 BPM, 8 bars: sustained chord hits with silence, a ticking hi-hat
# ======================================================================================
section(92, KE, name="bridge (War Pigs)")
WAR = [[(0, E2, 3, "p")], [(0, G2, .5, "p"), (.5, A2, 2.5, "p")], [(0, E2, 3, "p")], [(0, Cn3, .5, "p"), (.5, D3, 2.5, "p")],
       [(0, E2, 3, "p")], [(0, G2, .5, "p"), (.5, A2, 2.5, "p")], [(0, Cn3, 2, "p"), (2, D3, 2, "p")], [(0, B2, 3.5, "p")]]
BRA = [[(0, 9, 1), (1, 9, .5), (1.5, 11, .5), (2, 12, 2)], [(0, 11, 1), (1, 9, 1), (2, 7, 2)]]
BRB = [[(0, 7, .5), (.5, 9, .5), (1, 11, 1), (2, 14, 2)], [(0, 13, 1), (1, 12, 1), (2, 11, 2)]]
BRD = [[(0, 11, .5), (.5, 12, .5), (1, 13, .5), (1.5, 14, .5), (2, 14, 2)], []]
for k, sp in enumerate(WAR):
    riff([C3, C8], k, sp, 110, gate=0.97)
    for b, r, ln, kind in sp:
        drum(t(k, b), CRASH if b == 0 else SPLASH, 108)
        drum(t(k, b), KICK, 108)
    for i in range(8):
        drum(t(k, i * .5), CHH, 64 if i % 2 else 76)
    if k % 2 == 1:
        drum(t(k, 3), SNARE, 104)
for i, ph in enumerate((BRA, BRB, BRA, BRD)):
    sing(i * 2, ph, KE, 110)
scream(7, 0, KE(14), 3.6)
fill(7, 2, "down", 104)
advance(8)

# ======================================================================================
# 7  Hook - E, 172 BPM, 12 bars of gallop ("Eddie's watching"), then a becalmed sea (80, 4 bars)
# ======================================================================================
section(172, KE, name="hook (Iron Maiden)")
ROOTS7 = [E2, D3, Cn3, D3, E2, D3, Cn3, B2, E2, Cn3, D3, B2]
HOOK2 = [[(0, 4, 1), (1, 4, .5), (1.5, 6, .5), (2, 7, 2)], [(0, 7, 1), (1, 9, .5), (1.5, 11, .5), (2, 11, 2)],
         [(0, 12, .5), (.5, 11, .5), (1, 9, .5), (1.5, 7, .5), (2, 9, 1), (3, 11, 1)], [(0, 11, 4)]]
EDDIE = [[(0, 7, .5), (.5, 7, .5), (1, 9, .5), (1.5, 7, .5), (2, 6, .5), (2.5, 7, 1.5)], [(0, 4, 1), (1, 6, 1), (2, 7, 2)]]
DIOH = [[(0, 9, .5), (.5, 9, .5), (1, 11, .5), (1.5, 9, .5), (2, 7, 1), (3, 9, 1)], [(0, 11, 4)]]
for k, r in enumerate(ROOTS7):
    gallop([C3] if k >= 8 else [C3, C8], k, r, vel=106)
    gallop_kit(k, 104, crash=(k % 4 == 0))
sing(0, HOOK, KE, 112)
sing(4, HOOK2, KE, 112)
sing(8, EDDIE, KE, 112, harmony=C8)
sing(10, DIOH, KE, 114, harmony=C8)
fill(11, 3, "snare", 96)
advance(12)
section(80, KE, name="becalmed (Rime)")
prog(C13, t(0) - 30, 122, vol=96, pan=64, rev=60, expr=90, msb=3)    # Wind
prog(C6, t(0) - 30, 89, vol=96, pan=40, rev=90, expr=40)             # Warm pad
note(C13, t(0), 60, 4 * 4, 90, jitter=0, gate=0.98)
nocheck.append((C13, t(0), t(4)))
ramp(C6, 11, t(0), t(2), 40, 100)
chord(C6, t(0), [52, 59, 64, 67], 16, 80, gate=0.97)
chord(C11, t(1), [59, 64, 67], 12, 60, gate=0.95)
for k in range(4):
    note(C5, t(k), [71, 64, 67, 71][k], 2, 70, jitter=0)            # bass harmonics
    drum(t(k), RIDE, 50)
sing(0, [[(0, 11, 2), (2, 9, 2)], [(0, 7, 4)], [(0, 6, 2), (2, 4, 2)], [(0, 7, 4)]], KE, 92, depth=120)
fill(3, 2, "down", 90)
advance(4)

# ======================================================================================
# 8  Bridge 2 - E, 112 BPM, 8 bars: the bass drives, the guitars hit and ring
# ======================================================================================
section(112, KE, name="bridge 2 (Heaven and Hell)")
BASSHH = [[28, 28, 31, 28, 33, 28, 35, 33], [28, 28, 31, 33, 35, 33, 31, 30]]
B2A = [[(0, 7, 1), (1, 9, 1), (2, 11, 1.5), (3.5, 9, .5)], [(0, 7, 2), (2, 4, 2)]]
B2B = [[(0, 7, .5), (.5, 9, .5), (1, 11, .5), (1.5, 12, .5), (2, 11, 1), (3, 9, 1)], [(0, 11, 4)]]


def hh_groove(k, vel=106):
    for i, n in enumerate(BASSHH[k % 2]):
        note(C5, t(k, i * .5), n, .5, 104 + (6 if i % 2 == 0 else 0), jitter=2, gate=0.8)
    riff([C3, C8], k, [(0, E2, 2, "p"), (3.5, G2, .5, "p")] if k % 2 == 0 else [(0, Cn3, 1.5, "p"), (2, D3, 2, "p")],
         vel, gate=0.95, bass=False)
    kit(k, kicks=(0, 2.5), snares=(1, 3), hats=[i * .5 for i in range(8)], hat=RIDE, crash=(k % 4 == 0), vel=104)


for k in range(8):
    hh_groove(k)
for i, ph in enumerate((B2A, B2B, B2A, B2B)):
    sing(i * 2, ph, KE, 110)
advance(8)

# ======================================================================================
# 9  Riff break - E, 140 BPM, 8 bars: a syncopated heavy riff, licks in the gaps
# ======================================================================================
section(140, KE, extra={1}, name="riff break (Sacred Heart)")          # the F#5 power chord
SACRED = [[(0, E2, .5, "p"), (.75, E2, .25, "p"), (1, G2, .5, "p"), (1.5, A2, .5, "p"), (2.5, E2, .5, "p"), (3, D3, .5, "p"), (3.5, Cn3, .5, "p")],
          [(0, B2, 1.5, "p"), (1.5, A2, .5, "p"), (2, G2, 1, "p"), (3, Fs2, .5, "p"), (3.5, G2, .5, "p")]]
for k in range(8):
    riff([C3, C8], k, SACRED[k % 2], 110, gate=0.8)
    for b, r, ln, kind in SACRED[k % 2]:
        drum(t(k, b), KICK, 108)
    kit(k, snares=(1, 3), hats=(0, 1, 2, 3), hat=RIDE, crash=(k % 2 == 0), vel=104)
    if k % 2 == 1:
        lick = [(2 + i * .25, d, .25) for i, d in enumerate((14, 13, 11, 9, 11, 9, 7, 9))]
        mel(C1, k, KE, lick, 108, gate=0.85, jitter=2)
advance(8)

# ======================================================================================
# 10 Soaring solo - E, 112 BPM, 12 bars over the bass groove: long bends (GTR Multi 3)
# ======================================================================================
section(112, KE, name="soaring solo")
SOLO = [[(0, 11, .5), (.5, 12, .5), (1, 14, 3)],
        [(0, 14, .5), (.5, 13, .5), (1, 12, 1), (2, 11, .5), (2.5, 9, .5), (3, 11, 1)],
        [(0, 12, 2), (2.5, 11, .5), (3, 9, 1)],
        [(0, 9, .5), (.5, 11, .5), (1, 12, .5), (1.5, 13, .5), (2, 13, 2)],
        [(0, 14, 1 / 3), (1 / 3, 13, 1 / 3), (2 / 3, 11, 1 / 3), (1, 13, 1 / 3), (4 / 3, 11, 1 / 3), (5 / 3, 9, 1 / 3), (2, 11, 2)],
        [(0, 12, 1.5), (1.5, 11, .5), (2, 9, 1), (3, 7, 1)],
        [(0, 9, .25), (.25, 11, .25), (.5, 12, .25), (.75, 14, .25), (1, 16, 3)],
        [(0, 15, 1), (1, 14, .5), (1.5, 13, .5), (2, 11, 1), (3, 6, 1)],
        [(0, 7, .5), (.5, 9, .5), (1, 11, 1), (2, 14, 2)],
        [(0, 12, 1.5), (1.5, 11, .5), (2, 9, 1), (3, 7, 1)],
        [(i * .25, 7 + i, .25) for i in range(8)] + [(2, 13, 2)],
        [(0, 14, 4)]]
BENDS = {0: (2.0, 2.5), 3: (2.5, 3.0), 6: (1.6, 2.0), 11: (1.0, 1.6)}
for k in range(12):
    hh_groove(k, 104)
    mel(C1, k, KE, SOLO[k], 116, jitter=2)
    if k in BENDS:
        b0, b1 = BENDS[k]
        bend_curve(C1, t(k, b0), t(k, b1), 0, TONE, 6)
        vib(C1, t(k, b1), t(k, 3.85), TONE, 300)
        bend(C1, t(k, 3.97), 0)
    elif SOLO[k][-1][2] >= 2:
        vib(C1, t(k, SOLO[k][-1][0] + 0.4), t(k, 3.85), 0, 260)
fill(11, 2, "down", 104)
advance(12)

# ======================================================================================
# 11 Verse 2 (Sabbath to Maiden, drop D) - D minor: a 70 BPM doom crawl, then a 170 BPM gallop
# ======================================================================================
section(70, KD, extra={3, 8}, name="verse 2 (doom, drop D)")   # Eb (b2), G# (the tritone)
DDOOM = [[(0, D2, 2, "p"), (2, Eb2, 1, "p"), (3, Gs2, 2.5, "p")],
         [(1.5, G2, .5, "p"), (2, F2, 1, "p"), (3, Eb2, .5, "p"), (3.5, D2, .5, "p")]]
for k in range(4):
    riff([C3, C8], k, DDOOM[k % 2], 110, gate=0.97)
    kit(k, kicks=(0,), snares=(2,), hats=(0, 1, 2, 3), hat=RIDE, crash=(k % 2 == 0), vel=106)
sing(0, VA, KD, 110)
sing(2, VB, KD, 110)
fill(3, 2, "kicks", 104)
advance(4)
section(170, KD, name="verse 2 (Maiden's flight)")
for k, r in enumerate([D2, As2, Cn3, D2, D2, As2, Cn3, A2]):
    gallop([C3, C8], k, r, vel=106)
    gallop_kit(k, 104, crash=(k % 4 == 0))
sing(0, VC, KD, 112, stretch=2)
sing(4, VD, KD, 114, stretch=2)
fill(7, 2, "down", 104)
advance(8)

# ======================================================================================
# 12 Verse 3 (twin guitars) - A minor, 150 BPM: an open-string pedal riff and harmonised leads
# ======================================================================================
section(150, KA, name="verse 3 (twin guitars, Priest)")
PEDAL = [[45, 60, 45, 62, 45, 64, 45, 62], [45, 60, 45, 62, 45, 67, 45, 64]]
TWIN12 = [[(0, 7, .5), (.5, 9, .5), (1, 11, 1), (2, 10, .5), (2.5, 9, .5), (3, 7, 1)],
          [(0, 9, 1), (1, 7, 1), (2, 6, 2)],
          [(0, 7, .5), (.5, 9, .5), (1, 11, .5), (1.5, 12, .5), (2, 14, 2)],
          [(0, 13, 1), (1, 11, 1), (2, 12, 2)]]
ROOTS12 = [A2, A2, A2, A2] + [A2, A2, F2, G2] * 3 + [A2, F2, G2, E2]
for k, r in enumerate(ROOTS12):
    for i, n in enumerate(PEDAL[k % 2]):
        note(C3, t(k, i * .5), n, .5, 104 if n == 45 else 112, jitter=2, gate=0.6 if n == 45 else 0.85)
    note(C5, t(k), r - 12, 2, 108, jitter=2)
    note(C5, t(k, 2), r - 12, 2, 100, jitter=2)
    if k >= 4:
        eighths([C8], k, r, 104, kind="5", bass=False)
    kit(k, kicks=(0, 1.5, 2), snares=(1, 3), hats=[i * .5 for i in range(8)], hat=CHH, crash=(k % 4 == 0), vel=104)
sing(0, TWIN12, KA, 112, harmony=C8)
sing(4, VA, KA, 112, stretch=2, shift=7)
sing(8, VB, KA, 112, stretch=2, shift=7)
sing(12, VC, KA, 112, stretch=2, shift=7)
sing(16, VD[:1], KA, 114, stretch=2, shift=7)
scream(18, 0, KA(18), 7.6)
fill(19, 2, "down", 106)
advance(20)

# ======================================================================================
# 13 Verse 4 (Dio, from Rainbow to his own) - E, 96 BPM: synth intro, an Eastern march,
#    clean arpeggios, then a heavy mid-tempo riff with the organ
# ======================================================================================
section(96, KE, name="Tarot synth intro")
prog(C14, t(0) - 30, 81, vol=96, pan=96, rev=70, expr=40)            # Saw synth
ramp(C14, 11, t(0), t(2), 40, 120)
chord(C6, t(0), [52, 59, 64, 67], 8, 84, gate=0.97)
for k in range(2):
    for i in range(16):
        note(C14, t(k, i * .25), [64, 71, 76, 79, 83, 79, 76, 71][i % 8] - (12 if k else 0), .25, 84, jitter=1, gate=0.7)
sing(0, [[(0, 7, 4)], [(0, 9, 2), (2, 11, 2)]], KE, 100)
drum(t(1, 2), CRASH, 96)
advance(2)
section(96, KEp, name="Eastern march (Stargazer)")                 # E phrygian dominant
prog(C7, t(0) - 30, 48, vol=100, pan=76, rev=80)                   # Strings
MARCH = [52, 53, 56, 57, 56, 53, 52, 47]
for k in range(4):
    chord(C7, t(k), [52, 56, 59, 64] if k % 2 == 0 else [53, 57, 60, 65], 4, 92)
    for i, n in enumerate(MARCH):
        note(C3, t(k, i * .5), n, .5, 106, jitter=2, gate=0.85)
        note(C8, t(k, i * .5), n + 12, .5, 100, jitter=2, gate=0.85)
        note(C5, t(k, i * .5), 28 if k % 2 == 0 else 29, .5, 104, jitter=2, gate=0.7)
    for b, tn, ln in ((0, 40, .5), (2.5, 47, .25), (2.75, 47, .25), (3, 40, .5)):
        note(C15, t(k, b), tn, ln, 110)
    for i in range(8):
        drum(t(k, i * .5), SNARE if i in (0, 3, 5, 6) else KICK, 96)
    if k % 2 == 0:
        drum(t(k), CRASH, 108)
sing(0, [[(0, 7, 1), (1, 8, .5), (1.5, 9, .5), (2, 10, 1), (3, 9, 1)], [(0, 8, 2), (2, 7, 2)],
         [(0, 9, .5), (.5, 10, .5), (1, 11, 1), (2, 12, 1), (3, 11, 1)], [(0, 10, 1), (1, 9, 1), (2, 8, 1), (3, 7, 1)]], KEp, 112)
advance(4)
section(96, KE, name="clean arpeggios (Children of the Sea)")
prog(C2, t(0) - 30, 27, vol=100, pan=30, rev=70, cho=40)          # Clean guitar
for k, arp in enumerate(([40, 47, 52, 55, 59, 55, 52, 47], [42, 50, 54, 57, 62, 57, 54, 50])):
    for i, n in enumerate(arp):
        note(C2, t(k, i * .5), n, ring(arp, i, 1.2), 84, jitter=2)
    drum(t(k), RIDE, 60)
sing(0, [[(0, 11, 4)], [(0, 9, 4)]], KE, 96, depth=140)
advance(2)
section(96, KE, extra={1}, name="verse 4 (Holy Diver)")                # the F#5 power chord
DIVER = [[(0, E2, 1.5, "p"), (1.5, E2, .5, "n"), (2, D3, 1, "p"), (3, Cn3, .5, "p"), (3.5, D3, .5, "p")],
         [(0, E2, 1, "p"), (1, G2, .5, "p"), (1.5, A2, 1, "p"), (2.5, G2, .5, "p"), (3, Fs2, .5, "p"), (3.5, E2, .5, "p")]]
ORG4 = [0, 0, 6, 0, 5, 6, 0, 0]
DIO_A = [[(0, 7, 1), (1, 9, 1), (2, 11, 1.5), (3.5, 12, .5)], [(0, 11, 2), (2, 9, 2)]]
DIO_B = [[(0, 12, 1), (1, 11, .5), (1.5, 9, .5), (2, 7, 1), (3, 9, 1)], [(0, 8, 4)]]
DIO_D = [[(0, 9, .5), (.5, 11, .5), (1, 12, .5), (1.5, 14, .5), (2, 14, 2)], []]
prog(C4, t(0) - 30, 18, vol=100, pan=40, rev=60, expr=90)            # Rock organ (set late: it keeps its unit)
for k in range(8):
    riff([C3, C8], k, DIVER[k % 2], 110, gate=0.85)
    kit(k, kicks=(0, 1.5, 2.5), snares=(1, 3), hats=[i * .5 for i in range(8)], hat=RIDE, crash=(k % 2 == 0), vel=106)
    d = ORG4[k]
    chord(C4, t(k), [x - 12 for x in KE.tri(d + 7)], 4, 92, gate=0.98)
for i, ph in enumerate((DIO_A, DIO_B, DIO_A, DIO_D)):
    sing(i * 2, ph, KE, 112, shift=2 if i == 2 else 0)
scream(7, 0, KE(14), 3.7)
chord(C11, t(6), KE.tri(7), 8, 96)
fill(7, 2, "down", 104)
advance(8)

# ======================================================================================
# 14 Verse 5 (power groove) - D minor (drop D): stop-start chugs, pinch squeals; a thrash burst
# ======================================================================================
section(100, KD, extra={3, 8}, name="verse 5 (Pantera groove)")
GROOVE = [[(0, D2, .25, "5"), (.25, D2, .25, "5"), (.5, F2, .5, "5"), (1, D2, .25, "5"), (1.25, D2, .25, "5"), (1.5, Gs2, .5, "5"),
           (3, Eb2, .25, "5"), (3.25, D2, .25, "5"), (3.5, D2, .5, "5")],
          [(0, D2, .25, "5"), (.25, D2, .25, "5"), (.5, G2, .5, "5"), (1, D2, .25, "5"), (1.25, D2, .25, "5"), (1.5, F2, .5, "5"),
           (2, Eb2, .5, "5"), (2.5, D2, .5, "5")]]
PANT = [[(0, 7, .5), (.5, 7, .5), (1, 6, .5), (1.5, 7, .5), (2, 9, 1)], [(0, 7, 1), (1, 4, 1)]]
PANT2 = [[(0, 9, .5), (.5, 9, .5), (1, 11, .5), (1.5, 9, .5), (2, 7, 1)], [(0, 7, .5), (.5, 6, .5), (1, 7, 1)]]
for k in range(8):
    riff([C3, C8], k, GROOVE[k % 2], 112, gate=0.7)
    for b, r, ln, kind in GROOVE[k % 2]:
        drum(t(k, b), KICK, 110)
    kit(k, snares=(1, 3) if k % 2 == 0 else (1,), crash=False, vel=104)
    drum(t(k), CHINA, 104)
    if k % 2 == 1:                                                   # pinch squeal in the stop
        note(C1, t(k, 2.75), KD(18), 1, 118, jitter=0)
        bend_curve(C1, t(k, 2.8), t(k, 3.2), 0, TONE, 5)
        vib(C1, t(k, 3.2), t(k, 3.7), TONE, 420)
        bend(C1, t(k, 3.9), 0)
for i, ph in enumerate((PANT, PANT2, PANT, PANT2)):
    sing(i * 2, [ph[0], []], KD, 112)
advance(8)
section(200, KD, extra={3, 8}, name="thrash burst (Art of Shredding)")
SHRED = [[D2] * 4 + [Eb2, D2, D2, D2] + [D2] * 4 + [Gs2, G2, F2, Eb2], [D2] * 4 + [F2, D2, D2, D2] + [G2, D2, Gs2, D2] + [A2, Gs2, G2, F2]]
for k in range(4):
    riff([C3, C8], k, [(i * .25, n, .25, "5") for i, n in enumerate(SHRED[k % 2])], 108, gate=0.7)
    dkick_kit(k, 106, crash=(k % 2 == 0))
mel(C1, 3, KD, [(i * .25, 14 - i, .25) for i in range(16)], 112, gate=0.8, jitter=1)
advance(4)

# ======================================================================================
# 15 Verse 6 (thrash) - E: an ominous 84 BPM intro, then 216 BPM tremolo riffs, a scream, chaos
# ======================================================================================
section(84, KE, extra={5, 10, 3}, name="verse 6 intro (South of Heaven)")
OMEN = [[(0, 52, 2, "n"), (2, 53, 1, "n"), (3, 55, 1, "n")], [(0, 54, 1.5, "n"), (1.5, 53, .5, "n"), (2, 52, 2, "n")],
        [(0, 52, 2, "n"), (2, 55, 1, "n"), (3, 58, 1, "n")], [(0, 57, 1.5, "n"), (1.5, 55, .5, "n"), (2, 53, 2, "n")]]
for k in range(4):
    riff([C3], k, OMEN[k], 106, gate=0.95, bass=False)
    chord(C8, t(k), pw(E2), 4, 100, gate=0.97)
    note(C5, t(k), 28, 4, 100, jitter=0)
    for b in range(4):
        drum(t(k, b), LTOM if b % 2 == 0 else LTOM2, 96)
    drum(t(k), CRASH, 104)
sing(0, [[(2, 4, 2)], [(0, 5, 3)], [(0, 4, 2), (2, 7, 2)], [(0, 6, 4)]], KE, 104)
advance(4)
section(216, KE, extra={5, 10, 3}, name="verse 6 (thrash)")
TREM = [[E2] * 8 + [F2] * 4 + [E2] * 4, [G2] * 4 + [Fs2] * 4 + [F2] * 4 + [E2] * 4]
for k in range(13):
    if k < 8:
        riff([C3, C8], k, [(i * .25, n, .25, "n") for i, n in enumerate(TREM[k % 2])], 106, gate=0.7)
        skank_kit(k, 106, crash=(k % 4 == 0))
    elif k == 8:                                                   # "We are here to witness Slayer!"
        riff([C3, C8], k, [(0, E2, 4, "p")], 116, gate=0.97)
        drum(t(k), CRASH, 120)
        drum(t(k), KICK, 120)
    else:                                                          # whammy chaos over the tremolo
        riff([C3, C8], k, [(i * .25, n, .25, "n") for i, n in enumerate(TREM[k % 2])], 106, gate=0.7)
        dkick_kit(k, 108, crash=(k == 9))
for i, ph in enumerate((VA, VB, VC)):
    sing(i * 2, ph, KE, 112)
sing(6, [VD[0], []], KE, 114)
scream(7, 0, KE(11), 1.9)
note(C1, t(8), KE(14), 3.5, 126, jitter=0)
bend_curve(C1, t(8, .2), t(8, 1), 0, TONE, 6)
vib(C1, t(8, 1), t(8, 2.5), TONE, 500)
bend_curve(C1, t(8, 2.5), t(8, 3.6), TONE, -8192, 10)
bend(C1, t(9) - 10, 0)
CHAOS = [64, 65, 67, 70, 71, 72, 74, 75, 76, 77, 79, 82, 83, 84, 86, 88]
for k in range(9, 13):
    for i in range(14):
        note(C1, t(k, i * .25), CHAOS[rng.randrange(len(CHAOS))], .25, 114, jitter=1, gate=0.85)
    note(C1, t(k, 3.5), 88, .5, 120, jitter=0)
    bend_curve(C1, t(k, 3.55), t(k, 3.9), 0, -8192 if k % 2 else 4096, 6)
    bend(C1, t(k + 1) - 8, 0)
advance(13)

# ======================================================================================
# 16 Verse 7 (rock'n'roll) - E, 160 BPM: a relentless drive with bass chords, then a shuffle
# ======================================================================================
section(160, KEx, extra={7}, name="verse 7 (Motorhead)")              # mixolydian + the blue third
DRIVE = [[E2] * 4 + [D3, D3, E2, E2], [E2] * 4 + [G2, G2, A2, A2]]
for k in range(8):
    eighths([C3, C8], k, DRIVE[k % 2], 110, bass=False)
    for i, r in enumerate(DRIVE[k % 2]):
        chord(C5, t(k, i * .5), [r - 12, r - 5], .5, 110, gate=0.8)     # bass chords
    kit(k, kicks=(0, 1, 2, 3), snares=(1, 3), hats=[i * .5 for i in range(8)], hat=RIDE, crash=(k % 2 == 0), vel=108)
for i, ph in enumerate((VA, VB, VC, VD)):
    sing(i * 2, ph, KEx, 112)
advance(8)
section(160, KEx, extra={7}, name="shuffle (Train Kept A-Rollin')")


def sw(b):
    whole, frac = divmod(b, 1.0)
    return whole + (2 / 3 if abs(frac - 0.5) < 1e-6 else frac)


for k in range(4):
    for i in range(8):
        top = E2 + (7 if (i // 2) % 2 == 0 else 9)
        for ch in (C3, C8):
            chord(ch, t(k, sw(i * .5)), [E2, top], .4, 104, gate=0.8)
        note(C5, t(k, sw(i * .5)), [28, 32, 35, 37, 38, 37, 35, 32][i], .4, 106, gate=0.8)
        drum(t(k, sw(i * .5)), RIDE, 76)
    kit(k, kicks=(0, 2), snares=(1, 3), crash=(k == 0), vel=104)
mel(C1, 3, KEx, [(sw(i * .5), d, 1 / 3 if i % 2 else 2 / 3) for i, d in enumerate((7, 9, 11, 9, 7, 6, 4, 2))], 110)
fill(3, 3, "snare", 100)
advance(4)

# ======================================================================================
# 17 Chorus 2 (with the organ and the choir), 18 Big Finish x2
# ======================================================================================
cc(C4, pos, 11, 100)
chorus(organ=True, choir_from=0)
section(144, KE, name="big finish")
BFR = [E2, Cn3, D3, B2] * 3 + [E2, Cn3, D3, B2, E2, Cn3, D3, E2]
BFA = [[(0, 7, .5), (.5, 9, .5), (1, 11, 1), (2, 12, 1), (3, 11, 1)], [(0, 9, 2), (2, 7, 2)]]
BFB = [[(0, 9, .5), (.5, 11, .5), (1, 12, 1), (2, 14, 1), (3, 12, 1)], [(0, 11, 4)]]
BFD = [[(0, 11, .5), (.5, 12, .5), (1, 14, 1), (2, 14, 2)], []]
ramp(C4, 11, t(0), t(12), 80, 127)
ramp(C11, 11, t(0), t(12), 80, 127)
for k, r in enumerate(BFR):
    eighths([C3, C8], k, r, 108 + (k // 4) * 2)
    rock_kit(k, 104 + (k // 4) * 2, crash=(k % 2 == 0))
    tri = KE.tri(TRI[r] + (7 if TRI[r] < 3 else 0))
    chord(C11, t(k), tri, 4, 100)
    chord(C4, t(k), [x - 12 for x in tri], 4, 96, gate=0.98)
    if k % 4 == 0:
        note(C15, t(k), E2, 2, 112)
for rep in range(3):
    sing(rep * 4, HOOK[:3], KE, 112 + rep * 3)
    scream(rep * 4 + 3, 0, KE(4 + 7 * (rep == 2)), 3.8)
for i, ph in enumerate((BFA, BFB, BFA, BFD)):
    sing(12 + i * 2, ph, KE, 116)
scream(19, 0, KE(14), 3.8, up=TONE * 2)
for i in range(16):
    note(C15, t(19, 2) + i * TPB // 8, E2, 0.125, 70 + i * 3, jitter=0)
fill(19, 2, "down", 108)
advance(20)

# ======================================================================================
# 19 Face-melting solo - E, 176 BPM, 16 bars over a gallop: sweeps, runs, tapping, bends
# ======================================================================================
section(176, KE, name="face-melting solo")
FR = [E2, Cn3, D3, B2] * 4
for k, r in enumerate(FR):
    gallop([C3, C8], k, r, vel=104)
    gallop_kit(k, 104, crash=(k % 4 == 0))
    tri = TRI[r] + 7
    if k < 4:                                                    # sweeps: 16th triplets up and down
        arp = [tri, tri + 2, tri + 4, tri + 7, tri + 9, tri + 11]
        seq = arp + arp[::-1]
        mel(C1, k, KE, [(i / 3, seq[i % 12], 1 / 3) for i in range(12)], 110, gate=0.85, jitter=1)
    elif k < 8:                                                  # scale runs
        run = [tri + x for x in (0, 1, 2, 3, 4, 3, 2, 1, 2, 3, 4, 5, 6, 5, 4, 3)]
        mel(C1, k, KE, [(i * .25, d, .25) for i, d in enumerate(run)], 112, gate=0.85, jitter=1)
    elif k < 12:                                                 # tapping: a high note against the triad
        low = [tri, tri + 2, tri + 4]
        mel(C1, k, KE, [(i * .25, 14 + (2 if k % 2 else 0) if i % 2 == 0 else low[(i // 2) % 3], .25) for i in range(16)],
            110, gate=0.85, jitter=1)
    else:                                                        # bends to finish
        mel(C1, k, KE, [(0, 14, 2), (2, 16, 2)] if k < 15 else [(0, 14, 4)], 120, jitter=0)
        bend_curve(C1, t(k, .2), t(k, .6), 0, TONE, 5)
        vib(C1, t(k, .6), t(k, 1.9), TONE, 360)
        bend(C1, t(k, 1.97), 0)
        vib(C1, t(k, 2.3), t(k, 3.9), 0, 360)
fill(15, 2, "down", 108)
advance(16)

# ======================================================================================
# 20 King Diamond interlude - E harmonic minor: church organ + harpsichord (80), twin leads (150)
# ======================================================================================
section(80, KEh, extra={5}, name="King Diamond (the graves)")
prog(C4, t(0) - 30, 19, vol=106, pan=40, rev=100)                  # Church organ
prog(C7, t(0) - 30, 6, vol=104, pan=88, rev=60)                    # Harpsichord
KDC = [(0, [52, 55, 59]), (3, [57, 60, 64]), (4, [59, 63, 66, 69]), (0, [52, 55, 59])]
for k, (d, tri) in enumerate(KDC):
    chord(C4, t(k), [n - 12 for n in tri] + [tri[0] - 24], 4, 100, gate=0.98)
    for i in range(8):
        note(C7, t(k, i * .5), tri[i % len(tri)] + (12 if i >= 4 else 0), .5, 92, jitter=2)
    chord(C11, t(k), tri, 4, 84)
    if k % 2 == 0:
        note(C9, t(k), 64, 4, 96, jitter=0)
    drum(t(k), RIDE, 56)
sing(0, [[(0, 14, 4)], [(0, 12, 2), (2, 11, 2)], [(0, 13, 4)], [(0, 14, 4)]], KEh, 104, depth=260)
advance(4)
section(150, KEh, extra={5}, name="King Diamond (Abigail riff)")
ABI = [[(0, E2, .5, "p"), (.5, E2, .25, "p"), (.75, E2, .25, "p"), (1, E2, .5, "p"), (1.5, Ds3, .5, "n"),
        (2, E3, .5, "n"), (2.5, 54, .5, "n"), (3, 55, .5, "n"), (3.5, 54, .5, "n")],
       [(0, A2, .5, "p"), (.5, A2, .25, "p"), (.75, A2, .25, "p"), (1, B2, 1, "p"), (2, Cn3, .5, "p"), (2.5, B2, .5, "p"),
        (3, A2, .5, "p"), (3.5, Ds3, .5, "n")]]
KTWIN = [[(0, 7, .5), (.5, 8, .5), (1, 9, .5), (1.5, 10, .5), (2, 11, 1), (3, 10, .5), (3.5, 9, .5)],
         [(0, 8, 1), (1, 7, .5), (1.5, 6, .5), (2, 7, 2)],
         [(0, 9, .5), (.5, 10, .5), (1, 11, .5), (1.5, 12, .5), (2, 13, 1), (3, 12, 1)],
         [(0, 11, 1), (1, 10, .5), (1.5, 9, .5), (2, 8, 1), (3, 6, 1)]]
for k in range(8):
    riff([C3], k, ABI[k % 2], 110, gate=0.8)
    gallop_kit(k, 104, crash=(k % 4 == 0)) if k % 2 == 0 else rock_kit(k, 104)
    chord(C4, t(k), [40, 47, 52] if k % 2 == 0 else [45, 52, 57], 4, 92, gate=0.98)
sing(0, KTWIN, KEh, 112, harmony=C8)
sing(4, KTWIN[:3], KEh, 114, harmony=C8)
scream(7, 0, KEh(14), 3.6, up=TONE * 2)                            # the falsetto shriek
advance(8)
section(80, KEh, name="King Diamond (cremation)")
chord(C4, t(0), [47, 51, 54, 57, 59], 7.5, 110, gate=0.98)         # B7, the dominant
chord(C11, t(0), [59, 63, 66], 7.5, 100)
riff([C3, C8], 0, [(0, B2, 4, "p")], 112, gate=0.97)
riff([C3, C8], 1, [(0, B2, 3.5, "p")], 104, gate=0.97)
for i in range(32):
    note(C15, t(0) + i * TPB // 4, 47, 0.25, 60 + i * 2, jitter=0)
sing(0, [[(0, 13, 4)], [(0, 13, 3.5)]], KEh, 112, depth=300)
drum(t(0), CRASH, 112)
advance(2)

# ======================================================================================
# 21 Drum solo + riff refrain - E, 160 BPM: 4 bars of drums, then the tribute riffs (2 bars each)
# ======================================================================================
section(160, KE, extra={1, 3, 5, 8, 10}, name="drum solo + refrain")
for k in range(4):
    if k == 0:
        for i in range(16):
            drum(t(k, i * .25), TOMS[min(4, i * 5 // 16)], 96 + i)
            drum(t(k, i * .25), KICK, 100)
    elif k == 1:
        for i in range(12):
            drum(t(k, i / 3), SNARE if i % 3 == 0 else (KICK if i % 3 == 1 else MTOM), 104)
    elif k == 2:
        dkick_kit(k, 106, crash=True)
    else:
        for i in range(8):
            drum(t(k, i * .25), SNARE, 90 + i * 4)
        fill(k, 2, "down", 108)
    if k in (0, 2):
        riff([C3, C8], k, [(0, E2, 1.5, "p")], 118, gate=0.95)
        note(C15, t(k), E2, 2, 118)
mel(C1, 3, KE, [(2 + i * .25, 14 - i, .25) for i in range(8)], 110, gate=0.85, jitter=1)
k0 = 4
for k in range(2):                                                 # the gallop
    gallop([C3, C8], k0 + k, [E2, Cn3][k], vel=106)
    gallop_kit(k0 + k, 104, crash=(k == 0))
for k in range(2):                                                 # the pedal riff, in E
    for i, n in enumerate([40, 55, 40, 57, 40, 59, 40, 57]):
        note(C3, t(k0 + 2 + k, i * .5), n, .5, 108, jitter=2, gate=0.7)
        note(C8, t(k0 + 2 + k, i * .5), n + (12 if n > 40 else 0), .5, 102, jitter=2, gate=0.7)
    note(C5, t(k0 + 2 + k), 28, 4, 106)
    rock_kit(k0 + 2 + k, 104, crash=(k == 0), hat=CHH)
for k in range(2):                                                 # the Dio riff
    riff([C3, C8], k0 + 4 + k, DIVER[k], 110, gate=0.85)
    kit(k0 + 4 + k, kicks=(0, 1.5, 2.5), snares=(1, 3), hats=(0, 1, 2, 3), hat=RIDE, crash=(k == 0), vel=106)
for k in range(2):                                                 # the groove, in E
    riff([C3, C8], k0 + 6 + k, [(b, r + 2, ln, kd) for b, r, ln, kd in GROOVE[k]], 112, gate=0.7)
    kit(k0 + 6 + k, kicks=(0, .25, 1, 1.25), snares=(1, 3), crash=(k == 0), vel=106)
for k in range(2):                                                 # the tremolo
    riff([C3, C8], k0 + 8 + k, [(i * .25, n, .25, "n") for i, n in enumerate(TREM[k])], 106, gate=0.7)
    skank_kit(k0 + 8 + k, 106, crash=(k == 0))
for k in range(2):                                                 # the drive
    eighths([C3, C8], k0 + 10 + k, DRIVE[0] if k == 0 else [E2] * 4 + [D3, D3, B2, B2], 110)
    kit(k0 + 10 + k, kicks=(0, 1, 2, 3), snares=(1, 3), hats=[i * .5 for i in range(8)], hat=RIDE, crash=(k == 0), vel=108)
for k in range(k0, k0 + 12, 2):                                    # the lead answers each one
    mel(C1, k + 1, KE, [(2, 11, 1), (3, 14, 1)], 110)
fill(k0 + 11, 3, "down", 108)
advance(k0 + 12)

# ======================================================================================
# 22 Final solo - E, 144 BPM, 8 bars: the hook, an octave up, then higher
# ======================================================================================
section(144, KE, name="final solo")
FS = [[(0, 11, 1), (1, 11, .5), (1.5, 13, .5), (2, 14, 2)], [(0, 11, 1), (1, 11, .5), (1.5, 13, .5), (2, 16, 2)],
      [(0, 14, .5), (.5, 13, .5), (1, 11, .5), (1.5, 10, .5), (2, 9, 1), (3, 10, 1)], [(0, 11, 4)],
      [(0, 14, 1), (1, 14, .5), (1.5, 15, .5), (2, 16, 2)], [(0, 16, 1), (1, 15, 1), (2, 14, 2)],
      [(i * .25, 14 - i, .25) for i in range(8)] + [(2, 9, 2)], [(0, 14, 4)]]
for k, r in enumerate([E2, Cn3, D3, B2] * 2):
    eighths([C3, C8], k, r, 108)
    rock_kit(k, 106, crash=(k % 2 == 0))
    chord(C11, t(k), KE.tri(TRI[r] + (7 if TRI[r] < 3 else 0)), 4, 90)
sing(0, FS, KE, 118, depth=320)
fill(7, 2, "down", 104)
advance(8)

# ======================================================================================
# 23 Black Horsemen closer - E, 72 BPM: acoustic intro, the slow epic build, the last chord
# ======================================================================================
section(72, KEh, name="closer (Black Horsemen) acoustic")
prog(C2, t(0) - 30, 24, vol=110, pan=40, rev=70)                   # Nylon guitar
prog(C6, t(0) - 30, 89, vol=90, pan=88, rev=90, expr=60)           # Warm pad
BHC = [[40, 47, 52, 55, 59, 55, 52, 47], [48, 52, 55, 60, 64, 60, 55, 52], [45, 52, 57, 60, 64, 60, 57, 52],
       [47, 51, 54, 57, 63, 57, 54, 51]] * 2
for k, arp in enumerate(BHC):
    for i, n in enumerate(arp):
        note(C2, t(k, i * .5), n, ring(arp + sum(BHC[k + 1:k + 2], []), i, 1.5), 92 if i == 0 else 80, jitter=3)
    chord(C6, t(k), [arp[1], arp[2], arp[3]], 4, 76)
    note(C5, t(k), arp[0] - 12, 4, 84)
sing(4, [[(0, 7, 2), (2, 9, 1), (3, 8, 1)], [(0, 7, 3), (3, 6, 1)], [(0, 5, 2), (2, 7, 2)], [(0, 6, 4)]], KEh, 98, depth=200)
mel(C1, 1, KEh, [(2, 4, 2)], 90)
advance(8)
section(72, KEh, name="closer (Black Horsemen) epic")
BHR = [(E2, 0), (Cn3, 5), (A2, 3), (B2, 4), (E2, 0), (Cn3, 5), (B2, 4), (E2, 0)]
BHL = [[(0, 11, 1), (1, 11, .5), (1.5, 13, .5), (2, 14, 2)], [(0, 14, 2), (2, 12, 2)], [(0, 12, 2), (2, 9, 2)], [(0, 11, 4)],
       [(0, 14, 1), (1, 16, 1), (2, 14, 2)], [(0, 12, 2), (2, 11, 2)], [(0, 13, 4)], [(0, 14, 4)]]
ramp(C4, 11, t(0), t(6), 70, 127)
ramp(C11, 11, t(0), t(6), 70, 127)
for k, (r, d) in enumerate(BHR):
    riff([C3, C8], k, [(0, r, 4, "p")], 110 + k, gate=0.98)
    tri = [59, 63, 66] if r == B2 else KEh.tri(d + (7 if d < 3 else 0))
    chord(C11, t(k), tri, 4, 96 + k * 2)
    chord(C4, t(k), [n - 12 for n in tri], 4, 96, gate=0.98)
    kit(k, kicks=(0, 2), snares=(2,), hats=(0, 1, 2, 3), hat=RIDE, crash=True, vel=104 + k)
    note(C15, t(k), E2 if r == E2 else B2, 2, 110)
sing(0, BHL, KEh, 116, depth=320)
for i in range(16):
    note(C15, t(7, 2) + i * TPB // 8, E2, 0.125, 70 + i * 3, jitter=0)
advance(8)
section(60, KEh, name="the last chord")
end = t(0)
riff([C3, C8], 0, [(0, E2, 12, "p")], 120, gate=1.0)
chord(C11, end, [52, 55, 59, 64, 67, 71], 12, 110, gate=1.0)
chord(C4, end, [28, 40, 47, 52, 55, 59], 12, 112, gate=1.0)
note(C1, end, KEh(14), 12, 120, jitter=0, gate=1.0)
vib(C1, end + TPB, end + 10 * TPB, 0, 360)
bend_curve(C1, end + 10 * TPB, end + 12 * TPB - 20, 0, -8192, 16)
drum(end, CRASH, 124)
drum(end, CRASH2, 118)
drum(end, KICK, 124)
for i in range(64):
    note(C15, end + i * TPB // 6, E2, 1 / 6, max(40, 116 - i), jitter=0)
for c_ in (C1, C3, C8, C5, C4, C11, C15):
    ramp(c_, 7, t(2), t(3), 110, 0)
end_tick = t(3) + TPB * 2

# ======================================================================================
# checks: notes in key, no program change under a held note, no unintended silence
# ======================================================================================
allow.sort(key=lambda a: a[0])
bad = []
for tk, _o, m in events:
    if m.type != "note_on" or not m.velocity or m.channel == DR:
        continue
    if any(ch == m.channel and a <= tk < b for ch, a, b in nocheck):
        continue
    sec = [a for a in allow if a[0] <= tk + 30]
    if not sec:
        continue
    t0, pcs, extra, name = sec[-1]
    if m.note % 12 not in pcs | extra:
        bad.append((name, m.channel + 1, m.note, tk))
if bad:
    print(f"{len(bad)} notes out of key (section: channel / note names, first tick):")
    seen = {}
    for name, ch_, n_, tk in bad:
        seen.setdefault(name, {}).setdefault((ch_, n_ % 12), tk)
    PCN = "C C# D D# E F F# G G# A A# B".split()
    for name, hits in seen.items():
        print("   ", name + ":", ", ".join(f"ch{c} {PCN[p]} @{tk}" for (c, p), tk in sorted(hits.items())))
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

meta = [(tk, 0, mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm))) for tk, bpm in tempos]
meta += [(tk, 0, mido.MetaMessage("time_signature", numerator=n, denominator=d)) for tk, n, d in sigs]
meta += [(tk, 0, mido.MetaMessage("marker", text=nm)) for tk, nm in names]
allev = sorted(meta + events, key=lambda e: (e[0], e[1]))
mf = mido.MidiFile(ticks_per_beat=TPB)
tr = mido.MidiTrack()
mf.tracks.append(tr)
tr.append(mido.MetaMessage("track_name", name="A Tribute to the Metal Gods", time=0))
tr.append(mido.Message("sysex", data=[0x41, 0x10, 0x42, 0x12, 0x40, 0x00, 0x7F, 0x00, 0x41], time=0))
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

# Format 1 for editors: a conductor track, then one named track per channel
mf = common.format1(mf)
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "midi", "metal_gods.mid")
os.makedirs(os.path.dirname(out), exist_ok=True)
mf.save(out)
n_on = sum(1 for m in tr if m.type == "note_on" and m.velocity)
print(f"{out}: Format 1, {len(mf.tracks)} tracks (ties kept in order, <= {mf.max_shift} ticks late), "
      f"{mf.length:.1f} s ({int(mf.length // 60)}:{int(mf.length % 60):02d}), {n_on} notes, "
      f"{sum(1 for m in tr if m.type == 'program_change')} program changes, all in key")
