"""CM-64 PCM half under Voodoo (0.19.055), no song.

  1. pool, three CM-64s: each unit gets its PCM reserve (6,5,5,5,5,5) and six PCM receive
     channels, none of them its own LA channels or ch10
  2. a GM piano (tables_cm64 "pcm") claims a part on the unit that owns its channel on LA:
     PC A.PIANO 1 and the controllers go to the part's channel, its notes play there and
     never on LA; CC10 is sent as is (the PCM half pans continuously)
  3. a square lead ("la") plays on its LA owner as before
  4. a program change to "la" with a note held: the note-off still reaches the PCM part,
     the next note plays on LA
  5. partials: 16 notes of A.PIANO 1 (2 partials) on one CM-64 steal one note there
  6. layer: a "layer" program at LA 50% / PCM 80% plays on both halves; CC7 100 reaches LA
     as 50 and the PCM part as 80; leaving the layer puts the LA volume back
  7. one MT-32 + one CM-64: six parts; a seventh PCM channel plays on LA until a part's
     owner has rested 10 s, then takes that part
  8. leaving Voodoo silences the parts and gives them back ch11-16
  9. seats, one CM-64 (MT-TO-GM: LA parts on ch1-8): PCM parts on ch9 and 11-15, ch16 has
     none; a seat plays the nearest PCM tone of any program (square lead -> SAX 1), ch1 stays LA
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
REAL_PICK = D.cm64_gm_pick


def fresh(specs):
    REC.clear()
    CLOCK[0] = 1000.0
    tags = [D.parse_out_spec(f"P{i+1}:{s}")[1] for i, s in enumerate(specs)]
    d = D.Duality("in", [f"P{i+1}" for i in range(len(specs))], show_status=False,
                  out_formats=tags, crucible=True, input_format="gm", poly_limits=[32] * len(specs))
    d._voodoo_begin("test")
    for _ in range(20000):
        if not d.voodoo_loading:
            break
        CLOCK[0] += 0.5
        d._voodoo_tick()
    if not d.voodoo_active:
        fails.append(f"{specs}: Voodoo did not finish loading")
    REC.clear()
    return d


def send(d, m):
    CLOCK[0] += 0.05
    d.process(m)


def on(d, ch, n, v=100):
    send(d, mido.Message("note_on", channel=ch, note=n, velocity=v))


def off(d, ch, n):
    send(d, mido.Message("note_off", channel=ch, note=n, velocity=0))


def pc(d, ch, p):
    send(d, mido.Message("program_change", channel=ch, program=p))


def cc(d, ch, c, v):
    send(d, mido.Message("control_change", channel=ch, control=c, value=v))


def sent(kind, port=None, ch=None, **kw):
    out = []
    for _t, p, m in REC:
        if m.type != kind or (port is not None and p != port) or (ch is not None and m.channel != ch):
            continue
        if all(getattr(m, k) == v for k, v in kw.items()):
            out.append((p, m))
    return out


def part_of(d, ch):
    return d._cm64v_owned(ch)


# 1. pool placement
d = fresh(["cm64", "cm64", "cm64"])
plan = D._voodoo_channel_plan(3, "stripe")
for u in range(3):
    parts = [p for p in d._cm64v_parts if p["port"] == u]
    rx = [p["rx"] for p in parts]
    la = {c - 1 for c in plan[u]} | {9}
    if len(rx) != 6 or set(rx) & la:
        fails.append(f"1: unit {u + 1} PCM rx {rx} vs LA {sorted(la)}")
if d._cm64v_seats:
    fails.append("1: three units planned as seats")

# 2. piano on PCM
pc(d, 0, 0)
part = part_of(d, 0)
if part is None:
    fails.append("2: GM piano claimed no PCM part")
else:
    if part["port"] not in d._voodoo_ch_owners[0]:
        fails.append(f"2: piano part on port{part['port'] + 1}, LA owners {d._voodoo_ch_owners[0]}")
    if not sent("program_change", part["port"], part["rx"], program=0):
        fails.append("2: no PC A.PIANO 1 on the part's channel")
    REC.clear()
    on(d, 0, 60)
    cc(d, 0, 10, 20)
    if not sent("note_on", part["port"], part["rx"], note=60):
        fails.append("2: piano note not on the PCM part")
    if sent("note_on", ch=0):
        fails.append(f"2: piano note also on LA: {sent('note_on', ch=0)}")
    if not sent("control_change", part["port"], part["rx"], control=10, value=20):
        fails.append("2: CC10 20 not passed as is to the PCM part")
    off(d, 0, 60)

# 3. square lead on LA
pc(d, 1, 80)
REC.clear()
on(d, 1, 72)
if part_of(d, 1) is not None or not sent("note_on", ch=1, note=72):
    fails.append(f"3: square lead: part {part_of(d, 1)}, LA notes {sent('note_on', ch=1)}")
off(d, 1, 72)

# 4. PC to "la" with a note held
on(d, 0, 64)
pc(d, 0, 80)
REC.clear()
off(d, 0, 64)
if part is not None and not sent("note_off", part["port"], part["rx"], note=64):
    fails.append("4: held piano note-off did not reach the PCM part")
REC.clear()
on(d, 0, 65)
if not sent("note_on", ch=0, note=65) or part_of(d, 0) is not None:
    fails.append("4: after PC to a lead the next note is not on LA")
off(d, 0, 65)

# 5. partials
pc(d, 0, 0)
part = part_of(d, 0)
before = d.steal_count
for i in range(16):
    on(d, 0, 40 + i)
if d.steal_count - before != 1:
    fails.append(f"5: 16 A.PIANO 1 notes stole {d.steal_count - before}, want 1")
for i in range(16):
    off(d, 0, 40 + i)

# 6. layer
D.cm64_gm_pick = lambda p: ("layer", 33, 50, 80) if p == 48 else REAL_PICK(p)
REC.clear()
pc(d, 2, 48)
part = part_of(d, 2)
la_ports = d._voodoo_ch_owners[2]
if not any(sent("control_change", p, 2, control=7, value=50) for p in la_ports):
    fails.append("6: layer LA volume not set to 50")
REC.clear()
on(d, 2, 60)
cc(d, 2, 7, 100)
if part is None or not sent("note_on", part["port"], part["rx"], note=60) or not sent("note_on", ch=2, note=60):
    fails.append("6: layer note not on both halves")
if part is not None and not sent("control_change", part["port"], part["rx"], control=7, value=80):
    fails.append("6: PCM half of the layer did not get CC7 80")
if not any(sent("control_change", p, 2, control=7, value=50) for p in la_ports):
    fails.append("6: LA half of the layer did not get CC7 50")
off(d, 2, 60)
REC.clear()
pc(d, 2, 80)
if not any(sent("control_change", p, 2, control=7, value=100) for p in la_ports):
    fails.append("6: leaving the layer did not put LA CC7 back to 100")
D.cm64_gm_pick = REAL_PICK

# 8. exit
REC.clear()
d._voodoo_exit("test")
if len({(p, m.channel) for p, m in sent("control_change", control=123)}) < 18:
    fails.append("8: exit did not send all-notes-off to the PCM parts")
restore = bytes(D._mt32_dt1(D.CM64_PCM_RX, list(range(10, 16))))
if sorted(p for _t, p, m in REC if m.type == "sysex" and bytes(m.data) == restore) != [0, 1, 2]:
    fails.append("8: PCM channels not restored on every CM-64")

# 7. one MT-32 + one CM-64
d = fresh(["mt32", "cm64"])
pcm_progs = [0, 4, 24, 25, 32, 33, 48]          # pianos, guitars, basses, strings: all "pcm"
chans = [0, 1, 2, 3, 4, 5, 6]
for c, p in zip(chans, pcm_progs):
    pc(d, c, p)
owned = [c for c in chans if part_of(d, c) is not None]
if len(owned) != 6 or part_of(d, 6) is not None:
    fails.append(f"7: parts owned by {owned}, want ch1-6")
REC.clear()
on(d, 6, 60)
if not sent("note_on", ch=6, note=60) or part_of(d, 6) is not None:
    fails.append("7: seventh PCM channel did not play on LA with the pool full")
off(d, 6, 60)
for c in chans[1:6]:
    on(d, c, 50)
    off(d, c, 50)
CLOCK[0] += 3.0
on(d, 6, 61)                                   # nobody rested 10 s yet
off(d, 6, 61)
if part_of(d, 6) is not None:
    fails.append("7: a part was taken before its owner rested 10 s")
CLOCK[0] += 11.0
for c in chans[1:6]:
    on(d, c, 50)
    off(d, c, 50)
REC.clear()
on(d, 6, 62)
p6 = part_of(d, 6)
if p6 is None or not sent("note_on", p6["port"], p6["rx"], note=62):
    fails.append("7: seventh channel did not take ch1's rested part")
elif part_of(d, 0) is not None:
    fails.append("7: ch1 still owns a part after it was taken")
off(d, 6, 62)
d._voodoo_exit("test")

# 9. seats on one CM-64
d = fresh(["cm64"])
rx = sorted(p["rx"] for p in d._cm64v_parts)
if not d._cm64v_seats or rx != [8, 10, 11, 12, 13, 14]:
    fails.append(f"9: seats {d._cm64v_seats} on {rx}, want ch9 and 11-15")
pc(d, 8, 80)                                   # square lead on a seat
REC.clear()
on(d, 8, 70)
sax = D.CM64_PCM_TONES.index("SAX 1")
if not sent("note_on", 0, 8, note=70):
    fails.append("9: seat ch9 note did not play on its PCM part")
seat = part_of(d, 8)
if seat is None or seat["prog"] != sax:
    fails.append(f"9: seat ch9 tone {seat and seat['prog']}, want SAX 1 ({sax})")
off(d, 8, 70)
REC.clear()
on(d, 0, 60)
if not sent("note_on", 0, 0, note=60) or part_of(d, 0) is not None:
    fails.append("9: ch1 does not play on LA on one unit")
off(d, 0, 60)
REC.clear()
on(d, 15, 60)
if part_of(d, 15) is not None:
    fails.append("9: ch16 has a seat")

if fails:
    print("FAILS")
    for f in fails:
        print("   " + f)
    sys.exit(1)
print("PASS")
