"""Read a CM-32L / CM-64's rhythm setup (keys 24-108) and save it.

    python tools/cm_rhythm_dump.py                      # list MIDI ports
    python tools/cm_rhythm_dump.py "OUT NAME" "IN NAME" [out_stem]

Sends one Roland RQ1 for the rhythm setup temporary area (03 01 10, 85 keys x 4 bytes =
340 bytes; CM-64 manual p.31, 5-3-1) and waits up to 10 s for the DT1 answer, which a
CM-32L / CM-64 sends in one or more packets. Run it on a freshly powered-on unit (or a
freshly reset gearmulator) before any Voodoo load, so the answer is the factory map.

Writes <out_stem>.syx (the raw answer) and <out_stem>.json:
    {"24": [timbre, level, pan, reverb], ..., "108": [...]}
Default out_stem: cm_rhythm_factory. Upload both files.

The RQ1 it sends:  F0 41 10 16 11 03 01 10 00 02 54 16 F7
(any SysEx tool can send that instead; save what comes back as a .syx file).
"""
import json
import sys
import time

import mido

RQ1 = [0x41, 0x10, 0x16, 0x11, 0x03, 0x01, 0x10, 0x00, 0x02, 0x54]
FIRST_KEY, KEYS = 24, 85


def checksum(body):
    return (128 - sum(body) % 128) % 128


def addr_offset(a):
    """7-bit address of the rhythm setup area -> byte offset from 03 01 10."""
    return ((a[0] << 14) | (a[1] << 7) | a[2]) - ((0x03 << 14) | (0x01 << 7) | 0x10)


def main():
    if len(sys.argv) < 3:
        print("Outputs:")
        for n in mido.get_output_names():
            print("  ", n)
        print("Inputs:")
        for n in mido.get_input_names():
            print("  ", n)
        print(__doc__)
        return
    out_name, in_name = sys.argv[1], sys.argv[2]
    stem = sys.argv[3] if len(sys.argv) > 3 else "cm_rhythm_factory"
    rq = RQ1 + [checksum(RQ1[4:])]
    assert rq[-1] == 0x16
    data = [None] * (KEYS * 4)
    raw = []
    with mido.open_input(in_name) as inp, mido.open_output(out_name) as out:
        for _ in inp.iter_pending():
            pass
        out.send(mido.Message("sysex", data=rq))
        print("RQ1 sent:", " ".join(f"{b:02X}" for b in [0xF0] + rq + [0xF7]))
        t_end = time.time() + 10.0
        while time.time() < t_end and None in data:
            for m in inp.iter_pending():
                if m.type != "sysex":
                    continue
                d = list(m.data)
                raw.append(d)
                if len(d) < 9 or d[0] != 0x41 or d[2] != 0x16 or d[3] != 0x12:
                    print("  (other SysEx ignored)")
                    continue
                body = d[4:-1]
                if checksum(body) != d[-1]:
                    print("  checksum mismatch in a packet; keeping it anyway")
                off = addr_offset(d[4:7])
                for i, v in enumerate(d[7:-1]):
                    if 0 <= off + i < len(data):
                        data[off + i] = v
                print(f"  DT1 packet: offset {off}, {len(d) - 8} bytes")
            time.sleep(0.01)
    with open(stem + ".syx", "wb") as f:
        for d in raw:
            f.write(bytes([0xF0] + d + [0xF7]))
    missing = data.count(None)
    table = {}
    for k in range(KEYS):
        q = data[4 * k:4 * k + 4]
        if None not in q:
            table[str(FIRST_KEY + k)] = q
    with open(stem + ".json", "w") as f:
        json.dump(table, f, indent=1)
    print(f"Wrote {stem}.syx and {stem}.json: {len(table)} of {KEYS} keys"
          + (f" ({missing} bytes missing - try again, or check the unit's MIDI out)" if missing else ""))


if __name__ == "__main__":
    main()
