"""Copy the CM-64 PCM Picks into tables_cm64.CM64_GM_PICKS (a generated block).

    python tools/picker/apply_cm64_picks.py <dir with cm64/g001.json ...>

The directory is what ArtifactData "list" with out_dir writes for collection "cm64".
Each doc is {pc, use, pcm, la, lv, note}; programs with no doc keep their current pick.
Notes are kept verbatim in CM64_GM_NOTES.
"""
import glob
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)
import tables_cm64 as T  # noqa: E402

picks = {pc: list(T.cm64_gm_pick(pc)) for pc in range(128)}
notes = dict(T.CM64_GM_NOTES)
n = 0
for f in sorted(glob.glob(os.path.join(sys.argv[1], "cm64", "g*.json"))):
    doc = json.load(open(f))
    doc = doc.get("data", doc)
    pc = int(doc["pc"])
    use = doc.get("use") if doc.get("use") in T.CM64_USES else picks[pc][0]
    pcm = max(0, min(63, int(doc.get("pcm", picks[pc][1]))))
    la = max(0, min(150, int(doc.get("la", picks[pc][2]))))
    lv = max(0, min(150, int(doc.get("lv", picks[pc][3]))))
    picks[pc] = [use, pcm, la, lv]
    note = (doc.get("note") or "").strip()
    if note:
        notes[pc] = note
    else:
        notes.pop(pc, None)
    n += 1

lines = ["# --- CM64_GM_PICKS (generated) ---", "CM64_GM_PICKS = {"]
for pc in range(128):
    use, pcm, la, lv = picks[pc]
    lines.append(f"    {pc}: ({use!r}, {pcm}, {la}, {lv}),  # {pc + 1:03d} -> {T.CM64_PCM_TONES[pcm]}")
lines.append("}")
lines.append("CM64_GM_NOTES: dict = {")
for pc in sorted(notes):
    lines.append(f"    {pc}: {notes[pc]!r},")
lines.append("}")
lines.append("# --- end CM64_GM_PICKS ---")
path = os.path.join(REPO, "tables_cm64.py")
src = open(path).read()
pat = re.compile(r"# --- CM64_GM_PICKS \(generated\) ---.*?# --- end CM64_GM_PICKS ---", re.S)
assert pat.search(src)
src = pat.sub(lambda _m: "\n".join(lines), src)
open(path, "w").write(src)
print(f"{n} picks applied; {sum(1 for p in picks.values() if p[0] != 'la')} of 128 programs on PCM / layer")
