# Duality

**Intelligent Multi-Device MIDI Polyphony Router**

Duality routes MIDI notes across two or more sound modules / synthesizers to maximize effective polyphony, while keeping non-note messages synchronized across all devices.

It is designed for musicians and retro-computing enthusiasts who want to combine multiple hardware MIDI modules and treat them as one higher-polyphony instrument.

<img width="1080" height="260" alt="20260806-0555-53 2798323" src="https://github.com/user-attachments/assets/38f339ec-0894-41b3-b933-a882c6dec397" />

<img width="1080" height="260" alt="20260806-0550-42 8483259" src="https://github.com/user-attachments/assets/55dbf0c4-9be0-4747-8fae-65511ae5bcd0" />

<img width="1080" height="260" alt="20260806-0603-15 4788434" src="https://github.com/user-attachments/assets/56312654-1d04-429c-b382-35203fe7053d" />

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
  - Rolling recent-status history
  - Format badge (GM / GM2 / GS / XG / MT-32)
- SysEx recognition with human-readable status messages:
  - **GS** – Reset, Reverb/Chorus macros, EFX/MFX types, part EFX on/off, display text
  - **XG** – System On, Reverb / Chorus / Variation / Insertion effect types, display text
  - **MT-32** – Display text, reverb mode/time/level, master volume & tune
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
If you omit `--outs`, Duality will interactively ask you to choose two output ports.

---

## Command-line options

| Option | Description |
|--------|-------------|
| `--input` | MIDI input port name (or partial match) |
| `--outs` | One or more MIDI output port names (minimum 2) |
| `--poly` | Polyphony limit(s). One value applies to all ports, or one value per port |
| `--mode` | `balance` (default) or `rr` (pure round-robin) |
| `--chord-ms` | Chord detection window in milliseconds (default 30) |
| `--no-status` | Disable the live status panel |
| `--list` | List available MIDI ports and exit |
| `--version` | Show version |
| `-h, --help` | Show help message |

---

## Status Panel

While running, Duality shows a live panel with:

- Per-port activity meters and peak indicators
- Total / Peak voices and utilisation
- Drops (notes silently discarded), Steals (voice stealing events), and Filtered (redundant controllers suppressed)
- Per-channel voice counts, Volume, Pan, Mod Wheel, and Pitch Bend
- Last chord size and activity information
- Format badge when GM / GS / XG / MT-32 SysEx is detected
- Human-readable SysEx status (effects, resets, display text, etc.) plus a short rolling history

<img width="1086" height="269" alt="image" src="https://github.com/user-attachments/assets/767d3c82-0850-48d3-b060-7df83c8da3c7" />

---

## Tips

- For best results, set `--poly` to the *real* available polyphony of each module (some patches use multiple voices internally).
- Use a virtual loopback port (e.g. loopMIDI on Windows, IAC on macOS) as the input so your DAW or sequencer can send to Duality.
- Press Ctrl+C to panic (All Notes Off) and exit cleanly.
- Wide terminals (≥ ~118 columns) get the side-by-side status history panel automatically.

---

## Licensing

This software is free for personal, educational, research, and other
non-commercial use.

Commercial use requires a separate license from the copyright holder.

Copyright © 2026 MIDIMan369. All rights reserved.

See [LICENSE](LICENSE) for full terms.
