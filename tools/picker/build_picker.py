"""Build the EFX palette picker page from the live tables_gs.py.

    python tools/picker/build_picker.py tools/picker/picker_template.html efx-palettes.html

Families come in GM order (like the tone picker): each sits at the GM group of 8
programs most of its programs fall in, from Duality's own program -> family map; the
seat unit comes last. Each shows its priority (P1 takes a unit first,
ANIMA_EFX_PRIORITY). Weights: 4 = favoured, 2 = normal, 1 = less often. The published
page saves picks to its own database (collection "palettes", one doc per family:
nums / fav / rare as SC-8850 type numbers).
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
fams = []
for fid in sorted(T.ANIMA_EFX_PRIORITY, key=gm_key) + ["seat"]:
    rows = T.ANIMA_EFX_GS.get(fid) or []
    nums, fav, rare = [], [], []
    for r in rows:
        n = num[(r[0], r[1])]
        w = r[3] if len(r) > 3 else 2
        nums.append(n)
        if w >= 4:
            fav.append(n)
        elif w <= 1:
            rare.append(n)
    fams.append({"id": fid, "nums": nums, "fav": fav, "rare": rare, "ranked": fid != "seat",
                 "prio": prio.get(fid, 0), "gm": f"{gm_key(fid)[1] + 1:03d}" if fid != "seat" else ""})
dly = sorted(num[k] for k, v in T.ANIMA_EFX_DELAY.items() if v.get("times"))
data = json.dumps({"list": lst, "fams": fams, "version": ver, "dly": dly})


def rep(a, b):
    global src
    assert src.count(a) == 1, a[:60]
    src = src.replace(a, b)


rep("const DATA = __DATA__;", "const DATA = " + data + ";")
rep('''  fx:{label:"Synth FX",pcs:"GM 97–104 · Rain, Soundtrack, Crystal …"},
};''', '''  fx:{label:"Synth FX",pcs:"GM 97–104 · Rain, Soundtrack, Crystal …"},
  seat:{label:"Seat unit (harmony)",pcs:"Spare unit carrying harmony · ranks below every family"},
};''')
rep('''const DEF = Object.fromEntries(DATA.fams.map(f=>[f.id,f.nums]));
const state = {}; // fam -> {nums:[], fav:[], rare:[]}
for (const f of DATA.fams) state[f.id] = {nums:[...f.nums], fav:[], rare:[]};''', '''const DEF = Object.fromEntries(DATA.fams.map(f=>[f.id,{nums:f.nums,fav:f.fav,rare:f.rare}]));
const state = {}; // fam -> {nums:[], fav:[], rare:[]}
for (const f of DATA.fams) state[f.id] = {nums:[...f.nums], fav:[...f.fav], rare:[...f.rare]};''')
rep('''function isChanged(id){const s=state[id];return !sameSet(s.nums,DEF[id])||s.fav.length>0||s.rare.length>0}''',
    '''function isChanged(id){const s=state[id],d=DEF[id];return !sameSet(s.nums,d.nums)||!sameSet(s.fav,d.fav)||!sameSet(s.rare,d.rare)}
function rankOf(id){const f=DATA.fams.find(f=>f.id===id);return f&&f.prio?String(f.prio):"S"}''')
rep('''      <span class="rank">${i+1}</span><span>${esc(FAMINFO[f.id].label)}''',
    '''      <span class="rank">${f.gm}</span><span>${esc(FAMINFO[f.id].label)}<span class="prio" title="Priority: P1 takes a unit first">${f.prio?'P'+f.prio:'seat'}</span>''')
rep('''<div class="navhead">Priority · family · types</div>''', '''<div class="navhead">GM · family · priority · types</div>''')
rep('''"Matches Duality 0.19.010"''', '''"Matches Duality "+DATA.version''')
rep('''  const rank = DATA.fams.findIndex(f=>f.id===cur)+1;''', '''  const rank = rankOf(cur);''')
rep('''<h2>${rank}. ${esc(info.label)}</h2><span class="pcs">${esc(info.pcs)}</span>''',
    '''<h2>${esc(info.label)}</h2><span class="pcs">${esc(info.pcs)}${rank==="S"?"":" · priority P"+rank}</span>''')
rep('''.rank{font-family:var(--mono);font-size:11px;color:var(--muted);text-align:right}''',
    '''.rank{font-family:var(--mono);font-size:11px;color:var(--muted);text-align:right;font-variant-numeric:tabular-nums}
.prio{font-family:var(--mono);font-size:10px;color:var(--muted);border:1px solid var(--line);border-radius:4px;padding:0 4px;margin-left:6px;vertical-align:1px}
.fambtn[aria-current="true"] .prio{color:var(--accent-ink);border-color:var(--accent)}''')
rep('''grid-template-columns:22px 1fr auto;''', '''grid-template-columns:28px 1fr auto;''')
rep('''      <button class="act" id="rev" ${sameSet(s.nums,DEF[cur])&&!s.fav.length&&!s.rare.length?'disabled':''}>Revert to current</button>''',
    '''      <button class="act" id="rev" ${isChanged(cur)?'':'disabled'}>Revert to current</button>''')
rep('''  $("#rev").onclick=()=>{state[cur]={nums:[...DEF[cur]],fav:[],rare:[]};save(cur);render();};''',
    '''  $("#rev").onclick=()=>{const d=DEF[cur];state[cur]={nums:[...d.nums],fav:[...d.fav],rare:[...d.rare]};save(cur);render();};''')
rep('''    : '<span class="odds">Nothing ticked: this family plays dry.</span>';''',
    '''    : `<span class="odds">${cur==="seat"?"Nothing ticked: seat units stay plain (no insert).":"Nothing ticked: this family plays dry."}</span>`;''')
rep('''<p class="foot">Priority order is the order boxes are handed out: a family higher on the list takes an insert box from a lower one.''',
    '''<p class="foot">Families are listed in GM order, like the tone picker; the number on the left is the first GM program of each. <b>P</b> is its priority, the order insert boxes are handed out: a family with a lower P number takes a box from one with a higher number.''')
rep('''a favoured type counts twice and a less-often type counts half. Hex pairs are the MSB/LSB written to 40 03 00.</p>''',
    '''a favoured type counts twice and a less-often type counts half. Hex pairs are the MSB/LSB written to 40 03 00. <b>Seat unit</b> is not an instrument family: it is the insert a spare unit gets while it carries harmony, and any family takes that unit when it needs it.</p>''')
rep('''<nav class="fams" id="fams" aria-label="Families in priority order"></nav>''', '''<nav class="fams" id="fams" aria-label="Families in GM order, then the seat unit"></nav>''')
open(sys.argv[2], "w").write(src)
print("built", ver, [(f["gm"], f["id"], f["prio"]) for f in fams])
