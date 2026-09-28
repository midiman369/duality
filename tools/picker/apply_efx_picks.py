"""Copy the EFX Palettes picks into tables_gs.ANIMA_EFX_GS (each family's rows).

    python tools/picker/apply_efx_picks.py <dir with palettes/<family>.json ...>

The directory is what ArtifactData "list" with out_dir writes for collection "palettes".
Rows come out in SC-8850 type order as (msb, lsb, name, weight), weight = 2 x the page's
multiplier (2 normal, 4 x2, 1 x1/2, 2/3 x1/3 ...). Families the page has no doc for stay.
"""
import glob
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)
import tables_gs as T  # noqa: E402

BY_N = {n: (m, l, name) for n, name, m, l in T.GS_EFX_LIST}


def weight(st):
    m = st + 1 if st > 0 else (1 / (1 - st) if st < 0 else 1)
    w = 2 * m
    return str(int(w)) if abs(w - round(w)) < 1e-9 else f"2 / {1 - st}"


path = os.path.join(REPO, "tables_gs.py")
src = open(path).read()
changed = []
for f in sorted(glob.glob(os.path.join(sys.argv[1], "palettes", "*.json"))):
    fam = os.path.basename(f)[:-5]
    v = json.load(open(f))
    nums = sorted(n for n in v.get("nums") or [] if n in BY_N)
    step = {}
    if isinstance(v.get("step"), dict):
        step = {int(k): int(x) for k, x in v["step"].items()}
    else:
        step = {**{n: 1 for n in v.get("fav") or []}, **{n: -1 for n in v.get("rare") or []}}
    rows = []
    for n in nums:
        m, l, name = BY_N[n]
        rows.append(f"        (0x{m:02X}, 0x{l:02X}, \"{name}\", {weight(step.get(n, 0))}),  # #{n}")
    pat = re.compile(r'(\n    "%s": \[\n)(.*?)(\n    \],)' % re.escape(fam), re.S)
    mt = pat.search(src)
    if not mt:
        print("no block for", fam)
        continue
    body = "\n".join(rows)
    if mt.group(2) != body:
        src = src[:mt.start(2)] + body + src[mt.end(2):]
        changed.append(fam)
open(path, "w").write(src)
print("changed:", changed)
