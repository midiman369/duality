# Duality

**Intelligent Multi-Device MIDI Polyphony Router**

Version **1.0.0** (`python duality.py --version`). What changed: [CHANGELOG.md](CHANGELOG.md).

Duality routes MIDI notes across one or more sound modules so you can treat several hardware and soft synths as a single, higher-polyphony instrument. Non-note messages stay synchronized. Optional layers sit on top of that core:

| Layer | What it does |
|-------|----------------|
| **Router** | Load-balance or round-robin notes; chord grouping; voice steal |
| **Crucible** | Send the stream only to outputs tagged for that MIDI dialect |
| **Voodoo** | Super-Munt-style GM on real MT-32 / CM-32L / CM-64 hardware |
| **Anima** | Humanize + GS EFX + foley + SC-8850 / CM-64 tone colors (GM files on GS hardware) |
| **Player** | Plays MIDI files itself, including songs with more than 16 channels (one port per kind of synth) |
| **Alchemy** | Experimental GS↔XG rewrite — **broken; do not rely on it** |

Built for musicians and retro-computing folks (DOS soundtracks, Sound Canvas, XG, MT-32, Ketron/Solton, etc.).

![Duality live status: four SC-VA GS units, an XG and an MT-32 out, Anima on](docs/images/status-hero.svg)

*Live panel from an offline replay of ONESTOP2 (one of the [demo songs](#demo-songs)) with the input locked to GS (**R** then **L**, badge `[GS*]`): four Sound Canvas VA units take the notes, the XG and MT-32 outs stay idle; Crucible + Anima, seed FC6C, the screaming solo: ch1 on GTR Multi 3 is the featured line, bent up an octave, while the rhythm guitar strums and the pads swell.*

---

## Features

### Polyphony routing
- Load-balancing by **utilization** (fair with mixed `--poly` limits) or pure **round-robin**
- Chord preference (notes arriving close together stay on the same device when possible)
- Smart voice stealing (lowest velocity first, then oldest)
- Independent polyphony limit per device
- Full panic / All Notes Off; **X** sends dialect resets to tagged outs and clears Anima locks

### Crucible (format-aware routing)
- Optional **output** tags: what each device can accept (`gs`, `xg`, `gm`, `gm2`, `mt32`, `cm32`, `cm64`, plus `gs+gm2`, …; model names such as `8850`, `88pro`, `55`, `scva` work too)
- **Input / stream format** (what the feed *is*): SysEx detect, `--input-format`, or hotkeys — not the same as output tags
- Affinity: notes and SysEx go to compatible ports
- Unknown input → GM-family ports only (**pure MT-32 excluded** until the stream is MT-32)
- An MT-32 stream plays on every LA out (`mt32`, `cm32`, `cm64`); on a CM-64, ch 11–16 go to its PCM half (see [CM-64 notes](#cm-64-notes))
- No silent “send to all” when nothing matches
- `GM` → `gm` / `gm2`; `--crucible-gm-wide` also reaches `gs` / `xg`
- **Set** format (G/R/Y/M) vs **lock** (L): lock blocks SysEx override and idle clear
- `--strict-format-detection`: only System On / Reset SysEx may switch format
- SCPOP / SC-ext (model-45 or banner — not LCD animation text) + optional `--scpop`

![Crucible: GM, GS, XG and MT-32 streams on the same six outs](docs/images/crucible-demo.gif)

*Same notes, four input dialects, same outs (four `8850+gm2`, one `xg`, one `mt32`). GM and GS land on the 8850 outs, XG only on the XG out, MT-32 only on the MT-32 out. Stills: [GM](docs/images/crucible-gm.svg) · [GS](docs/images/crucible-gs.svg) · [XG](docs/images/crucible-xg.svg) · [MT-32](docs/images/crucible-mt32.svg).*

### Voodoo (MT-32 GM)
- Roland **MT-TO-GM** (1993) or Sierra **KQ6** bank on `:mt32` / `:cm32` / `:cm64` outs (`:mt` / `:cm` work too)
- Paced SysEx (at the MIDI line's own speed) + input queue with elastic catch-up (does not dump the buffer)
- 1 / 2 / 3 unit maps; 4+ even units can use **pairs** (hotkey **P**)
- LA32 pan table (8 real positions, center split L1 / C)
- On CM-64s, GM programs with a fitting PCM tone play on the CM-32P half; the CM-32L sound effects stay playable
- Auto when every out is LA (MT-32 / CM-32L / CM-64) and the stream is not; exit on real MT-32 SysEx
- `--voodoo` at launch seeds MT-32 format so you can **L**ock it

### Anima (opt-in phrasing)
- Velocity humanize, expression / mod ramps, guitar strum (including “Hetfield” down-pick on dirt tones), mallet sticking
- **GS EFX**: one insertion per `:gs` unit, chosen by instrument-family priority; never retyped under a sounding part; guitars pair via OD1/OD2 by pan; file-driven EFX stays on its port
- **Insert shaping**: each family picks from hand-chosen palettes of the 64 SC-8850 / SC-88Pro types; pan-capable inserts follow the file's pan, delays lock to the beat (feedback ≤ 50 %), pitch shifters play a doubler / octave / fifth, and dirt inserts fade out with the file
- **Live insert control**: the wah follows the player like a foot on a pedal (lead vs rhythm), rotary speed flips on held chords, and a file's own set-and-left wah gets played too
- **Hero split**: a featured line that shares a unit with its family can take a spare unit with another type of the same family
- **Family spread**: a big family (a string section on many channels) shares a spare unit too, half its channels moving over one by one in their rests
- **Look-ahead with the player**: Anima knows each part's next note, so inserts go on in gaps before a family's first note instead of at it
- **Ghosts**: chord-tone harmony, bass / organ sub-octaves, dirt-guitar unison on a spare unit; **seat units** put the harmony on an idle unit, panned like a second desk
- **Featured lines**: a run or a tune worth hearing is lifted and the parts competing with it step back
- **Foley**: shared high channel (usually 16) for 8850 SFX (fret, cut, chord stroke, slap, breath, …)
- **Tone colors**: seeded 8850 CC00 (same PC), older-map (SC-55 / 88 / 88Pro) and **CM-64** tones that are not copies, weighted per tone by ear; per-tone traits (no LFO insert on a tone that already moves, no harmony on a tone that plays fifths, one-shots go back to the capital when held, …)
- File **GM/GM2 On** on `:gs` ports becomes **GS Reset** so the Canvas leaves GM-lock and honors those banks
- 4-char hex **seed** on the badge; `--anima-seed` / **S** lock a keeper across **X**
- Game mode (`--anima-game` / **A** cycle): 4 s of real silence resets; a real PC burst (new cue) rolls a new seed
- On LA outs (MT-32 / CM-32L / CM-64) the touch layers work too; EFX, tone colors, seats, foley and harmony are GS-only
- Single output allowed when Anima is on

### Player
- `--play` plays MIDI files through Duality itself: files, folders (their `.mid` / `.midi` / `.kar` files by name) or wildcards, as a playlist; `--play-loop` repeats it
- Same path as live input, so routing, Crucible, Voodoo, Anima and `--record` all apply; `--input` is optional with `--play`, and when given, live input keeps playing alongside the songs
- Reads what an outside player keeps to itself: the tempo map, every SysEx, and each track's MIDI Port marker (FF 21)
- Hotkeys: **Space** pause / play, **N** next, **Z** back (start of the song, or the one before), **T** stop; the panel shows song, time and ports

### More than 16 channels: multi-port songs
- A song whose tracks use more than one MIDI port (32, 48 or 64 channels, like Roland's SC-8850 demo "Space Flight") plays each port on units of its own, so port B's instruments never land on port A's units
- Every port that can play gets a unit first, then the rest are shared in blocks: two ports on six units play A on units 1–3 and B on 4–6
- A port can ask for a kind of unit with a text event (Text, Marker or Cue) on one of its tracks, which other players ignore:
  - `duality: 8850` — this track's port wants an SC-8850 (any `--outs` tag works: `gs`, `xg`, `mt32`, `cm64`, …)
  - `duality: port C mt32 x2` — port C wants two MT-32-family units
  - `duality: B=xg` — port B wants an XG unit
  - `duality: 8850, cm64` — an SC-8850 if one is free, else a CM-64 (kinds in order of preference)

  So one song can drive several kinds of synth at once. Without a request a port takes GM-family units (not LA-only ones). A port with no free unit of its kind is dropped (one unit plays port A only)
- A song can also set the foley for itself, with the same kind of text event: `duality: foley off` (or `duality: no foley`) or `duality: foley 25%` (a quarter of its usual level). It holds while the song plays (one port or several), then `--anima-foley` is back
- Port A's system SysEx (GM / GS / XG resets, reverb / chorus macros, master volume) also reaches the other ports' units, as on one multi-port device
- Under the hood each port plays on a *lane*, a router of its own with the same settings (Crucible, Anima, Voodoo …); the routing hotkeys reach every lane, live input goes to port A's, and when the song ends the router takes all its outs back

### Record + log
- `--record [DIR]` / hotkey **W**: IN + each OUT as type-1 SMF (conductor + Ch1–Ch16 + SysEx), in `recordings/` by default
- Idle ~10 s closes a take and the next MIDI opens a new file
- `--log` / `--log-verbose`: `logs/duality-<date>-<time>.log`, one per run and, with `--record`, one per take (same stamp as its IN/OUT files); **C** starts a new log

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

## Demo songs

Five original songs written for Duality come with the 1.0 release, as MIDI files attached to the [GitHub release](https://github.com/midiman369/duality/releases/tag/v1.0.0) (they are not in the repository):

| Song | Length | Written for |
|------|--------|-------------|
| **ONESTOP2 – A Brief History of Sound** (`onestop2.mid`) | 9:20 | Anima on several GS units: medieval lute to baroque, a cathedral organ, ragtime and Dixieland, big band, rock'n'roll, analog synths, prog organ, a screaming guitar solo and a metal anthem. Plays complete on one SC-8850; channel 16 is left for Anima's foley |
| **Point & Click Overture** (`point_and_click_overture.mid`) | 4:56 | Voodoo: five adventure-game scenes (calypso, noir swing, storybook, sci-fi march, lounge) joined by CM-32L sound effects, then a finale on all 15 melody channels |
| **Adventure Game Night** (`adventure_game_night.mid`) | 3:21 | Voodoo: two tunes over one progression, one per half, played together in the finale |
| **The Hint Line** (`the_hint_line.mid`) | 3:57 | Voodoo: a call to a game hint line; the hold music travels through five worlds in a key, metre and groove of their own |
| **A Tribute to the Metal Gods** (`metal_gods.mid`) | 11:53 | Anima: a heavy metal epic (lead guitar sings the melody and takes every solo over a hard-panned rhythm duo), each verse in the manner of a band it names, with original riffs and melodies |

The three Voodoo demos are plain GM files (GM System On, GM capitals), so MT-32s and CM-64s play them under Voodoo, as does any GM synth; ONESTOP2 and Metal Gods are GS files on GM capitals (one GS reset, GS drum sets, no file inserts) that leave the colors and inserts to Anima. Try them with the player, for example:

```bash
python duality.py --play onestop2.mid --outs "SCVA:gs+gm2" "SCVA2:gs+gm2" "SCVA3:gs+gm2" "SCVA4:gs+gm2" --anima
python duality.py --play the_hint_line.mid --outs "MT-32 A:mt32" "MT-32 B:mt32" "CM-64:cm64"
```

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

Files:

| File | Role |
|------|------|
| `duality.py` | Router, UI, Crucible, Anima, Voodoo, player, record |
| `tables_gs.py` | GS EFX types (all 64, SC-8850 / 88Pro), macros, Anima palettes, insert shaping + fixed settings |
| `tables_xg.py` | XG types + Alchemy maps |
| `tables_anima.py` | GM / MT-32 / Sierra categories |
| `tables_cm64.py` | CM-64 PCM tones and the GM → LA / PCM / layer picks for Voodoo |
| `tables_8850.py` | SC-8850 CC00 + map + CM-64 variation tables, Anima's tone weights (`ANIMA_TONE_PREFS`) and tone traits |
| `tables_voices.py` | SC-8850 voices per tone (poly accounting) |
| `tables_voodoo.py` / `voodoo_banks.py` | MT-TO-GM / KQ6 SysEx |

Branches: `main` holds the releases; `dev` is where Duality is developed (it also carries the offline regression suite and the tools that generate the tables).

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

### Play songs with Duality's own player
```bash
python duality.py --play "C:\MIDI\Demo Songs" --outs "SCVA:gm2+8850" "SCVA2:gm2+8850" --anima
python duality.py --input "loopMIDI Port" --play song1.mid song2.mid --play-loop --outs "MS40 A" "MS40 B"
```
The first plays a folder with no live input; the second plays two songs on repeat while live input still comes in.

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

### Four GS ports + Anima (GM soundtrack on Canvas hardware)
```bash
python duality.py --input duality \
  --outs "SCVA:gs+gm2" "SCVA2:gs+gm2" "SCVA3:gs+gm2" "SCVA4:gs+gm2" \
  --poly 32 32 32 32 --crucible --crucible-gm-wide --anima-game --log --record
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
| `--input` | MIDI input port (partial name ok). Optional with `--play` |
| `--play FILE…` | Play MIDI files / folders / wildcards through Duality (a playlist). Hotkeys **Space N Z T** |
| `--play-loop` | With `--play`: start the playlist again after its last song |
| `--outs` | `Name` or `Name:tag` or `Name:tag+tag` (`gs`, `xg`, `gm`, `gm2`, `mt32` / `mt`, `cm32` / `cm-32` / `cm`, `cm64` / `cm-64`, model names like `8850`) |
| `--poly` | One limit for all, or one per port |
| `--sync-delay` | Per-port delay in ms. Negatives = relative. ±500 max. `0` = fast path |
| `--mode` | `balance` (default) or `rr` |
| `--chord-ms` | Chord window in ms (default 30) |
| `--crucible` | Format-aware routing |
| `--crucible-notes` | `affinity` (default) or `all` |
| `--crucible-gm-wide` | GM/GM2 also matches `gs` and `xg` |
| `--input-format` | Assume `gm` / `gm2` / `gs` / `xg` / `mt32` until SysEx says otherwise. Any `--outs` tag works too (`8850`, `88pro`, `55`, `scva`, `cm64`, …): a GS model means `gs`, a CM-32L / CM-64 means `mt32` |
| `--strict-format-detection` | Only System On / Reset SysEx may switch format |
| `--scpop` | Force SCPOP note broadcast to format-matched ports |
| `--anima` | Phrasing + GS EFX + foley + 8850 / CM-64 tone colors |
| `--anima-game` | Game mode (implies `--anima`): 4 s silence reset + cue reroll |
| `--anima-seed [HEX]` | Lock seed (`4A2F`, `0x4A2F`, or decimal). Bare flag locks first roll |
| `--anima-foley LEVEL` | Foley level: `off`, `on` (default) or a percentage (`25`); a song's `duality: foley ...` wins while it plays |
| `--anima-efx-stable` | Deprecated alias for bare `--anima-seed` |
| `--voodoo` | Load GM bank on MT-32 outs at start |
| `--cm64-seats` | One CM-64 under Voodoo: `live` (default) or `fixed` PCM seats |
| `--voodoo-bank` | `mtgm` (default) or `kq6` |
| `--voodoo-layout` | `stripe` (default) or `pairs` |
| `--alchemy` | **BROKEN/EXPERIMENTAL** GS↔XG rewrite; allows one output |
| `--alchemy-all` | Alchemy fan-out to all GS/XG outs (implies `--alchemy`) |
| `--record [DIR]` | Write IN/OUT SMFs (default dir `recordings/`, created if needed). Hotkey **W** |
| `--log [PATH]` | Status / bank / port health. Default `logs/duality-<stamp>.log` (per run, per take). A path with `{stamp}` does the same; a plain path is appended to |
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
| **S** | Lock / unlock Anima seed (X keeps colors while locked) |
| **B** | Balance ↔ round-robin |
| **X** | Panic + dialect resets + Anima session reset (not format lock) |
| **W** | Start / stop recording |
| **C** | Start a new log file (a fixed `--log` path is cleared instead) |
| **Space** | Player: pause / play (from stopped or the end: plays) |
| **N** | Player: next song |
| **Z** | Player: back to the start of the song (or, near its start, the song before) |
| **T** | Player: stop (Space plays the song from the start) |
| **Q** | Panic and quit |
| **Ctrl+C** | Panic and quit |

---

## Status panel

![Status panel: meters, channel grid, Recent](docs/images/status-panel.svg)

While running:

- Per-port meters and peak markers
- Total / Peak / Util; Drops, Steals, Filtered
- Per-channel voices, Volume, Pan, Mod, Pitch
- Last chord, last activity, status + rolling history
- With `--play`: a **Player** row (▶ / ⏸ / ■, song n of N, name, time / length, the ports a song uses)
- Format badge (`[GS]`, `[GS*]`), Crucible / Voodoo / Anima / SCPOP
- Activity pulse and decoded SysEx

Wide terminals (≥ ~118 columns) get the side **Recent** panel automatically.

---

## Anima notes

Anima is off unless `--anima` / `--anima-game` or hotkey **A**. It is the musician between the file and the hardware: touch, colors, and inserts — not a rewrite of the sequence.

### GM files on a Sound Canvas

A file **GM System On** locks an SC-8850 / SC-VA into GM mode, which **ignores** CC00, CC32, and CM-64 banks. With Anima on, Duality turns that message into a **GS Reset** on `:gs` / `:sc` ports (and **XG System On** on `:xg` ports) so variations actually sound. That is why a capital-only GM soundtrack can use the 8850 map and the CM-64 LA organs / horns.

### Tone colors

If the file leaves bank `0/0` (or lands back on a GM capital), Anima may pick:

- another **8850 CC00** of the **same PC** (map 1–4),
- an older-map version of it (SC-55, SC-88, SC-88Pro) that is not an exact copy of one already offered (compared by tone data read from the ROM: voices, waveforms, parameters; 252 older-map tones such as each map's own Piano 1, 1w, 1d, the SC-55 Jazz Gt., Viola, Clarinet, Saw Wave), or
- a family-matched **CM-64 PCM (126) / LA (127)** tone on the SC-55 map (`CC32=1`; 131 of the 166 are not copies).

Family is tracked so a later PC stays in brass / organ / strings / …. A *real* file variation (non-zero CC00 that is not “back to capital”) wins and Anima steps off that part. Live slots are held across a scene `CC0=0` pad so a GM reset dump does not wipe a CM horn back to Bowed Glass.

Every candidate tone was listened to and weighted by ear (605 tones on 101 programs; 57 switched off): normal, favoured or less often, an EFX level (drier or wetter), and notes on how it plays (`tables_8850.ANIMA_TONE_PREFS`). The notes become **traits**:

- a sample that already moves (vibrato, tremolo, rotary, a strummed or arpeggiated sustain) gets no chorus / flanger / phaser / tremolo / rotary insert, and a built-in rotary gets no speed flips;
- tones that play extra pitches (built-in octaves, fourths, fifths, chord tones) get no harmony ghosts, no bass sub-octave and no pitch shifter;
- a short stab that does not loop, a slow-attack tone or a low-register tone that the part turns out not to suit (held notes, quick short notes, high notes) goes back to the capital once, at the part's next rest;
- a tone whose notes start with a squeal that sweeps down (303SqDistBs3 / 2) changes when the part's notes keep ending before the squeal settles, and a tone in a set steps down to its tamer sibling instead of the capital (303SqDistBs3 → 303SqDistBs2 → 303SqDistBs); a palm-muted chug tone held long steps to a rhythm guitar that sustains.

A tone's EFX level moves its insert's wet/dry Balance from the type's default (drier ×0.6 / ×0.35, wetter 40 % / 65 % of the way to full wet; the driest part on a unit wins).

### Seeds

The badge shows a 4-char hex. Same seed → same colors and inserts. `--anima-seed 4A2F` or hotkey **S** locks it; **X** then repeats the take. Game mode rolls a new seed on a burst of program changes (new cue) unless the seed is locked. On a multi-port song every port plays the badge's seed plus 0101 per port (port A the badge's own), locked or not, so the badge describes the whole take: lock it with **S** (or play it again with `--anima-seed`) and every port comes back the same; the log lists each port's seed when the song starts.

### GS EFX

Each tagged GS unit has one insertion effect, so with four units Anima can give four instrument families an insert at a time. Families are ranked (table below): guitars first, then organ / harmonica / plucked / e-pianos, lead / wind / brass, bass, strings, pad, piano, chromatic, fx.

- **Placement.** The program-change dump at song start is placed once, after it settles (or at the first note), so each unit gets one type write. A part that is actually playing takes a lower-ranked unit in a gap in that owner's playing. A lower part only gets a unit whose owner has gone stale: silent 15 s, or never played within its grace (1 s after the song-start dump, 12 s after a mid-song PC).
- **No glitches under notes.** A unit's insert type (and who owns it) never changes while one of its insert parts is sounding, including ghosts and queued strums. Dry parts on that unit don't count. At most one type change per unit every 1.2 s, and for 150 ms after a change that part's notes play on another unit instead (rerouted, never delayed).
- **Guitars.** A second guitar pairs onto its partner's unit before taking another family's. Hard-left / hard-right pairs use OD1/OD2 so each keeps its side (centered until a quiet moment allows the switch). A panned lone guitar prefers Overdrive / Distortion, which honour its pan.
- **File EFX** stays on the file's port (a GS bulk dump's insert counts too); Anima uses the *other* units.
- **Hero split.** Families share one insert unit (stereo inserts take several parts cleanly). When a featured line plays in a family that shares a unit, every family already has its unit, a unit is spare and no part makes harmony, the line gets that spare unit with a different type from its family's palette. The type is written onto the empty unit first; the line moves over in its next breath (a quarter second with nothing of it sounding), so no note is delayed and no type changes under a sounding part. Any family that needs the unit later takes it back once it is quiet.
- **Family spread.** A family heard on four or more channels of one unit also takes a spare unit: a second unit it already holds, an empty one (given the family's insert while it is silent) or one another family has left idle for a minute. About half its channels, the right-hand side by pan, move over, each in a rest of its own (Part EFX On there and Off on the old unit together), so a big string section plays from two units across the stereo field and shares their polyphony. Units carrying harmony seats are left alone; any family that needs the unit takes it back once it is quiet, and the channels rejoin their family's unit.
- **Look-ahead with the file player.** While `--play` plays a song, Anima reads each channel's next note from the file: a family without a unit is placed two seconds before it plays, so its insert type and Part EFX On are in place before the first note; an insert change that would land right at a note is put off to the part's next gap (it starts dry for at most four seconds); a unit is not taken from a family that plays again within three seconds; and a part only moves units when its next note is at least 0.3 s away. Live input works as before.

**Palettes.** Every family has its own list of insert types, drawn from all 64 on the SC-8850 (the SC-88Pro has the same 64, at the same addresses, so both get the Multis). The lists were picked by ear, one tone per family, and each type is weighted: normal, **favoured** in steps (×2, ×3, …) or **less often** (×½, ×⅓, …). The seed picks one per unit; a locked seed repeats it. The bass splits three ways: finger / picked lean on **Bass Multi**; slap, fretless and synth bass, and the upright have their own lists, mostly chorus / Space D / enhancer. The harpsichord takes the acoustic piano's inserts, a Jazz Gt. never gets a wah, and a rotary organ never gets a distortion stage.

![Anima EFX priority and palettes](docs/images/anima-efx-priority.svg)

**Shaping.** After a type is picked, Duality sets the parameters that make it fit the part:

- **Pan follows the file.** Types with a Pan knob (Humanizer, Auto Wah, Overdrive / Distortion, Compressor, the OD→ / DS→ series, …) put the output where the file panned the player. Parallel pairs (Cho/Delay, OD/Rotary, …) and the two pitch voices sit ±24 either side of it.
- **Delays on the beat.** Delay times come from the tempo: MIDI clock if the player sends it, otherwise the rhythm of the notes. Multi-tap delays keep their tap pattern, and a delay picked before the beat is known is set once the part rests. Feedback is +30 % (+16 % on strings, pads, organs, fx and synth brass) and never above +50 %.
- **Pitch shifters as free harmony.** 2 Pitch Shifter, Fb P.Shifter and Keyboard Multi play a doubler, an octave or a fifth (by family and seed) — harmony that costs no polyphony.
- **Gate Reverb** gets one of its four types (Normal, Reverse, Sweep 1, Sweep 2) by seed.
- **Dirt fades out.** A part's volume sits *before* its insert, so a fade into Overdrive would stay loud. Dirt inserts drop their own Level with the file's CC7 / CC11 once it falls below 75 %.
- **Levels set by ear.** GTR Multi 2's drive stage is Distortion; GTR Multi 3 plays at Level 127 and lifts its players' CC7 ×1.2 (capped at 127), like the organ lift on rotary types; Overdrive runs at Level 80, and the OD1/OD2 guitar split runs both sides as Distortion with OD1 at 80. Fixed settings per type live in `tables_gs.ANIMA_EFX_TYPE_SET`.

![Anima insert shaping](docs/images/anima-efx-shaping.svg)

### Live insert control (CC16)

The SC-8850 has no built-in controller for its inserts: EFX Control Source 1/2 (`40 03 1B` / `1D`) default to Off. Anima sets the one that carries the wah or speed knob to CC16 at +100 % depth and drives each unit on its own, sending CC16 only to that unit's players. Only wah and rotary types move.

- **Rotary** flips speed while a chord is held and flips back on release.
- **Wah** follows the player like a foot on a pedal: each pick gives a quick quack scaled by velocity; a held note sweeps from heel to toe, then (by seed) rocks at a rate tied to the beat, holds open, eases back closed, or moves with the player's vibrato; a bend up opens it further, high notes sit a little more open, fast runs and tapping stay narrower, and silence lets it fall back to the heel. A hard-played high note held for half a second lifts the whole wah for a scream, at most once every 8 s.
- **Lead or rhythm.** Two or more notes at once, or a low register, is rhythm; single high notes are lead. A lead line opens the wah within its first note or two, while dropping back to rhythm glides over about 1.5 s, so a chord stab inside a solo does not knock it back. A lead on GTR Multi 3 (a pedal wah) gets its Peak at 80 and the full phrasing; a rhythm part gets Peak 48, 60 % of the pedal's travel and never the scream. The auto-wah types keep their own Peak, LFO and Sens, and the phrasing moves the centre they swing around.
- **A file's own wah.** When the file sets a wah type on its home unit and leaves it (wah switch On, no pedal Control Source or CC16 of its own, no EFX write after its first 4 s of setup), Anima plays that pedal for it, around the file's own Manual, keeping the file's Peak and every other parameter. Any later EFX write from the file hands the unit straight back, restored, and Anima stays hands-off for the rest of the song.

Values live in `tables_gs.py` (`ANIMA_WAH_MAN_BASE`, `ANIMA_WAH_MAN_SCREAM`, `ANIMA_EFX_WAH_PEAK`) and the `ANIMA_WAH_*` constants.

### Ghosts and seat units

Ghosts are extra notes Anima adds on the same channel: a chord-tone harmony on melody lines (never above C7), a sub-octave under bass and organ (never replacing the file's own bass tone), and a unison double of a dirt guitar on a spare unit.

- **Balance.** A section should not just get louder: a melody plays at 90 % and gets its ghost above at 50 %; an accompaniment voice (another part sounds above it, or it tops a held chord while a line moves) plays at 85 % with its ghost *below* at 45 % (a third or sixth under, never below C3); a thin source (at most one other voice) gets both sides, extending the chord. An upper ghost steps aside when a line starts over it, and a pitch another part (or its ghost) already sounds is not doubled.
- **Tonal.** Harmony prefers a third or sixth, then a fourth or fifth, then the octave, and never moves a second, tritone or seventh against its hero; a note that would rub a semitone against something sounding nearby is skipped, and a passing tone (a melody note outside the chord) is not harmonised. The chord Anima reads includes notes other parts struck in the last 0.8 s, so a picked guitar's chord still counts after each note is released.
- **An acoustic guitar** plays at 112 % while a sustained part at least as loud sounds within an octave of it (its notes decay, theirs hold).
- **Seat units** ("second desk"): when a GS unit has no family or file insert of its own, the harmony plays there instead of on top of its hero, each channel panned to the mirror of its hero (flute at 44 → harmony at 84; a centred hero's harmony goes to a seeded side) plus a seeded ±5 %. One spare takes every family's harmony; two or more are shared out by family. Once quiet, the seat gets a gentle insert of its own (Space D favoured, drier than its default; Hexa, Stereo and 3D Chorus; now and then a Reverb). A seat ranks below every instrument family and hands its unit over under the usual rules. Because a seat's harmony is heard apart from its hero, some fullness comes back there (both-sides voicing with up to three other voices, +5 %), except on a part that is already the loudest thing playing.
- Each wheel Anima moves (CC1 mod, CC11 expression) returns to rest on every unit, and a program change starts the new instrument with the mod wheel at zero.

### Mallet sticking

Glockenspiel, vibes, marimba, xylophone, tubular bells, hammered dulcimer, tinkle bell and steel drums play like a mallet player. A chord is struck by hands, two or four mallets: the low pair and the high pair land about 18 ms apart. When the part usually leaves room before its next note (at least 0.2 s, judged from its own recent spacing), the seed sometimes adds a soft **double** or **triplet**. Marimba, xylophone, dulcimer and steel drums with 0.45 s or more of room can also **roll**, the hands alternating every 75 ms and fading. Extra strokes start at 68 % of the note's velocity and fade; a new note or a program change cancels whatever is still pending, and no key ever gets a second note-on while it sounds. Celesta and music box keep the plain unroll, as do harp and pizzicato.

On a delay insert, a mallet part's echoes are timed from its own note spacing instead of the song's beat, with a light 12 % feedback: each delay type's longest echo lands on the part's next note when that type reaches that far (Tm Ctrl Delay up to 1 s; Stereo Delay, 3D Delay and the →Delay / /Delay types up to 500 ms). A pitch shifter just doubles every stroke for free (mallets get the doubler or octave-up); if it adds a fifth, triplets and rolls get half as likely.

### Featured lines

Anima watches every part for a line worth hearing, in the middle or top register: a *fast* run (at least 2.5 notes/s, mostly single notes, mostly stepwise, so arpeggios and ostinatos do not qualify) or a *slow* tune (0.4–3 notes/s, one note at a time, no big leaps). One line is featured at a time: a clearly busier line wins, otherwise the current one keeps it unless a new one sits above it. While it plays, its notes are lifted part of the way toward the loudest part sounding over it (never more than ×1.4); notes from other parts that compete with it in its register play at 85 % (75 % within a tone of its current note) and turn their harmony below it; and no harmony ghost is left on its notes. Loudness here is velocity × CC7 × CC11, so a horn at velocity 109 on CC7 50 does not count as louder than a wind at 90 on CC7 127.

### Foley

One shared SFX channel per GS synth (usually 16), overflowed to another out if the hero is full. 8850 programming stays on the **default map**. Gesture after a short hold: fret / cut / chord stroke / steel slide; bass slap vs slide; wind click vs breath. Families take turns on the same lane.

![Anima foley map](docs/images/foley-8850-map.svg)

### Game mode

Resets after 4 s of real silence (no new MIDI *and* nothing still sounding, so a held chord is not a new scene), and rolls a new seed + EFX set on a real PC burst (DOS / soundtrack cue changes). A new cue is its own channels: only the parts that got a program change in the burst, or play a note afterwards, count for the insert planner and the seat units, so parts left over from the previous cue do not squeeze the new cue's guitars onto a shared unit or hold units as seats.

### Anima on LA outs and mixed rigs

On MT-32 / CM-32L / CM-64 outs, velocity humanizing, CC11 / CC1 swells, strum / unroll, mallet sticking and the lifts work as on GS; EFX, tone colors, seats, foley and harmony ghosts are GS-only (and ghosts stay off on native MT-32 / CM music). Native MT-32 streams look their LA patches up as the nearest GM program (`tables_anima.MT32_TO_GM`, from the CM-64 manual's sound list), so MT-32 organs are not played as mallets; a native CM-64 stream's PCM channels (11–16) use the CM-32P tones. On a mixed rig, the GS layer (inserts, seats, hero split, foley) only uses GS units that can get notes: under Voodoo, or when Crucible sends an MT-32 stream to the LA outs only, the GS units are left alone.

---

## Voodoo notes

Think “Super Munt GM,” but on hardware. `--voodoo` or **M** while the input format is already MT-32.

- Init is paced on purpose (MT-32 buffer), and follows the MIDI line itself: a unit cannot take SysEx faster than 31,250 baud (3,125 bytes/s), so each step waits until that unit's line has delivered the last one, and Voodoo reports ready only when every unit has its last byte. A full MT-TO-GM load is about 28 KB a unit, about 9 s on the wire. Several units in parallel still share the host MIDI interface.
- Incoming MIDI is queued during load, then caught up with a speed ceiling — not dumped.
- Real MT-32 SysEx in the stream drops Voodoo and returns to normal MT-32 routing.
- Drum kits: ch10 program 49 loads the Orchestra kit and every other kit program (Room, Power, Brush, Jazz, TR-808 …) the Standard kit. A kit change that lands on the kit already loaded sends nothing and holds no input back.
- A GM or GM2 System On keeps Voodoo running: the bank stays loaded, nothing is resent. A GS or XG reset still leaves Voodoo unless the format is locked (**L**).

---

## CM-64 notes

The CM-64 is a CM-32L (LA, parts 1–8 on ch 2–9 plus rhythm on ch 10) and a CM-32P (PCM, parts 1–6 on ch 11–16, 31 voices) in one box. Tag it `:cm64` (or `:cm-64`); the panel shows CM-64.

- Ch 1–10 behave as on a CM-32L: the CM-32L pan table, Voodoo, the LCD text, **X** sends the MT-32 reset.
- Ch 11–16 of an MT-32-format stream go only to CM-64 outs (an MT-32 or CM-32L would ignore them). With no CM-64 out they route as before.
- Voices are counted per half: the LA half uses the port's `--poly`, the PCM half has 31 partials; a full half steals only its own notes. A PCM note takes 1 or 2 partials by its tone (manual p.12–13: A.PIANO 1–4, the organs, CHOIR 3/4 … are 2), so 15 notes of a 2-partial piano fill the half; a part with no program change yet counts its power-on patch. The PCM half pans continuously but reversed like the LA half (0 = right, 127 = left), so GM pan sent to it is flipped (127 − value); a native CM-64 stream's own pan is passed as is.
- **Voodoo with the PCM half**: the LA maps stay as they are, and each CM-64 adds 6 PCM parts. `tables_cm64.py` says per GM program whether the LA half, a PCM part or both (layer) play it, which PCM tone, and a level per half (CC7 scale). The seed picks PCM wherever the manual has a fitting tone: pianos, Rhodes, organs, guitars, basses, strings, choir, orch hit, trumpet / trombone / brass, saxes.
  - **2+ units — pool**: a channel whose program is PCM claims a free part, preferring the unit that plays it on LA. Duality sends it that channel's traffic on the part's own receive channel (one the unit's LA parts don't use) with the program translated to the PCM tone. Back to an LA program, the channel plays on LA again; a held note's off still reaches its part. When all parts are taken, a part whose channel has rested 10 s can be taken; otherwise the newcomer plays on LA.
  - **1 unit — live seats** (default): the 15 GM melody channels share 8 LA + 6 PCM parts. Each part listens on its channel's own number (Duality rewrites receive channels: LA `10 00 0D`+part, PCM `52 00 0A`+part). At each program change a channel moves to the half its pick wants when a part there is free, or its channel has rested 10 s (a program change counts as use, so the song's opening burst settles cleanly); its sounding notes are ended first. A channel without a part takes one at its next note; with none free it stays silent. A layer plays on PCM here (one unit has no spare part for the LA side).
  - **1 unit — fixed seats** (`--cm64-seats fixed`): the PCM parts stay on the melody channels the bank's LA parts leave free (MT-TO-GM: ch 9 and 11–15; ch 16 silent) and always play PCM, the program's nearest tone.
  - **Anima and the display**: PCM-played notes take Duality's normal note path and are handed to their PCM part only as they are sent, so they show in the channel and unit counters and get Anima (humanizing, strum / unroll, mallet sticking, lifts, CC11 / CC1 swells). The header shows **[Voodoo] [CM-64 LA+PCM]** while CM-64 PCM parts are in play.
  - **Sound effects**: the Voodoo kit fills every drum key, so on `:cm32` / `:cm64` outs Voodoo writes the CM-32L sound effects back after it (and after every kit switch): Applause … Bubble on keys 82–108 as the manual lists them, and Laughing, Screaming, Punch, Heartbeat, Footsteps 1 / 2 on keys 24–29 (GM percussion keeps 76–81). Drum notes on those keys go to CM units only; plain MT-32s never get them.
  - PCM partial reserve 6/5/5/5/5/5; parts go silent and back to ch 11–16 when Voodoo ends. Card sounds (PC 65–128) are not mapped yet.

```bash
python duality.py --outs "MT-32 A:mt32" "MT-32 B:mt32" "CM-64:cm64"
```

---

## Recordings

`--record` or **W** writes into `recordings/` (or the folder you give) — git ignores it, like `logs/`:

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
- Feed Duality from a loopback (loopMIDI, IAC, ALSA virtual ports), or play files with `--play`.
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
