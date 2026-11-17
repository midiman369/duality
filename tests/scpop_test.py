"""SCPOP broadcast: every note-off reaches every unit its note-on went to (1.0.011).

A file with the SCPOP banner in its SysEx (41 10 45 12 10 00 00 "SCPOP ...") arms SCPOP mode, which sends
each note-on to every format-matched unit. The note-off used to pop one unit from the key's stack (built for a
re-struck held key on one unit), so the other units kept the note: R. Diodati's SCPOP2000 organ BWV 565 left
hundreds of notes hanging on units 2-6.

  SONG unset : self-contained, a short song written here (banner, held-key re-strike, chord), played on three
               units with Anima; also the same song without the banner (one unit per note, the re-strike's two
               offs on that unit).
  SONG=bach  : the real file, "Bach - Toccata e Fuga in Re min BWV565 2K.mid" (tests/README.md; SKIP when
               absent), whole song on six units, Anima seed 5150.
"""
import collections
import os
import random
import sys
import tempfile
import time as _time

import common
import mido

CLOCK = [1000.0]
_time.monotonic = lambda: CLOCK[0]
_time.time = lambda: CLOCK[0]
import duality as D
from rich.console import Console
D.console = Console(file=open(os.devnull, "w"))

random.seed(0x5150)
fails = []


def check(ok, what):
    if not ok:
        fails.append(what)


REC = []


class FakeOut:
    def __init__(s, n, i): s.name = n; s.i = i; s.closed = False
    def send(s, m): REC.append((round(CLOCK[0] - 1000.0, 3), s.i, m))
    def close(s): pass
    def reset(s): pass
    def panic(s): pass


def play(path, units, until):
    """Play one song with the file player on `units` fake GS units (Anima on); returns the router."""
    REC.clear()
    names = [f"SC{i + 1}" for i in range(units)]
    D.mido.open_output = lambda n, *a, **k: FakeOut(n, names.index(n))
    d = D.Duality(None, names, show_status=False, out_formats=[frozenset({"gm2", "gs8850"})] * units,
                  poly_limits=[64] * units, anima=True, anima_seed=0x5150, play=[path], play_loop=False)
    d.player.threaded = False
    CLOCK[0] = 1000.0
    while CLOCK[0] < 1000.0 + until:
        d._service()
        CLOCK[0] = round(CLOCK[0] + 0.005, 3)
    return d


def tally(units, keep=None):
    """Per unit and channel: note-ons, note-offs (incl. velocity-0 note-ons) of the notes `keep` (channel, note)
    allows (all by default); every key still sounding, whatever `keep` says."""
    ons, offs, held = collections.Counter(), collections.Counter(), collections.Counter()
    first_open = {}
    for t, i, m in REC:
        if m.type in ("note_on", "note_off") and keep and not keep(m.channel, m.note):
            if m.type == "note_on" and m.velocity:
                held[(i, m.channel, m.note)] += 1
                first_open.setdefault((i, m.channel, m.note), t)
            elif held[(i, m.channel, m.note)] > 0:
                held[(i, m.channel, m.note)] -= 1
                if not held[(i, m.channel, m.note)]:
                    first_open.pop((i, m.channel, m.note), None)
            continue
        if m.type == "note_on" and m.velocity:
            ons[(i, m.channel)] += 1
            held[(i, m.channel, m.note)] += 1
            first_open.setdefault((i, m.channel, m.note), t)
        elif m.type in ("note_on", "note_off"):
            offs[(i, m.channel)] += 1
            k = (i, m.channel, m.note)
            if held[k] > 0:
                held[k] -= 1
            if held[k] == 0:
                first_open.pop(k, None)
    hang = sorted((first_open.get(k, 0.0), k[0] + 1, k[1] + 1, k[2]) for k, v in held.items() if v > 0)
    return ons, offs, hang


def banner():
    """41 10 45 12 10 00 00 "SCPOP 2000!" checksum (the SCPOP2000 files' LCD banner)."""
    body = [0x10, 0x00, 0x00] + list(b"SCPOP 2000!")
    return [0x41, 0x10, 0x45, 0x12] + body + [(128 - sum(body) % 128) % 128]


if os.environ.get("SONG", "").lower() == "bach":
    path = common.midi("Bach - Toccata e Fuga in Re min BWV565 2K.mid")
    units = 6
    d = play(path, units, D.PlayerSong(path).length + 3.0)
    check(d.scpop_mode, "the file's SCPOP banner did not arm SCPOP mode (the test no longer covers broadcast)")
    ons, offs, hang = tally(units)
    file_ons = collections.Counter()
    for m in mido.MidiFile(path):
        if m.type == "note_on" and m.velocity:
            file_ons[m.channel] += 1
    for i in range(units):
        line = " ".join(f"ch{c + 1} {ons[(i, c)]}/{offs[(i, c)]}" for c in range(16) if ons[(i, c)] or offs[(i, c)])
        print(f"unit {i + 1}: {line}")
        for c in range(16):
            if ons[(i, c)] != offs[(i, c)]:
                fails.append(f"unit {i + 1} ch{c + 1}: {ons[(i, c)]} note-ons, {offs[(i, c)]} note-offs")
    reached = sum(1 for i in range(units) if ons[(i, 0)])
    check(reached >= 2, f"ch1 notes reached {reached} unit(s): the broadcast path is not exercised")
    check(max(ons[(i, 0)] for i in range(units)) == file_ons[0],
          f"a unit got ch1 {max(ons[(i, 0)] for i in range(units))} note-ons, the file has {file_ons[0]}")
    check(not hang, f"{len(hang)} notes left sounding, first (s, unit, ch, note): {hang[:6]}")
    print("FAILS:" if fails else "PASS")
    for f in fails:
        print("   ", f)
    sys.exit(1 if fails else 0)

# ---- self-contained: a short organ song with and without the banner


def organ_song(path, with_banner):
    mf = mido.MidiFile(type=1, ticks_per_beat=480)
    t0 = mido.MidiTrack()
    t0.append(mido.MetaMessage("set_tempo", tempo=500000, time=0))                     # 120 BPM: 480 ticks = 0.5 s
    t0.append(mido.Message("sysex", data=[0x41, 0x10, 0x42, 0x12, 0x40, 0x00, 0x7F, 0x00, 0x41], time=0))
    if with_banner:
        t0.append(mido.Message("sysex", data=banner(), time=10))
    t1 = mido.MidiTrack()
    t1.append(mido.Message("program_change", channel=0, program=19, time=0))            # Church Organ
    t1.append(mido.Message("program_change", channel=1, program=19, time=0))
    ev = [  # (tick, channel, note, velocity): offs written as velocity-0 note-ons, as SCPOP2000 does
        (480, 0, 62, 90),                      # D held ...
        (720, 0, 62, 80),                      # ... and struck again while held (a stacked on)
        (960, 0, 62, 0), (1200, 0, 62, 0),     # its two offs
        (1200, 0, 57, 90), (1200, 0, 61, 90), (1200, 0, 64, 90),        # a chord
        (1440, 1, 38, 100), (1920, 1, 38, 0),                           # another channel
        (1680, 0, 57, 0), (1680, 0, 61, 0), (1680, 0, 64, 0),
    ]
    last = 0
    for tk, ch, n, v in sorted(ev, key=lambda e: e[0]):
        t1.append(mido.Message("note_on", channel=ch, note=n, velocity=v, time=tk - last))
        last = tk
    t1.append(mido.MetaMessage("end_of_track", time=480))
    mf.tracks += [t0, t1]
    mf.save(path)
    return path


tmp = tempfile.mkdtemp(prefix="duality-scpop-")
units = 3
FILE_NOTES = {0: {57, 61, 62, 64}, 1: {38}}
file_note = lambda ch, n: n in FILE_NOTES.get(ch, ())        # not Anima's own ghosts  # noqa: E731

d = play(organ_song(os.path.join(tmp, "scpop_banner.mid"), True), units, 4.0)
check(d.scpop_mode, "the SCPOP banner did not arm SCPOP mode")
ons, offs, hang = tally(units, file_note)
for i in range(units):
    check(ons[(i, 0)] == 5 and offs[(i, 0)] == 5, f"SCPOP: unit {i + 1} ch1 {ons[(i, 0)]} ons / {offs[(i, 0)]} offs (want 5 / 5)")
    check(ons[(i, 1)] == 1 and offs[(i, 1)] == 1, f"SCPOP: unit {i + 1} ch2 {ons[(i, 1)]} ons / {offs[(i, 1)]} offs (want 1 / 1)")
check(not hang, f"SCPOP: notes left sounding (s, unit, ch, note): {hang}")
# the first off of the re-struck D releases one on everywhere, the second off the other
d_offs = [(t, i) for t, i, m in REC if m.type == "note_on" and m.note == 62 and m.channel == 0 and not m.velocity]
check(sorted(i for t, i in d_offs if abs(t - 1.5) < 0.05) == list(range(units))
      and sorted(i for t, i in d_offs if abs(t - 1.75) < 0.05) == list(range(units)),
      f"SCPOP: the re-struck D's two offs each go to every unit: {d_offs}")
check(not d.active, f"SCPOP: router still holds {sorted(d.active)}")

d = play(organ_song(os.path.join(tmp, "plain.mid"), False), units, 4.0)
check(not d.scpop_mode, "no banner, yet SCPOP mode is on")
ons, offs, hang = tally(units, file_note)
for c in (0, 1):
    check(sum(ons[(i, c)] for i in range(units)) == (5 if c == 0 else 1), f"plain: ch{c + 1} note-ons {dict(ons)}")
    for i in range(units):
        check(ons[(i, c)] == offs[(i, c)], f"plain: unit {i + 1} ch{c + 1} {ons[(i, c)]} ons / {offs[(i, c)]} offs")
d_on = [i for t, i, m in REC if m.type == "note_on" and m.note == 62 and m.channel == 0 and m.velocity]
d_off = [i for t, i, m in REC if m.type == "note_on" and m.note == 62 and m.channel == 0 and not m.velocity]
check(len(d_on) == 2 and len(set(d_on)) == 1 and d_off == d_on,
      f"plain: the re-struck D stays on one unit, both offs there: ons {d_on}, offs {d_off}")
check(not hang, f"plain: notes left sounding (s, unit, ch, note): {hang}")
check(not d.active, f"plain: router still holds {sorted(d.active)}")

print("FAILS:" if fails else "PASS")
for f in fails:
    print("   ", f)
sys.exit(1 if fails else 0)
