"""Crucible demo: one Duality per input dialect, same six outs, same notes."""
import os, sys, time as _time
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
D.mido.open_output = lambda n, *a, **k: FakeOut(n)
D.mido.open_input = lambda *a, **k: FakeIn()
W = 168
null = open("/dev/null", "w")
names = ["Roland Sound Canvas VA", "SCVA2", "SCVA3", "SCVA4", "Yamaha S-YXG100", "MUNT"]
fmts = [frozenset({"gm2", "gs8850"})] * 4 + [frozenset({"xg"}), frozenset({"mt32"})]
def sysex_of(path):
    m = mido.MidiFile(os.path.join(common.REPO, path))
    return [x for x in mido.merge_tracks(m.tracks) if x.type == "sysex"]
heads = {
    "GM": [mido.Message("sysex", data=[0x7E, 0x7F, 0x09, 0x01])],
    "GS": sysex_of("test_gs_display.mid"),
    "XG": sysex_of("test_xg_display.mid"),
    "MT-32": sysex_of("test_mt32_display.mid"),
}
IN = common.midi("onestop-in-222922.mid")
mf = mido.MidiFile(IN); body = []; t = 0.0
for m in mido.merge_tracks(mf.tracks):
    t += mido.tick2second(m.time, mf.ticks_per_beat, 500000) if m.time else 0
    if m.is_meta or m.type == "sysex":
        continue
    if 25.0 <= t < 32.0 and m.type in ("note_on", "note_off"):
        body.append((t - 25.0 + 1.0, m))
    elif t < 4.0 and m.type in ("program_change", "control_change"):
        body.append((0.5, m))
for fmt, head in heads.items():
    CLOCK[0] = 1000.0
    D.console = Console(width=W, record=True, force_terminal=True, color_system="truecolor", file=null)
    d = D.Duality("duality", names, show_status=False, out_formats=fmts,
                  poly_limits=[32, 32, 32, 32, 64, 32], crucible=True)
    ev = [(0.0, m) for m in head] + body
    ev.sort(key=lambda e: e[0])
    i = 0; tt = 0.0; snap = 5.9
    while tt <= snap:
        CLOCK[0] = 1000.0 + tt
        while i < len(ev) and ev[i][0] <= tt:
            d.process(ev[i][1]); i += 1
        tt = round(tt + 0.01, 3)
    c = Console(width=W, record=True, force_terminal=True, color_system="truecolor", file=null)
    D.console = c
    c.print(d._make_status_panel())
    out = fcommon.IMAGES + "/crucible-{fmt.lower().replace('-', '')}.svg"
    save_wt(c, out)
    print(fmt, "badge", d.detected_format, "voices", d.voice_counts, "->", out)
