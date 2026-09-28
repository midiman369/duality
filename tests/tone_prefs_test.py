"""Tone Palettes picks (tables_8850.ANIMA_TONE_PREFS), no song.

  1. no picks: every program picks exactly as the plain seeded rule (slots[mix % n])
  2. w 0 removes a tone, and a blocked tone switched on comes back
  3. a favoured tone wins about twice as often as a normal one over many seeds
  4. stepped weights (x3, x1/3) land near their ratio; the old 1 / 2 / 4 weights keep the
     original roll exactly (EFX palettes and tone picks keep their seeds)
"""
import sys
import common  # noqa: F401  (sets sys.path)
import tables_8850 as T
import duality as D

fails = []
choose = D.Duality._anima_tone_choose
T.ANIMA_TONE_PREFS.clear()   # these checks start from no picks (the real ones live in tables_8850)

# 1. no picks
for pc in range(120):
    slots = T.anima_tone_slots(pc)
    for mix in (0, 7, 123, 99991):
        if slots and choose(pc, slots, mix) != slots[mix % len(slots)]:
            fails.append(f"1: pc{pc} mix {mix} changed with no picks")
            break

# 2. off / blocked on
T.ANIMA_TONE_PREFS[48] = {(8, 4, 48): {"w": 0}}
if (8, 4, 48) in T.anima_tone_slots(48):
    fails.append("2: an unticked tone is still offered")
T.ANIMA_TONE_PREFS[61] = {(16, 4, 61): {"w": 2}}
if (16, 4, 61) not in T.anima_tone_slots(61):
    fails.append("2: a reserved tone switched on is not offered")

# 3. favoured x2
slots = T.anima_tone_slots(48)
fav = slots[1]
T.ANIMA_TONE_PREFS[48][fav] = {"w": 4}
n = {s: 0 for s in slots}
for mix in range(20000):
    n[choose(48, slots, mix)] += 1
normal = [v for s, v in n.items() if s != fav]
ratio = n[fav] / (sum(normal) / len(normal))
if not 1.8 < ratio < 2.2:
    fails.append(f"3: favoured picked {ratio:.2f}x a normal tone, want ~2")
print(f"favoured vs normal: {ratio:.2f}x over {len(slots)} tones")
T.ANIMA_TONE_PREFS.clear()

# 4. steps
pick = D.Duality._anima_weighted_pick
items = list("abcd")
for ws, want in (([6, 2, 2, 2], 3.0), ([2 / 3, 2, 2, 2], 1 / 3)):
    n = {x: 0 for x in items}
    for mix in range(65536):
        n[pick(items, ws, mix)] += 1
    got = n["a"] / (sum(n[x] for x in "bcd") / 3)
    if abs(got - want) / want > 0.05:
        fails.append(f"4: weight {ws[0]:.2f} picked {got:.2f}x normal, want {want:.2f}")
    print(f"step weight {ws[0]:.2f}: {got:.2f}x normal")
for ws in ([4, 2, 1, 2], [2, 2, 2, 2], [1, 1, 4, 2]):
    for mix in range(0, 65536, 7):
        roll, old = mix % sum(ws), items[-1]
        for x, w in zip(items, ws):
            roll -= w
            if roll < 0:
                old = x
                break
        if pick(items, ws, mix) != old:
            fails.append(f"4: old weights {ws} changed the pick at mix {mix}")
            break

if fails:
    print(f"FAILS ({len(fails)}):")
    for f in fails:
        print("   ", f)
    sys.exit(1)
print("PASS")
