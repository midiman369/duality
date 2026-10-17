"""File player (--play): timing through the tempo map, ports, controls, and Duality routing the songs.

Self-contained: the songs are written here.
  - PlayerSong: events in seconds through tempo changes, each track's MIDI Port marker kept, SysEx kept,
    the length from end-of-track.
  - MidiPlayer: lead-in, events on time, pause / resume (note-offs for what sounds), next / back,
    the gap between songs, the end of the playlist, an unreadable file skipped.
  - Duality with fake ports and a fake clock: the songs reach the outs like live input, live input still
    flows while a song plays, port B is noted (not routed yet), and nothing hangs after stop.
"""
import os
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

fails = []


def check(ok, what):
    if not ok:
        fails.append(what)


tmp = tempfile.mkdtemp(prefix="duality-player-")


def song(path, tempo_change=True, port_b=True, tail=0):
    mf = mido.MidiFile(type=1, ticks_per_beat=480)
    t0 = mido.MidiTrack()
    t0.append(mido.MetaMessage("set_tempo", tempo=500000, time=0))                     # 120 BPM
    t0.append(mido.Message("sysex", data=[0x41, 0x10, 0x42, 0x12, 0x40, 0x00, 0x7F, 0x00, 0x41], time=0))
    if tempo_change:
        t0.append(mido.MetaMessage("set_tempo", tempo=1000000, time=960))              # 60 BPM from 1.0 s
    t1 = mido.MidiTrack()
    t1.append(mido.MetaMessage("midi_port", port=0, time=0))
    t1.append(mido.Message("program_change", channel=0, program=0, time=0))
    t1.append(mido.Message("note_on", channel=0, note=60, velocity=100, time=0))
    t1.append(mido.Message("note_off", channel=0, note=60, velocity=0, time=480))       # 0.5 s
    t1.append(mido.Message("note_on", channel=0, note=64, velocity=100, time=960))      # tick 1440 = 2.0 s
    t1.append(mido.Message("note_off", channel=0, note=64, velocity=0, time=480))       # tick 1920 = 3.0 s
    t1.append(mido.MetaMessage("end_of_track", time=tail))
    mf.tracks += [t0, t1]
    if port_b:
        t2 = mido.MidiTrack()
        t2.append(mido.MetaMessage("midi_port", port=1, time=0))
        t2.append(mido.Message("note_on", channel=0, note=72, velocity=90, time=480))   # 0.5 s, port B
        t2.append(mido.Message("note_off", channel=0, note=72, velocity=0, time=240))
        mf.tracks.append(t2)
    mf.save(path)
    return path


a = song(os.path.join(tmp, "a_first.mid"), tail=480)        # end-of-track one beat (1 s at 60 BPM) after the last note
b = song(os.path.join(tmp, "b_second.mid"), tempo_change=False, port_b=False)
with open(os.path.join(tmp, "c_broken.mid"), "wb") as f:
    f.write(b"not a midi file")

# ---- PlayerSong
s = D.PlayerSong(a)
times = [(round(t, 3), p, m.type) for t, p, m in s.events]
check(times[0] == (0.0, 0, "sysex"), f"first event {times[0]}")
on = [(round(t, 3), p, m.note) for t, p, m in s.events if m.type == "note_on"]
check(on == [(0.0, 0, 60), (0.5, 1, 72), (2.0, 0, 64)], f"note-ons {on}")
check(abs(s.length - 4.0) < 1e-6, f"length {s.length} (want 4.0: last note-off 3.0 s, end-of-track 1 s later)")
check(s.ports == [0, 1], f"ports {s.ports}")

# ---- the playlist: a folder plays its MIDI files by name
pl = D.player_playlist([tmp])
check([os.path.basename(x) for x in pl] == ["a_first.mid", "b_second.mid", "c_broken.mid"], f"playlist {pl}")
try:
    D.player_playlist([os.path.join(tmp, "missing.mid")])
    fails.append("a missing file did not raise")
except ValueError:
    pass

# ---- MidiPlayer on a fake clock
p = D.MidiPlayer([a, b, os.path.join(tmp, "c_broken.mid")], threaded=False)
got = []


def run(t0, t1, step=0.01):
    t = t0
    while t <= t1 + 1e-9:
        for port, m in p.tick(round(t, 4)):
            got.append((round(t, 2), port, m.type, getattr(m, "note", None)))
        t += step


run(100.0, 100.4)
check(got == [], f"lead-in: events before 0.5 s: {got}")
run(100.41, 101.1)
check(("sysex" in [g[2] for g in got]) and (100.5, 0, "note_on", 60) in got, f"song start {got[:4]}")
check((101.0, 1, "note_on", 72) in got, f"port B note at song 0.5 s: {got}")
got.clear()
# pause at 102.0 (song 1.5 s: nothing sounds) then resume 10 s later
ev = p.toggle(102.0)
check(p.state == "paused" and abs(p.held - 1.5) < 1e-6, f"pause state {p.state} {p.held}")
run(102.01, 112.0)
check(got == [], f"events while paused {got}")
p.toggle(112.0)
run(112.01, 112.6)
check((112.5, 0, "note_on", 64) in got, f"resume: note 64 at song 2.0 s = 112.5: {got}")
# pause while 64 sounds: its note-off comes with the pause
ev = p.toggle(112.7)
offs = [(port, m.type, getattr(m, "note", None)) for port, m in ev]
check((0, "note_off", 64) in offs, f"pause flush {offs}")
check(any(m.type == "control_change" and m.control == 64 for _p, m in ev), "pause sends sustain off")
p.toggle(113.0)
got.clear()
# song 1 ends at song 4.0 s = 114.8, a 2 s gap, then song 2 after its 0.5 s lead-in: 117.3
run(113.01, 117.5)
check(p.index == 1 and p.state == "playing", f"after the gap: index {p.index} state {p.state}")
starts = [g for g in got if g[2] == "note_on" and g[3] == 60]
check(starts and abs(starts[0][0] - 117.3) < 0.02, f"song 2 start {starts}")
# N on song 2: the broken file is skipped and N wraps to song 1
p.next(118.0)
check(p.index == 0 and any("skipped c_broken.mid" in x for x in p.messages), f"skip broken: {p.index} {p.messages}")
# Z near the start of song 1: the song before it, skipping the broken file backwards → song 2
p.prev(118.2)
check(p.index == 1, f"back from song 1's start → {p.index} (want 1)")
p.next(119.0)
idx = p.index
run(119.0, 123.5)
p.prev(123.5)
check(p.index == idx and p.state == "playing", f"Z after 3 s restarts the song ({p.index} vs {idx})")
# stop: position 0; Space plays from the start
p.stop(121.0)
check(p.state == "stopped" and p.song_time(121.0) == 0.0, f"stop {p.state}")
# end of the playlist (no loop): done
q = D.MidiPlayer([b], threaded=False)
t = 200.0
while t < 210 and q.state != "done":
    q.tick(t)
    t += 0.05
check(q.state == "done", f"single-song playlist ends: {q.state}")

# ---- Duality plays the songs (fake ports, fake clock), live input still flows
REC = []


class FakeOut:
    def __init__(s, n, i): s.name = n; s.i = i; s.closed = False
    def send(s, m): REC.append((round(CLOCK[0] - 1000.0, 3), s.i, m))
    def close(s): pass
    def reset(s): pass
    def panic(s): pass


LIVE = []


class FakeIn:
    name = "live"; closed = False
    def poll(s): return None
    def iter_pending(s):
        out = [m for t, m in LIVE if t <= CLOCK[0] - 1000.0]
        LIVE[:] = [(t, m) for t, m in LIVE if t > CLOCK[0] - 1000.0]
        return iter(out)
    def close(s): pass


names = ["SC1", "SC2"]
D.mido.open_output = lambda n, *a, **k: FakeOut(n, names.index(n))
D.mido.open_input = lambda *a, **k: FakeIn()
d = D.Duality("live", names, show_status=False, out_formats=[frozenset({"gm2", "gs8850"})] * 2,
              poly_limits=[32, 32], play=[a], play_loop=False)
d.player.threaded = False
LIVE.append((1.25, mido.Message("note_on", channel=5, note=50, velocity=80)))
LIVE.append((1.75, mido.Message("note_off", channel=5, note=50, velocity=0)))
CLOCK[0] = 1000.0
while CLOCK[0] < 1009.0:
    d._service()
    CLOCK[0] = round(CLOCK[0] + 0.005, 3)
ons = [(t, i, m.channel, m.note) for t, i, m in REC if m.type == "note_on" and m.velocity]
check(any(c == 0 and n == 60 and abs(t - 0.5) < 0.02 for t, i, c, n in ons), f"song note 60 at 0.5 s: {ons}")
check(any(c == 0 and n == 64 and abs(t - 2.5) < 0.02 for t, i, c, n in ons), f"song note 64 at song 2.0 s = 2.5: {ons}")
check(any(c == 5 and n == 50 for t, i, c, n in ons), f"live input note while the song plays: {ons}")
check(not any(n == 72 for t, i, c, n in ons), "port B note was routed (it should wait for multi-port)")
check(1 in d._player_port_note, "port B noted")
sx = [m for t, i, m in REC if m.type == "sysex"]
check(len(sx) >= 1, "the song's SysEx reached the outs")
held = {}
for t, i, m in REC:
    if m.type == "note_on" and m.velocity:
        held[(i, m.channel, m.note)] = held.get((i, m.channel, m.note), 0) + 1
    elif m.type in ("note_on", "note_off"):
        k = (i, m.channel, m.note)
        if held.get(k):
            held[k] -= 1
hang = [k for k, v in held.items() if v > 0]
check(not hang, f"hanging notes {hang}")
check(d.player.state == "done", f"player state after the song: {d.player.state}")

# ---- --play with no live input: _NoInput, and a stop mid-note leaves nothing hanging
REC.clear()
d2 = D.Duality(None, names, show_status=False, out_formats=[frozenset({"gm2", "gs8850"})] * 2,
               poly_limits=[32, 32], play=[a])
d2.player.threaded = False
check(isinstance(d2.inport, D._NoInput), "no live input → _NoInput")
CLOCK[0] = 2000.0
while CLOCK[0] < 2002.6:          # into note 64 (song 2.0-2.5 s = 2002.5-2003.0)
    d2._service()
    CLOCK[0] = round(CLOCK[0] + 0.005, 3)
d2._handle_hotkey("t")
held = {}
for t, i, m in REC:
    if m.type == "note_on" and m.velocity:
        held[(i, m.channel, m.note)] = held.get((i, m.channel, m.note), 0) + 1
    elif m.type in ("note_on", "note_off"):
        k = (i, m.channel, m.note)
        if held.get(k):
            held[k] -= 1
hang = [k for k, v in held.items() if v > 0]
check(not hang and d2.player.state == "stopped", f"stop mid-note: hanging {hang}, state {d2.player.state}")

print("FAILS:" if fails else "PASS")
for f in fails:
    print("  ", f)
sys.exit(1 if fails else 0)
