"""Build the CM-64 PCM Picks page from the live tables_cm64.py.

    python tools/picker/build_cm64_picker.py tools/picker/cm64_picker_template.html cm64-picks.html

One row per GM program (1-128): which half of a CM-64 plays it under Voodoo (la / pcm /
layer), its PCM tone (the 64 internal tones, CM-64 manual p.12-13) and a level per half.
The published page saves to its own database: collection "cm64", one doc per program
("g001".."g128"): {pc, use, pcm, la, lv, note}. Apply them with apply_cm64_picks.py.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, REPO)
import tables_cm64 as T  # noqa: E402

GM = [
    "Acoustic Grand Piano", "Bright Acoustic Piano", "Electric Grand Piano", "Honky-tonk Piano",
    "Electric Piano 1", "Electric Piano 2", "Harpsichord", "Clavi",
    "Celesta", "Glockenspiel", "Music Box", "Vibraphone", "Marimba", "Xylophone", "Tubular Bells", "Dulcimer",
    "Drawbar Organ", "Percussive Organ", "Rock Organ", "Church Organ", "Reed Organ", "Accordion", "Harmonica",
    "Tango Accordion",
    "Acoustic Guitar (nylon)", "Acoustic Guitar (steel)", "Electric Guitar (jazz)", "Electric Guitar (clean)",
    "Electric Guitar (muted)", "Overdriven Guitar", "Distortion Guitar", "Guitar Harmonics",
    "Acoustic Bass", "Electric Bass (finger)", "Electric Bass (pick)", "Fretless Bass", "Slap Bass 1",
    "Slap Bass 2", "Synth Bass 1", "Synth Bass 2",
    "Violin", "Viola", "Cello", "Contrabass", "Tremolo Strings", "Pizzicato Strings", "Orchestral Harp", "Timpani",
    "String Ensemble 1", "String Ensemble 2", "Synth Strings 1", "Synth Strings 2", "Choir Aahs", "Voice Oohs",
    "Synth Voice", "Orchestra Hit",
    "Trumpet", "Trombone", "Tuba", "Muted Trumpet", "French Horn", "Brass Section", "Synth Brass 1", "Synth Brass 2",
    "Soprano Sax", "Alto Sax", "Tenor Sax", "Baritone Sax", "Oboe", "English Horn", "Bassoon", "Clarinet",
    "Piccolo", "Flute", "Recorder", "Pan Flute", "Blown Bottle", "Shakuhachi", "Whistle", "Ocarina",
    "Lead 1 (square)", "Lead 2 (sawtooth)", "Lead 3 (calliope)", "Lead 4 (chiff)", "Lead 5 (charang)",
    "Lead 6 (voice)", "Lead 7 (fifths)", "Lead 8 (bass + lead)",
    "Pad 1 (new age)", "Pad 2 (warm)", "Pad 3 (polysynth)", "Pad 4 (choir)", "Pad 5 (bowed)", "Pad 6 (metallic)",
    "Pad 7 (halo)", "Pad 8 (sweep)",
    "FX 1 (rain)", "FX 2 (soundtrack)", "FX 3 (crystal)", "FX 4 (atmosphere)", "FX 5 (brightness)",
    "FX 6 (goblins)", "FX 7 (echoes)", "FX 8 (sci-fi)",
    "Sitar", "Banjo", "Shamisen", "Koto", "Kalimba", "Bag pipe", "Fiddle", "Shanai",
    "Tinkle Bell", "Agogo", "Steel Drums", "Woodblock", "Taiko Drum", "Melodic Tom", "Synth Drum", "Reverse Cymbal",
    "Guitar Fret Noise", "Breath Noise", "Seashore", "Bird Tweet", "Telephone Ring", "Helicopter", "Applause",
    "Gunshot",
]
assert len(GM) == 128


def partials():
    src = open(os.path.join(REPO, "duality.py")).read()
    m = re.search(r"CM64_PCM_PARTIALS = \((.*?)\n\)", src, re.S)
    nums = [int(x) for x in re.findall(r"^\s*([\d, ]+),\s*#", m.group(1), re.M) for x in x.split(",") if x.strip()]
    assert len(nums) == 64, len(nums)
    return nums


def version():
    return re.search(r'^VERSION = "([^"]+)"', open(os.path.join(REPO, "duality.py")).read(), re.M).group(1)


def main(tpl, out):
    pt = partials()
    picks = {}
    for pc in range(128):
        use, pcm, la, lv = T.cm64_gm_pick(pc)
        picks[pc] = {"use": use, "pcm": pcm, "la": la, "lv": lv, "note": T.CM64_GM_NOTES.get(pc, "")}
    data = {
        "version": version(),
        "tones": [[n, pt[i]] for i, n in enumerate(T.CM64_PCM_TONES)],
        "gm": GM,
        "picks": picks,
        "seed": {pc: ("pcm" if pc in T.CM64_GM_FITTING else "la") for pc in range(128)},
    }
    html = open(tpl).read().replace("__DATA__", json.dumps(data, separators=(",", ":")))
    open(out, "w").write(html)
    print(f"{out}: {sum(1 for p in picks.values() if p['use'] != 'la')} of 128 programs on PCM / layer")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
