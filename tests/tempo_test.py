"""Beat tracker: exact on MIDI clock; note onsets land on the tempo or a musical relative."""
import sys, random, types
import common
import mido
import duality as D


def fresh():
    return types.SimpleNamespace(_tempo_clock_t=0.0, _tempo_clock_iv=0.0, _tempo_onsets=[],
                                 _tempo_beat=0.0, _tempo_beat_t=0.0)


fails = []
for bpm in (72, 96, 120, 140, 174):
    b = 60.0 / bpm
    o = fresh(); t = 0.0; random.seed(bpm)
    while t < 11:
        for k, hit in enumerate([1, 0, 1, 1, 0, 1, 1, 0]):   # syncopated 8ths
            if hit:
                D.Duality._tempo_feed(o, mido.Message("note_on", note=60, velocity=90),
                                      t + k * b / 2 + random.uniform(-0.01, 0.01))
        t += 4 * b
    D.time.monotonic = lambda t=t: t
    est = D.Duality._anima_beat_sec(o)
    o2 = fresh(); tc = 0.0
    for _ in range(200):
        D.Duality._tempo_feed(o2, mido.Message("clock"), tc); tc += b / 24
    D.time.monotonic = lambda tc=tc: tc
    clk = 60.0 / D.Duality._anima_beat_sec(o2)
    on = 60.0 / est if est else 0.0
    ratio = on / bpm if bpm else 0
    musical = any(abs(ratio - r) < 0.03 for r in (0.5, 2 / 3, 1.0, 1.5, 2.0))
    print(f"{bpm:4d} BPM  onsets → {on:6.1f}  clock → {clk:6.1f}")
    if abs(clk - bpm) > 0.5:
        fails.append(f"clock {bpm} → {clk:.1f}")
    if not musical:
        fails.append(f"onsets {bpm} → {on:.1f} (not a musical relative)")
print("FAILS:" if fails else "PASS")
for f in fails:
    print("  ", f)
sys.exit(1 if fails else 0)
