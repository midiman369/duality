"""Render README panel images from an offline ONESTOP2 replay (no MIDI hardware).

    python tests/render_status.py <seconds> <out.svg> [<seconds> <out.svg> ...]
"""
import sys, time as _time
import common  # repo on sys.path, MIDI paths
import mido
CLOCK = [1000.0]
_time.monotonic = lambda: CLOCK[0]
class FakeOut:
    def __init__(s, n): s.name = n; s.closed = False
    def send(s, m): pass
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
from wt_svg import save_wt
from rich.table import Table
from rich import box
D.mido.open_output = lambda n, *a, **k: FakeOut(n)
D.mido.open_input = lambda *a, **k: FakeIn()
W = 168
D.console = Console(width=W, record=True, force_terminal=True, color_system="truecolor", file=open("/dev/null", "w"))
names = ["Roland Sound Canvas VA", "SCVA2", "SCVA3", "SCVA4", "Yamaha S-YXG100", "MUNT"]
fmts = [frozenset({"gm2", "gs8850"})] * 4 + [frozenset({"xg"}), frozenset({"mt32"})]
d = D.Duality("duality", names, anima=True, show_status=False, out_formats=fmts,
              anima_seed=0xFC6C, poly_limits=[32, 32, 32, 32, 64, 32],
              crucible=True, crucible_gm_wide=True)
# As played: R (GS) then L (lock) before starting the file.
d._force_format("GS", "hotkey R")
d._toggle_format_lock()
ev = common.onestop2_events()
shots = {float(sys.argv[i]): sys.argv[i + 1] for i in range(1, len(sys.argv), 2)}
i = 0; tt = 0.0
while shots and tt < ev[-1][0]:
    CLOCK[0] = 1000.0 + tt
    while i < len(ev) and ev[i][0] <= tt:
        d.process(ev[i][1]); i += 1
    try: d._anima_tick()
    except Exception: pass
    d._check_anima_session_idle()
    for st in list(shots):
        if tt >= st:
            out = shots.pop(st)
            c = Console(width=W, record=True, force_terminal=True, color_system="truecolor", file=open("/dev/null", "w"))
            D.console = c
            c.print(d._make_status_panel())
            save_wt(c, out)
            print("wrote", out, "at", round(tt, 2))
    tt = round(tt + 0.01, 3)
