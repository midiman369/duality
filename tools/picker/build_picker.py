"""Build the EFX palette picker page from the live tables_gs.py.

    python tools/picker/build_picker.py tools/picker/picker_template.html efx-palettes.html

Families come in GM order (like the tone picker): each sits at the GM group of 8
programs most of its programs fall in, from Duality's own program -> family map; the
seat unit comes last. Each shows its priority (P1 takes a unit first,
ANIMA_EFX_PRIORITY). Table weights are 2 x the multiplier (2 = normal, 4 = x2, 6 = x3,
1 = x1/2, 2/3 = x1/3); the page shows them as steps. The published page saves picks to its
own database (collection "palettes", one doc per family: nums, step {type number: step},
plus fav / rare lists for older readers). The template holds the whole page; this script
only fills in DATA.
"""
import collections
import json
import os
import re
import sys
import types

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)
import tables_gs as T  # noqa: E402
import duality as D  # noqa: E402

src = open(sys.argv[1]).read()
ver = re.search(r'VERSION = "([^"]+)"', open(os.path.join(REPO, "duality.py")).read()).group(1)
num = {(m, l): n for n, _name, m, l in T.GS_EFX_LIST}
lst = [{"n": n, "name": name, "addr": f"{m:02X} {l:02X}"} for n, name, m, l in T.GS_EFX_LIST]

_o = types.SimpleNamespace(_anima_is_rhythm=lambda c: False, _anima_prog=[0] * 16, bank_msb=[0] * 16,
                           _anima_efx_from_cat=lambda c: None)
progs = collections.defaultdict(list)
for p in range(128):
    _o._anima_prog[0] = p
    f = D.Duality._anima_efx_family(_o, 0)
    if f:
        progs[f].append(p)


def gm_key(fid):
    ps = progs.get(fid)
    if not ps:
        return (999, 999)
    grp = collections.Counter(p // 8 for p in ps).most_common(1)[0][0]
    return (grp, min(p for p in ps if p // 8 == grp))


prio = {fid: i + 1 for i, fid in enumerate(T.ANIMA_EFX_PRIORITY)}


def step_of(w):
    """Table weight (2 = normal, 4 = x2, 1 = x1/2, 6 = x3, 2/3 = x1/3 ...) -> picker step."""
    m = float(w) / 2.0
    return int(round(m - 1)) if m >= 1 else -int(round(1 / m - 1))


fams = []
for fid in sorted(T.ANIMA_EFX_PRIORITY, key=gm_key) + ["seat"]:
    nums, step = [], {}
    for r in T.ANIMA_EFX_GS.get(fid) or []:
        n = num[(r[0], r[1])]
        nums.append(n)
        st = step_of(r[3] if len(r) > 3 else 2)
        if st:
            step[n] = st
    fams.append({"id": fid, "nums": nums, "step": step, "ranked": fid != "seat",
                 "prio": prio.get(fid, 0), "gm": f"{gm_key(fid)[1] + 1:03d}" if fid != "seat" else ""})
dly = sorted(num[k] for k, v in T.ANIMA_EFX_DELAY.items() if v.get("times"))
data = json.dumps({"list": lst, "fams": fams, "version": ver, "dly": dly})
assert src.count("const DATA = __DATA__;") == 1
src = src.replace("const DATA = __DATA__;", "const DATA = " + data + ";")
open(sys.argv[2], "w").write(src)
print("built", ver, sum(len(f["nums"]) for f in fams), "types,", sum(len(f["step"]) for f in fams), "weighted")
