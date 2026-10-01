"""Build "A Tribute to the Metal Gods" for Duality from the Suno MIDI stems.

    python tests/make_metalgods.py [stems.zip or folder] [out.mid]
        (defaults: tests/midi/A_Tribute_to_the_Metal_Gods__MIDI.zip, tests/midi/metal_gods.mid)

The stems are the song author's own (Suno export) and stay out of the repo, like the test songs;
this script is the arrangement. It reads the nine stem files, cleans them up and adds the
layers Anima is built to play, the way ONESTOP2 and the metal test do:

  timing    Suno's 705 tempo events become a steady 158.5 BPM (the ritard and the 121 BPM outro
            stay); every stem is shifted onto the drums' 16th grid (each stem has its own
            latency) and snapped: 16ths, 32nds for the lead lines.
  parts     ch1  lead guitar: the vocal melody (screams included), Suno's lead licks in the gaps,
                 and every solo (one player, so it keeps its own unit: the GTR Multi 3 showcase)
            ch3 / ch8  the stereo-wide rhythm duo, hard left / right, power chords only
                 (ch8 takes the harmony line in the twin-guitar verse)
            ch5  bass;  ch10  drums on the SC-88Pro map's Standard 1 kit (CC32 3, the one
                 non-GM touch)
            ch4  rock organ: Suno's synth riff under chorus 1, held chords under chorus 2 and
                 the big finish (rotary flips on held chords)
            ch11 choir: the intro hook, the gothic verse, chorus 2, the big finish, the end
            ch15 timpani: section hits and rolls;  ch16 free for Anima's foley
  dynamics  section levels and beat accents where Suno's velocities are flat.
  added     an 8-bar continuation of the virtuoso solo, a 4-bar drum solo before the outro, and
            an 8-bar final solo built on the intro hook.
  dropped   the low "bass" in the drum stem (kick bleed), the 2-note keyboard, the flute
            (it doubles the outro solo) and the low synth fragments.

Format 1 (conductor + one named track per channel), GS reset at the start, no file EFX. The
build fails if an added part leaves its section's key, if a program change lands under a held
note, or on a silence over 1.5 s.
"""
import glob
import io
import math
import os
import random
import sys
import zipfile
from collections import Counter, defaultdict

import mido
import mido.midifiles.meta as _meta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common  # noqa: E402


class _AnyKey(dict):
    def __missing__(self, key):        # one stem carries an impossible key signature (11 sharps)
        return "C"


_meta._key_signature_decode = _AnyKey(_meta._key_signature_decode)

TPB = 480
BAR = 4 * TPB
rng = random.Random(1980)
C1, C2, C3, C4, C5, C6, C7, C8, C9, DR, C11, C12, C13, C14, C15, C16 = range(16)
KICK, SNARE, LTOM, CHH, MTOM, OHH, HTOM, CRASH, RIDE, CRASH2 = 36, 38, 43, 42, 47, 46, 50, 49, 51, 57
TOMS = [HTOM, 48, MTOM, 45, LTOM, 41]
SEMI = 4096                       # pitch bend steps per semitone (2-semitone range)

# ======================================================================================
# 1  read the stems
# ======================================================================================
STEMS = ("Backing Vocals", "Bass", "Drums", "Guitar", "Keyboard", "Percussion", "Synth", "Vocals", "Woodwinds")


def load_stems(path):
    files = {}
    if os.path.isdir(path):
        for f in glob.glob(os.path.join(path, "*.mid")):
            files[os.path.basename(f)] = open(f, "rb").read()
    else:
        with zipfile.ZipFile(path) as z:
            for n in z.namelist():
                if n.lower().endswith(".mid"):
                    files[os.path.basename(n)] = z.read(n)
    out = {}
    for stem in STEMS:
        hit = [k for k in files if k.endswith(f"({stem}).mid")]
        if not hit:
            sys.exit(f"stem ({stem}) missing in {path}")
        out[stem] = mido.MidiFile(file=io.BytesIO(files[hit[0]]))
    return out


def spans(mf, track):
    """(start, end, note, velocity) of one stem track, in source ticks."""
    t, on, out = 0, {}, []
    for m in mf.tracks[track]:
        t += m.time
        if m.type == "note_on" and m.velocity:
            on.setdefault((m.channel, m.note), []).append((t, m.velocity))
        elif m.type in ("note_off", "note_on") and on.get((m.channel, m.note)):
            s, v = on[(m.channel, m.note)].pop(0)
            out.append((s, t, m.note, v))
    return sorted(out)


def phase(onsets):
    """Circular mean of the onsets' position inside a 16th (ticks)."""
    x = sum(math.cos(2 * math.pi * (s % 120) / 120) for s in onsets)
    y = sum(math.sin(2 * math.pi * (s % 120) / 120) for s in onsets)
    return (math.atan2(y, x) / (2 * math.pi) * 120) % 120


src_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "midi", "A_Tribute_to_the_Metal_Gods__MIDI.zip")
if not os.path.exists(src_path):
    print(f"SKIP: stems not found at {src_path} (the song author's own files; see tests/README.md)")
    sys.exit(77)
S = load_stems(src_path)
DRUM_SRC = spans(S["Drums"], 2) + spans(S["Drums"], 3) + spans(S["Percussion"], 1)
DPH = phase([s for s, *_ in DRUM_SRC])          # the drums sit DPH ticks into each 16th


def aligned(sp, grid=120, ref=None):
    """Shift a part onto the drums' grid (its own latency removed) and snap to `grid`."""
    if not sp:
        return []
    ph = phase([s for s, *_ in (ref or sp)])
    sh = ((DPH - ph + 60) % 120) - 60 + (120 - DPH)
    out = []
    for s, e, n, v in sp:
        a = int(round((s + sh) / grid)) * grid
        b = max(a + grid, int(round((e + sh) / grid)) * grid)
        out.append((a, b, n, v))
    return out


def mono(notes):
    """One line: a later onset ends the note before it; on a shared onset the top note wins."""
    by = {}
    for s, e, n, v in notes:
        if s not in by or n > by[s][2]:
            by[s] = (s, e, n, v)
    seq = [by[k] for k in sorted(by)]
    out = []
    for i, (s, e, n, v) in enumerate(seq):
        if i + 1 < len(seq):
            e = min(e, seq[i + 1][0])
        if e - s >= 30:
            out.append((s, e, n, v))
    return out


def overlaps(a, b):
    return a[0] < b[1] and b[0] < a[1]


# ---- the lead guitar: vocal melody first, then licks and solos only where it is free -------------
VOCAL = mono(sum((aligned(spans(S["Vocals"], i)) for i in (1, 2, 3, 4, 5, 6)), []))
SCREAM = {(s, n) for s, e, n, v in aligned(spans(S["Vocals"], 4)) + aligned(spans(S["Vocals"], 6))}
g1_raw = spans(S["Guitar"], 1)
g1 = aligned(g1_raw)                      # same order as g1_raw
by_onset = defaultdict(list)
for i, x in enumerate(g1):
    by_onset[x[0]].append(i)
lead_i = set()
for s, idx in by_onset.items():          # a high note over a low strum, or a strum up high, is a lick
    lo = min(g1[i][2] for i in idx)
    lead_i |= {i for i in idx if g1[i][2] >= 64 and (lo >= 60 or g1[i][2] - lo > 24)}
G1_RHY = [x for i, x in enumerate(g1) if i not in lead_i]
G1_LEAD = aligned([x for i, x in enumerate(g1_raw) if i in lead_i], 60, ref=g1_raw)   # licks keep 32nds


def lead_from(stem, track, lo=50, hi=96):
    return [x for x in aligned(spans(S[stem], track), 60) if lo <= x[2] <= hi]


LEAD_SOURCES = [lead_from("Synth", 7), lead_from("Guitar", 2), G1_LEAD, lead_from("Synth", 2),
                lead_from("Synth", 3, 55), lead_from("Synth", 11), lead_from("Guitar", 3)]
accepted = [(s, e, n, v, "voc") for s, e, n, v in VOCAL]
for src in LEAD_SOURCES:
    for s, e, n, v in mono(src):
        if not any(overlaps((s, e), (a[0], a[1])) for a in accepted):
            accepted.append((s, e, n, v, "lead"))
LEAD = sorted(accepted)

# ---- rhythm duo, bass, drums ------------------------------------------------------------------


def power(notes):
    """Keep root / fifth / octave of each strum (Suno stacks extra octaves and stray tops)."""
    by = defaultdict(list)
    for x in notes:
        by[x[0]].append(x)
    out = []
    for s, xs in by.items():
        lo = min(x[2] for x in xs)
        keep = {}
        for x in xs:
            if x[2] - lo in (0, 7, 12) and x[2] not in keep:
                keep[x[2]] = x
        out += keep.values()
    # each strum chokes the one before it (palm-muted metal rhythm, not a wash)
    onsets = sorted(by)
    nxt = {a: b for a, b in zip(onsets, onsets[1:])}
    return sorted((s, min(e, nxt.get(s, e)), n, v) for s, e, n, v in out)


RHY_L = power(G1_RHY)
RHY_R = power(aligned(spans(S["Bass"], 1)) + aligned(spans(S["Bass"], 3)))
BASS = aligned(spans(S["Bass"], 2)) + aligned(spans(S["Bass"], 4))
BASS = [x for x in BASS if not (x[0] >= 737 * TPB and x[2] == 28)]        # the end: D#, not D#+E
DRUMS = aligned(DRUM_SRC, ref=DRUM_SRC)
ORGAN_RIFF = [(s, e, n + 12, v) for s, e, n, v in aligned(spans(S["Synth"], 1))]
BACKING = sum((aligned(spans(S["Backing Vocals"], i)) for i in range(1, 7)), [])

# ======================================================================================
# 2  the timeline: source beats -> output, with three added passages
# ======================================================================================
KEY_MIN = [0, 2, 3, 5, 7, 8, 10]                 # D# natural minor (from D#)
KEY_PHR = [0, 1, 3, 5, 7, 8, 10]                 # D# phrygian (the outro's D# / E)
D_SHARP = 63                                      # D#4


def deg(d, mode=KEY_MIN, tonic=D_SHARP):
    o, i = divmod(int(d), 7)
    return tonic + 12 * o + mode[i]


SEGS = [  # (kind, src start beat, src end beat, out length in beats)
    ("copy", 0, 504, 504),
    ("solo+", 472, 504, 32),          # the virtuoso solo goes on over its own riff
    ("copy", 504, 684, 180),
    ("drums", 0, 0, 16),              # drum solo refrain, 121 BPM
    ("copy", 684, 728, 44),
    ("final", 688, 720, 32),          # the final solo over the outro riff
    ("copy", 728, 752, 24),
]
LEAD_IN = 2 * TPB                                 # after the GS reset
seg_out = []
pos = LEAD_IN
for kind, a, b, ln in SEGS:
    seg_out.append((kind, a, b, pos, pos + ln * TPB))
    pos += ln * TPB
END = pos


def out_tick(src_tick):
    for kind, a, b, o0, o1 in seg_out:
        if kind == "copy" and a * TPB <= src_tick < b * TPB:
            return o0 + src_tick - a * TPB
    return None


def out_bar(src_bar, beat=0.0):
    return out_tick(int(src_bar * BAR + beat * TPB))


def seg(kind):
    return next(x for x in seg_out if x[0] == kind)


events, notes_out, gen_spans = [], [], []   # gen_spans: added notes, for the key check


def ev(tick, order, msg):
    events.append((int(tick), order, msg))


def note(ch, tick, n, ticks, vel, gen=False):
    notes_out.append([ch, int(tick), int(tick) + max(15, int(ticks)), int(n), max(1, min(127, int(round(vel))))])
    if gen:
        gen_spans.append((int(tick), int(n), ch))


def cc(ch, tick, c, v):
    ev(tick, 1, mido.Message("control_change", channel=ch, control=c, value=max(0, min(127, int(v)))))


def ramp(ch, c, t0, t1, v0, v1, steps=24):
    for k in range(steps + 1):
        cc(ch, t0 + (t1 - t0) * k // steps, c, v0 + (v1 - v0) * k / steps)


def bend(ch, tick, value):
    ev(tick, 1, mido.Message("pitchwheel", channel=ch, pitch=max(-8192, min(8191, int(value)))))


def vibrato(ch, t0, t1, base=0, depth=700):
    step, k, tk = 40, 0, t0
    while tk < t1 - step:
        ramp_in = min(1.0, (tk - t0) / max(1, (t1 - t0) / 3))
        bend(ch, tk, base + depth * ramp_in * math.sin(k * math.pi / 3))
        tk += step
        k += 1
    bend(ch, t1, base)


def prog(ch, tick, program, vol=100, pan=64, rev=40, cho=0, expr=127, lsb=0):
    cc(ch, tick, 0, 0)
    cc(ch, tick, 32, lsb)
    ev(tick + 1, 1, mido.Message("program_change", channel=ch, program=program))
    cc(ch, tick + 2, 7, vol)
    cc(ch, tick + 2, 10, pan)
    cc(ch, tick + 2, 91, rev)
    cc(ch, tick + 2, 93, cho)
    cc(ch, tick + 2, 11, expr)


def bend_range(ch, tick, semis):
    for c, v in ((101, 0), (100, 0), (6, semis), (38, 0), (101, 127), (100, 127)):
        cc(ch, tick + 3, c, v)


# ---- sections (source bars) and their levels ---------------------------------------------------
SECTIONS = [  # (first source bar, name, guitar level, lead level)
    (0, "intro hook", 92, 104), (8, "riff intro", 104, 106), (16, "verse 1", 94, 100),
    (32, "verse 1 (lines 3-4)", 90, 100), (40, "pre-chorus", 100, 104), (48, "chorus", 108, 110),
    (64, "bridge", 98, 104), (67, "instrumental break", 108, 112), (77, "verse (drop-D)", 96, 102),
    (92, "verse (twin guitars)", 104, 106), (104, "verse (gothic)", 86, 98), (116, "virtuoso solo", 108, 114),
    (126, "verse", 100, 104), (143, "chorus", 110, 112), (159, "big finish", 114, 116),
    (168, "ritardando", 112, 118), (171, "outro", 106, 112), (182, "ending", 116, 118),
]


def level(src_bar, lead=False):
    cur = SECTIONS[0]
    for sct in SECTIONS:
        if src_bar >= sct[0]:
            cur = sct
    return cur[3] if lead else cur[2]


def accent(tick_in_bar):
    if tick_in_bar % BAR == 0:
        return 10
    if tick_in_bar % TPB == 0:
        return 4
    if tick_in_bar % (TPB // 2) == 0:
        return 0
    return -6


# ---- copy the parts through the timeline -------------------------------------------------------
def place(ch, notes, kind_ok=("copy",), shape=None, extra=()):
    """Copy a part's notes into every segment of `kind_ok`, clipped at the segment end."""
    for kind, a, b, o0, o1 in seg_out:
        if kind not in kind_ok and kind not in extra:
            continue
        for s, e, n, v, *tag in notes:
            if not (a * TPB <= s < b * TPB):
                continue
            t0 = o0 + s - a * TPB
            t1 = min(o0 + e - a * TPB, o1 - 10)
            vel = shape(s, n, v, tag[0] if tag else None) if shape else v
            note(ch, t0, n, t1 - t0, vel)


def rhy_shape(base_adj=0):
    def f(s, n, v, tag):
        return level(s // BAR) + base_adj + accent(s % BAR) + (v - 53) * 0.15 + rng.randint(-3, 3)
    return f


TWIN = (92, 104)                                   # source bars where ch8 plays the harmony


def in_bars(s, rng_bars):
    return rng_bars[0] * BAR <= s < rng_bars[1] * BAR


place(C3, RHY_L, shape=rhy_shape(), extra=("solo+", "final"))
place(C8, [x for x in RHY_R if not in_bars(x[0], TWIN)], shape=rhy_shape(-2), extra=("solo+", "final"))
place(C5, BASS, shape=rhy_shape(-2), extra=("solo+", "final"))


def drum_shape(s, n, v, tag):
    v = 38 + v * 0.85
    floor = {KICK: 78, SNARE: 88, CRASH: 98, CRASH2: 98}.get(n, 0)
    return max(v, floor) + (6 if level(s // BAR) >= 110 else 0)


place(DR, DRUMS, shape=drum_shape, extra=("solo+", "final"))


def lead_shape(s, n, v, tag):
    lv = level(s // BAR, lead=True)
    if (s, n) in SCREAM:
        return 122
    if tag == "lead":
        return lv + 2 + (4 if s % TPB == 0 else 0)
    return lv + (v - 60) * 0.2 + (3 if n >= 75 else 0)


place(C1, LEAD, shape=lead_shape)


def seg_end(src_tick):
    return next(o1 for kind, a, b, o0, o1 in seg_out if kind == "copy" and a * TPB <= src_tick < b * TPB)


# singing vibrato on the long notes of the lead guitar
for s, e, n, v, tag in LEAD:
    t0 = out_tick(s)
    if t0 is not None and e - s >= int(1.5 * TPB):
        t1 = min(t0 + (e - s) - 20, seg_end(s) - 30)
        vibrato(C1, t0 + int(0.4 * TPB), t1, depth=500 if tag == "voc" else 800)

# ---- the twin-guitar verse: ch8 a diatonic third under the melody ------------------------------
for s, e, n, v, tag in LEAD:
    if not in_bars(s, TWIN):
        continue
    pc = (n - D_SHARP) % 12
    if pc not in KEY_MIN:
        continue
    i = KEY_MIN.index(pc)
    octv = (n - D_SHARP - pc) // 12
    h = deg(octv * 7 + i - 2)
    if h >= 52:
        note(C8, out_tick(s), h, e - s - 10, lead_shape(s, n, v, tag) - 4, gen=True)

# ======================================================================================
# 3  chords per bar (from the rhythm parts) for the added layers
# ======================================================================================
TRIAD = {3: [3, 6, 10], 11: [11, 3, 6], 1: [1, 5, 8], 6: [6, 10, 1], 10: [10, 1, 5], 8: [8, 11, 3],
         4: [4, 8, 11]}                         # D#m, B, C#, F#, A#m, G#m, (outro) E


def root_pc(t0, t1):
    """The chord root under [t0, t1) (source ticks), from the bass and the low guitar notes;
    only roots with a chord in the key count (E only in the outro), else D#."""
    ok = set(TRIAD) - ({4} if t0 < 171 * BAR else set())
    w = Counter()
    for s, e, n, v in BASS + RHY_R + RHY_L:
        if s < t1 and e > t0 and n < 56 and n % 12 in ok:
            w[n % 12] += min(e, t1) - max(s, t0)
    return w.most_common(1)[0][0] if w else 3


def chord_notes(pc, lo, hi):
    pcs = TRIAD.get(pc, [pc, (pc + 7) % 12])
    return [n for n in range(lo, hi + 1) if n % 12 in pcs]


def timp(pc):
    n = 40 + (pc - 4) % 12
    return n if n <= 51 else n - 12


# ---- organ: the synth riff under chorus 1, held chords under chorus 2 and the big finish ---------
ORG_START = out_bar(48)
place(C4, [x for x in ORGAN_RIFF if 48 * BAR <= x[0] < 60 * BAR],
      shape=lambda s, n, v, t: 84 + accent(s % BAR) // 2)
for b in range(48, 64):
    for h in range(2):
        pc = root_pc(b * BAR + h * 2 * TPB, b * BAR + (h + 1) * 2 * TPB)
        for n in chord_notes(pc, 63, 74):
            note(C4, out_bar(b, 2 * h), n, 2 * TPB - 20, 70, gen=True)
for b in range(143, 168):
    pc = root_pc(b * BAR, (b + 1) * BAR)
    for n in chord_notes(pc, 55, 74):
        note(C4, out_bar(b), n, BAR - 20, 82 if b < 159 else 92, gen=True)
ramp(C4, 11, out_bar(47), out_bar(48), 60, 112)
cc(C4, out_bar(64), 11, 100)
ramp(C4, 11, out_bar(141), out_bar(143), 50, 115)
ramp(C4, 11, out_bar(159), out_bar(160), 115, 127)

# ---- choir: intro hook, gothic verse, chorus 2, big finish ----------------------------------------
for bars, vel in (((3, 9), 76), ((104, 116), 70), ((143, 159), 84), ((159, 168), 96)):
    for b in range(*bars):
        pc = root_pc(b * BAR, (b + 1) * BAR)
        for n in chord_notes(pc, 58, 75):
            note(C11, out_bar(b), n, BAR - 30, vel, gen=True)
place(C11, BACKING, shape=lambda s, n, v, t: 70 + v * 0.4)
ramp(C11, 11, out_bar(104), out_bar(106), 60, 110)
cc(C11, out_bar(116), 11, 100)

# ---- timpani + crash on the section changes, rolls into the big moments ---------------------------
CHANGES = [8, 16, 48, 67, 77, 92, 104, 116, 126, 143, 159, 171]
for b in CHANGES:
    t0 = out_bar(b)
    pc = root_pc(b * BAR, b * BAR + 2 * TPB)
    note(C15, t0, timp(pc), 2 * TPB, 112, gen=True)
    if not any(n in (CRASH, CRASH2) and abs(out_tick(s) - t0) < 60 for s, e, n, v in DRUMS
               if out_tick(s) is not None and abs(s - b * BAR) < 240):
        note(DR, t0, CRASH, 120, 110)
for b in (47, 142, 158, 167):
    t0 = out_bar(b, 2)
    for i in range(16):
        note(C15, t0 + i * TPB // 8, timp(3), TPB // 8, 60 + i * 4, gen=True)

# ======================================================================================
# 4  the added passages
# ======================================================================================
# 4a the virtuoso solo goes on: long notes, bends and a scream over its own riff (8 bars)
SOLO_X1 = [
    [(0, 11, .5), (.5, 12, .5), (1, 14, 3)],
    [(0, 14, .5), (.5, 13, .5), (1, 11, 1), (2, 9, .5), (2.5, 10, .5), (3, 11, 1)],
    [(0, 9, 2), (2.5, 7, .5), (3, 6, 1)],
    [(0, 7, .5), (.5, 9, .5), (1, 10, .5), (1.5, 11, .5), (2, 13, 2)],
    [(0, 14, 1 / 3), (1 / 3, 13, 1 / 3), (2 / 3, 11, 1 / 3), (1, 13, 1 / 3), (4 / 3, 11, 1 / 3), (5 / 3, 10, 1 / 3), (2, 9, 2)],
    [(0, 11, 1.5), (1.5, 10, .5), (2, 9, 1), (3, 7, 1)],
    [(0, 12, .25), (.25, 13, .25), (.5, 14, .25), (.75, 16, .25), (1, 16, 3)],
    [(0, 15, 1), (1, 14, .5), (1.5, 13, .5), (2, 12, .5), (2.5, 11, .5), (3, 10, 1)],
]
BENDS_X1 = {0: (2.0, 2.5, 2), 3: (2.6, 3.0, 2), 6: (1.6, 2.0, 2)}    # bar: (beat0, beat1, semitones)
_, _, _, x1, _ = seg("solo+")
for k, bar in enumerate(SOLO_X1):
    for b, d, ln in bar:
        note(C1, x1 + k * BAR + int(b * TPB), deg(d), int(ln * TPB) - 20, 112 + (6 if b == 0 else 0), gen=True)
    if k in BENDS_X1:
        b0, b1, semis = BENDS_X1[k]
        for j in range(9):
            bend(C1, x1 + k * BAR + int((b0 + (b1 - b0) * j / 8) * TPB), SEMI * semis * j / 8)
        vibrato(C1, x1 + k * BAR + int(b1 * TPB), x1 + k * BAR + int(3.9 * TPB), SEMI * semis, 900)
        bend(C1, x1 + k * BAR + int(3.97 * TPB), 0)
    elif bar[-1][2] >= 2:
        vibrato(C1, x1 + k * BAR + int((bar[-1][0] + 0.4) * TPB), x1 + k * BAR + int(3.9 * TPB), 0, 800)
        bend(C1, x1 + k * BAR + int(3.97 * TPB), 0)
gen_keys = [(x1, x1 + 32 * TPB, KEY_MIN)]

# 4b drum solo refrain (4 bars, 121 BPM): toms, double kick, snare rolls; the band stabs bar 1 and 3
_, _, _, x2, _ = seg("drums")
for k in range(4):
    b = x2 + k * BAR
    if k == 0:
        for i in range(16):
            note(DR, b + i * TPB // 4, TOMS[min(5, i * 6 // 16)], 60, 96 + i)
            note(DR, b + i * TPB // 4, KICK, 60, 100)
    elif k == 1:
        for i in range(12):
            note(DR, b + i * TPB // 3, SNARE if i % 3 == 0 else (KICK if i % 3 == 1 else MTOM), 60, 104)
    elif k == 2:
        for i in range(16):
            note(DR, b + i * TPB // 4, KICK, 60, 98 + (8 if i % 4 == 0 else 0))
        for bt in (1, 3):
            note(DR, b + bt * TPB, SNARE, 60, 112)
        for bt in (0, 2):
            note(DR, b + bt * TPB, CRASH, 120, 112)
    else:
        for i in range(8):
            note(DR, b + i * TPB // 4, SNARE, 60, 90 + i * 4)
        for i in range(8):
            note(DR, b + 2 * TPB + i * TPB // 4, TOMS[i % 6], 60, 104 + i * 2)
    if k in (0, 2):                                                     # the band hits with it
        for ch, ns in ((C3, [39, 46, 51]), (C8, [39, 46, 51]), (C5, [27])):
            for n in ns:
                note(ch, b, n, int(1.5 * TPB), 118)
        note(C15, b, timp(3), 2 * TPB, 118, gen=True)
note(DR, x2 + 16 * TPB, CRASH, 120, 120)

# 4c the final solo: the "Feel the power" hook an octave up, then higher, over D# / E (phrygian)
SOLO_X3 = [
    [(0, 10, 1), (1, 10, .5), (1.5, 12, 2.5)],
    [(0, 12, .5), (.5, 12, .5), (1, 9, 1), (2, 12, 2)],
    [(0, 12, 1), (1, 12, .5), (1.5, 12, .5), (2, 13, 1), (3, 12, 1)],
    [(0, 13, 2), (2, 15, 2)],
    [(i * 0.25, 14 - i, 0.25) for i in range(8)] + [(2, 10, 2)],
    [(0, 7, .5), (.5, 8, .5), (1, 10, 1), (2, 12, 1), (3, 13, 1)],
    [(0, 14, 3), (3, 12, 1)],
    [(0, 14, .5), (.5, 15, .5), (1, 17, 3)],
]
_, _, _, x3, _ = seg("final")
for k, bar in enumerate(SOLO_X3):
    for b, d, ln in bar:
        note(C1, x3 + k * BAR + int(b * TPB), deg(d, KEY_PHR), int(ln * TPB) - 20, 114 + (6 if b == 0 else 0), gen=True)
    if k == 3:                                    # C#6 bent up a tone, sung
        for j in range(9):
            bend(C1, x3 + k * BAR + int((0.4 + 0.4 * j / 8) * TPB), SEMI * 2 * j / 8)
        vibrato(C1, x3 + k * BAR + int(0.8 * TPB), x3 + k * BAR + int(1.95 * TPB), SEMI * 2, 900)
        bend(C1, x3 + k * BAR + int(1.98 * TPB), 0)
    elif k == 6:                                  # D#6 rises a semitone into the E half
        vibrato(C1, x3 + k * BAR + int(0.4 * TPB), x3 + k * BAR + int(1.9 * TPB), 0, 800)
        for j in range(9):
            bend(C1, x3 + k * BAR + int((2.0 + 0.3 * j / 8) * TPB), SEMI * j / 8)
        vibrato(C1, x3 + k * BAR + int(2.3 * TPB), x3 + k * BAR + int(2.95 * TPB), SEMI, 900)
        bend(C1, x3 + k * BAR + int(2.98 * TPB), 0)
    elif bar[-1][2] >= 2:
        vibrato(C1, x3 + k * BAR + int((bar[-1][0] + 0.4) * TPB), x3 + k * BAR + int(3.9 * TPB), 0, 900)
        bend(C1, x3 + k * BAR + int(3.97 * TPB), 0)
gen_keys.append((x3, x3 + 32 * TPB, KEY_PHR))

# 4d the last chord: organ, choir and timpani join the guitars' D#
t_end = out_tick(737 * TPB + 240)
for n in (51, 58, 63, 66, 70):
    note(C4, t_end, n, 11 * TPB, 100, gen=True)
for n in (63, 66, 70, 75):
    note(C11, t_end, n, 11 * TPB, 100, gen=True)
for i in range(48):
    note(C15, t_end + i * TPB // 6, timp(3), TPB // 6, max(40, 110 - i), gen=True)

# ======================================================================================
# 5  setup, tempo, checks, write
# ======================================================================================
prog(C1, 0, 30, vol=110, pan=64, rev=50)                    # Lead guitar (Distortion)
bend_range(C1, 0, 2)
prog(C3, 0, 30, vol=100, pan=0, rev=30)                     # Rhythm guitar L
prog(C8, 0, 30, vol=100, pan=127, rev=30)                   # Rhythm guitar R
prog(C5, 0, 34, vol=110, pan=64, rev=10)                    # Picked bass
prog(C4, 0, 18, vol=96, pan=40, rev=60, expr=60)            # Rock organ
prog(C11, 0, 52, vol=94, pan=88, rev=90, expr=100)          # Choir Aahs
prog(C15, 0, 47, vol=104, pan=64, rev=60)                   # Timpani
prog(DR, 0, 0, vol=110, rev=35, lsb=3)                      # Standard 1, SC-88Pro map

tempos = [(0, 158.5)]
_, _, _, b0, _ = seg("drums")
for src_beat, bpm in ((669, 150.0), (671, 148.0), (672, 140.0), (673, 130.0), (674, 115.0)):
    tempos.append((out_tick(src_beat * TPB), bpm))
tempos.append((b0, 121.0))

# one note at a time per pitch: a re-strike ends the ringing one first
by_key = defaultdict(list)
for x in notes_out:
    by_key[(x[0], x[3])].append(x)
for xs in by_key.values():
    xs.sort(key=lambda x: x[1])
    for a, b in zip(xs, xs[1:]):
        if b[1] < a[2]:
            a[2] = max(a[1] + 15, b[1] - 5)
for ch, t0, t1, n, v in notes_out:
    if t1 > t0:
        ev(t0, 2, mido.Message("note_on", channel=ch, note=n, velocity=v))
        ev(t1, 0, mido.Message("note_off", channel=ch, note=n, velocity=0))

# checks: added parts in key, no program change under a held note, no long silence
bad = []
for tk, n, ch in gen_spans:
    mode = KEY_MIN
    for a, b, m in gen_keys:
        if a <= tk < b:
            mode = m
    if tk >= out_bar(171):
        mode = KEY_PHR
    if (n - D_SHARP) % 12 not in mode:
        bad.append((ch + 1, n, tk))
if bad:
    print(f"{len(bad)} added notes out of key: {bad[:12]}")
    sys.exit(1)
spans_by = defaultdict(list)
for tk, o, m in sorted(events, key=lambda e: (e[0], e[1])):
    if m.type == "note_on" and m.velocity:
        spans_by[m.channel].append([tk, None, m.note])
    elif m.type in ("note_on", "note_off"):
        for sp in spans_by.get(m.channel, []):
            if sp[1] is None and sp[2] == m.note:
                sp[1] = tk
                break
pc_bad = [(m.channel + 1, tk) for tk, o, m in events if m.type == "program_change" and m.channel != DR
          and any(a < tk < (b or 1 << 30) for a, b, _ in spans_by[m.channel])]
if pc_bad:
    print("program change under a held note:", pc_bad[:10])
    sys.exit(1)

meta = [(tk, 0, mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm))) for tk, bpm in tempos]
meta.append((0, 0, mido.MetaMessage("time_signature", numerator=4, denominator=4)))
meta.append((0, 0, mido.MetaMessage("key_signature", key="D#m")))
allev = sorted(meta + events, key=lambda e: (e[0], e[1]))
mf = mido.MidiFile(ticks_per_beat=TPB)
tr = mido.MidiTrack()
mf.tracks.append(tr)
tr.append(mido.MetaMessage("track_name", name="A Tribute to the Metal Gods", time=0))
tr.append(mido.Message("sysex", data=[0x41, 0x10, 0x42, 0x12, 0x40, 0x00, 0x7F, 0x00, 0x41], time=0))
last = 0
for tk, _o, m in allev:
    tk += TPB                                     # one beat after the GS reset
    tr.append(m.copy(time=max(0, tk - last)))
    last = max(last, tk)
tr.append(mido.MetaMessage("end_of_track", time=max(0, END + 12 * TPB - last)))

secs, cur, quiet, held, gaps = 0.0, 500000, 0.0, set(), []
for m in tr:
    secs += mido.tick2second(m.time, TPB, cur)
    if m.type == "set_tempo":
        cur = m.tempo
    if m.type == "note_on" and m.velocity:
        if not held and secs - quiet > 1.5 and secs > 3:
            gaps.append((round(quiet, 1), round(secs - quiet, 1)))
        held.add((m.channel, m.note))
    elif m.type in ("note_off", "note_on"):
        held.discard((m.channel, m.note))
        if not held:
            quiet = secs
if gaps:
    print("silences longer than 1.5 s at", gaps)
    sys.exit(1)

mf = common.format1(mf)
out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "midi", "metal_gods.mid")
os.makedirs(os.path.dirname(out), exist_ok=True)
mf.save(out)
n_on = sum(1 for m in tr if m.type == "note_on" and m.velocity)
print(f"{out}: Format 1, {len(mf.tracks)} tracks (ties kept in order, <= {mf.max_shift} ticks late), "
      f"{mf.length:.1f} s ({int(mf.length // 60)}:{int(mf.length % 60):02d}), {n_on} notes, added parts in key")
