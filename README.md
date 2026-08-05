# Duality

**Intelligent Multi-Device MIDI Polyphony Router**

Duality routes MIDI notes across two or more sound modules / synthesizers to maximize effective polyphony, while keeping non-note messages synchronized across all devices.

It is designed for musicians and retro-computing enthusiasts who want to combine multiple hardware MIDI modules and treat them as one single higher-polyphony instrument.

<img width="1101" height="260" alt="Duality-v0 9 3" src="https://github.com/user-attachments/assets/45318bf1-3cfc-4802-b796-80b2cf055607" />

---

## Features

- Load-balancing or pure round-robin note assignment
- Chord preference (notes arriving close together stay on the same device when possible)
- Smart voice stealing (lowest velocity first, then oldest)
- Independent polyphony limit per device
- Full panic / All Notes Off handling
- Live status panel with:
  - Per-port level meters + peak hold
  - Channel activity & voice counts
  - Volume / Pan / Mod Wheel / Pitch Bend display
  - Drops, Steals, and Filtered message counters
- Redundant controller filtering (keeps devices in sync while reducing unnecessary MIDI traffic)
- Arbitrary number of output ports (default 2)
- Cross-platform (Windows, macOS, Linux)

---

## Requirements

- Python 3.8+
- [mido](https://mido.readthedocs.io/) + python-rtmidi
- [rich](https://rich.readthedocs.io/)

#### Install dependencies:

```bash
pip install mido[ports] python-rtmidi rich
```

- See [requirements.txt](requirements.txt)

---

## Usage

### List available MIDI ports
```bash
python duality.py --list
```

### Basic usage (two devices)
```bash
python duality.py --input "loopMIDI Port" --outs "MS40 A" "MS40 B"
```
### Three devices with different polyphony limits
```bash
python duality.py \
  --input "loopMIDI Port" \
  --outs "Module A" "Module B" "Module C" \
  --poly 28 32 24
```
### Custom chord detection window + silent mode
```bash
python duality.py --input "..." --outs "A" "B" --chord-ms 25 --no-status
```
### Show version
```bash
python duality.py --version
```
### Interactive mode
If you omit --outs, Duality will interactively ask you to choose two output ports.

---

## Command-line options

| Option | Description |
|--------|-------------|
| --input | MIDI input port name (or partial match) |
| --outs | One or more MIDI output port names (minimum 2) |
| --poly | Polyphony limit(s). One value applies to all ports, or one value per port |
| --mode | balance (default) or rr (pure round-robin) |
| --chord-ms | Chord detection window in milliseconds (default 30) |
| --no-status | Disable the live status panel |
| --list | List available MIDI ports and exit |
| --version | Show version |
| -h, --help | Show help message |

---

## Status Panel

While running, Duality shows a live panel with:

- Per-port activity meters and peak indicators
- Total / Peak voices and utilisation
- Drops (notes silently discarded), Steals (voice stealing events), and Filtered (redundant controllers suppressed)
- Per-channel voice counts, Volume, Pan, Mod Wheel, and Pitch Bend
- Last chord size and activity information

<img width="1079" height="260" alt="image" src="https://github.com/user-attachments/assets/96ca2cdb-c13f-4e34-a50d-7133e638b209" />

---

## Tips

- For best results, set --poly to the *real* available polyphony of each module (some patches use multiple voices internally).
- Use a virtual loopback port (e.g. loopMIDI on Windows, IAC on macOS) as the input so your DAW or sequencer can send to Duality.
- Press Ctrl+C to panic (All Notes Off) and exit cleanly.

---

## Licensing

This software is free for personal, educational, research, and other
non-commercial use.

Commercial use requires a separate license from the copyright holder.

Copyright © 2026 MIDIMan369. All rights reserved.

See [LICENSE](LICENSE) for full terms.
