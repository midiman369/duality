"""Write "Adventure Game Night", an original ~3 minute adventure-game medley for Duality Voodoo.

    python tests/make_voodoo_demo2.py [out.mid]     (default tests/midi/adventure_game_night.mid)

The second Voodoo demo (the first is make_voodoo_demo.py): a GM file (GM System On, GM capitals)
in two halves and a finale. Two original main tunes share one 8-bar progression (I vi IV V I vi
ii V), so they work as counterpoint: the Rascal's tune (quick, syncopated off-beat eighths) carries
the LucasArts half, the Hero's tune (long singing notes) the Sierra half, and the finale plays them
together. In minor and dorian keys the V chord is a dominant (its leading tone raised).

   Prologue           G    90   a creaking door, footsteps, the door shuts
   Monkey Island      G    80   reggae one-drop: organ bubble, guitar skank, harmonica (the Rascal's
                                tune), steel-drum pings, horn stabs, the Hero's tune hinted on pan flute
   (bridge)           Dm   80   a car passing, a siren, brakes
   Sam & Max          Dm  208   bebop chase: alto + trumpet head over a walking bass, then a
                                big-band shout chorus (brass, trombone, tenor)
   (intermission)     Em   80   a record scratch, windchime, a horse: LucasArts -> Sierra
   King's Quest       Em   96   the dark forest: lute-like guitar, pizzicato, dulcimer, the Hero's
                                tune on oboe, then French horn, choir and strings (ch6 pizz -> strings)
   (bridge)           Am   80   a jet, a starship, an explosion
   Space Quest        Am  132   synth odyssey: square arpeggios sweeping left-right, synth bass,
                                the Hero's tune on a saw lead, orch hits panned hard left / right
   (bridge)           F    80   a heartbeat, a laugh, applause
   Leisure Suit Larry F   120   disco: four on the floor, octave slap bass, clavinet, Rhodes, the
                                Hero's tune on synth brass + strings, horn stabs, a string run
   Finale             C   112   both tunes together, then all 15 melody channels; applause, a laugh

Sound effects are CM-32L rhythm keys on ch10 (82-108; 24-29 for the six Duality moves there) over
a melodic bridge, so plain MT-32s never fall silent (the build checks it). Program changes move
channels between LA- and PCM-friendly sounds (ch1 harmonica -> alto sax, ch5 organ -> vibes -> harp
-> polysynth -> Rhodes -> organ, ch6 pizzicato -> strings, ch3 piano -> clavinet -> piano). Format 1.
The build fails if a note leaves its section's key, a program change lands under a held note, or
on a silence over 1.5 s.
"""
import os
import random
import sys

import mido

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common  # noqa: E402

TPB = 480
rng = random.Random(1987)
events = []          # (tick, order, message)
tempos, sigs, allow, names = [], [], [], []

C1, C2, C3, C4, C5, C6, C7, C8, C9, DR, C11, C12, C13, C14, C15, C16 = range(16)

# CM-32L sound effects (rhythm part); 76-81 sit on 24-29 under Duality Voodoo on CM outs
LAUGH, SCREAM, PUNCH, HEARTBEAT, STEPS1, STEPS2 = 24, 25, 26, 27, 28, 29
(APPLAUSE, CREAK, DOOR, SCRATCH, WINDCHIME, ENGINE, CARSTOP, CARPASS, CRASHFX, SIREN, TRAIN, JET,
 HELI, STARSHIP, PISTOL, MGUN, LASER, EXPLOSION, DOG, HORSE, BIRDS, RAIN, THUNDER, WIND, WAVES,
 STREAM, BUBBLE) = range(82, 109)
SFX = set(range(24, 30)) | set(range(82, 109))

KICK, STICK, SNARE, CLAP, CHH, PHH, OHH, CRASH, RIDE, TAMB = 36, 37, 38, 39, 42, 44, 46, 49, 51, 54
LFTOM, LTOM, MTOM, HTOM, CABASA, SHAKE = 41, 45, 47, 50, 69, 70

MODES = {"major": [0, 2, 4, 5, 7, 9, 11], "minor": [0, 2, 3, 5, 7, 8, 10], "dorian": [0, 2, 3, 5, 7, 9, 10]}


class Key:
    def __init__(self, tonic, mode):
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

    def lead_tone(self):
        return (self.tonic - 1) % 12


# --------------------------------------------------------------------------------------
pos = TPB * 4
BPB = 4.0
SWING = False


def section(bpm, key, name, swing=False):
    global SWING
    SWING = swing
    tempos.append((pos, bpm))
    sigs.append((pos, 4, 4))
    extra = {key.lead_tone()} if key.minorish else set()
    allow.append((pos, key.pcs(), extra, name))
    names.append((pos, name))


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
    """Melody: one string per bar of 'degree/beats' tokens; 'r' rests, a trailing # or b alters.
    A bar may be (string, chord degree): over a dominant V (minor / dorian keys) the leading tone
    is raised wherever the line lands on degree 7, harmony lines (shift) included."""
    for i, bar in enumerate(bars):
        lt = False
        if isinstance(bar, tuple):
            bar, cd = bar
            lt = key.minorish and cd == 4
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
# the two tunes over one progression: I vi IV V I vi ii V (degrees of the section's key)
# --------------------------------------------------------------------------------------
P = [0, 5, 3, 4, 0, 5, 1, 4]
RASCAL = ["r/.5 7/.5 9/.5 7/.5 r/.5 4/.5 7/1", "r/.5 9/.5 7/.5 5/.5 r/.5 4/.5 5/1",
          "r/.5 10/.5 9/.5 7/.5 r/.5 5/.5 7/1", "8/.5 8/.5 r/.5 6/.5 8/1 r/1",
          "r/.5 7/.5 9/.5 11/.5 r/.5 9/.5 7/1", "12/.5 11/.5 9/.5 7/.5 9/1 r/1",
          "r/.5 8/.5 10/.5 12/.5 r/.5 10/.5 8/1", "11/1 8/.5 6/.5 4/1 r/1"]
HERO = ["4/2 2/1 4/1", "5/3 7/1", "7/1.5 5/.5 3/2", "4/3 r/1",
        "4/1 7/1 9/2", "9/1.5 7/.5 5/2", "5/1 3/1 8/1 7/1", "6/2 4/1 r/1"]


def tune(bars, key, idx=range(8)):
    """The tune's bars with the chord degree each one sits on (see line())."""
    return [(bars[i], P[i]) for i in idx]


def harmony(key, d, seventh=False):
    """Pitch classes of the chord on degree d (V is a dominant in minor / dorian)."""
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


def bridge(key, vel=84):
    """Two bars of the music-box motif over the pad, in the next scene's key (I then V).
    Plain MT-32s hear this alone; CM units add the sound effects."""
    lt = "6#" if key.minorish else "6"
    line(C13, 0, key.at(key.tonic % 12 + 72), ["0/.5 2/.5 4/.5 7/1.5 4/1", f"{lt}/.5 4/.5 1/1 4/2"], vel)
    for b, d in enumerate((0, 4)):
        pcs = harmony(key, d)
        chord(C9, t(b), voice(pcs, 55, 4), 4, 70, gate=1.0)
        note(C9, t(b), low_root(pcs, 36), 4, 64, gate=1.0)


# ======================================================================================
# setup burst
# ======================================================================================
FIRST = {
    C1: (22, 100, 64),   # harmonica (the Rascal's tune)
    C2: (61, 92, 40),    # brass section
    C3: (27, 86, 30),    # clean guitar (skank)
    C4: (33, 106, 64),   # fingered bass
    C5: (16, 82, 92),    # drawbar organ (bubble)
    C6: (45, 90, 48),    # pizzicato strings
    C7: (56, 96, 80),    # trumpet
    C8: (52, 86, 60),    # choir aahs
    C9: (89, 76, 64),    # warm pad (bridges)
    C11: (114, 90, 100),  # steel drums
    C12: (66, 94, 56),   # tenor sax
    C13: (10, 100, 64),  # music box (bridges)
    C14: (15, 84, 24),   # dulcimer
    C15: (57, 92, 72),   # trombone
    C16: (75, 84, 100),  # pan flute
}
for ch, (p, v, pan) in FIRST.items():
    prog(ch, 12, p, v, pan)
cc(DR, 13, 7, 110)

KG = Key(55, "major")
KD = Key(62, "dorian")
KE = Key(64, "minor")
KA = Key(69, "minor")
KF = Key(65, "major")
KC = Key(60, "major")

# ======================================================================================
# Prologue: a creaking door, footsteps, the door shuts
# ======================================================================================
section(90, KG, "Prologue")
bridge(KG)
sfx(0, 0, CREAK, 100)
sfx(0, 2, STEPS1, 96)
sfx(0, 3, STEPS2, 96)
sfx(1, 2, DOOR, 112)
advance(2)

# ======================================================================================
# Monkey Island: reggae one-drop, G major, 80
# ======================================================================================
section(80, KG, "Monkey Island (reggae)")


def reggae_bar(b, d, horns=False, pings=False):
    pcs = harmony(KG, d)
    root = low_root(pcs, 36)
    for off, n, ln, v in ((0.5, root, 1.0, 100), (2.0, root + 7, 0.5, 90),
                          (2.5, root + 12, 0.5, 88), (3.0, root, 1.0, 96)):
        note(C4, t(b, off), n, ln, v)
    for off in (1, 3):                                             # guitar skank on 2 and 4
        chord(C3, t(b, off), voice(pcs, 62, 3), 0.25, 84, roll=8)
    for k, off in enumerate((0.5, 1.5, 2.5, 3.5)):                 # organ bubble
        chord(C5, t(b, off), voice(pcs, 55 if k % 2 == 0 else 62, 3), 0.3, 70)
    drum(t(b, 2), KICK, 100)                                        # the one drop
    drum(t(b, 2), STICK, 92)
    for k in range(8):
        drum(t(b, k * 0.5), CHH, 66 if k % 2 == 0 else 52)
    drum(t(b, 3.5), OHH, 64)
    if pings:
        for off in (0.5, 1.5, 2.5, 3.5):
            note(C11, t(b, off), voice(pcs, 76, 3)[(int(off) + b) % 3], 0.4, 78)
    if horns:
        for off in (1.5, 3.5):
            chord(C2, t(b, off), voice(pcs, 60, 3), 0.4, 92)


for b in range(12):
    reggae_bar(b, P[b % 8], horns=b >= 8, pings=b < 4 or b >= 8)
line(C1, 4, KG, tune(RASCAL, KG), 104)                             # harmonica: the Rascal's tune
line(C16, 8, KG.at(67), tune(HERO, KG, range(4, 8)), 78)           # pan flute hints the Hero's tune
drum(t(11, 3), CRASH, 96)
advance(12)

# ======================================================================================
# bridge -> Sam & Max: a car passing, a siren, brakes
# ======================================================================================
section(80, KD, "Bridge: the chase")
prog(C1, pos, 65, 100, 64)      # harmonica -> alto sax
prog(C3, pos, 0, 88, 40)        # clean guitar -> piano
prog(C4, pos, 32, 106, 64)      # fingered -> acoustic bass
prog(C5, pos, 11, 80, 90)       # organ -> vibes
bridge(KD)
sfx(0, 0, CARPASS, 104)
sfx(0, 2, SIREN, 100)
sfx(1, 2, CARSTOP, 110)
advance(2)

# ======================================================================================
# Sam & Max: bebop chase, D dorian, 208 swing
# ======================================================================================
section(208, KD, "Sam & Max (bebop chase)", swing=True)


def bebop_bar(b, d, next_d, shout=False):
    pcs = harmony(KD, d, seventh=True)
    root = low_root(pcs, 38)
    nxt = low_root(harmony(KD, next_d), 38)
    # root, third, fifth, then a scale step next to the coming root (a diatonic walk)
    walk = [root, voice(pcs, root + 1, 1)[0], voice(pcs, root + 5, 1)[0]]
    scale = [KD(k) - 24 for k in range(-7, 21)]
    walk.append(min((n for n in scale if 1 <= abs(n - nxt) <= 2), key=lambda n: abs(n - walk[2])))
    for k, n in enumerate(walk):
        note(C4, t(b, k), n, 1, 98 if k == 0 else 88, gate=0.95)
    chord(C3, t(b, 0), voice(pcs, 53, 4), 0.5, 74)                  # piano comps (Charleston)
    chord(C3, t(b, 1.5), voice(pcs, 53, 4), 0.5, 68)
    if b % 2 == 0:
        chord(C5, t(b, 0), voice(pcs, 65, 3), 1.5, 66, roll=20)      # vibes
    for off, v in ((0, 78), (1, 74), (1.5, 60), (2, 78), (3, 74), (3.5, 60)):
        drum(t(b, off), RIDE, v)
    drum(t(b, 1), PHH, 64)
    drum(t(b, 3), PHH, 64)
    drum(t(b, rng.choice((0.5, 1.5, 2.5, 3.5))), SNARE, rng.randint(40, 70))
    if shout:
        drum(t(b, 0), KICK, 70)


for b in range(16):
    bebop_bar(b, P[b % 8], P[(b + 1) % 8], shout=b >= 8)
head = tune(RASCAL, KD)
line(C1, 0, KD, head, 104)                                          # alto sax
line(C7, 0, KD, head, 96)                                           # trumpet in unison
line(C12, 0, KD.at(50), head, 90)                                   # tenor an octave down
line(C7, 8, KD.at(74), head, 104)                                   # shout chorus: trumpet up top
line(C1, 8, KD, head, 100)
line(C2, 8, KD, head, 96, shift=-2)                                 # brass a third below
line(C15, 8, KD.at(50), head, 94, shift=-5)                         # trombone a sixth below
line(C12, 8, KD.at(50), head, 90)
drum(t(15, 3), CRASH, 104)
drum(t(15, 3), KICK, 100)
advance(16)

# ======================================================================================
# intermission -> King's Quest: a record scratch, windchime, a horse
# ======================================================================================
section(80, KE, "Intermission")
prog(C3, pos, 24, 88, 36)       # piano -> nylon guitar (lute)
prog(C4, pos, 43, 100, 64)      # acoustic bass -> contrabass
prog(C5, pos, 46, 88, 86)       # vibes -> harp
prog(C7, pos, 60, 92, 70)       # trumpet -> French horn
prog(C12, pos, 68, 98, 60)      # tenor sax -> oboe (the Hero's tune)
prog(C11, pos, 47, 100, 64)     # steel drums -> timpani
bridge(KE)
sfx(0, 0, SCRATCH, 110)
sfx(0, 2, WINDCHIME, 96)
sfx(1, 1, HORSE, 104)
advance(2)

# ======================================================================================
# King's Quest: the dark forest, E minor, 96
# ======================================================================================
section(96, KE, "King's Quest (the dark forest)")


def forest_bar(b, d, full=False):
    pcs = harmony(KE, d)
    lo = voice(pcs, 52, 3)
    for k, n in enumerate(lo + [lo[1] + 12, lo[2] + 12, lo[0] + 24, lo[2] + 12, lo[1] + 12][:5]):
        note(C3, t(b, k * 0.5), n, 0.6, 72 + (8 if k == 0 else 0))
    if not full:
        note(C6, t(b, 0), low_root(pcs, 40), 0.5, 84)               # pizzicato
        note(C6, t(b, 2), low_root(pcs, 40) + (pcs[2] - pcs[0]) % 12, 0.5, 78)   # the chord's fifth
    if b % 2 == 1:
        for k in range(8):                                          # dulcimer shimmer
            note(C14, t(b, 2 + k * 0.25), voice(pcs, 72, 3)[k % 3], 0.25, 58 + 2 * k)
    drum(t(b, 0), LTOM, 74)
    drum(t(b, 2.5), LTOM, 62)
    drum(t(b, 1), TAMB, 48)
    drum(t(b, 3), TAMB, 52)
    if b >= 4:
        chord(C5, t(b), voice(pcs, 59, 4), 4, 66, roll=40)          # harp
        note(C4, t(b), low_root(pcs, 28), 4, 86, gate=0.97)         # contrabass
    if full:
        chord(C6, t(b), voice(pcs, 52, 4), 4, 76, gate=0.99)        # strings
        chord(C8, t(b), voice(pcs, 60, 3), 4, 72, gate=0.99)        # choir


for b in range(12):
    if b == 8:
        prog(C6, t(8), 49, 92, 48)                                  # pizzicato -> slow strings
    forest_bar(b, P[b % 8], full=b >= 8)
line(C12, 4, KE, tune(HERO, KE), 102)                               # oboe: the Hero's tune
line(C7, 8, KE.at(52), tune(HERO, KE, range(4, 8)), 92)             # French horn, an octave down
for k in range(12):                                                 # timpani roll on the V
    note(C11, t(11, k / 4), low_root(harmony(KE, 4), 40), 0.25, 60 + 4 * k)
advance(12)

# ======================================================================================
# bridge -> Space Quest: a jet, a starship, an explosion
# ======================================================================================
section(80, KA, "Bridge: lift-off")
prog(C4, pos, 39, 104, 64)      # contrabass -> synth bass 2
prog(C5, pos, 90, 80, 90)       # harp -> polysynth
prog(C11, pos, 55, 100, 20)     # timpani -> orch hit
prog(C12, pos, 81, 96, 60)      # oboe -> saw lead
prog(C14, pos, 80, 80, 0)       # dulcimer -> square (arpeggios)
prog(C16, pos, 103, 80, 64)     # pan flute -> sci-fi pad
bridge(KA)
sfx(0, 0, JET, 104)
sfx(0, 2, STARSHIP, 104)
sfx(1, 2, EXPLOSION, 120)
advance(2)

# ======================================================================================
# Space Quest: synth odyssey, A minor, 132
# ======================================================================================
section(132, KA, "Space Quest (synth odyssey)")


def synth_bar(b, d, full=False):
    pcs = harmony(KA, d)
    root = low_root(pcs, 33)
    arp = voice(pcs, 57, 6)
    for k in range(16):
        note(C14, t(b, k * 0.25), arp[[0, 1, 2, 3, 4, 5, 4, 3][k % 8]], 0.25, 64 + (10 if k % 4 == 0 else 0))
    for k in range(8):
        note(C4, t(b, k * 0.5), root + (12 if k % 2 else 0), 0.45, 96)
    chord(C5, t(b, 0), voice(pcs, 60, 4), 1.5, 70)
    chord(C5, t(b, 2.5), voice(pcs, 60, 4), 1.0, 66)
    drum(t(b, 0), KICK, 104)
    drum(t(b, 2), KICK, 98)
    drum(t(b, 2.5), KICK, 84)
    drum(t(b, 1), CLAP, 92)
    drum(t(b, 3), CLAP, 96)
    for k in range(16):
        drum(t(b, k * 0.25), CHH, 50 + (16 if k % 2 == 0 else 0))
    if b % 4 == 0:
        note(C16, t(b), low_root(pcs, 45), 16, 70, gate=0.99)
        note(C16, t(b), low_root(pcs, 45) + 7, 16, 64, gate=0.99)
    if full:
        chord(C6, t(b), voice(pcs, 57, 4), 4, 74, gate=0.99)
        chord(C8, t(b), voice(pcs, 57, 3), 4, 70, gate=0.99)
        cc(C11, t(b) - 4, 10, 10 if b % 2 == 0 else 117)           # orch hits ping-pong
        note(C11, t(b, 0), root + 24, 0.5, 104)


for b in range(12):
    synth_bar(b, P[b % 8], full=b >= 8)
ramp(C14, 10, t(0), t(6), 0, 127, 32)                               # arpeggios sweep across
ramp(C14, 10, t(6), t(12) - 8, 127, 0, 32)
line(C12, 4, KA, tune(HERO, KA), 104)                               # saw lead: the Hero's tune
drum(t(4), CRASH, 100)
drum(t(8), CRASH, 104)
advance(12)

# ======================================================================================
# bridge -> Leisure Suit Larry: a heartbeat, a laugh, applause
# ======================================================================================
section(80, KF, "Bridge: the club")
prog(C3, pos, 7, 84, 30)        # nylon guitar -> clavinet
prog(C4, pos, 37, 106, 64)      # synth bass 2 -> slap bass 2
prog(C5, pos, 4, 86, 92)        # polysynth -> Rhodes
prog(C6, pos, 48, 92, 40)       # slow strings -> strings
prog(C7, pos, 56, 96, 80)       # French horn -> trumpet
prog(C12, pos, 62, 96, 60)      # saw lead -> synth brass
cc(C11, pos, 10, 64)
bridge(KF)
sfx(0, 0, HEARTBEAT, 100)
sfx(0, 1, HEARTBEAT, 100)
sfx(0, 2, LAUGH, 108)
sfx(1, 1, APPLAUSE, 96)
advance(2)

# ======================================================================================
# Leisure Suit Larry: disco, F major, 120
# ======================================================================================
section(120, KF, "Leisure Suit Larry (disco)")


def disco_bar(b, d, full=False):
    pcs = harmony(KF, d)
    root = low_root(pcs, 29)
    for k in range(8):
        note(C4, t(b, k * 0.5), root + (12 if k % 2 else 0), 0.4, 100 if k % 2 else 92)
    for k in (1, 3, 6, 7, 9, 11, 14, 15):                           # clavinet chops
        chord(C3, t(b, k * 0.25), voice(pcs, 60, 3), 0.2, 70)
    chord(C5, t(b, 0), voice(pcs, 57, 4), 2, 70)                    # Rhodes
    chord(C5, t(b, 2), voice(pcs, 57, 4), 2, 66)
    for k in range(4):
        drum(t(b, k), KICK, 104)
        drum(t(b, k + 0.5), OHH, 72)
    drum(t(b, 1), CLAP, 94)
    drum(t(b, 3), CLAP, 96)
    for k in range(16):
        drum(t(b, k * 0.25), CHH, 44)
    if full:
        chord(C2, t(b, 3.5), voice(pcs, 60, 3), 0.4, 98)            # horn stabs
        note(C15, t(b), voice(pcs, 48, 3)[1], 3.5, 78)              # trombone


for b in range(12):
    disco_bar(b, P[b % 8], full=b >= 8)
hero_f = tune(HERO, KF)
line(C12, 4, KF, hero_f, 104)                                       # synth brass
line(C6, 4, KF.at(77), hero_f, 86)                                  # strings an octave up
for k in range(8):                                                  # string run into the finale
    note(C6, t(11, 2 + k * 0.25), KF.at(77)(k), 0.25, 80 + 3 * k)
drum(t(11, 3), CRASH, 104)
advance(12)

# ======================================================================================
# Finale: both tunes together, then all 15 melody channels, C major 112
# ======================================================================================
section(112, KC, "Finale (both tunes)")
prog(C3, pos, 0, 90, 40)        # clavinet -> piano
prog(C4, pos, 33, 106, 64)      # slap bass 2 -> fingered bass
prog(C5, pos, 16, 80, 92)       # Rhodes -> organ
prog(C12, pos, 60, 96, 56)      # synth brass -> French horn (the Hero's tune)
prog(C13, pos, 9, 90, 70)       # music box -> glockenspiel (the Rascal's tune, up high)
prog(C14, pos, 98, 76, 30)      # square -> crystal
prog(C16, pos, 75, 84, 100)     # sci-fi pad -> pan flute


def finale_bar(b, d, tutti):
    pcs = harmony(KC, d)
    root = low_root(pcs, 36)
    chord(C3, t(b, 0), voice(pcs, 55, 4), 1.5, 76)
    chord(C3, t(b, 2), voice(pcs, 55, 4), 1.5, 72)
    for off, n in ((0, root), (1.5, root + 7), (2, root + 12), (3, root + 7)):
        note(C4, t(b, off), n, 0.9, 98)
    chord(C9, t(b), voice(pcs, 55, 4), 4, 60, gate=1.0)
    drum(t(b, 0), KICK, 100)
    drum(t(b, 2), KICK, 96)
    drum(t(b, 1), SNARE, 92)
    drum(t(b, 3), SNARE, 96)
    for k in range(8):
        drum(t(b, k * 0.5), CHH, 64 if k % 2 == 0 else 50)
    if tutti:
        chord(C5, t(b), voice(pcs, 55, 4), 4, 64, gate=0.98)        # organ
        chord(C6, t(b), voice(pcs, 55, 4), 4, 74, gate=0.99)        # strings
        chord(C8, t(b), voice(pcs, 60, 3), 4, 70, gate=0.99)        # choir
        chord(C2, t(b, 1.5), voice(pcs, 58, 3), 0.4, 94)            # brass stabs
        chord(C2, t(b, 3.5), voice(pcs, 58, 3), 0.4, 94)
        note(C11, t(b, 0), root + 24, 0.5, 100)                     # orch hit
        for k in range(8):
            note(C14, t(b, k * 0.5), voice(pcs, 79, 3)[k % 3], 0.5, 54)


for b in range(16):
    finale_bar(b, P[b % 8], b >= 8)
for b0 in (0, 8):
    line(C1, b0, KC, tune(RASCAL, KC), 102)                          # alto sax: the Rascal's tune
    line(C12, b0, KC, tune(HERO, KC), 100)                           # French horn: the Hero's tune
    line(C15, b0, KC.at(48), tune(HERO, KC), 90)                     # trombone, an octave down
line(C13, 8, KC.at(72), tune(RASCAL, KC), 88)                        # glockenspiel an octave up
line(C7, 8, KC, tune(RASCAL, KC), 98)                                # trumpet joins the Rascal
line(C16, 8, KC.at(72), tune(HERO, KC), 80)                          # pan flute: the Hero up high
drum(t(8), CRASH, 108)
advance(16)

section(112, KC, "Finale: last chord")
end = t(0)
chord(C3, end, [36, 48, 55, 60, 64, 67, 72], 8, 100, gate=1.0)
chord(C6, end, [48, 55, 60, 64, 67], 8, 90, gate=1.0)
chord(C8, end, [60, 64, 67], 8, 84, gate=1.0)
chord(C2, end, [55, 60, 64, 67], 8, 100, gate=1.0)
chord(C5, end, [48, 55, 64, 67], 8, 70, gate=1.0)
chord(C9, end, [48, 55, 64, 67], 8, 64, gate=1.0)
note(C1, end, 72, 8, 100, gate=1.0)
note(C12, end, 67, 8, 96, gate=1.0)
note(C15, end, 48, 8, 92, gate=1.0)
note(C7, end, 79, 8, 96, gate=1.0)
note(C4, end, 36, 8, 104, gate=1.0)
note(C11, end, 60, 1, 110)
note(C13, end, 84, 4, 90)
note(C14, end, 91, 4, 60)
note(C16, end, 84, 6, 80, gate=1.0)
drum(end, CRASH, 116)
drum(end, KICK, 116)
sfx(0, 2, APPLAUSE, 104)
sfx(1, 0, APPLAUSE, 110)
sfx(1, 2, LAUGH, 108)
for c_ in (C1, C2, C3, C4, C5, C6, C7, C8, C9, C12, C15, C16):
    ramp(c_, 7, t(1), t(2), 100, 0, 16)
end_tick = t(2) + TPB * 2

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
tr.append(mido.MetaMessage("track_name", name="Adventure Game Night", time=0))
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
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "midi", "adventure_game_night.mid")
os.makedirs(os.path.dirname(out), exist_ok=True)
mf.save(out)
n_on = sum(1 for m in tr if m.type == "note_on" and m.velocity)
n_fx = sum(1 for m in tr if m.type == "note_on" and m.velocity and m.channel == DR and m.note in SFX)
chs = sorted({m.channel + 1 for m in tr if m.type == "note_on" and m.channel != DR})
print(f"{out}: Format 1, {len(mf.tracks)} tracks, {mf.length:.1f} s ({int(mf.length // 60)}:"
      f"{int(mf.length % 60):02d}), {n_on} notes ({n_fx} sound effects), "
      f"{sum(1 for m in tr if m.type == 'program_change')} program changes, melody channels {chs}, all in key")
