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
# Seven seconds of ONESTOP2's big-band shout chorus (notes only), after its program / CC setup.
WIN = (194.0, 201.0)
body = []
for t, m in common.onestop2_events():
    if m.type == "sysex":
        continue
    if WIN[0] <= t < WIN[1] and m.type in ("note_on", "note_off"):
        body.append((t - WIN[0] + 1.0, m))
    elif t < WIN[0] and m.type in ("program_change", "control_change"):
        body.append((0.5, m))
def play(head, until=None):
    """Run the head + window; return (duality, busiest time) or the duality at `until`."""
    CLOCK[0] = 1000.0
    D.console = Console(width=W, record=True, force_terminal=True, color_system="truecolor", file=null)
    d = D.Duality("duality", names, show_status=False, out_formats=fmts,
                  poly_limits=[32, 32, 32, 32, 64, 32], crucible=True)
    ev = sorted([(0.0, m) for m in head] + body, key=lambda e: e[0])
    i = 0; tt = 0.0; best = (-1, 0.0)
    end = WIN[1] - WIN[0] + 1.0 if until is None else until
    while tt <= end:
        CLOCK[0] = 1000.0 + tt
        while i < len(ev) and ev[i][0] <= tt:
            d.process(ev[i][1]); i += 1
        if until is None and tt >= 2.0 and sum(d.voice_counts) > best[0]:
            best = (sum(d.voice_counts), tt)
        tt = round(tt + 0.01, 3)
    return d, best[1]


snap = play(heads["GS"])[1]          # the busiest moment, the same for every dialect
for fmt, head in heads.items():
    d = play(head, snap)[0]
    c = Console(width=W, record=True, force_terminal=True, color_system="truecolor", file=null)
    D.console = c
    c.print(d._make_status_panel())
    out = common.IMAGES + f"/crucible-{fmt.lower().replace('-', '')}.svg"
    save_wt(c, out)
    print(fmt, "badge", d.detected_format, "voices", d.voice_counts, "->", out)

# The README's animated demo: the four stills, 1100 px wide, 1.8 s each (needs Playwright + Pillow).
try:
    import base64, io, re
    from PIL import Image
    from playwright.sync_api import sync_playwright
except ImportError:
    print("skip crucible-demo.gif (needs playwright and Pillow)")
else:
    frames = []
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=os.environ.get("CHROMIUM", "/opt/pw-browsers/chromium"))
        for fmt in heads:
            txt = open(common.IMAGES + f"/crucible-{fmt.lower().replace('-', '')}.svg").read()
            w, h = map(float, re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', txt).groups())
            pg = b.new_page(viewport={"width": int(w) + 20, "height": int(h) + 20})
            pg.set_content('<html><body style="margin:0"><img src="data:image/svg+xml;base64,'
                           + base64.b64encode(txt.encode()).decode() + f'" width="{w}" height="{h}"></body></html>')
            pg.wait_for_timeout(300)
            png = pg.screenshot(clip={"x": 0, "y": 0, "width": w, "height": h})
            pg.close()
            im = Image.open(io.BytesIO(png)).convert("RGB")
            frames.append(im.resize((1100, round(1100 * im.height / im.width)), Image.LANCZOS))
        b.close()
    pal = [f.convert("P", palette=Image.ADAPTIVE, colors=128) for f in frames]
    pal[0].save(common.IMAGES + "/crucible-demo.gif", save_all=True, append_images=pal[1:],
                duration=1800, loop=0, optimize=True)
    print("wrote", common.IMAGES + "/crucible-demo.gif")
