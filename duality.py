#!/usr/bin/env python3
VERSION = "0.19.011"


"""
Duality – Intelligent Multi-Device MIDI Polyphony Router
---------------------------------------------------------
Version {VERSION}

Routes MIDI notes across one or more sound modules / synthesizers
to maximize effective polyphony while keeping non-note messages
synchronized across all devices.

Features
--------
Router
  • Load-balance by utilization (fair with mixed --poly) or pure round-robin
  • Chord preference; smart steal (low velocity, then oldest)
  • Independent poly limit per device; panic / All Notes Off
  • X = dialect resets + Anima session clear (does not clear format lock)

Crucible (format-aware routing)
  • Output tags = device capability (--outs "SC:gs+gm2") — not the input stream
  • Input format from SysEx, --input-format, or hotkeys (G/R/Y/M; L lock; F clear)
  • Affinity routing; unknown input → GM-family only (pure MT-32 excluded)
  • No spill-to-all when nothing matches; --crucible-gm-wide adds gs/xg for GM
  • --strict-format-detection: only System On / Reset SysEx may switch format
  • SCPOP / SC-ext (model-45 or banner, not LCD text) + optional --scpop

Voodoo (MT-32 GM)
  • MT-TO-GM or KQ6 bank on :mt32/:mt/:cm — --voodoo / M while already MT-32
  • Paced SysEx + queued input with elastic catch-up; exit on real MT-32 SysEx
  • 1/2/3-unit maps; 4+ even units can use pairs (P); LA32 pan table

Anima (opt-in)
  • Velocity humanize, expr/mod ramps, guitar strum; CC1 returns to rest
    on every unit, and each PC starts the new tone with CC1=0
  • GS EFX: one insert per GS unit by family priority (tables_gs
    ANIMA_EFX_PRIORITY), placed once after the PC dump. A playing part
    takes a lower-priority unit in that owner's gap; lower parts wait until
    the owner is stale. Never retypes under a sounding EFX player; one type
    write per unit per 1.2 s; notes skip a unit for 150 ms after its type /
    Part On changes. Notes are never delayed. Guitars pair on OD1/OD2 by pan.
  • Foley: shared ch16 8850 SFX (PC 121/122 variations)
  • Ghosts: chord-tone harmony (≤ C7), bass/organ sub-octave on-channel,
    dist-guitar unison on a spare GS unit (inherits EFX)
  • Seeded 8850 / CM-64 tone colors on capital 0/0 only — file bank wins
  • --anima-game / A cycle: 4 s of real silence resets; PC burst rerolls
  • Single output allowed

Record / log / panel
  • --record / W: type-1 SMF per IN and OUT (Ch1–Ch16 + SysEx)
  • --log / --log-verbose; C clears; port health on session end
  • Live meters, channel grid, Recent history, format badge, decoded SysEx

Other
  • Redundant CC filter; --sync-delay (negatives relative; 0 = fast path)
  • Reconnect dropped outs by name (does not re-program the synth)
  • Alchemy BROKEN/EXPERIMENTAL (--alchemy / --alchemy-all)
  • Developed and tested on Windows. MIDI I/O via python-rtmidi
    (WinMM / CoreMIDI / ALSA). Unix hotkeys = cbreak stdin (best-effort).

Hotkeys (input/stream format — not output tags)
-------
F clear input format   L lock/unlock input format
G GM↔GM2   R GS   Y XG   M MT-32 (again = Voodoo GM)
V Voodoo bank   P Voodoo layout   A Anima off/normal/game   S seed lock
B balance↔rr   X reset+Anima   W record   C clear log   Q quit

Usage examples
--------------
# List ports
python duality.py --list

# Two devices (classic)
python duality.py --input "loopMIDI Port" --outs "MS40 A" "MS40 B"

# Mixed polyphony
python duality.py --input "loopMIDI Port" \
  --outs "Module A" "Module B" "Module C" --poly 28 32 24

# Crucible + multi-capability tags
python duality.py --input "loopMIDI Port" --crucible --crucible-gm-wide \
  --outs "SC A:gs+gm2" "SC B:gs+gm2" "MU:xg+gm2" "MUNT:mt32"

# Four GS ports + Anima + record + log
python duality.py --input duality \
  --outs "SCVA:gs+gm2" "SCVA2:gs+gm2" "SCVA3:gs+gm2" "SCVA4:gs+gm2" \
  --poly 32 32 32 32 --crucible --anima --log --record

# Voodoo on two MT-32s
python duality.py --input duality \
  --outs "MIDIMate 1:mt32" "MIDIMate 2:mt32" \
  --voodoo --voodoo-bank mtgm --sync-delay 0 80

# Sync delay (softsynth ~80 ms ahead of hardware)
python duality.py --input "..." --outs "SC:gs+mt32" "MUNT:mt32" --sync-delay 0 -80

# Strict format detect + silent panel
python duality.py --input "..." --outs "A:gs" "B:xg" \
  --crucible --strict-format-detection --no-status

python duality.py --version
""".format(VERSION=VERSION)

import argparse
import os
import signal
import sys
import time
import random
import math
import random
import threading
from typing import List, Optional

import mido
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn
from rich.table import Table
from rich.text import Text
from rich.markup import escape

try:
    from tables_voodoo import (
        mtgm_sysex,
        mtr_stnd_sysex,
        mtr_orch_sysex,
        kq6_sysex,
        GM_ORCHESTRA_KIT_PC,
        VOODOO_BANK_INFO,
        VOODOO_BANK_NAMES,
        DEFAULT_VOODOO_BANK,
        get_bank_sysex,
        bank_has_kits,
        bank_label,
        bank_display,
        bank_anima_map,
    )
    _VOODOO_BANKS = True
except ImportError:
    _VOODOO_BANKS = False
    GM_ORCHESTRA_KIT_PC = frozenset({48})
    VOODOO_BANK_NAMES = ("mtgm",)
    DEFAULT_VOODOO_BANK = "mtgm"
    VOODOO_BANK_INFO = {}

    def mtgm_sysex():
        return []

    def mtr_stnd_sysex():
        return []

    def mtr_orch_sysex():
        return []

    def kq6_sysex():
        return []

    def get_bank_sysex(name):
        return []

    def bank_has_kits(name):
        return True

    def bank_label(name):
        return name or "mtgm"

    def bank_display(name):
        return (name or "MT-TO-GM")[:20]

    def bank_anima_map(name):
        return "gm"

mido.set_backend("mido.backends.rtmidi")

POLY_DEFAULT = 24
CHORD_MS_DEFAULT = 30.0
FORMAT_IDLE_SEC = 60.0
RECORD_IDLE_SEC = 10.0  # auto-split recording after this much MIDI silence
SYNC_DELAY_MAX_MS = 500.0  # clamp |offset| for --sync-delay

# Voodoo (MT-32 GM bank) pacing – real hardware is buffer-sensitive
VOODOO_SYSEX_GAP = 0.035          # seconds between DT1 SysEx during bank load
# Host/USB transfer dominates over SYSEX_GAP on multiport interfaces (e.g. M8U).
# Bench: ~75ms of wall time per unit per paced step when all units share one
# USB MIDI device — estimate uses max(gap, units × this) so the UI is honest.
VOODOO_SEC_PER_UNIT_STEP = 0.075
VOODOO_CATCHUP_MIN_GAP = 0.001    # floor gap between catch-up sends (was 8ms → too slow)
VOODOO_CATCHUP_SPEED = 8.0        # compress original spacing by this factor
VOODOO_CATCHUP_BURST = 48         # max messages drained per run-loop tick
VOODOO_CATCHUP_FAST_DEPTH = 400   # above this, ignore timing and burst

# Phase V2 – multi-MT-32 Super Munt channel map
# Partial reserve (parts 1-8 + rhythm) must sum to 32
VOODOO_PARTIAL_RESERVE = [4, 4, 4, 4, 4, 4, 3, 3, 2]
VOODOO_MIDI_CH_OFF = 16           # MT-32: 0-15 = ch1-16, 16+ = OFF

# Set master volume on MT/CM outs in Voodoo to avoid clipping on hardware.
VOODOO_MASTER_VOLUME = 70

# LA32 only has 8 pan positions (3-bit), not the 15 the manuals imply.
# Higher CC = LEFT (reversed vs GM). Bands from fresh-boot hardware tests.
# Representative wire values = mid of each measured band.
# Order: L4, L3, L2, L1, Center, R1, R2, R3
# LA32 8 positions from measured bands (forum chart). Order:
#   L4, L3, L2, L1, Center, R1, R2, R3  (higher CC = left)
# Values = mid of each band. Perceptual GM center is L1 (not the chip's
# "Center" slot) — L1 is what images best as middle on real hardware. IMHO
MT32_PAN_POSITIONS = [127, 116, 98, 80, 62, 44, 26, 8]   # L1=80 (72-89)
CM32_PAN_POSITIONS = [123, 110, 93, 76, 59, 42, 25, 8]    # L1=76 (68-84)

# Port / stream format tags (CLI values → canonical)
FORMAT_ALIASES = {
    "gm": "gm",
    "gm2": "gm2",
    "gs": "gs",
    "55": "gs55",
    "sc55": "gs55",
    "88": "gs88",
    "88vl": "gs88",
    "88pro": "gs88pro",
    "88-pro": "gs88pro",
    "880": "gs88pro",
    "88emu": "gs88pro",
    "8850": "gs8850",
    "8820": "gs8820",
    "sc8850": "gs8850",
    "sc-8850": "gs8850",
    "scva": "gs8850",
    "xg": "xg",
    "mt": "mt32",
    "mt32": "mt32",
    "mt-32": "mt32",
    "cm": "cm32",
    "cm32": "cm32",
    "cm-32": "cm32",
    "any": "any",
}
FORMAT_DISPLAY = {
    "gm": "GM",
    "gm2": "GM2",
    "gs": "GS",
    "gs55": "55",
    "gs88": "88",
    "gs88pro": "88Pro",
    "gs8850": "8850",
    "gs8820": "8820",
    "xg": "XG",
    "mt32": "MT-32",
    "cm32": "CM-32L",
    "any": "ANY",
}

# GM-family tags used when stream format is unknown (exclude pure MT-32)
GM_FAMILY_TAGS = frozenset({"gm", "gm2", "gs", "gs55", "gs88", "gs88pro", "gs8850", "gs8820", "xg"})

def format_tags_label(tags) -> str:
    """Human label for a port capability set, e.g. GS+GM2."""
    if not tags or "any" in tags:
        return "ANY"
    order = ["gs", "gs8850", "gs8820", "gs88pro", "gs88", "gs55", "xg", "gm", "gm2", "mt32"]
    parts = [FORMAT_DISPLAY[t] for t in order if t in tags]
    for t in sorted(tags):
        if t not in order:
            parts.append(FORMAT_DISPLAY.get(t, t.upper()))
    return "+".join(parts) if parts else "ANY"
# detected_format (badge) → canonical tag for Crucible matching
DETECT_TO_TAG = {
    "GM": "gm",
    "GM2": "gm2",
    "GS": "gs",
    "XG": "xg",
    "MT-32": "mt32",
}
# Base Crucible compatibility: stream tag → allowed port tags
FORMAT_COMPAT = {
    "gm": {"gm", "gm2"},   # GM always reaches GM2 ports
    "gm2": {"gm2"},
    "gs": {"gs", "gs55", "gs88", "gs88pro", "gs8850", "gs8820"},
    "xg": {"xg"},
    "mt32": {"mt32"},
}

from tables_gs import (
    GS_REVERB_MACRO,
    GS_CHORUS_MACRO,
    GS_DELAY_MACRO,
    GS_EFX_TYPES,
    ANIMA_EFX_GS,
    ANIMA_EFX_PRIORITY,
    ANIMA_SPLIT_MSB,
    ANIMA_SPLIT_LSB,
    ANIMA_SPLIT_LABEL,
    ANIMA_SPLIT_PAN_LO,
    ANIMA_SPLIT_PAN_HI,
    ANIMA_EFX_DRIVE_03,
    ANIMA_EFX_WAH,
    ANIMA_EFX_WAH_MAN,
    ANIMA_EFX_CTRL2,
    ANIMA_EFX_ROTARY,
    ANIMA_HETFIELD_PC,
    ANIMA_FILE_DIRT_TYPES,
    ANIMA_FILE_DIRT_FAMS,
    ANIMA_EFX_PAN_SLOT,
    ANIMA_EFX_PAN_PARAMS,
    ANIMA_EFX_PAN_PAIR_SPREAD,
    GS_DLY_MS,
    ANIMA_EFX_DELAY,
    ANIMA_EFX_FB_CAP_PCT,
    ANIMA_EFX_FB_PCT,
    ANIMA_EFX_FB_PCT_HELD,
    ANIMA_EFX_FB_HELD_FAMS,
    ANIMA_EFX_PITCH,
    ANIMA_EFX_PITCH_MODES,
    ANIMA_EFX_PITCH_FAM_MODES,
    ANIMA_EFX_PITCH_DEFAULT_MODES,
    ANIMA_EFX_GATE_TYPE,
    ANIMA_EFX_EXCLUSIVE,
    GS_EFX_PARAMS,
)
from tables_voices import gs8850_tone_voices
from tables_xg import (
    XG_REVERB_TYPES,
    XG_CHORUS_TYPES,
    XG_VARIATION_TYPES,
    XG_INSERTION_TYPES,
    ALCHEMY_GS_REVERB_TO_XG,
    ALCHEMY_XG_REVERB_TO_GS,
    ALCHEMY_GS_CHORUS_TO_XG,
    ALCHEMY_XG_CHORUS_TO_GS,
    ALCHEMY_XG_VARIATION_DELAY_TO_GS,
    ALCHEMY_XG_VARIATION_REVERB_TO_GS,
    ALCHEMY_XG_INS_TO_GS_EFX,
    ALCHEMY_GS_EFX_TO_XG_INS,
    ALCHEMY_XG_VARIATION_TO_GS_EFX,
)
from tables_anima import (
    MT32_REVERB_MODES,
    _MT32_DEFAULT_CAT,
    _gm_category,
    _mt32_category,
    ANIMA_BANK_SIGNATURES,
    ANIMA_BANK_NAME_HINTS,
    ANIMA_SIERRA_PC,
    ANIMA_EXPR_CATS,
    ANIMA_MOD_CATS,
    ANIMA_TONE_VARS,
)
from tables_8850 import anima_cm_to_gm, anima_tone_slots, anima_combo_ok, ANIMA_TONE_RARE


def _roland_checksum(body: list[int]) -> int:
    return (128 - (sum(body) % 128)) % 128


def _mt32_dt1(addr: tuple[int, int, int], data: list[int]) -> bytes:
    """Build MT-32/CM DT1 SysEx payload (manufacturer body, no F0/F7)."""
    body = [addr[0], addr[1], addr[2], *data]
    return bytes([0x41, 0x10, 0x16, 0x12, *body, _roland_checksum(body)])


def _voodoo_channel_plan(
    n_units: int,
    layout: str = "stripe",
) -> list[list[int]]:
    """
    Assign GM melody channels (1-9, 11-16) across n_units.

    layout:
      stripe – alternate channels across all units (default; best for 3)
      pairs  – even unit counts ≥4: mirrored 2-unit maps, notes LB across twins

    Returns list of length n_units; each entry is 1-based MIDI channels for
    that unit's parts (≤8). Rhythm (ch 10) is handled separately (all units).
    """
    if n_units < 1:
        return []
    melody = [1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16]
    layout = (layout or "stripe").lower().strip()

    if layout == "pairs" and n_units >= 4 and n_units % 2 == 0:
        # Each pair is a full 2-unit Super-Munt split; pairs mirror each other
        # so Duality can load-balance a channel across the twins.
        base: list[list[int]] = [[], []]
        for i, ch in enumerate(melody):
            base[i % 2].append(ch)
        base = [b[:8] for b in base]
        buckets: list[list[int]] = []
        for _ in range(n_units // 2):
            buckets.append(list(base[0]))
            buckets.append(list(base[1]))
        return buckets

    # stripe (and any fallback)
    buckets = [[] for _ in range(n_units)]
    for i, ch in enumerate(melody):
        buckets[i % n_units].append(ch)
    return [b[:8] for b in buckets]


def _voodoo_unit_map_sysex(melody_chs: list[int]) -> list[bytes]:
    """
    System-area SysEx for one MT-32 unit.

    Uses the same 33-byte System block shape as Roland's MTGM (addr 10 00 00)
    so real hardware accepts the write, with our equal partial reserve and
    per-unit MIDI receive channels substituted in.

    Also emits individual 1-byte channel DT1s (10 00 0D..15) as a compatibility
    follow-up — some units apply the long block more reliably this way.
    """
    # 0-based MIDI channel bytes for parts 1-8 + rhythm (ch10 = 9)
    ch_bytes: list[int] = []
    for i in range(8):
        if i < len(melody_chs):
            ch_bytes.append(max(0, min(15, melody_chs[i] - 1)))
        else:
            ch_bytes.append(VOODOO_MIDI_CH_OFF)
    ch_bytes.append(9)  # rhythm → MIDI channel 10

    # MTGM System data template (33 bytes @ 10 00 00)
    data = list([74, 2, 3, 4, 8, 4, 4, 3, 3, 3, 3, 2, 2, 0, 1, 2, 3, 4, 5, 6, 7, 9, 100, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127])
    # Partial reserve @ offset 4 (9 bytes) — must sum to 32
    data[4:13] = list(VOODOO_PARTIAL_RESERVE)
    # MIDI channels @ offset 13 (9 bytes)
    data[13:22] = ch_bytes
    assert sum(data[4:13]) == 32
    assert len(data) == 33

    msgs = [_mt32_dt1((0x10, 0x00, 0x00), data)]
    # Discrete channel writes (Part1 @ 0D … Rhythm @ 15)
    for i, chv in enumerate(ch_bytes):
        msgs.append(_mt32_dt1((0x10, 0x00, 0x0D + i), [chv]))
    return msgs


console = Console()


# ---------------------------------------------------------------------------
# Anima – automatic phrasing / humanize (Phase 1)
# Opt-in via --anima. When off, cost is a single boolean on the note path.
# ---------------------------------------------------------------------------
# Asymmetric humanize: favor lift; at high velocity, tame machine-gun peaks
ANIMA_HUMANIZE_DOWN = 3         # max velocity decrease (normal repeats)
ANIMA_HUMANIZE_UP = 7           # max velocity increase (normal repeats)
ANIMA_HUMANIZE_HOT = 120        # velocity >= this → invert bias (tame)
ANIMA_HUMANIZE_HOT_DOWN = 7     # max decrease when hot
ANIMA_HUMANIZE_HOT_UP = 3       # max increase when hot
ANIMA_REPEAT_IOI = 0.11         # seconds – near-grid repeat window
ANIMA_REPEAT_VEL_SLACK = 2      # velocities within this count as "same"
ANIMA_EXPR_FLOOR = 100          # min CC11 — velocity already carries dynamics
ANIMA_EXPR_SHAPE_CATS = frozenset({"strings", "ensemble", "brass", "pad"})
ANIMA_EXPR_SHAPE_HOLD = 0.40    # seconds held before fp / swell / sfz-cres
ANIMA_EXPR_SHAPE_FP_DIP = 0.16  # fp / sfz drop window
ANIMA_EXPR_SHAPE_NAMES = ("swell", "fp", "sfz")
ANIMA_MOD_HELD_SEC = 0.45       # default hold before light auto-mod
ANIMA_MOD_LEVEL = 18            # default gentle CC1
# Brass/wind: engage sooner + slightly stronger vibrato/breath motion
ANIMA_MOD_HELD_SEC_WIND = 0.32  # user-tuned
ANIMA_MOD_HELD_SEC_MT32 = 0.18  # MT-32 has no CC11; CC1 speaks sooner
ANIMA_MOD_LEVEL_WIND = 28
# Inserts that already LFO the pitch/time. Stacking CC1 on these is the
# ONESTOP "wild wobble" (Mod Delay + wind CC1=28, Phaser + lead CC1).
ANIMA_LFO_EFX = frozenset({
    (0x01, 0x20),  # Phaser
    (0x01, 0x23),  # Stereo Flanger
    (0x01, 0x51),  # Mod Delay
    (0x01, 0x22),  # Rotary
    (0x03, 0x00),  # Rotary Multi
    (0x11, 0x00),  # Cho/Delay
    (0x11, 0x01),  # FL/Delay
    (0x11, 0x08),  # PH/Auto Wah
    (0x01, 0x03),  # Humanizer
})
ANIMA_FILE_CC11_HOLD = 2.0      # if file sent CC11 recently, do not override
ANIMA_STATUS_GAP = 2.5          # min seconds between Anima status-line flashes
ANIMA_EXPR_DEFAULT = 127        # GM default (full) – return here on idle
ANIMA_IDLE_SEC = 0.28           # quiet time before ramping back to defaults
ANIMA_STAB_SEC = 0.14           # last note shorter than this: do not duck CC11
ANIMA_ORGAN_VOL_LO = 75         # at this CC7 (and below): ×1.4
ANIMA_ORGAN_VOL_GAIN_LO = 1.4
ANIMA_ORGAN_VOL_HI = 127        # ×1.0 — no lift at full
ANIMA_ORGAN_VOL_GAIN_HI = 1.0
ANIMA_RAMP_MOD_UP = 55          # CC1 units / second (joystick-like)
ANIMA_RAMP_MOD_DOWN = 70
ANIMA_RAMP_EXPR_UP = 80         # CC11 units / second
ANIMA_RAMP_EXPR_DOWN = 55
ANIMA_CC_QUANT = 4              # only emit CC when value moves by this
ANIMA_CC_GAP = 0.003            # min seconds between Anima CCs on a port
# Thin high-rate channel streams so DIN-speed modules (MS40 via M8U)
# are not asked to eat > MIDI 31.25 kbps (e.g. 190 pitchbends / 100ms).
STREAM_THIN_SEC = 0.008         # min gap per channel for pitch/AT/CC1
GS_88PRO_SYSEX_GAP = 0.004      # 88emu-88Pro drops burst DT1; space GS SysEx
# Strum (plucked / guitar)
ANIMA_STRUM_COLLECT = 0.010     # gather window before a stroke
ANIMA_STRUM_STEP = 0.0035       # seconds between strings
ANIMA_STRUM_JITTER = 0.003      # ±ms on a whole stroke / 0–3ms per string
ANIMA_BURST_IOI_LO = 0.070      # machine-gun train
ANIMA_BURST_IOI_HI = 0.180
ANIMA_BURST_HOLE = 0.280        # gap that ends a train
ANIMA_BURST_PICKUP = (0.004, 0.012)
ANIMA_BURST_RELEASE = (0.0, 0.0)     # off-hold raced new ons; keep mutes tight
ANIMA_STRUM_CATS = frozenset({"guitar"})
# Block-chord unroll (no extra pitches). Wider than a guitar stroke.
ANIMA_UNROLL_PCS = frozenset(
    list(range(8, 16)) + [45, 46, 104, 105, 106, 107, 108]
)  # chromatic perc + pizz/harp + sitar/banjo/shamisen/koto/kalimba
ANIMA_UNROLL_COLLECT = 0.016
ANIMA_UNROLL_STEP = 0.014
ANIMA_UNROLL_JITTER = 0.004
ANIMA_ACOUSTIC_PCS = frozenset({24, 25})  # nylon / steel — slightly more harp-like
# Harmony: chord-tones from held notes; octave if we cannot see a chord.
ANIMA_HARM_CATS = frozenset({"brass", "wind", "strings", "ensemble", "pad"})
ANIMA_HARM_VEL = 0.58
ANIMA_HARM_HOLD = 0.080  # ignore passing tones younger than this
ANIMA_HARM_TEMPLATES = (
    ((0, 4, 7, 11), "maj7"),
    ((0, 3, 7, 10), "m7"),
    ((0, 4, 7, 10), "7"),
    ((0, 3, 7, 11), "mMaj7"),
    ((0, 3, 6, 9), "dim7"),
    ((0, 3, 6, 10), "m7b5"),
    ((0, 4, 8), "aug"),
    ((0, 3, 6), "dim"),
    ((0, 4, 7), "maj"),
    ((0, 3, 7), "min"),
    ((0, 5, 7), "sus4"),
    ((0, 2, 7), "sus2"),
    ((0, 7), "pow"),
)
ANIMA_FOLEY_VEL = (36, 64)
ANIMA_FOLEY_MS = 0.070
ANIMA_FOLEY_GAP = 1.85          # phrase-level, not every riff note
ANIMA_FOLEY_GAP_JITTER = 0.45
ANIMA_FOLEY_SKIP = 0.18         # drop some hits so it is not a grid
ANIMA_FOLEY_JUMP = 5
ANIMA_FOLEY_SLIDE = 7
ANIMA_FOLEY_BEND = 380          # mild scoop (~¼–½ st at range 2)
ANIMA_FOLEY_BEND_SEC = 0.09
ANIMA_FOLEY_BEND_JUMP = 12      # only wide leaps get a bend
ANIMA_FOLEY_CC7 = 82
ANIMA_FOLEY_CC91 = 100  # a bit of hall on noise so it sits in the mix
ANIMA_FOLEY_EFX_PRE = 0.028   # EFX On before the SFX note
ANIMA_FOLEY_EFX_POST = 0.045  # keep the insert through the tail
ANIMA_FOLEY_IDLE = 8.0
ANIMA_GHOST_POLY_FRAC = 0.70   # skip ghosts when port is this full
ANIMA_GHOST_SUB_VEL = 0.55
ANIMA_GHOST_UNI_VEL = 0.72
ANIMA_GHOST_MIN_NOTE = 24      # no sub-octave below C1
ANIMA_GHOST_LOG_SEC = 2.5
# Waveform sub (Bass Multi / organ stack): GM PC, 0-based
ANIMA_WAVE_SUB_PCS = (80, 81, 38)   # Square, Saw, Synth Bass 2 (legacy fallback)
ANIMA_WAVE_SUB_CC7 = 127            # cap; actual send is 60% of source CC7
ANIMA_WAVE_SUB_VOL = 0.60           # vs the hero part's CC7
ANIMA_WAVE_SUB_VEL = 0.75           # sit under the hero, not beside it
# Named 8850 variations on Square / Saw / SynBass 1 / SynBass 2.
# slot = (cc00, cc32=4, pc 0-based, name). adapt_tone_slot shrinks for 88Pro/88/55.
ANIMA_BASS_SUB_SOFT = (
    (9, 4, 80, "Sine Lead"),
    (11, 4, 80, "Twin Sine"),
    (35, 4, 38, "OB sine Bass"),
    (19, 4, 39, "Smooth Bass"),
    (32, 4, 39, "Mild Bass"),
    (17, 4, 39, "SH101 Bass 1"),
    (18, 4, 39, "SH101 Bass 2"),
)
ANIMA_BASS_SUB_HARD = (
    (4, 4, 80, "CC Solo"),
    (10, 4, 80, "KG Lead"),
    (24, 4, 80, "Pulse Lead"),
    (8, 4, 81, "Doctor Solo"),
    (21, 4, 38, "Jungle Bass"),
    (34, 4, 38, "AtkSineBass"),
    (21, 4, 39, "Spike Bass"),
)
ANIMA_BASS_SUB_SLOTS = ANIMA_BASS_SUB_SOFT + ANIMA_BASS_SUB_HARD
# Picked / slap — already a hard front. Syn-bass click is the same idea.
ANIMA_BASS_HARD_PC = frozenset({34, 36, 37, 38, 39})
ANIMA_FOLEY_DRUM_GATE = 0.14  # skip foley this close to a ch10 hit
# SC-8850 Inst. List ~p.184 SFX: PC 121/122 + GS variations (CC32)
# (pc 0-based, bankLSB, keys)
ANIMA_FOLEY_SPEC = {
    "guitar_acoustic": (120, 0, (66, 72, 64, 60)),
    "guitar_clean":    (120, 1, (60, 62, 64)),
    "guitar_mute":     (120, 1, (60, 62)),
    "guitar_dist":     (120, 4, (60, 61)),
    "bass_electric":   (120, 2, (36, 38, 40)),
    "bass_acoustic":   (120, 2, (36, 38)),
    "bass_wide":       (120, 5, (48, 50, 52)),
    "ethnic_wind":     (121, 0, (60, 64, 67)),
    "harmonica":       (121, 0, (60, 62, 64)),
}
ANIMA_FOLEY_HOLD = 0.022

ANIMA_FOLEY_CAT = {
    "guitar": "guitar_acoustic",
    "bass": "bass_electric",
    "wind": "ethnic_wind",
    "brass": "harmonica",
}

# Phase 2.5 – one GS insertion EFX for the unit. Sticky per phrase.

ANIMA_FILE_EFX_HOLD = 1e9   # file-owned EFX lasts until GS Reset / format clear
ANIMA_SESSION_IDLE_SEC = 30.0  # quiet MIDI → drop Anima EFX/slot state
ANIMA_GAME_IDLE_SEC = 4.0      # --anima-game: shorter "new cue" silence
ANIMA_GAME_PC_BURST = 3        # PCs in a window = song setup dump
ANIMA_GAME_PC_WINDOW = 0.28
ANIMA_GAME_PC_SETTLE = 0.12
ANIMA_GAME_SNAP_DIFF = 3       # channels whose PC changed vs last cue
ANIMA_EFX_IDLE_SEC = 15.0   # keep current EFX this long after hero goes quiet
ANIMA_EFX_HOLD_SEC = 5.0    # family stays "sounding" this long after last note
ANIMA_EFX_ARM_SEC = 12.0    # unused by the 0.19 planner; kept so older logs stay readable
ANIMA_EFX_SWITCH_SEC = 1.20 # min seconds between EFX type/owner changes on one unit
ANIMA_EFX_FLUSH_GAP = 0.18  # unused; 166 flush applies on the part's own note-off
ANIMA_EFX_SETTLE_SEC = 0.060  # unused; notes are not delayed
ANIMA_EFX_DUMP_SEC = 1.0    # an unheard claim is not stolen for this long; after it a quiet unheard box can be taken
ANIMA_EFX_BURST_SEC = 0.25  # PC dump is placed once after this much PC silence (or at the first note)
ANIMA_EFX_PC_GRACE_SEC = 12.0  # mid-song PC claim: lower families leave it alone this long while unheard
ANIMA_EFX_PAN_OFF = 20        # |CC10-64| beyond this = a placed guitar (keep a pan-capable dirt type)
ANIMA_EFX_BIG_BURST = 4       # this many PC channels in one burst = song setup (short DUMP grace)
ANIMA_HARM_TOP = 96          # no chord-tone harmony ghost above C7
ANIMA_EFX_WET_SEC = 0.15      # after a type/Part On change, that part's notes use another box this long
ANIMA_EFX_CTRL_CC = 16    # 8850 EFX C.Src1 → CC16 after one SysEx bind
ANIMA_WAH_LFO_HZ = 0.55
ANIMA_ROTARY_HOLD_SEC = 0.60

class Duality:
    def __init__(
        self,
        in_name: str,
        out_names: List[str],
        mode: str = "balance",
        poly_limits: List[int] | None = None,
        chord_window_ms: float = CHORD_MS_DEFAULT,
        show_status: bool = True,
        out_formats: List[str] | None = None,
        alchemy: bool = False,
        alchemy_all: bool = False,
        crucible: bool = False,
        crucible_notes: str = "affinity",
        crucible_gm_wide: bool = False,
        input_format: str | None = None,
        scpop: bool = False,
        sync_delays_ms: list[float] | None = None,
        strict_format_detection: bool = False,
        log_path: str | None = None,
        log_verbose: bool = False,
        voodoo: bool = False,
        voodoo_bank: str = "mtgm",
        voodoo_layout: str = "stripe",
        anima: bool = False,
        anima_efx_stable: bool = False,
        anima_seed: int | None = None,
        anima_game: bool = False,
        record_dir: str | None = None,
    ):
        # One output is a valid pass-through (like-for-like / 88emu tests).
        if len(out_names) < 1:
            raise ValueError("At least 1 output port is required.")

        self.mode = mode
        self.n_ports = len(out_names)
        self._anima_cc_port_t = [0.0] * self.n_ports
        self._thin_last = {}  # (ch, kind) -> monotonic
        self.chord_window = chord_window_ms / 1000.0
        self.show_status = show_status
        # --alchemy-all implies Alchemy; fan-out to all GS/XG-capable outs
        self.alchemy_all = bool(alchemy_all)
        self.alchemy = bool(alchemy) or self.alchemy_all
        self.crucible = crucible
        self.crucible_notes = crucible_notes if crucible_notes in ("affinity", "all") else "affinity"
        self.crucible_gm_wide = bool(crucible_gm_wide)

        # Per-port format tags ("any" = untagged / receive everything)
        if out_formats is None:
            self.out_formats = [frozenset({"any"})] * self.n_ports
        else:
            if len(out_formats) != self.n_ports:
                raise ValueError("out_formats length must match number of output ports")
            self.out_formats = out_formats

        # GS part Rx channel (0–15). Defaults 1:1. YS4 stacks parts 7+16
        # on ch7 and writes Key Shift after/before the remap.
        self._gs_part_rx = list(range(16))
        self._gs_part_ks = [0x40] * 16
        self._gs_part_rel = [None] * 16
        self._ys_stack_fixed = set()
        self._ys_rel_fixed = set()
        self._ys_skip_ks = False  # Hirari revision: 88emu50 already in tune

        # New status tracking variables
        self.peak_voices = 0
        self.notes_played = 0
        self.current_chord_size = 0
        self.last_activity_time = 0.0          # for the pulse
        self.peak_chord_size = 0
        self.port_peaks = [0.0] * self.n_ports   # for VU-style peak hold (0.0–1.0)
        self.status_message = ""
        self.status_message_time = 0.0
        self.voice_counts = [0] * self.n_ports   # running note counts per port
        self.voice_display = [0.0] * 16   # lingering voice count for display
        self.drop_count = 0
        self.filtered_count = 0
        self.detected_format: str | None = None      # "GM", "GM2", "GS", "XG", "MT-32"
        self.format_pulse_time: float = 0.0          # when the format badge stops glowing
        # Sticky session format for Crucible; may be seeded by --input-format
        if input_format:
            self.detected_format = FORMAT_DISPLAY.get(input_format, input_format.upper())
            self.format_pulse_time = time.monotonic() + 2.8
        self.last_midi_time = time.monotonic()       # any MIDI activity (for 60s idle clear)
        # SCPOP: broadcast notes to format-matched ports (force via --scpop or auto-detect)
        self.scpop_mode = bool(scpop)
        self.scpop_forced = bool(scpop)
        # Anima Phase 1 – CC phrasing + velocity humanize
        self.anima_game = bool(anima_game)
        self.anima = bool(anima) or self.anima_game
        self.anima_efx_stable = bool(anima_efx_stable)
        # --anima-seed N → lock that value. --anima-seed (no N) or old
        # --anima-efx-stable → lock the first rolled seed.
        self._anima_efx_launch = None
        if anima_seed is not None and int(anima_seed) >= 0:
            self._anima_efx_seed = int(anima_seed) & 0xFFFF
            self._anima_seed_locked = True
        elif anima_efx_stable or anima_seed == -1:
            self._anima_efx_seed = None
            self._anima_seed_locked = True
        else:
            self._anima_efx_seed = None
            self._anima_seed_locked = False
        self._anima_game_pc_t = []
        self._anima_game_snap = None
        self.record_dir = record_dir
        self._rec_on = False
        self._rec_wanted = False
        self._rec_last = 0.0
        self._rec_t0 = 0.0
        self._rec_in = []
        self._rec_out = []
        self._rec_stamp = ""
        self._anima_prog = [0] * 16
        self._anima_tone_cc0 = [None] * 16
        self._anima_tone_slot = [None] * 16
        self._anima_cm64 = [False] * 16
        self._file_used_ch = [False] * 16
        self._anima_seen_cc0 = [False] * 16
        self._anima_seen_cc32 = [False] * 16
        self._file_pc = [0] * 16
        self._anima_pend_bank = [None] * 16
        self._anima_pend_bank = [None] * 16  # (cc0, cc32) waiting for a legal PC
        self._anima_last_note = [-1] * 16
        self._anima_last_vel = [-1] * 16
        self._anima_last_on = [0.0] * 16
        self._anima_last_dur = [1.0] * 16
        self._anima_file_cc11_t = [0.0] * 16
        self._anima_mod_on = set()          # (ch, note) already armed for auto-mod
        self._anima_mod_ch = [False] * 16
        self._anima_status_t = 0.0
        self._anima_stats = {"humanize": 0, "expr": 0, "mod": 0, "skip_cc11": 0}
        self._anima_stream_bank = None   # lsl3 / sq4 / kq5 from MIDI SysEx
        self._anima_stream_map = None    # gm | mt32 | sfx learned from stream
        self._anima_file_efx_t = 0.0
        self._anima_file_efx_home = None   # GS port that keeps the file insert
        self._anima_file_efx_type = None   # (msb, lsb) last file EFX type
        self._anima_file_efx_parts = set() # parts the FILE turned On
        self._anima_file_dirt = [False] * 16
        self._anima_hetfield_roll = [False] * 16
        self._anima_file_off_sent = set()
        self._anima_file_park = []  # [{port, typ, chs}] previous file types
        self._anima_efx_ours = False
        self._anima_efx_sent_sig = []
        self._anima_efx_hero = None     # channel owning the insertion slot
        self._anima_efx_key = None      # palette key currently applied
        self._anima_efx_label = ""
        self._anima_efx_sent = None     # (msb,lsb) last sent
        self._anima_efx_sound_t = {}
        self._anima_fam_played = {}     # family -> last real note (not a PC)
        self._anima_efx_burst_dirty = False  # PC dump waiting for one settle
        self._anima_efx_burst_t = 0.0
        self._anima_efx_seek_t = [0.0] * 16
        self._anima_efx_switch_t = 0.0
        self._anima_efx_pending = None  # (fam, since)
        self._anima_split_on = False
        self._anima_split_saved_pan = {}  # ch -> original CC10
        self._anima_slots = [{} for _ in range(self.n_ports)]
        self._anima_ch_port = {}  # channel -> GS port that owns its EFX
        self._anima_fam_was = [None] * 16  # last EFX family per channel (leave-dirt)
        self._anima_note_port = {}  # channel -> last port that played it (phrase pin)
        self._anima_rhythm = [False] * 16
        self._anima_rhythm[9] = True  # ch10 is always rhythm
        self._last_key_ports = {}  # (ch,note) -> ports of last sounding voice
        self._anima_efx_on = [[False] * 16 for _ in range(self.n_ports)]
        self._anima_efx_pick = {}  # (fam, port) -> (msb, lsb, label)
        # Beat tracking for delay inserts: MIDI clock first, note onsets second.
        self._tempo_clock_t = 0.0
        self._tempo_clock_iv = 0.0
        self._tempo_onsets = []        # note-on times (chords merged)
        self._tempo_beat = 0.0         # cached beat length in seconds (0 = unknown)
        self._tempo_beat_t = 0.0
        self._anima_ports = [[] for _ in range(16)]
        self._anima_cc1_cur = [0] * 16
        self._anima_cc1_tgt = [0] * 16
        self._anima_cc11_cur = [ANIMA_EXPR_DEFAULT] * 16
        self._anima_cc11_tgt = [ANIMA_EXPR_DEFAULT] * 16
        self._anima_cc11_own = [False] * 16  # Anima is driving CC11
        self._anima_expr_phrase = [False] * 16   # first note of phrase already set peak
        self._anima_expr_peak = [ANIMA_EXPR_DEFAULT] * 16
        self._anima_expr_shape = [None] * 16     # None | swell | fp | sfz
        self._anima_expr_shape_t = [0.0] * 16
        self._anima_idle_t = [0.0] * 16
        self._anima_ramp_t = time.monotonic()
        self._anima_cc_sent = [(-1, -1)] * 16   # last (cc1, cc11) actually sent
        self._anima_strum_buf = [None] * 16
        self._anima_strum_dir = [1] * 16     # 1 = down (low→high)
        self._anima_strum_n = [0] * 16       # completed strokes per ch
        self._anima_strum_q = []             # (when, port, msg)
        self._anima_efx_settle = [0.0] * self.n_ports  # port -> monotonic, notes wait
        self._anima_settle_q = []            # (when, port, msg) — no voice-count changes
        self._anima_settle_on = {}           # (port, ch, note) -> [{when, recv}, ...]
        self._anima_settle_bypass = False
        self._anima_settle_draining = False
        self._anima_strum_last_t = [0.0] * 16
        self._anima_strum_burst = [0] * 16
        self._anima_strum_off_hold = [0.0] * 16
        self._anima_foley_ch = [None] * self.n_ports   # reserved noise channel
        self._anima_foley_armed = [False] * self.n_ports
        self._anima_foley_last = 0.0
        self._anima_drum_last = 0.0
        self._anima_foley_pitch = [-1] * 16
        self._anima_foley_n = 0
        self._anima_foley_pend = None
        self._anima_ghosts = {}          # (ch, note) -> [(port, ch, note), ...]
        self._anima_ghost_sound = {}     # (ch, gnote) -> hero key sounding that pitch
        self._anima_ghost_log_t = 0.0
        self._anima_wave_sub_armed = set()  # (port, ch) already on a waveform sub patch
        self._anima_fam_ghost = {}       # "bass"|"organ" -> owning (ch, note)
        self._anima_bass_sub_choice = None  # (cc0, cc32, pc, name) for this seed
        self.format_locked = False                  # L hotkey: freeze format against SysEx overrides
        # Per-channel bank select state (for Alchemy PC mapping)
        self.bank_msb = [0] * 16
        self.bank_lsb = [0] * 16
        self._gs_efx_pending = False
        self._gs_efx_parts_on = [False] * 16
        # GS EFX slot owner: None | 'ins' | 'var'  (Insertion wins over Variation)
        self._gs_efx_owner = None
        self._gs_efx_part_explicit = False
        self._xg_var_connection = 1
        # When True, only strong identity/reset SysEx switches input format
        # (GM/GM2 On, GS Reset, XG System On, MT-32 reset). Default False = any family SysEx.
        self.strict_format_detection = bool(strict_format_detection)
        self._log_path = log_path
        self.log_verbose = bool(log_verbose)
        # Voodoo – hardware Super-Munt GM for :mt32 outs
        self.voodoo_requested = bool(voodoo)  # --voodoo startup flag
        self.voodoo_bank = (voodoo_bank or "mtgm").lower().strip()
        if _VOODOO_BANKS and self.voodoo_bank not in VOODOO_BANK_NAMES:
            self.voodoo_bank = DEFAULT_VOODOO_BANK
        layout = (voodoo_layout or "stripe").lower().strip()
        self.voodoo_layout = layout if layout in ("stripe", "pairs") else "stripe"
        self.voodoo_active = False            # GM bank is loaded / mode on
        self.voodoo_loading = False           # paced SysEx in progress
        self.voodoo_catchup = False           # draining deferred input queue
        self.voodoo_kit = "standard"          # standard | orchestra
        self._voodoo_full_bank = False        # True = MTGM+kit load; False = kit-only
        # Phase V2: MIDI ch 0-15 → list of mt32 port indices that own that channel.
        # Empty list ⇒ multi-map not active (single unit or Voodoo off).
        self._voodoo_ch_owners: list[list[int]] = [[] for _ in range(16)]
        self._voodoo_queue: list[tuple[float, object]] = []  # (recv_ts, msg)
        self._voodoo_send_list: list = []  # entries: (payload_bytes, ports|None)
        self._voodoo_send_idx = 0
        self._voodoo_next_send = 0.0
        self._voodoo_targets: list[int] = []
        self._voodoo_catchup_idx = 0
        self._voodoo_catchup_end = 0
        self._voodoo_catchup_next = 0.0
        self._voodoo_catchup_origin = 0.0
        self._voodoo_catchup_t0 = 0.0
        self._log_file = None
        if log_path:
            try:
                self._log_file = open(log_path, "a", encoding="utf-8")
                self._log_file.write(
                    f"\n--- Duality session start {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n"
                )
                self._log_file.flush()
            except OSError as e:
                console.print(f"[yellow]Could not open log {log_path!r}: {e}[/]")
                self._log_file = None
        self.status_history: list[tuple[float, str]] = []   # (timestamp, message)
        self.STATUS_HISTORY_MAX = 7
        self.STATUS_HISTORY_TTL = 10                       # seconds before a message ages out 
 
        # Per-channel controller state (0-indexed)
        self.vol = [None] * 16          # CC7 (display; may be Anima-lifted)
        self._file_vol = [None] * 16    # last file CC7 before organ lift
        self.pan = [None] * 16          # CC10 (64 = center)
        self.mod = [None] * 16          # CC1
        self.pitch = [None] * 16        # Pitch bend (display value)
        
        # Last time each controller changed (for highlight)
        self.vol_time   = [0.0] * 16
        self.pan_time   = [0.0] * 16
        self.mod_time   = [0.0] * 16
        self.pitch_time = [0.0] * 16
        
        # Last value sent to each port for deduplication
        # Key: (port_index, channel, type_key) → last value
        self.last_sent = {}

        # Per-port polyphony limits
        if poly_limits is None:
            self.poly_limits = [POLY_DEFAULT] * self.n_ports
        else:
            if len(poly_limits) == 1:
                self.poly_limits = poly_limits * self.n_ports
            elif len(poly_limits) == self.n_ports:
                self.poly_limits = poly_limits
            else:
                raise ValueError(
                    f"--poly must have 1 value or exactly {self.n_ports} values (one per port)"
                )

        # Per-port sync delay (ms). Negatives are relative offsets; we normalize
        # so the most-negative port becomes 0 and others shift later.
        raw = list(sync_delays_ms) if sync_delays_ms is not None else [0.0]
        if len(raw) == 1:
            raw = raw * self.n_ports
        elif len(raw) != self.n_ports:
            raise ValueError(
                f"--sync-delay must have 1 value or exactly {self.n_ports} values (one per port)"
            )
        clamped = []
        for v in raw:
            v = float(v)
            if v > SYNC_DELAY_MAX_MS:
                v = SYNC_DELAY_MAX_MS
            elif v < -SYNC_DELAY_MAX_MS:
                v = -SYNC_DELAY_MAX_MS
            clamped.append(v)
        base = min(clamped)  # most negative (or 0) → reference "now"
        self.sync_delays = [(v - base) / 1000.0 for v in clamped]  # seconds, ≥ 0
        self.sync_enabled = any(d > 0.0 for d in self.sync_delays)
        self._send_queue: list[tuple[float, int, object]] = []  # (send_at, port, msg)

        # Snapshot available ports before we claim any (helps diagnose loopMIDI / WinMM issues)
        try:
            avail_in = list(mido.get_input_names())
            avail_out = list(mido.get_output_names())
            self._log_line("PORT  Available inputs : " + (", ".join(avail_in) if avail_in else "(none)"))
            self._log_line("PORT  Available outputs: " + (", ".join(avail_out) if avail_out else "(none)"))
        except Exception as e:
            self._log_line(f"PORT  Could not list ports: {e}")

        self.in_name = in_name
        console.print(f"[bold cyan]Opening input[/] : {in_name}")
        try:
            self.inport = mido.open_input(in_name)
            self._log_line(f"PORT  Opened input: {in_name}")
        except Exception as e:
            self._log_line(f"PORT  FAILED input: {in_name} – {e}")
            raise

        self.outs = []
        self.port_names = out_names
        for i, name in enumerate(out_names):
            tag_disp = format_tags_label(self.out_formats[i])
            console.print(
                f"[bold cyan]Opening out {i+1}[/] : {name} "
                f"(limit {self.poly_limits[i]}, format {tag_disp})"
            )
            try:
                self.outs.append(mido.open_output(name))
                self._log_line(f"PORT  Opened out {i + 1}: {name}")
            except Exception as e:
                self._log_line(f"PORT  FAILED out {i + 1}: {name} – {e}")
                raise

        if self.record_dir:
            self._rec_wanted = True
            self._record_start("startup --record")

        # Output health / reconnect (Windows often invalidates ports when apps quit)
        self._out_offline = [False] * self.n_ports
        self._out_last_reconnect_attempt = [0.0] * self.n_ports
        self._out_last_ok = [0.0] * self.n_ports          # last successful send (monotonic)
        self._gs_syx_last = [0.0] * self.n_ports          # last GS SysEx send (88Pro pace)

        self._out_fail_logged = [False] * self.n_ports    # rate-limit fail log spam
        self._reconnect_cooldown = 2.0  # seconds between reconnect attempts per port

        # File init dump (GS Reset → first note / 3s quiet): wire-speed forward
        self._init_dump = False
        self._init_dump_last = 0.0
        self._init_dump_n = 0

        self.active: dict[tuple[int, int], dict] = {}
        self.rr_next = 0
        self.last_note_time = 0.0
        self.last_chord_port: Optional[int] = None
        self.steal_count = 0
        self.start_time = time.monotonic()

        console.print(f"[green]Mode[/]          : {self.mode}")
        console.print(f"[green]Output ports[/]  : {self.n_ports}")
        console.print(f"[green]Chord window[/]  : {chord_window_ms:.0f} ms")
        if self.sync_enabled:
            ms = [f"{d*1000:.0f}" for d in self.sync_delays]
            console.print(f"[green]Sync delay[/]    : {', '.join(ms)} ms (per port, normalized)")
        if self.crucible:
            wide = ", gm-wide" if self.crucible_gm_wide else ""
            console.print(f"[green]Crucible[/]      : on (notes={self.crucible_notes}{wide})")
        if self.alchemy:
            mode = "fanout (all GS/XG)" if self.alchemy_all else "on"
            console.print(f"[yellow]Alchemy[/]       : {mode} [BROKEN/EXPERIMENTAL]")
        if self._log_file is not None:
            verb = "verbose" if self.log_verbose else "normal"
            console.print(f"[green]Log file[/]      : {self._log_path} ({verb})")
        if self.detected_format:
            console.print(f"[green]Input format[/]  : {self.detected_format} (assumed/seeded)")
        if self.strict_format_detection:
            console.print("[green]Format detect[/] : strict (resets / System On only)")
        if self.scpop_forced:
            console.print("[green]SCPOP[/]         : forced on (--scpop) – broadcasting notes to format-matched ports")
        if self.voodoo_requested:
            console.print("[green]Voodoo[/]        : will load GM bank on :mt32 outs at start")
        console.print(
            "[green]Ready.[/] Notes will be distributed. Ctrl+C to stop + panic.\n"
            "  Hotkeys: [bold]F[/]=clear  [bold]L[/]=lock format  [bold]G[/]=GM/GM2  [bold]R[/]=GS  "
            "[bold]Y[/]=XG  [bold]M[/]=MT-32/Voodoo  [bold]B[/]=balance/rr  [bold]A[/]=Anima/game  "
            "[bold]S[/]=seed lock  [bold]C[/]=log  [bold]X[/]=reset  [bold]Q[/]=quit"
        )
        # --voodoo: seed MT-32 format (so L can lock) then begin paced GM load
        if self.voodoo_requested:
            self.detected_format = "MT-32"
            self.format_pulse_time = time.monotonic() + 2.8
            self._voodoo_begin("startup --voodoo")

    # ------------------------------------------------------------------
    

    def _log_line(self, line: str) -> None:
        """Append one line to --log file (no-op if logging disabled).

        Flush at most ~4 times/sec so dense Anima sessions cannot stall MIDI.
        """
        if getattr(self, "_log_file", None) is None or not line:
            return
        try:
            self._log_file.write(f"{time.strftime('%H:%M:%S')} {line}\n")
            now = time.monotonic()
            last = getattr(self, "_log_flush_t", 0.0)
            if now - last >= 0.25:
                self._log_file.flush()
                self._log_flush_t = now
        except OSError:
            pass

    def _clear_log(self) -> None:
        """Truncate the --log file and start a fresh section (hotkey C)."""
        if not getattr(self, "_log_path", None):
            self._set_status("No log file (--log not set)", duration=2.0)
            return
        try:
            if self._log_file is not None:
                try:
                    self._log_file.close()
                except OSError:
                    pass
                self._log_file = None
            self._log_file = open(self._log_path, "w", encoding="utf-8")
            self._log_file.write(
                f"--- Duality log cleared {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n"
            )
            self._log_file.flush()
            self._set_status(f"Log cleared: {self._log_path}", duration=2.5)
        except OSError as e:
            self._log_file = None
            self._set_status(f"Log clear failed: {e}", duration=3.0)

    def _log_msg(self, port: int | None, msg: mido.Message, note: str = "") -> None:
        """
        Log non-note MIDI of interest when --log is active.
        port: 0-based out index, or None for input/pre-route.
        """
        if getattr(self, "_log_file", None) is None:
            return
        tag = f"OUT{port + 1}" if port is not None else "IN  "
        extra = f"  {note}" if note else ""

        if msg.type == "program_change":
            ch = msg.channel + 1
            msb = self.bank_msb[msg.channel]
            lsb = self.bank_lsb[msg.channel]
            self._log_line(
                f"{tag}  ch{ch:02d}  bank {msb}/{lsb}  PC {msg.program + 1}{extra}"
            )
            return
        if msg.type == "control_change":
            ch = msg.channel + 1
            cc, val = msg.control, msg.value
            named = {
                0: "BankMSB",
                32: "BankLSB",
                1: "Mod",
                7: "Vol",
                10: "Pan",
                11: "Expr",
                64: "Sustain",
                91: "Reverb",
                93: "Chorus",
                98: "NRPN_LSB",
                99: "NRPN_MSB",
                100: "RPN_LSB",
                101: "RPN_MSB",
                6: "DataMSB",
                38: "DataLSB",
                96: "DataInc",
                97: "DataDec",
            }
            # Normal --log: bank + RPN/NRPN/data only (patch path)
            # Data entry (6/38) is high-rate in XG files — verbose only
            normal_ccs = {0, 32, 98, 99, 100, 101}
            if not self.log_verbose and cc not in normal_ccs:
                return
            # Verbose: every CC (named when known)
            name = named.get(cc)
            if name:
                self._log_line(f"{tag}  ch{ch:02d}  CC{cc} {name}={val}{extra}")
            else:
                self._log_line(f"{tag}  ch{ch:02d}  CC{cc}={val}{extra}")
            return
        if msg.type == "sysex":
            if getattr(self, "_init_dump", False) and not extra:
                return
            data = list(msg.data)[:10]
            hx = " ".join(f"{b:02X}" for b in data)
            more = "…" if len(msg.data) > 10 else ""
            self._log_line(f"{tag}  SysEx [{hx}{more}]{extra}")
            return
        if msg.type == "pitchwheel":
            if not self.log_verbose:
                return
            # Skip zero/center spam unless labeled
            if msg.pitch == 0 and not note:
                return
            ch = msg.channel + 1
            self._log_line(f"{tag}  ch{ch:02d}  Pitch {msg.pitch}{extra}")
            return

    def _set_status(self, message: str, duration: float = 5.0):
        """
        Show a temporary message in the bottom row.
        When a new message arrives, the previous one is moved into history.
        Optionally mirrors lines to --log file.
        """
        now = time.monotonic()
        if message:
            self._log_line(message)

        # Push the previous bottom message into history (if it still exists)
        if self.status_message and self.status_message != message:
            self.status_history.insert(0, (now, self.status_message))
            self.status_history = self.status_history[: self.STATUS_HISTORY_MAX]

        self.status_message = message
        self.status_message_time = now + duration

    def _make_status_history(self) -> Text:
        """Build a vertical list of recent status messages with fading."""
        now = time.monotonic()
        lines = []

        # Age out old entries
        self.status_history = [
            (ts, msg) for ts, msg in self.status_history
            if now - ts < self.STATUS_HISTORY_TTL
        ]

        for ts, msg in self.status_history:
            # Never show the exact message that is currently in the bottom row
            if msg == self.status_message and now < self.status_message_time:
                continue
            
            # Fade: full brightness → dim as it ages
            age = now - ts
            if age < 1.2:
                style = "bold yellow"
            elif age < 2.8:
                style = "yellow"
            else:
                style = "dim"

            # Truncate long messages so they don’t push the layout
            display = msg if len(msg) <= 32 else msg[:29] + "…"
            lines.append(f"[{style}]{escape(display)}[/]")

        if not lines:
            return Text("")

        return Text.from_markup("\n".join(lines))

    def _force_format(self, fmt_display: str, reason: str = "hotkey") -> None:
        """Set session format from a hotkey (G/R/Y/M, etc.). Does not lock — SysEx can still override unless L is used."""
        prev = self.detected_format
        # Manual non-MT-32 format set while Voodoo is on → leave Voodoo.
        # Explicit hotkey choice always wins over lock (lock is cleared below anyway).
        if (
            fmt_display
            and fmt_display != "MT-32"
            and (self.voodoo_active or self.voodoo_loading or self.voodoo_catchup)
        ):
            self._voodoo_exit(f"format → {fmt_display}")
        self.detected_format = fmt_display
        self.format_pulse_time = time.monotonic() + 2.8
        self.last_midi_time = time.monotonic()  # refresh idle timer
        self._warned_no_match = False
        # Changing format manually clears a previous lock (user is choosing a new set point)
        self.format_locked = False
        # Auto SCPOP only makes sense in the GS world
        if fmt_display != "GS" and self.scpop_mode and not self.scpop_forced:
            self.scpop_mode = False
        if prev == fmt_display:
            self._set_status(f"Format set {fmt_display} ({reason})", duration=2.0)
        elif prev:
            self._set_status(f"Format set: {prev} → {fmt_display} ({reason})", duration=2.5)
        else:
            self._set_status(f"Format set {fmt_display} ({reason})", duration=2.5)
        # Auto Voodoo if this set a non-MT-32 stream on an mt32-only rig
        if fmt_display != "MT-32":
            self._voodoo_maybe_auto()

    def _toggle_format_lock(self) -> None:
        """L hotkey: lock/unlock current format against SysEx detection overrides."""
        if self.detected_format is None:
            self._set_status("No format to lock – set one first (G/R/Y/M or SysEx)", duration=2.5)
            return
        self.format_locked = not self.format_locked
        if self.format_locked:
            self._set_status(
                f"Format LOCKED {self.detected_format} – SysEx will not override",
                duration=3.0,
            )
        else:
            self._set_status(
                f"Format unlocked ({self.detected_format}) – detection active again",
                duration=2.5,
            )

    def _clear_format(self, reason: str = "manual") -> None:
        """Clear sticky session format (idle timeout, hotkey, or explicit)."""
        if self.detected_format is None and not self.scpop_mode:
            # Still acknowledge hotkey / explicit clear so the UI doesn't feel dead
            self._set_status(f"Format already clear ({reason})", duration=1.5)
            return
        # Leaving a sticky format also leaves Voodoo so routing is not pinned to :mt32
        if self.voodoo_active or self.voodoo_loading or self.voodoo_catchup:
            self._voodoo_exit(f"format cleared ({reason})")
        prev = self.detected_format or "none"
        was_locked = self.format_locked
        self._anima_release_efx_lock("format clear")
        self._anima_reset_efx_seed()
        self._gs_reset_part_rx()
        self.detected_format = None
        self.format_pulse_time = 0.0
        self.format_locked = False
        # --scpop stays armed; auto-detected SCPOP is cleared with format
        lock_note = ", was locked" if was_locked else ""
        if not self.scpop_forced:
            self.scpop_mode = False
            self._set_status(f"Format cleared ({prev} → none, {reason}{lock_note})", duration=3.0)
        else:
            self.scpop_mode = True
            self._set_status(
                f"Format cleared ({prev} → none, {reason}{lock_note}); SCPOP still forced",
                duration=3.0,
            )

    def _check_format_idle(self) -> None:
        """Clear format after FORMAT_IDLE_SEC with no MIDI of any kind."""
        if self.detected_format is None:
            return
        if self.format_locked:
            return  # L lock holds through idle gaps
        if time.monotonic() - self.last_midi_time >= FORMAT_IDLE_SEC:
            self._clear_format("idle")

    def _port_matches_format(self, port_idx: int, fmt_display: str | None) -> bool:
        """
        True if this port should receive traffic for the given session format.

        Port tags are a capability set (e.g. {gs, gm2}). Untagged/"any" matches all.
        Unknown stream format (None): GM-family ports only — pure MT-32 is excluded.
        GM stream reaches gm+gm2 capabilities; --crucible-gm-wide also adds gs+xg.
        """
        tags = self.out_formats[port_idx]
        if not tags or "any" in tags:
            return True

        if fmt_display is None:
            # No detect/set/lock: do not send to pure MT-32 ports
            return bool(tags & GM_FAMILY_TAGS)

        stream_tag = DETECT_TO_TAG.get(fmt_display)
        if stream_tag is None:
            return bool(tags & GM_FAMILY_TAGS)

        allowed = set(FORMAT_COMPAT.get(stream_tag, {stream_tag}))
        # Crucible gm-wide OR Alchemy Phase 1: GM/GM2 may use GS/XG hardware natively
        if stream_tag in ("gm", "gm2") and (self.crucible_gm_wide or self.alchemy):
            allowed |= {"gs", "xg"}
        return bool(tags & allowed)

    def _port_has_alchemy_target(self, port_idx: int) -> bool:
        """Phase 1: port can participate in Alchemy (gs/xg/gm/any — not pure mt32-only)."""
        tags = self.out_formats[port_idx]
        if not tags or "any" in tags:
            return True
        return bool(tags & {"gs", "xg", "gm", "gm2"})

    def _port_target_dialect(self, port_idx: int) -> str | None:
        """Dialect to translate toward, or None = pass-through."""
        tags = self.out_formats[port_idx]
        if not tags or "any" in tags:
            return None
        has_gs = "gs" in tags
        has_xg = "xg" in tags
        if has_gs and has_xg:
            return None
        if has_gs:
            return "gs"
        if has_xg:
            return "xg"
        return None

    def _primary_note_ports(self) -> list[int]:
        """Native-affinity ports (Crucible match, or Alchemy-capable when Crucible off)."""
        if not self.crucible or self.crucible_notes == "all":
            if self.alchemy and not self.crucible:
                return [i for i in range(self.n_ports) if self._port_has_alchemy_target(i)]
            return list(range(self.n_ports))
        return [
            i for i in range(self.n_ports)
            if self._port_matches_format(i, self.detected_format)
        ]

    def _overflow_note_ports(self) -> list[int]:
        """Hybrid Alchemy: GS↔XG ports outside primary affinity (not used with --alchemy-all)."""
        if not self.alchemy or self.alchemy_all:
            return []
        if not self.crucible or self.crucible_notes == "all":
            return []
        primary = set(self._primary_note_ports())
        stream = DETECT_TO_TAG.get(self.detected_format or "", None)
        out = []
        for i in range(self.n_ports):
            if i in primary:
                continue
            tags = self.out_formats[i]
            if not tags or "any" in tags:
                continue
            if stream == "gs" and "xg" in tags:
                out.append(i)
            elif stream == "xg" and "gs" in tags:
                out.append(i)
            elif stream in ("gm", "gm2") and (tags & {"gs", "xg"}):
                out.append(i)
        return out

    def _eligible_note_ports(self) -> list[int]:
        """Ports allowed to receive notes under Crucible / Alchemy policy."""
        if self.alchemy_all:
            return [i for i in range(self.n_ports) if self._port_has_alchemy_target(i)]
        if self.alchemy and not self.crucible:
            return [i for i in range(self.n_ports) if self._port_has_alchemy_target(i)]
        if not self.crucible or self.crucible_notes == "all":
            return list(range(self.n_ports))
        primary = self._primary_note_ports()
        if primary:
            return primary
        if self.alchemy:
            return self._overflow_note_ports()
        return []

    def _is_strong_format_signal(self, data: list, fmt: str) -> bool:
        """
        True if this SysEx is a strong identity/reset for the given format.
        Used when --strict-format-detection is on.
        """
        if fmt in ("GM", "GM2"):
            # Already only matched from Universal GM/GM2 System On
            return True
        if fmt == "XG":
            # XG System On: F0 43 1n 4C 00 00 7E 00 F7
            return (
                len(data) >= 7
                and data[0] == 0x43
                and data[2] == 0x4C
                and data[3] == 0x00
                and data[4] == 0x00
                and data[5] == 0x7E
            )
        if fmt == "GS":
            # GS Reset: F0 41 1n 42 12 40 00 7F 00 [ck] F7
            return (
                len(data) >= 7
                and data[0] == 0x41
                and data[2] == 0x42
                and data[3] == 0x12
                and data[4] == 0x40
                and data[5] == 0x00
                and data[6] == 0x7F
            )
        if fmt == "MT-32":
            # MT-32 reset-all (common): DT1 addr 7F 00 00 ...
            return (
                len(data) >= 6
                and data[0] == 0x41
                and data[2] == 0x16
                and data[3] == 0x12
                and data[4] == 0x7F
            )
        return False

    def _detect_format(self, msg: mido.Message) -> None:
        """
        Detect GM / GM2 / GS / XG / MT-32 from SysEx and update sticky format.
        Default: any family SysEx can set/switch format.
        With --strict-format-detection: only strong resets / System On messages switch.
        """
        if msg.type != "sysex":
            return

        data = list(msg.data)
        if len(data) < 4:
            return

        fmt = None

        # Universal Non-Realtime → GM / GM2
        # F0 7E 7F 09 01 F7  = GM System On
        # F0 7E 7F 09 03 F7  = GM2 System On
        if data[0] == 0x7E and len(data) >= 4 and data[2] == 0x09:
            if data[3] == 0x01:
                fmt = "GM"
            elif data[3] == 0x03:
                fmt = "GM2"

        # Roland
        elif data[0] == 0x41 and len(data) >= 5:
            model = data[2]
            if model == 0x42:                     # GS (SC-55 / SC-88 / SC-8850 family)
                fmt = "GS"
            elif model == 0x16:                   # MT-32 / CM-32 / CM-64 family
                fmt = "MT-32"

        # Yamaha XG
        # Most common form: F0 43 1n 4C ...
        elif data[0] == 0x43 and len(data) >= 4 and data[2] == 0x4C:
            fmt = "XG"

        # Strict mode: incidental parameter SysEx must not flip input format
        if fmt and self.strict_format_detection and not self._is_strong_format_signal(data, fmt):
            fmt = None

        # SCPOP / SC-extended detection (broadcast notes to format-matched ports)
        #
        # Model ID 0x45 is SC-88-family, NOT SCPOP-specific — many games only
        # use it for LCD text (e.g. Noctropolis "NOCTROPOLIS AWAITS"). Require a
        # stronger signal than bare model 0x45:
        #   1) printable payload contains "SCPOP", or
        #   2) model 0x45 + large bulk DT1 that is not a short display string
        # Never auto-arm when format is locked away from GS, or when the active
        # format is clearly non-GS (GM/XG/MT-32). --scpop still forces the mode.
        if (
            data[0] == 0x41
            and len(data) >= 6
            and not self.scpop_mode
            and not self.scpop_forced
        ):
            # Respect lock / non-GS world
            active_fmt = (fmt or self.detected_format or "").upper()
            if self.format_locked and active_fmt and active_fmt != "GS":
                pass  # ignore auto-SCPOP while locked to something else
            elif active_fmt in ("GM", "GM2", "XG", "MT32", "MT-32"):
                pass
            else:
                try:
                    ascii_payload = bytes(
                        b for b in data[4:] if 32 <= b <= 126
                    ).decode("ascii", errors="ignore")
                except Exception:
                    ascii_payload = ""
                model = data[2]
                # DT1: 41 dd model 12 aa bb cc ... checksum
                addr = tuple(data[4:7]) if len(data) >= 7 and data[3] == 0x12 else ()
                body_len = max(0, len(data) - 8)  # after addr, before checksum-ish

                triggered = False
                reason = ""
                if "SCPOP" in ascii_payload.upper():
                    triggered = True
                    reason = "SCPOP banner in SysEx"
                elif model == 0x45 and data[3] == 0x12:
                    # SC-88 family dumps (user tones @ 10 xx xx) are common in
                    # game/module MIDIs and are NOT SCPOP. Only the banner
                    # string arms auto-SCPOP. Use --scpop to force.
                    pass
                if triggered:
                    self.scpop_mode = True
                    if fmt is None:
                        fmt = "GS"
                    self._set_status(
                        f"{reason} – broadcasting notes to format-matched ports",
                        duration=5.0,
                    )

        if fmt:
            if self.format_locked:
                # Locked: ignore opposing SysEx for session format (still OK to describe in status elsewhere)
                if fmt != self.detected_format:
                    # Soft notice at most once-ish via short status; keep quiet to avoid spam
                    pass
                else:
                    self.format_pulse_time = time.monotonic() + 2.8
                return
            # Non-MT-32 identity while Voodoo is on → leave Voodoo (unless locked above)
            self._voodoo_on_foreign_format(fmt)
            prev = self.detected_format
            self.detected_format = fmt
            self.format_pulse_time = time.monotonic() + 2.8
            self._warned_no_match = False
            # SCPOP is GS/SC-specific – clear when we leave that world
            # (keep if user forced via --scpop)
            if self.scpop_mode and not self.scpop_forced and fmt != "GS":
                self.scpop_mode = False
            if prev and prev != fmt:
                self._set_status(f"Format switch: {prev} → {fmt}", duration=2.5)
          
    def _describe_sysex(self, msg: mido.Message) -> str:
        """
        Return a human-readable description of a SysEx message.
        Currently focused on GS; falls back gracefully.
        """
        data = list(msg.data)
        if len(data) < 4:
            return "SysEx"

        # ----- GS (Roland Model ID 42) -----
        if data[0] == 0x41 and len(data) >= 6 and data[2] == 0x42 and data[3] == 0x12:
            # Address is the next 3 bytes
            if len(data) < 7:
                return "GS SysEx"

            aa, bb, cc = data[4], data[5], data[6]

            # GS Reset
            if aa == 0x40 and bb == 0x00 and cc == 0x7F:
                return "GS Reset"

            # Reverb Macro
            if aa == 0x40 and bb == 0x01 and cc == 0x30 and len(data) >= 8:
                val = data[7]
                name = GS_REVERB_MACRO.get(val, f"Type {val}")
                return f"GS Reverb: {name}"

            # Chorus Macro
            if aa == 0x40 and bb == 0x01 and cc == 0x38 and len(data) >= 8:
                val = data[7]
                name = GS_CHORUS_MACRO.get(val, f"Type {val}")
                return f"GS Chorus: {name}"

            # Delay Macro
            if aa == 0x40 and bb == 0x01 and cc == 0x50 and len(data) >= 8:
                val = data[7]
                name = GS_DELAY_MACRO.get(val, f"Type {val}")
                return f"GS Delay: {name}"

            # Part USE FOR RHYTHM / drum map (40 1x 15)
            if aa == 0x40 and cc == 0x15 and len(data) >= 8:
                part = self._gs_mid_to_part(bb)
                if part is not None:
                    val = data[7]
                    if val:
                        return f"GS Rhythm map {val} → Part {part + 1}"
                    return f"GS Rhythm off → Part {part + 1}"

            # EFX Type (address 40 03 00)
            if aa == 0x40 and bb == 0x03 and cc == 0x00 and len(data) >= 9:
                msb, lsb = data[7], data[8]
                name = GS_EFX_TYPES.get((msb, lsb), f"{msb:02X} {lsb:02X}")
                return f"GS EFX {name}"

            # EFX On/Off for a part (address 40 xx 22)
            if aa == 0x40 and cc == 0x22 and len(data) >= 8:
                # Use the same block map as send
                if bb == 0x40:
                    part = 10
                elif 0x41 <= bb <= 0x49:
                    part = bb - 0x40
                elif 0x4A <= bb <= 0x4F:
                    part = bb - 0x4A + 11
                else:
                    part = (bb & 0x0F) + 1
                state = "On" if data[7] == 0x01 else "Off"
                return f"GS EFX {state} → Part {part}"

            # Display string (common SC / GS address 10 00 00)
            if aa == 0x10 and bb == 0x00 and cc == 0x00 and len(data) >= 8:
                payload = data[7:-1] if len(data) > 8 else data[7:]
                text = self._extract_display_text(payload, max_len=32)
                if text:
                    return f"GS Display: {text}"
                return "GS Display"

            return "GS SysEx"

        # ----- XG (Yamaha Model ID 4C) -----
        if data[0] == 0x43 and len(data) >= 6 and data[2] == 0x4C:
            # XG has no command byte – address starts immediately
            if len(data) < 6:
                return "XG SysEx"

            aa, bb, cc = data[3], data[4], data[5]   # ← was data[4], data[5], data[6]

            # XG System On
            if aa == 0x00 and bb == 0x00 and cc == 0x7E:
                return "XG System On"

            # Reverb Type (02 01 00)
            if aa == 0x02 and bb == 0x01 and cc == 0x00 and len(data) >= 8:
                msb, lsb = data[6], data[7]
                name = (XG_REVERB_TYPES.get((msb, lsb))
                        or XG_REVERB_TYPES.get((msb, 0x00))
                        or f"{msb:02X} {lsb:02X}")
                return f"XG Reverb: {name}"

            # Chorus Type (02 01 20)
            if aa == 0x02 and bb == 0x01 and cc == 0x20 and len(data) >= 8:
                msb, lsb = data[6], data[7]
                name = (XG_CHORUS_TYPES.get((msb, lsb))
                        or XG_CHORUS_TYPES.get((msb, 0x00))
                        or f"{msb:02X} {lsb:02X}")
                return f"XG Chorus: {name}"

            # Variation Type (02 01 40)
            if aa == 0x02 and bb == 0x01 and cc == 0x40 and len(data) >= 8:
                msb, lsb = data[6], data[7]
                name = (XG_VARIATION_TYPES.get((msb, lsb))
                        or XG_VARIATION_TYPES.get((msb, 0x00))
                        or f"{msb:02X} {lsb:02X}")
                return f"XG Variation: {name}"

            # Insertion Effect 1 Type (03 00 00)
            if aa == 0x03 and bb == 0x00 and cc == 0x00 and len(data) >= 8:
                msb, lsb = data[6], data[7]
                name = (XG_INSERTION_TYPES.get((msb, lsb))
                        or XG_INSERTION_TYPES.get((msb, 0x00))
                        or f"{msb:02X} {lsb:02X}")
                return f"XG Ins1: {name}"

            # Insertion Effect 2 Type (03 01 00)
            if aa == 0x03 and bb == 0x01 and cc == 0x00 and len(data) >= 8:
                msb, lsb = data[6], data[7]
                name = (XG_INSERTION_TYPES.get((msb, lsb))
                        or XG_INSERTION_TYPES.get((msb, 0x00))
                        or f"{msb:02X} {lsb:02X}")
                return f"XG Ins2: {name}"

            # Display Letter (06 00 00) – up to 32 ASCII characters
            if aa == 0x06 and bb == 0x00 and cc == 0x00 and len(data) >= 7:
                text = self._extract_display_text(data[6:], max_len=32)
                if text:
                    return f"XG Display: {text}"
                return "XG Display"

            return "XG SysEx"

        # ----- SC-88 family / SC-ext (Roland Model ID 45) -----
        # Model 0x45 is not SCPOP-specific (LCD text, bulk dumps, etc.).
        # Only prefix "SCPOP:" when the payload actually says so.
        if data[0] == 0x41 and len(data) >= 6 and data[2] == 0x45:
            addr = tuple(data[4:7]) if len(data) >= 7 else ()
            body = data[7:-1] if len(data) > 8 else data[7:]
            printable = [b for b in body if 32 <= b <= 126]
            try:
                text_payload = bytes(printable).decode("ascii", errors="ignore").strip()
            except Exception:
                text_payload = ""
            if text_payload and "SCPOP" in text_payload.upper():
                if len(text_payload) > 40:
                    text_payload = text_payload[:37] + "…"
                return f"SCPOP: {text_payload}"
            # Real LCD string: 10 00 00 and mostly ASCII. Bitmap/animation
            # dumps (10 01 xx, ~64 bytes of pixels) are not status text.
            is_lcd = addr == (0x10, 0x00, 0x00)
            ratio = (len(printable) / len(body)) if body else 0.0
            if is_lcd and text_payload and ratio >= 0.6:
                if len(text_payload) > 40:
                    text_payload = text_payload[:37] + "…"
                return f"SC Display: {text_payload}"
            if len(data) >= 40:
                return "SC-ext bulk SysEx"
            return "SC-ext SysEx"

        # ----- MT-32 / CM-32 / CM-64 (Roland Model ID 16) -----
        if data[0] == 0x41 and len(data) >= 6 and data[2] == 0x16 and data[3] == 0x12:
            if len(data) < 7:
                return "MT-32 SysEx"

            aa, bb, cc = data[4], data[5], data[6]

            # Display message (20 00 00) – 20 characters
            if aa == 0x20 and bb == 0x00 and cc == 0x00 and len(data) >= 8:
                # data[7:] is chars + trailing Roland checksum – exclude checksum
                payload = data[7:-1] if len(data) > 8 else data[7:]
                text = self._extract_display_text(payload, max_len=20)
                if text:
                    return f"MT-32 Display: {text}"
                return "MT-32 Display"

            # System area – Reverb Mode (10 00 01)
            if aa == 0x10 and bb == 0x00 and cc == 0x01 and len(data) >= 8:
                mode = data[7]
                name = MT32_REVERB_MODES.get(mode, f"Mode {mode}")
                return f"MT-32 Reverb: {name}"

            # Reverb Time (10 00 02)
            if aa == 0x10 and bb == 0x00 and cc == 0x02 and len(data) >= 8:
                return f"MT-32 Reverb Time: {data[7]}"

            # Reverb Level (10 00 03)
            if aa == 0x10 and bb == 0x00 and cc == 0x03 and len(data) >= 8:
                return f"MT-32 Reverb Level: {data[7]}"

            # Master Volume (10 00 16) – present on MT-32 / CM-32L
            if aa == 0x10 and bb == 0x00 and cc == 0x16 and len(data) >= 8:
                return f"MT-32 Master Volume: {data[7]}"

            # Master Tune (10 00 00) – only when this is a single-parameter write
            if aa == 0x10 and bb == 0x00 and cc == 0x00 and len(data) == 9:
                # data[7] = value, data[8] = checksum typically
                return f"MT-32 Master Tune: {data[7]}"

            # Patch Temporary area (03 xx …)
            if aa == 0x03:
                part = bb + 1  # rough; parts are block-indexed
                return f"MT-32 Patch Temp (block {bb:02X})"

            # Timbre Temporary area (04 xx …)
            if aa == 0x04:
                return f"MT-32 Timbre Temp (block {bb:02X})"

            return "MT-32 SysEx"

        # Fallbacks
        if data[0] == 0x7E:
            return "GM/Universal SysEx"
        if data[0] == 0x43:
            return "XG SysEx"
        if data[0] == 0x41 and len(data) >= 3 and data[2] == 0x16:
            return "MT-32 SysEx"

        return "SysEx"
  
    def _extract_display_text(self, raw: list[int], max_len: int = 32) -> str:
        """Pull printable ASCII from SysEx payload; stop at first NUL/non-printable."""
        chars = []
        for b in raw[:max_len]:
            if b == 0x00:
                break
            if 32 <= b <= 126:
                chars.append(chr(b))
            else:
                # skip or replace non-printable
                if chars:
                    break
        text = "".join(chars).strip()
        return text if text else ""

    def _count(self, port: int) -> int:
        return sum(1 for info in self.active.values() if info["port"] == port)

    def _tone_voices(self, ch: int, port: int | None = None) -> int:
        """8850 (and mapped) hardware voices for this part's sounding tone.

        Unknown slot → 1 (MIDI-note fallback). Rhythm / missing table → 1.
        """
        ch = ch & 0x0F
        if ch == 9 or (hasattr(self, "_anima_is_rhythm") and self._anima_is_rhythm(ch)):
            return 1
        slot = None
        if self.anima and ch < len(getattr(self, "_anima_tone_slot", []) or []):
            slot = self._anima_tone_slot[ch]
        if slot and port is not None and hasattr(self, "_anima_adapt_tone_slot"):
            try:
                adapted = self._anima_adapt_tone_slot(port, slot)
                if adapted:
                    slot = adapted
            except Exception:
                pass
        if slot:
            cc0, cc32, pc = int(slot[0]) & 0x7F, int(slot[1]) & 0x7F, int(slot[2]) & 0x7F
        else:
            cc0 = int(self.bank_msb[ch]) & 0x7F if hasattr(self, "bank_msb") else 0
            cc32 = int(self.bank_lsb[ch]) & 0x7F if hasattr(self, "bank_lsb") else 0
            pc = 0
            if hasattr(self, "_anima_prog"):
                pc = int(self._anima_prog[ch]) & 0x7F
            elif hasattr(self, "_file_pc"):
                pc = int(self._file_pc[ch]) & 0x7F
        try:
            n = int(gs8850_tone_voices(cc0, cc32, pc))
        except Exception:
            n = 1
        return n if n >= 1 else 1

    def _resync_voice_counts(self):
        """Quietly rebuild counts from active notes. Never triggers steals by itself."""
        actual = [0] * self.n_ports
        for info in self.active.values():
            w = int(info.get("voices") or 1)
            ports = info.get("ports") or [info["port"]]
            for port in ports:
                if 0 <= port < self.n_ports:
                    actual[port] += w
        for key, ghosts in (self._anima_ghosts or {}).items():
            ch = key[0] if isinstance(key, tuple) else 0
            for item in ghosts:
                port, gch = item[0], item[1]
                w = item[3] if len(item) > 3 else self._tone_voices(gch, port)
                if 0 <= port < self.n_ports:
                    actual[port] += int(w or 1)
        self.voice_counts = actual
        # Optional: uncomment the next line if you want to see when it heals
        # self._set_status("Voice counts re-synchronized", duration=2.0)

    def _steal_least_important(self, port: int):
        """
        Steal the least important note on the given port.
        Priority: lowest velocity first, then oldest.
        """
        candidates = []
        for key, info in self.active.items():
            ports = info.get("ports", [info["port"]])
            if port in ports:
                candidates.append((info.get("velocity", 64), info["time"], key))

        if not candidates:
            return

        # Sort by velocity (ascending), then by time (ascending = oldest first)
        candidates.sort()

        # Steal the first one (quietest, then oldest)
        _, _, key = candidates[0]
        ch, note = key

        off = mido.Message("note_off", channel=ch, note=note, velocity=0)
        info = self.active[key]
        ports = info.get("ports", [port])
        w = int(info.get("voices") or 1)
        for p in ports:
            self._send_routed(p, off)
            self.voice_counts[p] = max(0, self.voice_counts[p] - w)
        del self.active[key]
        if self.anima:
            self._anima_ghost_kill(key)
        self.steal_count += 1

    def _choose_from_ports(self, eligible: list[int], is_chord: bool) -> int | None:
        """Utilization / RR / chord pick among a concrete eligible list."""
        if not eligible:
            return None
        counts = self.voice_counts

        if self.mode == "rr":
            for _ in range(self.n_ports):
                port = self.rr_next % self.n_ports
                self.rr_next = (self.rr_next + 1) % self.n_ports
                if port in eligible:
                    return port
            return eligible[0]

        if is_chord and self.last_chord_port is not None and self.last_chord_port in eligible:
            preferred = self.last_chord_port
            if counts[preferred] < self.poly_limits[preferred]:
                return preferred

        def _util(i: int) -> float:
            lim = self.poly_limits[i] or 1
            return counts[i] / lim

        min_util = min(_util(i) for i in eligible)
        candidates = [i for i in eligible if abs(_util(i) - min_util) < 1e-9]
        if len(candidates) > 1:
            min_count = min(counts[i] for i in candidates)
            candidates = [i for i in candidates if counts[i] == min_count]
        if len(candidates) == 1:
            return candidates[0]
        port = self.rr_next % self.n_ports
        self.rr_next = (self.rr_next + 1) % self.n_ports
        for c in candidates:
            if c == port:
                return c
        return candidates[0]

    def _choose_port(self, is_chord: bool) -> int | None:
        """
        Pick an output port. With Alchemy hybrid (--alchemy + Crucible):
        prefer primary (native) ports with free polyphony; overflow to
        GS↔XG translate targets only when primary would steal/drop.
        """
        counts = self.voice_counts
        if self.alchemy_all:
            return self._choose_from_ports(self._eligible_note_ports(), is_chord)

        primary = self._primary_note_ports()
        overflow = self._overflow_note_ports() if self.alchemy else []

        def _free(pool: list[int]) -> list[int]:
            return [i for i in pool if counts[i] < self.poly_limits[i]]

        free_primary = _free(primary)
        if free_primary:
            return self._choose_from_ports(free_primary, is_chord)

        free_overflow = _free(overflow)
        if free_overflow:
            return self._choose_from_ports(free_overflow, is_chord)

        if primary:
            return self._choose_from_ports(primary, is_chord)
        if overflow:
            return self._choose_from_ports(overflow, is_chord)
        return self._choose_from_ports(self._eligible_note_ports(), is_chord)

    def _should_send(self, port_idx: int, msg: mido.Message) -> bool:
        """
        Return True if this message should be sent to the given port.
        SysEx and important messages always return True.
        Continuous controllers / pitch bend are filtered if unchanged.
        """
        # Single-out pass-through: do not collapse repeats (like-for-like).
        if self.n_ports <= 1:
            return True
        # Always send these
        if msg.type in ("sysex", "program_change", "reset", "stop", "start", "continue", "songpos", "song_select"):
            return True

        if msg.type == "control_change":
            # Always send Bank Select, mode, and RPN/NRPN data entry
            if msg.control in (0, 32, 6, 38, 96, 97, 98, 99, 100, 101,
                               120, 121, 122, 123, 124, 125, 126, 127):
                return True
            key = (port_idx, msg.channel, "cc", msg.control)
            last = self.last_sent.get(key)
            if last == msg.value:
                self.filtered_count += 1
                return False
            self.last_sent[key] = msg.value
            return True

        if msg.type == "pitchwheel":
            key = (port_idx, msg.channel, "pitch")
            last = self.last_sent.get(key)
            if last == msg.pitch:
                self.filtered_count += 1
                return False
            self.last_sent[key] = msg.pitch
            return True

        if msg.type in ("aftertouch", "polytouch"):
            key = (port_idx, msg.channel, msg.type, getattr(msg, "note", None))
            last = self.last_sent.get(key)
            val = msg.value
            if last == val:
                self.filtered_count += 1
                return False
            self.last_sent[key] = val
            return True

        # Default: send it
        return True

    # ------------------------------------------------------------------
    def _try_reconnect_out(self, port: int, force: bool = False) -> bool:
        """
        Re-open output by original port name. Rate-limited unless force=True.
        Returns True if the port is usable afterward.
        """
        now = time.monotonic()
        if not force and (now - self._out_last_reconnect_attempt[port]) < self._reconnect_cooldown:
            return not self._out_offline[port]
        self._out_last_reconnect_attempt[port] = now

        name = self.port_names[port]
        self._log_line(f"PORT  Reconnect attempt out {port + 1}: {name}")
        # Close stale handle
        try:
            self.outs[port].close()
        except Exception as e:
            self._log_line(f"PORT  Close before reconnect out {port + 1}: {e}")

        try:
            self.outs[port] = mido.open_output(name)
            self._out_offline[port] = False
            self._out_fail_logged[port] = False
            self._log_line(f"PORT  Reconnected out {port + 1}: {name}")
            self._set_status(f"Reconnected out {port + 1}: {name}", duration=3.0)
            return True
        except Exception as e:
            self._out_offline[port] = True
            self._log_line(f"PORT  Reconnect FAILED out {port + 1}: {name} – {e}")
            self._set_status(
                f"Out {port + 1} offline ({name}) – will retry",
                duration=3.0,
            )
            return False

    def _voodoo_fanout(self, dest: list[int], payload) -> None:
        """
        Deliver one SysEx payload to one or more ports.

        When multiple ports are listed, sends run concurrently so wall-clock
        time tracks a single port — not N × serial WinMM blocking calls.
        (Each MT-32 still only receives one DT1 per paced step.)
        """
        ports = list(dest)
        if not ports:
            return
        data = list(payload) if not isinstance(payload, list) else payload
        if len(ports) == 1:
            self._safe_out_send(ports[0], mido.Message("sysex", data=data))
            return

        def _one(p: int) -> None:
            self._safe_out_send(p, mido.Message("sysex", data=list(data)))

        threads = [
            threading.Thread(target=_one, args=(p,), daemon=True)
            for p in ports
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=2.0)

    def _safe_out_send(self, port: int, msg: mido.Message) -> bool:
        """
        Send on an output port. On failure, attempt one reconnect + resend.
        Never raises — dead devices must not take down the router.
        """
        if self._out_offline[port]:
            if not self._try_reconnect_out(port):
                return False

        try:
            self.outs[port].send(msg)
            mt = getattr(msg, "type", "")
            if mt in ("program_change", "control_change"):
                # Per-unit tone as sent (bank / PC / CC7), so a bass-sub
                # reprogram can be undone for the file's own notes.
                tone = getattr(self, "_tone_port", None)
                if tone is None:
                    tone = self._tone_port = [[[None, None, None, None] for _ in range(16)] for _ in range(self.n_ports)]
                if port < len(tone):
                    slot = tone[port][msg.channel & 0x0F]
                    if mt == "program_change":
                        slot[2] = int(msg.program)
                    elif msg.control == 0:
                        slot[0] = int(msg.value)
                    elif msg.control == 32:
                        slot[1] = int(msg.value)
                    elif msg.control == 7:
                        slot[3] = int(msg.value)
            if mt == "control_change" and msg.control == 1:
                # Per-unit CC1 as sent. Anima mod swells go only to live ports,
                # so one unit can keep a stale wheel the others already reset.
                shadow = getattr(self, "_cc1_port", None)
                if shadow is None:
                    shadow = self._cc1_port = [[0] * 16 for _ in range(self.n_ports)]
                if port < len(shadow):
                    shadow[port][msg.channel & 0x0F] = int(msg.value)
            self._out_last_ok[port] = time.monotonic()
            self._out_fail_logged[port] = False
            if getattr(self, "_anima_efx_ours", False) and getattr(msg, "type", "") == "sysex":
                sig = tuple(int(b) & 0xFF for b in (msg.data or [])[:10])
                bag = list(getattr(self, "_anima_efx_sent_sig", None) or [])
                bag.append(sig)
                self._anima_efx_sent_sig = bag[-12:]
            self._record_out(port, msg)
            return True
        except Exception as e:
            name = self.port_names[port]
            if not self._out_fail_logged[port]:
                self._out_fail_logged[port] = True
                self._log_line(
                    f"PORT  Send FAIL out {port + 1} ({name}): {type(e).__name__}: {e}"
                )
            if self._try_reconnect_out(port, force=True):
                try:
                    self.outs[port].send(msg)
                    self._out_last_ok[port] = time.monotonic()
                    self._out_fail_logged[port] = False
                    return True
                except Exception as e2:
                    self._out_offline[port] = True
                    self._log_line(
                        f"PORT  Send FAIL after reconnect out {port + 1} ({name}): "
                        f"{type(e2).__name__}: {e2}"
                    )
                    return False
            return False

    def _send(self, port: int, msg: mido.Message) -> None:
        """Single outbound gate: optional per-port delay, else direct send."""
        if not self.sync_enabled:
            self._safe_out_send(port, msg)
            return
        delay = self.sync_delays[port]
        if delay <= 0.0:
            self._safe_out_send(port, msg)
            return
        # Queue a copy-ish: mido messages are small; copy() if available
        try:
            queued = msg.copy()
        except Exception:
            queued = msg
        self._send_queue.append((time.monotonic() + delay, port, queued))

    def _flush_send_queue(self) -> None:
        """Send any delayed messages that are due. No-op when sync disabled."""
        if not self.sync_enabled or not self._send_queue:
            return
        now = time.monotonic()
        due = []
        pending = []
        for item in self._send_queue:
            if item[0] <= now:
                due.append(item)
            else:
                pending.append(item)
        self._send_queue = pending
        due.sort(key=lambda x: x[0])
        for _, port, msg in due:
            self._safe_out_send(port, msg)

    def _retry_offline_ports(self) -> None:
        """Periodic background reconnect for outs marked offline."""
        if not any(self._out_offline):
            return
        now = time.monotonic()
        for i, offline in enumerate(self._out_offline):
            if offline and (now - self._out_last_reconnect_attempt[i]) >= self._reconnect_cooldown:
                self._try_reconnect_out(i)



    def _stream_dialect(self) -> str | None:
        """Canonical input dialect tag or None."""
        if not self.detected_format:
            return None
        return DETECT_TO_TAG.get(self.detected_format)


    def _gs_file_efx_kind(self, msg: mido.Message) -> str | None:
        if msg.type != "sysex":
            return None
        data = list(msg.data)
        if len(data) < 8:
            return None
        if not (data[0] == 0x41 and data[2] == 0x42 and data[3] == 0x12):
            return None
        if data[4] != 0x40:
            return None
        if data[5] == 0x03:
            return "type" if data[6] == 0x00 else "param"
        if data[6] == 0x22:
            return "part"
        return None


    def _gs_canvas_class(self, tags) -> str:
        """55 / 88 / 88pro / 8850 / none — EFX + tone map generation."""
        tags = {str(x).lower() for x in (tags or [])}
        if tags & {"gs8850", "gs8820", "sc", "8820", "8850", "scva", "sc8850", "sc-8850"}:
            return "8850"
        if tags & {"gs88pro"}:
            return "88pro"
        if tags & {"gs55"}:
            return "55"
        if tags & {"gs88"}:
            return "88"
        if tags & {"xg", "mt32", "cm32"}:
            return "none"
        # bare :gs / :gm / any → 8850-class (SCVA). Tag 88emu :gs+88pro.
        if tags & {"gs", "gm", "gm2", "any"} or not tags:
            return "8850"
        return "none"

    def _port_wants_8850_keyshift_compat(self, tags) -> bool:
        """Only 8820/8850. 88Pro/88emu must receive 40 1x 16 as the file wrote it."""
        return self._gs_canvas_class(tags) == "8850"

    def _port_has_insertion_efx(self, tags) -> bool:
        return self._gs_canvas_class(tags) in ("88pro", "8850")

    def _gs_keyshift_fixup(self, port: int, msg: mido.Message):
        """8850 last-mile: pass Key Shift unless this is the YS4 stack."""
        tags = self.out_formats[port] if port < len(self.out_formats) else set()
        if self._gs_canvas_class(tags) != "8850":
            return None
        return self._gs_8850_compat(msg, cls="8850")

    def _gs_88pro_keyshift_zero(self, msg: mido.Message):
        """File writes 40 1x 16 (88Pro vel-offset / 88emu Key Shift display).
        Also pin 40 1x 12 to 0 so sounding Key Shift cannot stick at -6.
        Does not replace 16.
        """
        if msg.type != "sysex":
            return None
        data = list(msg.data or [])
        if data and data[0] == 0xF0:
            data = data[1:]
        addr = None
        for i in range(0, max(0, len(data) - 7)):
            if data[i] == 0x41 and data[i + 2] == 0x42 and data[i + 3] == 0x12:
                if data[i + 4] == 0x40:
                    addr = (data[i + 5], data[i + 6], data[i + 7] & 0x7F)
                    break
        if addr is None:
            return None
        bb, cc, val = addr
        if not (0x10 <= bb <= 0x1F) or cc != 0x16:
            return None
        if val == 0x40:
            return None
        part = (bb - 0x10) + 1
        self._anima_feedback(
            "gs-compat",
            f"P{part} 88Pro pin Key Shift 0 (12) keep 16={val}",
            status=True,
        )
        return self._gs_dt1([0x40, bb, 0x12], [0x40])

    @staticmethod
    def _gs_bb_to_part(bb: int):
        """GS part mid-byte → 1–16. None if not a part block."""
        if bb == 0x10:
            return 10
        if 0x11 <= bb <= 0x19:
            return bb - 0x10
        if 0x1A <= bb <= 0x1F:
            return 11 + (bb - 0x1A)
        return None

    def _gs_reset_part_rx(self) -> None:
        self._gs_part_rx = list(range(16))
        self._gs_part_ks = [0x40] * 16
        self._gs_part_rel = [None] * 16
        self._ys_stack_fixed = set()
        self._ys_rel_fixed = set()
        self._ys_skip_ks = False

    @staticmethod
    def _gs_part_to_bb(part: int) -> int:
        if part == 10:
            return 0x10
        if 1 <= part <= 9:
            return 0x10 + part
        return 0x1A + (part - 11)

    def _gs_stacked_parts(self) -> set:
        """Parts that share an Rx channel with at least one other part."""
        rx = getattr(self, "_gs_part_rx", None)
        if not rx or len(rx) < 16:
            return set()
        counts = {}
        for ch in rx:
            counts[ch] = counts.get(ch, 0) + 1
        shared = {ch for ch, n in counts.items() if n >= 2}
        return {i + 1 for i, ch in enumerate(rx) if ch in shared}

    def _gs_ys_stack_apply(self) -> None:
        """After Rx remaps settle, zero Key Shift on stacked parts (8850 only).

        YS4 writes 16=−6 on parts 7 and 16 *before* part 16 is remapped
        onto ch7, so in-flight intercept always misses. Last write wins
        and this runs before the first note.
        """
        stacked = self._gs_stacked_parts()
        if not stacked:
            return
        if getattr(self, "_ys_skip_ks", False):
            self._gs_ys_release_apply()
            return
        ks = getattr(self, "_gs_part_ks", [0x40] * 16)
        ports = [
            i for i, tags in enumerate(self.out_formats)
            if self._gs_canvas_class(tags) == "8850"
        ]
        if not ports:
            return
        for part in sorted(stacked):
            if part in self._ys_stack_fixed:
                continue
            val = ks[part - 1]
            if val == 0x40:
                continue
            bb = self._gs_part_to_bb(part)
            msg = self._gs_dt1([0x40, bb, 0x16], [0x40])
            for i in ports:
                self._send(i, msg)
            self._ys_stack_fixed.add(part)
            self._gs_part_ks[part - 1] = 0x40
            self._log_line(f"GS YS-stack: P{part} KS {val - 64:+d} → 0 after remap")
            self._set_status(
                f"YS stack: part {part} Key Shift 0 (8850)",
                duration=2.0,
            )
        self._gs_ys_release_apply()

    def _gs_ys_release_apply(self) -> None:
        """YS4 slams TVA release (40 1x 1F) to 1 on Hyper Alto.

        That patch sustains normally on 8850; only this dump does it.
        Restore default 64 when the YS stack is in effect.
        """
        if not self._gs_stacked_parts():
            return
        ports = [
            i for i, tags in enumerate(self.out_formats)
            if self._gs_canvas_class(tags) == "8850"
        ]
        if not ports:
            return
        rel = getattr(self, "_gs_part_rel", None) or [None] * 16
        for part in range(1, 17):
            if part in self._ys_rel_fixed:
                continue
            val = rel[part - 1]
            if val is None or val >= 16:
                continue
            bb = self._gs_part_to_bb(part)
            msg = self._gs_dt1([0x40, bb, 0x1F], [0x40])
            for i in ports:
                self._send(i, msg)
            self._ys_rel_fixed.add(part)
            self._gs_part_rel[part - 1] = 0x40
            self._log_line(f"GS YS-stack: P{part} release {val} → 64 (8850)")
            self._set_status(
                f"YS stack: part {part} release 64 (8850)",
                duration=2.0,
            )

    def _gs_observe_part_dt1(self, msg: mido.Message) -> None:
        """Track part Rx (40 1x 02), Key Shift (40 1x 16), GS Reset."""
        if msg.type != "sysex":
            return
        data = list(msg.data or [])
        if data and data[0] == 0xF0:
            data = data[1:]
        if len(data) < 8:
            return
        if data[0] != 0x41 or data[2] != 0x42 or data[3] != 0x12:
            return
        aa, bb, cc, val = data[4], data[5], data[6], data[7] & 0x7F
        if aa == 0x40 and bb == 0x00 and cc == 0x7F:
            self._gs_reset_part_rx()
            return
        # Hirari SC-88Pro revision LCD. That dump still writes 16=−6 but
        # 88emu50 already plays the lead in tune; neutralizing KS then
        # pushes it +6. Keep the Hyper Alto release fix only.
        if aa == 0x41 and bb in (0x00, 0x10) and cc == 0x00:
            raw = bytes(data[7:-1])
            if b"Hirari" in raw or b"HIRARI" in raw:
                if not self._ys_skip_ks:
                    self._ys_skip_ks = True
                    self._log_line("GS YS-stack: Hirari dump — skip KS neutralize")
            return
        if aa != 0x40:
            return
        part = self._gs_bb_to_part(bb)
        if part is None:
            return
        if cc == 0x02:
            self._gs_part_rx[part - 1] = val & 0x0F
            # KS neutralize waits for dump end so Hirari LCD can set skip.
        elif cc == 0x16:
            self._gs_part_ks[part - 1] = val
        elif cc == 0x1F:
            # Store only. Sending 64 here is overwritten when this
            # same message is forwarded later in process().
            self._gs_part_rel[part - 1] = val

    def _gs_8850_compat(self, msg: mido.Message, cls: str = "8850"):
        """8850 last-mile: replace slammed TVA release while YS stack is on."""
        if cls != "8850" or msg.type != "sysex":
            return None
        data = list(msg.data or [])
        if data and data[0] == 0xF0:
            data = data[1:]
        if len(data) < 8:
            return None
        if data[0] != 0x41 or data[2] != 0x42 or data[3] != 0x12:
            return None
        aa, bb, cc, val = data[4], data[5], data[6], data[7] & 0x7F
        if aa != 0x40 or cc != 0x1F:
            return None
        part = self._gs_bb_to_part(bb)
        if part is None or val >= 16:
            return None
        if not self._gs_stacked_parts():
            return None
        self._log_line(f"GS YS-stack: P{part} release {val} → 64 (last-mile)")
        self._ys_rel_fixed.add(part)
        self._gs_part_rel[part - 1] = 0x40
        return [self._gs_dt1([0x40, bb, 0x1F], [0x40])]

    def _gs_dt1(self, addr: list[int], values: list[int]) -> mido.Message:
        """Build Roland GS DT1 SysEx with checksum."""
        body = list(addr) + list(values)
        ck = _roland_checksum(body)
        return mido.Message("sysex", data=[0x41, 0x10, 0x42, 0x12, *body, ck])

    def _xg_param(self, addr: list[int], values: list[int]) -> mido.Message:
        """Build Yamaha XG parameter SysEx (device 0x10)."""
        return mido.Message("sysex", data=[0x43, 0x10, 0x4C, *addr, *values])

    def _gs_silence_delay(self) -> list:
        """
        Zero GS Delay times/feedback/levels so ER/reverb maps do not leave a
        long echo tail from a previous Delay macro or sticky SC state.
        """
        return [
            self._gs_dt1([0x40, 0x01, 0x50], [0x00]),  # Delay type 0
            self._gs_dt1([0x40, 0x01, 0x52], [0x00]),  # time C
            self._gs_dt1([0x40, 0x01, 0x53], [0x00]),  # time L
            self._gs_dt1([0x40, 0x01, 0x54], [0x00]),  # time R
            self._gs_dt1([0x40, 0x01, 0x55], [0x00]),  # level C
            self._gs_dt1([0x40, 0x01, 0x56], [0x00]),  # feedback
            self._gs_dt1([0x40, 0x01, 0x5A], [0x00]),  # delay send→rev (common)
        ]

    def _gs_efx_enable_all_parts(self) -> list:
        """Turn GS EFX on for parts 1–16 (correct GS part mid encoding)."""
        return [
            self._gs_dt1([0x40, self._gs_efx_part_mid(p), 0x22], [0x01])
            for p in range(16)
        ]

    @staticmethod
    def _gs_part_mid(part: int) -> int:
        """Classic GS PART mid: 1–9 → 11–19, 10 → 10, 11–16 → 1A–1F."""
        part = int(part) & 0x0F
        if part < 9:
            return 0x11 + part
        if part == 9:
            return 0x10
        return 0x1A + (part - 10)

    @staticmethod
    def _gs_efx_part_mid(part: int) -> int:
        """SC-8850 EFX On/Off: Part 1–9 → 41–49, Part 10 → 40, 11–16 → 4A–4F."""
        cm = Duality._gs_part_mid(part)
        if cm == 0x10:
            return 0x40
        return 0x40 + (cm & 0x0F)

    @staticmethod
    def _gs_mid_to_part(mid: int):
        """GS PART mid → part index 0–15 (classic 1x and EFX 4x)."""
        mid = int(mid) & 0xFF
        if mid == 0x40 or mid == 0x10:
            return 9
        if 0x41 <= mid <= 0x49:
            return mid - 0x41
        if 0x4A <= mid <= 0x4F:
            return mid - 0x4A + 10
        if 0x11 <= mid <= 0x19:
            return mid - 0x11
        if 0x1A <= mid <= 0x1F:
            return mid - 0x1A + 10
        return None

    def _maybe_gs_efx_on_note(self, port: int, msg: mido.Message) -> None:
        """
        Fallback when XG sets Insertion but never sends PART.
        Enable GS EFX on the *first* note channel only (not every channel).
        """
        if not self.alchemy:
            return
        if self._port_target_dialect(port) != "gs":
            return
        if self._gs_efx_owner != "ins":
            return
        if self._gs_efx_part_explicit:
            return
        # Already assigned a fallback part this Ins session
        if any(self._gs_efx_parts_on):
            return
        if msg.type != "note_on" or msg.velocity == 0:
            return
        ch = msg.channel
        for m in self._gs_efx_on_part(ch):
            self._send(port, m)
            if self._log_file is not None:
                data = list(m.data) if hasattr(m, "data") else []
                hx = " ".join(f"{b:02X}" for b in data[:12])
                self._log_line(
                    f"OUT{port + 1}  SysEx [{hx}]  "
                    f"Alchemy: GS EFX on ch{ch + 1} (first-note fallback)"
                )
        self._set_status(
            f"Alchemy: GS EFX on ch{ch + 1} only (first-note fallback)",
            duration=2.5,
        )

    def _gs_efx_on_part(self, part: int) -> list:
        """Enable GS EFX for one part (0–15). Idempotent per-session flags."""
        if part < 0 or part > 15:
            return []
        if self._gs_efx_parts_on[part]:
            return []
        self._gs_efx_parts_on[part] = True
        mid = self._gs_efx_part_mid(part)
        return [self._gs_dt1([0x40, mid, 0x22], [0x01])]

    def _translate_sysex(self, msg: mido.Message, target: str) -> tuple:
        """
        Phase 1 GS ↔ XG SysEx translation.
        Returns (message_or_None, status_label_or_None).
        """
        data = list(msg.data)
        stream = self._stream_dialect()
        if stream is None or stream == target:
            return msg, None
        if stream in ("gm", "gm2") and target in ("gs", "xg"):
            return msg, None

        # --- GS → XG ---
        if stream == "gs" and target == "xg":
            if (
                len(data) >= 7
                and data[0] == 0x41
                and data[2] == 0x42
                and data[3] == 0x12
                and data[4] == 0x40
                and data[5] == 0x00
                and data[6] == 0x7F
            ):
                return (
                    mido.Message("sysex", data=[0x43, 0x10, 0x4C, 0x00, 0x00, 0x7E, 0x00]),
                    "GS Reset → XG System On",
                )
            # GS Reverb Macro: 40 01 30 vv
            if (
                len(data) >= 8
                and data[0] == 0x41
                and data[2] == 0x42
                and data[3] == 0x12
                and data[4] == 0x40
                and data[5] == 0x01
                and data[6] == 0x30
            ):
                vv = data[7]
                pair = ALCHEMY_GS_REVERB_TO_XG.get(vv, (0x02, 0x00))
                return (
                    self._xg_param([0x02, 0x01, 0x00], [pair[0], pair[1]]),
                    f"GS Reverb {vv} → XG {pair[0]:02X}/{pair[1]:02X}",
                )
            # GS Chorus Macro: 40 01 38 vv
            if (
                len(data) >= 8
                and data[0] == 0x41
                and data[2] == 0x42
                and data[3] == 0x12
                and data[4] == 0x40
                and data[5] == 0x01
                and data[6] == 0x38
            ):
                vv = data[7]
                pair = ALCHEMY_GS_CHORUS_TO_XG.get(vv, (0x41, 0x00))
                return (
                    self._xg_param([0x02, 0x01, 0x20], [pair[0], pair[1]]),
                    f"GS Chorus {vv} → XG {pair[0]:02X}/{pair[1]:02X}",
                )
            # GS EFX type: 40 03 00 mm ll → XG Insertion 1 type
            if (
                len(data) >= 9
                and data[0] == 0x41
                and data[2] == 0x42
                and data[3] == 0x12
                and data[4] == 0x40
                and data[5] == 0x03
                and data[6] == 0x00
            ):
                mm, ll = data[7], data[8]
                pair = ALCHEMY_GS_EFX_TO_XG_INS.get((mm, ll))
                if pair is None:
                    return None, f"GS EFX {mm:02X}/{ll:02X} unmapped"
                return (
                    self._xg_param([0x03, 0x00, 0x00], [pair[0], pair[1]]),
                    f"GS EFX {mm:02X}/{ll:02X} → XG Ins {pair[0]:02X}/{pair[1]:02X}",
                )
            # GS EFX On/Off for a part: 40 <mid> 22 vv
            if (
                len(data) >= 8
                and data[0] == 0x41
                and data[2] == 0x42
                and data[3] == 0x12
                and data[4] == 0x40
                and data[6] == 0x22
            ):
                mid = data[5]
                part = self._gs_mid_to_part(mid)
                if part is None:
                    return None, f"GS EFX part mid {mid:02X} unmapped"
                on = data[7] == 0x01
                if on:
                    msgs = [
                        self._xg_param([0x03, 0x00, 0x50], [part]),
                        self._xg_param([0x02, 0x01, 0x5A], [0x00]),  # Var Connection=INSERTION
                    ]
                    return (
                        msgs,
                        f"GS EFX On part {part + 1} → XG Ins PART {part + 1}",
                    )
                return (
                    self._xg_param([0x03, 0x00, 0x50], [0x7F]),
                    f"GS EFX Off part {part + 1} → XG Ins PART OFF",
                )
            if data[0] == 0x41 and len(data) >= 3 and data[2] == 0x42:
                return None, None
            return msg, None

        # --- XG → GS ---
        if stream == "xg" and target == "gs":
            if (
                len(data) >= 7
                and data[0] == 0x43
                and data[2] == 0x4C
                and data[3] == 0x00
                and data[4] == 0x00
                and data[5] == 0x7E
            ):
                msgs = [self._gs_dt1([0x40, 0x00, 0x7F], [0x00])]
                msgs.extend(self._gs_silence_delay())
                self._gs_efx_pending = False
                self._gs_efx_parts_on = [False] * 16
                self._gs_efx_owner = None
                self._gs_efx_part_explicit = False
                self._xg_var_connection = 1
                return (msgs, "XG System On → GS Reset + Delay clear")
            # XG Reverb type: 02 01 00 mm ll
            if (
                len(data) >= 8
                and data[0] == 0x43
                and data[2] == 0x4C
                and data[3] == 0x02
                and data[4] == 0x01
                and data[5] == 0x00
            ):
                mm, ll = data[6], data[7]
                vv = ALCHEMY_XG_REVERB_TO_GS.get((mm, ll), 0)
                return (
                    self._gs_dt1([0x40, 0x01, 0x30], [vv]),
                    f"XG Reverb {mm:02X}/{ll:02X} → GS macro {vv}",
                )
            # XG Chorus type: 02 01 20 mm ll
            if (
                len(data) >= 8
                and data[0] == 0x43
                and data[2] == 0x4C
                and data[3] == 0x02
                and data[4] == 0x01
                and data[5] == 0x20
            ):
                mm, ll = data[6], data[7]
                vv = ALCHEMY_XG_CHORUS_TO_GS.get((mm, ll), 0)
                return (
                    self._gs_dt1([0x40, 0x01, 0x38], [vv]),
                    f"XG Chorus {mm:02X}/{ll:02X} → GS macro {vv}",
                )
            # XG Variation Connection: 02 01 5A vv (0=INSERTION, 1=SYSTEM)
            if (
                len(data) >= 7
                and data[0] == 0x43
                and data[2] == 0x4C
                and data[3] == 0x02
                and data[4] == 0x01
                and data[5] == 0x5A
            ):
                self._xg_var_connection = data[6]
                return (
                    None,
                    f"XG Variation Connection={'SYSTEM' if data[6] else 'INSERTION'}",
                )
            # XG Variation type: 02 01 40 mm ll
            if (
                len(data) >= 8
                and data[0] == 0x43
                and data[2] == 0x4C
                and data[3] == 0x02
                and data[4] == 0x01
                and data[5] == 0x40
            ):
                mm, ll = data[6], data[7]
                # True delay family → short GS Delay (system delay path)
                if (mm, ll) in ALCHEMY_XG_VARIATION_DELAY_TO_GS:
                    vv = ALCHEMY_XG_VARIATION_DELAY_TO_GS[(mm, ll)]
                    msgs = [
                        self._gs_dt1([0x40, 0x01, 0x50], [vv]),
                        self._gs_dt1([0x40, 0x01, 0x52], [0x18]),
                        self._gs_dt1([0x40, 0x01, 0x53], [0x14]),
                        self._gs_dt1([0x40, 0x01, 0x54], [0x14]),
                        self._gs_dt1([0x40, 0x01, 0x56], [0x0C]),
                    ]
                    return (
                        msgs,
                        f"XG Variation {mm:02X}/{ll:02X} → GS Delay macro {vv} (short)",
                    )
                # Space-like Variation
                if (mm, ll) in ALCHEMY_XG_VARIATION_TO_GS_EFX:
                    # SYSTEM connection (default / this PSR) → system reverb, keep EFX free
                    if getattr(self, "_xg_var_connection", 1) == 1:
                        vv = ALCHEMY_XG_VARIATION_REVERB_TO_GS.get((mm, ll), 0)
                        msgs = self._gs_silence_delay()
                        msgs.append(self._gs_dt1([0x40, 0x01, 0x30], [vv]))
                        return (
                            msgs,
                            f"XG Variation {mm:02X}/{ll:02X} (SYSTEM) → GS Room {vv}",
                        )
                    if self._gs_efx_owner == "ins":
                        return (
                            None,
                            f"XG Variation {mm:02X}/{ll:02X} skipped (EFX owned by Insertion)",
                        )
                    efx = ALCHEMY_XG_VARIATION_TO_GS_EFX[(mm, ll)]
                    self._gs_efx_owner = "var"
                    self._gs_efx_pending = True
                    msgs = self._gs_silence_delay()
                    msgs.append(self._gs_dt1([0x40, 0x03, 0x00], [efx[0], efx[1]]))
                    return (
                        msgs,
                        f"XG Variation {mm:02X}/{ll:02X} → GS EFX {efx[0]:02X}/{efx[1]:02X}",
                    )
                return None, None
            # XG Variation Part Number: 02 01 5B vv (0..63 part, 127=off)
            if (
                len(data) >= 7
                and data[0] == 0x43
                and data[2] == 0x4C
                and data[3] == 0x02
                and data[4] == 0x01
                and data[5] == 0x5B
            ):
                part = data[6]
                if part >= 127:
                    return None, None
                if part > 15:
                    part = part % 16  # map higher parts into 1–16 for GS
                self._gs_efx_part_explicit = True
                msgs = self._gs_efx_on_part(part)
                return (msgs, f"XG Variation part {part + 1} → GS EFX on")
            # XG Insertion 1 type: 03 00 00 mm ll — amp/drive → GS EFX (priority)
            if (
                len(data) >= 8
                and data[0] == 0x43
                and data[2] == 0x4C
                and data[3] == 0x03
                and data[4] == 0x00
                and data[5] == 0x00
            ):
                mm, ll = data[6], data[7]
                efx = ALCHEMY_XG_INS_TO_GS_EFX.get((mm, ll))
                if efx is not None:
                    self._gs_efx_owner = "ins"
                    self._gs_efx_pending = True
                    self._gs_efx_parts_on = [False] * 16
                    return (
                        self._gs_dt1([0x40, 0x03, 0x00], [efx[0], efx[1]]),
                        f"XG Ins {mm:02X}/{ll:02X} → GS EFX {efx[0]:02X}/{efx[1]:02X}",
                    )
                return None, None
            # XG Insertion 1 PART: 03 00 50 vv (0..3 on some, often 0..15; 127=off)
            if (
                len(data) >= 7
                and data[0] == 0x43
                and data[2] == 0x4C
                and data[3] == 0x03
                and data[4] == 0x00
                and data[5] == 0x50
            ):
                part = data[6]
                if part >= 127:
                    return None, None
                if part > 15:
                    part = part % 16
                self._gs_efx_part_explicit = True
                msgs = self._gs_efx_on_part(part)
                return (msgs, f"XG Ins part {part + 1} → GS EFX on")
            # XG Multi Part Variation Send: 08 nn 14 vv — high send ⇒ enable EFX on that part
            if (
                len(data) >= 7
                and data[0] == 0x43
                and data[2] == 0x4C
                and data[3] == 0x08
                and data[5] == 0x14
            ):
                nn, vv = data[4], data[6]
                if vv > 0 and nn <= 15 and self._gs_efx_owner in ("var", "ins", None):
                    # Only useful once an EFX type is set; still enable part for later
                    self._gs_efx_part_explicit = True
                    msgs = self._gs_efx_on_part(nn)
                    return (msgs, f"XG VarSend part {nn + 1}={vv} → GS EFX on")
                return None, None
            if data[0] == 0x43 and len(data) >= 3 and data[2] == 0x4C:
                return None, None
            return msg, None

        return msg, None

    def _translate_program(self, msg: mido.Message, target: str) -> tuple:
        """
        Best-effort program/bank mapping GS ↔ XG.
        Returns (msg_or_list_of_msgs, label). list = bank select(s) + PC to send in order.
        """
        stream = self._stream_dialect()
        ch = msg.channel
        pc = msg.program
        msb = self.bank_msb[ch]
        lsb = self.bank_lsb[ch]

        if stream is None or stream == target:
            return msg, None
        if stream in ("gm", "gm2") and target in ("gs", "xg"):
            return msg, None

        # GS → XG: capital tones (MSB 0) pass; variations → GM capital PC on MSB/LSB 0
        if stream == "gs" and target == "xg":
            if msb == 0 and lsb == 0:
                return msg, None
            # Variation / map: fall back to capital-style on XG melody bank 0
            msgs = [
                mido.Message("control_change", channel=ch, control=0, value=0),
                mido.Message("control_change", channel=ch, control=32, value=0),
                mido.Message("program_change", channel=ch, program=pc),
            ]
            return msgs, f"GS bank {msb}/{lsb} PC {pc + 1} → XG GM bank PC {pc + 1}"

        # XG → GS: melody bank 0 pass; other banks → GS capital (MSB 0) same PC
        if stream == "xg" and target == "gs":
            # XG drum banks 126/127 — pass through PC only with GS drum-ish bank 0
            # (full drum-channel policy is a later Alchemy item)
            if msb in (126, 127):
                msgs = [
                    mido.Message("control_change", channel=ch, control=0, value=0),
                    mido.Message("control_change", channel=ch, control=32, value=0),
                    mido.Message("program_change", channel=ch, program=pc),
                ]
                return msgs, f"XG drum bank {msb} PC {pc + 1} → GS PC {pc + 1} (best-effort)"
            if msb == 0 and lsb == 0:
                return msg, None
            msgs = [
                mido.Message("control_change", channel=ch, control=0, value=0),
                mido.Message("control_change", channel=ch, control=32, value=0),
                mido.Message("program_change", channel=ch, program=pc),
            ]
            return msgs, f"XG bank {msb}/{lsb} PC {pc + 1} → GS capital PC {pc + 1}"

        return msg, None

    def _alchemy_prepare(self, msg: mido.Message, port: int):
        """
        Prepare message(s) for a specific out.
        Returns msg | list[msg] | None (skip).
        """
        if not self.alchemy:
            return msg
        target = self._port_target_dialect(port)
        if target is None:
            return msg

        stream = self._stream_dialect()
        if stream is None or stream == target:
            return msg
        if stream in ("gm", "gm2") and target in ("gs", "xg"):
            return msg

        if msg.type == "sysex":
            out, label = self._translate_sysex(msg, target)
            if label:
                self._alchemy_last_label = label
            return out

        if msg.type == "program_change":
            out, label = self._translate_program(msg, target)
            if label:
                self._alchemy_last_label = label
            # EFX On is driven by XG part-assign SysEx (Ins PART / Var PART / VarSend),
            # not by every Program Change (that was flooding all parts).
            return out

        # CCs: do not pass raw bank select to a foreign dialect (PC path emits banks)
        if msg.type == "control_change":
            if msg.control in (0, 32):
                # Opposite dialect: skip; same dialect / GM: pass
                return None
            return msg

        return msg

    def _la_port_kind(self, port: int) -> str | None:
        """Return 'mt32', 'cm32', or None for pan-table selection."""
        tags = self.out_formats[port] if port < len(self.out_formats) else None
        if not tags:
            return None
        if "cm32" in tags or "cm" in tags:
            return "cm32"
        if "mt32" in tags:
            return "mt32"
        return None

    def _should_map_mt32_pan(self, port: int) -> bool:
        """
        Apply GM→LA pan mapping when feeding non-native material to :mt32/:cm32.
        Native MT-32 streams keep author pan as-is.
        """
        if self._la_port_kind(port) is None:
            return False
        if self.voodoo_active:
            return True
        fmt = self.detected_format
        return bool(fmt) and fmt != "MT-32"

    @staticmethod
    def _gm_pan_to_la(
        gm_value: int,
        positions: list[int],
        channel: int = 0,
    ) -> int:
        """
        GM CC10 (0–127, center 64) → one of 8 LA32 pan wire values.

        LA32: 8 positions only; higher CC = left (reversed vs GM).
        `positions` = [L4, L3, L2, L1, Center, R1, R2, R3] from measured bands.

        No whole-range skew toward L1 — equal bins across the pot.
        Near GM center (56–72) there is no true mono detent; alternate
        L1 and chip-Center by channel parity so the mix averages middle.
        (Rhythm ch10 excluded upstream.)
        """
        gm = max(0, min(127, int(gm_value)))
        idx = min(7, gm // 16)
        if 56 <= gm <= 72:
            idx = 3 if (channel & 1) == 0 else 4
        return positions[idx]

    def _apply_mt32_pan_invert(self, port: int, msg: mido.Message) -> mido.Message:
        """Call-site name kept; maps GM pan onto LA32 8-position tables."""
        if msg.type != "control_change" or msg.control != 10:
            return msg
        # Rhythm (ch10) ignores pan on MT-32/CM — leave CC10 alone, and do not
        # consume an even/odd slot in the artistic center split.
        if msg.channel == 9:
            return msg
        if not self._should_map_mt32_pan(port):
            return msg
        kind = self._la_port_kind(port)
        positions = CM32_PAN_POSITIONS if kind == "cm32" else MT32_PAN_POSITIONS
        val = self._gm_pan_to_la(msg.value, positions, channel=msg.channel)
        try:
            return msg.copy(value=val)
        except Exception:
            return mido.Message(
                "control_change",
                channel=msg.channel,
                control=10,
                value=val,
            )

    def _send_routed(self, port: int, msg: mido.Message) -> None:
        """Send with optional Alchemy prepare (skip if translation says None)."""
        self._alchemy_last_label = None
        out_msg = self._alchemy_prepare(msg, port)
        if out_msg is None:
            if msg.type == "sysex":
                label = getattr(self, "_alchemy_last_label", None)
                if label:
                    self._set_status(f"Alchemy: {label} → out {port + 1}", duration=2.5)
                else:
                    self._set_status(
                        f"Alchemy: skipped SysEx → out {port + 1} (no Phase-1 map)",
                        duration=2.0,
                    )
            elif (
                self._log_file is not None
                and msg.type == "program_change"
            ):
                self._log_msg(port, msg, note="SKIP")
            # Bank CC suppressed on foreign dialect: silent (expected)
            return
        label = getattr(self, "_alchemy_last_label", None)
        note = f"Alchemy: {label}" if label else ("pass" if self.alchemy else "")
        if isinstance(out_msg, list):
            for m in out_msg:
                m = self._apply_mt32_pan_invert(port, m)
                fixed = self._gs_keyshift_fixup(port, m)
                if fixed is None:
                    self._send(port, m)
                    self._log_msg(port, m, note=note or "Alchemy multi")
                else:
                    for fm in fixed:
                        self._send(port, fm)
                        self._log_msg(port, fm, note="ks-fix")
            if label:
                self._set_status(f"Alchemy: {label} → out {port + 1}", duration=2.5)
            return
        out_msg = self._apply_mt32_pan_invert(port, out_msg)
        fixed = self._gs_keyshift_fixup(port, out_msg)
        if fixed is None:
            self._send(port, out_msg)
        else:
            for m in fixed:
                self._send(port, m)
                if m is not out_msg:
                    self._log_msg(port, m, note="ks-fix")
            return
        # Log non-notes on the wire (mapped or pass-through)
        if out_msg.type != "note_on" and out_msg.type != "note_off":
            self._log_msg(port, out_msg, note=note)
        if label:
            self._set_status(f"Alchemy: {label} → out {port + 1}", duration=2.5)


    # ------------------------------------------------------------------
    # Voodoo – Super-Munt-style GM bank for MT-32 hardware
    # ------------------------------------------------------------------
    def _mt32_port_indices(self) -> list[int]:
        """Ports whose capability tags include mt32 or cm32 (LA family)."""
        out = []
        for i, tags in enumerate(self.out_formats):
            if tags and (tags & {"mt32", "cm32"}):
                out.append(i)
        return out

    def _mt32_display_msg(self, text: str) -> mido.Message:
        """
        Build MT-32 / CM-32 display SysEx (addr 20 00 00, 20 ASCII chars).
        Used for Voodoo status lines and future fun banners.
        """
        # Pad / trim to exactly 20 characters
        s = (text or "")[:20]
        s = s + (" " * (20 - len(s)))
        payload = [ord(c) if 32 <= ord(c) <= 126 else 0x20 for c in s]
        body = [0x20, 0x00, 0x00] + payload
        ck = _roland_checksum(body)
        return mido.Message("sysex", data=[0x41, 0x10, 0x16, 0x12, *body, ck])

    def _voodoo_display(self, text: str) -> None:
        """Send a display string to all current Voodoo :mt32 targets (or all mt32 ports)."""
        targets = self._voodoo_targets or self._mt32_port_indices()
        if not targets:
            return
        msg = self._mt32_display_msg(text)
        for p in targets:
            self._safe_out_send(p, msg)

    def _only_mt32_outs(self) -> bool:
        """True when every port is mt32-capable and none offer gm/gs/xg/any."""
        if self.n_ports < 1:
            return False
        for tags in self.out_formats:
            if not tags or "any" in tags:
                return False
            if "mt32" not in tags:
                return False
            # pure mt32 (may also list nothing else) – reject if gm/gs/xg/gm2 present
            if tags & {"gm", "gm2", "gs", "xg"}:
                return False
        return True

    def _voodoo_begin(self, reason: str = "manual") -> None:
        """Start paced GM bank load to all :mt32 outs; queue live input."""
        if not _VOODOO_BANKS:
            self._set_status("Voodoo unavailable (tables_voodoo.py missing)", duration=4.0)
            return
        targets = self._mt32_port_indices()
        if not targets:
            self._set_status("Voodoo: no :mt32 outs to program", duration=3.0)
            return
        if self.voodoo_loading:
            self._set_status("Voodoo: already loading", duration=2.0)
            return

        try:
            bank = list(get_bank_sysex(self.voodoo_bank))
        except Exception as e:
            self._set_status(f"Voodoo: bank load failed ({e})", duration=4.0)
            return
        kit: list = []
        if bank_has_kits(self.voodoo_bank):
            kit = list(mtr_stnd_sysex())
        if not bank:
            self._set_status("Voodoo: empty GM bank data", duration=3.0)
            return

        self.voodoo_loading = True
        self.voodoo_catchup = False
        self.voodoo_active = False
        self.voodoo_kit = "standard"
        self._voodoo_full_bank = True
        self._voodoo_targets = targets
        self._voodoo_ch_owners = [[] for _ in range(16)]

        # Display banners + bank/kit go to ALL mt32 targets (ports=None).
        # Phase V2 unit maps go to ONE port only — otherwise the last map
        # would overwrite every unit and only one device would look programmed.
        def _all(payloads):
            out = []
            for p in payloads:
                out.append((p if isinstance(p, (bytes, bytearray)) else bytes(p), None))
            return out

        def _one(payloads, port: int):
            out = []
            for p in payloads:
                out.append((p if isinstance(p, (bytes, bytearray)) else bytes(p), [port]))
            return out

        banner_load = bytes(self._mt32_display_msg("Duality Voodoo...").data)
        banner_gm = bytes(self._mt32_display_msg(("Loading " + bank_display(self.voodoo_bank))[:20]).data)
        send_list = _all([banner_load, banner_gm]) + _all(bank) + _all(kit)

        # Phase V2: with 2+ MT-32s, program alternating channel map + equal reserve
        if len(targets) >= 2:
            banner_map = bytes(self._mt32_display_msg("Mapping 16ch...").data)
            send_list.extend(_all([banner_map]))
            plan = _voodoo_channel_plan(len(targets), self.voodoo_layout)
            # Build per-unit map SysEx, then interleave by step so all units
            # receive their i-th message in the SAME paced tick. Wall-clock
            # map time stays ~constant as unit count grows.
            unit_maps: list[tuple[int, list]] = []
            for u, port in enumerate(targets):
                melody = plan[u]
                for ch in melody:
                    self._voodoo_ch_owners[ch - 1].append(port)
                # Rhythm (ch 10): every unit – Duality load-balances notes
                self._voodoo_ch_owners[9].append(port)
                unit_maps.append((port, list(_voodoo_unit_map_sysex(melody))))
                self._log_line(
                    f"VOODOO map [{self.voodoo_layout}] → port{port + 1}: "
                    f"melody ch {','.join(str(c) for c in melody)} + rhythm/10"
                )
            max_steps = max((len(ms) for _, ms in unit_maps), default=0)
            for step in range(max_steps):
                batch = []
                for port, ms in unit_maps:
                    if step < len(ms):
                        batch.append((ms[step], [port]))
                if batch:
                    send_list.append(batch)  # parallel multi-port step
            # Ownership summary for debugging missing channels
            for ch in range(16):
                owners = self._voodoo_ch_owners[ch]
                if owners:
                    self._log_line(
                        f"VOODOO ch{ch + 1} → port(s) "
                        + ",".join(str(p + 1) for p in owners)
                    )
        else:
            # Single unit: no remap – leave factory/bank receive channels as-is
            self._voodoo_ch_owners = [[] for _ in range(16)]

        # Master volume last so it wins over any level in the bank dump.
        # MT-32 scale is 0–100; GM banks at 100 often clip on original hardware.
        vol = max(0, min(100, int(VOODOO_MASTER_VOLUME)))
        vol_msg = _mt32_dt1((0x10, 0x00, 0x16), [vol])
        send_list.extend(_all([vol_msg]))
        self._log_line(f"VOODOO master volume → {vol}/100")

        self._voodoo_send_list = send_list
        self._voodoo_send_idx = 0
        self._voodoo_next_send = time.monotonic()
        self._voodoo_load_t0 = time.monotonic()
        self._voodoo_queue.clear()
        self._voodoo_catchup_idx = 0
        n = len(self._voodoo_send_list)
        n_units = max(1, len(targets))
        # Honest ETA: paced gap is a floor; shared USB MIDI scales with unit count.
        est = n * max(VOODOO_SYSEX_GAP, n_units * VOODOO_SEC_PER_UNIT_STEP)
        multi = " 16ch" if len(targets) >= 2 else ""
        self._set_status(
            f"Voodoo: loading {bank_label(self.voodoo_bank)}{multi} "
            f"({n} steps × {n_units} unit(s), ~{est:.0f}s) – {reason}",
            duration=max(est + 5.0, 15.0),
        )
        self._log_line(
            f"VOODOO begin ({reason}): {n} paced steps → "
            f"{n_units} unit(s) ["
            + ",".join(str(i + 1) for i in targets)
            + f"] est ~{est:.0f}s "
            f"(USB-bound ~{VOODOO_SEC_PER_UNIT_STEP*1000:.0f}ms×units/step)"
        )

    def _voodoo_exit(self, reason: str = "manual") -> None:
        """Leave Voodoo mode; flush any deferred queue live (no catch-up compress)."""
        was = self.voodoo_active or self.voodoo_loading or self.voodoo_catchup
        self.voodoo_active = False
        self.voodoo_loading = False
        self.voodoo_catchup = False
        self.voodoo_requested = False  # allow future auto-enter if mt32-only + non-MT-32 stream
        self._voodoo_ch_owners = [[] for _ in range(16)]
        self._voodoo_send_list = []
        self._voodoo_send_idx = 0
        # Drop deferred song data on exit-via-MT32-SysEx / foreign format
        # to avoid fighting the new map. Other exits (hotkey) flush live.
        if reason.startswith("MT-32") or reason.startswith("format"):
            self._voodoo_queue.clear()
        elif self._voodoo_queue:
            # Best-effort: release remaining as live under normal routing
            pending = self._voodoo_queue
            self._voodoo_queue = []
            for _, msg in pending:
                self._voodoo_deliver_live(msg)
        if was:
            try:
                self._voodoo_display("Voodoo Off")
            except Exception:
                pass
            self._set_status(f"Voodoo: exited ({reason})", duration=3.0)
            self._log_line(f"VOODOO exit ({reason})")

    def _voodoo_tick(self) -> None:
        """Advance paced bank load or elastic catch-up. Call from run loop."""
        now = time.monotonic()
        if self.voodoo_loading:
            # One SysEx per tick keeps the Live panel + hotkeys responsive
            if (
                self._voodoo_send_idx < len(self._voodoo_send_list)
                and now >= self._voodoo_next_send
            ):
                item = self._voodoo_send_list[self._voodoo_send_idx]
                # Formats:
                #   (payload, ports|None) — None = all voodoo targets
                #   [(payload, ports), ...] — parallel step (different maps to
                #       different units in ONE gap interval)
                # Gap is anchored to step START so 2 vs 4 outs share the same
                # wall-clock pace. Each device still sees one DT1 per gap.
                step_t0 = time.monotonic()
                if isinstance(item, list):
                    # Parallel map step: different payloads to different units
                    # concurrently (one thread per unit).
                    def _send_pair(payload, ports) -> None:
                        dest = ports if ports is not None else self._voodoo_targets
                        self._voodoo_fanout(dest, payload)

                    threads = [
                        threading.Thread(
                            target=_send_pair,
                            args=(payload, ports),
                            daemon=True,
                        )
                        for payload, ports in item
                    ]
                    for t in threads:
                        t.start()
                    for t in threads:
                        t.join(timeout=2.0)
                else:
                    if isinstance(item, tuple):
                        payload, ports = item
                    else:
                        payload, ports = item, None
                    dest = ports if ports is not None else self._voodoo_targets
                    self._voodoo_fanout(dest, payload)
                self._voodoo_send_idx += 1
                self._voodoo_next_send = step_t0 + VOODOO_SYSEX_GAP
            if self._voodoo_send_idx >= len(self._voodoo_send_list):
                self.voodoo_loading = False
                self.voodoo_active = True
                # Friendly display on the hardware
                if self._voodoo_full_bank:
                    if any(self._voodoo_ch_owners):
                        self._voodoo_display("Voodoo 16ch Ready!")
                    else:
                        self._voodoo_display("Voodoo GM Ready!")
                qn = len(self._voodoo_queue)
                elapsed = time.monotonic() - getattr(self, "_voodoo_load_t0", time.monotonic())
                self._log_line(
                    f"VOODOO send done (full_bank={self._voodoo_full_bank}); "
                    f"elapsed={elapsed:.1f}s; queue depth={qn}"
                )
                if qn == 0:
                    if self._voodoo_full_bank:
                        self._set_status("Voodoo: GM ready", duration=6.0)
                    # kit-only: status already set by _voodoo_rhythm_pc
                else:
                    self.voodoo_catchup = True
                    self._voodoo_catchup_idx = 0
                    # Snapshot: only drain what was queued during load. Messages that
                    # arrive during catch-up are flushed after, then we go live —
                    # avoids chasing a still-playing song for tens of seconds.
                    self._voodoo_catchup_end = qn
                    self._voodoo_catchup_origin = self._voodoo_queue[0][0]
                    self._voodoo_catchup_t0 = time.monotonic()
                    self._voodoo_catchup_next = self._voodoo_catchup_t0
                    self._set_status(
                        f"Voodoo: catching up {qn} msgs",
                        duration=4.0,
                    )
                    self._log_line(f"VOODOO catch-up start depth={qn}")
            return

        if self.voodoo_catchup:
            # Drain the load-time snapshot first (not a moving live target).
            end = getattr(self, "_voodoo_catchup_end", len(self._voodoo_queue))
            end = min(end, len(self._voodoo_queue))
            burst = 0
            now = time.monotonic()
            remaining = end - self._voodoo_catchup_idx
            fast = remaining >= VOODOO_CATCHUP_FAST_DEPTH
            while (
                self._voodoo_catchup_idx < end
                and burst < VOODOO_CATCHUP_BURST
            ):
                recv_ts, msg = self._voodoo_queue[self._voodoo_catchup_idx]
                if not fast:
                    # Elastic: compress original spacing, with a small floor gap
                    rel = max(0.0, (recv_ts - self._voodoo_catchup_origin) / VOODOO_CATCHUP_SPEED)
                    due = max(self._voodoo_catchup_t0 + rel, self._voodoo_catchup_next)
                    if now < due:
                        break
                self._voodoo_deliver_live(msg)
                self._voodoo_catchup_idx += 1
                burst += 1
                self._voodoo_catchup_next = time.monotonic() + (
                    0.0 if fast else VOODOO_CATCHUP_MIN_GAP
                )
                now = time.monotonic()
            if self._voodoo_catchup_idx >= end:
                # Snapshot done — flush anything that arrived during catch-up ASAP
                while self._voodoo_catchup_idx < len(self._voodoo_queue):
                    _, msg = self._voodoo_queue[self._voodoo_catchup_idx]
                    self._voodoo_deliver_live(msg)
                    self._voodoo_catchup_idx += 1
                self._voodoo_queue.clear()
                self._voodoo_catchup_idx = 0
                self._voodoo_catchup_end = 0
                self.voodoo_catchup = False
                self._set_status("Voodoo: live", duration=2.0)
                self._log_line("VOODOO catch-up complete")

    def _voodoo_enqueue(self, msg: mido.Message) -> None:
        """Defer a live input message while loading / until catch-up owns it."""
        try:
            queued = msg.copy()
        except Exception:
            queued = msg
        self._voodoo_queue.append((time.monotonic(), queued))

    def _voodoo_deliver_live(self, msg: mido.Message) -> None:
        """
        Deliver one deferred message through the normal process path.
        Temporarily clears loading/catchup guards so process() does not re-queue.
        """
        was_loading = self.voodoo_loading
        was_catchup = self.voodoo_catchup
        self.voodoo_loading = False
        # Keep catchup flag false only for this call's re-entry guard
        hold_catchup = was_catchup
        self.voodoo_catchup = False
        try:
            self.process(msg)
        finally:
            self.voodoo_loading = was_loading
            self.voodoo_catchup = hold_catchup

    def _voodoo_on_mt32_sysex(self, msg: mido.Message) -> bool:
        """
        If this is MT-32 model SysEx while Voodoo is active/loading, exit Voodoo
        and let the message pass through normal routing. Returns True if handled
        as an exit trigger (caller should still route the SysEx).
        """
        if not (self.voodoo_active or self.voodoo_loading or self.voodoo_catchup):
            return False
        data = list(msg.data)
        if len(data) >= 3 and data[0] == 0x41 and data[2] == 0x16:
            self._voodoo_exit("MT-32 SysEx")
            return True
        return False

    def _voodoo_on_foreign_format(self, fmt: str) -> None:
        """
        Leave Voodoo when the input stream identifies as a non-MT-32 format
        (GS / XG / GM / GM2) and the user has not locked the format.

        Restores normal Crucible routing (notes, pitch bends, CC, SysEx) to the
        appropriate tagged outs instead of keeping everything pinned to :mt32
        under the GM-reprogrammed map.
        """
        if not (self.voodoo_active or self.voodoo_loading or self.voodoo_catchup):
            return
        if not fmt or fmt == "MT-32":
            return
        if self.format_locked:
            # User intentionally locked (typically to MT-32) – stay in Voodoo
            return
        self._voodoo_exit(f"format → {fmt}")


    def _voodoo_toggle_layout(self) -> None:
        """Hotkey P: stripe ↔ pairs when 4+ even MT-32 units are present."""
        targets = self._mt32_port_indices()
        n = len(targets)
        if n < 4 or n % 2 != 0:
            self._set_status(
                f"Voodoo pairs layout needs 4+ even units (have {n})",
                duration=3.0,
            )
            return
        self.voodoo_layout = "pairs" if self.voodoo_layout == "stripe" else "stripe"
        self._set_status(
            f"Voodoo layout → {self.voodoo_layout}",
            duration=3.0,
        )
        self._log_line(f"VOODOO layout → {self.voodoo_layout}")
        if self.voodoo_active or self.voodoo_loading:
            # Re-program channel maps (bank reload keeps SysEx consistent)
            self._voodoo_begin(f"layout → {self.voodoo_layout}")

    def _voodoo_ports_for_channel(self, channel: int) -> list[int] | None:
        """
        Phase V2 routing. channel is 0-based (msg.channel).

        Returns:
          None  – multi-map inactive (single MT-32 or Voodoo off); use normal routing
          list  – port indices that own this channel (rhythm may have several for LB)
        """
        if not self.voodoo_active:
            return None
        owners = self._voodoo_ch_owners
        if not owners or not any(owners):
            return None
        ch = channel & 0x0F
        ports = owners[ch]
        return list(ports) if ports else None

    def _voodoo_maybe_auto(self) -> None:
        """Auto-enter Voodoo when only :mt32 outs exist and stream is non-MT-32."""
        if self.voodoo_active or self.voodoo_loading or self.voodoo_catchup:
            return
        if self.voodoo_requested:
            return  # startup path owns init
        if not self._only_mt32_outs():
            return
        fmt = self.detected_format
        if fmt is None or fmt == "MT-32":
            return
        self._voodoo_begin(f"auto ({fmt} stream, mt32-only outs)")

    def _voodoo_rhythm_pc(self, msg: mido.Message) -> bool:
        """
        While Voodoo active: ch10 PC selects Standard vs Orchestra kit SysEx.
        Returns True if the PC was consumed (kit SysEx sent instead of raw PC).
        """
        if not self.voodoo_active or self.voodoo_loading:
            return False
        if msg.type != "program_change" or msg.channel != 9:  # ch 10
            return False
        # KQ6 (and similar) bake rhythm into the bank — no STND/ORCH overlay
        if not bank_has_kits(self.voodoo_bank):
            return False
        targets = self._mt32_port_indices()
        if not targets:
            return False
        if msg.program in GM_ORCHESTRA_KIT_PC:
            if self.voodoo_kit == "orchestra":
                return True  # already there – swallow duplicate
            blob = list(mtr_orch_sysex())
            label = "Orchestra"
            self.voodoo_kit = "orchestra"
        else:
            if self.voodoo_kit == "standard" and msg.program == 0:
                return True
            blob = list(mtr_stnd_sysex())
            label = "Standard"
            self.voodoo_kit = "standard"
        if not blob:
            return False
        # Non-blocking: inject kit SysEx at the front of a micro paced send
        # (reuse loader only if idle; otherwise send immediately with gaps via tick)
        banner = bytes(self._mt32_display_msg(f"Kit: {label}"[:20]).data)
        kit_items = [(banner, None)] + [
            (b if isinstance(b, (bytes, bytearray)) else bytes(b), None) for b in blob
        ]
        if not self.voodoo_loading:
            self.voodoo_loading = True  # brief — only kit msgs
            self._voodoo_full_bank = False
            self._voodoo_targets = targets
            self._voodoo_send_list = kit_items
            self._voodoo_send_idx = 0
            self._voodoo_next_send = time.monotonic()
            # Keep voodoo_active True so we don't look "off"
        else:
            for payload, _ports in kit_items:
                m = mido.Message("sysex", data=list(payload))
                for p in targets:
                    self._safe_out_send(p, m)
        self._set_status(f"Voodoo: {label} kit", duration=2.5)
        self._log_line(f"VOODOO kit → {label} (ch10 PC {msg.program + 1})")
        return True



    # ----- Anima Phase 1 -----------------------------------------------------

    def _anima_feedback(self, kind: str, detail: str, *, status: bool = False) -> None:
        """Always log (with --log); optional throttled status-line flash."""
        self._log_line(f"ANIMA {kind}: {detail}")
        if not status:
            return
        now = time.monotonic()
        if now - self._anima_status_t < ANIMA_STATUS_GAP:
            return
        self._anima_status_t = now
        self._set_status(f"Anima {kind}: {detail}", duration=2.0)

    def _anima_on_cc(self, msg: mido.Message) -> None:
        """Track file-driven expression so we do not fight it."""
        if msg.type == "control_change" and msg.control == 11:
            self._anima_file_cc11_t[msg.channel & 0x0F] = time.monotonic()

    def _anima_port_8850(self, port: int) -> bool:
        """True for any Sound Canvas-class port (55/88/Pro/8850)."""
        tags = self.out_formats[port] if port < len(self.out_formats) else frozenset()
        return self._gs_canvas_class(tags) != "none"

    def _anima_adapt_tone_slot(self, port: int, slot):
        """Shrink an 8850-centric (cc00, cc32, pc) to what this port's map has."""
        if not slot:
            return None
        cc0, cc32, pc = slot
        cls = self._gs_canvas_class(self.out_formats[port] if port < len(self.out_formats) else set())
        if cls == "8850":
            return slot
        if cls == "none":
            return None
        # CM-64 banks live on the 55 map of an 8850; skip on earlier boxes.
        if cc0 in (126, 127):
            return (0, 0, pc & 0x7F)
        if cls == "88pro":
            # Native 88Pro/880: capitals + CC00 variations, no 8850 map 4.
            if cc32 >= 4:
                return (0, 0, pc & 0x7F)
            return (cc0, 0, pc & 0x7F)
        if cls == "88":
            if cc32 >= 3:
                return (0, 0, pc & 0x7F)
            return (cc0 if cc32 <= 2 else 0, 0, pc & 0x7F)
        # 55
        if cc32 >= 2:
            return (0, 0, pc & 0x7F)
        return (cc0 if cc32 <= 1 else 0, 0, pc & 0x7F)

    def _anima_file_map(self, cc0: int, cc32: int) -> int:
        """Map LSB that makes this file bank exist on an 8850."""
        cc0, cc32 = int(cc0) & 0x7F, int(cc32) & 0x7F
        if cc0 in (126, 127):
            return 1          # CM-64 only on SC-55 map
        if cc32 in (1, 2, 3, 4):
            return cc32       # file asked for a canvas map
        return 0              # classic GS variation (CC32=0)

    def _anima_cm64_restore_pc(self, msg: mido.Message) -> None:
        """File sent a bank after Anima/CM — drop our slot; map snap happens on PC."""
        if not self.anima or msg.type != "control_change":
            return
        if msg.control not in (0, 32):
            return
        ch = msg.channel & 0x0F
        self._anima_park_on_program(ch)
        if msg.control == 0 and msg.value not in (0,):
            self._anima_cm64[ch] = False
            self._anima_tone_slot[ch] = None
        elif msg.control == 32 and self._anima_cm64[ch] and msg.value not in (1,):
            self._anima_cm64[ch] = False
            self._anima_tone_slot[ch] = None

    def _anima_gs_map_home(self, reason: str = "") -> None:
        """GS Reset does not clear tone map. Force CC32=4 on GS parts."""
        for i in range(self.n_ports):
            if not self._anima_port_8850(i):
                continue
            for ch in range(16):
                if getattr(self, "_anima_cm64", [False]*16)[ch]:
                    continue
                # File GS variation (CC00!=0, often CC32=0): do not yank map.
                if int(self.bank_msb[ch]) & 0x7F:
                    continue
                try:
                    self._send_routed(
                        i, mido.Message("control_change", channel=ch, control=32, value=4)
                    )
                except Exception:
                    break
        if reason:
            self._log_line(f"ANIMA map home CC32=4 ({reason})")

    def _anima_acoustic_pc(self, pc: int) -> bool:
        return (pc & 0x7F) in (24, 25)  # Nylon / Steel

    def _anima_acoustic_mate(self, ch: int, pc: int):
        """Other channel already in the same acoustic 'one guitar' cluster."""
        pc = pc & 0x7F
        if not self._anima_acoustic_pc(pc):
            return None
        my_msb = int(self.bank_msb[ch]) & 0x7F
        my_lsb = int(self.bank_lsb[ch]) & 0x7F
        my_file = bool(self._anima_seen_cc0[ch] or self._anima_seen_cc32[ch]) and (my_msb or my_lsb)
        if my_file:
            return None
        for other in range(16):
            if other == ch or self._anima_is_rhythm(other):
                continue
            opc = int(self._anima_prog[other]) & 0x7F
            if not self._anima_acoustic_pc(opc):
                continue
            slot = self._anima_tone_slot[other]
            if not slot:
                continue
            o_file = bool(self._anima_seen_cc0[other] or self._anima_seen_cc32[other]) and (
                (int(self.bank_msb[other]) & 0x7F) or (int(self.bank_lsb[other]) & 0x7F)
            )
            if o_file:
                continue
            return other
        return None

    def _anima_tone_pick(self, ch: int, pc: int):
        """Return (cc00, cc32, pc) or None for capital-as-written."""
        cached = self._anima_tone_slot[ch]
        if cached is not None:
            return cached
        pc = pc & 0x7F
        mate = self._anima_acoustic_mate(ch, pc)
        if mate is not None:
            slot = self._anima_tone_slot[mate]
            self._anima_tone_slot[ch] = slot
            self._anima_tone_cc0[ch] = slot[0]
            self._anima_cm64[ch] = (slot[0] in (126, 127)) or (slot[2] != pc)
            self._anima_feedback(
                "tone",
                f"cluster ch{ch + 1} → ch{mate + 1} CC00={slot[0]:03d} map{slot[1]} (one guitar)",
                status=True,
            )
            return slot
        slots = anima_tone_slots(pc)
        # Guitar Harmonics (GM 32): file put this in an insert for a reason
        # (pinch squeals). Keep capital. Dry GM streams: 75% keep.
        if pc == 31:
            file_on = ch in (getattr(self, "_anima_file_efx_parts", set()) or set())
            file_dirt = (
                getattr(self, "_anima_file_efx_type", None) in ANIMA_FILE_DIRT_TYPES
            )
            mix = self._anima_mix((ch + 1) * 17, 32 * 31)
            # File insert on this part, or a dirt insert anywhere in the cue
            # (other guitar in the Multi/OD) → keep capital Harmonics.
            if file_on or file_dirt or (mix % 4) != 0:
                slot = (0, 4, 31)
                self._anima_tone_slot[ch] = slot
                self._anima_tone_cc0[ch] = 0
                self._anima_cm64[ch] = False
                return slot
        if not slots:
            slot = (0, 4, pc & 0x7F)
        else:
            mix = self._anima_mix((ch + 1) * 17, (pc + 1) * 31)
            same = [s for s in slots if s[0] not in (126, 127) and s[2] == (pc & 0x7F)]
            cm = [s for s in slots if s[0] in (126, 127)]
            varied = [s for s in same if s[0] != 0]
            # Official CM-64 PCM/LA (CC00 126/127, SC-55 map) ~1 in 4.
            if cm and (mix % 4 == 0):
                slot = cm[(mix // 4) % len(cm)]
            elif varied and (mix % 3 != 0):
                slot = varied[mix % len(varied)]
                rare_n = ANIMA_TONE_RARE.get((slot[0], slot[2]))
                if rare_n and (mix % rare_n) != 0:
                    alt = [s for s in varied if (s[0], s[2]) != (slot[0], slot[2])]
                    if alt:
                        slot = alt[mix % len(alt)]
            elif same:
                slot = same[mix % len(same)]
            else:
                slot = (0, 4, pc & 0x7F)
        self._anima_tone_slot[ch] = slot
        self._anima_tone_cc0[ch] = slot[0]
        self._anima_cm64[ch] = (slot[0] in (126, 127)) or (slot[2] != (pc & 0x7F))
        return slot

    def _anima_on_pc(self, msg: mido.Message) -> None:
        if msg.type != "program_change":
            return
        ch = msg.channel & 0x0F
        self._anima_prog[ch] = msg.program & 0x7F
        self._anima_tone_cc0[ch] = None
        self._anima_tone_slot[ch] = None
        self._anima_cm64[ch] = False
        self._file_used_ch[ch] = True
        self._file_pc[ch] = msg.program & 0x7F
        self._anima_seen_cc0[ch] = False
        self._anima_seen_cc32[ch] = False
        # File reclaimed a channel we had borrowed for fret noise.
        for i, fch in enumerate(getattr(self, "_anima_foley_ch", []) or []):
            if fch == ch and (msg.program & 0x7F) not in (120, 121):
                self._anima_foley_ch[i] = None
                self._anima_foley_armed[i] = False
        self._anima_mod_on = {k for k in self._anima_mod_on if k[0] != ch}
        self._anima_mod_ch[ch] = False
        if self.anima:
            # New instrument starts with a resting wheel on every unit; the
            # file re-sends CC1 after the PC if it wants one.
            self._anima_mod_clear(ch)
            # The file's PC reached every unit and replaced any bass-sub
            # patch on this channel; old sub snapshots no longer apply.
            armed = getattr(self, "_anima_wave_sub_armed", None) or set()
            for key in [k for k in armed if k[1] == ch]:
                armed.discard(key)
                (getattr(self, "_anima_wave_sub_saved", None) or {}).pop(key, None)
            self._anima_expr_phrase[ch] = False
            self._anima_expr_shape[ch] = None
            self._anima_expr_peak[ch] = ANIMA_EXPR_DEFAULT
            self._anima_park_on_program(ch)
            cat = self._anima_category(ch)
            bank = getattr(self, "_anima_stream_bank", None) or "-"
            msb = self.bank_msb[ch] if hasattr(self, "bank_msb") else 0
            lsb = self.bank_lsb[ch] if hasattr(self, "bank_lsb") else 0
            fmt = getattr(self, "detected_format", None) or "-"
            self._anima_feedback(
                "cat",
                f"ch{ch + 1} PC{msg.program + 1} bank {msb}/{lsb} → {cat} [{bank}|{fmt}]",
                status=True,
            )
            if self.anima_game:
                self._anima_game_note_pc()
            # Insert types are placed once the PC dump settles (or at the
            # first note), still ahead of the notes. Not per PC in arrival order.
            self._anima_efx_on_pc(ch)

    def _anima_cat_pc(self, ch: int) -> int:
        """GM capital this part is *for*, even if we are sounding a CM-64 PC."""
        ch = ch & 0x0F
        if self._anima_cm64[ch] and self._file_used_ch[ch]:
            return int(self._file_pc[ch]) & 0x7F
        msb = int(self.bank_msb[ch]) & 0x7F
        prog = int(self._anima_prog[ch]) & 0x7F
        if msb in (126, 127):
            gm = anima_cm_to_gm(msb, prog)
            if gm is not None:
                return gm
        return prog

    def _anima_category(self, ch: int) -> str:
        """Pick articulation family from the active tonemap."""
        if self._anima_is_rhythm(ch):
            return "sfx"
        prog = self._anima_cat_pc(ch)
        voodoo_on = bool(
            getattr(self, "voodoo_active", False)
            or getattr(self, "voodoo_loading", False)
        )
        bank = getattr(self, "_anima_stream_bank", None)
        if bank and bank in ANIMA_SIERRA_PC:
            spec = ANIMA_SIERRA_PC[bank].get(prog)
            if spec is None:
                return _mt32_category(prog)
            if isinstance(spec, str) and spec.startswith("P"):
                try:
                    return _mt32_category(int(spec[1:]))
                except ValueError:
                    return _mt32_category(prog)
            return spec
        if voodoo_on and _VOODOO_BANKS:
            amap = bank_anima_map(getattr(self, "voodoo_bank", "mtgm"))
            if amap == "sfx":
                return "sfx"
            if amap == "mt32":
                return _mt32_category(prog)
            return _gm_category(prog)
        fmt = (getattr(self, "detected_format", None) or "").upper()
        if getattr(self, "_anima_stream_map", None) == "sfx":
            return "sfx"
        if getattr(self, "_anima_stream_map", None) == "mt32":
            return _mt32_category(prog)
        if fmt in ("MT-32", "MT32", "MT"):
            return _mt32_category(prog)
        return self._gs_xg_gm_category(ch, prog, fmt)

    def _gs_xg_gm_category(self, ch: int, prog: int, fmt: str) -> str:
        """GM / GS / XG family from program + bank select (CC0 / CC32).

        Capital / GM and most GS/XG *variations* keep the GM program number,
        so family follows _gm_category(PC). Special maps:
          GS CC0=127  MT-32 / CM-32L tone map
          GS CC0=126  CM-32P / CM-64 PCM (approx as GM family)
          XG CC0=64 or 126  SFX voices
          XG CC0=127        drum kit (non-ch10)
        """
        ch = ch & 0x0F
        try:
            msb = int(self.bank_msb[ch]) & 0x7F
        except Exception:
            msb = 0
        fmt = (fmt or "").upper().replace(" ", "")
        if fmt in ("GS", "SC", "SC-8850", "SC8850"):
            if msb == 127:
                return _mt32_category(prog)
            return _gm_category(prog)
        if fmt in ("XG",):
            if msb in (64, 126):
                return "sfx"
            if msb == 127:
                return "percussive"
            return _gm_category(prog)
        return _gm_category(prog)

    def _anima_mt32_mode(self) -> bool:
        fmt = (getattr(self, "detected_format", None) or "").upper()
        if fmt in ("MT-32", "MT32", "MT"):
            return True
        if getattr(self, "_anima_stream_bank", None) in ANIMA_SIERRA_PC:
            return True
        if getattr(self, "voodoo_active", False) or getattr(self, "voodoo_loading", False):
            return True
        return False

    def _anima_observe_sysex(self, msg: mido.Message, description: str = "") -> None:
        """Learn custom MT-32 banks from dumped SysEx / display text."""
        if not self.anima and not True:
            # Cheap enough to always track; category only used when Anima is on
            pass
        data = list(msg.data) if msg.data else []
        blob = ""
        if description:
            blob += " " + description.lower()
        # Display + timbre-name ASCII from MT-32 DT1
        if (
            len(data) >= 8
            and data[0] == 0x41
            and data[2] == 0x16
            and data[3] == 0x12
        ):
            aa, bb, cc = data[4], data[5], data[6]
            body = bytes(data[7:-1] if len(data) > 8 else data[7:])
            chars = "".join(chr(b) if 32 <= b < 127 else " " for b in body)
            blob += " " + chars.lower()
            # Factory reset wipes custom memory → back to stock MT-32 map
            if aa == 0x7F:
                if getattr(self, "_anima_stream_bank", None):
                    self._anima_stream_bank = None
                    self._anima_stream_map = None
                    self._anima_feedback("bank", "MT-32 factory map", status=True)
                return
        blob = " ".join(blob.split())
        if not blob:
            return
        locked = getattr(self, "_anima_stream_bank", None)
        for needles, bank_id, amap, label in ANIMA_BANK_SIGNATURES:
            if any(n in blob for n in needles):
                if locked == bank_id:
                    return
                self._anima_stream_bank = bank_id
                self._anima_stream_map = amap
                self._anima_feedback("bank", f"{label} custom MT-32 ({amap})", status=True)
                return
        # Names only fill in when nothing is locked yet
        if locked:
            return
        for needles, bank_id, amap, label in ANIMA_BANK_NAME_HINTS:
            if any(n in blob for n in needles):
                self._anima_stream_bank = bank_id
                self._anima_stream_map = amap
                self._anima_feedback("bank", f"{label} custom MT-32 ({amap})", status=True)
                return



    def _anima_hold_retrigger(self, port: int, chs: list) -> list:
        """Gate held voices around an EFX switch without double-striking.

        Cancel any strum-queued ons first. Only send an off if that note
        already left the port. Caller sends SysEx, then _anima_hold_resume.
        """
        held = []
        want = set(chs)
        for ch in want:
            buf = self._anima_strum_buf[ch]
            if buf:
                self._anima_strum_buf[ch] = None
        keep_q = []
        for when, p, msg in self._anima_strum_q:
            if (
                p == port
                and msg.type == "note_on"
                and (msg.channel & 0x0F) in want
                and msg.velocity > 0
            ):
                continue
            keep_q.append((when, p, msg))
        self._anima_strum_q = keep_q
        for key, info in list(self.active.items()):
            ch, note = key[0], key[1]
            if ch not in want:
                continue
            ports = info.get("ports") or [info["port"]]
            if port not in ports:
                continue
            vel = int(info.get("velocity") or 64)
            # Note may only live in the (now cleared) strum queue — no off.
            if info.get("strum_pending"):
                held.append((ch, note, vel))
                info["strum_pending"] = False
                continue
            self._safe_out_send(
                port, mido.Message("note_off", channel=ch, note=note, velocity=0)
            )
            held.append((ch, note, vel))
        return held

    def _anima_hold_resume(self, port: int, held: list) -> None:
        for ch, note, vel in held:
            self._safe_out_send(
                port, mido.Message("note_on", channel=ch, note=note, velocity=max(1, vel))
            )

    def _anima_reset_session(self, reason: str = "idle") -> None:
        """Clear Anima EFX/slot/strum state. Does not touch format lock."""
        self._anima_release_efx_lock(reason)
        self._anima_reset_efx_seed()
        self._anima_efx_sound_t = {}
        self._anima_fam_played = {}     # family -> last real note (not a PC)
        self._anima_efx_burst_dirty = False  # PC dump waiting for one settle
        self._anima_efx_burst_t = 0.0
        self._anima_efx_seek_t = [0.0] * 16
        self._anima_ch_port = {}
        self._anima_fam_was = [None] * 16
        self._anima_note_port = {}
        self._anima_rhythm = [False] * 16
        self._anima_rhythm[9] = True
        self._anima_strum_q = []
        self._anima_settle_q = []
        self._anima_settle_on = {}
        self._anima_efx_settle = [0.0] * self.n_ports
        self._anima_settle_bypass = False
        self._anima_strum_buf = [None] * 16
        self._anima_foley_ch = [None] * self.n_ports
        self._anima_foley_armed = [False] * self.n_ports
        self._anima_foley_patch = None
        self._anima_foley_pitch = [-1] * 16
        self._file_used_ch = [False] * 16
        self._anima_seen_cc0 = [False] * 16
        self._anima_seen_cc32 = [False] * 16
        self._anima_tone_cc0 = [None] * 16
        self._anima_tone_slot = [None] * 16
        self._anima_cm64 = [False] * 16
        self.bank_msb = [0] * 16
        self.bank_lsb = [0] * 16
        self._anima_gs_map_home("session")
        self._anima_session_idle_done = True
        self._anima_fam_ghost = {}
        self._anima_bass_sub_choice = None
        self._anima_wave_sub_armed = set()
        self._anima_wave_sub_saved = {}
        self._anima_cc11_cur = [ANIMA_EXPR_DEFAULT] * 16
        self._anima_cc11_tgt = [ANIMA_EXPR_DEFAULT] * 16
        self._anima_cc11_own = [False] * 16
        self._anima_expr_phrase = [False] * 16
        self._anima_expr_peak = [ANIMA_EXPR_DEFAULT] * 16
        self._anima_expr_shape = [None] * 16
        self._anima_expr_shape_t = [0.0] * 16
        # YS4 stack Rx map is session state — drop so the next cue's KS
        # is not neutralized from a previous song.
        self._gs_reset_part_rx()
        # Do not send new PCs here — that was audible "X changes patches".
        # Next file PC / prime picks from the new seed.
        self._set_status(f"Anima reset ({reason})", duration=2.5)

    def _check_anima_session_idle(self) -> None:
        if not self.anima:
            return
        self._anima_game_poll()
        self._anima_park_idle_poll()
        self._anima_efx_burst_poll()
        self._anima_efx_dly_upkeep()
        idle_need = (
            ANIMA_GAME_IDLE_SEC if self.anima_game else ANIMA_SESSION_IDLE_SEC
        )
        now = time.monotonic()
        # Held notes, ghosts and queued strums are not idle: a game cue that
        # sustains a chord past 4 s with no new MIDI was being reset mid-scene.
        if self.active or (self._anima_ghosts or {}) or self._anima_strum_q:
            self._anima_sound_t = now
        quiet_since = max(self.last_midi_time, float(getattr(self, "_anima_sound_t", 0.0) or 0.0))
        if now - quiet_since < idle_need:
            self._anima_session_idle_done = False
            return
        if getattr(self, "_anima_session_idle_done", False):
            return
        if not (self._anima_efx_key or any(self._anima_slots) or self._anima_file_efx_t):
            self._anima_session_idle_done = True
            return
        label = f"{int(idle_need)}s idle"
        self._anima_reset_session(label)

    def _send_format_resets(self, reason: str = "hotkey X") -> None:
        """GM / GS / XG / MT-32 reset on each out from its tags. Format lock stays."""
        self._anima_ghost_kill_all()
        gm = mido.Message("sysex", data=[0x7E, 0x7F, 0x09, 0x01])
        gs = self._gs_dt1([0x40, 0x00, 0x7F], [0x00])
        xg = mido.Message("sysex", data=[0x43, 0x10, 0x4C, 0x00, 0x00, 0x7E, 0x00])
        # MT-32 all-parameters reset (7F 00 00 01 00)
        mt_body = [0x7F, 0x00, 0x00, 0x01, 0x00]
        mt_ck = _roland_checksum(mt_body)
        mt = mido.Message("sysex", data=[0x41, 0x10, 0x16, 0x12, *mt_body, mt_ck])
        sent = []
        for i, tags in enumerate(self.out_formats):
            names = {str(x).lower() for x in tags}
            msgs = []
            if names & {"gs", "gs55", "gs88", "gs88pro", "gs8850", "gs8820", "sc", "sc-8850", "sc8850"}:
                msgs = [gm, gs]
                kind = "GS"
            elif names & {"xg"}:
                msgs = [gm, xg]
                kind = "XG"
            elif names & {"mt32", "mt-32", "mt", "cm"}:
                msgs = [mt]
                kind = "MT-32"
            else:
                msgs = [gm]
                kind = "GM"
            for m in msgs:
                self._safe_out_send(i, m)
            sent.append(f"{kind}:P{i + 1}")
        self.panic(reason=reason)
        self._gs_reset_part_rx()
        self._anima_reset_session(reason)
        self._set_status(f"Reset {', '.join(sent)} ({reason})", duration=3.0)

    def _anima_release_efx_lock(self, reason: str = "") -> None:
        """Drop file-owned EFX ban so Anima can pick again (test / format clear)."""
        had = bool(self._anima_file_efx_t) or bool(self._anima_efx_key)
        self._anima_file_efx_t = 0.0
        self._anima_file_efx_home = None
        self._anima_file_efx_type = None
        self._anima_file_efx_parts = set()
        self._anima_file_dirt = [False] * 16
        self._anima_hetfield_roll = [False] * 16
        self._anima_file_off_sent = set()
        self._anima_file_park = []
        self._anima_file_prev_typ = None
        self._anima_file_last_typ = None
        self._anima_efx_key = None
        self._anima_efx_sent = None
        self._anima_efx_hero = None
        self._anima_efx_label = ""
        self._gs_efx_parts_on = [False] * 16
        self._anima_slots = [{} for _ in range(self.n_ports)]
        self._anima_settle_q = []
        self._anima_settle_on = {}
        self._anima_efx_settle = [0.0] * self.n_ports
        self._anima_settle_bypass = False
        self._anima_ch_port = {}
        self._anima_fam_was = [None] * 16
        self._anima_note_port = {}
        self._anima_efx_on = [[False] * 16 for _ in range(self.n_ports)]
        self._anima_split_restore()
        if had and reason:
            self._anima_feedback("efx", f"EFX lock cleared ({reason})", status=True)
    def _anima_park_file_efx(self, old_typ: tuple, home: int, chs=None) -> None:
        """Keep a file insert that just lost P1 on the next GS unit (ahead of Anima extras)."""
        gs = [p for p in self._anima_gs_ports() if p != home]
        if not gs or not old_typ:
            return
        used = {home} | {p.get("port") for p in self._anima_file_park}
        dest = next((p for p in gs if p not in used), None)
        if dest is None:
            dest = next(
                (p for p in gs
                 if (self._anima_slots[p] if p < len(self._anima_slots) else {}).get("fam") != "file_park"),
                gs[0],
            )
        if chs is None:
            chs = sorted(self._anima_file_efx_parts)
        chs = [c for c in chs if c not in (9,)]
        if not chs:
            return
        self._anima_file_park = [p for p in self._anima_file_park if p.get("port") != dest]
        self._anima_file_park.append({
            "port": dest, "typ": old_typ, "chs": chs,
            "t": time.monotonic(), "heard": time.monotonic(),
        })
        self._anima_efx_ours = True
        self._safe_out_send(dest, self._gs_dt1([0x40, 0x03, 0x00], [old_typ[0], old_typ[1]]))
        for c in chs:
            self._anima_efx_ours = True
            self._safe_out_send(
                dest, self._gs_dt1([0x40, self._gs_efx_part_mid(c), 0x22], [0x01])
            )
            self._anima_efx_on[dest][c] = True
            # Keep those parts sounding on the parked insert, not only home.
            self._anima_ch_port[c] = dest
        self._anima_slots[dest] = {
            "fam": "file_park", "chs": chs, "split": False, "typ": old_typ, "t": time.monotonic()
        }
        self._anima_feedback(
            "efx-park",
            f"file EFX {old_typ[0]:02X} {old_typ[1]:02X} parked on P{dest + 1}",
            status=True,
        )

    def _anima_unpark(self, ch=None, reason: str = "") -> None:
        """Drop file-parks for a channel (or all empty parks). Slot goes back to Anima."""
        parks = list(getattr(self, "_anima_file_park", []) or [])
        if not parks:
            return
        keep = []
        dropped = []
        for park in parks:
            chs = [c for c in (park.get("chs") or []) if ch is None or c != ch]
            if not chs:
                dropped.append(park)
                continue
            park = dict(park)
            park["chs"] = chs
            keep.append(park)
        if not dropped and keep == parks:
            return
        self._anima_file_park = keep
        for park in dropped:
            port = park.get("port")
            if port is None:
                continue
            sl = self._anima_slots[port] if port < len(self._anima_slots) else {}
            if sl.get("fam") == "file_park":
                self._anima_clear_slot(port)
            for c in park.get("chs") or []:
                if self._anima_ch_port.get(c) == port:
                    self._anima_ch_port.pop(c, None)
        if dropped and reason:
            ports = ",".join(f"P{p.get('port', 0)+1}" for p in dropped)
            self._anima_feedback("efx-park", f"unpark {ports} ({reason})", status=True)

    def _anima_park_on_program(self, ch: int) -> None:
        ch = ch & 0x0F
        if any(ch in (p.get("chs") or []) for p in self._anima_file_park):
            self._anima_unpark(ch, "PC/bank")

    def _anima_park_idle_poll(self) -> None:
        if not self._anima_file_park:
            return
        now = time.monotonic()
        idle = ANIMA_GAME_IDLE_SEC if self.anima_game else ANIMA_EFX_IDLE_SEC
        gone = []
        for park in self._anima_file_park:
            chs = park.get("chs") or []
            if any(self._anima_ch_has_notes(c) for c in chs):
                park["heard"] = now
                continue
            heard = park.get("heard") or park.get("t") or now
            if now - heard >= idle:
                gone.extend(chs)
        for c in sorted(set(gone)):
            self._anima_unpark(c, "idle")

    def _anima_refresh_file_dirt(self) -> None:
        """Clean/acoustic/mute PCs whose FILE insert is an OD/dist type."""
        dirt_type = self._anima_file_efx_type in ANIMA_FILE_DIRT_TYPES
        for ch in range(16):
            fam = None
            try:
                if not self._anima_is_rhythm(ch):
                    fam = self._anima_efx_family(ch)
            except Exception:
                fam = None
            on = dirt_type and ch in self._anima_file_efx_parts and fam in ANIMA_FILE_DIRT_FAMS
            self._anima_file_dirt[ch] = bool(on)
            if on and not self._anima_hetfield_roll[ch]:
                mix = self._anima_mix(ch * 17)
                self._anima_hetfield_roll[ch] = (mix % 10) < 7
            if on:
                self._anima_feedback(
                    "dirt",
                    f"ch{ch + 1} file-dirt ({'Hetfield' if self._anima_hetfield_roll[ch] else 'alt'})",
                    status=True,
                )

    def _anima_file_off_park(self, part: int, home: int, src: str = "") -> None:
        """Park a file insert that just lost a part. Always log so we can see misses."""
        typ = (
            getattr(self, "_anima_file_prev_typ", None)
            or self._anima_file_efx_type
            or getattr(self, "_anima_file_last_typ", None)
        )
        was = part in (self._anima_file_efx_parts or set())
        self._anima_feedback(
            "efx-park",
            f"Off Part {part + 1} typ={typ} in_set={was} src={src}",
            status=True,
        )
        if typ and home is not None:
            self._anima_park_file_efx(typ, home, [part])
        self._anima_file_efx_parts.discard(part)

    def _anima_observe_file_efx(self, msg: mido.Message, description: str, quiet: bool = False) -> None:
        """File EFX owns the home GS port only; other :gs units stay Anima."""
        if not self.anima:
            return
        # Only ignore our own echo, not the next file SysEx.
        if msg.type == "sysex":
            sig = tuple(int(b) & 0xFF for b in (msg.data or [])[:10])
            bag = getattr(self, "_anima_efx_sent_sig", None) or []
            if sig in bag:
                self._anima_efx_sent_sig = [s for s in bag if s != sig]
                self._anima_efx_ours = False
                return
        self._anima_efx_ours = False
        desc = (description or "").lower()
        if "gs reset" in desc or desc.startswith("xg system on") or "gm system on" in desc:
            self._anima_release_efx_lock("reset")
            self._anima_reset_efx_seed()
            return
        data = list(msg.data) if msg.type == "sysex" else []
        if data and data[0] == 0xF0:
            data = data[1:]
        if data and data[-1] == 0xF7:
            data = data[:-1]
        gs = self._anima_gs_ports()
        home = gs[0] if gs else None
        changed = False
        if "gs efx off" in desc and home is not None:
            part = None
            for tok in desc.replace("→", " ").replace(",", " ").split():
                if tok.isdigit():
                    part = int(tok) - 1
                    break
            if part is not None and 0 <= part <= 15:
                self._anima_file_off_park(part, home, src="desc")
        if len(data) >= 9 and data[0] == 0x41 and data[2] == 0x42 and data[3] == 0x12:
            aa, bb, cc = data[4], data[5], data[6]
            if aa == 0x40 and bb == 0x03 and cc == 0x00:
                typ = (data[7] & 0x7F, data[8] & 0x7F)
                if typ != (0x00, 0x00):
                    prev = self._anima_file_efx_type
                    # Type change with the same parts still On = file replaced
                    # the insert under those players. Do NOT park them.
                    # Handoff is Part Off only.
                    if prev and prev != typ:
                        self._anima_file_prev_typ = prev
                    self._anima_file_efx_type = typ
                    self._anima_file_last_typ = typ
                    self._anima_file_efx_t = time.monotonic()
                    self._anima_file_efx_home = home
                    changed = True
            elif aa == 0x40 and cc == 0x22:
                part = self._gs_mid_to_part(bb)
                if part is not None:
                    if data[7] == 0x01:
                        self._anima_file_efx_parts.add(part)
                        self._anima_unpark(part, "file EFX on")
                        if (int(self._anima_prog[part]) & 0x7F) == 31:
                            self._anima_tone_slot[part] = None
                            self._anima_tone_cc0[part] = None
                            self._anima_cm64[part] = False
                            slot = self._anima_tone_pick(part, 31)
                            if slot:
                                cc0, cc32, pc_out = slot
                                for i in range(self.n_ports):
                                    if not self._anima_port_8850(i):
                                        continue
                                    self._safe_out_send(i, mido.Message("control_change", channel=part, control=0, value=cc0))
                                    self._safe_out_send(i, mido.Message("control_change", channel=part, control=32, value=cc32))
                                    self._safe_out_send(i, mido.Message("program_change", channel=part, program=pc_out))
                                self._anima_feedback("tone", f"keep Gt.Harmonics ch{part+1} (file EFX)", status=True)
                    else:
                        self._anima_file_off_park(part, home, src="syx")
                    self._anima_file_efx_t = time.monotonic()
                    self._anima_file_efx_home = home
                    changed = True
        elif desc.startswith("gs efx") or "insertion" in desc or "xg variation" in desc:
            if "thru" in desc:
                return
            self._anima_file_efx_t = time.monotonic()
            self._anima_file_efx_home = home
            changed = True
        if changed:
            self._anima_refresh_file_dirt()
            if home is not None:
                for c in self._anima_file_efx_parts:
                    self._anima_ch_port[c] = home
            if not quiet:
                parts = ",".join(str(p + 1) for p in sorted(self._anima_file_efx_parts)) or "-"
                self._anima_feedback(
                    "efx-file",
                    f"file EFX on P{(home or 0) + 1} parts {parts}",
                    status=True,
                )

    def _anima_observe_rhythm(self, msg: mido.Message, quiet: bool = False) -> None:
        """Track GS 'use for rhythm' so Anima never puts EFX on a drum part."""
        if not self.anima:
            return
        if msg.type != "sysex":
            return
        data = list(msg.data)
        if len(data) < 8:
            return
        if not (data[0] == 0x41 and data[2] == 0x42 and data[3] == 0x12):
            return
        aa, bb, cc = data[4], data[5], data[6]
        if aa == 0x40 and bb == 0x00 and cc == 0x7F:
            self._anima_rhythm = [False] * 16
            self._anima_rhythm[9] = True
            return
        if aa == 0x40 and cc == 0x15:
            part = self._gs_mid_to_part(bb)
            if part is None:
                return
            on = bool(data[7])
            if part == 9:
                on = True
            self._anima_rhythm[part] = on
            if on and not quiet:
                self._anima_feedback(
                    "rhythm",
                    f"GS drums on ch{part + 1} — Anima EFX skipped",
                    status=True,
                )

    def _anima_is_rhythm(self, ch: int) -> bool:
        ch = ch & 0x0F
        if ch == 9:
            return True
        return bool(self._anima_rhythm[ch])

    def _anima_efx_from_cat(self, cat: str | None) -> str | None:
        """Coarse phrasing category → insertion family (MT-32 / bank 127)."""
        return {
            "guitar": "guitar_clean",
            "bass": "bass_wide",
            "lead": "lead",
            "strings": "strings",
            "ensemble": "strings",
            "pad": "pad",
            "brass": "orch_brass",
            "wind": "ethnic_wind",
            "organ": "organ_chorus",
            "piano": "piano_acoustic",
            "harmonica": "harmonica",
            "ethnic": "ethnic_wind",
        }.get(cat or "")

    def _anima_ch_lfo_insert(self, ch: int) -> bool:
        """True if this channel is currently patched through a modulating insert."""
        ch = ch & 0x0F
        port = self._anima_ch_port.get(ch)
        if port is None:
            port = self._anima_note_port.get(ch)
        if port is None or port >= len(self._anima_slots):
            return False
        typ = self._anima_slots[port].get("typ")
        if not typ:
            return False
        if ch not in (self._anima_slots[port].get("chs") or []):
            # Sounding on this box with EFX still armed
            if port < len(self._anima_efx_on) and not self._anima_efx_on[port][ch]:
                return False
        return tuple(typ)[:2] in ANIMA_LFO_EFX

    def _anima_efx_family(self, ch: int) -> str | None:
        """Map program (+ GS bank) to an Anima GS insertion family."""
        if self._anima_is_rhythm(ch):
            return None
        ch = ch & 0x0F
        p = int(self._anima_prog[ch]) & 0x7F
        try:
            msb = int(self.bank_msb[ch]) & 0x7F
        except Exception:
            msb = 0
        # GS bank 127 is the MT-32 / CM-32L map — GM PC 31 is Dist Gtr,
        # MT-32 PC 31 is syn bass.
        if msb == 127:
            return self._anima_efx_from_cat(_mt32_category(p))
        if msb == 126:
            return self._anima_efx_from_cat(_gm_category(p))
        if p <= 2:
            return "piano_acoustic"
        if p == 3 or 8 <= p <= 14:
            return "chromatic"
        if 96 <= p <= 103:
            return "fx"
        if p == 4:
            return "ep_rhodes"
        if p == 5:
            return "ep_dx"
        if p in (6, 7):
            return "keys_pluck"
        if p in (16, 17, 18):
            return "organ_rotary"   # Drawbar / Percussive / Rock
        if p == 22:
            return "harmonica"
        if 19 <= p <= 23:
            return "organ_chorus"   # Church / Reed / Accordion
        if p in (24, 25):
            return "guitar_acoustic"
        if p in (26, 27):
            return "guitar_clean"
        if p == 28:
            return "guitar_mute"
        if 29 <= p <= 31:
            return "guitar_dist"
        if p == 32:
            return "bass_acoustic"   # upright — never Bass Multi
        if p in (33, 34):
            return "bass_electric"   # finger / picked — Bass Multi ok
        if p in (35, 36, 37, 38, 39):
            return "bass_wide"       # fretless / slap / synth — stay stereo
        if 56 <= p <= 61:
            return "orch_brass"      # GM 57–62 Trumpet … Brass Section
        if p in (62, 63):
            return "synth_brass"     # GM 63–64 Synth Brass 1 and 2
        if 40 <= p <= 55:
            return "strings"         # Violin…Timp + ensemble/choir (48–55)
        if p in (64, 65, 66, 67, 68, 69, 70, 71, 72, 73):
            return "ethnic_wind"     # Sax / flute / recorder (was unmapped → no slot)
        if p in (74, 75, 76, 77, 78):
            return "ethnic_wind"     # Pan Flute … Ocarina
        if 80 <= p <= 87:
            return "lead"            # Square / Saw / Charang / Voice / 5ths
        if 88 <= p <= 95:
            return "pad"
        if p == 15 or 104 <= p <= 107:
            return "plucked"
        return None

    def _anima_gs_ports(self) -> list[int]:
        ports = []
        fmt = (getattr(self, "detected_format", None) or "").upper()
        for i, tags in enumerate(self.out_formats):
            names = {str(t).lower() for t in tags}
            if names & {"xg", "mt32", "mt-32", "mt"}:
                continue
            cls = self._gs_canvas_class(names)
            # Insertion EFX only exists on 88Pro/880 and 8820/8850.
            if cls in ("88pro", "8850"):
                ports.append(i)
            elif names <= {"any"} and fmt in ("GS", "SC", "SC-8850", "8850"):
                ports.append(i)
        return ports


    @staticmethod
    def _anima_pcs_compatible(union: set) -> bool:
        """True if a pitch-class set is still 'one guitar part' (double/power/triad)."""
        pcs = {int(p) % 12 for p in union}
        n = len(pcs)
        if n <= 1:
            return True
        if n == 2:
            a, b = sorted(pcs)
            iv = min((b - a) % 12, (a - b) % 12)
            return iv in (3, 4, 5, 7)
        if n == 3:
            for r in range(12):
                rel = frozenset((p - r) % 12 for p in pcs)
                if rel in ({0, 4, 7}, {0, 3, 7}, {0, 3, 6}, {0, 4, 8}):
                    return True
            return False
        return False

    def _anima_guitar_dist_chs(self) -> list:
        return sorted({
            k[0] for k in self.active
            if k[0] != 9 and self._anima_efx_family(k[0]) == "guitar_dist"
        })

    def _anima_channel_pcs(self, ch: int) -> set:
        return {k[1] % 12 for k in self.active if k[0] == ch}

    def _anima_guitar_conflict(self) -> bool:
        chs = self._anima_guitar_dist_chs()
        if len(chs) < 2:
            return False
        sets = [self._anima_channel_pcs(c) for c in chs]
        sets = [s for s in sets if s]
        if len(sets) < 2:
            return False
        if all(s == sets[0] for s in sets):
            return False
        union = set().union(*sets)
        return not self._anima_pcs_compatible(union)

    def _anima_split_restore(self) -> None:
        """Put back any CC10 we wrote for OD1/OD2."""
        saved = getattr(self, "_anima_split_saved_pan", None) or {}
        self._anima_split_on = False
        if not saved:
            self._anima_split_saved_pan = {}
            return
        ports = self._anima_gs_ports()
        for ch, val in saved.items():
            self.pan[ch] = val
            if ports and val is not None:
                self._anima_send_cc(ports, ch, 10, int(val) & 0x7F)
        self._anima_split_saved_pan = {}

    def _anima_apply_od_split(self, chs: list, ports: list | None = None) -> None:
        """OD1/OD2 on the slot that owns these guitars only.

        Writing the insert to every GS port stomped Bass Multi / flanger
        on the other boxes and looked like EFX in-fighting.
        """
        if ports is None:
            ports = self._anima_gs_ports()
        ports = [p for p in ports if 0 <= p < self.n_ports]
        if not ports:
            return
        now = time.monotonic()
        orig = []
        for c in chs:
            v = self.pan[c]
            if c in self._anima_split_saved_pan and self._anima_split_saved_pan[c] is not None:
                orig.append(int(self._anima_split_saved_pan[c]))
            else:
                orig.append(64 if v is None else int(v))
        if len(chs) == 1:
            sides = ["L" if orig[0] <= 64 else "R"]
        else:
            # Prefer already-left / already-right; else chs[0]=L, chs[1]=R.
            sides = []
            for v in orig:
                if v <= ANIMA_SPLIT_PAN_LO:
                    sides.append("L")
                elif v >= ANIMA_SPLIT_PAN_HI:
                    sides.append("R")
                else:
                    sides.append(None)
            if sides.count("L") == 0:
                sides[0] = "L"
            if len(sides) > 1 and sides.count("R") == 0:
                idx = 1 if sides[0] == "L" else 0
                sides[idx] = "R"
            for i, s in enumerate(sides):
                if s is None:
                    sides[i] = "L" if sides.count("L") <= sides.count("R") else "R"
        od1_pan = 0
        od2_pan = 127
        for c, s, v in zip(chs, sides, orig):
            if s == "L":
                od1_pan = v
            else:
                od2_pan = v
            if c not in self._anima_split_saved_pan:
                self._anima_split_saved_pan[c] = self.pan[c] if self.pan[c] is not None else 64
            hard = 0 if s == "L" else 127
            self.pan[c] = hard
            self._anima_send_cc(ports, c, 10, hard)
        msgs = [
            self._gs_dt1([0x40, 0x03, 0x00], [ANIMA_SPLIT_MSB, ANIMA_SPLIT_LSB]),
            self._gs_dt1([0x40, 0x03, 0x03], [0x00]),  # OD1 = Overdrive
            self._gs_dt1([0x40, 0x03, 0x08], [0x01]),  # OD2 = Distortion
            self._gs_dt1([0x40, 0x03, 0x12], [int(od1_pan) & 0x7F]),
            self._gs_dt1([0x40, 0x03, 0x14], [int(od2_pan) & 0x7F]),
        ]
        self._anima_efx_ours = True
        for i in ports:
            for m in msgs:
                self._safe_out_send(i, m)
        self._anima_split_on = True
        self._anima_efx_sent = (ANIMA_SPLIT_MSB, ANIMA_SPLIT_LSB)
        self._anima_efx_key = "guitar_dist"
        self._anima_efx_label = ANIMA_SPLIT_LABEL
        self._anima_efx_switch_t = now
        hero = chs[0]
        for i in ports:
            for c in chs:
                self._anima_efx_ours = True
                self._safe_out_send(
                    i, self._gs_dt1([0x40, self._gs_efx_part_mid(c), 0x22], [0x01])
                )
                if i < len(self._anima_efx_on):
                    self._anima_efx_on[i][c] = True
        self._anima_efx_bind_and_seed(ANIMA_SPLIT_MSB, ANIMA_SPLIT_LSB, ports=ports)
        pair = "+".join(f"ch{c+1}" for c in chs[:4])
        self._anima_feedback(
            "efx",
            f"{pair} guitar_dist → GS {ANIMA_SPLIT_LABEL} (pan split)",
            status=True,
        )

    def _anima_maybe_guitar_split(self) -> None:
        # Mid-phrase OD1/OD2 upgrades were dry-firing the other guitars
        # on that box. Split is decided only at first commit.
        return
        if self._anima_efx_key != "guitar_dist":
            return
        if self._anima_split_on:
            return
        if not self._anima_guitar_conflict():
            return
        now = time.monotonic()
        if self._anima_efx_switch_t and (now - self._anima_efx_switch_t) < ANIMA_EFX_SWITCH_SEC:
            return
        chs = self._anima_guitar_dist_chs()
        if len(chs) < 2:
            return
        home = self._anima_gs_ports()
        self._anima_apply_od_split(chs, ports=home[:1] if home else [])


    def _anima_game_note_pc(self) -> None:
        now = time.monotonic()
        self._anima_game_pc_t.append(now)
        cut = now - ANIMA_GAME_PC_WINDOW
        self._anima_game_pc_t = [x for x in self._anima_game_pc_t if x >= cut]

    def _anima_game_poll(self) -> None:
        """After a PC dump settles, reroll EFX if the 16-program map moved."""
        if not (self.anima and self.anima_game):
            return
        # Locked game mode still changes scenes; salt makes them repeatable.
        if self.anima_efx_stable and not getattr(self, "_anima_seed_locked", False):
            return
        if len(self._anima_game_pc_t) < ANIMA_GAME_PC_BURST:
            return
        now = time.monotonic()
        if now - self._anima_game_pc_t[-1] < ANIMA_GAME_PC_SETTLE:
            return
        snap = tuple(int(x) & 0x7F for x in self._anima_prog)
        prev = self._anima_game_snap
        self._anima_game_pc_t = []
        if prev is None:
            self._anima_game_snap = snap
            return
        diff = sum(1 for a, b in zip(prev, snap) if a != b)
        self._anima_game_snap = snap
        if diff < ANIMA_GAME_SNAP_DIFF:
            return
        self._anima_reset_efx_seed()
        self._anima_tone_cc0 = [None] * 16
        self._anima_tone_slot = [None] * 16
        self._anima_cm64 = [False] * 16
        # Unstick ports so the next family map can land on a fresh box.
        home = self._anima_file_home_port()
        for p in self._anima_gs_ports():
            if p == home:
                continue
            if self._anima_slots[p].get("fam"):
                self._anima_clear_slot(p)
        self._anima_ch_port = {}
        self._anima_fam_was = [None] * 16
        self._anima_efx_sound_t = {}
        self._anima_fam_played = {}     # family -> last real note (not a PC)
        self._anima_efx_burst_dirty = False  # PC dump waiting for one settle
        self._anima_efx_burst_t = 0.0
        self._anima_efx_seek_t = [0.0] * 16
        self._anima_feedback("game", f"new cue ({diff} PCs) — EFX/tone reroll", status=True)

    def _anima_reroll_tones(self) -> None:
        """Re-pick and send variation slots for programs we already learned."""
        if not self.anima:
            return
        for ch in range(16):
            if self._anima_is_rhythm(ch):
                continue
            if not (self._file_used_ch[ch] or int(self._anima_prog[ch]) != 0):
                continue
            pc = int(self._file_pc[ch] if self._file_used_ch[ch] else self._anima_prog[ch]) & 0x7F
            slot = self._anima_tone_pick(ch, pc)
            if not slot:
                continue
            for i in range(self.n_ports):
                if not self._anima_port_8850(i):
                    continue
                adapted = self._anima_adapt_tone_slot(i, slot)
                if not adapted:
                    continue
                cc0, cc32, pc_out = adapted
                self._send_routed(i, mido.Message("control_change", channel=ch, control=32, value=cc32))
                self._send_routed(i, mido.Message("control_change", channel=ch, control=0, value=cc0))
                if cc0 in (126, 127):
                    self._send_routed(i, mido.Message("control_change", channel=ch, control=32, value=cc32))
                    self._send_routed(i, mido.Message("control_change", channel=ch, control=0, value=cc0))
                self._send_routed(i, mido.Message("program_change", channel=ch, program=pc_out))
            self._anima_feedback(
                "tone",
                f"reroll ch{ch + 1} GM{pc + 1} → CC00={cc0:03d} map{cc32} PC{pc_out + 1}",
                status=True,
            )

    def _anima_reset_efx_seed(self) -> None:
        if getattr(self, "_anima_seed_locked", False):
            # Keep the hex. Drop cached picks so the next cue/X can
            # recompute from seed (+ scene salt in game mode).
            self._anima_efx_pick = {}
            self._anima_bass_sub_choice = None
            return
        self._anima_efx_seed = None
        self._anima_efx_pick = {}
        self._anima_bass_sub_choice = None
        self._anima_efx_launch = None
        if self.anima:
            self._anima_ensure_efx_seed()

    def _anima_ensure_efx_seed(self) -> int:
        if self._anima_efx_seed is not None:
            return int(self._anima_efx_seed) & 0xFFFF
        if not getattr(self, "_anima_efx_launch", None):
            self._anima_efx_launch = random.randrange(1, 0x10000)
        snap = tuple(int(x) & 0x7F for x in self._anima_prog)
        self._anima_efx_seed = (hash(snap) ^ self._anima_efx_launch) & 0xFFFF
        self._log_line(f"ANIMA seed {self._anima_efx_seed:04X}")
        return self._anima_efx_seed

    def _anima_scene_salt(self) -> int:
        """Game mode: FNV-ish hash of the 16-PC snapshot.

        Same cue + locked seed → same tones/inserts. A different snapshot
        (new area) → different rolls. Normal Anima: 0 so only seed+ch+PC
        matter.
        """
        if not getattr(self, "anima_game", False):
            return 0
        snap = getattr(self, "_anima_game_snap", None)
        if not snap:
            snap = tuple(int(x) & 0x7F for x in self._anima_prog)
        h = 0x811C9DC5
        for pc in snap:
            h ^= (int(pc) + 1) * 0x01000193
            h &= 0xFFFFFFFF
        return h & 0xFFFF

    def _anima_mix(self, *parts: int) -> int:
        seed = self._anima_ensure_efx_seed()
        acc = (seed + self._anima_scene_salt()) & 0xFFFF
        for part in parts:
            acc = (acc + int(part)) & 0xFFFF
        return acc

    def _anima_toggle_seed_lock(self) -> None:
        if not self.anima:
            self._set_status("Anima off — seed lock ignored", duration=2.0)
            return
        self._anima_ensure_efx_seed()
        self._anima_seed_locked = not bool(self._anima_seed_locked)
        seed = int(self._anima_efx_seed) & 0xFFFF
        if self._anima_seed_locked:
            self._log_line(f"ANIMA seed LOCK {seed:04X}")
            extra = " + scene salt" if self.anima_game else ""
            self._set_status(
                f"Anima seed LOCK {seed:04X}{extra} — X keeps hex, cues stay repeatable",
                duration=4.0,
            )
        else:
            self._log_line(f"ANIMA seed unlock {seed:04X}")
            self._set_status(f"Anima seed unlock {seed:04X} — X/idle will reroll", duration=3.0)

    def _anima_palette_pick(self, fam: str, port: int | None = None, chs=None):
        """Keep a player's type when they relocate; new player in same fam gets another row."""
        # Rows are (msb, lsb, name, weight); callers get (msb, lsb, name).
        pal = [
            (r[0], r[1], r[2], int(r[3]) if len(r) > 3 else 2)
            for r in (ANIMA_EFX_GS.get(fam) or [])
        ]
        if port is not None:
            tags = self.out_formats[port] if port < len(self.out_formats) else set()
            cls = self._gs_canvas_class(tags)
            # 88Pro/880 and 8820/8850 share the same 64 insertion types.
            if cls not in ("88pro", "8850"):
                return None
        if not pal:
            return None
        chs_set = set(chs or [])
        # OD1/OD2 is a two-player insert. Never seed it for a lone guitar.
        if fam == "guitar_dist" and len(chs_set) < 2:
            pal = [row for row in pal if (row[0], row[1]) != (ANIMA_SPLIT_MSB, ANIMA_SPLIT_LSB)]
            if not pal:
                return None
        # A panned lone guitar keeps its side: GTR Multi has no Output Pan
        # here, so it collapsed hard-panned guitars to the middle.
        want_pan = False
        if fam == "guitar_dist" and len(chs_set) < 2 and chs_set:
            want_pan = any(
                abs(int(self.pan[c] if self.pan[c] is not None else 64) - 64) > ANIMA_EFX_PAN_OFF
                for c in chs_set
            )
            if want_pan:
                panned = [row for row in pal if (row[0], row[1]) in ANIMA_EFX_PAN_SLOT]
                if panned:
                    pal = panned
                else:
                    want_pan = False
        # MandolinTrem already has a built-in tremolo — no delay/echo insert.
        trem = False
        for c in chs_set:
            sl = self._anima_tone_slot[c] if c < 16 else None
            if sl and sl[0] == 17 and sl[2] == 25:
                trem = True
                break
        if trem:
            pal = [
                row for row in pal
                if "delay" not in str(row[2]).lower()
                and "echo" not in str(row[2]).lower()
            ]
            if not pal:
                pal = [(0x01, 0x02, "Enhancer", 2)]

        def _from_typ(typ):
            if not typ:
                return None
            if want_pan and tuple(typ)[:2] not in ANIMA_EFX_PAN_SLOT:
                return None
            for row in pal:
                if (row[0], row[1]) == tuple(typ)[:2]:
                    return tuple(row[:3])
            return (typ[0], typ[1], fam)

        # Same channels already on a slot → keep that insert (relocation).
        same = [s for s in self._anima_slots if s.get("fam") == fam and s.get("typ")]
        for slot in same:
            old_chs = set(slot.get("chs") or [])
            if chs_set and (chs_set & old_chs):
                kept = _from_typ(slot.get("typ"))
                if kept:
                    return kept
        # Family moving to another unit: take the insert with you.
        if len(same) == 1:
            kept = _from_typ(same[0].get("typ"))
            if kept:
                return kept
        live = set()
        ft = self._anima_file_efx_type
        if ft:
            live.add(tuple(ft)[:2])
        for i, slot in enumerate(self._anima_slots):
            if slot.get("typ") and i != port:
                live.add(tuple(slot["typ"])[:2])
        exclusive_live = live & ANIMA_EFX_EXCLUSIVE

        key = (fam, port)
        cached = self._anima_efx_pick.get(key)
        if cached and (cached[0], cached[1]) not in exclusive_live:
            return cached
        mix = self._anima_mix(sum(ord(c) for c in fam) * 31, 0 if port is None else (port + 1) * 97)
        # Weighted by the picker: favoured ×2, less often ×½.
        total = sum(max(1, row[3]) for row in pal)
        roll = mix % total
        pick = pal[-1]
        for row in pal:
            roll -= max(1, row[3])
            if roll < 0:
                pick = row
                break
        used = {
            (v[0], v[1])
            for k, v in self._anima_efx_pick.items()
            if isinstance(k, tuple) and k[0] == fam and v
        }
        used |= live
        def _blocked(row):
            typ = (row[0], row[1])
            return typ in exclusive_live or (typ in used and typ in ANIMA_EFX_EXCLUSIVE)
        if _blocked(pick) and len(pal) > 1:
            for alt in pal:
                if not _blocked(alt):
                    pick = alt
                    break
        pick = tuple(pick[:3])
        self._anima_efx_pick[key] = pick
        return pick



    def _anima_organ_vol_gain(self, raw: int) -> int:
        """75 and below → ×1.4; 127 → ×1.0; linear in between."""
        raw = max(0, min(127, int(raw)))
        if raw >= ANIMA_ORGAN_VOL_HI:
            return raw
        if raw <= ANIMA_ORGAN_VOL_LO:
            gain = ANIMA_ORGAN_VOL_GAIN_LO
        else:
            span = float(ANIMA_ORGAN_VOL_HI - ANIMA_ORGAN_VOL_LO)
            u = (raw - ANIMA_ORGAN_VOL_LO) / span
            gain = ANIMA_ORGAN_VOL_GAIN_LO + u * (
                ANIMA_ORGAN_VOL_GAIN_HI - ANIMA_ORGAN_VOL_GAIN_LO
            )
        return min(127, int(round(raw * gain)))

    def _anima_organ_rotary_ch(self, ch: int) -> bool:
        if not self.anima:
            return False
        for slot in self._anima_slots:
            if ch not in (slot.get("chs") or []):
                continue
            typ = slot.get("typ") or ()
            lab = (self._anima_efx_label or "").lower() if typ else ""
            # Prefer the type tuple; fall back to last label on that slot
            if typ[:2] in ANIMA_EFX_ROTARY:
                return True
            fam = slot.get("fam") or ""
            if fam in ("organ_rotary", "organ") and typ:
                return True
        return False

    def _anima_organ_vol_lift(self, port: int, chs: list, label: str) -> None:
        """Rotary / Organ Multi eats level — lift file CC7 on every GS port."""
        lab = (label or "").lower()
        if "rotary" not in lab and "organ multi" not in lab:
            return
        targets = self._anima_gs_ports() or [port]
        for ch in chs or []:
            cur = self._file_vol[ch]
            if cur is None:
                cur = self.vol[ch]
            if cur is None:
                cur = 100
            new = self._anima_organ_vol_gain(cur)
            if new <= cur:
                continue
            msg = mido.Message("control_change", channel=ch, control=7, value=new)
            for i in targets:
                self._send_routed(i, msg)
            self.vol[ch] = new
            self.vol_time[ch] = time.monotonic()
            self._anima_feedback(
                "efx",
                f"ch{ch + 1} organ CC7 {cur}→{new} ({len(targets)} ports)",
                status=True,
            )

    # ------------------------------------------------------------------
    # Beat tracking (for delay-time inserts)
    # ------------------------------------------------------------------
    def _tempo_feed(self, msg, now: float) -> None:
        if msg.type == "clock":
            if self._tempo_clock_t and 0.004 < now - self._tempo_clock_t < 0.2:
                iv = now - self._tempo_clock_t
                self._tempo_clock_iv = iv if not self._tempo_clock_iv else self._tempo_clock_iv * 0.9 + iv * 0.1
            self._tempo_clock_t = now
            return
        ons = self._tempo_onsets
        if ons and now - ons[-1] < 0.04:
            return  # same chord / strum
        ons.append(now)
        cut = now - 12.0
        if len(ons) > 256 or (ons and ons[0] < cut):
            self._tempo_onsets = [t for t in ons[-256:] if t >= cut]

    def _anima_beat_sec(self) -> float:
        """Beat length in seconds, or 0.0 when there is not enough to go on."""
        now = time.monotonic()
        if self._tempo_clock_iv and now - self._tempo_clock_t < 1.0:
            return self._tempo_clock_iv * 24.0
        if self._tempo_beat_t and now - self._tempo_beat_t < 2.0:
            return self._tempo_beat
        self._tempo_beat_t = now
        ons = [t for t in self._tempo_onsets if t >= now - 12.0]
        if len(ons) < 12:
            self._tempo_beat = 0.0
            return 0.0
        # Histogram of onset-to-onset gaps (10 ms bins, up to 2.2 s).
        hist = [0.0] * 221
        for i, a in enumerate(ons):
            for b in ons[i + 1:]:
                gap = b - a
                if gap > 2.2:
                    break
                if gap >= 0.1:
                    hist[int(gap * 100 + 0.5)] += 1.0

        def h(sec: float) -> float:
            k = int(sec * 100 + 0.5)
            if k < 1 or k > 219:
                return 0.0
            return hist[k] + 0.5 * (hist[k - 1] + hist[k + 1])

        best, best_t = 0.0, 0.0
        for ms in range(250, 1251, 5):
            t = ms / 1000.0
            s = h(t) + 0.5 * h(t / 2) + 0.5 * h(2 * t) + 0.33 * h(3 * t)
            if s > best:
                best, best_t = s, t
        while best_t and best_t < 0.4:
            best_t *= 2
        while best_t > 0.8:
            best_t /= 2
        self._tempo_beat = best_t
        return best_t

    # ------------------------------------------------------------------
    # Insert shaping: delay times / feedback, pitch intervals, gate type
    # ------------------------------------------------------------------
    def _anima_efx_dly_upkeep(self) -> None:
        """Set delay times once the beat is known (or has moved), box quiet only."""
        now = time.monotonic()
        if now - getattr(self, "_anima_dly_check_t", 0.0) < 1.0:
            return
        self._anima_dly_check_t = now
        beat = self._anima_beat_sec()
        if not beat:
            return
        for port, sl in enumerate(self._anima_slots):
            typ = tuple(sl.get("typ") or ())[:2]
            dly = ANIMA_EFX_DELAY.get(typ)
            if not dly or not dly["times"]:
                continue
            old = float(sl.get("dly_beat") or 0.0)
            if old and abs(beat - old) / old < 0.12:
                continue
            chs = list(sl.get("chs") or [])
            if self._anima_port_players_sounding(port):
                continue
            if now - float(sl.get("heard_t") or 0.0) < 1.5:
                continue  # let the echo tail die before moving the time
            self._anima_efx_shape(port, typ, chs, sl.get("fam"))

    @staticmethod
    def _gs_dly_index(scale: int, ms: float) -> int:
        tab = GS_DLY_MS[scale]
        return min(range(128), key=lambda i: abs(tab[i] - ms))

    def _anima_efx_shape(self, port: int, typ: tuple, chs: list, fam: str | None) -> None:
        typ = tuple(typ or ())[:2]
        msgs = []
        notes = []
        seed = self._anima_ensure_efx_seed()
        dly = ANIMA_EFX_DELAY.get(typ)
        if dly:
            beat = self._anima_beat_sec()
            if beat and dly["times"]:
                # One factor (halve/double) for every tap, so the taps keep
                # their rhythm instead of folding onto the same echo.
                scale = dly["times"][0][1]
                tab = GS_DLY_MS[scale]
                lo, hi = max(tab[1], 5.0), tab[-1]
                top = max(b for _a, _s, b in dly["times"])
                low = min(b for _a, _s, b in dly["times"])
                k = 1.0
                while beat * 1000.0 * top * k > hi:
                    k /= 2
                while beat * 1000.0 * low * k < lo and beat * 1000.0 * top * k * 2 <= hi:
                    k *= 2
                for addr, sc, beats in dly["times"]:
                    ms = min(hi, max(lo, beat * 1000.0 * beats * k))
                    msgs.append(self._gs_dt1([0x40, 0x03, addr], [self._gs_dly_index(sc, ms)]))
                sl = self._anima_slots[port] if 0 <= port < len(self._anima_slots) else None
                if sl is not None:
                    sl["dly_beat"] = beat
                notes.append(f"beat {beat * 1000:.0f}ms")
            addr, kind = dly["fb"]
            pct = ANIMA_EFX_FB_PCT_HELD if fam in ANIMA_EFX_FB_HELD_FAMS else ANIMA_EFX_FB_PCT
            pct = min(pct, ANIMA_EFX_FB_CAP_PCT)
            if kind == "pct":
                val = 0x40 + int(round(pct / 2.0))
            else:
                val = int(round(127 * pct / 100.0))
            msgs.append(self._gs_dt1([0x40, 0x03, addr], [val & 0x7F]))
            notes.append(f"fb {pct}%")
        voices = ANIMA_EFX_PITCH.get(typ)
        if voices:
            modes = ANIMA_EFX_PITCH_FAM_MODES.get(fam or "", ANIMA_EFX_PITCH_DEFAULT_MODES)
            mode = modes[self._anima_mix(seed, (port + 1) * 131 + len(fam or "")) % len(modes)]
            for (c_addr, f_addr), (semi, cents) in zip(voices, ANIMA_EFX_PITCH_MODES[mode]):
                msgs.append(self._gs_dt1([0x40, 0x03, c_addr], [max(0x28, min(0x4C, 0x40 + semi))]))
                msgs.append(self._gs_dt1([0x40, 0x03, f_addr], [max(0x0E, min(0x72, 0x40 + int(cents / 2)))]))
            if typ == (0x01, 0x61) and fam != "fx":
                msgs.append(self._gs_dt1([0x40, 0x03, 0x05], [0x40]))  # no feedback cascade
            notes.append(f"pitch {mode}")
        gate = ANIMA_EFX_GATE_TYPE.get(typ)
        if gate:
            addr, vals = gate
            v = vals[self._anima_mix(seed, port + 7) % len(vals)]
            msgs.append(self._gs_dt1([0x40, 0x03, addr], [v]))
            notes.append("sweep " + str(v - 1))
        if not msgs:
            return
        self._anima_efx_ours = True
        for m in msgs:
            self._safe_out_send(port, m)
        self._anima_feedback("efx-param", f"P{port + 1} {' · '.join(notes)}", status=False)

    def _anima_efx_bind_and_seed(self, msb: int, lsb: int, ports=None) -> None:
        """One-shot: bind CC16 to EFX Ctrl1, seed drive, set rotary/wah base."""
        ports = list(ports) if ports is not None else self._anima_gs_ports()
        if not ports:
            return
        seed = self._anima_ensure_efx_seed()
        key = (msb, lsb)
        # CC16 drives whichever EFX Control carries the wah / rotary speed
        # knob; the other depth sits at 0% (0x40) so CC16 moves nothing else.
        # Only wah and rotary types are driven by CC16. Everything else gets
        # 0 % on both, so a CC16 left over from a wah cannot push, say,
        # Stereo Delay's feedback (its Control 1 knob).
        live = key in ANIMA_EFX_WAH or key in ANIMA_EFX_ROTARY
        on2 = key in ANIMA_EFX_CTRL2
        msgs = [
            self._gs_dt1([0x40, 0x03, 0x1B], [ANIMA_EFX_CTRL_CC]),                  # C.Src1 = CC16
            self._gs_dt1([0x40, 0x03, 0x1C], [0x7F if live and not on2 else 0x40]),  # C.Dep1
            self._gs_dt1([0x40, 0x03, 0x1D], [ANIMA_EFX_CTRL_CC]),                  # C.Src2 = CC16
            self._gs_dt1([0x40, 0x03, 0x1E], [0x7F if live and on2 else 0x40]),      # C.Dep2
        ]
        if key in ANIMA_EFX_DRIVE_03:
            drive = 40 + (seed % 51)  # 40–90
            msgs.append(self._gs_dt1([0x40, 0x03, 0x03], [drive]))
        man = ANIMA_EFX_WAH_MAN.get(key)
        if man is not None:
            msgs.append(self._gs_dt1([0x40, 0x03, man], [0x40]))  # Wah Man center
        self._anima_efx_ours = True
        for i in ports:
            for m in msgs:
                self._safe_out_send(i, m)
        self._anima_efx_lfo_ph = 0.0
        self._anima_efx_cc16 = -1
        self._anima_rot_flipped = False
        self._anima_rot_fast = bool(seed & 1)
        if key in ANIMA_EFX_ROTARY:
            hero = self._anima_efx_hero if self._anima_efx_hero is not None else 0
            self._anima_send_cc(ports, hero, ANIMA_EFX_CTRL_CC, 127 if self._anima_rot_fast else 0)

    def _anima_efx_param_tick(self, dt: float) -> None:
        """CC16 wah LFO / rotary slow-fast while the insertion type supports it."""
        sent = self._anima_efx_sent
        if not sent or not self.anima:
            return
        ports = [
            i for i, sl in enumerate(self._anima_slots)
            if sl.get("typ") == sent
        ] or self._anima_gs_ports()
        if not ports:
            return
        hero = self._anima_efx_hero if self._anima_efx_hero is not None else 0
        now = time.monotonic()
        if sent in ANIMA_EFX_WAH:
            live = any(
                k[0] != 9 and self._anima_efx_family(k[0]) == self._anima_efx_key
                for k in self.active
            )
            if not live:
                return
            self._anima_efx_lfo_ph += dt * ANIMA_WAH_LFO_HZ * 6.28318530718
            val = int(64 + 48 * math.sin(self._anima_efx_lfo_ph))
            val = max(0, min(127, val))
            self._anima_send_cc(ports, hero, ANIMA_EFX_CTRL_CC, val)
            return
        if sent in ANIMA_EFX_ROTARY:
            longest = 0.0
            for key, info in self.active.items():
                ch = key[0]
                if ch == 9:
                    continue
                if self._anima_efx_family(ch) not in ("organ",):
                    # still allow rotary types on whatever family owns the slot
                    if self._anima_efx_family(ch) != self._anima_efx_key:
                        continue
                t0 = info.get("time") or 0.0
                if t0:
                    longest = max(longest, now - t0)
            want_flip = longest >= ANIMA_ROTARY_HOLD_SEC
            if want_flip and not self._anima_rot_flipped:
                self._anima_rot_flipped = True
                self._anima_send_cc(
                    ports, hero, ANIMA_EFX_CTRL_CC,
                    0 if self._anima_rot_fast else 127,
                )
            elif not want_flip and self._anima_rot_flipped:
                self._anima_rot_flipped = False
                self._anima_send_cc(
                    ports, hero, ANIMA_EFX_CTRL_CC,
                    127 if self._anima_rot_fast else 0,
                )


    def _anima_chs_conflict(self, chs: list) -> bool:
        sets = [self._anima_channel_pcs(c) for c in chs]
        sets = [s for s in sets if s]
        if len(sets) < 2:
            return False
        if all(s == sets[0] for s in sets):
            return False
        union = set().union(*sets)
        return not self._anima_pcs_compatible(union)

    def _anima_ch_pan(self, ch: int) -> int:
        v = self.pan[ch & 0x0F] if ch < 16 else None
        return 64 if v is None else int(v) & 0x7F

    def _anima_chs_spread(self, chs: list) -> bool:
        """Two players hard-panned apart — they should not share a mono insert."""
        if len(chs) < 2:
            return False
        pans = [self._anima_ch_pan(c) for c in chs[:4]]
        if max(pans) - min(pans) >= 28:
            return True
        left = any(p <= ANIMA_SPLIT_PAN_LO for p in pans)
        right = any(p >= ANIMA_SPLIT_PAN_HI for p in pans)
        return left and right

    def _anima_chs_want_split(self, chs: list) -> bool:
        """OD1/OD2 (or separate boxes) when they clash in pitch *or* in the stereo field."""
        return self._anima_chs_conflict(chs) or self._anima_chs_spread(chs)

    def _anima_file_home_port(self) -> int | None:
        """Reserve P1 only while the file actually owns an insert."""
        if not self._anima_file_efx_t:
            return None
        gs = self._anima_gs_ports()
        if self._anima_file_efx_home is not None:
            return self._anima_file_efx_home
        return gs[0] if gs else None

    def _anima_build_plan(self, extra_ch: int | None = None) -> list:
        """Global plan for the settled PC dump: one insert per GS unit by priority.

        Used by the burst settle only; a single note places its own channel
        with _anima_efx_place. Guitars pack 2-per-unit (OD1/OD2 if they clash).
        """
        gs_all = self._anima_gs_ports()
        home = self._anima_file_home_port()
        reserved = set(self._anima_file_efx_parts) if self._anima_file_efx_t else set()
        gs = [p for p in gs_all if p != home]
        if not gs:
            return []
        now = time.monotonic()
        fam_chs: dict = {}

        def _add(c: int) -> None:
            if c == 9 or c in reserved:
                return
            fam = self._anima_efx_family(c)
            if not fam:
                return
            fam_chs.setdefault(fam, [])
            if c not in fam_chs[fam]:
                fam_chs[fam].append(c)
            self._anima_efx_sound_t[fam] = now

        for key in self.active:
            _add(key[0])
        if extra_ch is not None:
            _add(extra_ch)
        # PC already told us the family — pack it now, not at the first note.
        # Current tables (chromatic, fx, wider wind/strings) join this same pass.
        for c in range(16):
            if self._file_used_ch[c]:
                _add(c)
        # While a family is inside HOLD, keep every channel that still
        # classifies as that family — not only when the family is absent.
        for fam, ts in list(self._anima_efx_sound_t.items()):
            if now - ts >= ANIMA_EFX_HOLD_SEC:
                continue
            for c in range(16):
                if not (self._file_used_ch[c] or self._anima_ch_has_notes(c)):
                    continue
                if c in reserved:
                    continue
                if self._anima_efx_family(c) == fam:
                    fam_chs.setdefault(fam, [])
                    if c not in fam_chs[fam]:
                        fam_chs[fam].append(c)
        # Sticky: channels already on a slot stay in that family while PC matches.
        for slot in self._anima_slots:
            fam = slot.get("fam")
            if not fam:
                continue
            for c in slot.get("chs") or []:
                if c in reserved:
                    continue
                if self._anima_efx_family(c) == fam:
                    fam_chs.setdefault(fam, [])
                    if c not in fam_chs[fam]:
                        fam_chs[fam].append(c)
        # Idle may keep a family, but never steal channels that already
        # reclassified (clean → dist) or that a higher family owns.
        used = {c for chs in fam_chs.values() for c in chs}
        for slot in self._anima_slots:
            fam = slot.get("fam")
            if not fam or fam in fam_chs:
                continue
            ts = self._anima_efx_sound_t.get(fam, 0.0)
            if not ts or (now - ts) >= ANIMA_EFX_IDLE_SEC:
                continue
            keep = [
                c for c in (slot.get("chs") or [])
                if c not in reserved and self._anima_efx_family(c) == fam and c not in used
            ]
            if keep:
                fam_chs[fam] = keep
                used.update(keep)

        plan = []
        used_ports = set()
        used_chs = set(reserved)
        for park in list(self._anima_file_park):
            pp = park.get("port")
            if pp is None or pp == home or pp not in gs:
                continue
            pch = [c for c in (park.get("chs") or []) if c not in reserved]
            plan.append({
                "port": pp, "fam": "file_park", "chs": pch,
                "split": False, "typ": park.get("typ"),
            })
            used_ports.add(pp)
            used_chs.update(pch)
        pri = {f: i for i, f in enumerate(ANIMA_EFX_PRIORITY)}

        def _rank(fam: str) -> int:
            return pri.get(fam, 99)

        def _take(for_fam: str):
            # 1) this family already lives here
            for p in gs:
                if p in used_ports:
                    continue
                sl = self._anima_slots[p] if p < len(self._anima_slots) else {}
                if sl.get("fam") == for_fam:
                    used_ports.add(p)
                    return p
            # 2) empty box
            for p in gs:
                if p not in used_ports:
                    sl = self._anima_slots[p] if p < len(self._anima_slots) else {}
                    if not sl.get("fam"):
                        used_ports.add(p)
                        return p
            # 3) steal the lowest-priority occupant, only if that box is
            #    evictable (quiet players, and owner unheard or silent IDLE_SEC)
            steal = None
            steal_rank = -1
            for p in gs:
                if p in used_ports:
                    continue
                sl = self._anima_slots[p] if p < len(self._anima_slots) else {}
                fam = sl.get("fam")
                if not fam or fam == "file_park":
                    continue
                if not self._anima_slot_evictable(p, now):
                    continue
                r = _rank(fam)
                if sl.get("heard_t") and r <= _rank(for_fam):
                    continue
                if r > steal_rank:
                    steal, steal_rank = p, r
            if steal is not None:
                used_ports.add(steal)
                return steal
            return None

        for fam in ANIMA_EFX_PRIORITY:
            chs = [c for c in fam_chs.get(fam, []) if c not in used_chs]
            if not chs:
                continue
            if fam == "guitar_dist":
                rest = list(chs)
                n_other = sum(
                    1 for f in ANIMA_EFX_PRIORITY
                    if f != "guitar_dist" and any(
                        c not in used_chs for c in fam_chs.get(f, [])
                    )
                )
                n_free0 = sum(1 for p in gs if p not in used_ports)
                can_solo = n_free0 >= len(rest) + n_other
                while rest:
                    port = _take(fam)
                    if port is None:
                        break
                    sl = self._anima_slots[port] if port < len(self._anima_slots) else {}
                    old_chs = [
                        c for c in (sl.get("chs") or [])
                        if c in rest
                    ] if sl.get("fam") == fam and sl.get("typ") else []
                    # Already committed on this box — do not restack mid-phrase.
                    if old_chs:
                        take = old_chs[:2] if len(old_chs) >= 2 else old_chs[:1]
                        rest = [c for c in rest if c not in take]
                        plan.append({
                            "port": port, "fam": fam, "chs": take,
                            "split": bool(sl.get("split")),
                        })
                    # Spare boxes: one guitar per unit so each keeps its pan.
                    elif can_solo:
                        one = [rest.pop(0)]
                        plan.append({
                            "port": port, "fam": fam, "chs": one,
                            "split": False,
                        })
                    elif len(rest) >= 2:
                        pair, rest = rest[:2], rest[2:]
                        split = bool(sl.get("split"))
                        if not sl.get("typ") and self._anima_chs_want_split(pair):
                            split = True
                        plan.append({
                            "port": port, "fam": fam, "chs": pair,
                            "split": split,
                        })
                    else:
                        plan.append({
                            "port": port, "fam": fam, "chs": rest[:],
                            "split": False,
                        })
                        rest = []
                    used_chs.update(plan[-1]["chs"])
            else:
                port = _take(fam)
                if port is None:
                    # Lower families may still own their boxes.
                    continue
                sl = self._anima_slots[port] if port < len(self._anima_slots) else {}
                plan.append({
                    "port": port, "fam": fam, "chs": chs,
                    "split": bool(sl.get("split")) if sl.get("fam") == fam else False,
                })
                used_chs.update(chs)
        return plan

    def _anima_ch_has_notes(self, ch: int) -> bool:
        ch = ch & 0x0F
        return any(k[0] == ch for k in self.active)

    def _anima_efx_part_release(self, ch: int) -> None:
        """EFX Off on a part that is no longer sounding. Type stays reserved."""
        ch = ch & 0x0F
        if self._anima_ch_has_notes(ch):
            return
        for port in range(self.n_ports):
            ons = self._anima_efx_on[port] if port < len(self._anima_efx_on) else None
            if not ons or not ons[ch]:
                continue
            self._anima_efx_ours = True
            self._safe_out_send(
                port,
                self._gs_dt1([0x40, self._gs_efx_part_mid(ch), 0x22], [0x00]),
            )
            ons[ch] = False

    def _anima_clear_slot(self, port: int) -> None:
        ports = [port]
        for c in range(16):
            if not self._anima_efx_on[port][c]:
                continue
            off = self._gs_dt1([0x40, self._gs_efx_part_mid(c), 0x22], [0x00])
            self._anima_efx_ours = True
            self._safe_out_send(port, off)
            self._anima_efx_on[port][c] = False
        for c, p in list((self._anima_ch_port or {}).items()):
            if p == port:
                self._anima_ch_port.pop(c, None)
        self._anima_slots[port] = {}

    def _anima_commit_plan(self, plan: list) -> None:
        gs = self._anima_gs_ports()
        home = self._anima_file_home_port()
        reserved = set(self._anima_file_efx_parts) if self._anima_file_efx_t else set()
        keep = {item["port"] for item in plan}
        # Sticky pin: a sounding part stays on the box that already has
        # its insert. Wiping ch_port every note was load-balancing guitars
        # onto dry ports.
        sticky = {
            c: p for c, p in (self._anima_ch_port or {}).items()
            if self._anima_ch_has_notes(c)
        }
        for item in plan:
            stay = []
            move = []
            for c in item["chs"]:
                prev = sticky.get(c)
                if prev is not None and prev != item["port"]:
                    stay.append(c)
                else:
                    move.append(c)
            if stay and not move:
                continue
            if stay:
                item = dict(item)
                item["chs"] = move
            if not item["chs"]:
                continue
            self._anima_commit_slot(item)
            sl = self._anima_slots[item["port"]] if item["port"] < len(self._anima_slots) else {}
            # Busy non-dirt commit leaves the sounding family in place.
            # Pinning the rejected family anyway was the dry-part bug:
            # notes stayed on the box after Part EFX had been turned off.
            if sl.get("fam") != item["fam"] and sl.get("pending_fam") != item["fam"]:
                continue
            for c in item["chs"]:
                if c in reserved and home is not None:
                    self._anima_ch_port[c] = home
                else:
                    self._anima_ch_port[c] = item["port"]
                    sticky[c] = item["port"]
        for c, p in sticky.items():
            sl = self._anima_slots[p] if isinstance(p, int) and 0 <= p < len(self._anima_slots) else {}
            try:
                same = self._anima_efx_family(c) == sl.get("fam")
            except Exception:
                same = False
            if c in (sl.get("chs") or []) or same:
                self._anima_ch_port.setdefault(c, p)
        for p in gs:
            if p == home:
                continue
            if p not in keep and self._anima_slots[p].get("fam"):
                # A heard owner keeps its box; never pull Part EFX out from
                # under a sounding player.
                if not self._anima_slot_evictable(p):
                    continue
                self._anima_clear_slot(p)
        # Secondaries: EFX Off on parts the FILE turned on (home keeps them).
        # Once per port — commit_plan runs on every note and was flooding Offs.
        if home is not None and reserved:
            key = (home, tuple(sorted(reserved)))
            for p in gs:
                if p == home:
                    continue
                if (p, key) in self._anima_file_off_sent:
                    continue
                for c in reserved:
                    self._anima_efx_ours = True
                    self._safe_out_send(
                        p,
                        self._gs_dt1([0x40, self._gs_efx_part_mid(c), 0x22], [0x00]),
                    )
                    self._anima_efx_on[p][c] = False
                self._anima_file_off_sent.add((p, key))
        if plan:
            self._anima_efx_key = plan[0]["fam"]
            self._anima_efx_hero = plan[0]["chs"][0] if plan[0]["chs"] else None
        else:
            self._anima_efx_key = None
            self._anima_efx_hero = None

    def _anima_efx_set_param(self, port: int, typ: tuple, name: str, val: int) -> None:
        params = GS_EFX_PARAMS.get(tuple(typ) if typ else None) or {}
        slot = params.get(name)
        if not slot:
            return
        addr = 0x03 + (int(slot) - 1)
        self._anima_efx_ours = True
        self._safe_out_send(port, self._gs_dt1([0x40, 0x03, addr], [int(val) & 0x7F]))
        self._anima_feedback(
            "efx-param",
            f"P{port + 1} {name} → {int(val) & 0x7F}",
            status=False,
        )

    def _anima_efx_apply_pan(self, port: int, typ: tuple, chs: list) -> None:
        """Inserts with a Pan knob follow the player's file pan (CC10).

        One pan address: the output sits where the player is panned.
        Two (parallel pairs, the two pitch voices): spread around it.
        A centred player keeps the type's own default, except the extra
        dirt box, which still leans L/R by port.
        """
        key = tuple(typ)[:2] if typ else None
        addrs = ANIMA_EFX_PAN_PARAMS.get(key)
        if not addrs or not chs:
            return
        pans = [int(self.pan[c]) if self.pan[c] is not None else 64 for c in chs]
        pan = pans[0]
        why = ""
        if len(pans) >= 2 and min(pans) < 64 - ANIMA_EFX_PAN_OFF and max(pans) > 64 + ANIMA_EFX_PAN_OFF:
            # Opposite-side players sharing one insert (ONESTOP intro guitars):
            # centre it; the OD1/OD2 split latches in a quiet gap.
            pan, why = 64, " (split pending)"
        elif abs(pan - 64) <= 4:
            if key in ANIMA_EFX_PAN_SLOT:
                # Centred part on an extra dirt box: lean L/R by port.
                pan, why = (32 if port % 2 == 0 else 96), " (dirt lean)"
            else:
                pan = 64
        if len(addrs) == 1:
            vals = [pan]
        elif pan == 64 and not why:
            vals = [0x01, 0x7F]  # the pair's own hard L/R default
        else:
            sp = ANIMA_EFX_PAN_PAIR_SPREAD
            vals = [max(1, min(127, pan - sp)), max(1, min(127, pan + sp))]
        self._anima_efx_ours = True
        for addr, v in zip(addrs, vals):
            self._safe_out_send(port, self._gs_dt1([0x40, 0x03, addr], [int(v) & 0x7F]))
        self._anima_feedback(
            "efx-pan",
            f"P{port + 1} EFX pan → {'/'.join(str(v) for v in vals)}{why}",
            status=False,
        )


    def _anima_bass_harm_drive(self, port: int, typ: tuple, chs: list) -> None:
        """F.Bass / Harm. (CC00=16 on finger/pick bass) through Bass Multi: Drive 16 not 48."""
        if tuple(typ)[:2] != (0x04, 0x05):
            return
        hit = False
        for c in chs:
            pc = int(self._anima_prog[c]) & 0x7F
            msb = int(self.bank_msb[c]) & 0x7F
            if msb == 16 and pc in (32, 33, 34):
                hit = True
                break
        if hit:
            self._anima_efx_set_param(port, typ, "OD Drive", 16)

    def _anima_lead_dirt_drive(self, port: int, typ: tuple, chs: list) -> None:
        """Lead + Overdrive/Distortion: default Drive 48 is too hot. Match bass-harm idea."""
        if tuple(typ)[:2] not in ((0x01, 0x10), (0x01, 0x11)):
            return
        if not any((self._anima_efx_family(c) or "") == "lead" for c in chs):
            return
        self._anima_efx_set_param(port, typ, "Drive", 24)

    def _anima_efx_follow_pan(self, ch: int) -> None:
        port = self._anima_ch_port.get(ch)
        if port is None:
            return
        slot = self._anima_slots[port] if port < len(self._anima_slots) else {}
        if ch not in (slot.get("chs") or []):
            return
        self._anima_efx_apply_pan(port, slot.get("typ"), slot.get("chs") or [ch])
        self._anima_efx_guitar_upkeep(ch)

    def _anima_efx_guitar_upkeep(self, ch: int) -> None:
        """Fix a dirt box's stereo placement once it is quiet.

        Two opposite-side guitars merged under a riff → latch OD1/OD2.
        A lone panned guitar left on GTR Multi (CC10 came after the PC)
        → move it to Overdrive/Distortion so it keeps its side.
        Same rules as every other type change: quiet players, one type
        write per box per switch window, no hold/retrigger.
        """
        port = self._anima_ch_port.get(ch & 0x0F)
        if port is None or not (0 <= port < len(self._anima_slots)):
            return
        sl = self._anima_slots[port]
        if sl.get("fam") != "guitar_dist" or not sl.get("typ"):
            return
        chs = list(sl.get("chs") or [])
        if not chs or self._anima_port_players_sounding(port):
            return
        if time.monotonic() - float(sl.get("t") or 0) < ANIMA_EFX_SWITCH_SEC:
            return
        if len(chs) >= 2:
            pair = chs[:2]
            if sl.get("split") or not self._anima_chs_want_split(pair):
                return
            self._anima_commit_slot({"port": port, "fam": "guitar_dist", "chs": pair, "split": True})
            return
        if tuple(sl["typ"])[:2] in ANIMA_EFX_PAN_SLOT:
            return
        c = chs[0]
        pan = int(self.pan[c]) if self.pan[c] is not None else 64
        if abs(pan - 64) <= ANIMA_EFX_PAN_OFF:
            return
        self._anima_commit_slot({
            "port": port, "fam": "guitar_dist", "chs": chs, "split": False, "retype": True,
        })

    def _anima_port_has_notes(self, port: int) -> bool:
        for info in self.active.values():
            ports = info.get("ports") or [info.get("port")]
            if port in ports:
                return True
        return False

    def _anima_efx_wet_mark(self, port: int, ch: int) -> None:
        """Part just went wet / type just changed: keep its next notes off this box briefly."""
        wet = getattr(self, "_anima_efx_wet", None)
        if wet is None:
            wet = self._anima_efx_wet = {}
        wet[(port, ch & 0x0F)] = time.monotonic() + ANIMA_EFX_WET_SEC

    def _anima_efx_wet_blocked(self, port: int, ch: int) -> bool:
        wet = getattr(self, "_anima_efx_wet", None) or {}
        return time.monotonic() < float(wet.get((port, ch & 0x0F), 0.0))

    def _anima_port_players(self, port: int, extra_chs=None) -> set:
        """Channels wired into this box's insert: Part EFX On here, slot owners, newcomers."""
        sl = self._anima_slots[port] if port < len(self._anima_slots) else {}
        ons = self._anima_efx_on[port] if port < len(self._anima_efx_on) else [False] * 16
        players = {c for c in range(16) if ons[c]}
        players.update(sl.get("chs") or [])
        players.update(extra_chs or [])
        return players

    def _anima_port_players_sounding(self, port: int, extra_chs=None) -> bool:
        """Any EFX player of this box sounding on it (notes, ghosts, queued strums).

        Dry parts load-balanced onto the unit do not count: their Part EFX is
        Off, so an insert type change never reaches them.
        """
        players = self._anima_port_players(port, extra_chs)
        if not players:
            return False
        for key, info in self.active.items():
            if key[0] in players and port in (info.get("ports") or [info.get("port")]):
                return True
        for ghosts in (getattr(self, "_anima_ghosts", None) or {}).values():
            for g in ghosts or []:
                if g and g[0] == port and (g[1] & 0x0F) in players:
                    return True
        for _when, p, msg in getattr(self, "_anima_strum_q", None) or []:
            if (
                p == port
                and getattr(msg, "type", "") == "note_on"
                and msg.velocity > 0
                and (msg.channel & 0x0F) in players
            ):
                return True
        return False

    def _anima_slot_evictable(self, port: int, now: float | None = None) -> bool:
        """A box may change owner: empty, or unheard past the dump, or silent IDLE_SEC.

        Once a family has actually played on a box it keeps it while it plays.
        "Unheard" alone was the 0.19.002 ping-pong (lead ↔ pad on every gap).
        """
        now = time.monotonic() if now is None else now
        sl = self._anima_slots[port] if port < len(self._anima_slots) else {}
        fam = sl.get("fam")
        if not fam:
            return True
        if fam == "file_park":
            return False
        if self._anima_port_players_sounding(port):
            return False
        if now - float(sl.get("t") or 0) < ANIMA_EFX_SWITCH_SEC:
            return False
        return self._anima_slot_stale(port, now)

    def _anima_slot_stale(self, port: int, now: float | None = None) -> bool:
        """Owner no longer has a claim a LOWER family must respect.

        Heard owners: silent ANIMA_EFX_IDLE_SEC. Unheard owners: past their
        grace (short for the song-setup dump, longer for a mid-song PC,
        which says that part is about to play).
        """
        now = time.monotonic() if now is None else now
        sl = self._anima_slots[port] if port < len(self._anima_slots) else {}
        fam = sl.get("fam")
        if not fam:
            return True
        if fam == "file_park":
            return False
        heard = float(sl.get("heard_t") or 0)
        if heard:
            return (now - heard) >= ANIMA_EFX_IDLE_SEC
        claimed = float(sl.get("t") or 0)
        grace = float(sl.get("grace") or ANIMA_EFX_DUMP_SEC)
        return (now - claimed) >= grace

    def _anima_unpin_others(self, port: int, fam: str, chs: list, old_chs: list) -> None:
        """Channels this box no longer owns must re-home. Same family stays.

        Unpin and Part EFX Off are one action: pinned-but-Off played dry
        forever (0.19.001).
        """
        victims = set(old_chs or [])
        for c, p in list((self._anima_ch_port or {}).items()):
            if p == port:
                victims.add(c)
        for c in victims:
            if c in chs or self._anima_ch_port.get(c) != port:
                continue
            try:
                if self._anima_efx_family(c) == fam:
                    continue
            except Exception:
                pass
            self._anima_ch_port.pop(c, None)
            if self._anima_efx_on[port][c]:
                self._anima_efx_ours = True
                self._safe_out_send(
                    port,
                    self._gs_dt1([0x40, self._gs_efx_part_mid(c), 0x22], [0x00]),
                )
                self._anima_efx_on[port][c] = False

    def _anima_commit_slot(self, item: dict) -> None:
        port = item["port"]
        fam = item["fam"]
        chs = list(item["chs"])
        split = bool(item.get("split"))
        old = self._anima_slots[port]
        if fam == "file_park" and item.get("typ"):
            typ = tuple(item["typ"])[:2]
            if old.get("typ") != typ:
                self._anima_efx_ours = True
                self._safe_out_send(port, self._gs_dt1([0x40, 0x03, 0x00], [typ[0], typ[1]]))
            self._anima_slots[port] = {
                "fam": "file_park", "chs": chs, "split": False, "typ": typ, "t": time.monotonic(),
            }
            for c in range(16):
                want = c in chs
                if want == self._anima_efx_on[port][c]:
                    continue
                val = 0x01 if want else 0x00
                self._anima_efx_ours = True
                self._safe_out_send(
                    port,
                    self._gs_dt1([0x40, self._gs_efx_part_mid(c), 0x22], [val]),
                )
                self._anima_efx_on[port][c] = want
            self._anima_unpin_others(port, "file_park", chs, list(old.get("chs") or []))
            return
        # Invariant: never change type or owner under a sounding EFX player
        # (dirt, OD1/OD2 and GTR Multi included). Dry parts do not count.
        busy = self._anima_port_players_sounding(port, chs)
        # One type write per box per switch window (the 196 s GTR Multi →
        # OD1/OD2 double write). An empty box is never "recent".
        if old.get("typ") and time.monotonic() - float(old.get("t") or 0) < ANIMA_EFX_SWITCH_SEC:
            busy = True
        # Same family + type already on this box: keep it. Channel list
        # may grow/shrink; that must not re-roll GTR Multi 1↔3.
        # Split may still latch ON below, but only on a quiet box.
        if (
            old.get("fam") == fam
            and old.get("typ")
            and (not (split and not old.get("split")) or busy)
            and not (item.get("retype") and not busy)
        ):
            before = set(old.get("chs") or [])   # old IS the live slot dict
            self._anima_slots[port]["chs"] = list(set(chs) | before)
            self._anima_slots[port]["split"] = bool(old.get("split"))
            for c in chs:
                if self._anima_efx_on[port][c]:
                    continue
                self._anima_efx_ours = True
                self._safe_out_send(
                    port,
                    self._gs_dt1([0x40, self._gs_efx_part_mid(c), 0x22], [0x01]),
                )
                self._anima_efx_on[port][c] = True
                self._anima_efx_wet_mark(port, c)
            merged = list(self._anima_slots[port].get("chs") or [])
            self._anima_unpin_others(port, fam, merged, list(old.get("chs") or []))
            if set(merged) != before:
                self._anima_efx_apply_pan(port, old.get("typ"), merged)
            return
        # Same family, type already sent — do not flap GTR Multi ↔ OD1/OD2
        # inside the switch window unless we are latching split ON.
        last_t = old.get("t") or 0.0
        if (
            old.get("fam") == fam
            and old.get("typ")
            and (now := time.monotonic()) - last_t < ANIMA_EFX_SWITCH_SEC
            and not (split and not old.get("split"))
        ):
            self._anima_slots[port]["chs"] = chs
            return
        if old.get("split") and fam == "guitar_dist":
            split = True
        if split:
            already = (
                old.get("split")
                and old.get("typ") == (ANIMA_SPLIT_MSB, ANIMA_SPLIT_LSB)
            )
            if not already:
                if busy:
                    # No hold/retrigger under a riff (ONESTOP hitch).
                    return
                self._anima_apply_od_split(chs, ports=[port])
            self._anima_slots[port] = {
                "fam": fam, "chs": chs, "split": True,
                "typ": (ANIMA_SPLIT_MSB, ANIMA_SPLIT_LSB), "t": time.monotonic(),
                "heard_t": float(old.get("heard_t") or 0) if old.get("fam") == fam else 0.0,
                "grace": float(getattr(self, "_anima_efx_grace", ANIMA_EFX_DUMP_SEC)),
            }
            for c in range(16):
                want = c in chs
                if want == self._anima_efx_on[port][c]:
                    continue
                val = 0x01 if want else 0x00
                self._anima_efx_ours = True
                self._safe_out_send(
                    port,
                    self._gs_dt1([0x40, self._gs_efx_part_mid(c), 0x22], [val]),
                )
                self._anima_efx_on[port][c] = want
                if want:
                    self._anima_efx_wet_mark(port, c)
            self._anima_unpin_others(port, fam, chs, list(old.get("chs") or []))
            return
        pick = self._anima_palette_pick(fam, port, chs)
        if not pick:
            return
        msb, lsb, label = pick
        typ = (msb, lsb)
        if typ == (ANIMA_SPLIT_MSB, ANIMA_SPLIT_LSB) and fam == "guitar_dist":
            if len(chs) < 2:
                pal = [
                    row for row in (ANIMA_EFX_GS.get(fam) or [])
                    if (row[0], row[1]) != (ANIMA_SPLIT_MSB, ANIMA_SPLIT_LSB)
                ]
                if not pal:
                    return
                pick = tuple(pal[0][:3])
                msb, lsb, label = pick
                typ = (msb, lsb)
            else:
                item["split"] = True
                return self._anima_commit_slot(item)
        if busy and (old.get("typ") != typ or (old.get("fam") and old.get("fam") != fam)):
            # A player is sounding: leave type, owner and part toggles alone.
            # The new family stays unpinned (dry) and retries when this box
            # or another one is quiet. No defer, no flush, no hold/retrigger.
            return
        if old.get("typ") != typ:
            self._anima_efx_ours = True
            self._safe_out_send(port, self._gs_dt1([0x40, 0x03, 0x00], [msb, lsb]))
            self._anima_efx_sent = typ
            for c in chs:
                self._anima_efx_wet_mark(port, c)
            self._anima_efx_label = label
            self._anima_efx_hero = chs[0] if chs else None
            self._anima_efx_bind_and_seed(msb, lsb, ports=[port])
            self._anima_efx_shape(port, typ, chs, fam)
            self._anima_efx_apply_pan(port, typ, chs)
            self._anima_organ_vol_lift(port, chs, label)
            self._anima_bass_harm_drive(port, typ, chs)
            self._anima_lead_dirt_drive(port, typ, chs)
            self._anima_feedback("efx", f"P{port + 1} ch{',' .join(str(c+1) for c in chs)} {fam} → GS {label}", status=True)
        elif old.get("fam") != fam:
            self._anima_feedback("efx", f"P{port + 1} ch{',' .join(str(c+1) for c in chs)} {fam} keeps GS {label}", status=True)
        # Type and part toggles change together; only this box's owners are On.
        for c in range(16):
            want = c in chs and not self._anima_is_rhythm(c)
            if want == self._anima_efx_on[port][c]:
                continue
            val = 0x01 if want else 0x00
            self._anima_efx_ours = True
            self._safe_out_send(
                port,
                self._gs_dt1([0x40, self._gs_efx_part_mid(c), 0x22], [val]),
            )
            self._anima_efx_on[port][c] = want
            if want:
                self._anima_efx_wet_mark(port, c)
        self._anima_unpin_others(port, fam, chs, list(old.get("chs") or []))
        if old.get("split") and not split:
            self._anima_split_restore()
        self._anima_slots[port] = {
            "fam": fam, "chs": chs, "split": False, "typ": typ, "t": time.monotonic(),
            "heard_t": float(old.get("heard_t") or 0) if old.get("fam") == fam else 0.0,
            "grace": float(getattr(self, "_anima_efx_grace", ANIMA_EFX_DUMP_SEC)),
        }

    def _anima_efx_flush_pending(self, ch: int) -> None:
        """Legacy deferred-type flush. The 0.19 planner never sets ``pending``
        (a busy unit is simply left alone), so this is a no-op guard kept for
        slots restored from older state."""
        if any(k[0] == ch for k in self.active):
            return
        now = time.monotonic()
        for port, slot in enumerate(self._anima_slots):
            pend = slot.get("pending")
            if not pend or ch not in (slot.get("chs") or []):
                continue
            if any(
                port in info.get("ports", [info["port"]])
                for info in self.active.values()
            ):
                # Stale defer: drop rather than apply minutes later onto a new family.
                age = now - float(slot.get("t") or now)
                if age > 8.0:
                    slot["pending"] = None
                    slot.pop("pending_fam", None)
                    self._anima_feedback(
                        "efx",
                        f"P{port + 1} drop stale defer {pend[2] if len(pend) > 2 else pend}",
                        status=False,
                    )
                continue
            msb, lsb, label = pend
            want_fam = slot.get("pending_fam") or slot.get("fam")
            live_fams = {
                self._anima_efx_family(c)
                for c in (slot.get("chs") or [])
                if not self._anima_is_rhythm(c)
            }
            live_fams.discard(None)
            if want_fam and live_fams and want_fam not in live_fams:
                slot["pending"] = None
                slot.pop("pending_fam", None)
                self._anima_feedback(
                    "efx",
                    f"P{port + 1} drop defer {label} (now {','.join(sorted(live_fams))})",
                    status=False,
                )
                continue
            self._anima_efx_ours = True
            self._safe_out_send(port, self._gs_dt1([0x40, 0x03, 0x00], [msb, lsb]))
            slot["typ"] = (msb, lsb)
            slot["pending"] = None
            slot.pop("pending_fam", None)
            slot["t"] = now
            self._anima_efx_sent = (msb, lsb)
            self._anima_efx_label = label
            self._anima_efx_bind_and_seed(msb, lsb, ports=[port])
            self._anima_efx_shape(port, (msb, lsb), slot.get("chs") or [ch], slot.get("fam"))
            self._anima_efx_apply_pan(port, (msb, lsb), slot.get("chs") or [ch])
            self._anima_organ_vol_lift(port, slot.get("chs") or [ch], label)
            self._anima_bass_harm_drive(port, (msb, lsb), slot.get("chs") or [ch])
            self._anima_lead_dirt_drive(port, (msb, lsb), slot.get("chs") or [ch])
            chs_now = list(slot.get("chs") or [])
            dirt_commit = (
                (msb, lsb) in ANIMA_FILE_DIRT_TYPES
                or str(slot.get("fam") or "").startswith("guitar_dist")
            )
            for c in range(16):
                want = c in chs_now
                if self._anima_is_rhythm(c):
                    want = False
                elif not want and any(
                    k[0] == c and port in info.get("ports", [info["port"]])
                    for k, info in self.active.items()
                ):
                    cfam = self._anima_efx_family(c) or ""
                    if dirt_commit:
                        want = cfam.startswith("guitar_dist") or cfam in ANIMA_FILE_DIRT_FAMS
                    else:
                        want = True
                if want == self._anima_efx_on[port][c]:
                    continue
                val = 0x01 if want else 0x00
                self._anima_efx_ours = True
                self._safe_out_send(
                    port,
                    self._gs_dt1([0x40, self._gs_efx_part_mid(c), 0x22], [val]),
                )
                self._anima_efx_on[port][c] = want
            self._anima_unpin_others(port, slot.get("fam") or "", chs_now, chs_now)
            self._anima_feedback(
                "efx",
                f"P{port + 1} apply deferred GS {label}",
                status=True,
            )

    def _anima_ghost_poly_ok(self, port: int) -> bool:
        if port < 0 or port >= self.n_ports:
            return False
        lim = self.poly_limits[port] or 1
        return self.voice_counts[port] < int(lim * ANIMA_GHOST_POLY_FRAC)

    def _anima_ghost_fam(self, ch: int):
        """bass / organ family key for one-sub-per-family, else None."""
        ch = ch & 0x0F
        fam = self._anima_efx_family(ch) or ""
        cat = self._anima_category(ch)
        if fam.startswith("bass") or cat == "bass":
            return "bass"
        if fam.startswith("organ") or cat == "organ":
            return "organ"
        return None

    def _anima_family_lowest(self, fam: str, extra=None):
        """Lowest sounding pitch in a family. extra = (ch, note) not yet in active."""
        cands = []
        if extra is not None:
            cands.append((int(extra[1]) & 0x7F, int(extra[0]) & 0x0F))
        for (c, n) in self.active:
            if self._anima_ghost_fam(c) == fam:
                cands.append((int(n) & 0x7F, int(c) & 0x0F))
        if not cands:
            return None
        n, c = min(cands)
        return (c, n)

    def _anima_bass_hero_hard(self, ch: int) -> bool:
        pc = int(self._anima_prog[ch & 0x0F]) & 0x7F
        return pc in ANIMA_BASS_HARD_PC

    def _anima_bass_slot_is_multi(self, port: int) -> bool:
        slot = self._anima_slots[port] if port < len(self._anima_slots) else None
        if not slot:
            return False
        lab = str(slot.get("label") or "").lower()
        if "bass multi" in lab:
            return True
        typ = slot.get("typ")
        if typ and tuple(typ)[:2] in ((0x01, 0x10), (0x01, 0x11)):
            return True
        return False

    def _anima_bass_sub_wanted(self, ch: int, hero: int) -> bool:
        """Thin-mix only. Skip if the arrangement already has bottom."""
        if self._anima_bass_slot_is_multi(hero):
            return False
        others = 0
        for (c, _n) in self.active:
            if c != ch and self._anima_ghost_fam(c) == "bass":
                others += 1
        if others:
            return False
        return True

    def _anima_pick_bass_sub(self, port: int, ch: int = 0):
        """Seed-stable named bass-sub slot that this port can actually play."""
        hard_hero = self._anima_bass_hero_hard(ch)
        cached = getattr(self, "_anima_bass_sub_choice", None)
        if cached:
            name = cached[3] if len(cached) > 3 else ""
            hard_names = {s[3] for s in ANIMA_BASS_SUB_HARD}
            if not (hard_hero and name in hard_names):
                adapted = self._anima_adapt_tone_slot(port, cached[:3])
                if adapted:
                    return adapted + (cached[3],)
        seed = int(self._anima_ensure_efx_seed()) & 0xFFFF
        if getattr(self, "anima_game", False) or getattr(self, "_anima_game", False):
            seed = (seed + int(self._anima_scene_salt() or 0)) & 0xFFFF
        if hard_hero:
            slots = list(ANIMA_BASS_SUB_SOFT)
        else:
            slots = list(ANIMA_BASS_SUB_SOFT) + list(ANIMA_BASS_SUB_HARD)
        if slots:
            rot = seed % len(slots)
            slots = slots[rot:] + slots[:rot]
        for cc0, _cc32, pc, name in slots:
            adapted = None
            for maplsb in (4, 3, 2, 0):
                cand = self._anima_adapt_tone_slot(port, (cc0, maplsb, pc))
                if not cand:
                    continue
                if cand[0] == 0 and cc0 != 0:
                    continue
                adapted = cand
                break
            if not adapted:
                continue
            self._anima_bass_sub_choice = (adapted[0], adapted[1], adapted[2], name)
            return adapted + (name,)
        # Last resort: capital SynBass 1
        self._anima_bass_sub_choice = (0, 0, 38, "Synth Bass 1")
        return (0, 0, 38, "Synth Bass 1")

    def _anima_ghost_kill(self, key) -> None:
        """Note-off every ghost tied to a hero (ch, note)."""
        ghosts = (self._anima_ghosts or {}).pop(key, None)
        fams = getattr(self, "_anima_fam_ghost", None) or {}
        for fam, owner in list(fams.items()):
            if owner == key:
                fams.pop(fam, None)
        snd = getattr(self, "_anima_ghost_sound", None)
        if snd is None:
            self._anima_ghost_sound = {}
            snd = self._anima_ghost_sound
        if not ghosts:
            return
        for item in ghosts:
            port, ch, note = item[0], item[1], item[2]
            w = item[3] if len(item) > 3 else self._tone_voices(ch, port)
            if snd.get((ch, note)) == key:
                snd.pop((ch, note), None)
            try:
                self._send_routed(
                    port,
                    mido.Message("note_off", channel=ch, note=note, velocity=0),
                )
            except Exception:
                pass
            if 0 <= port < self.n_ports:
                self.voice_counts[port] = max(0, self.voice_counts[port] - int(w or 1))

    def _anima_ghost_release_pitch(self, ch: int, note: int) -> None:
        """If Anima is ghosting this pitch on this channel, drop that ghost.

        Stops the file+ghost stack where the file later releases nX on port A
        while the harmony ghost of nX is still hanging on port B.
        """
        ch, note = ch & 0x0F, int(note) & 0x7F
        snd = getattr(self, "_anima_ghost_sound", None) or {}
        hero = snd.get((ch, note))
        if hero:
            self._anima_ghost_kill(hero)

    def _anima_ghost_kill_all(self) -> None:
        for key in list((self._anima_ghosts or {}).keys()):
            self._anima_ghost_kill(key)

    def _anima_ghost_log(self, detail: str) -> None:
        now = time.monotonic()
        if now - getattr(self, "_anima_ghost_log_t", 0) < ANIMA_GHOST_LOG_SEC:
            self._log_line(f"ANIMA ghost: {detail}")
            return
        self._anima_ghost_log_t = now
        self._anima_feedback("ghost", detail, status=True)

    def _anima_ghost_efx_on(self, port: int, ch: int) -> None:
        """Same-part EFX On on the unison port if the hero already uses an insert."""
        if port < 0 or port >= self.n_ports:
            return
        ch = ch & 0x0F
        hero_has = (
            self._anima_ch_port.get(ch) is not None
            or ch in (self._anima_file_efx_parts or set())
        )
        if not hero_has:
            return
        if self._gs_canvas_class(self.out_formats[port]) not in ("88pro", "8850"):
            return
        try:
            mid = self._gs_efx_part_mid(ch)
            self._send(port, self._gs_dt1([0x40, mid, 0x22], [0x01]))
            # Track it so the next type change on this box turns it Off.
            if port < len(self._anima_efx_on):
                self._anima_efx_on[port][ch] = True
        except Exception:
            pass

    def _anima_family_rehome(self) -> None:
        """If a family lost its sub owner, give the sub to the new lowest pitch."""
        if getattr(self, "_anima_rehome_guard", False):
            return
        self._anima_rehome_guard = True
        try:
            for fam in ("bass", "organ"):
                if fam in (getattr(self, "_anima_fam_ghost", None) or {}):
                    continue
                lowest = self._anima_family_lowest(fam)
                if not lowest:
                    continue
                c, n = lowest
                info = self.active.get((c, n))
                if not info:
                    continue
                ports = info.get("ports") or [info["port"]]
                vel = int(info.get("velocity") or 80)
                msg = mido.Message("note_on", channel=c, note=n, velocity=vel)
                self._anima_ghost_maybe(msg, ports)
        finally:
            self._anima_rehome_guard = False

    def _anima_chord_guess(self, extra=None):
        """Held pitch-classes → (root, name, tone_pcs) or None.

        extra = (ch, note) not yet in self.active. Passing tones younger
        than ANIMA_HARM_HOLD are ignored so we do not chase melody debris.
        """
        now = time.monotonic()
        pcs = set()
        if extra is not None:
            pcs.add(int(extra[1]) & 0x7F)
        for (c, n), info in list(self.active.items()):
            if self._anima_is_rhythm(c):
                continue
            cat = self._anima_category(c)
            if cat in ("sfx",):
                continue
            t0 = float(info.get("time") or 0)
            if t0 and (now - t0) < ANIMA_HARM_HOLD:
                continue
            pcs.add(int(n) & 0x7F)
        classes = {p % 12 for p in pcs}
        if len(classes) < 2:
            return None
        best = None
        for root in range(12):
            rel = frozenset((p - root) % 12 for p in classes)
            for iv, name in ANIMA_HARM_TEMPLATES:
                siv = frozenset(iv)
                if siv <= rel:
                    score = len(siv) * 10 + (0 if name == "pow" else 3)
                    cand = (score, root, name, siv)
                    if best is None or cand[0] > best[0]:
                        best = cand
                elif name != "pow" and rel <= siv and len(rel) >= 2:
                    score = len(rel) * 3
                    cand = (score, root, name, siv)
                    if best is None or cand[0] > best[0]:
                        best = cand
        if not best:
            return None
        _, root, name, siv = best
        tones = frozenset((root + i) % 12 for i in siv)
        return root, name, tones

    def _anima_harm_interval(self, note: int, chord) -> int | None:
        """Chord-tone interval above `note`, or +12 when we have no chord."""
        note = int(note) & 0x7F
        if chord is None:
            return 12 if note + 12 <= 127 else None
        _root, name, tones = chord
        if name == "pow":
            for iv in (12, 7):
                if note + iv <= 127:
                    return iv
            return None
        if name in ("maj", "maj7", "7", "aug"):
            prefer = (4, 11, 10, 7, 12)
        elif name in ("min", "m7", "mMaj7", "dim", "dim7", "m7b5"):
            prefer = (3, 10, 6, 7, 12)
        elif name.startswith("sus"):
            prefer = (5, 7, 12)
        else:
            prefer = (7, 12)
        seed = int(self._anima_ensure_efx_seed()) & 0xFFFF
        # Rotate preference slightly so a locked seed is repeatable but not identical.
        rot = seed % max(1, len(prefer) - 1)
        ordered = prefer[rot:] + prefer[:rot]
        for iv in ordered:
            cand = note + iv
            if cand > 127 or cand == note:
                continue
            if (cand % 12) not in tones:
                continue
            if (note % 12) == (cand % 12) and iv != 12:
                continue
            return iv
        return 12 if note + 12 <= 127 else None

    def _anima_harm_is_melody(self, ch: int, note: int) -> bool:
        """Only harmonize the current highest held tone in harmony families."""
        best = (int(note) & 0x7F, -(int(ch) & 0x0F))
        for (c, n) in self.active:
            if self._anima_is_rhythm(c):
                continue
            if self._anima_category(c) not in ANIMA_HARM_CATS:
                continue
            cand = (int(n) & 0x7F, -(int(c) & 0x0F))
            if cand > best:
                return False
        return True

    def _anima_ghost_maybe(self, msg: mido.Message, hero_ports: list) -> None:
        """Bass/organ −12, chord-tone harmony, or dist unison on a spare GS port."""
        if not self.anima or not hero_ports:
            return
        if self.scpop_mode or getattr(self, "voodoo_active", False):
            return
        if getattr(self, "voodoo_loading", False):
            return
        ch = msg.channel & 0x0F
        if self._anima_is_rhythm(ch):
            return
        note = int(msg.note) & 0x7F
        vel = int(msg.velocity) & 0x7F
        if vel <= 0:
            return
        key = (ch, note)
        gfam = self._anima_ghost_fam(ch)
        # Retrigger of a pitch we already ghosted: keep the sounding layer.
        # Killing/recreating every 16th was the "rolling" click.
        if key in (self._anima_ghosts or {}):
            if gfam:
                if getattr(self, "_anima_fam_ghost", None) is None:
                    self._anima_fam_ghost = {}
                self._anima_fam_ghost[gfam] = key
            return
        hero = hero_ports[0]
        fam = self._anima_efx_family(ch)
        cat = self._anima_category(ch)
        ghosts = []

        is_bass = gfam == "bass"
        is_organ = gfam == "organ"
        sl = (self._anima_slots[hero] if hero < len(self._anima_slots) else {}) or {}
        want_sub = is_bass or is_organ
        if want_sub and self._anima_should_strum(ch):
            want_sub = False
        # One sub-octave per family. Do not hop to another channel
        # that is only tied for lowest pitch (ch3 n64 vs ch6 n64).
        if want_sub and gfam:
            owner = (getattr(self, "_anima_fam_ghost", None) or {}).get(gfam)
            if owner:
                _och, onote = owner
                if note > onote:
                    want_sub = False
                elif note == onote and owner != key:
                    if owner in (self._anima_ghosts or {}) or owner in self.active:
                        want_sub = False
                    else:
                        self._anima_ghost_kill(owner)
                elif note < onote:
                    self._anima_ghost_kill(owner)
            elif self._anima_family_lowest(gfam, extra=(ch, note)) != key:
                want_sub = False
        if want_sub and note >= ANIMA_GHOST_MIN_NOTE:
            sub = note - 12
            if sub >= 12 and (ch, sub) not in self.active:
                dest = None
                if is_bass:
                    # Dedicated variation on a spare box so Bass Multi stays clean.
                    # Never a unit the file's bass plays on: the sub reprograms
                    # this channel there (22:07 test: first sub hit the bass's
                    # pinned P1 while a 150 ms reroute sent that note to P2,
                    # and every later bass note played as Mild Bass).
                    avoid = set(hero_ports)
                    for q in (self._anima_ch_port.get(ch), self._anima_note_port.get(ch)):
                        if q is not None:
                            avoid.add(q)
                    for p in self._anima_gs_ports():
                        if p in avoid:
                            continue
                        if self._anima_ghost_poly_ok(p):
                            dest = p
                            break
                elif self._anima_ghost_poly_ok(hero):
                    dest = hero
                if dest is not None and is_bass and not self._anima_bass_sub_wanted(ch, hero):
                    dest = None
                if dest is not None:
                    try:
                        if is_bass:
                            slot = self._anima_pick_bass_sub(dest, ch)
                            cc0, cc32, pc, name = slot
                            saved = getattr(self, "_anima_wave_sub_saved", None)
                            if saved is None:
                                saved = self._anima_wave_sub_saved = {}
                            if (dest, ch) not in saved:
                                tone = getattr(self, "_tone_port", None)
                                if tone and dest < len(tone):
                                    saved[(dest, ch)] = list(tone[dest][ch])
                            self._safe_out_send(dest, mido.Message("control_change", channel=ch, control=32, value=int(cc32) & 0x7F))
                            self._safe_out_send(dest, mido.Message("control_change", channel=ch, control=0, value=int(cc0) & 0x7F))
                            self._safe_out_send(dest, mido.Message("program_change", channel=ch, program=int(pc) & 0x7F))
                            src_vol = self.vol[ch]
                            if src_vol is None:
                                src_vol = 100
                            cc7 = max(1, min(127, int(src_vol * ANIMA_WAVE_SUB_VOL)))
                            self._safe_out_send(dest, mido.Message("control_change", channel=ch, control=7, value=cc7))
                            armed = getattr(self, "_anima_wave_sub_armed", None)
                            if armed is None:
                                self._anima_wave_sub_armed = set()
                                armed = self._anima_wave_sub_armed
                            armed.add((dest, ch))
                            gvel = max(1, min(127, int(vel * ANIMA_WAVE_SUB_VEL)))
                            kind = name
                            w = 1
                        else:
                            # Organ: same part / same tone as the hero.
                            gvel = max(1, min(127, int(vel * ANIMA_GHOST_SUB_VEL)))
                            kind = "organ"
                            pc = None
                            name = None
                            w = self._tone_voices(ch, dest)
                        self._send_routed(
                            dest,
                            mido.Message("note_on", channel=ch, note=sub, velocity=gvel),
                        )
                        self.voice_counts[dest] += w
                        ghosts.append((dest, ch, sub, w))
                        up = None
                        # Organ +12 on the same tone when there is headroom.
                        if is_organ:
                            cand = note + 12
                            if (
                                cand <= 127
                                and (ch, cand) not in self.active
                                and self._anima_ghost_poly_ok(dest)
                            ):
                                self._send_routed(
                                    dest,
                                    mido.Message("note_on", channel=ch, note=cand, velocity=gvel),
                                )
                                self.voice_counts[dest] += w
                                ghosts.append((dest, ch, cand, w))
                                up = cand
                        if up is not None:
                            self._anima_ghost_log(
                                f"organ ±12 ch{ch + 1} n{note}→{sub}/{up} P{dest + 1}"
                            )
                        else:
                            self._anima_ghost_log(
                                f"{kind} −12 ch{ch + 1} n{note}→{sub} P{dest + 1}"
                            )
                    except Exception:
                        pass

        # Chord-tone harmony (one voice per harmony family).
        want_harm = (
            not ghosts
            and cat in ANIMA_HARM_CATS
            and not is_bass
            and not is_organ
            and not self._anima_should_strum(ch)
        )
        if want_harm and not self._anima_harm_is_melody(ch, note):
            want_harm = False
        hfam = f"harm-{cat}" if want_harm else None
        if want_harm and hfam:
            owner = (getattr(self, "_anima_fam_ghost", None) or {}).get(hfam)
            if owner and owner != key:
                if owner in (self._anima_ghosts or {}) or owner in self.active:
                    och, onote = owner
                    if note < onote:
                        want_harm = False
                    else:
                        self._anima_ghost_kill(owner)
                else:
                    pass
        if want_harm:
            chord = self._anima_chord_guess(extra=(ch, note))
            iv = self._anima_harm_interval(note, chord)
            dest = hero if self._anima_ghost_poly_ok(hero) else None
            if dest is None:
                for p in self._anima_gs_ports():
                    if p != hero and self._anima_ghost_poly_ok(p):
                        dest = p
                        break
            if dest is not None and iv and note + iv > ANIMA_HARM_TOP:
                iv = 0   # ONESTOP end: n92→104 string ghosts stacked shrill
            if dest is not None and iv:
                hnote = note + iv
                occupied = (
                    (ch, hnote) in self.active
                    or (ch, hnote) in (getattr(self, "_anima_ghost_sound", None) or {})
                )
                if not occupied and hnote != note:
                    gvel = max(1, min(127, int(vel * ANIMA_HARM_VEL)))
                    try:
                        self._send_routed(
                            dest,
                            mido.Message("note_on", channel=ch, note=hnote, velocity=gvel),
                        )
                        w = self._tone_voices(ch, dest)
                        self.voice_counts[dest] += w
                        ghosts.append((dest, ch, hnote, w))
                        label = chord[1] if chord else "oct"
                        self._anima_ghost_log(
                            f"harm {label} +{iv} ch{ch + 1} n{note}→{hnote} P{dest + 1}"
                        )
                        gfam = hfam
                    except Exception:
                        pass

        if not ghosts and fam == "guitar_dist" and not self._anima_should_strum(ch):
            def _uni_dest_ok(p: int) -> bool:
                if not self._anima_ghost_poly_ok(p):
                    return False
                sl = (self._anima_slots[p] if p < len(self._anima_slots) else {}) or {}
                fam_p = sl.get("fam")
                if fam_p and fam_p not in ("guitar_dist", "file_park"):
                    return False
                for k, info in self.active.items():
                    if k == (ch, note) and p in info.get("ports", [info["port"]]):
                        return False
                return True
            gs = [p for p in self._anima_gs_ports() if p not in hero_ports]
            dest = next((p for p in gs if _uni_dest_ok(p)), None)
            if dest is not None:
                gvel = max(1, min(127, int(vel * ANIMA_GHOST_UNI_VEL)))
                try:
                    self._anima_ghost_efx_on(dest, ch)
                    self._send_routed(
                        dest,
                        mido.Message("note_on", channel=ch, note=note, velocity=gvel),
                    )
                    w = self._tone_voices(ch, dest)
                    self.voice_counts[dest] += w
                    ghosts.append((dest, ch, note, w))
                    self._anima_ghost_log(
                        f"dist unison ch{ch + 1} n{note} P{hero + 1}→P{dest + 1}"
                    )
                except Exception:
                    pass

        if ghosts:
            if key in (self._anima_ghosts or {}):
                self._anima_ghost_kill(key)
            self._anima_ghosts[key] = ghosts
            snd = getattr(self, "_anima_ghost_sound", None)
            if snd is None:
                self._anima_ghost_sound = {}
                snd = self._anima_ghost_sound
            for item in ghosts:
                snd[(item[1], item[2])] = key
            if gfam:
                if getattr(self, "_anima_fam_ghost", None) is None:
                    self._anima_fam_ghost = {}
                self._anima_fam_ghost[gfam] = key

    def _anima_foley_spec(self, ch: int):

        fam = self._anima_efx_family(ch)
        if fam in ANIMA_FOLEY_SPEC:
            return ANIMA_FOLEY_SPEC[fam]
        cat = self._anima_category(ch)
        alias = ANIMA_FOLEY_CAT.get(cat)
        if alias:
            return ANIMA_FOLEY_SPEC.get(alias)
        return None

    def _anima_foley_restore_ch(self, port: int, fch: int) -> None:
        """Put a borrowed part back on a safe capital so SFX does not linger."""
        if port < 0 or port >= self.n_ports or fch is None:
            return
        self._safe_out_send(port, mido.Message("control_change", channel=fch, control=32, value=4))
        self._safe_out_send(port, mido.Message("control_change", channel=fch, control=0, value=0))
        self._safe_out_send(port, mido.Message("program_change", channel=fch, program=0))
        self._safe_out_send(
            port, self._gs_dt1([0x40, self._gs_efx_part_mid(fch), 0x22], [0x00])
        )
        try:
            self._anima_efx_on[port][fch] = False
        except Exception:
            pass

    def _anima_foley_reclaim(self, reason: str = "") -> None:
        """Drop the reserved noise channel so a later song can use it."""
        if not any(c is not None for c in self._anima_foley_ch):
            return
        for i, fch in enumerate(self._anima_foley_ch):
            if fch is not None:
                self._anima_foley_restore_ch(i, fch)
        self._anima_foley_ch = [None] * self.n_ports
        self._anima_foley_armed = [False] * self.n_ports
        self._anima_foley_patch = None
        if reason:
            self._anima_feedback("foley", f"foley channel released ({reason})", status=False)

    def _anima_foley_pick_ch(self, avoid: int) -> int | None:
        """Quiet high channel. Prefer ones the file never programmed."""
        def _ok(c: int, allow_used: bool) -> bool:
            if c == avoid or c == 9 or self._anima_is_rhythm(c):
                return False
            if any(k[0] == c for k in self.active):
                return False
            if not allow_used and self._file_used_ch[c]:
                return False
            if any(c in (s.get("chs") or []) for s in self._anima_slots):
                return False
            return True
        for c in range(15, -1, -1):
            if _ok(c, False):
                return c
        # Do not steal a channel the file already programmed.
        # ONESTOP uses ch15 as flute; stealing it for SFX 122 was the
        # "foley goes nuts" collision (longform and song loops alike).
        return None

    def _anima_foley_dest(self, hero: int, eligible: list[int]) -> int | None:
        """Stay on the guitar's port unless that synth is at its poly ceiling."""
        if hero is None:
            return None
        if self.voice_counts[hero] < self.poly_limits[hero]:
            return hero
        pool = eligible or list(range(self.n_ports))
        for p in pool:
            if p == hero:
                continue
            if self.voice_counts[p] < self.poly_limits[p]:
                return p
        return None

    def _anima_foley_place(self, hero: int, eligible: list[int], avoid: int):
        """Hero GS port first, then other GS outs. None = skip foley this hit."""
        order = []
        if hero is not None and self._anima_port_8850(hero):
            order.append(hero)
        for p in (eligible or []):
            if p not in order and self._anima_port_8850(p):
                order.append(p)
        for p in self._anima_gs_ports():
            if p not in order:
                order.append(p)
        for p in order:
            if self.voice_counts[p] >= self.poly_limits[p]:
                continue
            fch = self._anima_foley_arm(p, avoid)
            if fch is not None:
                return p, fch
        return None, None

    def _anima_foley_arm(self, port: int, ch: int) -> int | None:
        fch = self._anima_foley_ch[port]
        if fch is None:
            fch = self._anima_foley_pick_ch(ch)
            if fch is None:
                return None
            self._anima_foley_ch[port] = fch
        return fch

    def _anima_foley_follow_efx(self, port: int, hero_ch: int, fch: int) -> None:
        """Same insert as the hero part — foley would be on the same mic."""
        if port < 0 or port >= self.n_ports:
            return
        on = False
        try:
            on = bool(self._anima_efx_on[port][hero_ch])
        except Exception:
            on = False
        slot = (self._anima_slots[port] if port < len(self._anima_slots) else None) or {}
        if hero_ch in (slot.get("chs") or []):
            on = True
        if not on or fch == hero_ch:
            return False
        already = False
        try:
            already = bool(self._anima_efx_on[port][fch])
        except Exception:
            already = False
        if not already:
            self._anima_efx_ours = True
            self._safe_out_send(
                port, self._gs_dt1([0x40, self._gs_efx_part_mid(fch), 0x22], [0x01])
            )
            try:
                self._anima_efx_on[port][fch] = True
            except Exception:
                pass
            self._anima_feedback(
                "foley",
                f"foley EFX on P{port + 1} ch{fch + 1} (follow ch{hero_ch + 1})",
                status=False,
            )
        return True

    def _anima_foley_program(self, port: int, fch: int, pc: int, lsb: int) -> None:
        key = (pc, lsb)
        last = getattr(self, "_anima_foley_patch", None)
        if last == (port, fch, key) and self._anima_foley_armed[port]:
            return
        # SFX on 8850 map: map first, then variation, then PC 121/122.
        var = lsb & 0x7F
        self._safe_out_send(port, mido.Message("control_change", channel=fch, control=32, value=4))
        self._safe_out_send(port, mido.Message("control_change", channel=fch, control=0, value=var))
        self._safe_out_send(port, mido.Message("program_change", channel=fch, program=pc & 0x7F))
        self._safe_out_send(port, mido.Message("control_change", channel=fch, control=7, value=ANIMA_FOLEY_CC7))
        self._safe_out_send(port, mido.Message("control_change", channel=fch, control=11, value=127))
        self._safe_out_send(port, mido.Message("control_change", channel=fch, control=10, value=64))
        self._safe_out_send(port, mido.Message("control_change", channel=fch, control=91, value=ANIMA_FOLEY_CC91))
        self._anima_foley_armed[port] = True
        self._anima_foley_patch = (port, fch, key)

    def _anima_maybe_foley(self, ch: int, note: int, vel: int, hero: int, eligible: list[int], ports: list[int] | None = None) -> None:
        if not self.anima:
            return
        now = time.monotonic()
        spec = self._anima_foley_spec(ch)
        if not spec:
            if now - self._anima_foley_last > ANIMA_FOLEY_IDLE:
                self._anima_foley_reclaim("no foley instrument")
            return
        pc, lsb, keys = spec
        # Keep wind/brass SFX on the soft banks (Breath / Harmonica).
        # CC00 3 and 8 on PC 122 are the harsh "stab/rip" noises.
        if pc == 121 and lsb not in (0, 1):
            lsb = 0
        pend = self._anima_foley_pend
        if pend and pend["ch"] == ch and (now - pend["t0"]) < 0.05:
            pend["n"] += 1
            pend["note"] = note
            pend["vel"] = vel
            pend["t"] = now + ANIMA_FOLEY_HOLD
            return
        gap = ANIMA_FOLEY_GAP + random.uniform(-ANIMA_FOLEY_GAP_JITTER, ANIMA_FOLEY_GAP_JITTER)
        if (now - self._anima_foley_last) < max(0.6, gap):
            prev = self._anima_foley_pitch[ch]
            self._anima_foley_pitch[ch] = note
            return
        if random.random() < ANIMA_FOLEY_SKIP:
            self._anima_foley_last = now
            prev = self._anima_foley_pitch[ch]
            self._anima_foley_pitch[ch] = note
            return
        prev = self._anima_foley_pitch[ch]
        self._anima_foley_pitch[ch] = note
        jump = abs(note - prev) if prev >= 0 else 0
        if prev >= 0 and jump < ANIMA_FOLEY_JUMP:
            return
        self._anima_foley_pend = {
            "t": now + ANIMA_FOLEY_HOLD + random.uniform(0.0, 0.035), "t0": now,
            "ch": ch, "note": note, "vel": vel, "jump": jump, "prev": prev,
            "hero": hero, "eligible": list(eligible or []),
            "ports": list(ports or []), "n": 1,
            "pc": pc, "lsb": lsb, "keys": keys,
        }

    def _anima_foley_tick(self) -> None:
        pend = getattr(self, "_anima_foley_pend", None)
        if not pend or time.monotonic() < pend["t"]:
            return
        self._anima_foley_pend = None
        self._anima_foley_fire(pend)

    def _anima_foley_fire(self, pend: dict) -> None:
        ch, pc, jump, nnotes = pend["ch"], pend["pc"], pend["jump"], pend["n"]
        hero, eligible, ports = pend["hero"], pend["eligible"], pend["ports"]
        note, vel = pend["note"], pend["vel"]
        prev = pend.get("prev", note)
        now = time.monotonic()
        fam = self._anima_efx_family(ch) or ""
        cat = self._anima_category(ch)
        lsb, keys = pend["lsb"], pend["keys"]
        if fam.startswith("guitar") or cat == "guitar":
            # + samples live near C4. Prefer fret / cut; stroke is a last resort.
            if jump >= 12:
                lsb, keys = 35, (60, 61)        # StlGt.SldNz1
            elif nnotes >= 3:
                lsb, keys = 1, (60, 62)         # cut in a chord (not Chord Stroke)
            elif nnotes >= 2 or jump >= ANIMA_FOLEY_SLIDE:
                lsb, keys = 1, (60, 62)         # Gt.Cut Noise
            else:
                lsb, keys = 0, (60, 64, 67)     # Gt.FretNoise
        elif fam.startswith("bass") or cat == "bass":
            lsb, keys = (5, (48, 50)) if jump >= ANIMA_FOLEY_SLIDE else (2, (36, 38))
        elif cat == "wind" or fam == "ethnic_wind":
            # 122/0 Breath and 122/3 Fl.Breath sit under the line.
            # 122/1 Fl.Key Click is a dart — rare and quieter.
            if jump >= 12:
                lsb, keys = 3, (60, 62)
            elif random.random() < 0.12:
                lsb, keys = 1, (60, 61)
            else:
                lsb, keys = 0, (60, 64)
        elif cat == "brass" or fam in ("orch_brass", "synth_brass"):
            pc = 121
            lsb, keys = (9, (60, 64)) if (self._anima_prog[ch] & 0x7F) in (56, 57) else (8, (60, 64))
        # Key click / brass-noise one-shots sit on C4–C5 and flam the kit.
        if now - getattr(self, "_anima_drum_last", 0.0) < ANIMA_FOLEY_DRUM_GATE:
            return
        if pc == 121 and lsb in (1, 8, 9):
            if now - getattr(self, "_anima_drum_last", 0.0) < 2.0:
                return
        # On-channel tricks do not need a spare part.
        if jump >= ANIMA_FOLEY_BEND_JUMP and ports:
            amt = ANIMA_FOLEY_BEND if note >= prev else -ANIMA_FOLEY_BEND
            scoop = mido.Message("pitchwheel", channel=ch, pitch=amt)
            zero = mido.Message("pitchwheel", channel=ch, pitch=0)
            for port in ports:
                self._send_routed(port, scoop)
                self._anima_strum_q.append((now + ANIMA_FOLEY_BEND_SEC, port, zero))
        dest, fch = self._anima_foley_place(hero, eligible, ch)
        if dest is None or fch is None:
            self._anima_foley_last = now
            self._anima_feedback("foley", "foley SFX skipped (on-channel only)", status=False)
            return
        self._anima_foley_program(dest, fch, pc, lsb)
        wet = bool(self._anima_foley_follow_efx(dest, ch, fch))
        n = keys[self._anima_foley_n % len(keys)]
        self._anima_foley_n += 1
        fv = max(ANIMA_FOLEY_VEL[0], min(ANIMA_FOLEY_VEL[1], 24 + vel // 3))
        if pc == 120 and lsb == 1:  # Gt.Cut Noise is a quiet sample
            fv = min(127, fv + 12)
        if pc == 121 and lsb == 1:  # Fl.Key Click is hot
            fv = max(18, fv - 22)
        elif pc == 121:
            # Breath / brass harmonica foley — sit under the section
            fv = max(14, int(fv * 0.75))
        cat = self._anima_category(ch)
        if cat == "brass" or (self._anima_efx_family(ch) or "").startswith("orch_brass"):
            fv = max(12, int(fv * 0.75))
        # Spare parts often inherit CC7=0 from the file. Stamp level every hit.
        self._safe_out_send(dest, mido.Message("control_change", channel=fch, control=7, value=ANIMA_FOLEY_CC7))
        self._safe_out_send(dest, mido.Message("control_change", channel=fch, control=11, value=110))
        self._safe_out_send(dest, mido.Message("control_change", channel=fch, control=91, value=ANIMA_FOLEY_CC91))
        on = mido.Message("note_on", channel=fch, note=n, velocity=fv)
        off = mido.Message("note_off", channel=fch, note=n, velocity=0)
        pre = ANIMA_FOLEY_EFX_PRE if wet else 0.0
        post = ANIMA_FOLEY_EFX_POST if wet else 0.0
        if pre <= 0:
            self._send_routed(dest, on)
        else:
            self._anima_strum_q.append((now + pre, dest, on))
        self.voice_counts[dest] += 1
        self._anima_strum_q.append((now + pre + ANIMA_FOLEY_MS + post, dest, off))
        self._anima_foley_last = now
        where = "overflow" if dest != hero else "home"
        self._anima_feedback(
            "foley",
            f"foley {pc+1}/{lsb} n{n} P{dest + 1} ch{fch + 1} ({where})",
            status=True,
        )

    def _anima_efx_place(self, ch: int) -> None:
        """Seat one unpinned part on a box. Touches only that box.

        Order: this family's box (guitars prefer a spare unit first), an
        empty box, then the lowest-priority evictable box. A heard owner is
        only displaced by a higher family after ANIMA_EFX_IDLE_SEC of
        silence. Nothing fits → the part plays dry and retries later.
        """
        fam = self._anima_efx_family(ch)
        if not fam:
            return
        home = self._anima_file_home_port()
        reserved = set(self._anima_file_efx_parts) if self._anima_file_efx_t else set()
        if ch in reserved:
            return
        gs = [p for p in self._anima_gs_ports() if p != home]
        if not gs:
            return
        now = time.monotonic()
        pri = {f: i for i, f in enumerate(ANIMA_EFX_PRIORITY)}
        rank = pri.get(fam, 99)

        def _slot(p: int) -> dict:
            return self._anima_slots[p] if p < len(self._anima_slots) else {}

        same = [p for p in gs if _slot(p).get("fam") == fam]
        empty = [p for p in gs if not _slot(p).get("fam")]
        steal = None
        steal_r = -1
        for p in gs:
            of = _slot(p).get("fam")
            if not of or of == fam or of == "file_park":
                continue
            # Never under a sounding player of that box, and never twice
            # inside SWITCH_SEC (one type write per box per switch window).
            if self._anima_port_players_sounding(p):
                continue
            if now - float(_slot(p).get("t") or 0) < ANIMA_EFX_SWITCH_SEC:
                continue
            r = pri.get(of, 99)
            if r <= rank:
                # A higher (or equal) owner only yields once it has gone stale.
                if not self._anima_slot_stale(p, now):
                    continue
            elif not self._anima_slot_stale(p, now):
                # This part is playing and outranks the owner: take it in the
                # owner's gap (none of its channels sounding anywhere).
                owners = set(_slot(p).get("chs") or [])
                if any(k[0] in owners for k in self.active):
                    continue
            if r > steal_r:
                steal, steal_r = p, r
        spare = empty[0] if empty else steal
        port = None
        chs = [ch]
        split = False
        partner = [
            p for p in same
            if len([c for c in (_slot(p).get("chs") or []) if c != ch]) == 1
        ]
        if fam == "guitar_dist" and empty:
            port = empty[0]            # one guitar per unit keeps its pan
        elif fam == "guitar_dist" and partner:
            # Pair with the other guitar (OD1/OD2 keeps both sides) rather
            # than taking another family's box (ONESTOP end: organ lost P3).
            port = partner[0]
            pair = [c for c in (_slot(port).get("chs") or []) if c != ch][:1] + [ch]
            chs = pair
            split = bool(_slot(port).get("split")) or self._anima_chs_want_split(pair)
        elif fam == "guitar_dist" and spare is not None:
            port = spare
        elif same:
            port = same[0]
            sl = _slot(port)
            if fam == "guitar_dist":
                pair = [c for c in (sl.get("chs") or []) if c != ch][:1] + [ch]
                chs = pair
                split = bool(sl.get("split")) or (
                    len(pair) >= 2 and self._anima_chs_want_split(pair)
                )
        elif spare is not None:
            port = spare
        if port is None:
            return
        self._anima_efx_grace = ANIMA_EFX_DUMP_SEC  # playing now; heard at once
        self._anima_commit_slot({"port": port, "fam": fam, "chs": chs, "split": split})
        sl = _slot(port)
        if sl.get("fam") == fam and ch in (sl.get("chs") or []) and self._anima_efx_on[port][ch]:
            self._anima_ch_port[ch] = port

    def _anima_efx_settle_burst(self) -> None:
        """One global plan after the PC dump has gone quiet (or at the first note)."""
        if not getattr(self, "_anima_efx_burst_dirty", False):
            return
        self._anima_efx_burst_dirty = False
        n = int(getattr(self, "_anima_efx_burst_n", 0) or 0)
        self._anima_efx_burst_n = 0
        self._anima_efx_grace = (
            ANIMA_EFX_DUMP_SEC if n >= ANIMA_EFX_BIG_BURST else ANIMA_EFX_PC_GRACE_SEC
        )
        plan = self._anima_build_plan()
        self._anima_commit_plan(plan)
        self._anima_efx_grace = ANIMA_EFX_DUMP_SEC

    def _anima_efx_burst_poll(self) -> None:
        if not getattr(self, "_anima_efx_burst_dirty", False):
            return
        if time.monotonic() - float(getattr(self, "_anima_efx_burst_t", 0.0) or 0.0) >= ANIMA_EFX_BURST_SEC:
            self._anima_efx_settle_burst()

    def _anima_efx_on_pc(self, ch: int) -> None:
        """PC: re-seat a pinned part whose family changed; then mark the burst."""
        ch = ch & 0x0F
        port = self._anima_ch_port.get(ch)
        if port is not None and 0 <= port < len(self._anima_slots):
            sl = self._anima_slots[port]
            fam = self._anima_efx_family(ch)
            if sl.get("fam") not in (None, "file_park") and fam != sl.get("fam"):
                others = [c for c in (sl.get("chs") or []) if c != ch]
                if fam and not others and not self._anima_port_players_sounding(port):
                    # Sole owner, quiet box: retype on the PC, before its notes.
                    self._anima_efx_grace = ANIMA_EFX_PC_GRACE_SEC
                    self._anima_commit_slot({"port": port, "fam": fam, "chs": [ch], "split": False})
                    self._anima_efx_grace = ANIMA_EFX_DUMP_SEC
                    if self._anima_slots[port].get("fam") == fam and self._anima_efx_on[port][ch]:
                        self._anima_ch_port[ch] = port
                        return
                # Leave the box to its remaining owners: unpin + Part Off together.
                sl["chs"] = others
                self._anima_ch_port.pop(ch, None)
                if self._anima_efx_on[port][ch]:
                    self._anima_efx_ours = True
                    self._safe_out_send(
                        port,
                        self._gs_dt1([0x40, self._gs_efx_part_mid(ch), 0x22], [0x00]),
                    )
                    self._anima_efx_on[port][ch] = False
                if not others:
                    # Owner left; box keeps its type but is free for the next family.
                    sl["heard_t"] = 0.0
                    sl["t"] = 0.0
        if self._anima_ch_port.get(ch) is None and self._anima_efx_family(ch):
            self._anima_efx_burst_t = time.monotonic()
            self._anima_efx_burst_dirty = True
            self._anima_efx_burst_n = int(getattr(self, "_anima_efx_burst_n", 0) or 0) + 1

    def _anima_maybe_efx(self, ch: int) -> None:
        if not self.anima or self._anima_is_rhythm(ch):
            return
        fmt = (getattr(self, "detected_format", None) or "").upper()
        if fmt not in ("GS", "SC", "SC-8850", "XG") and not self._anima_gs_ports():
            return
        # A pending setup burst is placed once, before this note routes.
        self._anima_efx_settle_burst()
        # Already parked on a box — do not rebuild the 4-port map.
        # Re-planning every note was the 17:49:27 OD1/OD2 + 170 toggles.
        if self._anima_ch_port.get(ch) is not None:
            return
        # No insert family (sfx, unmapped PC) must not rebuild the plan.
        # A hit on that channel was stealing a box a millisecond after a
        # real part had just turned its EFX on.
        if not self._anima_efx_family(ch):
            return
        # A dry part re-seeks at most once per SWITCH_SEC.
        now = time.monotonic()
        seek = getattr(self, "_anima_efx_seek_t", None)
        if seek is None:
            seek = self._anima_efx_seek_t = [0.0] * 16
        if now - seek[ch] < ANIMA_EFX_SWITCH_SEC:
            return
        seek[ch] = now
        self._anima_efx_place(ch)

    def _anima_efx_assign_family(self, fam: str, hero: int) -> None:
        """EFX On for every channel in this family; Off for the others."""
        ports = self._anima_gs_ports()
        want = {c for c in range(16) if c != 9 and self._anima_efx_family(c) == fam}
        for c in range(16):
            if c in want or not self._gs_efx_parts_on[c]:
                continue
            off = self._gs_dt1([0x40, self._gs_efx_part_mid(c), 0x22], [0x00])
            self._anima_efx_ours = True
            for i in ports:
                self._safe_out_send(i, off)
            self._gs_efx_parts_on[c] = False
        newly = []
        for c in sorted(want):
            already = self._gs_efx_parts_on[c]
            for m in self._gs_efx_on_part(c):
                self._anima_efx_ours = True
                for i in ports:
                    self._safe_out_send(i, m)
            if not already:
                newly.append(c + 1)
        self._anima_efx_hero = hero
        if newly:
            self._anima_feedback(
                "efx-on",
                "GS EFX On → Part " + ",".join(str(n) for n in newly),
                status=True,
            )

    def _anima_efx_assign_part(self, hero: int) -> None:
        fam = self._anima_efx_family(hero) or self._anima_efx_key
        if fam:
            self._anima_efx_assign_family(fam, hero)
    def _anima_humanize_velocity(self, msg: mido.Message) -> mido.Message:
        """Nudge velocity on rigid same-note repeats (including channel 10).

        Normal repeats: bias upward (-3..+7). High-velocity machine-gunning
        (vel >= ANIMA_HUMANIZE_HOT): bias downward (-7..+3) to tame peaks.
        """
        ch = msg.channel & 0x0F
        note = msg.note
        vel = msg.velocity
        now = time.monotonic()
        last_n = self._anima_last_note[ch]
        last_v = self._anima_last_vel[ch]
        last_t = self._anima_last_on[ch]
        ioi = (now - last_t) if last_t else 999.0

        new_vel = vel
        if (
            last_n == note
            and last_v >= 0
            and abs(last_v - vel) <= ANIMA_REPEAT_VEL_SLACK
            and ioi <= ANIMA_REPEAT_IOI
            and vel > 0
        ):
            if vel >= ANIMA_HUMANIZE_HOT:
                lo, hi = -ANIMA_HUMANIZE_HOT_DOWN, ANIMA_HUMANIZE_HOT_UP
                bias = "tame"
            else:
                lo, hi = -ANIMA_HUMANIZE_DOWN, ANIMA_HUMANIZE_UP
                bias = "lift"
            span = hi - lo
            wobble = lo + ((note * 3 + int(now * 50) + ch) % (span + 1))
            if wobble == 0:
                wobble = 1 if bias == "lift" else -1
            new_vel = max(1, min(127, vel + wobble))
            self._anima_stats["humanize"] += 1
            if self._anima_stats["humanize"] % 8 == 1:
                self._anima_feedback(
                    "humanize",
                    f"ch{ch + 1} n{note} {vel}→{new_vel} ({bias} {wobble:+d})",
                    status=True,
                )

        self._anima_last_note[ch] = note
        self._anima_last_vel[ch] = new_vel
        self._anima_last_on[ch] = now
        if new_vel != vel:
            try:
                return msg.copy(velocity=new_vel)
            except Exception:
                return mido.Message("note_on", channel=ch, note=note, velocity=new_vel)
        return msg

    def _anima_apply_note_on_cc(self, port: int, msg: mido.Message) -> None:
        """Set expression *target* (Phase 1.5 ramp). No one-shot jump."""
        ch = msg.channel & 0x0F
        ports = self._anima_ports[ch]
        if port not in ports:
            ports.append(port)
        if self._anima_is_rhythm(ch):
            return
        cat = self._anima_category(ch)
        if cat not in ANIMA_EXPR_CATS:
            return
        if self._anima_mt32_mode() and cat in ANIMA_MOD_CATS:
            if self._anima_cc1_tgt[ch] < 8:
                self._anima_cc1_tgt[ch] = 12
            return
        if time.monotonic() - self._anima_file_cc11_t[ch] < ANIMA_FILE_CC11_HOLD:
            self._anima_stats["skip_cc11"] += 1
            self._anima_cc11_own[ch] = False
            self._anima_feedback(
                "expr-skip",
                f"ch{ch + 1} {cat} file CC11 active",
                status=False,
            )
            return
        # Phrase lock: later notes in the same line do not retarget CC11.
        if self._anima_expr_phrase[ch]:
            self._anima_idle_t[ch] = 0.0
            return
        tgt = ANIMA_EXPR_FLOOR + (msg.velocity * (127 - ANIMA_EXPR_FLOOR)) // 127
        tgt = max(ANIMA_EXPR_FLOOR, min(127, tgt))
        # Stabs: keep prior (louder) expression — do not double-dip velocity
        if self._anima_last_dur[ch] < ANIMA_STAB_SEC and tgt < self._anima_cc11_tgt[ch]:
            tgt = self._anima_cc11_tgt[ch]
        self._anima_expr_peak[ch] = tgt
        self._anima_expr_phrase[ch] = True
        self._anima_expr_shape[ch] = None
        # Shape families wait for the hold clock. Lead / wind / fx take the peak now.
        if cat in ANIMA_EXPR_SHAPE_CATS:
            self._anima_cc11_own[ch] = True
            self._anima_idle_t[ch] = 0.0
            return
        if (not self._anima_cc11_own[ch]) and tgt < 118:
            start = min(tgt, max(ANIMA_EXPR_FLOOR, tgt - 24))
            self._anima_cc11_cur[ch] = start
        self._anima_cc11_tgt[ch] = tgt
        self._anima_cc11_own[ch] = True
        self._anima_idle_t[ch] = 0.0
        self._anima_stats["expr"] += 1
        self._anima_feedback(
            "expr-tgt",
            f"ch{ch + 1} {cat} CC11 → {tgt} (vel {msg.velocity})",
            status=True,
        )

    def _anima_live_ports(self, ch: int) -> list:
        """Ports that currently hold notes on this channel — not historical.

        Include ghost/harmony dests so a swell on the hero also moves the
        doubled voice on another box (same MIDI channel, parallel engines).
        """
        ports = []
        for key, info in self.active.items():
            if key[0] != ch:
                continue
            for p in info.get("ports") or [info["port"]]:
                if p not in ports:
                    ports.append(p)
        for _hero, ghosts in (getattr(self, "_anima_ghosts", None) or {}).items():
            if _hero[0] != ch:
                continue
            for g in ghosts:
                p = g[0] if g else None
                if p is not None and p not in ports:
                    ports.append(p)
        if not ports:
            ports = list(self._anima_ports[ch])
        return ports

    def _anima_wave_sub_restore(self, port: int, ch: int) -> None:
        """A file note is about to play where a bass sub reprogrammed this
        channel: put the unit's own tone (bank / PC / CC7) back first."""
        armed = getattr(self, "_anima_wave_sub_armed", None) or set()
        if (port, ch) not in armed:
            return
        armed.discard((port, ch))
        saved = (getattr(self, "_anima_wave_sub_saved", None) or {}).pop((port, ch), None)
        if not saved:
            return
        cc0, cc32, pc, cc7 = saved
        if cc32 is not None:
            self._safe_out_send(port, mido.Message("control_change", channel=ch, control=32, value=cc32))
        if cc0 is not None:
            self._safe_out_send(port, mido.Message("control_change", channel=ch, control=0, value=cc0))
        if pc is not None:
            self._safe_out_send(port, mido.Message("program_change", channel=ch, program=pc))
        if cc7 is not None:
            self._safe_out_send(port, mido.Message("control_change", channel=ch, control=7, value=cc7))
        self._anima_feedback("ghost", f"ch{ch + 1} tone restored on P{port + 1} after bass sub", status=False)

    def _anima_mod_clear(self, ch: int) -> None:
        """CC1=0 on every unit that still holds a raised wheel for this channel.

        ONESTOP: ch6's brass swell left CC1=25 on P2; ch6 then became a
        piano there and played with heavy vibrato. Same for a file lead's
        wheel carried into a mallet PC.
        """
        ch = ch & 0x0F
        shadow = getattr(self, "_cc1_port", None) or []
        msg = mido.Message("control_change", channel=ch, control=1, value=0)
        for p, vals in enumerate(shadow):
            if vals[ch] > 0:
                self._safe_out_send(p, msg)
        self._anima_cc1_cur[ch] = 0
        self._anima_cc1_tgt[ch] = 0
        _l1, l11 = self._anima_cc_sent[ch]
        self._anima_cc_sent[ch] = (0, l11)
        self.mod[ch] = 0

    def _anima_send_cc(self, ports, ch: int, control: int, value: int) -> None:
        """Send a CC only to live ports, quantized, with a small per-port gap.

        MS40 / busy USB interfaces choke if we spray every ramp step to every
        port a channel has ever touched.
        """
        if not ports:
            return
        last1, last11 = self._anima_cc_sent[ch]
        last = last1 if control == 1 else last11
        if last >= 0 and abs(value - last) < ANIMA_CC_QUANT and value not in (0, 127):
            return
        now = time.monotonic()
        sent_any = False
        msg = mido.Message("control_change", channel=ch, control=control, value=value)
        gap_t = self._anima_cc_port_t or []
        for p in ports:
            if p < len(gap_t) and now - gap_t[p] < ANIMA_CC_GAP:
                continue
            self._safe_out_send(p, msg)
            if p < len(gap_t):
                gap_t[p] = now
            sent_any = True
        if not sent_any:
            return
        if control == 1:
            self._anima_cc_sent[ch] = (value, last11)
            self.mod[ch] = value
            self.mod_time[ch] = now
        elif control == 11:
            self._anima_cc_sent[ch] = (last1, value)
        elif control == ANIMA_EFX_CTRL_CC:
            self._anima_efx_cc16 = value

    def _anima_step(self, cur: int, tgt: int, rate: float, dt: float) -> int:
        if cur == tgt or dt <= 0:
            return tgt if cur == tgt else cur
        delta = rate * dt
        if tgt > cur:
            return min(tgt, int(cur + max(1, delta)))
        return max(tgt, int(cur - max(1, delta)))

    def _anima_roll_mode(self, ch: int) -> str | None:
        """strum (guitar) / unroll (mallets, harp, pizz, ethnic plucked) / None."""
        if self._anima_is_rhythm(ch):
            return None
        pc = self._anima_cat_pc(ch)
        if pc in ANIMA_UNROLL_PCS:
            return "unroll"
        if self._anima_category(ch) in ANIMA_STRUM_CATS:
            return "strum"
        return None

    def _anima_should_strum(self, ch: int) -> bool:
        if self._anima_is_rhythm(ch):
            return False
        return self._anima_roll_mode(ch) is not None

    def _anima_strum_style(self, ch: int) -> str:
        """Choose stroke style for this chord.

        Default: alternate. Occasional double down/up for feel.
        Distortion/overdrive (Hetfield): down-picks only.
        """
        pc = self._anima_prog[ch]
        if pc in ANIMA_HETFIELD_PC:
            return "hetfield"
        if self._anima_file_dirt[ch] and self._anima_hetfield_roll[ch]:
            return "hetfield"
        n = self._anima_strum_n[ch]
        # Every 8th stroke: stay in the same direction (double down or up)
        if n and n % 8 == 0:
            return "hold"
        # Every 13th: forced down (accent)
        if n and n % 13 == 0:
            return "down"
        return "alt"

    def _anima_strum_push(self, ch: int, note_msg, ports: list) -> None:
        now = time.monotonic()
        buf = self._anima_strum_buf[ch]
        if buf is None:
            mode = self._anima_roll_mode(ch) or "strum"
            if mode == "unroll":
                style = "alt"
            else:
                style = self._anima_strum_style(ch)
            if style == "hetfield" or style == "down":
                direction = 1
            elif style == "hold":
                direction = self._anima_strum_dir[ch]
            else:
                direction = -self._anima_strum_dir[ch]
            self._anima_strum_dir[ch] = direction
            buf = {
                "t0": now,
                "dir": direction,
                "style": style,
                "mode": mode,
                "items": [],
            }
            self._anima_strum_buf[ch] = buf
        buf["items"].append((note_msg, list(ports)))

    def _anima_strum_flush(self, ch: int, *, immediate: bool = False) -> None:
        buf = self._anima_strum_buf[ch]
        if not buf or not buf["items"]:
            self._anima_strum_buf[ch] = None
            return
        now = time.monotonic()
        mode = buf.get("mode") or "strum"
        collect = ANIMA_UNROLL_COLLECT if mode == "unroll" else ANIMA_STRUM_COLLECT
        if not immediate and (now - buf["t0"]) < collect:
            return
        items = buf["items"]
        items.sort(key=lambda it: it[0].note)
        if buf["dir"] < 0:
            items.reverse()
        last = self._anima_strum_last_t[ch]
        ioi = (now - last) if last else 999.0
        burst = self._anima_strum_burst[ch]
        pickup = 0.0
        release = 0.0
        jitter = ANIMA_UNROLL_JITTER if mode == "unroll" else ANIMA_STRUM_JITTER
        if mode == "strum" and last and ioi > ANIMA_BURST_HOLE and len(items) >= 2:
            # First stroke after a hole – land a hair late
            pickup = random.uniform(*ANIMA_BURST_PICKUP)
            burst = 1
        elif mode == "strum" and ANIMA_BURST_IOI_LO <= ioi <= ANIMA_BURST_IOI_HI and len(items) >= 2:
            burst += 1
            pickup = random.uniform(-jitter, jitter)
            release = random.uniform(*ANIMA_BURST_RELEASE)
        else:
            burst = 1 if len(items) >= 2 else 0
        self._anima_strum_burst[ch] = burst
        self._anima_strum_last_t[ch] = now
        self._anima_strum_off_hold[ch] = release
        t0 = now + pickup + random.uniform(-jitter, jitter)
        pc = self._anima_cat_pc(ch)
        if mode == "unroll":
            step = ANIMA_UNROLL_STEP
        elif pc in ANIMA_ACOUSTIC_PCS:
            step = ANIMA_STRUM_STEP * 1.65
        else:
            step = ANIMA_STRUM_STEP
        for i, (note_msg, ports) in enumerate(items):
            string_j = random.uniform(0.0, jitter)
            when = t0 + (i * step) + string_j
            for p in ports:
                self._anima_strum_q.append((when, p, note_msg))
        self._anima_strum_n[ch] += 1
        nstr = len(items)
        label = {1: "down", -1: "up"}[buf["dir"]]
        if buf["style"] == "hetfield":
            label = "down/Hetfield"
        if nstr >= 2:
            kind = "roll" if mode == "unroll" else "strum"
            self._anima_feedback(
                kind,
                f"ch{ch + 1} {label} x{nstr}",
                status=True,
            )
        self._anima_strum_buf[ch] = None

    def _anima_strum_drain(self) -> None:
        if self.anima:
            self._anima_foley_tick()
        if not self._anima_strum_q:
            return
        now = time.monotonic()
        keep = []
        for when, port, msg in self._anima_strum_q:
            if when <= now:
                self._send_routed(port, msg)
                if msg.type == "note_on" and msg.velocity > 0:
                    info = self.active.get((msg.channel & 0x0F, msg.note))
                    if info:
                        info["strum_pending"] = False
                elif (
                    msg.type in ("note_off",)
                    or (msg.type == "note_on" and msg.velocity == 0)
                ) and self._anima_foley_ch[port] == (msg.channel & 0x0F):
                    self.voice_counts[port] = max(0, self.voice_counts[port] - 1)
                elif msg.type in ("note_off",) or (msg.type == "note_on" and msg.velocity == 0):
                    self.voice_counts[port] = max(0, self.voice_counts[port] - 1)
            else:
                keep.append((when, port, msg))
        self._anima_strum_q = keep

    def _anima_strum_cancel(self, ch: int, note: int) -> bool:
        """Note-off arrived while the on was still in the strum queue.

        Ghost / 1-tick backbeats die if we drop the on. Fire any pending
        on immediately and return False so the off still goes out.
        """
        fired = False
        buf = self._anima_strum_buf[ch]
        if buf and buf.get("items"):
            keep = []
            for note_msg, ports in buf["items"]:
                if note_msg.note == note:
                    for p in ports:
                        self._send_routed(p, note_msg)
                    fired = True
                else:
                    keep.append((note_msg, ports))
            buf["items"] = keep
            if not keep:
                self._anima_strum_buf[ch] = None
        keep_q = []
        for when, port, msg in self._anima_strum_q:
            if (
                msg.type == "note_on"
                and (msg.channel & 0x0F) == ch
                and msg.note == note
                and msg.velocity > 0
            ):
                self._send_routed(port, msg)
                info = self.active.get((ch, note))
                if info:
                    info["strum_pending"] = False
                fired = True
                continue
            keep_q.append((when, port, msg))
        self._anima_strum_q = keep_q
        return False

    def _anima_tick(self) -> None:
        """Hold-detect + joystick-style ramps for CC1 / CC11."""

        if not self.anima:
            return
        for ch in range(16):
            if self._anima_strum_buf[ch] is not None:
                self._anima_strum_flush(ch)
        self._anima_strum_drain()
        now = time.monotonic()
        dt = now - self._anima_ramp_t
        if dt <= 0:
            return
        # Cap dt so a UI stall doesn't jump the wheel
        if dt > 0.08:
            dt = 0.08
        self._anima_ramp_t = now
        self._anima_efx_param_tick(dt)

        # --- arm mod targets for notes held long enough ---
        for key, info in list(self.active.items()):
            ch, note = key[0], key[1]
            if ch == 9 or key in self._anima_mod_on:
                continue
            cat = self._anima_category(ch)
            if cat not in ANIMA_MOD_CATS:
                continue
            if self._anima_ch_lfo_insert(ch):
                continue
            if cat in ("brass", "wind"):
                if self._anima_mt32_mode():
                    held_need, mod_level = ANIMA_MOD_HELD_SEC_MT32, ANIMA_MOD_LEVEL_WIND
                else:
                    held_need, mod_level = ANIMA_MOD_HELD_SEC_WIND, ANIMA_MOD_LEVEL_WIND
            else:
                held_need, mod_level = ANIMA_MOD_HELD_SEC, ANIMA_MOD_LEVEL
            if (now - info.get("time", now)) < held_need:
                continue
            ports = info.get("ports") or [info["port"]]
            self._anima_ports[ch] = list(ports)
            self._anima_cc1_tgt[ch] = mod_level
            self._anima_mod_on.add(key)
            self._anima_mod_ch[ch] = True
            self._anima_stats["mod"] += 1
            self._anima_feedback(
                "mod-tgt",
                f"ch{ch + 1} n{note} {cat} CC1 → {mod_level} (held {held_need:.2f}s)",
                status=True,
            )

        # --- held-chord shapes (swell / fp / sfz→cres). No messa. ---
        for ch in range(16):
            if not any(k[0] == ch for k in self.active):
                continue
            if time.monotonic() - self._anima_file_cc11_t[ch] < ANIMA_FILE_CC11_HOLD:
                continue
            cat = self._anima_category(ch)
            if cat not in ANIMA_EXPR_SHAPE_CATS:
                continue
            if self._anima_last_dur[ch] < ANIMA_STAB_SEC and self._anima_expr_shape[ch] is None:
                continue
            hold = 0.0
            oldest = None
            for (c, _n), info in self.active.items():
                if c != ch:
                    continue
                t0 = info.get("time", now)
                oldest = t0 if oldest is None else min(oldest, t0)
            if oldest is not None:
                hold = now - oldest
            shape = self._anima_expr_shape[ch]
            if shape is None:
                if hold < ANIMA_EXPR_SHAPE_HOLD:
                    continue
                seed = int(self._anima_ensure_efx_seed()) & 0xFFFF
                seed = (seed + ch * 19) & 0xFFFF
                if getattr(self, "anima_game", False):
                    seed = (seed + int(self._anima_scene_salt() or 0)) & 0xFFFF
                if cat == "brass":
                    shape = "swell"  # fp/sfz dunked muted horns
                else:
                    shape = ANIMA_EXPR_SHAPE_NAMES[seed % len(ANIMA_EXPR_SHAPE_NAMES)]
                self._anima_expr_shape[ch] = shape
                self._anima_expr_shape_t[ch] = now
                peak = self._anima_expr_peak[ch] or ANIMA_EXPR_DEFAULT
                dip = max(ANIMA_EXPR_FLOOR, peak - 12)
                if shape == "swell":
                    start = max(ANIMA_EXPR_FLOOR, peak - 10)
                    self._anima_cc11_cur[ch] = min(self._anima_cc11_cur[ch], start)
                    self._anima_cc11_tgt[ch] = peak
                elif shape == "fp":
                    self._anima_cc11_cur[ch] = peak
                    self._anima_cc11_tgt[ch] = dip
                else:  # sfz → cres
                    self._anima_cc11_cur[ch] = peak
                    self._anima_cc11_tgt[ch] = dip
                self._anima_cc11_own[ch] = True
                self._anima_stats["expr"] += 1
                self._anima_feedback(
                    "expr-shape",
                    f"ch{ch + 1} {cat} {shape} peak {peak}",
                    status=True,
                )
            elif shape == "sfz":
                if now - self._anima_expr_shape_t[ch] >= ANIMA_EXPR_SHAPE_FP_DIP:
                    peak = self._anima_expr_peak[ch] or ANIMA_EXPR_DEFAULT
                    if self._anima_cc11_tgt[ch] < peak:
                        self._anima_cc11_tgt[ch] = peak

        # --- idle: return wheels to rest ---
        active_ch = {k[0] for k in self.active}
        for ch in range(16):
            if ch in active_ch:
                self._anima_idle_t[ch] = now
                continue
            if self._anima_idle_t[ch] == 0.0:
                self._anima_idle_t[ch] = now
            if now - self._anima_idle_t[ch] < ANIMA_IDLE_SEC:
                continue
            if self._anima_mod_ch[ch] or self._anima_cc1_tgt[ch] or self._anima_cc1_cur[ch]:
                self._anima_cc1_tgt[ch] = 0
            if self._anima_cc11_own[ch] and self._anima_cc11_tgt[ch] != ANIMA_EXPR_DEFAULT:
                if now - self._anima_file_cc11_t[ch] >= ANIMA_FILE_CC11_HOLD:
                    self._anima_cc11_tgt[ch] = ANIMA_EXPR_DEFAULT
                    self._anima_expr_phrase[ch] = False
                    self._anima_expr_shape[ch] = None

        # --- ramp toward targets ---
        for ch in range(16):
            ports = self._anima_live_ports(ch) if self.active else self._anima_ports[ch]
            if not ports:
                continue
            # Mod
            cur, tgt = self._anima_cc1_cur[ch], self._anima_cc1_tgt[ch]
            if cur != tgt:
                rate = ANIMA_RAMP_MOD_UP if tgt > cur else ANIMA_RAMP_MOD_DOWN
                nxt = self._anima_step(cur, tgt, rate, dt)
                if nxt != cur:
                    self._anima_cc1_cur[ch] = nxt
                    self._anima_send_cc(ports, ch, 1, nxt)
                    if nxt == tgt:
                        if tgt == 0:
                            self._anima_mod_ch[ch] = False
                            self._anima_mod_clear(ch)   # units the ramp skipped
                            self._anima_feedback("mod-rest", f"ch{ch + 1} CC1=0", status=False)
                        else:
                            self._anima_feedback("mod", f"ch{ch + 1} CC1={nxt}", status=False)
            # Expression
            if not self._anima_cc11_own[ch]:
                continue
            if now - self._anima_file_cc11_t[ch] < ANIMA_FILE_CC11_HOLD:
                continue
            cur, tgt = self._anima_cc11_cur[ch], self._anima_cc11_tgt[ch]
            if cur != tgt:
                rate = ANIMA_RAMP_EXPR_UP if tgt > cur else ANIMA_RAMP_EXPR_DOWN
                nxt = self._anima_step(cur, tgt, rate, dt)
                if nxt != cur:
                    self._anima_cc11_cur[ch] = nxt
                    self._anima_send_cc(ports, ch, 11, nxt)
                    # Only drop ownership after a real idle return to default
                    active_ch = {k[0] for k in self.active}
                    if (
                        nxt == ANIMA_EXPR_DEFAULT
                        and tgt == ANIMA_EXPR_DEFAULT
                        and ch not in active_ch
                    ):
                        self._anima_cc11_own[ch] = False
                        self._anima_expr_phrase[ch] = False
                        self._anima_expr_shape[ch] = None
                        self._anima_feedback("expr-rest", f"ch{ch + 1} CC11=127", status=False)

    def _thin_high_rate(self, msg: mido.Message) -> bool:
        """True = drop this message (too soon after the last of its kind)."""
        if self.n_ports <= 1:
            return False
        kind = None
        settle = False
        if msg.type == "pitchwheel":
            # 88Pro leads in YS4-style files use small scoops; do not thin them.
            if any(self._gs_canvas_class(tags) == "88pro" for tags in self.out_formats):
                return False
            kind = "pw"
            settle = msg.pitch == 0
        elif msg.type == "aftertouch":
            kind = "at"
            settle = msg.value == 0
        elif msg.type == "polytouch":
            kind = "pt"
            settle = msg.value == 0
        elif msg.type == "control_change" and msg.control == 1:
            kind = "cc1"
            settle = msg.value == 0
        if kind is None:
            return False
        ch = getattr(msg, "channel", 0) & 0x0F
        key = (ch, kind)
        now = time.monotonic()
        last = self._thin_last.get(key, 0.0)
        if settle or now - last >= STREAM_THIN_SEC:
            self._thin_last[key] = now
            return False
        return True


    def _record_skip(self, msg: mido.Message) -> bool:
        return msg.type in ("clock", "start", "stop", "continue", "songpos", "songselect", "active_sensing")

    def _record_fmt_tag(self, port: int | None = None) -> str:
        if port is None:
            fmt = (getattr(self, "detected_format", None) or "in").lower()
            return fmt.replace(" ", "") or "in"
        tags = []
        try:
            tags = sorted(str(t).lower() for t in self.out_formats[port] if str(t).lower() != "any")
        except Exception:
            tags = []
        if tags:
            return "+".join(tags)
        fmt = (getattr(self, "detected_format", None) or "out").lower()
        return fmt.replace(" ", "") or "out"

    @staticmethod
    def _record_slug(name: str) -> str:
        s = "".join(ch if ch.isalnum() or ch in "-_+" else "-" for ch in (name or "port"))
        while "--" in s:
            s = s.replace("--", "-")
        return s.strip("-")[:40] or "port"

    def _record_start(self, reason: str = "") -> None:
        import datetime
        if self._rec_on:
            self._record_stop("restart")
        self._rec_on = True
        self._rec_wanted = True
        self._rec_t0 = time.monotonic()
        self._rec_last = self._rec_t0
        self._rec_in = []
        self._rec_out = [[] for _ in range(self.n_ports)]
        self._rec_stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        self._set_status(f"Recording ON ({self._rec_stamp})", duration=3.0)
        self._log_line(f"RECORD start {self._rec_stamp} ({reason})")

    def _record_touch(self) -> None:
        self._rec_last = time.monotonic()

    def _record_in(self, msg: mido.Message) -> None:
        if self._record_skip(msg):
            return
        if self._rec_wanted and not self._rec_on:
            self._record_start("activity after idle")
        if not self._rec_on:
            return
        self._record_touch()
        self._rec_in.append((time.monotonic() - self._rec_t0, msg.copy(time=0)))

    def _record_out(self, port: int, msg: mido.Message) -> None:
        if self._record_skip(msg):
            return
        if self._rec_wanted and not self._rec_on:
            self._record_start("activity after idle")
        if not self._rec_on:
            return
        self._record_touch()
        if 0 <= port < len(self._rec_out):
            self._rec_out[port].append((time.monotonic() - self._rec_t0, msg.copy(time=0)))

    def _record_idle_check(self) -> None:
        if not self._rec_on or not self._rec_wanted:
            return
        if (time.monotonic() - self._rec_last) < RECORD_IDLE_SEC:
            return
        has = self._rec_in or any(self._rec_out)
        if has:
            self._record_stop("idle 10s")
            self._rec_wanted = True  # next MIDI opens a new take
        else:
            # nothing captured — just roll the stamp so we don't sit on an empty take
            self._rec_t0 = time.monotonic()
            self._rec_last = self._rec_t0

    def _record_fill_track(self, events, name: str, tempo: bool = False):
        track = mido.MidiTrack()
        track.append(mido.MetaMessage("track_name", name=name[:32], time=0))
        if tempo:
            track.append(mido.MetaMessage("set_tempo", tempo=500000, time=0))
        last_tick = 0
        for t, msg in events:
            tick = int(max(0.0, t) * 960.0)  # 120 BPM, 480 TPB
            delta = max(0, tick - last_tick)
            last_tick = tick
            try:
                track.append(msg.copy(time=delta))
            except Exception:
                continue
        track.append(mido.MetaMessage("end_of_track", time=1))
        return track

    def _record_write_file(self, events, name: str):
        """Type-1 SMF: tempo + one chronological track (SysEx interleaved).

        Per-channel tracks left SysEx on a dead last track; some players
        (and 88emu via those players) then replay a different stream than live.
        """
        mid = mido.MidiFile(type=1, ticks_per_beat=480)
        mid.tracks.append(self._record_fill_track([], name[:32], tempo=True))
        mid.tracks.append(self._record_fill_track(events, "MIDI"))
        return mid

    def _record_stop(self, reason: str = "") -> None:
        if not self._rec_on:
            return
        self._rec_on = False
        import os
        dest = self.record_dir or "."
        try:
            os.makedirs(dest, exist_ok=True)
        except Exception:
            dest = "."
        stamp = self._rec_stamp or "take"
        written = []

        def _save(events, port_label, fmt_tag, direction):
            if not events:
                return
            mid = self._record_write_file(events, port_label[:32])
            fname = f"{direction}-{self._record_slug(port_label)}-{self._record_slug(fmt_tag)}-{stamp}.mid"
            path = os.path.join(dest, fname)
            mid.save(path)
            written.append(path)

        try:
            _save(self._rec_in, getattr(self, "in_name", None) or "IN", self._record_fmt_tag(None), "IN")
        except Exception as e:
            self._log_line(f"RECORD IN save failed: {e}")
        for i, ev in enumerate(self._rec_out):
            try:
                _save(ev, self.port_names[i], self._record_fmt_tag(i), "OUT")
            except Exception as e:
                self._log_line(f"RECORD OUT{i + 1} save failed: {e}")
        self._rec_in = []
        self._rec_out = [[] for _ in range(self.n_ports)]
        names = ", ".join(written) if written else "(none)"
        self._set_status(f"Recording saved: {names}", duration=5.0)
        self._log_line(f"RECORD stop ({reason}): {names}")

    def _is_init_reset_sysex(self, msg: mido.Message) -> bool:
        """GS Reset / XG On / GM On — start of a module program dump."""
        if msg.type != "sysex":
            return False
        d = list(msg.data or [])
        if d and d[0] == 0xF0:
            d = d[1:]
        if len(d) >= 7 and d[0] == 0x41 and d[2] == 0x42 and d[3] == 0x12:
            if d[4] == 0x00 and d[5] == 0x00 and d[6] == 0x7F:
                return True
            if d[4] == 0x40 and d[5] == 0x00 and d[6] == 0x7F:
                return True
        if len(d) >= 6 and d[0] == 0x43 and d[2] == 0x4C and d[3] == 0x00 and d[4] == 0x00 and d[5] == 0x7E:
            return True
        if len(d) >= 4 and d[0] == 0x7E and d[2] == 0x09 and d[3] in (0x01, 0x03):
            return True
        return False

    def _init_dump_begin(self, why: str = "GS Reset") -> None:
        if self._init_dump:
            self._init_dump_last = time.monotonic()
            return
        self._init_dump = True
        self._init_dump_last = time.monotonic()
        self._init_dump_n = 0
        self._gs_reset_part_rx()
        self._log_line(f"INIT dump fast-path ON ({why})")
        self._set_status(f"Init dump — fast path ({why})", duration=2.0)
        # File is about to re-program inserts / rhythm. Clear Anima's
        # previous file-EFX picture so observe during the dump is clean.
        if self.anima:
            self._anima_release_efx_lock("reset")
            self._anima_reset_efx_seed()
            self._anima_gs_map_home("GS Reset")

    def _init_dump_end(self, why: str) -> None:
        if not self._init_dump:
            return
        n = self._init_dump_n
        self._init_dump = False
        self._gs_ys_stack_apply()
        self._log_line(f"INIT dump fast-path OFF ({why}, {n} msgs)")
        extra = ""
        if self.anima and getattr(self, "_anima_file_efx_parts", None):
            parts = ",".join(str(p + 1) for p in sorted(self._anima_file_efx_parts))
            extra = f" · file EFX parts {parts}"
            self._log_line(f"ANIMA efx-file: dump captured parts {parts}")
        self._set_status(f"Init dump done ({why}, {n}){extra}", duration=2.5)

    def _init_dump_touch(self, msg: mido.Message) -> None:
        if msg.type in ("sysex", "control_change", "program_change"):
            self._init_dump_last = time.monotonic()
            self._init_dump_n += 1

    def process(self, msg: mido.Message):
        # Any MIDI activity refreshes format-idle timer
        self.last_midi_time = time.monotonic()
        # YS4-style dumps pause ~0.9s after GS Reset. 200ms was cutting the window.
        if self._init_dump and (self.last_midi_time - self._init_dump_last) >= 3.0:
            self._init_dump_end("idle")
        self._record_in(msg)
        if self.anima and (msg.type == "clock" or (msg.type == "note_on" and msg.velocity > 0)):
            self._tempo_feed(msg, self.last_midi_time)

        # Drop surplus pitch/AT/mod from the FILE. 190 pitchbends in 100ms
        # cannot fit a 31.25 kbps DIN cable (MS40, many M8U ports). USB
        # modules hide this; hardware does not. Always keep center/zero.
        if self._thin_high_rate(msg):
            return

        # Anima bookkeeping (no-ops when disabled aside from the bool check)
        if self.anima:
            if msg.type == "control_change":
                self._anima_on_cc(msg)
            elif msg.type == "program_change":
                self._anima_on_pc(msg)

        # Voodoo: while loading or catching up, defer input (catch-up owns drain)
        if self.voodoo_loading or self.voodoo_catchup:
            # MT-32 SysEx still aborts Voodoo immediately
            if msg.type == "sysex" and self._voodoo_on_mt32_sysex(msg):
                # Fall through to normal SysEx routing after exit
                pass
            else:
                self._voodoo_enqueue(msg)
                return

        if msg.type in ("note_on", "note_off"):
            key = (msg.channel, msg.note)
            is_note_on = msg.type == "note_on" and msg.velocity > 0
            if is_note_on and self._init_dump:
                self._init_dump_end("first note")
            if is_note_on and self.anima:
                ch = msg.channel & 0x0F
                pend = self._anima_pend_bank[ch]
                if pend:
                    pc = int(self._file_pc[ch]) & 0x7F
                    if not anima_combo_ok(pend[0], self._anima_file_map(*pend), pc):
                        self._anima_pend_bank[ch] = None
            now = time.monotonic()

            if is_note_on:
                is_chord = (now - self.last_note_time) < self.chord_window
                self.last_note_time = now
                self.last_activity_time = now
                self.notes_played += 1

                if is_chord:
                    self.current_chord_size += 1
                else:
                    self.current_chord_size = 1

                if self.current_chord_size > self.peak_chord_size:
                    self.peak_chord_size = self.current_chord_size

                eligible = self._eligible_note_ports()
                # Phase V2: Voodoo multi-map pins melody channels to one unit;
                # rhythm (ch10) may list several units for load-balance.
                # Trust the map exclusively — do not intersect with Crucible
                # eligibility (avoids silently dropping a mapped unit).
                voodoo_ports = self._voodoo_ports_for_channel(msg.channel)
                if voodoo_ports is not None:
                    eligible = list(voodoo_ports)

                if not eligible:
                    self.drop_count += 1
                    if not getattr(self, "_warned_no_match", False):
                        self._warned_no_match = True
                        fmt = self.detected_format or "unknown"
                        self._set_status(
                            f"No ports match format {fmt} – check --outs tags",
                            duration=4.0,
                        )
                    return

                # SCPOP: broadcast the same note to every format-matched port.
                # After init only one SC input may produce sound, but we cannot
                # know which Duality out is Part A — broadcasting is safe.
                if self.scpop_mode:
                    targets = eligible
                elif voodoo_ports is not None and len(eligible) == 1:
                    # Strict channel affinity (typical 2-unit melody split)
                    targets = [eligible[0]]
                    self.last_chord_port = eligible[0]
                elif voodoo_ports is not None:
                    # Rhythm (or future multi-owner channels): load-balance
                    port = self._choose_from_ports(eligible, is_chord)
                    if port is None:
                        self.drop_count += 1
                        return
                    self.last_chord_port = port
                    targets = [port]
                else:
                    ch_n = msg.channel & 0x0F
                    if self.anima:
                        fchs = getattr(self, "_anima_foley_ch", None) or []
                        blocked = [
                            i for i, fc in enumerate(fchs)
                            if fc == ch_n
                        ]
                        if blocked:
                            filtered = [p for p in eligible if p not in blocked]
                            if filtered:
                                eligible = filtered
                    if (
                        self.anima
                        and self._anima_file_efx_t
                        and ch_n in self._anima_file_efx_parts
                        and self._anima_file_efx_home is not None
                    ):
                        self._anima_ch_port[ch_n] = self._anima_file_efx_home
                    pin = self._anima_ch_port.get(ch_n) if self.anima else None
                    if pin is None and self.anima:
                        self._anima_maybe_efx(ch_n)
                        pin = self._anima_ch_port.get(ch_n)
                    if pin is None and self.anima:
                        # Keep a phrase on one box even without an EFX slot.
                        # Flute/wind lines hopping P1–P4 sounded like cutoffs.
                        last = self._anima_note_port.get(ch_n)
                        if last is not None and last in eligible:
                            lim = self.poly_limits[last] or 1
                            if self.voice_counts[last] < lim:
                                pin = last
                    wet_skip = None
                    if (
                        pin is not None
                        and self.anima
                        and self._anima_efx_wet_blocked(pin, ch_n)
                    ):
                        # Box was just retyped / Part On for this channel:
                        # this note plays dry elsewhere (not delayed); the
                        # next phrase lands on the insert.
                        others = [p for p in eligible if p != pin]
                        if others:
                            wet_skip = pin
                            pin = None
                    if pin is not None and pin in eligible:
                        port = pin
                    elif wet_skip is not None:
                        port = self._choose_from_ports(
                            [p for p in eligible if p != wet_skip], is_chord
                        )
                    else:
                        port = self._choose_port(is_chord)
                    if port is None:
                        self.drop_count += 1
                        return
                    self.last_chord_port = port
                    if self.anima:
                        self._anima_note_port[ch_n] = port
                    targets = [port]

                # Same key already down. Drums / rhythm parts often retrigger
                # without an off — synthesize one so a later file-off is not
                # the voice that gets dropped. Melodic parts stack in 88emu
                # when the file overlaps the same pitch; we refcount those
                # ons so a later off cannot hop to another port.
                stacking = False
                if key in self.active:
                    old = self.active[key]
                    old_ports = old.get("ports") or [old["port"]]
                    ch_n = msg.channel & 0x0F
                    rhythm = ch_n == 9 or (
                        hasattr(self, "_anima_is_rhythm")
                        and self._anima_is_rhythm(ch_n)
                    )
                    old_w = int(old.get("voices") or 1)
                    self._last_key_ports[key] = old_ports
                    if rhythm:
                        self.active.pop(key, None)
                        for p in old_ports:
                            self.voice_counts[p] = max(0, self.voice_counts[p] - old_w)
                        off = mido.Message(
                            "note_off",
                            channel=msg.channel,
                            note=msg.note,
                            velocity=0,
                        )
                        for p in old_ports:
                            self._send_routed(p, off)
                        if self.anima:
                            self._anima_mod_on.discard(key)
                            self._anima_ghost_kill(key)
                    else:
                        stacking = True
                        targets = list(old_ports)
                        self.last_chord_port = targets[0]

                # Anima Phase 1: velocity humanize before send
                note_msg = msg
                if self.anima:
                    note_msg = self._anima_humanize_velocity(msg)
                    # File (or retrigger) now owns this pitch — drop a harmony
                    # ghost that was sitting on the same channel+note.
                    self._anima_ghost_release_pitch(note_msg.channel & 0x0F, note_msg.note)

                def _notes_on_port(p: int) -> int:
                    return sum(
                        1 for info in self.active.values()
                        if p in info.get("ports", [info["port"]])
                    )

                sent_ports = []
                for port in targets:
                    real_count = _notes_on_port(port)
                    if real_count >= self.poly_limits[port]:
                        self._steal_least_important(port)
                    real_count = _notes_on_port(port)
                    if real_count >= self.poly_limits[port]:
                        continue  # this port full – try others when broadcasting
                    self._maybe_gs_efx_on_note(port, note_msg)
                    sent_ports.append(port)

                if not sent_ports:
                    self.drop_count += 1
                    return

                if self.anima and getattr(self, "_anima_wave_sub_armed", None):
                    for port in sent_ports:
                        self._anima_wave_sub_restore(port, note_msg.channel & 0x0F)

                if self.anima and self._anima_should_strum(note_msg.channel & 0x0F):
                    self._anima_strum_push(note_msg.channel & 0x0F, note_msg, sent_ports)
                else:
                    for port in sent_ports:
                        self._send_routed(port, note_msg)

                if self.anima:
                    for port in sent_ports:
                        self._anima_apply_note_on_cc(port, note_msg)
                    try:
                        played = self._anima_efx_family(note_msg.channel & 0x0F)
                    except Exception:
                        played = None
                    if played:
                        self._anima_fam_played[played] = time.monotonic()
                        # This box's owner is actively playing. Any note of a
                        # pinned owner counts: a re-struck held key stays on its
                        # old port, and that must not make the box look unheard.
                        hch = note_msg.channel & 0x0F
                        hp = self._anima_ch_port.get(hch)
                        if hp is not None and 0 <= hp < len(self._anima_slots):
                            hsl = self._anima_slots[hp]
                            if hch in (hsl.get("chs") or []):
                                hsl["heard_t"] = time.monotonic()
                    if (note_msg.channel & 0x0F) == 9:
                        self._anima_drum_last = time.monotonic()
                    self._anima_maybe_foley(
                        note_msg.channel & 0x0F,
                        note_msg.note,
                        note_msg.velocity,
                        sent_ports[0],
                        list(eligible),
                        sent_ports,
                    )
                    self._anima_ghost_maybe(note_msg, sent_ports)

                primary = sent_ports[0]
                self.last_chord_port = primary
                w = self._tone_voices(note_msg.channel & 0x0F, primary)
                for port in sent_ports:
                    self.voice_counts[port] += w
                if stacking and key in self.active:
                    info = self.active[key]
                    stack = list(info.get("stack") or info.get("ports") or [info["port"]])
                    stack.extend(sent_ports)
                    info["stack"] = stack
                    info["port"] = stack[0]
                    info["ports"] = list(dict.fromkeys(stack))
                    info["time"] = now
                    info["velocity"] = note_msg.velocity
                    info["voices"] = w
                    self._last_key_ports[key] = info["ports"]
                else:
                    self.active[key] = {
                        "port": primary,
                        "ports": sent_ports,
                        "stack": list(sent_ports),
                        "time": now,
                        "velocity": note_msg.velocity,
                        "voices": w,
                        "strum_pending": bool(
                            self.anima and self._anima_should_strum(note_msg.channel & 0x0F)
                        ),
                    }
                    self._last_key_ports[key] = sent_ports

                total_now = sum(self.voice_counts)
                if total_now > self.peak_voices:
                    self.peak_voices = total_now
            else:
                # Note Off — one off pops one stacked on on that port.
                info = self.active.get(key)
                if info is not None:
                    stack = list(info.get("stack") or info.get("ports") or [info["port"]])
                    port_off = stack.pop(0) if stack else (info.get("port") or 0)
                    ports = [port_off]
                    info["stack"] = stack
                    if stack:
                        info["port"] = stack[0]
                        info["ports"] = list(dict.fromkeys(stack))
                        self._last_key_ports[key] = info["ports"]
                    else:
                        self.active.pop(key, None)
                    ch_off = msg.channel & 0x0F
                    # If the matching on is still in the strum queue, drop it
                    # and do not send an off (the synth never saw the on).
                    cancelled = False
                    if self.anima:
                        cancelled = self._anima_strum_cancel(ch_off, msg.note)
                    hold = 0.0 if cancelled else (
                        self._anima_strum_off_hold[ch_off] if self.anima else 0.0
                    )
                    if not cancelled:
                        for port in ports:
                            if hold > 0:
                                self._anima_strum_q.append((now + hold, port, msg))
                            else:
                                self._send_routed(port, msg)
                    w = int(info.get("voices") or 1)
                    for port in ports:
                        self.voice_counts[port] = max(0, self.voice_counts[port] - w)
                    if self.anima:
                        still_held = key in self.active
                        if not still_held:
                            self._anima_mod_on.discard(key)
                            self._anima_ghost_kill(key)
                            self._anima_family_rehome()
                        self._anima_ghost_release_pitch(ch_off, msg.note)
                        ch = msg.channel & 0x0F
                        on_t = self._anima_last_on[ch]
                        if on_t:
                            self._anima_last_dur[ch] = time.monotonic() - on_t
                        if self._anima_strum_buf[ch] is not None:
                            self._anima_strum_flush(ch, immediate=True)
                            self._anima_strum_drain()
                        still = any(k[0] == ch for k in self.active)
                        if not still:
                            self._anima_idle_t[ch] = time.monotonic()
                            self._anima_efx_flush_pending(ch)
                            self._anima_efx_guitar_upkeep(ch)
                else:
                    # Unknown off — do not broadcast to every port (that
                    # was leaving phantom offs on the unit that never
                    # played the note). Cancel a queued on if present.
                    ch_off = msg.channel & 0x0F
                    if self.anima and self._anima_strum_cancel(ch_off, msg.note):
                        pass
                    else:
                        ports = self._last_key_ports.get(key)
                        if ports:
                            for p in ports:
                                self._send_routed(p, msg)
                        else:
                            pin = self._anima_ch_port.get(ch_off) if self.anima else None
                            if pin is not None:
                                self._send_routed(pin, msg)

                # Only resync if the drift is significant
                if abs(sum(self.voice_counts) - len(self.active)) > 1:
                    self._resync_voice_counts()

            return

        if self._is_panic(msg):
            self.panic(reason=f"received {msg}")
            return

        # SysEx → detect format, describe it, show in status, and forward
        if msg.type == "sysex":
            if self._is_init_reset_sysex(msg):
                self._init_dump_begin("reset")
                self._gs_reset_part_rx()
            self._gs_observe_part_dt1(msg)
            self._init_dump_touch(msg)
            self._voodoo_on_mt32_sysex(msg)
            self._detect_format(msg)
            self._voodoo_maybe_auto()
            dump = self._init_dump
            description = "" if dump else self._describe_sysex(msg)
            if dump:
                # State only — no describe / status / history. Bytes already
                # on the wire. Anima needs the file's EFX + rhythm map.
                if self.anima:
                    self._anima_observe_file_efx(msg, "", quiet=True)
                    self._anima_observe_rhythm(msg, quiet=True)
            else:
                if description == "GS Reset" or (description and description.startswith("GS Reset")):
                    self._anima_gs_map_home("GS Reset")
                self._anima_observe_sysex(msg, description)
                self._anima_observe_file_efx(msg, description)
                self._anima_observe_rhythm(msg)
                # Suppress pure noise
                if description in (
                    "GS SysEx", "SysEx", "GM/Universal SysEx", "XG SysEx", "MT-32 SysEx",
                    "SC-ext SysEx", "SC-ext bulk SysEx",
                ):
                    # Only show the generic message if history is empty
                    if not self.status_history and not self.status_message:
                        self._set_status(description, duration=2.5)
                else:
                    self._set_status(description, duration=3.5)

            # Route SysEx: Crucible affinity, Alchemy translate / overflow / fanout
            if self.alchemy_all:
                targets = [i for i in range(self.n_ports) if self._port_has_alchemy_target(i)]
            elif self.crucible:
                targets = [
                    i for i in range(self.n_ports)
                    if self._port_matches_format(i, self.detected_format)
                ]
                if self.alchemy:
                    for i in self._overflow_note_ports():
                        if i not in targets:
                            targets.append(i)
                    if not targets:
                        targets = self._overflow_note_ports()
            elif self.alchemy:
                targets = [i for i in range(self.n_ports) if self._port_has_alchemy_target(i)]
            else:
                targets = list(range(self.n_ports))

            kind = self._gs_file_efx_kind(msg)
            if kind and self.anima and self._anima_file_efx_home is not None:
                home = self._anima_file_efx_home
                parked = [p["port"] for p in self._anima_file_park]
                if kind == "type":
                    targets = [home]
                elif kind == "param":
                    targets = [home]
                elif kind == "part":
                    targets = [home]
            data = list(msg.data)
            gm_on = (
                self.anima
                and len(data) >= 4
                and data[0] == 0x7E
                and data[2] == 0x09
                and data[3] in (0x01, 0x03)
            )
            gs_reset = self._gs_dt1([0x40, 0x00, 0x7F], [0x00]) if gm_on else None
            xg_on = (
                mido.Message("sysex", data=[0x43, 0x10, 0x4C, 0x00, 0x00, 0x7E, 0x00])
                if gm_on else None
            )
            n_gs = n_xg = 0
            for i in targets:
                tags = {str(x).lower() for x in self.out_formats[i]}
                if gm_on and tags & {"gs", "gs55", "gs88", "gs88pro", "gs8850", "gs8820", "sc", "sc-8850", "sc8850"}:
                    self._send_routed(i, gs_reset)
                    n_gs += 1
                elif gm_on and tags & {"xg"}:
                    self._send_routed(i, xg_on)
                    n_xg += 1
                else:
                    # 88Pro vel-offset at 40 1x 16 is Key Shift on 8820/8850
                    rewritten = None
                    cls = self._gs_canvas_class(tags)
                    # Only 8820/8850 rewrite 40 1x 16. 88Pro gets the file unchanged.
                    if cls == "8850":
                        rewritten = self._gs_8850_compat(msg, cls=cls)
                    if rewritten:
                        for m in rewritten:
                            self._send_routed(i, m)
                    else:
                        self._send_routed(i, msg)
            if n_gs:
                self._anima_gs_map_home("GM On → GS Reset")
                self._anima_feedback(
                    "tone",
                    f"GM On → GS Reset ({n_gs} port(s))",
                    status=True,
                )
            if n_xg:
                self._anima_feedback(
                    "tone",
                    f"GM On → XG On ({n_xg} port(s))",
                    status=True,
                )

            return

        # Track common controllers per channel + timestamp
        # Bank select for Alchemy program mapping
        if msg.type in ("control_change", "program_change"):
            self._init_dump_touch(msg)
        if msg.type == "control_change":
            if msg.control == 0:
                ch = msg.channel & 0x0F
                prev = self._anima_pend_bank[ch] or (
                    self.bank_msb[ch], self.bank_lsb[ch]
                )
                self._anima_pend_bank[ch] = (msg.value & 0x7F, prev[1])
                pc = int(self._file_pc[ch]) & 0x7F
                cc0, cc32 = self._anima_pend_bank[ch]
                if anima_combo_ok(cc0, self._anima_file_map(cc0, cc32), pc):
                    self.bank_msb[ch] = cc0
                    self.bank_lsb[ch] = cc32
                    self._anima_pend_bank[ch] = None
                self._anima_seen_cc0[ch] = True
                self._anima_cm64_restore_pc(msg)
            elif msg.control == 32:
                ch = msg.channel & 0x0F
                prev = self._anima_pend_bank[ch] or (
                    self.bank_msb[ch], self.bank_lsb[ch]
                )
                self._anima_pend_bank[ch] = (prev[0], msg.value & 0x7F)
                pc = int(self._file_pc[ch]) & 0x7F
                cc0, cc32 = self._anima_pend_bank[ch]
                if anima_combo_ok(cc0, self._anima_file_map(cc0, cc32), pc):
                    self.bank_msb[ch] = cc0
                    self.bank_lsb[ch] = cc32
                    self._anima_pend_bank[ch] = None
                self._anima_seen_cc32[ch] = True
                self._anima_cm64_restore_pc(msg)

        # Input-side log for patch path (OUT lines still show per-port result)
        if self._log_file is not None and msg.type in (
            "program_change", "control_change", "sysex"
        ):
            if msg.type != "control_change" or msg.control in (
                0, 32, 7, 10, 11, 91, 93, 64, 1, 98, 99, 100, 101, 6, 38
            ):
                self._log_msg(None, msg)

        now = time.monotonic()
        if msg.type == "control_change":
            ch = msg.channel
            if msg.control == 7:       # Volume
                self._file_vol[ch] = msg.value
                if self._anima_organ_rotary_ch(ch):
                    lifted = self._anima_organ_vol_gain(msg.value)
                    if lifted != msg.value:
                        try:
                            msg = msg.copy(value=lifted)
                        except Exception:
                            msg = mido.Message(
                                "control_change", channel=ch, control=7, value=lifted
                            )
                        self._anima_feedback(
                            "efx",
                            f"ch{ch + 1} organ CC7 {self._file_vol[ch]}→{lifted} (file)",
                            status=False,
                        )
                self.vol[ch] = msg.value
                self.vol_time[ch] = now
            elif msg.control == 10:    # Pan
                self.pan[ch] = msg.value
                self.pan_time[ch] = now
                if self.anima:
                    self._anima_efx_follow_pan(ch)
            elif msg.control == 1:     # Mod Wheel
                self.mod[ch] = msg.value
                self.mod_time[ch] = now

        elif msg.type == "pitchwheel":
            ch = msg.channel
            self.pitch[ch] = round(msg.pitch / 128)
            self.pitch_time[ch] = now

        # Voodoo: ch10 kit select consumes PC (sends MTR kit SysEx instead)
        if msg.type == "program_change" and self._voodoo_rhythm_pc(msg):
            return

        # Auto Voodoo when format becomes non-MT-32 on mt32-only setups
        if msg.type == "program_change":
            self._voodoo_maybe_auto()

        # Everything else (CC, PC, pitch, …): same destination policy as SysEx
        # --alchemy-all fans out to all GS/XG-capable outs with per-port translate.
        # Phase V2: when Voodoo multi-map is active, channel-owned ports win.
        voodoo_ports = None
        if msg.type in ("control_change", "program_change", "pitchwheel",
                        "aftertouch", "polytouch"):
            voodoo_ports = self._voodoo_ports_for_channel(msg.channel)

        if voodoo_ports is not None:
            targets = list(voodoo_ports)
        elif self.alchemy_all:
            targets = [i for i in range(self.n_ports) if self._port_has_alchemy_target(i)]
        elif self.crucible:
            targets = [
                i for i in range(self.n_ports)
                if self._port_matches_format(i, self.detected_format)
            ]
            if self.alchemy:
                for i in self._overflow_note_ports():
                    if i not in targets:
                        targets.append(i)
        elif self.alchemy:
            targets = [i for i in range(self.n_ports) if self._port_has_alchemy_target(i)]
        else:
            targets = list(range(self.n_ports))

        # File CC00/CC32: send now if the combo exists on the sounding PC.
        # Otherwise hold — Piano+CC00=32 after GS Reset is empty until the
        # real PC arrives and the file_banked path emits LSB+MSB+PC.
        if (
            self.anima
            and msg.type == "control_change"
            and msg.control in (0, 32)
            and not self._anima_is_rhythm(msg.channel)
        ):
            ch = msg.channel & 0x0F
            pc = int(self._file_pc[ch]) & 0x7F
            pend = self._anima_pend_bank[ch]
            if pend:
                cc0, cc32 = pend
            else:
                cc0 = int(self.bank_msb[ch]) & 0x7F
                cc32 = int(self.bank_lsb[ch]) & 0x7F
            ok = anima_combo_ok(cc0, self._anima_file_map(cc0, cc32), pc)
            for i in targets:
                if not self._should_send(i, msg):
                    continue
                if self._anima_port_8850(i) and not ok:
                    continue
                self._send_routed(i, msg)
            return

        file_banked = False
        if msg.type == "program_change":
            ch = msg.channel & 0x0F
            pend = getattr(self, "_anima_pend_bank", [None]*16)[ch]
            msb = int((pend[0] if pend else self.bank_msb[ch])) & 0x7F
            lsb = int((pend[1] if pend else self.bank_lsb[ch])) & 0x7F
            fmt = (getattr(self, "detected_format", None) or "").upper()
            gs = fmt in ("GS", "SC", "SC-8850")
            seen = bool(self._anima_seen_cc0[ch] or self._anima_seen_cc32[ch])
            # File named the bank (including 0/0 after GS Reset, or map 1–3).
            file_banked = (msb != 0) or (lsb in (1, 2, 3)) or (gs and seen)
        # GM scene pads often send CC0=0 without a new PC. Forwarding that
        # wipes the 8850 variation Anima just chose. Hold the slot.
        if (
            self.anima
            and msg.type == "control_change"
            and msg.control in (0, 32)
            and msg.value == 0
        ):
            ch = msg.channel & 0x0F
            slot = self._anima_tone_slot[ch]
            if slot and slot[0] != 0 and not self._anima_is_rhythm(ch):
                for i in targets:
                    if not self._should_send(i, msg):
                        continue
                    if not self._anima_port_8850(i):
                        self._send_routed(i, msg)
                        continue
                    self._send_routed(i, mido.Message("control_change", channel=ch, control=32, value=slot[1]))
                    self._send_routed(i, mido.Message("control_change", channel=ch, control=0, value=slot[0]))
                self._anima_feedback(
                    "tone",
                    f"hold ch{ch + 1} CC00={slot[0]:03d} (file CC0=0 ignored)",
                    status=False,
                )
                return

        for i in targets:
            if not self._should_send(i, msg):
                continue
            if (
                self.anima
                and msg.type == "control_change"
                and msg.control in (7, 10, 11)
                and i < len(getattr(self, "_anima_foley_ch", []) or [])
                and self._anima_foley_ch[i] is not None
                and (msg.channel & 0x0F) == self._anima_foley_ch[i]
            ):
                continue
            if (
                self.anima
                and msg.type == "program_change"
                and not file_banked
                and not self._anima_is_rhythm(msg.channel)
                and self._anima_port_8850(i)
            ):
                ch = msg.channel & 0x0F
                slot = self._anima_tone_pick(ch, msg.program)
                adapted = self._anima_adapt_tone_slot(i, slot)
                if not adapted:
                    continue
                cc0, cc32, pc_out = adapted
                # Map first. 126/127 is only valid after SC-55 (CC32=1) on 8850.
                self._send_routed(i, mido.Message("control_change", channel=ch, control=32, value=cc32))
                self._send_routed(i, mido.Message("control_change", channel=ch, control=0, value=cc0))
                self._send_routed(i, mido.Message("program_change", channel=ch, program=pc_out))
                self._anima_feedback(
                    "tone",
                    f"tone ch{ch + 1} GM{msg.program + 1} → CC00={cc0:03d} map{cc32} PC{pc_out + 1}",
                    status=True,
                )
                continue
            if (
                self.anima
                and msg.type == "program_change"
                and file_banked
                and not self._anima_is_rhythm(msg.channel)
                and self._anima_port_8850(i)
            ):
                ch = msg.channel & 0x0F
                pend = self._anima_pend_bank[ch]
                if pend:
                    cc0, raw32 = pend
                    self._anima_pend_bank[ch] = None
                else:
                    cc0 = int(self.bank_msb[ch]) & 0x7F
                    raw32 = int(self.bank_lsb[ch]) & 0x7F
                cc32 = self._anima_file_map(cc0, raw32)
                pc = msg.program & 0x7F
                emit0, emit32 = cc0, cc32
                if not anima_combo_ok(cc0, cc32, pc):
                    # Hole for THIS pc only. Keep the file bank pending so
                    # the next PC (Strings+32) is still honored.
                    emit0, emit32 = 0, 0
                    self._anima_pend_bank[ch] = (cc0, raw32)
                    self._anima_feedback(
                        "tone",
                        f"file ch{ch + 1} empty combo → capital PC{pc + 1} (bank {cc0} held)",
                        status=False,
                    )
                else:
                    self.bank_msb[ch] = cc0
                    self.bank_lsb[ch] = cc32
                    self._anima_pend_bank[ch] = None
                adapted = self._anima_adapt_tone_slot(i, (emit0, emit32, pc))
                if not adapted:
                    continue
                cc0, cc32, pc = adapted
                self._anima_cm64[ch] = False
                self._anima_tone_slot[ch] = None
                self._send_routed(i, mido.Message("control_change", channel=ch, control=32, value=cc32))
                self._send_routed(i, mido.Message("control_change", channel=ch, control=0, value=cc0))
                self._send_routed(i, mido.Message("program_change", channel=ch, program=pc))
                self._anima_feedback(
                    "tone",
                    f"file ch{ch + 1} CC00={cc0:03d} map{cc32} PC{pc + 1}",
                    status=False,
                )
                continue
            self._send_routed(i, msg)

    def _is_panic(self, msg: mido.Message) -> bool:
        if msg.type == "control_change" and msg.control in (120, 123):
            return True
        if msg.type == "reset":
            return True
        return False

    def panic(self, reason: str = "manual"):
        """Silence all outs. Never raises — dead/closed ports are skipped."""
        for i, out in enumerate(self.outs):
            try:
                out.panic()
            except Exception:
                # Try reconnect once so panic can still reach a revived device
                if self._try_reconnect_out(i, force=True):
                    try:
                        self.outs[i].panic()
                    except Exception:
                        pass
            for ch in range(16):
                try:
                    self.outs[i].send(
                        mido.Message("control_change", channel=ch, control=123, value=0)
                    )
                    self.outs[i].send(
                        mido.Message("control_change", channel=ch, control=121, value=0)
                    )
                except Exception:
                    break  # port is gone; skip remaining channels
        self._anima_ghosts = {}
        self._anima_ghost_sound = {}
        self._anima_wave_sub_armed = set()
        self._anima_wave_sub_saved = {}
        self._anima_fam_ghost = {}
        self._anima_bass_sub_choice = None
        self.active.clear()
        self.voice_counts = [0] * self.n_ports
        self._anima_settle_q = []
        self._anima_settle_on = {}
        self._anima_efx_settle = [0.0] * self.n_ports
        self._anima_settle_bypass = False
        self.last_chord_port = None
        self.last_sent.clear()
        self._send_queue.clear()
        try:
            self._set_status(f"PANIC ({reason}) – all devices silenced", duration=6.0)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Status panel
    # ------------------------------------------------------------------
    def _make_status_panel(self) -> Panel:
        counts = self.voice_counts
        total = sum(counts)

        # Voices per MIDI channel (8850 weight when known, else 1)
        channel_counts = [0] * 16
        for key, info in self.active.items():
            ch = key[0]
            w = int(info.get("voices") or 1)
            channel_counts[ch] += w
        for key, ghosts in (self._anima_ghosts or {}).items():
            for item in ghosts:
                gch = item[1]
                w = item[3] if len(item) > 3 else 1
                if 0 <= gch < 16:
                    channel_counts[gch] += int(w or 1)

        # Dynamic bar width – make bars longer so they align better with Channel Activity
        term_width = console.width or 80
        # Label (~16) + nums (~8) + padding/borders; tags need extra room
        bar_width = max(20, term_width - 34)

        # Overall utilisation
        total_limit = sum(self.poly_limits) or 1
        util_pct = int((total / total_limit) * 100)

        # Last activity (with minutes)
        if self.last_note_time == 0:
            last_activity = "—"
        else:
            ago = time.monotonic() - self.last_note_time
            if ago < 0.05:
                last_activity = "now"
            elif ago < 60:
                last_activity = f"{ago:.1f}s ago"
            else:
                mins = int(ago // 60)
                last_activity = f"{mins}m ago"

        # Activity pulse – fixed 3-character footprint (♪ / ♫ ladder)
        #   idle ♪ → light ♪ → medium ♫ → busy ♫♪ → busy+ ♫♪♪
        #   → warm ♫♫ → hot ♫♫♪ → peak ♫♫♫
        ago_act = time.monotonic() - self.last_activity_time
        util_now = total / total_limit if total_limit else 0.0
        chord = self.current_chord_size

        if ago_act >= 0.40:
            pulse = " [dim]♪  [/]"                          # idle
        elif ago_act >= 0.22:
            pulse = " [green]♪  [/]"                        # light
        elif chord >= 10 or util_now >= 0.90:
            pulse = " [bold bright_green]♫♫♫[/]"            # peak
        elif chord >= 7 or util_now >= 0.75:
            pulse = " [bold bright_green]♫♫♪[/]"            # hot
        elif chord >= 5 or util_now >= 0.55:
            pulse = " [bold bright_green]♫♫ [/]"            # warm
        elif chord >= 4 or util_now >= 0.40:
            pulse = " [bold green]♫♪♪[/]"                   # busy+
        elif chord >= 2 or ago_act < 0.10:
            pulse = " [bold green]♫♪ [/]"                   # busy
        elif ago_act < 0.18 or util_now >= 0.15:
            pulse = " [green]♫  [/]"                        # medium
        else:
            pulse = " [green]♪  [/]"                        # light

        # Format badge – fixed width so counters don't shift ([MT-32] is longest)
        colours = {
            "GM": "bright_cyan",
            "GM2": "bright_cyan",
            "GS": "bright_magenta",
            "XG": "bright_yellow",
            "MT-32": "bright_red",
        }
        if self.detected_format:
            col = colours.get(self.detected_format, "white")
            # [GS] or [GS*] when locked (* = format lock via L)
            core = self.detected_format
            label = f"[{core}*]" if self.format_locked else f"[{core}]"
            # Pad to 8 visible chars so [MT-32*] still fits without shifting header
            pad = " " * max(0, 8 - len(label))
            if time.monotonic() < self.format_pulse_time or self.format_locked:
                format_badge = f" [bold {col}]{label}[/]{pad}"
            else:
                format_badge = f" [dim]{label}[/]{pad}"
        else:
            format_badge = " " * 9

        # If the bottom status message has just expired, move it into history
        now = time.monotonic()
        if self.status_message and now >= self.status_message_time:
            self.status_history.insert(0, (now, self.status_message))
            self.status_history = self.status_history[: self.STATUS_HISTORY_MAX]
            self.status_message = ""

        # --- Port bars ---
        table = Table(show_header=False, box=None, padding=(0, 1), expand=True)
        table.add_column("label", style="cyan", width=16, no_wrap=True)  # room for format tags
        table.add_column("bar", ratio=1, no_wrap=True)
        table.add_column("nums", justify="right", width=8, no_wrap=True)

        for i, (name, count, limit) in enumerate(zip(self.port_names, counts, self.poly_limits)):
            # Clamp count so we never exceed the visual limit
            display_count = min(count, limit)
            current_pct = display_count / limit if limit else 0.0

            # Peak hold + decay
            if current_pct > self.port_peaks[i]:
                self.port_peaks[i] = current_pct
            else:
                self.port_peaks[i] = max(current_pct, self.port_peaks[i] - 0.018)

            # Safe bar construction
            filled = min(int(current_pct * bar_width), bar_width)
            peak_pos = min(int(self.port_peaks[i] * bar_width), bar_width - 1)

            bar_chars = ["░"] * bar_width
            for j in range(filled):
                bar_chars[j] = "█"

            if 0 <= peak_pos < bar_width:
                bar_chars[peak_pos] = "┃"

            # Colour
            if current_pct >= 0.9:
                colour = "red"
            elif current_pct >= 0.7:
                colour = "yellow"
            else:
                colour = "green"

            # Build final bar with bright peak marker
            if 0 <= peak_pos < bar_width:
                bar = Text.from_markup(
                    f"[{colour}]{''.join(bar_chars[:peak_pos])}[/]"
                    f"[bold bright_white]┃[/]"
                    f"[{colour}]{''.join(bar_chars[peak_pos+1:])}[/]"
                )
            else:
                bar = Text("".join(bar_chars), style=colour)

            tags = self.out_formats[i]
            if tags and "any" not in tags:
                label = f"Port {i+1} [{format_tags_label(tags)}]"
            else:
                label = f"Port {i+1}"
            table.add_row(
                label,
                bar,
                f"{count}/{limit}",
            )

        # --- Channel Activity + Controllers ---
        HIGHLIGHT_SEC = 1.5  # how long a value stays bright after changing
        now = time.monotonic()

        # Build each row as a list of 3-character fields
        ch_num_parts = []
        voice_parts = []
        vol_parts = []
        pan_parts = []
        mod_parts = []
        pitch_parts = []

        for i in range(16):
            voices = channel_counts[i]

            # --- Lingering Voice Count (VU-style) ---
            if voices > self.voice_display[i]:
                self.voice_display[i] = float(voices)
            else:
                # Decay speed – adjust 0.15–0.25 to taste
                self.voice_display[i] = max(float(voices), self.voice_display[i] - 0.18)

            display_voices = int(round(self.voice_display[i]))

            # MIDI Channel number (stays realtime)
            if voices > 0:
                ch_num_parts.append(f"[bold]{i+1:2d}[/] ")
            else:
                ch_num_parts.append(f"[dim]{i+1:2d}[/] ")

            # Voice Count – two-stage colour (more obvious)
            if display_voices == 0:
                voice_parts.append(f"[dim]{display_voices:2d}[/] ")
            elif voices > 0:
                # Currently active → bright blue
                voice_parts.append(f"[bold bright_blue]{display_voices:2d}[/] ")
            else:
                # Lingering → distinct fade color
                voice_parts.append(f"[bold dark_blue]{display_voices:2d}[/] ")

            # Volume
            if self.vol[i] is None:
                vol_str = " - "
            else:
                vol_str = f"{self.vol[i]:3d}"

            if now - self.vol_time[i] < HIGHLIGHT_SEC:
                vol_parts.append(f"[bold]{vol_str}[/]")
            else:
                vol_parts.append(f"[dim]{vol_str}[/]")

            # Pan
            if self.pan[i] is None:
                pan_str = " - "
            else:
                p = self.pan[i]
                if p == 64:
                    pan_str = " C "
                elif p < 64:
                    pan_str = f"L{64 - p:2d}"
                else:
                    pan_str = f"R{p - 64:2d}"

            if now - self.pan_time[i] < HIGHLIGHT_SEC:
                pan_parts.append(f"[bold]{pan_str}[/]")
            else:
                pan_parts.append(f"[dim]{pan_str}[/]")

            # Mod
            if self.mod[i] is None:
                mod_str = " - "
            else:
                mod_str = f"{self.mod[i]:3d}" if self.mod[i] != 0 else " 0 "

            if now - self.mod_time[i] < HIGHLIGHT_SEC:
                mod_parts.append(f"[bold]{mod_str}[/]")
            else:
                mod_parts.append(f"[dim]{mod_str}[/]")

            # Pitch
            if self.pitch[i] is None:
                pb_str = " - "
            else:
                pb = self.pitch[i]
                if pb == 0:
                    pb_str = " 0 "
                elif pb > 0:
                    pb_str = f"+{pb:2d}"
                else:
                    pb_str = f"{pb:3d}"

            if now - self.pitch_time[i] < HIGHLIGHT_SEC:
                pitch_parts.append(f"[bold]{pb_str}[/]")
            else:
                pitch_parts.append(f"[dim]{pb_str}[/]")

        # Join with a single space between columns
        sep = " "

        channel_table = Table(show_header=False, box=None, padding=(0, 0), expand=True)
        channel_table.add_column("label", style="cyan", width=14, no_wrap=True)
        channel_table.add_column("values", ratio=1)
        channel_table.add_row("MIDI Channel", Text.from_markup(sep.join(ch_num_parts)))
        channel_table.add_row("Voice Count",  Text.from_markup(sep.join(voice_parts)))
        channel_table.add_row("Vol",          Text.from_markup(sep.join(vol_parts)))
        channel_table.add_row("Pan",          Text.from_markup(sep.join(pan_parts)))
        channel_table.add_row("Mod",          Text.from_markup(sep.join(mod_parts)))
        channel_table.add_row("Pitch",        Text.from_markup(sep.join(pitch_parts)))

        # Mode badges – fixed-width slots so the header never shifts when one appears
        if self.crucible:
            badge_crucible = " [bold bright_cyan][Crucible][/]"
        else:
            badge_crucible = " " * 11  # len(" [Crucible]")
        if self.alchemy:
            badge_alchemy = " [bold bright_yellow][Alchemy][/]"
        else:
            badge_alchemy = " " * 10  # len(" [Alchemy]")
        if self.scpop_mode:
            badge_scpop = " [bold bright_green][SCPOP][/]"
        else:
            badge_scpop = " " * 8  # len(" [SCPOP]")
        if self.anima:
            seed = self._anima_ensure_efx_seed() if self._anima_efx_seed is None else self._anima_efx_seed
            if seed is None:
                badge_anima = " [bold magenta][Anima][/]"
            elif self._anima_seed_locked:
                badge_anima = f" [bold magenta][Anima {seed:04X}*][/]"
            else:
                badge_anima = f" [bold magenta][Anima {seed:04X}][/]"
        else:
            badge_anima = ""
        if self.voodoo_loading:
            badge_voodoo = " [bold bright_red][Voodoo…][/]"
        elif self.voodoo_catchup:
            badge_voodoo = " [bold yellow][Voodoo↑][/]"
        elif self.voodoo_active:
            badge_voodoo = " [bold bright_red][Voodoo][/]"
        else:
            badge_voodoo = " " * 10  # len(" [Voodoo…]") approx
        mode_badges = f"{badge_crucible}{badge_alchemy}{badge_scpop}{badge_anima}{badge_voodoo}"

        # Header: pulse + fixed badges + core counters only (no Drops/Steals/Filtered)
        header = Text.from_markup(
            f"{pulse}{mode_badges}{format_badge} • "
            f"Total: [bold]{total:3d}[/] • Peak: [bold]{self.peak_voices:3d}[/] • "
            f"Util: [bold]{util_pct:2d}%"
        )

        # Chord / activity line (used under More Stats)
        if self.last_chord_port is not None:
            chord_text = (
                f"Last Chord Size: {self.current_chord_size} "
                f"(Peak {self.peak_chord_size}) → Port {self.last_chord_port + 1}"
            )
        else:
            chord_text = f"Last Chord Size: {self.current_chord_size} (Peak {self.peak_chord_size})"

        # Narrow-terminal footer still stacks chord + activity
        footer = Text.from_markup(
            f"[dim]Drops: {self.drop_count} • Steals: {self.steal_count} • "
            f"Filtered: {self.filtered_count}\n"
            f"{chord_text}   Last Activity: {last_activity}[/]"
        )

        # Status message row (auto-clears)
        status_line = Text("")
        if self.status_message and time.monotonic() < self.status_message_time:
            status_line = Text.from_markup(f"[bold yellow]{escape(self.status_message)}[/]")
        else:
            self.status_message = ""

        # --- Rolling status history (right side) ---
        history_text = self._make_status_history()

        term_width = console.width or 80
        use_side_history = term_width >= 118

        if use_side_history:
            # Combine channel table + labelled footer + status into one left column
            left_column = Table(show_header=False, box=None, padding=(0, 0), expand=True)
            left_column.add_column("content", ratio=1)

            # 1. Channel activity block
            left_column.add_row(channel_table)

            # 2. More Stats – Drops / Steals / Filtered (moved off the header)
            footer_row = Text.from_markup(
                f"[cyan]More Stats:[/]    [dim]Drops: {self.drop_count} • "
                f"Steals: {self.steal_count} • Filtered: {self.filtered_count}[/]"
            )
            left_column.add_row(footer_row)

            # 3. Chord / activity – no label, aligned under the More Stats values
            detail_row = Text.from_markup(
                f"               [dim]{chord_text}  Last Activity: {last_activity}[/]"
            )
            left_column.add_row(detail_row)

            # 4. Labelled status message (can wrap)
            if self.status_message and time.monotonic() < self.status_message_time:
                status_row = Text.from_markup(
                    f"[cyan]Status Message:[/]   [bold yellow]{escape(self.status_message)}[/]"
                )
            else:
                status_row = Text.from_markup("[cyan]Status Message:[/]   [dim]—[/]")
                self.status_message = ""
            left_column.add_row(status_row)

            # History panel – height 10 matches the taller left column (+1 for detail row)
            history_panel = Panel(
                history_text if str(history_text).strip() else Text(" "),
                border_style="bright_blue",
                padding=(0, 0),
                height=10,
                title="[dim]Recent Status Messages[/]",
                title_align="left",
            )

            side_by_side = Table(show_header=False, box=None, padding=(0, 1), expand=True)
            side_by_side.add_column("left", ratio=3)
            side_by_side.add_column("history", width=32, no_wrap=False)
            side_by_side.add_row(left_column, history_panel)

            content = Group(header, table, side_by_side)
        else:
            # Narrow terminal – original stacked layout
            content = Group(header, table, channel_table, footer, status_line)

        return Panel(
            content,
            title=f"[bold magenta]Duality v{VERSION}[/]",
            border_style="bright_blue",
            padding=(0, 1),
        )

    def _handle_hotkey(self, ch: str) -> None:
        """Dispatch a single hotkey character."""
        c = ch.lower()
        if c == "f":
            self._clear_format("hotkey")
        elif c == "g":
            # Cycle GM ↔ GM2 on repeated G
            if self.detected_format == "GM":
                self._force_format("GM2", "hotkey G")
            else:
                self._force_format("GM", "hotkey G")
        elif c == "r":
            # GS today; future multi-press can cycle GS → SC
            self._force_format("GS", "hotkey R")
        elif c == "y":
            self._force_format("XG", "hotkey Y")
        elif c == "m":
            # First press: set format MT-32. Second press while already MT-32: enter Voodoo.
            if self.detected_format == "MT-32" and not (
                self.voodoo_active or self.voodoo_loading or self.voodoo_catchup
            ):
                self._voodoo_begin("hotkey M")
            elif self.voodoo_active or self.voodoo_loading or self.voodoo_catchup:
                self._voodoo_exit("hotkey M")
                self._force_format("MT-32", "hotkey M")
            else:
                self._force_format("MT-32", "hotkey M")
        elif c == "v":
            # Cycle Voodoo bank and reload when Voodoo is engaged
            names = list(VOODOO_BANK_NAMES) if _VOODOO_BANKS else ["mtgm"]
            try:
                i = names.index(self.voodoo_bank)
            except ValueError:
                i = 0
            self.voodoo_bank = names[(i + 1) % len(names)]
            label = bank_label(self.voodoo_bank)
            if self.voodoo_active or self.voodoo_loading or self.voodoo_catchup:
                self._set_status(f"Voodoo bank → {label} (reloading…)", duration=3.0)
                self._voodoo_begin(f"bank → {self.voodoo_bank}")
            else:
                self._set_status(
                    f"Voodoo bank → {label} (load with M / --voodoo)",
                    duration=3.0,
                )
        elif c == "p":
            # Voodoo layout: stripe ↔ pairs (4+ even :mt32 units only)
            self._voodoo_toggle_layout()
        elif c == "b":
            # Toggle note assignment strategy (balance ↔ round-robin)
            self.mode = "rr" if self.mode == "balance" else "balance"
            self._set_status(f"Mode → {self.mode}", duration=2.5)
        elif c == "x":
            self._send_format_resets("hotkey X")
        elif c == "c":
            self._clear_log()
        elif c == "l":
            self._toggle_format_lock()
        elif c == "s":
            self._anima_toggle_seed_lock()
        elif c == "w":
            if self._rec_on or self._rec_wanted:
                self._rec_wanted = False
                self._record_stop("hotkey W")
            else:
                if not self.record_dir:
                    self.record_dir = "."
                self._rec_wanted = True
                self._record_start("hotkey W")
        elif c == "a":
            # off → normal → game → off
            if not self.anima:
                self.anima = True
                self.anima_game = False
            elif not self.anima_game:
                self.anima_game = True
            else:
                self.anima = False
                self.anima_game = False
            self._anima_release_efx_lock("Anima toggle")
            if not self.anima:
                self._anima_ghost_kill_all()
                # Park wheels we were driving so A/B compare is clean
                for ch in range(16):
                    if self._anima_mod_ch[ch] or self._anima_cc1_cur[ch]:
                        ports = self._anima_live_ports(ch) or self._anima_ports[ch]
                        if ports:
                            self._anima_send_cc(ports, ch, 1, 0)
                    self._anima_cc1_tgt[ch] = 0
                    self._anima_cc1_cur[ch] = 0
                    self._anima_mod_ch[ch] = False
                self._anima_mod_on.clear()
                self._set_status("Anima OFF", duration=2.5)
                self._log_line("ANIMA off (hotkey A)")
            else:
                self._anima_ramp_t = time.monotonic()
                mode = "game" if self.anima_game else "normal"
                self._set_status(f"Anima ON ({mode})", duration=2.5)
                self._log_line(f"ANIMA on {mode} (hotkey A)")
        elif c == "q":
            self._set_status("Quit requested – panicking and exiting…", duration=2.0)
            self.panic(reason="hotkey Q")
            self.close()
            sys.exit(0)

    def _hotkey_tty_setup(self) -> None:
        """Unix: cbreak so hotkeys do not wait for Enter. No-op on Windows / pipes."""
        self._tty_old = None
        self._tty_fd = None
        if os.name == "nt":
            return
        try:
            if not sys.stdin.isatty():
                return
            import termios
            import tty
            fd = sys.stdin.fileno()
            self._tty_old = termios.tcgetattr(fd)
            self._tty_fd = fd
            tty.setcbreak(fd)
        except Exception:
            self._tty_old = None
            self._tty_fd = None

    def _hotkey_tty_restore(self) -> None:
        old = getattr(self, "_tty_old", None)
        fd = getattr(self, "_tty_fd", None)
        if old is None or fd is None:
            return
        try:
            import termios
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        except Exception:
            pass
        self._tty_old = None
        self._tty_fd = None

    def _poll_hotkeys(self) -> None:
        """Non-blocking keyboard poll for format / control hotkeys."""
        try:
            import msvcrt  # Windows
            while msvcrt.kbhit():
                ch = msvcrt.getwch()
                if ch:
                    self._handle_hotkey(ch)
            return
        except ImportError:
            pass
        # Unix: cbreak stdin (see _hotkey_tty_setup)
        try:
            import select
            if not sys.stdin.isatty():
                return
            while select.select([sys.stdin], [], [], 0)[0]:
                ch = sys.stdin.read(1)
                if not ch:
                    break
                self._handle_hotkey(ch)
        except Exception:
            pass

    # ------------------------------------------------------------------
    def run(self):
        def _signal_handler(sig, frame):
            self.panic(reason="signal")
            self.close()
            sys.exit(0)

        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)
        self._hotkey_tty_setup()

        if self.show_status:
            with Live(self._make_status_panel(), console=console, refresh_per_second=10) as live:
                last_ui_update = 0.0
                try:
                    while True:
                        # --- Fast MIDI processing path ---
                        processed = False
                        for msg in self.inport.iter_pending():
                            self.process(msg)
                            processed = True

                        # Drain delayed outbound MIDI (no-op if sync disabled)
                        self._flush_send_queue()
                        self._record_idle_check()

                        # Voodoo paced bank load / elastic catch-up
                        if self.voodoo_loading or self.voodoo_catchup:
                            self._voodoo_tick()

                        # Anima sustained-note mod (idle when disabled / no notes)
                        if self.anima:
                            self._anima_tick()

                        # Background reconnect for offline outputs
                        self._retry_offline_ports()

                        # Format idle clear (60s with no MIDI)
                        self._check_format_idle()
                        self._check_anima_session_idle()

                        # Hotkeys (format, mode, quit, …)
                        self._poll_hotkeys()

                        # --- UI update only ~8–10 times per second ---
                        now = time.monotonic()
                        if now - last_ui_update >= 0.12:
                            live.update(self._make_status_panel())
                            last_ui_update = now

                        # Tiny sleep only when idle to avoid busy-waiting
                        if not processed:
                            time.sleep(0.001)

                except Exception as e:
                    console.print(f"[red]Error: {e}[/]")
                    try:
                        self.panic(reason="exception")
                    except Exception as e2:
                        console.print(f"[red]Panic also failed: {e2}[/]")
                finally:
                    self.close()
        else:
            # No status panel – pure low-latency path
            try:
                for msg in self.inport:
                    self.process(msg)
                    self._flush_send_queue()
                    self._record_idle_check()
                    if self.voodoo_loading or self.voodoo_catchup:
                        self._voodoo_tick()
                    if self.anima:
                        self._anima_tick()
                    self._retry_offline_ports()
            except Exception as e:
                console.print(f"[red]Error: {e}[/]")
                try:
                    self.panic(reason="exception")
                except Exception as e2:
                    console.print(f"[red]Panic also failed: {e2}[/]")
            finally:
                self.close()

    def close(self):
        self._hotkey_tty_restore()
        if getattr(self, "_rec_on", False):
            self._record_stop("close")
        # Log last-ok ages so a wedged-but-silent out is visible in the session log
        try:
            now = time.monotonic()
            for i, name in enumerate(getattr(self, "port_names", []) or []):
                last = self._out_last_ok[i] if i < len(self._out_last_ok) else 0.0
                offline = self._out_offline[i] if i < len(self._out_offline) else False
                if last <= 0.0:
                    age = "never"
                else:
                    age = f"{now - last:.1f}s ago"
                flag = " OFFLINE" if offline else ""
                self._log_line(f"PORT  Session end out {i + 1} ({name}): last ok {age}{flag}")
        except Exception:
            pass

        try:
            self.inport.close()
            self._log_line(f"PORT  Closed input: {getattr(self, 'in_name', '?')}")
        except Exception as e:
            self._log_line(f"PORT  Close input error: {e}")
        for i, out in enumerate(self.outs):
            name = self.port_names[i] if i < len(self.port_names) else "?"
            try:
                out.close()
                self._log_line(f"PORT  Closed out {i + 1}: {name}")
            except Exception as e:
                self._log_line(f"PORT  Close out {i + 1} ({name}) error: {e}")
        if self._log_file is not None:
            try:
                self._log_file.write(
                    f"--- session end {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n"
                )
                self._log_file.close()
            except OSError:
                pass
            self._log_file = None

# ----------------------------------------------------------------------
def list_ports():
    console.print("\n[bold]=== MIDI Input ports ===[/]")
    for name in mido.get_input_names():
        console.print(f"  {name}")
    console.print("\n[bold]=== MIDI Output ports ===[/]")
    for name in mido.get_output_names():
        console.print(f"  {name}")
    console.print()

def pick_port(available: list[str], prompt: str) -> str:
    if not available:
        console.print("[red]No ports found![/]")
        sys.exit(1)
    console.print(f"\n{prompt}")
    for i, name in enumerate(available):
        console.print(f"  [{i}] {name}")
    while True:
        try:
            idx = int(input("Enter number: ").strip())
            if 0 <= idx < len(available):
                return available[idx]
        except ValueError:
            pass
        console.print("[yellow]Invalid choice, try again.[/]")

def resolve_port(name: str | None, available: list[str], label: str) -> str:
    if name:
        for p in available:
            if p == name:
                return p
        matches = [p for p in available if name.lower() in p.lower()]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            console.print(f"[red]Ambiguous {label} '{name}'. Matches:[/]")
            for m in matches:
                console.print(f"  {m}")
            sys.exit(1)
        console.print(f"[red]No {label} matching '{name}'[/]")
        list_ports()
        sys.exit(1)
    return pick_port(available, f"Select {label}:")

def parse_out_spec(spec: str) -> tuple[str, frozenset]:
    """
    Parse --outs entry: "Port Name", "Port Name:gs", or "Port Name:gs+gm2".
    Returns (port_name, frozenset of format tags). Default tag set is {"any"}.
    """
    if ":" not in spec:
        return spec, frozenset({"any"})
    # Split on last colon so names with colons are less likely to break
    name, _, tag = spec.rpartition(":")
    name = name.strip()
    tag = tag.strip().lower()
    if not name:
        raise ValueError(f"Invalid --outs entry (empty name): {spec!r}")
    if not tag or tag == "any":
        return name, frozenset({"any"})
    parts = [p.strip() for p in tag.split("+") if p.strip()]
    if not parts:
        return name, frozenset({"any"})
    tags = set()
    for p in parts:
        if p not in FORMAT_ALIASES:
            valid = ", ".join(sorted(set(FORMAT_ALIASES.values())))
            raise ValueError(
                f"Unknown format tag {p!r} in {spec!r}. "
                f"Valid: {valid} (combine with +, e.g. gs+gm2)"
            )
        tags.add(FORMAT_ALIASES[p])
    if "any" in tags:
        return name, frozenset({"any"})
    return name, frozenset(tags)


# ----------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description=f"Duality v{VERSION} – Intelligent multi-device MIDI polyphony router"
    )
    parser.add_argument("--version", action="version", version=f"Duality {VERSION}")
    parser.add_argument("--list", action="store_true", help="List available MIDI ports and exit")
    parser.add_argument("--input", help="MIDI input port name (or partial match)")
    parser.add_argument(
        "--outs",
        nargs="+",
        metavar="PORT",
        help=(
            "MIDI output port names. Optional format tag: Name:gs|8850|8820|88pro|880|88|55|xg|gm|gm2|mt32. "
            "Minimum 2 ports (or 1 with --alchemy). Example: --outs \"SC:gs\" \"MU:xg\""
        ),
    )
    parser.add_argument(
        "--record",
        nargs="?",
        const=".",
        default=None,
        metavar="DIR",
        help=(
            "Record Duality input and each output as Standard MIDI Files "
            "in DIR (default: current directory). Includes SysEx. "
            "Hotkey W starts/stops a new take."
        ),
    )
    parser.add_argument(
        "--anima",
        action="store_true",
        help=(
            "Anima: GM-category phrasing (expr/mod ramps, velocity humanize, "
            "guitar strum). May be used with a single output port. Off by default."
        ),
    )
    parser.add_argument(
        "--anima-game",
        action="store_true",
        help=(
            "Enable Anima in game mode: 4s idle reset (not 30s) and reroll "
            "GS EFX when a burst of program changes looks like a new cue. "
            "Implies --anima. Hotkey A cycles Anima off / normal / game. "
            "Reroll skipped while the Anima seed is locked (S / --anima-seed)."
        ),
    )
    def _parse_anima_seed(s: str):
        # Badge is 4 hex digits. "1665" means 0x1665, not decimal 1665 (0x0681).
        s = str(s).strip()
        if s.lower().startswith("0x"):
            return int(s, 16) & 0xFFFF
        hexish = s[2:] if s.lower().startswith("0x") else s
        if 1 <= len(hexish) <= 4 and all(c in "0123456789abcdefABCDEF" for c in hexish):
            return int(hexish, 16) & 0xFFFF
        try:
            return int(s, 10) & 0xFFFF
        except ValueError:
            return int(s, 16) & 0xFFFF

    parser.add_argument(
        "--anima-seed",
        nargs="?",
        const=-1,
        default=None,
        type=_parse_anima_seed,
        metavar="4A2F",
        help=(
            "Anima seed (same value as the badge). "
            "Bare --anima-seed locks the first rolled seed. "
            "--anima-seed 1665  or  4A2F  or  0x4A2F  locks that hex seed "
            "(X will not reroll). Hotkey S toggles lock. "
            "Badge shows 4 hex digits, * when locked."
        ),
    )
    parser.add_argument(
        "--anima-efx-stable",
        action="store_true",
        help="Deprecated alias for bare --anima-seed (lock first roll).",
    )
    parser.add_argument(
        "--voodoo",
        action="store_true",
        help=(
            "Load a GM-style bank onto all :mt32/:cm outs at startup "
            "(paced SysEx + input queue with elastic catch-up). "
            "Also: M when format is already MT-32; auto when only :mt32 outs "
            "and the input stream is non-MT-32. Hotkey V cycles banks."
        ),
    )
    parser.add_argument(
        "--voodoo-bank",
        default="mtgm",
        metavar="NAME",
        help=(
            "Voodoo bank: mtgm (Roland MT-TO-GM, default) or kq6 "
            "(Sierra King's Quest VI). Hotkey V cycles while running."
        ),
    )
    parser.add_argument(
        "--voodoo-layout",
        default="stripe",
        choices=("stripe", "pairs"),
        help=(
            "Multi-MT-32 channel layout: stripe (default, best for 3) or "
            "pairs (4+ even units — mirrored 2-unit maps with note LB). "
            "Hotkey P toggles when eligible."
        ),
    )
    parser.add_argument(
        "--alchemy",
        action="store_true",
        help=(
            "Enable Alchemy (BROKEN/EXPERIMENTAL). Attempts GS↔XG SysEx/PC rewrite; "
            "allows single output. Same-dialect traffic should pass through unchanged."
        ),
    )
    parser.add_argument(
        "--alchemy-all",
        action="store_true",
        help=(
            "Enable Alchemy (BROKEN/EXPERIMENTAL) and fan out to all GS/XG-capable outs. "
            "Implies --alchemy."
        ),
    )
    parser.add_argument(
        "--crucible",
        action="store_true",
        help="Enable Crucible format-routing (SysEx and notes follow format affinity)",
    )
    parser.add_argument(
        "--crucible-notes",
        choices=["affinity", "all"],
        default="affinity",
        help="With --crucible: note destinations (affinity=format-matched, all=every port)",
    )
    parser.add_argument(
        "--crucible-gm-wide",
        action="store_true",
        help="With --crucible: also send GM/GM2 streams to gs and xg ports",
    )
    parser.add_argument(
        "--input-format",
        choices=["gm", "gm2", "gs", "xg", "mt32"],
        default=None,
        help="Assume this stream format until SysEx proves otherwise",
    )
    parser.add_argument(
        "--scpop",
        action="store_true",
        help=(
            "Force SCPOP mode: broadcast notes to format-matched ports "
            "(for pipe-organ SC files that only identify via meta, not SysEx)"
        ),
    )
    parser.add_argument(
        "--strict-format-detection",
        action="store_true",
        help=(
            "Only GM/GM2 System On, GS Reset, XG System On, and MT-32 reset SysEx "
            "may set/switch input format. Default: any family SysEx can (current behavior)."
        ),
    )
    parser.add_argument(
        "--mode",
        choices=["balance", "rr"],
        default="balance",
        help="balance = load-balance + chord preference (default), rr = pure round-robin",
    )
    parser.add_argument(
        "--poly",
        nargs="+",
        type=int,
        default=[POLY_DEFAULT],
        help=f"Polyphony limit(s). One value applies to all ports, or one value per port (default {POLY_DEFAULT})",
    )
    parser.add_argument(
        "--sync-delay",
        nargs="+",
        type=float,
        default=[0.0],
        metavar="MS",
        help=(
            "Per-port sync delay in ms (one value or one per port). "
            "Negatives are relative offsets (normalized so the earliest port is 0). "
            f"Clamped to ±{int(SYNC_DELAY_MAX_MS)} ms. Default 0 (fast path, no queue)."
        ),
    )
    parser.add_argument(
        "--chord-ms",
        type=float,
        default=CHORD_MS_DEFAULT,
        help=f"Chord detection window in milliseconds (default {CHORD_MS_DEFAULT})",
    )
    parser.add_argument(
        "--no-status",
        action="store_true",
        help="Disable the live status panel",
    )
    parser.add_argument(
        "--log",
        nargs="?",
        const="duality.log",
        default=None,
        metavar="PATH",
        help=(
            "Append status, Alchemy, bank/PC, and RPN/NRPN events to a log file "
            "(default path: duality.log). See also --log-verbose."
        ),
    )
    parser.add_argument(
        "--log-verbose",
        nargs="?",
        const="duality.log",
        default=None,
        metavar="PATH",
        help=(
            "Enable logging in verbose mode (all CCs, pitch, etc.). "
            "Optional path (default: duality.log). "
            "If both --log and --log-verbose are given, verbose wins."
        ),
    )
    args = parser.parse_args()

    if args.list:
        list_ports()
        return

    inputs = mido.get_input_names()
    outputs = mido.get_output_names()

    in_name = resolve_port(args.input, inputs, "input port")

    out_formats: list[str] = []

    if args.outs:
        if len(args.outs) < 1:
            console.print("[red]Error: at least 1 output port is required.[/]")
            sys.exit(1)
        out_names = []
        try:
            for spec in args.outs:
                name_part, fmt = parse_out_spec(spec)
                resolved = resolve_port(name_part, outputs, f"output port '{name_part}'")
                out_names.append(resolved)
                out_formats.append(fmt)
        except ValueError as e:
            console.print(f"[red]{e}[/]")
            sys.exit(1)
    else:
        # Interactive – default to 2 ports (or 1 when Alchemy-only)
        n_pick = min_ports if args.alchemy else 2
        console.print(f"\n[cyan]No --outs provided → interactive setup for {n_pick} port(s)[/]")
        out_names = []
        for i in range(n_pick):
            name = pick_port(outputs, f"Select output device {i+1} of {n_pick}:")
            while name in out_names:
                console.print("[yellow]That port is already selected.[/]")
                name = pick_port(outputs, f"Select output device {i+1} of {n_pick}:")
            out_names.append(name)
            out_formats.append(frozenset({"any"}))

    if len(set(out_names)) != len(out_names):
        console.print("[red]Error: all output ports must be unique.[/]")
        sys.exit(1)

    try:
        # Resolve --log / --log-verbose (verbose wins if both given)
        if args.log_verbose is not None:
            log_path = args.log_verbose
            log_verbose = True
        elif args.log is not None:
            log_path = args.log
            log_verbose = False
        else:
            log_path = None
            log_verbose = False

        router = Duality(
            in_name=in_name,
            out_names=out_names,
            mode=args.mode,
            poly_limits=args.poly,
            chord_window_ms=args.chord_ms,
            show_status=not args.no_status,
            out_formats=out_formats,
            alchemy=args.alchemy,
            alchemy_all=args.alchemy_all,
            crucible=args.crucible,
            crucible_notes=args.crucible_notes,
            crucible_gm_wide=args.crucible_gm_wide,
            input_format=args.input_format,
            scpop=args.scpop,
            sync_delays_ms=args.sync_delay,
            strict_format_detection=args.strict_format_detection,
            log_path=log_path,
            log_verbose=log_verbose,
            voodoo=args.voodoo,
            voodoo_bank=getattr(args, "voodoo_bank", "mtgm"),
            voodoo_layout=getattr(args, "voodoo_layout", "stripe"),
            anima=getattr(args, "anima", False),
            anima_efx_stable=getattr(args, "anima_efx_stable", False),
            anima_seed=getattr(args, "anima_seed", None),
            anima_game=getattr(args, "anima_game", False),
            record_dir=getattr(args, "record", None),
        )
        router.run()
    except ValueError as e:
        console.print(f"[red]{e}[/]")
        sys.exit(1)

if __name__ == "__main__":
    main()
