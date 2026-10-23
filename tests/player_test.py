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
# the song has ports A and B: with two outs each port gets one (a lane each)
check({i for t, i, c, n in ons if n == 72} == {1} and {i for t, i, c, n in ons if n in (60, 64)} == {0},
      f"2-port song on 2 outs: A on out 1, B on out 2: {ons}")
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

# ---- multi-port songs: a lane per port on its own outs (0.19.066)


def multiport(path, ports, requests=()):
    """A song whose port p plays note 60 + p on ch1 from 0.0 to 1.0 s; port A sends a GS reset first.
    requests: (port, text) "duality: ..." text events on that port's track."""
    mf = mido.MidiFile(type=1, ticks_per_beat=480)
    t0 = mido.MidiTrack()
    t0.append(mido.MetaMessage("set_tempo", tempo=500000, time=0))
    mf.tracks.append(t0)
    for p_ in ports:
        tr = mido.MidiTrack()
        tr.append(mido.MetaMessage("midi_port", port=p_, time=0))
        for rp, text in requests:
            if rp == p_:
                tr.append(mido.MetaMessage("text", text=text, time=0))
        if p_ == 0:
            tr.append(mido.Message("sysex", data=[0x41, 0x10, 0x42, 0x12, 0x40, 0x00, 0x7F, 0x00, 0x41], time=0))
        tr.append(mido.Message("program_change", channel=0, program=p_, time=0))
        tr.append(mido.Message("note_on", channel=0, note=60 + p_, velocity=100, time=0))
        tr.append(mido.Message("note_off", channel=0, note=60 + p_, velocity=0, time=960))
        mf.tracks.append(tr)
    mf.save(path)
    return path


def play_through(names, fmts, songs, until):
    REC.clear()
    D.mido.open_output = lambda n, *a, **k: FakeOut(n, names.index(n))
    dd = D.Duality(None, names, show_status=False, out_formats=fmts, poly_limits=[32] * len(names), play=songs)
    dd.player.threaded = False
    seen_lanes = []
    CLOCK[0] = 3000.0
    while CLOCK[0] < 3000.0 + until:
        dd._service()
        if dd._lanes and not seen_lanes:
            seen_lanes.append({p_: list(o) for p_, o in dd._lane_outs.items()})
        CLOCK[0] = round(CLOCK[0] + 0.005, 3)
    REC[:] = [(round(t - 2000.0, 3), i, m) for t, i, m in REC]      # song time from 0
    return dd, seen_lanes


gs = frozenset({"gm2", "gs8850"})
xg = frozenset({"xg"})
two = multiport(os.path.join(tmp, "m_two.mid"), [0, 1])
one = song(os.path.join(tmp, "m_after.mid"), tempo_change=False, port_b=False)
names4 = ["U1", "U2", "U3", "U4"]
dd, lanes_seen = play_through(names4, [gs] * 4, [two, one], 8.0)
check(lanes_seen and lanes_seen[0] == {0: [0, 1], 1: [2, 3]}, f"2 ports on 4 outs: {lanes_seen}")
ons = [(t, i, m.note) for t, i, m in REC if m.type == "note_on" and m.velocity]
a_outs = {i for t, i, n in ons if n == 60 and t < 2.0}
b_outs = {i for t, i, n in ons if n == 61}
check(a_outs and a_outs <= {0, 1}, f"port A notes on A's outs only: {a_outs}")
check(b_outs and b_outs <= {2, 3}, f"port B notes on B's outs only: {b_outs}")
pcs = {(i, m.program) for t, i, m in REC if m.type == "program_change" and t < 2.0}
check(not any(prog == 1 and i in (0, 1) for i, prog in pcs) and not any(prog == 0 and i in (2, 3) for i, prog in pcs),
      f"each port's programs stay on its outs: {sorted(pcs)}")
resets = {i for t, i, m in REC if m.type == "sysex" and list(m.data[:7]) == [0x41, 0x10, 0x42, 0x12, 0x40, 0x00, 0x7F]}
check(resets >= {0, 1, 2, 3}, f"port A's GS reset reaches every lane's outs: {resets}")
later = {i for t, i, m in REC if m.type == "note_on" and m.velocity and t > 4.0}
check(not dd._lanes and later, f"after the song the router plays on its outs again: lanes {dd._lanes}, outs {later}")
check(dd.player.index == 1, f"second song reached: {dd.player.index}")

# a request picks the kind of unit
req = multiport(os.path.join(tmp, "m_req.mid"), [0, 1], requests=[(1, "duality: xg")])
dd, lanes_seen = play_through(names4, [gs, gs, gs, xg], [req], 3.0)
check(lanes_seen and lanes_seen[0] == {0: [0, 1, 2], 1: [3]}, f"port B asks for XG: {lanes_seen}")
# kinds in order of preference: B wants an XG unit, else an 8850; C an XG unit, else an 8850
pref = multiport(os.path.join(tmp, "m_pref.mid"), [0, 1, 2],
                 requests=[(1, "duality: xg, 8850"), (2, "duality: xg, 8850")])
dd, lanes_seen = play_through(names4, [gs, gs, gs, xg], [pref], 3.0)
check(lanes_seen and lanes_seen[0] == {0: [0, 1], 1: [3], 2: [2]}, f"preferences: B gets the XG, C falls back: {lanes_seen}")
# a request nothing can meet: that port is dropped, the song plays port A on every out
drop = multiport(os.path.join(tmp, "m_drop.mid"), [0, 1], requests=[(1, "duality: port B cm64")])
dd, lanes_seen = play_through(names4, [gs] * 4, [drop], 3.0)
ons = [(t, i, m.note) for t, i, m in REC if m.type == "note_on" and m.velocity]
check(not lanes_seen and not any(n == 61 for t, i, n in ons) and any(n == 60 for t, i, n in ons),
      f"unmet request: port B dropped, port A plays ({lanes_seen}, {sorted({n for t, i, n in ons})})")
# four ports on six outs: A and B get two units, C and D one
four = multiport(os.path.join(tmp, "m_four.mid"), [0, 1, 2, 3])
names6 = [f"U{k}" for k in range(1, 7)]
dd, lanes_seen = play_through(names6, [gs] * 6, [four], 3.0)
check(lanes_seen and lanes_seen[0] == {0: [0, 1], 1: [2, 3], 2: [4], 3: [5]}, f"4 ports on 6 outs: {lanes_seen}")
ons = [(t, i, m.note) for t, i, m in REC if m.type == "note_on" and m.velocity]
for p_, outs in {0: {0, 1}, 1: {2, 3}, 2: {4}, 3: {5}}.items():
    got_outs = {i for t, i, n in ons if n == 60 + p_}
    check(got_outs and got_outs <= outs, f"port {chr(65 + p_)} notes on {got_outs}, want ⊆ {outs}")
held = {}
for t, i, m in REC:
    if m.type == "note_on" and m.velocity:
        held[(i, m.channel, m.note)] = held.get((i, m.channel, m.note), 0) + 1
    elif m.type in ("note_on", "note_off"):
        k = (i, m.channel, m.note)
        if held.get(k):
            held[k] -= 1
check(not [k for k, v in held.items() if v > 0], "multi-port: nothing left hanging")
# the request parser
for text, want in (("duality: 8850", (5, ("gs8850",), None)), ("Duality: port B mt32 x2", (1, ("mt32",), 2)),
                   ("duality: C=xg", (2, ("xg",), None)), ("duality: port 4 cm64", (3, ("cm64",), None)),
                   ("duality: 8850, cm64", (5, ("gs8850", "cm64"), None)), ("hello", None)):
    got = D.parse_port_request(text, 5)
    check(got == want, f"parse_port_request({text!r}) = {got}, want {want}")
# song options (1.0.003): the foley level, not a port request
for text, want in (("duality: foley off", ("foley", 0.0)), ("Duality: no foley", ("foley", 0.0)),
                   ("duality: foley 25%", ("foley", 0.25)), ("duality: foley on", ("foley", 1.0)),
                   ("duality: 8850", None), ("duality: foley loud", None)):
    got = D.parse_song_option(text)
    check(got == want, f"parse_song_option({text!r}) = {got}, want {want}")
opt = multiport(os.path.join(tmp, "m_opt.mid"), [0, 1], requests=[(0, "duality: 8850"), (0, "duality: foley 25%")])
ps = D.PlayerSong(opt)
check(ps.options == {"foley": 0.25} and ps.requests.get(0) == (("gs8850",), None),
      f"a song's foley option and its port request both read: {ps.options} {ps.requests}")
names2 = ["U1", "U2"]
REC.clear()
D.mido.open_output = lambda n, *a, **k: FakeOut(n, names2.index(n))
dd = D.Duality(None, names2, show_status=False, out_formats=[gs, gs], poly_limits=[32, 32], play=[opt],
               anima=True, anima_foley=0.0)
dd.player.threaded = False
CLOCK[0] = 3000.0
levels = set()
while CLOCK[0] < 3002.0:
    dd._service()
    if dd._lanes:
        levels.add((dd.anima_foley, tuple(sorted(l.anima_foley for l in dd._lanes.values()))))
    CLOCK[0] = round(CLOCK[0] + 0.005, 3)
check(levels == {(0.25, (0.25, 0.25))}, f"the song's foley level on the router and its lanes: {levels}")
while CLOCK[0] < 3006.0:
    dd._service()
    CLOCK[0] = round(CLOCK[0] + 0.005, 3)
check(dd.anima_foley == 0.0 and dd._anima_foley_cc7() == 1, f"after the song --anima-foley is back: {dd.anima_foley}")

# lane seeds (1.0.005): each port plays the badge seed + 0101 per port, locked or not; S locks the badge seed only,
# X (unlocked) rerolls it and the lanes follow
long2 = os.path.join(tmp, "m_seed.mid")
mf = mido.MidiFile(type=1, ticks_per_beat=480)
mf.tracks.append(mido.MidiTrack([mido.MetaMessage("set_tempo", tempo=500000, time=0)]))
for p_ in (0, 1):
    tr = mido.MidiTrack([mido.MetaMessage("midi_port", port=p_, time=0),
                         mido.Message("program_change", channel=0, program=48, time=0)])
    for k in range(12):
        tr.append(mido.Message("note_on", channel=0, note=60 + p_, velocity=90, time=0 if k == 0 else 240))
        tr.append(mido.Message("note_off", channel=0, note=60 + p_, velocity=0, time=240))
    mf.tracks.append(tr)
mf.save(long2)
REC.clear()
D.mido.open_output = lambda n, *a, **k: FakeOut(n, names4.index(n))
dd = D.Duality(None, names4, show_status=False, out_formats=[gs] * 4, poly_limits=[32] * 4, play=[long2], anima=True)
dd.player.threaded = False
CLOCK[0] = 3000.0
while CLOCK[0] < 3002.0 and not dd._lanes:
    dd._service()
    CLOCK[0] = round(CLOCK[0] + 0.005, 3)


def lane_seeds():
    return {p_: lane._anima_efx_seed for p_, lane in dd._lanes.items()}


base = dd._anima_efx_seed
want = {p_: (base + 0x0101 * p_) & 0xFFFF for p_ in dd._lanes}
check(dd._lanes and lane_seeds() == want and not dd._anima_seed_locked,
      f"unlocked: the lanes play the badge seed + 0101 per port: badge {base}, lanes {lane_seeds()}")
dd._handle_hotkey("x")
nb = dd._anima_efx_seed
check(lane_seeds() == {p_: (nb + 0x0101 * p_) & 0xFFFF for p_ in dd._lanes},
      f"after X the lanes follow the badge seed {nb}: {lane_seeds()}")
before = lane_seeds()
dd._handle_hotkey("s")
check(dd._anima_seed_locked and lane_seeds() == before and all(l._anima_seed_locked for l in dd._lanes.values()),
      f"S locks the badge seed; the lanes keep theirs: {lane_seeds()} vs {before}")

# a sequencer's port markers (1.0.006): the tempo track (and its SysEx) on port A, every part on port F, as in a
# re-saved ONESTOP2: one 16-channel song, played on every out
seq = os.path.join(tmp, "m_seqports.mid")
mf = mido.MidiFile(type=1, ticks_per_beat=480)
mf.tracks.append(mido.MidiTrack([mido.MetaMessage("midi_port", port=0, time=0),
                                 mido.MetaMessage("set_tempo", tempo=500000, time=0),
                                 mido.Message("sysex", data=[0x41, 0x10, 0x42, 0x12, 0x40, 0x00, 0x7F, 0x00, 0x41],
                                              time=0)]))
for c in (0, 1):
    mf.tracks.append(mido.MidiTrack([mido.MetaMessage("midi_port", port=5, time=0),
                                     mido.Message("program_change", channel=c, program=c, time=0),
                                     mido.Message("note_on", channel=c, note=60 + c, velocity=90, time=10),
                                     mido.Message("note_off", channel=c, note=60 + c, velocity=0, time=960)]))
mf.save(seq)
ps = D.PlayerSong(seq)
check(ps.ports == [5] and ps.port_moves == {0: 5}, f"port markers: the song is port F alone ({ps.ports}, {ps.port_moves})")
dd, lanes_seen = play_through(names4, [gs] * 4, [seq], 3.0)
ons = {(i, m.note) for t, i, m in REC if m.type == "note_on" and m.velocity}
resets = {i for t, i, m in REC if m.type == "sysex" and list(m.data[:7]) == [0x41, 0x10, 0x42, 0x12, 0x40, 0x00, 0x7F]}
check(not lanes_seen and {n for _i, n in ons} == {60, 61} and resets >= {0, 1, 2, 3},
      f"played as one 16-channel song on every out: lanes {lanes_seen}, notes {sorted(ons)}, resets {sorted(resets)}")

# the panel's channel grid while lanes play (1.0.006): every port's channels count, the label names the ports
import io
from rich.console import Console as _Console
mp = multiport(os.path.join(tmp, "m_panel.mid"), [0, 1])
REC.clear()
D.mido.open_output = lambda n, *a, **k: FakeOut(n, names4.index(n))
dd = D.Duality(None, names4, show_status=False, out_formats=[gs] * 4, poly_limits=[32] * 4, play=[mp])
dd.player.threaded = False
CLOCK[0] = 3000.0
while CLOCK[0] < 3002.0 and not (dd._lanes and all(l.active for l in dd._lanes.values())):
    dd._service()
    CLOCK[0] = round(CLOCK[0] + 0.005, 3)
buf = io.StringIO()
_Console(file=buf, width=140, color_system=None).print(dd._make_status_panel())
text = buf.getvalue()
row = next((ln for ln in text.splitlines() if "Voice Count" in ln), "")
first = row.split("Voice Count", 1)[1].split()[:1] if row else []
check("MIDI Ch AB" in text and first == ["2"],
      f"the grid merges ports A and B (ch1 plays on both): label {'MIDI Ch AB' in text}, ch1 voices {first}")

# the beat for delay inserts (1.0.008): the song's tempo map while the player plays, not the onset estimate, which
# takes a 3-eighth arpeggio at 132 BPM for a 680 ms beat
arp = os.path.join(tmp, "m_arp.mid")
mf = mido.MidiFile(type=0, ticks_per_beat=480)
tr = mido.MidiTrack([mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(132), time=0),
                     mido.Message("program_change", channel=0, program=81, time=0)])
for k in range(96):                                  # a figure every three eighths
    tr.append(mido.Message("note_on", channel=0, note=60 + (k % 3) * 4, velocity=90, time=0 if k == 0 else 600))
    tr.append(mido.Message("note_off", channel=0, note=60 + (k % 3) * 4, velocity=0, time=120))
mf.tracks.append(tr)
mf.save(arp)
REC.clear()
D.mido.open_output = lambda n, *a, **k: FakeOut(n, names4.index(n))
dd = D.Duality(None, names4, show_status=False, out_formats=[gs] * 4, poly_limits=[32] * 4, play=[arp], anima=True)
dd.player.threaded = False
CLOCK[0] = 3000.0
while CLOCK[0] < 3020.0:
    dd._service()
    CLOCK[0] = round(CLOCK[0] + 0.005, 3)
b = dd._anima_beat_sec()
check(abs(b - 60 / 132) < 0.002, f"the delay beat follows the tempo map while the player plays: {b:.3f}s (want 0.455)")

print("FAILS:" if fails else "PASS")
for f in fails:
    print("  ", f)
sys.exit(1 if fails else 0)
