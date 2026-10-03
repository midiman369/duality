"""Write an air-raid siren listening test for the medley's War Pigs bridge.

    python tests/make_siren_test.py [out.mid]      (default tests/midi/siren_test2.mid)
    ROUND=1 python tests/make_siren_test.py         (the first round, tests/midi/siren_test.mid)

A real air-raid siren is a motor: it spins up fast and slows near the top, holds with a little
wobble, then winds down slowly, sinking below where it started; the next spin-up starts before it
has fully stopped. Each candidate below plays that gesture twice on held notes with a 24-semitone
pitch-bend range (a GS RPN), louder as it climbs. Markers name each one (Format 1, GS reset,
88Pro map Standard 1 kit, mostly GM tones; Anima may swap tone variations unless the tone is locked).

  A  Saw Wave + Whistle          a bright motor whine with a pure top
  B  Square Wave                  hollow, older-sounding
  C  Two saws a minor third apart the two-tone siren
  D  Whistle + Wind (SC SFX)      a pure tone over a howl of air (GM: Seashore)
  E  Ocarina + Calliope           soft and eerie
  F  SC "Siren" (Helicopter var.) what the medley uses now, for comparison
  Round 2 (the default; A and C were the picks): C louder, then stacked with A's whistle and
  octaves / a fifth (G, H, I, J), and G and I over the riff.
  Round 1: A and C over an Iommi-style intro in E at 86 BPM: a big ringing power chord with a wide,
  slow vibrato, the hi-hat ticking in the gap, a two-chord pickup into the next hit.
"""
import math
import os
import sys

import mido

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common  # noqa: E402

TPB = 480
events = []          # (tick, order, message)
tempos, marks = [], []


def ev(tick, msg, order=1):
    events.append((int(tick), order, msg))


def cc(ch, tick, c, v):
    ev(tick, mido.Message("control_change", channel=ch, control=c, value=max(0, min(127, int(v)))))


def bend(ch, tick, v):
    ev(tick, mido.Message("pitchwheel", channel=ch, pitch=max(-8192, min(8191, int(v)))))


def note(ch, tick, n, ticks, vel):
    ev(tick, mido.Message("note_on", channel=ch, note=n, velocity=vel), 2)
    ev(tick + ticks, mido.Message("note_off", channel=ch, note=n, velocity=0), 0)


def prog(ch, tick, pc, vol=100, pan=64, rev=60, cho=0, msb=0, lsb=0, expr=127):
    cc(ch, tick, 0, msb)
    cc(ch, tick, 32, lsb)
    ev(tick + 1, mido.Message("program_change", channel=ch, program=pc))
    for c, v in ((7, vol), (10, pan), (91, rev), (93, cho), (11, expr)):
        cc(ch, tick + 2, c, v)


def bend_range(ch, tick, semis):
    for c, v in ((101, 0), (100, 0), (6, semis), (38, 0), (101, 127), (100, 127)):
        cc(ch, tick, c, v)


# ---- time: siren-only parts at 60 BPM (a beat is a second), the riff demo at 86
def sec(s, bpm=60.0):
    return int(round(s * TPB * bpm / 60.0))


SEMI = 8192 / 24.0                       # bend steps per semitone at a 24-semitone range


def siren(chs, t0, note_n, cycles=((3.4, 1.6, 3.2, -18), (2.4, 1.0, 5.0, -10)), vel=110,
          start=-20, offsets=None, scale=1.0, base_expr=40):
    """The motor gesture on held notes. cycles: (rise s, hold s, fall s, spin-up starts at semis).
    t0 in ticks at the current tempo (sec() gives seconds at 60 BPM); returns the end tick."""
    offsets = offsets or [0] * len(chs)
    total = sum(r + h + f for r, h, f, _s in cycles)
    for ch, off in zip(chs, offsets):
        bend(ch, t0 - 10, start * SEMI)
        note(ch, t0, note_n + off, sec(total * scale) + 20, vel)
    t = t0
    for rise, hold, fall, frm in cycles:
        steps = max(8, int(rise / 0.03))
        for k in range(steps + 1):
            u = k / steps
            x = 1 - (1 - u) ** 2.4                       # fast spin-up, slowing near the top
            semis = frm + (0 - frm) * x
            tk = t + sec(rise * u * scale)
            for ch in chs:
                bend(ch, tk, semis * SEMI)
                cc(ch, tk, 11, base_expr + (124 - base_expr) * x)
        t += sec(rise * scale)
        steps = max(4, int(hold / 0.04))
        for k in range(steps + 1):
            tk = t + sec(hold * k / steps * scale)
            for ch in chs:
                bend(ch, tk, 18 * math.sin(k * 0.9) + 10 * math.sin(k * 2.3))   # a little wobble
        t += sec(hold * scale)
        steps = max(8, int(fall / 0.03))
        for k in range(steps + 1):
            u = k / steps
            x = u ** 1.7                                  # winds down slowly, then sinks
            semis = -22 * x
            tk = t + sec(fall * u * scale)
            for ch in chs:
                bend(ch, tk, semis * SEMI)
                cc(ch, tk, 11, 124 - (124 - 30) * x)
        t += sec(fall * scale)
    for ch in chs:
        bend(ch, t + 30, 0)
    return t


SIREN_A, SIREN_B = 13 - 1, 14 - 1        # ch13 / ch14 (ch16 stays free for Anima's foley)
GT_L, GT_R, BASS, DR = 2, 7, 4, 9

prog(SIREN_A, 0, 81, vol=104, pan=64, rev=80)
prog(SIREN_B, 0, 78, vol=96, pan=64, rev=80)
bend_range(SIREN_A, 4, 24)
bend_range(SIREN_B, 4, 24)
prog(GT_L, 0, 30, vol=100, pan=0, rev=40)
prog(GT_R, 0, 30, vol=100, pan=127, rev=40)
prog(BASS, 0, 34, vol=106, rev=10)
prog(DR, 0, 0, vol=110, rev=40, lsb=3)

pos = TPB          # 1 beat after the GS reset
tempos.append((0, 60.0))


def gap(s=2.0):
    global pos
    pos += sec(s)


def mark(name):
    marks.append((pos, name))


def swap(ch, pc, msb=0, vol=100):
    """Program change between candidates (the channel is silent here)."""
    prog(ch, pos - 40, pc, vol=vol, pan=64, rev=80, msb=msb)
    bend_range(ch, pos - 30, 24)


ROUND = int(os.environ.get("ROUND", "2"))
VOICE_CHS = [12, 13, 11, 5, 6]          # ch13, ch14, ch12, ch6, ch7 (all free at the medley's War Pigs)


def stack(label, voices, base=73, at=None, scale=1.0, cycles=None):
    """voices: (program, volume, semitone offset); one channel each, the same motor gesture."""
    global pos
    t0 = pos if at is None else at
    chs = VOICE_CHS[:len(voices)]
    for ch, (pc, vol, _off) in zip(chs, voices):
        prog(ch, t0 - 60, pc, vol=vol, pan=64, rev=90, cho=20)
        bend_range(ch, t0 - 50, 24)
    kw = {"cycles": cycles} if cycles else {}
    return siren(chs, t0, base, offsets=[v[2] for v in voices], scale=scale, **kw)


ROUND2 = [
    ("C+  two saws a minor third apart, louder", [(81, 120, 0), (81, 114, 3)]),
    ("G   C+ with a whistle an octave up", [(81, 120, 0), (81, 114, 3), (78, 100, 12)]),
    ("H   G with a saw an octave down", [(81, 120, 0), (81, 114, 3), (78, 100, 12), (81, 106, -12)]),
    ("I   H with a whistle on the fifth above", [(81, 120, 0), (81, 114, 3), (78, 100, 12), (81, 106, -12),
                                                (78, 88, 19)]),
    ("J   both saws doubled an octave down, whistle on top", [(81, 118, 0), (81, 112, 3), (81, 104, -12),
                                                           (81, 100, -9), (78, 100, 12)]),
]
if ROUND == 1:
    # A: Saw + Whistle
    mark("A  Saw Wave + Whistle")
    pos = siren([SIREN_A, SIREN_B], pos, 76) + 0
    gap()
    # B: Square
    mark("B  Square Wave")
    swap(SIREN_A, 80)
    pos = siren([SIREN_A], pos, 76)
    gap()
    # C: two saws a minor third apart
    mark("C  two saws, a minor third apart")
    swap(SIREN_A, 81)
    swap(SIREN_B, 81, vol=92)
    pos = siren([SIREN_A, SIREN_B], pos, 73, offsets=[0, 3])
    gap()
    # D: Whistle + Wind
    mark("D  Whistle + Wind (SC SFX)")
    swap(SIREN_A, 78)
    swap(SIREN_B, 122, msb=3, vol=110)
    pos = siren([SIREN_A, SIREN_B], pos, 76, offsets=[0, -16])
    gap()
    # E: Ocarina + Calliope
    mark("E  Ocarina + Calliope")
    swap(SIREN_A, 79)
    swap(SIREN_B, 82, vol=90)
    pos = siren([SIREN_A, SIREN_B], pos, 76)
    gap()
    # F: the SC Siren the medley uses now
    mark("F  SC Siren (now in the medley)")
    swap(SIREN_A, 125, msb=5, vol=100)
    bend_range(SIREN_A, pos - 20, 2)
    note(SIREN_A, pos, 60, sec(10), 104)
    cc(SIREN_A, pos, 11, 110)
    pos += sec(10)
    gap()

else:
    for label, voices in ROUND2:
        mark(label)
        pos = stack(label, voices)
        gap()

# ---- riff demos: an Iommi-style intro in E at 86 BPM under sirens A and C
BPM = 86.0
tempos.append((pos, BPM))
B = TPB * 4                                               # ticks per bar


def bt(bar, beat=0.0):
    return pos + int(round((bar * 4 + beat) * TPB))


def power(root, tick, beats, vel):
    for ch in (GT_L, GT_R):
        for i, n in enumerate((root, root + 7, root + 12)):
            note(ch, tick + i * 6, n, int(beats * TPB * 0.97), vel - i)
    note(BASS, tick, root - 12, int(beats * TPB * 0.95), vel)


def iommi_vibrato(t0, t1):
    """Wide, slow vibrato on the held chord (default 2-semitone range: +-0.35 semitone)."""
    k, tk = 0, t0
    while tk < t1:
        ease = min(1.0, (tk - t0) / (TPB * 1.0))
        v = 1430 * ease * math.sin(k * 2 * math.pi / 10)
        for ch in (GT_L, GT_R):
            bend(ch, tk, v)
        tk += 30
        k += 1
    for ch in (GT_L, GT_R):
        bend(ch, t1, 0)


def drum(tick, n, vel):
    note(DR, tick, n, 60, vel)


E2, G2, A2, C3, D3 = 40, 43, 45, 48, 50
PICKUPS = [(G2, A2), (C3, D3), (G2, A2), (D3, C3)]


def riff_bars(n_bars):
    for b in range(n_bars):
        power(E2, bt(b), 3.0, 116)                          # the big hit, left to ring
        drum(bt(b), 49, 118)                                # crash
        drum(bt(b), 36, 116)                                # kick
        iommi_vibrato(bt(b, 1.0), bt(b, 2.9))
        p1, p2 = PICKUPS[b % 4]
        power(p1, bt(b, 3.25), 0.25, 108)                   # the pickup into the next hit
        power(p2, bt(b, 3.5), 0.5, 112)
        drum(bt(b, 3.5), 38, 104)
        for i in range(8):                                  # the hi-hat ticks through the gap
            drum(bt(b, i * 0.5), 42, 60 if i % 2 else 74)


RIFFS = ([("riff + siren A (Saw + Whistle)", [(81, 104, 0), (78, 96, 0)], 76),
          ("riff + siren C (two saws)", [(81, 104, 0), (81, 92, 3)], 73)] if ROUND == 1 else
         [("riff + siren G (two saws + whistle)", ROUND2[1][1], 73),
          ("riff + siren I (full stack)", ROUND2[3][1], 73)])
for label, voices, base in RIFFS:
    marks.append((pos, label))
    stack(label, voices, base=base, at=pos, scale=BPM / 60.0,
          cycles=((3.4, 1.6, 3.2, -18), (2.4, 1.0, 6.0, -10)))
    riff_bars(8)
    power(E2, bt(8), 4.0, 120)
    drum(bt(8), 49, 122)
    pos = bt(9, 2)

end_tick = pos + TPB * 2

# ---- write: GS reset, tempos, markers, events; Format 1
meta = [(tk, 0, mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(b))) for tk, b in tempos]
meta += [(tk, 0, mido.MetaMessage("marker", text=n)) for tk, n in marks]
allev = sorted(meta + events, key=lambda e: (e[0], e[1]))
mf = mido.MidiFile(ticks_per_beat=TPB)
tr = mido.MidiTrack()
mf.tracks.append(tr)
tr.append(mido.MetaMessage("track_name", name="Air-raid siren test", time=0))
tr.append(mido.Message("sysex", data=[0x41, 0x10, 0x42, 0x12, 0x40, 0x00, 0x7F, 0x00, 0x41], time=0))
last = 0
for tk, _o, m in allev:
    tk = max(tk, 0) + TPB // 2
    tr.append(m.copy(time=max(0, tk - last)))
    last = max(last, tk)
tr.append(mido.MetaMessage("end_of_track", time=max(0, end_tick + TPB - last)))
mf = common.format1(mf)
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "midi", "siren_test.mid" if ROUND == 1 else f"siren_test{ROUND}.mid")
os.makedirs(os.path.dirname(out), exist_ok=True)
mf.save(out)
print(f"{out}: Format 1, {len(mf.tracks)} tracks, {mf.length:.1f} s")
