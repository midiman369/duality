"""File Part EFX On is not swallowed as Anima's own echo (E1M1 after another song).

Run: GAME=0|1 PRE=0|12 python replay_file_efx_echo.py (run_all.py does all four)."""
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
import os
GAME = os.environ.get("GAME") == "1"
from rich.console import Console
D.console = Console(file=open("/dev/null", "w"))
names = ["Roland Sound Canvas VA", "SCVA2", "SCVA3", "SCVA4", "Yamaha S-YXG100", "MUNT"]
idx = {n: i for i, n in enumerate(names)}
D.mido.open_output = lambda n, *a, **k: FakeOut(n, idx[n])
D.mido.open_input = lambda *a, **k: FakeIn()
fmts = [frozenset({"gm2", "gs8850"})] * 4 + [frozenset({"xg"}), frozenset({"mt32"})]
d = D.Duality("duality", names, anima=True, show_status=False, out_formats=fmts,
              anima_seed=None, anima_game=GAME, poly_limits=[32, 32, 32, 32, 64, 32], crucible=True, crucible_gm_wide=True)
fb = []
print("start parts", sorted(d._anima_file_efx_parts))
_o = d._anima_feedback
d._anima_feedback = lambda k, t, status=False: (fb.append((round(CLOCK[0]-1000, 2), k, t)), _o(k, t, status=status))
mf = mido.MidiFile(common.midi("d_e1m1.mid"))
ev = []; t = 0.0
PRE = float(os.environ.get("PRE", "0"))
if PRE:
    # A different song first: other programs + notes, then silence.
    for c, p in ((0, 47), (1, 49), (2, 33), (6, 29), (8, 31)):
        ev.append((0.1, mido.Message("program_change", channel=c, program=p)))
    for k in range(20):
        ev.append((0.5 + k * 0.3, mido.Message("note_on", channel=k % 3, note=60 + k % 7, velocity=90)))
        ev.append((0.7 + k * 0.3, mido.Message("note_off", channel=k % 3, note=60 + k % 7, velocity=0)))
    t = PRE
for m in mf:
    t += m.time
    if not m.is_meta: ev.append((t, m))
END = 60.0
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
print("file parts at end", sorted(p+1 for p in d._anima_file_efx_parts))
print("== Part EFX for ch2 (mid 42)")
for t, p, m in REC:
    if m.type == "sysex":
        x = list(m.data)
        if x[4] == 0x40 and x[5] == 0x42 and x[6] == 0x22:
            print(f"  {t:6.2f} P{p+1} ch2 EFX {'On' if x[7] else 'Off'}")
print("== ch2 notes per unit:", {p + 1: sum(1 for t, pp, m in REC if pp == p and m.type == 'note_on' and m.channel == 1 and m.velocity) for p in range(6)})
print("== efx feedback")
for x in fb:
    if x[1].startswith("efx"): print("  ", x)

fails = []
if not {0, 1} <= set(d._anima_file_efx_parts):
    fails.append(f"file parts {sorted(p + 1 for p in d._anima_file_efx_parts)}, want 1,2")
song = [x for x in REC if x[0] >= (PRE or 0)]
ch2 = {p: sum(1 for t, pp, m in song if pp == p and m.type == "note_on" and m.channel == 1 and m.velocity) for p in range(6)}
if ch2[0] == 0 or sum(ch2.values()) != ch2[0]:
    fails.append(f"ch2 notes not all on P1 (file OD1/OD2): {ch2}")
print("FAILS:" if fails else "PASS")
for f in fails:
    print("  ", f)
sys.exit(1 if fails else 0)
