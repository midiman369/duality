"""Shared paths for the offline replay tests.

Songs are NOT in the repo. A test looks for its file, under the test name
or the original name, in:
  1. $DUALITY_TEST_MIDI (if set)
  2. tests/midi/          (source songs)
  3. recordings/          (Duality --record takes; git ignores it)
A test whose file is missing is skipped by run_all.py (exit 77).
"""
import os
import sys

TESTS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(TESTS)
MIDI_DIR = os.environ.get("DUALITY_TEST_MIDI", os.path.join(TESTS, "midi"))
IMAGES = os.path.join(REPO, "docs", "images")
SEARCH = [d for d in (os.environ.get("DUALITY_TEST_MIDI"), os.path.join(TESTS, "midi"),
                      os.path.join(REPO, "recordings")) if d]

# Test name -> original file name (see tests/README.md for checksums).
ORIGINAL = {
    "onestop-in-220022.mid": "IN-Duality-4-gs-20260924-220022.mid",
    "onestop-in-221619.mid": "IN-Duality-4-gs-20260924-221619.mid",
    "onestop-in-222922.mid": "IN-Duality-4-gs-20260924-222922.mid",
    "bass-in-000745.mid": "IN-Duality-4-gs-20260925-000745.mid",
    "every-breath-8850.mid": "Every_Breath_You_Take_8850.mid",
    "d_e1m1.mid": "D_E1M1.mid",
    "death-gate-03.mid": "03_-_Death_Gate.MID",
    "death-gate-07.mid": "07_-_Death_Gate.MID",
    "death-gate-97.mid": "97_-_Death_Gate.MID",
    "death-gate-09.mid": "09_-_Death_Gate.MID",
    "lotr-8850.mid": "LotR_8850.mid",
    "grabbag.mid": "01_GRABBAG.MID",
    "phobos-8850.mid": "18_-_phobos_anomaly_8850.mid",
    "rose-gun-sight.mid": "rose_in_the_gun_sight.mid",
}

if REPO not in sys.path:
    sys.path.insert(0, REPO)
if TESTS not in sys.path:
    sys.path.insert(0, TESTS)


def midi(name: str) -> str:
    """Path of a test song; exit 77 (skip) if it is not there."""
    for folder in SEARCH:
        for candidate in (name, ORIGINAL.get(name)):
            if candidate:
                path = os.path.join(folder, candidate)
                if os.path.exists(path):
                    return path
    alt = f" or {ORIGINAL[name]}" if name in ORIGINAL else ""
    print(f"SKIP: {name}{alt} not found in {', '.join(SEARCH)} (see tests/README.md)")
    sys.exit(77)


def load(path: str):
    """mido.MidiFile, tolerating XMI2MID files with stray bytes after end-of-track."""
    import io
    import struct
    import mido
    try:
        return mido.MidiFile(path)
    except (EOFError, OSError, ValueError):
        pass
    data = bytearray(open(path, "rb").read())
    i = 14
    while i + 8 <= len(data):
        ln = struct.unpack(">I", data[i + 4:i + 8])[0]
        end = data.find(b"\xff\x2f\x00", i + 8, i + 8 + ln)
        if data[i:i + 4] == b"MTrk" and end >= 0:
            new = end + 3 - (i + 8)
            del data[end + 3:i + 8 + ln]
            data[i + 4:i + 8] = struct.pack(">I", new)
            ln = new
        i += 8 + ln
    return mido.MidiFile(file=io.BytesIO(bytes(data)))


# --- Format 1 output for the generated test songs --------------------------------------
GM_NAMES = (
    "Piano 1,Piano 2,Piano 3,Honky-tonk,E.Piano 1,E.Piano 2,Harpsichord,Clav,Celesta,Glockenspiel,"
    "Music Box,Vibraphone,Marimba,Xylophone,Tubular Bells,Dulcimer,Drawbar Organ,Perc. Organ,"
    "Rock Organ,Church Organ,Reed Organ,Accordion,Harmonica,Bandoneon,Nylon Gt,Steel Gt,Jazz Gt,"
    "Clean Gt,Muted Gt,Overdrive Gt,Distortion Gt,Gt Harmonics,Acoustic Bass,Fingered Bass,"
    "Picked Bass,Fretless Bass,Slap Bass 1,Slap Bass 2,Synth Bass 1,Synth Bass 2,Violin,Viola,Cello,"
    "Contrabass,Tremolo Strings,Pizzicato,Harp,Timpani,Strings,Slow Strings,Synth Strings 1,"
    "Synth Strings 2,Choir Aahs,Voice Oohs,Synth Vox,Orchestra Hit,Trumpet,Trombone,Tuba,"
    "Muted Trumpet,French Horn,Brass Section,Synth Brass 1,Synth Brass 2,Soprano Sax,Alto Sax,"
    "Tenor Sax,Baritone Sax,Oboe,English Horn,Bassoon,Clarinet,Piccolo,Flute,Recorder,Pan Flute,"
    "Bottle Blow,Shakuhachi,Whistle,Ocarina,Square Lead,Saw Lead,Syn Calliope,Chiffer Lead,Charang,"
    "Solo Vox,5th Saw,Bass & Lead,Fantasia,Warm Pad,Polysynth,Space Voice,Bowed Glass,Metal Pad,"
    "Halo Pad,Sweep Pad,Ice Rain,Soundtrack,Crystal,Atmosphere,Brightness,Goblin,Echo Drops,"
    "Star Theme,Sitar,Banjo,Shamisen,Koto,Kalimba,Bagpipe,Fiddle,Shanai,Tinkle Bell,Agogo,"
    "Steel Drums,Woodblock,Taiko,Melo Tom,Synth Drum,Reverse Cymbal,Fret Noise,Breath Noise,"
    "Seashore,Bird,Telephone,Helicopter,Applause,Gun Shot").split(",")
GS_KITS = {0: "Standard", 8: "Room", 16: "Power", 24: "Electronic", 25: "TR-808", 26: "Dance",
           27: "CR-78", 28: "TR-606", 29: "TR-707", 30: "TR-909", 32: "Jazz", 40: "Brush",
           48: "Orchestra", 56: "SFX"}


def format1(mf, drum_ch: int = 9, max_shift: int = 12):
    """A single-track (Format 0 layout) MidiFile -> Format 1: a conductor track (meta events and
    SysEx) and one track per channel, named after the programs it plays.

    Players send events that share a tick track by track, which would reorder a program-change
    burst (and Anima places inserts by arrival order). So an event that would come out ahead of
    one written before it moves a tick later: played back, the tracks send every event in exactly
    the single track's order, each at most max_shift ticks late (checked)."""
    import mido
    assert len(mf.tracks) == 1
    evs, t, end = [], 0, 0
    for m in mf.tracks[0]:
        t += m.time
        if m.type == "end_of_track":
            end = t
        else:
            evs.append((t, m))
    chans = sorted({m.channel for _t, m in evs if not (m.is_meta or m.type == "sysex")})
    idx = {ch: i + 1 for i, ch in enumerate(chans)}          # conductor is track 0
    groups = [[] for _ in range(len(chans) + 1)]
    prev = (-1, -1)
    shift = 0
    for tk, m in evs:
        k = 0 if (m.is_meta or m.type == "sysex") else idx[m.channel]
        te = max(tk, prev[0])
        if te == prev[0] and k < prev[1]:
            te += 1
        prev = (te, k)
        shift = max(shift, te - tk)
        groups[k].append((te, m))
    assert shift <= max_shift, f"keeping the order moved an event {shift} ticks"
    names = [None]
    for ch in chans:
        progs = []
        for _t, m in groups[idx[ch]]:
            if m.type == "program_change":
                nm = (GS_KITS.get(m.program, f"Kit {m.program + 1}") + " kit") if ch == drum_ch \
                    else GM_NAMES[m.program]
                if nm not in progs:
                    progs.append(nm)
        names.append((f"Ch{ch + 1} " + " / ".join(progs)).strip()[:120])
    out = mido.MidiFile(type=1, ticks_per_beat=mf.ticks_per_beat)
    for g, name in zip(groups, names):
        trk = mido.MidiTrack()
        if name:
            trk.append(mido.MetaMessage("track_name", name=name, time=0))
        last = 0
        for tk, m in g:
            trk.append(m.copy(time=tk - last))
            last = tk
        trk.append(mido.MetaMessage("end_of_track", time=max(0, end + max_shift - last)))
        out.tracks.append(trk)
    merged = [str(m.copy(time=0)) for m in mido.merge_tracks(out.tracks) if not m.is_meta]
    assert merged == [str(m.copy(time=0)) for _t, m in evs if not m.is_meta], "Format 1 order differs"
    out.max_shift = shift
    return out


def onestop2_events():
    """ONESTOP2 (generated by make_onestop2.py, built here if missing) as [(seconds, msg)]."""
    import subprocess
    import mido
    path = os.path.join(TESTS, "midi", "onestop2.mid")
    if not os.path.exists(path):
        subprocess.run([sys.executable, os.path.join(TESTS, "make_onestop2.py"), path], check=True)
    out, t = [], 0.0
    for m in mido.MidiFile(path):
        t += m.time
        if not m.is_meta:
            out.append((t, m))
    return out
