"""Build the EFX palette picker page from the live tables_gs.py.

    python tools/picker/build_picker.py tools/picker/picker_template.html efx-palettes.html

Families come in ANIMA_EFX_PRIORITY order, then the seat unit. Weights: 4 = favoured,
2 = normal, 1 = less often. The published page saves picks to its own database
(collection "palettes", one doc per family: nums / fav / rare as SC-8850 type numbers).
"""
import json, sys, re
REPO = __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
sys.path.insert(0, REPO)
import tables_gs as T
src = open(sys.argv[1]).read()
ver = re.search(r'VERSION = "([^"]+)"', open(__import__("os").path.join(REPO, "duality.py")).read()).group(1)
num = {(m, l): n for n, _name, m, l in T.GS_EFX_LIST}
lst = [{"n": n, "name": name, "addr": f"{m:02X} {l:02X}"} for n, name, m, l in T.GS_EFX_LIST]
fams = []
for fid in list(T.ANIMA_EFX_PRIORITY) + ["seat"]:
    rows = T.ANIMA_EFX_GS.get(fid) or []
    nums, fav, rare = [], [], []
    for r in rows:
        n = num[(r[0], r[1])]
        w = r[3] if len(r) > 3 else 2
        nums.append(n)
        if w >= 4: fav.append(n)
        elif w <= 1: rare.append(n)
    fams.append({"id": fid, "nums": nums, "fav": fav, "rare": rare, "ranked": fid != "seat"})
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
const RANKED = DATA.fams.filter(f=>f.ranked);
const state = {}; // fam -> {nums:[], fav:[], rare:[]}
for (const f of DATA.fams) state[f.id] = {nums:[...f.nums], fav:[...f.fav], rare:[...f.rare]};''')
rep('''function isChanged(id){const s=state[id];return !sameSet(s.nums,DEF[id])||s.fav.length>0||s.rare.length>0}''',
    '''function isChanged(id){const s=state[id],d=DEF[id];return !sameSet(s.nums,d.nums)||!sameSet(s.fav,d.fav)||!sameSet(s.rare,d.rare)}
function rankOf(id){const i=RANKED.findIndex(f=>f.id===id);return i<0?"S":String(i+1)}''')
rep('''      <span class="rank">${i+1}</span>''', '''      <span class="rank">${rankOf(f.id)}</span>''')
rep('''"Matches Duality 0.19.010"''', '''"Matches Duality "+DATA.version''')
rep('''  const rank = DATA.fams.findIndex(f=>f.id===cur)+1;''', '''  const rank = rankOf(cur);''')
rep('''      <button class="act" id="rev" ${sameSet(s.nums,DEF[cur])&&!s.fav.length&&!s.rare.length?'disabled':''}>Revert to current</button>''',
    '''      <button class="act" id="rev" ${isChanged(cur)?'':'disabled'}>Revert to current</button>''')
rep('''  $("#rev").onclick=()=>{state[cur]={nums:[...DEF[cur]],fav:[],rare:[]};save(cur);render();};''',
    '''  $("#rev").onclick=()=>{const d=DEF[cur];state[cur]={nums:[...d.nums],fav:[...d.fav],rare:[...d.rare]};save(cur);render();};''')
rep('''    : '<span class="odds">Nothing ticked: this family plays dry.</span>';''',
    '''    : `<span class="odds">${cur==="seat"?"Nothing ticked: seat units stay plain (no insert).":"Nothing ticked: this family plays dry."}</span>`;''')
rep('''a favoured type counts twice and a less-often type counts half. Hex pairs are the MSB/LSB written to 40 03 00.</p>''',
    '''a favoured type counts twice and a less-often type counts half. Hex pairs are the MSB/LSB written to 40 03 00. <b>S · Seat unit</b> is not an instrument family: it is the insert a spare unit gets while it carries harmony, and any family takes that unit when it needs it.</p>''')
rep('''<nav class="fams" id="fams" aria-label="Families in priority order"></nav>''', '''<nav class="fams" id="fams" aria-label="Families in priority order, then the seat unit"></nav>''')
open(sys.argv[2], "w").write(src)
print("built", ver, [ (f["id"], len(f["nums"]), f["fav"], f["rare"]) for f in fams[-3:]])
