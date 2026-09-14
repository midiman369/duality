# Duality

**Intelligent Multi-Device MIDI Polyphony Router**

Current development line: **v0.18.40** (`python duality.py --version`).

Duality routes MIDI notes across one or more sound modules so you can treat several hardware and soft synths as a single, higher-polyphony instrument. Non-note messages stay synchronized. Optional layers sit on top of that core:

| Layer | What it does |
|-------|----------------|
| **Router** | Load-balance or round-robin notes; chord grouping; voice steal |
| **Crucible** | Send the stream only to outputs tagged for that MIDI dialect |
| **Voodoo** | Super-Munt-style GM on real MT-32 / CM-32 hardware |
| **Anima** | Humanize + GS insertion EFX + foley + 8850 tone variations |
| **Alchemy** | Experimental GS↔XG rewrite — **broken; do not rely on it** |

Built for musicians and retro-computing folks (DOS soundtracks, Sound Canvas, XG, MT-32, Ketron/Solton, etc.).

<!-- IMAGE NEEDED: hero — current live status panel, ~120-col terminal, 4 GS ports + history -->
<!-- ![Duality live status](docs/images/status-hero.png) -->

**Screenshots below are from earlier development builds** (layout and feature set have moved on).

<img width="1080" height="260" alt="Earlier build – status panel" src="https://github.com/user-attachments/assets/38f339ec-0894-41b3-b933-a882c6dec397" />

<img width="1080" height="260" alt="Earlier build – meters / activity" src="https://github.com/user-attachments/assets/55dbf0c4-9be0-4747-8fae-65511ae5bcd0" />

<img width="1080" height="260" alt="Earlier build – channel rows" src="https://github.com/user-attachments/assets/56312654-1d04-429c-b382-35203fe7053d" />

---

## Features

### Polyphony routing
- Load-balancing by **utilization** (fair with mixed `--poly` limits) or pure **round-robin**
- Chord preference (notes arriving close together stay on the same device when possible)
- Smart voice stealing (lowest velocity first, then oldest)
- Independent polyphony limit per device
- Full panic / All Notes Off; **X** sends dialect resets to tagged outs and clears Anima locks

### Crucible (format-aware routing)
- Optional **output** tags: what each device can accept (`gs`, `xg`, `gm`, `gm2`, `mt32`, plus `gs+gm2`, …)
- **Input / stream format** (what the feed *is*): SysEx detect, `--input-format`, or hotkeys — not the same as output tags
- Affinity: notes and SysEx go to compatible ports
- Unknown input → GM-family ports only (**pure MT-32 excluded** until the stream is MT-32)
- No silent “send to all” when nothing matches
- `GM` → `gm` / `gm2`; `--crucible-gm-wide` also reaches `gs` / `xg`
- **Set** format (G/R/Y/M) vs **lock** (L): lock blocks SysEx override and idle clear
- `--strict-format-detection`: only System On / Reset SysEx may switch format
- SCPOP / SC-ext (model-45 or banner — not LCD animation text) + optional `--scpop`

### Voodoo (MT-32 GM)
- Roland **MT-TO-GM** (1993) or Sierra **KQ6** bank on `:mt32` / `:mt` / `:cm` outs
- Paced SysEx + input queue with elastic catch-up (does not dump the buffer)
- 1 / 2 / 3 unit maps; 4+ even units can use **pairs** (hotkey **P**)
- LA32 pan table (8 real positions, center split L1 / C)
- Auto when every out is MT-32 and the stream is not; exit on real MT-32 SysEx
- `--voodoo` at launch seeds MT-32 format so you can **L**ock it

### Anima (opt-in phrasing)
- Velocity humanize, expression / mod ramps, guitar strum (including “Hetfield” down-pick on dirt tones)
- **GS EFX**: one insertion per `:gs` port; guitars can pack two via OD1/OD2 + pan; file-driven EFX stays on its port
- **Foley**: shared high channel (usually 16) for 8850 SFX (fret, cut, chord stroke, slap, breath, …)
- **Tone variations**: seeded 8850 CC00 on capital bank 0/0 only; **file bank always wins**
- Game mode (`--anima-game` / **A** cycle): shorter idle reset + PC-burst EFX reroll
- Single output allowed when Anima is on

### Record + log
- `--record [DIR]` / hotkey **W**: IN + each OUT as type-1 SMF (conductor + Ch1–Ch16 + SysEx)
- Idle ~10 s closes a take and the next MIDI opens a new file
- `--log` / `--log-verbose`; **C** clears the log

### Live status panel
- Per-port meters + VU-style peak hold, Total / Peak / Util
- MIDI Channel / Voice Count / Vol / Pan / Mod / Pitch
- Drops, Steals, Filtered; activity pulse
- Rolling “Recent” history; format badge (`[GS]`, locked `[GS*]`)
- Human-readable GS / XG / MT-32 SysEx (resets, EFX, display text, …)

### Other
- Redundant CC filtering (devices stay in sync with less traffic)
- Per-port `--sync-delay` (negatives relative; all zeros = no queue)
- Dropped output ports: stay up and reconnect by name (does **not** re-program the synth)
- **Developed and tested on Windows.** MIDI I/O is portable via python-rtmidi (WinMM / CoreMIDI / ALSA). Mac and Linux should run; they are not part of the regular test pass. Please file issues if you try them.

---

## Requirements

- Python 3.8+
- [mido](https://mido.readthedocs.io/) + [python-rtmidi](https://pypi.org/project/python-rtmidi/)
- [rich](https://rich.readthedocs.io/)

```bash
pip install -r requirements.txt
```

or:

```bash
pip install mido[ports] python-rtmidi rich
```

Repo layout (runtime):

| File | Role |
|------|------|
| `duality.py` | Router, UI, Crucible, Anima, Voodoo, record |
| `tables_gs.py` | GS EFX / macros / Anima insertion palettes |
| `tables_xg.py` | XG types + Alchemy maps |
| `tables_anima.py` | GM/MT-32/Sierra categories + 8850 tone palettes |
| `tables_voodoo.py` / `voodoo_banks.py` | MT-TO-GM / KQ6 SysEx |

### Platforms

| | Windows | macOS | Linux |
|--|---------|-------|-------|
| Tested by the author | Yes | No | No |
| MIDI backend | WinMM | CoreMIDI | ALSA |
| Typical loopback | loopMIDI | IAC Driver | `snd-virmidi` / JACK |
| Hotkeys | `msvcrt` | cbreak stdin | cbreak stdin |

Unix hotkeys need a real TTY. Ctrl+C always panics.

---

## Usage

### List ports
```bash
python duality.py --list
```

### Two devices (classic)
```bash
python duality.py --input "loopMIDI Port" --outs "MS40 A" "MS40 B"
```

### Mixed polyphony
```bash
python duality.py \
  --input "loopMIDI Port" \
  --outs "Module A" "Module B" "Module C" \
  --poly 28 32 24
```

### Crucible + multi-capability tags
```bash
python duality.py --input "loopMIDI Port" --crucible --crucible-gm-wide \
  --outs \
    "Roland SC-8850 PART A:gs+gm2" \
    "Roland SC-8850 PART B:gs+gm2" \
    "Roland SC-8850 PART C:gm+gm2" \
    "yxg50:xg+gm2" \
    "MUNT:mt32"
```

On Windows, quote each `Name:tag` so the shell does not split on `:`.

### Four GS ports + Anima + record + log
```bash
python duality.py --input duality \
  --outs "SCVA:gs+gm2" "SCVA2:gs+gm2" "SCVA3:gs+gm2" "SCVA4:gs+gm2" \
  --poly 32 32 32 32 --crucible --anima --log --record
```

### Voodoo on two MT-32s (hardware GM)
```bash
python duality.py --input duality \
  --outs "MIDIMate 1:mt32" "MIDIMate 2:mt32" \
  --voodoo --voodoo-bank mtgm --sync-delay 0 80
```

### Sync delay (softsynth ~80 ms ahead of hardware)
```bash
python duality.py --input "loopMIDI Port" --crucible \
  --outs "SC PART A:gs+mt32" "MUNT:mt32" \
  --sync-delay 0 -80
```

Negatives are relative: the most-negative port becomes 0 ms; others shift later.

### SCPOP without model-45 SysEx
```bash
python duality.py --input "loopMIDI Port" --scpop --crucible \
  --outs "SC A:gs" "SC B:gs"
```

### Silent / version
```bash
python duality.py --input "..." --outs "A" "B" --chord-ms 25 --no-status
python duality.py --version
```

Omit `--outs` for interactive pick (2 ports by default; 1 allowed with `--alchemy` or `--anima`).

---

## Command-line options

| Option | Description |
|--------|-------------|
| `--input` | MIDI input port (partial name ok) |
| `--outs` | `Name` or `Name:tag` or `Name:tag+tag` (`gs`, `xg`, `gm`, `gm2`, `mt32`, `mt`, `cm`) |
| `--poly` | One limit for all, or one per port |
| `--sync-delay` | Per-port delay in ms. Negatives = relative. ±500 max. `0` = fast path |
| `--mode` | `balance` (default) or `rr` |
| `--chord-ms` | Chord window in ms (default 30) |
| `--crucible` | Format-aware routing |
| `--crucible-notes` | `affinity` (default) or `all` |
| `--crucible-gm-wide` | GM/GM2 also matches `gs` and `xg` |
| `--input-format` | Assume `gm` / `gm2` / `gs` / `xg` / `mt32` until SysEx says otherwise |
| `--strict-format-detection` | Only System On / Reset SysEx may switch format |
| `--scpop` | Force SCPOP note broadcast to format-matched ports |
| `--anima` | Phrasing + GS EFX + foley + tone variations |
| `--anima-game` | Anima game mode (implies `--anima`) |
| `--anima-efx-stable` | Same song → same EFX hash (no per-launch roll) |
| `--voodoo` | Load GM bank on MT-32 outs at start |
| `--voodoo-bank` | `mtgm` (default) or `kq6` |
| `--voodoo-layout` | `stripe` (default) or `pairs` |
| `--alchemy` | **BROKEN/EXPERIMENTAL** GS↔XG rewrite; allows one output |
| `--alchemy-all` | Alchemy fan-out to all GS/XG outs (implies `--alchemy`) |
| `--record [DIR]` | Write IN/OUT SMFs (default dir `.`). Hotkey **W** |
| `--log [PATH]` | Status / bank / port health (default `duality.log`) |
| `--log-verbose [PATH]` | All CCs etc. Wins if both log flags are set |
| `--no-status` | No live panel |
| `--list` | List ports and exit |
| `--version` | Version |
| `-h, --help` | Help |

---

## Hotkeys

Format keys set the **input / stream format** for Crucible. They do **not** change `--outs` tags.

| Key | Action |
|-----|--------|
| **F** | Clear input format (and unlock) |
| **L** | Lock / unlock input format |
| **G** | Input GM; again → GM2 |
| **R** | Input GS |
| **Y** | Input XG |
| **M** | Input MT-32; again while MT-32 → Voodoo on/off |
| **V** | Cycle Voodoo bank (`mtgm` / `kq6`) |
| **P** | Voodoo layout stripe ↔ pairs (4+ even MT-32 units) |
| **A** | Anima off → normal → game → off |
| **B** | Balance ↔ round-robin |
| **X** | Panic + dialect resets + Anima session reset (not format lock) |
| **W** | Start / stop recording |
| **C** | Clear log file |
| **Q** | Panic and quit |
| **Ctrl+C** | Panic and quit |

---

## Status panel

<!-- IMAGE NEEDED: current full panel (header + meters + channel grid + Recent) -->
<!-- ![Status panel](docs/images/status-panel.png) -->

<!-- IMAGE NEEDED: short GIF — format badge / Crucible jumping GS vs XG -->
<!-- ![Crucible demo](docs/images/crucible-demo.gif) -->

<!-- IMAGE NEEDED: Anima — EFX + foley lines in Recent, Cut/Stroke on ch16 -->
<!-- ![Anima foley](docs/images/anima-foley.png) -->

While running:

- Per-port meters and peak markers
- Total / Peak / Util; Drops, Steals, Filtered
- Per-channel voices, Volume, Pan, Mod, Pitch
- Last chord, last activity, status + rolling history
- Format badge (`[GS]`, `[GS*]`), Crucible / Voodoo / Anima / SCPOP
- Activity pulse and decoded SysEx

**Older panel capture** (prior UI generation):

<img width="1086" height="269" alt="Earlier build – panel detail" src="https://github.com/user-attachments/assets/767d3c82-0850-48d3-b060-7df83c8da3c7" />

Wide terminals (≥ ~118 columns) get the side **Recent** panel automatically.

---

## Anima notes

Anima is off unless `--anima` / `--anima-game` or hotkey **A**.

**GS EFX** — one insert per tagged GS unit. Priority roughly: dirty guitar → clean/acoustic guitar → lead / shakuhachi → organ → bass → … File-programmed EFX stays on that port; Anima may use *other* units for extra inserts. OD1/OD2 can split two dirt guitars by pan when they are hard-left / hard-right.

**Foley** — one shared SFX channel per GS synth (usually 16). 8850 programming is **CC0 = variation (the list “CC00” column), CC32 = 0, PC 121 or 122**. Gesture after a short hold: fret / cut / chord stroke / steel slide; bass slap vs slide; wind click vs breath; brass noise. Phrase gap keeps it from firing every pick. Cut Noise is velocity-boosted. Families take turns on the same lane.

**Tone variations** — if the file sends capital bank `0/0`, Anima may pick another 8850 CC00 for that PC (seeded, sticky until PC / **X** / idle). Palettes are mostly **000 or 008** (plus **001** on Clean Gt and Fingered Bass). If the file already set CC0 or CC32, Duality does not touch it. Capitals always emit CC0=0 so a previous 1024/2048 bank cannot stick (many editors show bank = CC0 × 128).

**Game mode** — shorter idle reset and EFX reroll on a burst of program changes (DOS-era cue changes).

<!-- IMAGE NEEDED: 88emu / SC-8850 part screen showing 8850 map + Gt.Cut Noise -->
<!-- ![8850 foley map](docs/images/foley-8850-map.png) -->

---

## Voodoo notes

Think “Super Munt GM,” but on hardware. `--voodoo` or **M** while the input format is already MT-32.

- Init is paced on purpose (MT-32 buffer). Several units in parallel still share the host MIDI interface, so wall-clock time grows with unit count.
- Incoming MIDI is queued during load, then caught up with a speed ceiling — not dumped.
- Real MT-32 SysEx in the stream drops Voodoo and returns to normal MT-32 routing.

---

## Recordings

`--record` or **W** writes:

- `IN-<input>-<format>-<timestamp>.mid`
- `OUT-<port>-<tags>-<timestamp>.mid` per output

Type-1 SMF: tempo track, **Ch1–Ch16**, plus a SysEx track. Includes Duality’s own bank/PC/EFX/foley, so an OUT file is “what the synth heard.”

---

## Alchemy (BROKEN / EXPERIMENTAL)

`--alchemy` / `--alchemy-all` may rewrite GS↔XG SysEx and some PCs. Mapping is incomplete and effect translation is unreliable. Same-dialect traffic (XG → `:xg`) should pass through. Use Crucible + Anima + Voodoo instead unless you are debugging conversion.

---

## Tips

- Set `--poly` to each module’s **real** voices (multi-osc patches cost more than 1).
- **Balance** stays fair when limits differ (32 vs 96).
- Feed Duality from a loopback (loopMIDI, IAC, ALSA virtual ports).
- Tag multi-standard modules (`gs+gm2`) so a GM2 lock does not match nothing.
- `--sync-delay` for USB vs softsynth skew; leave `0` when unused.
- After a synth restart, Duality reconnects the port but does **not** re-send banks — play a reset or hit **X**.

### Duality looks active but my synth is silent

WinMM + loopMIDI ownership is fragile. Try:

1. Quit Duality (**Q** or Ctrl+C).
2. Quit the player if it was open.
3. Restart softsynths (or power-cycle hardware) so they re-open the **input** side of the cable.
4. Start Duality, then the player.

Cold start: **loopMIDI → softsynths → Duality → player**.

With `--log`, watch `PORT` lines. Session end logs last successful send age per out.

---

## Licensing

This software is free for personal, educational, research, and other non-commercial use.

Commercial use requires a separate license from the copyright holder.

Copyright © 2026 MIDIMan369. All rights reserved.

See [LICENSE](LICENSE) for full terms.
