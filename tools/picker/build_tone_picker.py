"""Build the tone palette picker page from the live tables_8850.py.

    python tools/picker/build_tone_picker.py tools/picker/tone_picker_template.html tone-palettes.html

One section per GM program (0-119) listing the tone slots anima_tone_slots() can pick,
plus the reserved (blocked) ones. Names, voice counts and loop mode come from
tone_info.json ("cc00-cc32-pc": [name, oneshot, voices]; oneshot 2 = every sample plays
once, 1 = an attack layer does), extracted from shingo45endo/tone-browser sc-8850.json
(sample byte 10: 0 = loop, 2 = no loop). Rebuild tone_info.json with --info <sc-8850.json>.

The published page saves to its own database: collection "tones", one doc per program
("p001".."p120"): {pc, slots: {"cc00-cc32-pc": {on, w, efx, note}}}, only tones that differ
from the defaults. Copy them into tables_8850.ANIMA_TONE_PREFS (w 0 when on is false).
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, REPO)
import tables_8850 as T  # noqa: E402
from tables_voices import gs8850_tone_voices  # noqa: E402

INFO = os.path.join(HERE, "tone_info.json")


def all_keys():
    progs = {}
    for pc in range(120):
        keys = list(T.anima_tone_slots(pc))
        for c0, p in sorted(T.ANIMA_TONE_BLOCK):
            if p == pc and (c0, 4, p) not in keys:
                keys.append((c0, 4, p))
        # A program whose picks switch some tones off still lists them on the page.
        for k in (T.ANIMA_TONE_PREFS.get(pc) or {}):
            if tuple(k) not in keys:
                keys.append(tuple(k))
        progs[pc] = keys
    return progs


def build_info(src):
    d = json.load(open(src))
    samples = {s["sampleNo"]: s for s in d["samples"]}
    waves = {w["waveNo"]: w for w in d["waves"]}
    tm = {(t["bankM"], t["bankL"], t["prog"]): t for t in d["toneMaps"]}

    def resolve(ref):
        _, a, i = ref.split("/")
        return d[a][int(i)]

    def info(t):
        if "combiRef" in t:
            c = resolve(t["combiRef"]["$ref"])
            tones, name = [resolve(s["toneRef"]["$ref"]) for s in c["toneSlots"]], c["name"]
        else:
            tones = [resolve(t["toneRef"]["$ref"])]
            name = tones[0]["name"]
        flags = []
        for tn in tones:
            for v in tn["voices"]:
                w = waves.get(v.get("waveNo"))
                for sl in (w or {}).get("sampleSlots", []):
                    s = samples.get(sl["sampleNo"])
                    if s:
                        flags.append(s["bytes"][10])
        one = 2 if flags and all(f == 2 for f in flags) else (1 if 2 in flags else 0)
        return name.rstrip(": ").strip(), one

    out = {}
    for keys in all_keys().values():
        for k in keys:
            for m in (k, (k[0], 4, k[2]), (k[0], 3, k[2]), (k[0], 2, k[2]), (k[0], 1, k[2])):
                if m in tm:
                    name, one = info(tm[m])
                    out[f"{k[0]}-{k[1]}-{k[2]}"] = [name, one, int(gs8850_tone_voices(*k))]
                    break
    json.dump(out, open(INFO, "w"), separators=(",", ":"), sort_keys=True)
    return out


def main(argv):
    if "--info" in argv:
        i = argv.index("--info")
        build_info(argv[i + 1])
        del argv[i:i + 2]
    info = json.load(open(INFO))
    progs = all_keys()
    ks = lambda k: f"{k[0]}-{k[1]}-{k[2]}"
    missing = [ks(k) for keys in progs.values() for k in keys if ks(k) not in info]
    if missing:
        sys.exit(f"tone_info.json lacks {missing[:8]}: rebuild with --info <sc-8850.json>")
    # Defaults = what Duality does today, so "Revert" and "changed" mean the same as in the EFX picker.
    blocked = [ks((c0, 4, p)) for c0, p in T.ANIMA_TONE_BLOCK]
    default = {}
    for pc, keys in progs.items():
        for k in keys:
            pref = T.anima_tone_pref(pc, k)
            d = {}
            if pref:
                w = int(pref.get("w", 2))
                if w <= 0:
                    d["on"] = False
                else:
                    d["w"] = w
                if pref.get("efx"):
                    d["efx"] = int(pref["efx"])
                if pref.get("note"):
                    d["note"] = str(pref["note"])
            elif ks(k) in blocked:
                d["on"] = False
            elif (k[0], k[2]) in T.ANIMA_TONE_RARE:
                d["w"] = 1
            if d:
                default.setdefault(pc, {})[ks(k)] = d
    used = {ks(k) for keys in progs.values() for k in keys} | {f"0-4-{pc}" for pc in range(120)}
    ver = re.search(r'VERSION = "([^"]+)"', open(os.path.join(REPO, "duality.py")).read()).group(1)
    # DEF is keyed per program on the page; flatten with the program so a tone listed
    # under two programs (Clean Gt colors on 29-31) keeps separate defaults.
    data = {
        "version": ver,
        "info": {k: v for k, v in info.items() if k in used},
        "progs": {pc: [ks(k) for k in keys] for pc, keys in progs.items()},
        "defp": {pc: v for pc, v in default.items()},
        "blocked": blocked,
    }
    src = open(argv[1]).read()
    assert src.count("const DATA = __DATA__;") == 1
    src = src.replace("const DATA = __DATA__;", "const DATA = " + json.dumps(data, separators=(",", ":")) + ";")
    open(argv[2], "w").write(src)
    n = sum(len(v) for v in progs.values())
    print("built", ver, n, "tones,", sum(len(v) for v in default.values()), "non-default")


if __name__ == "__main__":
    main(sys.argv)
