import sys; import common  # repo on sys.path, MIDI paths
import duality as D
from tables_gs import ANIMA_EFX_PRIORITY, ANIMA_EFX_GS
from rich.console import Console
from wt_svg import save_wt
from rich.table import Table
from rich import box
SFX = {(120, 0): "Gt.FretNoise", (120, 1): "Gt.Cut Noise", (120, 2): "String Slap",
       (120, 3): "Gt.CutNoise 2", (120, 4): "Dist.CutNoise", (120, 5): "Bass Slide",
       (120, 6): "Pick Scrape", (121, 0): "Breath Noise", (121, 1): "Fl.Key Click"}
NOTE = lambda n: "C C#D D#E F F#G G#A A#B ".replace(" ", "")  # unused
names = "C C# D D# E F F# G G# A A# B".split()
nn = lambda n: f"{names[n % 12]}{n // 12 - 1}"
def save(tbl, path, title, width=110):
    c = Console(width=width, record=True, force_terminal=True, color_system="truecolor", file=open("/dev/null", "w"))
    c.print(tbl)
    save_wt(c, path)
t = Table(title="Anima foley — SC-8850 SFX per family (shared foley channel)", box=box.ROUNDED,
          title_style="bold magenta", header_style="bold cyan")
for col in ("Family", "PC", "Var", "8850 SFX tone", "Keys"):
    t.add_column(col)
for fam, (pc, lsb, keys) in D.ANIMA_FOLEY_SPEC.items():
    if pc == 121 and lsb not in (0, 1):
        lsb = 0
    t.add_row(fam, str(pc + 1), str(lsb), SFX.get((pc, lsb), "?"), " ".join(nn(k) for k in keys))
save(t, common.IMAGES + "/foley-8850-map.svg", f"Duality {D.VERSION} — foley map")
e = Table(title="Anima GS insert EFX — family priority (top wins a unit) and palette (SC-8850 #)",
          box=box.ROUNDED, title_style="bold magenta", header_style="bold cyan")
e.add_column("#", justify="right"); e.add_column("Family", style="bold")
e.add_column("Favoured", style="yellow"); e.add_column("Normal"); e.add_column("Less often", style="bright_black")
from tables_gs import GS_EFX_LIST
NUM = {(m, l): n for n, _nm, m, l in GS_EFX_LIST}
def mult(w):
    """Table weight (2 x the picker's multiplier) as the picker's label: x2, x3 ... x1/2, x1/3 ..."""
    m = float(w) / 2.0
    return f"×{m:g}" if m >= 1 else f"×1/{round(1 / m)}"
def fmt(rows, show):
    return ", ".join(f"{r[2]} {mult(r[3])}" if show else r[2] for r in rows) or "—"
for i, fam in enumerate(ANIMA_EFX_PRIORITY, 1):
    rows = ANIMA_EFX_GS.get(fam, [])
    w = lambda r: float(r[3]) if len(r) > 3 else 2.0
    e.add_row(str(i), fam, fmt([r for r in rows if w(r) > 2], True), fmt([r for r in rows if w(r) == 2], False),
              fmt([r for r in rows if w(r) < 2], True))
save(e, common.IMAGES + "/anima-efx-priority.svg", f"Duality {D.VERSION} — EFX priority", width=200)

from tables_gs import (ANIMA_EFX_PAN_PARAMS, ANIMA_EFX_DELAY, ANIMA_EFX_PITCH, ANIMA_EFX_GATE_TYPE,
                       ANIMA_EFX_DIRT_LEVEL, ANIMA_EFX_WAH, ANIMA_EFX_ROTARY, GS_EFX_TYPES,
                       ANIMA_EFX_BALANCE_TYPES, ANIMA_EFX_TYPE_SET, ANIMA_SEAT_BALANCE)
s2 = Table(title="Anima insert shaping — what Duality sets after it picks a type", box=box.ROUNDED,
           title_style="bold magenta", header_style="bold cyan")
s2.add_column("Shaping", style="bold"); s2.add_column("Insert types"); s2.add_column("Rule")
def names(keys):
    return ", ".join(GS_EFX_TYPES[k] for k in sorted(keys, key=lambda k: NUM.get(k, 99)))
s2.add_row("Pan follows file", names(ANIMA_EFX_PAN_PARAMS),
           "Output at the player's CC10 when off centre; pairs ±24 around it")
s2.add_row("Delay time = beat", names(k for k, v in ANIMA_EFX_DELAY.items() if v["times"]),
           "MIDI clock, else note onsets; taps keep their rhythm; set again when quiet")
s2.add_row("Feedback ≤ 50 %", names(ANIMA_EFX_DELAY), "+30 %, held families +16 %")
s2.add_row("Pitch interval", names(ANIMA_EFX_PITCH), "Doubler, octave or fifth by family + seed")
s2.add_row("Gate type", names(ANIMA_EFX_GATE_TYPE), "Normal, Reverse, Sweep 1 or Sweep 2 by seed")
s2.add_row("Level follows fade", names(ANIMA_EFX_DIRT_LEVEL), "Below 75 % of the file level, Level goes to 0 with it")
s2.add_row("Fixed settings", names(ANIMA_EFX_TYPE_SET),
           "Overdrive Level 80; GTR Multi 2 drive = Distortion; GTR Multi 3 Level 127, wah Peak 80, players' CC7 ×1.2; "
           "OD1/OD2 both Distortion, OD1 Level 80")
s2.add_row("Wet / dry (Balance)", names(ANIMA_EFX_BALANCE_TYPES),
           "Tone Palettes EFX level: drier ×0.6 / ×0.35, wetter 40 % / 65 % to full wet; driest part wins; "
           "seat Space D at D>50E")
s2.add_row("CC16 control", names(set(ANIMA_EFX_WAH) | set(ANIMA_EFX_ROTARY)),
           "Wah follows the player (lead / rhythm Peak), rotary flips on held chords; other types 0 % depth")
save(s2, common.IMAGES + "/anima-efx-shaping.svg", f"Duality {D.VERSION} — EFX shaping", width=170)
print("ok")
