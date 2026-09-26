"""A file set up by an SC-8850 bulk dump keeps its own insert (GTR Multi 3 on ch7)."""
import sys, time as _time
import common
import common  # repo on sys.path, MIDI paths
import mido
CLOCK = [1000.0]
_time.monotonic = lambda: CLOCK[0]
REC = []
class FakeOut:
    def __init__(s, n, i): s.name = n; s.i = i; s.closed = False
    def send(s, m): REC.append((CLOCK[0] - 1000.0, s.i, m))
    def close(s): pass
    def reset(s): pass
    def panic(s): pass
class FakeIn:
    name = "duality"; closed = False
    def poll(s): return None
    def iter_pending(s): return iter(())
    def close(s): pass
import duality as D
from rich.console import Console
D.console = Console(file=open("/dev/null", "w"))
names = ["Roland Sound Canvas VA", "SCVA2", "SCVA3", "SCVA4", "Yamaha S-YXG100", "MUNT"]
idx = {n: i for i, n in enumerate(names)}
D.mido.open_output = lambda n, *a, **k: FakeOut(n, idx[n])
D.mido.open_input = lambda *a, **k: FakeIn()
fmts = [frozenset({"gm2", "gs8850"})] * 4 + [frozenset({"xg"}), frozenset({"mt32"})]
d = D.Duality("duality", names, anima=True, show_status=False, out_formats=fmts,
              anima_seed=0x668B, poly_limits=[32, 32, 32, 32, 64, 32], crucible=True, crucible_gm_wide=True)
fb = []
_o = d._anima_feedback
d._anima_feedback = lambda k, t, status=False: (fb.append((round(CLOCK[0]-1000, 2), k, t)), _o(k, t, status=status))
mf = mido.MidiFile(common.midi("every-breath-8850.mid"))
ev = []; t = 0.0
for m in mf:
    t += m.time
    if not m.is_meta: ev.append((t, m))
END = 240.0
i = 0; tt = 0.0
while tt < END and i < len(ev):
    CLOCK[0] = 1000.0 + tt
    while i < len(ev) and ev[i][0] <= tt:
        d.process(ev[i][1]); i += 1
    try: d._anima_tick()
    except Exception: pass
    d._check_anima_session_idle()
    tt = round(tt + 0.01, 3)
T = D.GS_EFX_TYPES
print("== insert type writes (40 03 00)")
for t, p, m in REC:
    if m.type == "sysex":
        x = list(m.data)
        if x[4:7] == [0x40, 0x03, 0x00]:
            print(f"  {t:6.2f} P{p+1} {T.get((x[7], x[8]), x[7:9])}")
print("== Part EFX (40 4x 22) for ch7 (mid 47)")
for t, p, m in REC:
    if m.type == "sysex":
        x = list(m.data)
        if x[4] == 0x40 and x[5] == 0x47 and x[6] == 0x22:
            print(f"  {t:6.2f} P{p+1} ch7 EFX {'On' if x[7] else 'Off'}")
print("== ch7 notes per unit:", {p + 1: sum(1 for t, pp, m in REC if pp == p and m.type == 'note_on' and m.channel == 6 and m.velocity) for p in range(6)})
print("== efx feedback")
for x in fb:
    if x[1].startswith("efx"): print("  ", x)

fails = []
p1_types = [t for t, p, m in REC if p == 0 and m.type == "sysex" and list(m.data)[4:7] == [0x40, 0x03, 0x00]]
if p1_types:
    fails.append(f"P1 (file insert) retyped {len(p1_types)}x")
ch7 = {p: sum(1 for t, pp, m in REC if pp == p and m.type == "note_on" and m.channel == 6 and m.velocity) for p in range(6)}
if ch7[0] == 0 or sum(ch7.values()) != ch7[0]:
    fails.append(f"ch7 notes not all on P1: {ch7}")
if 6 not in d._anima_file_efx_parts:
    fails.append("part 7 not captured from the bulk dump")
print("FAILS:" if fails else "PASS")
for f in fails:
    print("  ", f)
sys.exit(1 if fails else 0)
