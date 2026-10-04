"""CM-64 outs (0.19.053), no song.

  1. tags: "cm64" and "cm-64" parse to cm64 and show as CM-64; cm32 still parses
  2. routing: an MT-32 stream on two :mt32 outs and a :cm64 out spreads ch2-10 over all three;
     ch11-16 (the PCM half) go to the CM-64 only
  3. halves: on one :cm64 out (--poly 32) 20 quiet LA notes and 31 loud PCM notes all sound;
     the 32nd PCM note steals a PCM note (not a quieter LA one), and LA notes up to 32 steal
     nothing
  4. a :cm32-only out gets an MT-32 stream under Crucible; a :gs out does not
  5. X reset sends the MT-32 reset (not GM System On) to :cm32 and :cm64 outs
  6. Voodoo: the CM-64 gets its PCM part channels set OFF (52 00 0A = 16 x 6) at load, the
     MT-32 does not; leaving Voodoo sets them back to ch11-16
  7. pan: in Voodoo, CC10 on CM-64 ch2 is mapped to the CM-32L table, CC10 on ch11 is left as is
"""
import sys
import time as _time
import common  # noqa: F401
import mido

CLOCK = [1000.0]
_time.monotonic = lambda: CLOCK[0]
_time.time = lambda: CLOCK[0]
REC = []


class FakeOut:
    def __init__(self, i): self.idx = i; self.name = f"P{i+1}"; self.closed = False
    def send(self, m): REC.append((CLOCK[0] - 1000.0, self.idx, m))
    def close(self): pass
    reset = panic = close


class FakeIn:
    name = "in"; closed = False
    def poll(self): return None
    def iter_pending(self): return iter(())
    def close(self): pass


import duality as D
D.mido.open_output = lambda n, *a, **k: FakeOut(int(n[1:]) - 1)
D.mido.open_input = lambda *a, **k: FakeIn()
fails = []


def fresh(specs, poly=32, fmt="mt32"):
    REC.clear()
    CLOCK[0] = 1000.0
    tags = [D.parse_out_spec(f"P{i+1}:{s}")[1] for i, s in enumerate(specs)]
    return D.Duality("in", [f"P{i+1}" for i in range(len(specs))], show_status=False,
                     out_formats=tags, crucible=True, input_format=fmt,
                     poly_limits=[poly] * len(specs))


def note(d, ch, n, v=100):
    CLOCK[0] += 0.05
    d.process(mido.Message("note_on", channel=ch, note=n, velocity=v))


def note_ports(ch):
    return {p for _t, p, m in REC if m.type == "note_on" and m.channel == ch and m.velocity > 0}


# 1. tags
for spec in ("U:cm64", "U:cm-64", "U:CM-64"):
    if D.parse_out_spec(spec)[1] != frozenset({"cm64"}):
        fails.append(f"1: {spec} parsed to {D.parse_out_spec(spec)[1]}")
if D.parse_out_spec("U:cm32")[1] != frozenset({"cm32"}):
    fails.append("1: cm32 no longer parses")
if D.format_tags_label(frozenset({"cm64"})) != "CM-64":
    fails.append(f"1: cm64 label {D.format_tags_label(frozenset({'cm64'}))!r}")

# 2. routing
d = fresh(["mt32", "mt32", "cm64"])
for i in range(36):
    note(d, 1 + i % 9, 40 + i)
la = set().union(*(note_ports(c) for c in range(1, 10)))
if la != {0, 1, 2}:
    fails.append(f"2: ch2-10 reached ports {sorted(la)}, want all three")
for ch in range(10, 16):
    note(d, ch, 60)
    note(d, ch, 64)
    if note_ports(ch) != {2}:
        fails.append(f"2: ch{ch+1} reached ports {sorted(note_ports(ch))}, want only the CM-64")

# 3. halves
d = fresh(["cm64"])
for i in range(20):
    note(d, 1, 30 + i, v=10)            # quiet LA notes
for i in range(31):
    note(d, 10 + i % 6, 40 + i, v=100)  # loud PCM notes
if d.steal_count or len(d.active) != 51:
    fails.append(f"3: 20 LA + 31 PCM notes: steals {d.steal_count}, active {len(d.active)}, want 0 / 51")
note(d, 10, 90, v=100)
la_left = sum(1 for (c, _n) in d.active if c not in D.CM64_PCM_CHANNELS)
pcm_left = sum(1 for (c, _n) in d.active if c in D.CM64_PCM_CHANNELS)
if d.steal_count != 1 or la_left != 20 or pcm_left != 31:
    fails.append(f"3: 32nd PCM note: steals {d.steal_count}, LA {la_left}, PCM {pcm_left}, want 1 / 20 / 31")
for i in range(12):
    note(d, 2, 60 + i, v=50)
if d.steal_count != 1:
    fails.append(f"3: LA notes 21-32 stole {d.steal_count - 1}, want 0")
if d._port_voices(0, 1) != (32, 32) or d._port_voices(0, 11) != (31, D.CM64_PCM_POLY):
    fails.append(f"3: half voices LA {d._port_voices(0, 1)}, PCM {d._port_voices(0, 11)}")

# 4. cm32 under Crucible
d = fresh(["gs", "cm32"])
for i in range(6):
    note(d, 1, 50 + i)
if note_ports(1) != {1}:
    fails.append(f"4: MT-32 stream reached ports {sorted(note_ports(1))}, want only the CM-32L")

# 5. X reset
d = fresh(["gs", "cm32", "cm64"])
REC.clear()
d._send_format_resets("test")
for p in (1, 2):
    sx = [list(m.data) for _t, q, m in REC if q == p and m.type == "sysex"]
    if not any(s[:5] == [0x41, 0x10, 0x16, 0x12, 0x7F] for s in sx) or [0x7E, 0x7F, 0x09, 0x01] in sx:
        fails.append(f"5: port{p+1} reset sysex {sx}")

# 6. Voodoo
d = fresh(["mt32", "cm64"], fmt="gm")
d._voodoo_begin("test")
off = bytes(D._mt32_dt1(D.CM64_PCM_RX, [16] * 6))
hits = [ports for item in d._voodoo_send_list if isinstance(item, tuple)
        for payload, ports in [item] if bytes(payload) == off]
if hits != [[1]]:
    fails.append(f"6: PCM-off steps {hits}, want one to port2")
# run the paced load to the end
for _ in range(20000):
    if not d.voodoo_loading:
        break
    CLOCK[0] += 0.5
    d._voodoo_tick()
if not d.voodoo_active:
    fails.append("6: Voodoo did not finish loading")
sent_off = [p for _t, p, m in REC if m.type == "sysex" and bytes(m.data) == off]
if sent_off != [1]:
    fails.append(f"6: PCM-off sent to {sent_off}, want [port2]")

# 7. pan (Voodoo active: GM pan is mapped onto the LA table)
m = d._apply_mt32_pan_invert(1, mido.Message("control_change", channel=1, control=10, value=0))
if m.value not in D.CM32_PAN_POSITIONS:
    fails.append(f"7: CM-64 ch2 pan 0 -> {m.value}, want a CM-32L table value")
m = d._apply_mt32_pan_invert(1, mido.Message("control_change", channel=10, control=10, value=20))
if m.value != 20:
    fails.append(f"7: CM-64 ch11 pan 20 -> {m.value}, want 20 (PCM half pans continuously)")

REC.clear()
d._voodoo_exit("test")
on = bytes(D._mt32_dt1(D.CM64_PCM_RX, list(range(10, 16))))
sent_on = [p for _t, p, m in REC if m.type == "sysex" and bytes(m.data) == on]
if sent_on != [1]:
    fails.append(f"6: PCM channels restored on {sent_on}, want [port2]")

if fails:
    print("FAILS")
    for f in fails:
        print("   " + f)
    sys.exit(1)
print("PASS")
