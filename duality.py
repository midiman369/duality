#!/usr/bin/env python3
VERSION = "0.15.1"


"""
Duality – Intelligent Multi-Device MIDI Polyphony Router
---------------------------------------------------------
Version {VERSION}

Routes MIDI notes across two or more sound modules / synthesizers
to maximize effective polyphony while keeping non-note messages
synchronized across all devices.

Features
--------
• Load-balancing by utilization (fair with mixed poly limits) or pure round-robin
• Chord preference (notes arriving close together stay on the same device)
• Smart voice stealing (lowest velocity first, then oldest)
• Independent polyphony limit per device
• Full panic / All Notes Off handling
• Live status panel with per-port meters, channel activity,
  Volume / Pan / Mod Wheel / Pitch Bend, and activity counters
• Rolling status history + input-format badge (GM / GM2 / GS / XG / MT-32; * = locked)
• SysEx recognition & human-readable status for:
    – GS: Reset, Reverb/Chorus/Delay macros, EFX/MFX types, part EFX on/off, display text
    – XG: System On, Reverb/Chorus/Variation/Insertion types, display text
    – MT-32: Display text, reverb mode/time/level, master volume/tune
• Redundant controller filtering (keeps devices in sync while reducing traffic)
• Arbitrary number of output ports (default 2; 1 allowed with --alchemy)
• Output format tags = device capabilities (e.g. --outs "SC:gs+gm2") — not the input stream
• Crucible: route by input/stream format (SysEx detect, --input-format, or hotkeys)
• Unknown input format → GM-family ports only (pure MT-32 excluded until input is MT-32)
• No spill-to-all when no port matches the current input format
• Alchemy (BROKEN/EXPERIMENTAL): attempted GS↔XG SysEx/PC rewrite; --alchemy / --alchemy-all
• Hybrid with Crucible: native affinity first, overflow+translate under poly pressure
• Set input format (G/R/Y/M) vs lock input format (L); idle clear; F clears
• Optional --strict-format-detection: Only actual SYSTEM ON or RESET SysEx messages set/switch input format.
• GM→GM2 port affinity; optional --crucible-gm-wide for GS/XG
• SCPOP / SC-ext detection (model 45 or banner) + optional --scpop
• Per-port --sync-delay (ms); relative negatives normalized; 0 = fast path
• Graceful handling and attempted reconnect of dropped or lost output ports.
• Voodoo Phase V2: 2+ :mt32 outs get alternating 16-channel map
  (melody affinity + load-balanced rhythm) with equal partial reserve
• LA32 pan map for Voodoo / non-MT-32 streams (8 real positions, MT-32 & CM-32L tables)
• Port health logging (open/close/send fail/reconnect) when --log is enabled.
• Voodoo: Super-Munt-style GM bank load for MT-32 outs (Roland MT-TO-GM 1993).
  --voodoo / M multi-press / auto when only :mt32 outs + non-MT-32 stream.
  Paced SysEx + input queue with elastic catch-up; exit on MT-32 SysEx.

Hotkeys (input/stream format — not output tags)
-------
F clear input format   L lock/unlock input format
G GM↔GM2   R GS   Y XG   M MT-32 (again = Voodoo GM)
B balance↔rr     C clear log file     Q quit (panic)

Usage examples
--------------
# List available ports
python duality.py --list

# Two devices (classic)
python duality.py --input "loopMIDI Port" --outs "MS40 A" "MS40 B"

# Three devices with different polyphony limits
python duality.py \
  --input "loopMIDI Port" \
  --outs "Module A" "Module B" "Module C" \
  --poly 28 32 24

# Crucible + multi-capability tags
python duality.py --input "loopMIDI Port" --crucible --crucible-gm-wide \
  --outs "SC A:gs+gm2" "SC B:gs+gm2" "MU:xg+gm2" "MUNT:mt32"

# Sync delay (softsynth leads hardware by ~80 ms)
python duality.py --input "..." --outs "SC:gs+mt32" "MUNT:mt32" --sync-delay 0 -80

# Custom chord window + silent mode
python duality.py --input "..." --outs "A" "B" --chord-ms 25 --no-status

# Strict format detection (ignore stray XG/GS parameter SysEx)
python duality.py --input "..." --outs "A:gs" "B:xg" --crucible --strict-format-detection

# Show version
python duality.py --version
""".format(VERSION=VERSION)

import argparse
import signal
import sys
import time
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
    from voodoo_banks import (
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

mido.set_backend("mido.backends.rtmidi")

POLY_DEFAULT = 24
CHORD_MS_DEFAULT = 30.0
FORMAT_IDLE_SEC = 60.0
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
    "xg": "XG",
    "mt32": "MT-32",
    "cm32": "CM-32L",
    "any": "ANY",
}

# GM-family tags used when stream format is unknown (exclude pure MT-32)
GM_FAMILY_TAGS = frozenset({"gm", "gm2", "gs", "xg"})

def format_tags_label(tags) -> str:
    """Human label for a port capability set, e.g. GS+GM2."""
    if not tags or "any" in tags:
        return "ANY"
    order = ["gs", "xg", "gm", "gm2", "mt32"]
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
    "gs": {"gs"},
    "xg": {"xg"},
    "mt32": {"mt32"},
}

# ----------------------------------------------------------------------
# GS recognition tables (Based on SC-8850 / GS Standard)
# ----------------------------------------------------------------------

GS_REVERB_MACRO = {
    0: "Room 1",
    1: "Room 2",
    2: "Room 3",
    3: "Hall 1",
    4: "Hall 2",
    5: "Plate",
    6: "Delay",
    7: "Panning Delay",
}

GS_CHORUS_MACRO = {
    0: "Chorus 1",
    1: "Chorus 2",
    2: "Chorus 3",
    3: "Chorus 4",
    4: "Feedback Chorus",
    5: "Flanger",
    6: "Short Delay",
    7: "Short Delay (FB)",
}

GS_DELAY_MACRO = {
    0: "Delay 1",
    1: "Delay 2",
    2: "Delay 3",
    3: "Delay 4",
    4: "Pan Delay 1",
    5: "Pan Delay 2",
    6: "Pan Delay 3",
    7: "Pan Delay 4",
    8: "Delay → Reverb",
    9: "Pan Repeat",
}

# Key = (MSB, LSB) from address 40 03 00
GS_EFX_TYPES = {
    (0x00, 0x00): "Thru",

    # Filter
    (0x01, 0x00): "Stereo-EQ",
    (0x01, 0x01): "Spectrum",
    (0x01, 0x02): "Enhancer",
    (0x01, 0x03): "Humanizer",

    # Distortion
    (0x01, 0x10): "Overdrive",
    (0x01, 0x11): "Distortion",

    # Modulation
    (0x01, 0x20): "Phaser",
    (0x01, 0x21): "Auto Wah",
    (0x01, 0x22): "Rotary",
    (0x01, 0x23): "Stereo Flanger",
    (0x01, 0x24): "Step Flanger",
    (0x01, 0x25): "Tremolo",
    (0x01, 0x26): "Auto Pan",

    # Compressor
    (0x01, 0x30): "Compressor",
    (0x01, 0x31): "Limiter",

    # Chorus
    (0x01, 0x40): "Hexa Chorus",
    (0x01, 0x41): "Tremolo Chorus",
    (0x01, 0x42): "Stereo Chorus",
    (0x01, 0x43): "Space-D",
    (0x01, 0x44): "3D Chorus",

    # Delay / Reverb
    (0x01, 0x50): "Stereo Delay",
    (0x01, 0x51): "Mod Delay",
    (0x01, 0x52): "3 Tap Delay",
    (0x01, 0x53): "4 Tap Delay",
    (0x01, 0x54): "Time Ctrl Delay",
    (0x01, 0x55): "Reverb",
    (0x01, 0x56): "Gate Reverb",
    (0x01, 0x57): "3D Delay",

    # Pitch
    (0x01, 0x60): "Pitch Shifter",
    (0x01, 0x61): "2 Voice Pitch Shifter",

    # Others / Lo-Fi
    (0x01, 0x70): "Feedback Pitch Shifter",
    (0x01, 0x71): "3D Auto",
    (0x01, 0x72): "3D Manual",
    (0x01, 0x73): "Lo-Fi 1",
    (0x01, 0x74): "Lo-Fi 2",

    # Series multi-effects
    (0x02, 0x00): "OD → Chorus",
    (0x02, 0x01): "OD → Flanger",
    (0x02, 0x02): "OD → Delay",
    (0x02, 0x03): "OD → Phaser",
    (0x02, 0x04): "Dist → Chorus",
    (0x02, 0x05): "Dist → Flanger",
    (0x02, 0x06): "Dist → Delay",
    (0x02, 0x07): "Dist → Phaser",
    (0x02, 0x08): "Enh → Chorus",
    (0x02, 0x09): "Enh → Flanger",
    (0x02, 0x0A): "Enh → Delay",
    (0x02, 0x0B): "Enh → Phaser",

    # Higher multi / parallel
    (0x04, 0x00): "Rotary Multi",
    (0x04, 0x01): "Guitar Multi 1",
    (0x04, 0x02): "Guitar Multi 2",
    (0x04, 0x03): "Guitar Multi 3",
    (0x04, 0x04): "Clean Gt Multi 1",
    (0x04, 0x05): "Bass Multi",
    (0x04, 0x06): "Rhodes Multi",
    (0x05, 0x00): "Keyboard Multi",
    (0x11, 0x00): "Cho/Delay",
    (0x11, 0x01): "FL/Delay",
    (0x11, 0x02): "Cho/Flanger",
    (0x11, 0x03): "OD1/OD2",
    (0x11, 0x04): "OD/Rotary",
    (0x11, 0x05): "OD/Phaser",
    (0x11, 0x06): "OD/Auto Wah",
    (0x11, 0x07): "PH/Rotary",
    (0x11, 0x08): "PH/Auto Wah",
}

# ----------------------------------------------------------------------
# MT-32 recognition tables (Based on Roland MT-32 and compatibles)
# ----------------------------------------------------------------------
MT32_REVERB_MODES = {
    0: "Room",
    1: "Hall",
    2: "Plate",
    3: "Tap Delay",
}

# ----------------------------------------------------------------------
# XG recognition tables (Based on Yamaha MU128 / XG standard)
# Key = (MSB, LSB)
# ----------------------------------------------------------------------

XG_REVERB_TYPES = {
    (0x00, 0x00): "No Effect",
    (0x01, 0x00): "Hall 1",
    (0x01, 0x01): "Hall 2",
    (0x02, 0x00): "Room 1",
    (0x02, 0x01): "Room 2",
    (0x02, 0x02): "Room 3",
    (0x03, 0x00): "Stage 1",
    (0x03, 0x01): "Stage 2",
    (0x04, 0x00): "Plate",
    (0x10, 0x00): "White Room",
    (0x11, 0x00): "Tunnel",
    (0x12, 0x00): "Canyon",
    (0x13, 0x00): "Basement",
}

XG_CHORUS_TYPES = {
    (0x00, 0x00): "No Effect",
    (0x41, 0x00): "Chorus 1",
    (0x41, 0x01): "Chorus 2",
    (0x41, 0x02): "Chorus 3",
    (0x41, 0x08): "Chorus 4",
    (0x42, 0x00): "Celeste 1",
    (0x42, 0x01): "Celeste 2",
    (0x42, 0x02): "Celeste 3",
    (0x42, 0x08): "Celeste 4",
    (0x43, 0x00): "Flanger 1",
    (0x43, 0x01): "Flanger 2",
    (0x43, 0x08): "Flanger 3",
    (0x44, 0x00): "Symphonic",
    (0x57, 0x00): "Ensemble Detune",
    (0x48, 0x00): "Phaser 1",
}

# Variation is the big flexible effect block (system or insertion mode)
XG_VARIATION_TYPES = {
    (0x00, 0x00): "No Effect",
    (0x01, 0x00): "Hall 1",
    (0x01, 0x01): "Hall 2",
    (0x02, 0x00): "Room 1",
    (0x02, 0x01): "Room 2",
    (0x02, 0x02): "Room 3",
    (0x03, 0x00): "Stage 1",
    (0x03, 0x01): "Stage 2",
    (0x04, 0x00): "Plate",
    (0x05, 0x00): "Delay L,C,R",
    (0x06, 0x00): "Delay L,R",
    (0x07, 0x00): "Echo",
    (0x08, 0x00): "Cross Delay",
    (0x09, 0x00): "ER 1",
    (0x09, 0x01): "ER 2",
    (0x0A, 0x00): "Gate Reverb",
    (0x0B, 0x00): "Reverse Gate",
    (0x10, 0x00): "White Room",
    (0x11, 0x00): "Tunnel",
    (0x12, 0x00): "Canyon",
    (0x13, 0x00): "Basement",
    (0x14, 0x00): "Karaoke 1",
    (0x14, 0x01): "Karaoke 2",
    (0x14, 0x02): "Karaoke 3",
    (0x41, 0x00): "Chorus 1",
    (0x41, 0x01): "Chorus 2",
    (0x41, 0x02): "Chorus 3",
    (0x41, 0x08): "Chorus 4",
    (0x42, 0x00): "Celeste 1",
    (0x42, 0x01): "Celeste 2",
    (0x42, 0x02): "Celeste 3",
    (0x42, 0x08): "Celeste 4",
    (0x43, 0x00): "Flanger 1",
    (0x43, 0x01): "Flanger 2",
    (0x43, 0x08): "Flanger 3",
    (0x44, 0x00): "Symphonic",
    (0x45, 0x00): "Rotary Speaker",
    (0x46, 0x00): "Tremolo",
    (0x47, 0x00): "Auto Pan",
    (0x48, 0x00): "Phaser 1",
    (0x48, 0x08): "Phaser 2",
    (0x49, 0x00): "Distortion",
    (0x49, 0x01): "Comp+Distortion",
    (0x4A, 0x00): "Overdrive",
    (0x4B, 0x00): "Amp Simulator",
    (0x4C, 0x00): "3-Band EQ",
    (0x4D, 0x00): "2-Band EQ",
    (0x4E, 0x00): "Auto Wah",
    (0x4E, 0x01): "Auto Wah+Dist",
    (0x4E, 0x02): "Auto Wah+Overdrive",
    (0x50, 0x00): "Pitch Change 1",
    (0x50, 0x01): "Pitch Change 2",
    (0x51, 0x00): "Harmonic Enhancer",
    (0x52, 0x00): "Touch Wah 1",
    (0x52, 0x01): "Touch Wah+Dist",
    (0x52, 0x02): "Touch Wah+Overdrive",
    (0x52, 0x08): "Touch Wah 2",
    (0x53, 0x00): "Compressor",
    (0x54, 0x00): "Noise Gate",
    (0x55, 0x00): "Voice Cancel",
    (0x56, 0x00): "2-Way Rotary Speaker",
    (0x57, 0x00): "Ensemble Detune",
    (0x58, 0x00): "Ambience",
    (0x5D, 0x00): "Talking Modulator",
    (0x5E, 0x00): "Lo-Fi",
    (0x5F, 0x00): "Dist+Delay",
    (0x5F, 0x01): "Overdrive+Delay",
    (0x60, 0x00): "Comp+Dist+Delay",
    (0x60, 0x01): "Comp+Overdrive+Delay",
    (0x61, 0x00): "Wah+Dist+Delay",
    (0x61, 0x01): "Wah+Overdrive+Delay",
    (0x40, 0x00): "Thru",
}

# Insertion 1 / 2 use a subset of the same type codes
XG_INSERTION_TYPES = {
    (0x40, 0x00): "Thru",
    (0x01, 0x00): "Hall 1",
    (0x01, 0x01): "Hall 2",
    (0x02, 0x00): "Room 1",
    (0x02, 0x01): "Room 2",
    (0x02, 0x02): "Room 3",
    (0x03, 0x00): "Stage 1",
    (0x03, 0x01): "Stage 2",
    (0x04, 0x00): "Plate",
    (0x05, 0x00): "Delay L,C,R",
    (0x06, 0x00): "Delay L,R",
    (0x07, 0x00): "Echo",
    (0x08, 0x00): "Cross Delay",
    (0x14, 0x00): "Karaoke 1",
    (0x14, 0x01): "Karaoke 2",
    (0x14, 0x02): "Karaoke 3",
    (0x41, 0x00): "Chorus 1",
    (0x41, 0x01): "Chorus 2",
    (0x41, 0x02): "Chorus 3",
    (0x41, 0x08): "Chorus 4",
    (0x42, 0x00): "Celeste 1",
    (0x42, 0x01): "Celeste 2",
    (0x42, 0x02): "Celeste 3",
    (0x42, 0x08): "Celeste 4",
    (0x43, 0x00): "Flanger 1",
    (0x43, 0x01): "Flanger 2",
    (0x43, 0x08): "Flanger 3",
    (0x44, 0x00): "Symphonic",
    (0x45, 0x00): "Rotary Speaker",
    (0x46, 0x00): "Tremolo",
    (0x47, 0x00): "Auto Pan",
    (0x48, 0x00): "Phaser 1",
    (0x49, 0x00): "Distortion",
    (0x4A, 0x00): "Overdrive",
    (0x4B, 0x00): "Amp Simulator",
    (0x4C, 0x00): "3-Band EQ",
    (0x4D, 0x00): "2-Band EQ",
    (0x4E, 0x00): "Auto Wah",
    (0x51, 0x00): "Harmonic Enhancer",
    (0x52, 0x00): "Touch Wah 1",
    (0x52, 0x08): "Touch Wah 2",
    (0x53, 0x00): "Compressor",
    (0x54, 0x00): "Noise Gate",
    (0x57, 0x00): "Ensemble Detune",
}

# ----------------------------------------------------------------------
# Alchemy Phase 1b – best-effort GS ↔ XG maps (resets already in methods)
# ----------------------------------------------------------------------
# GS reverb macro (0–7) → XG reverb type (MSB, LSB)
ALCHEMY_GS_REVERB_TO_XG = {
    0: (0x02, 0x00),  # Room 1
    1: (0x02, 0x01),  # Room 2
    2: (0x02, 0x02),  # Room 3
    3: (0x01, 0x00),  # Hall 1
    4: (0x01, 0x01),  # Hall 2
    5: (0x04, 0x00),  # Plate
    6: (0x02, 0x00),  # Delay → Room 1 stand-in
    7: (0x02, 0x01),  # Panning Delay → Room 2 stand-in
}
# XG reverb (MSB, LSB) → GS reverb macro
ALCHEMY_XG_REVERB_TO_GS = {
    (0x00, 0x00): 0,  # No Effect → Room 1
    (0x01, 0x00): 3,  # Hall 1
    (0x01, 0x01): 4,  # Hall 2
    (0x02, 0x00): 0,  # Room 1
    (0x02, 0x01): 1,  # Room 2
    (0x02, 0x02): 2,  # Room 3
    (0x03, 0x00): 3,  # Stage 1 → Hall 1
    (0x03, 0x01): 4,  # Stage 2 → Hall 2
    (0x04, 0x00): 5,  # Plate
}
# GS chorus macro → XG chorus type
ALCHEMY_GS_CHORUS_TO_XG = {
    0: (0x41, 0x00),  # Chorus 1
    1: (0x41, 0x01),  # Chorus 2
    2: (0x41, 0x02),  # Chorus 3
    3: (0x41, 0x08),  # Chorus 4
    4: (0x41, 0x01),  # Feedback → Chorus 2
    5: (0x43, 0x00),  # Flanger 1
    6: (0x41, 0x00),  # Short Delay → Chorus 1
    7: (0x41, 0x01),  # Short Delay FB → Chorus 2
}
ALCHEMY_XG_CHORUS_TO_GS = {
    (0x00, 0x00): 0,
    (0x41, 0x00): 0,
    (0x41, 0x01): 1,
    (0x41, 0x02): 2,
    (0x41, 0x08): 3,
    (0x42, 0x00): 1,  # Celeste → Chorus 2
    (0x42, 0x01): 2,
    (0x43, 0x00): 5,  # Flanger
    (0x43, 0x01): 5,
    (0x43, 0x08): 5,
    (0x44, 0x00): 3,  # Symphonic → Chorus 4
}

# XG Variation types that are delay-like → GS Delay macro (prefer short: 0 = Delay 1)
# Values are GS delay macro index (see GS_DELAY_MACRO)
# True delay-family XG Variation → GS Delay macro (short: 0 = Delay 1)
ALCHEMY_XG_VARIATION_DELAY_TO_GS = {
    (0x05, 0x00): 0,  # Delay L,C,R
    (0x06, 0x00): 0,  # Delay L,R
    (0x07, 0x00): 1,  # Echo → Delay 2
    (0x08, 0x00): 0,  # Cross Delay
}
# Early reflection / short special reverb → GS Reverb Room (not long Delay)
# GS reverb macro: 0=Room1, 1=Room2, 2=Room3
ALCHEMY_XG_VARIATION_REVERB_TO_GS = {
    (0x09, 0x00): 0,  # ER 1 → Room 1
    (0x09, 0x01): 1,  # ER 2 → Room 2
    (0x0A, 0x00): 0,  # Gate Reverb → Room 1
    (0x0B, 0x00): 0,  # Reverse Gate → Room 1
    (0x10, 0x00): 0,  # White Room → Room 1 (short reverb + slight pre-delay)
    (0x11, 0x00): 1,  # Tunnel → Room 2
    (0x12, 0x00): 2,  # Canyon → Room 3
    (0x13, 0x00): 1,  # Basement → Room 2
}
# XG Insertion / amp-sim family → GS EFX type (MSB, LSB) at 40 03 00
ALCHEMY_XG_INS_TO_GS_EFX = {
    (0x49, 0x00): (0x01, 0x11),  # Distortion
    (0x4A, 0x00): (0x01, 0x10),  # Overdrive
    (0x4B, 0x00): (0x01, 0x10),  # Amp Simulator → Overdrive stand-in
    (0x4E, 0x00): (0x01, 0x21),  # Auto Wah
    (0x48, 0x00): (0x01, 0x20),  # Phaser 1
}
# Reverse: GS EFX type → XG Insertion 1 type
ALCHEMY_GS_EFX_TO_XG_INS = {
    # Core
    (0x01, 0x10): (0x4A, 0x00),  # Overdrive
    (0x01, 0x11): (0x49, 0x00),  # Distortion
    (0x01, 0x20): (0x48, 0x00),  # Phaser
    (0x01, 0x21): (0x4E, 0x00),  # Auto Wah
    (0x01, 0x00): (0x4C, 0x00),  # Stereo-EQ → 3-Band EQ
    (0x01, 0x01): (0x4C, 0x00),  # Spectrum
    (0x01, 0x02): (0x51, 0x00),  # Enhancer
    (0x01, 0x22): (0x45, 0x00),  # Rotary
    (0x01, 0x23): (0x43, 0x00),  # Stereo Flanger
    (0x01, 0x24): (0x43, 0x08),  # Step Flanger
    (0x01, 0x25): (0x46, 0x00),  # Tremolo
    (0x01, 0x26): (0x47, 0x00),  # Auto Pan
    (0x01, 0x30): (0x53, 0x00),  # Compressor
    (0x01, 0x40): (0x41, 0x00),  # Hexa Chorus
    (0x01, 0x42): (0x41, 0x00),  # Stereo Chorus
    (0x01, 0x50): (0x05, 0x00),  # Stereo Delay
    (0x01, 0x51): (0x06, 0x00),  # Mod Delay
    (0x01, 0x55): (0x02, 0x00),  # Reverb
    (0x01, 0x56): (0x0A, 0x00),  # Gate Reverb
    (0x01, 0x57): (0x08, 0x00),  # 3D Delay → Cross Delay stand-in
    # Series multi → nearest single
    (0x02, 0x00): (0x4A, 0x00),  # OD→Cho → Overdrive
    (0x02, 0x02): (0x4A, 0x00),  # OD→Delay
    (0x02, 0x04): (0x49, 0x00),  # Dist→Cho
    (0x02, 0x06): (0x49, 0x00),  # Dist→Delay
    (0x02, 0x0A): (0x05, 0x00),  # Enh→Delay → Delay
    (0x04, 0x01): (0x4B, 0x00),  # Guitar Multi → Amp Sim
    (0x04, 0x02): (0x4B, 0x00),
    (0x04, 0x03): (0x4B, 0x00),
    (0x04, 0x04): (0x4A, 0x00),  # Clean Gt Multi → Overdrive (milder)
    (0x04, 0x05): (0x4B, 0x00),  # Bass Multi
    (0x05, 0x00): (0x41, 0x00),  # Keyboard Multi → Chorus
    (0x11, 0x00): (0x41, 0x00),  # Cho/Delay
    (0x11, 0x01): (0x43, 0x00),  # FL/Delay
    (0x11, 0x02): (0x43, 0x00),  # Cho/Flanger
    (0x11, 0x03): (0x4A, 0x00),  # OD1/OD2
    (0x11, 0x08): (0x4E, 0x00),  # PH/Auto Wah
}
# Space-like Variation → GS EFX (dual path: system reverb stays independent)
# Only used when EFX slot is not owned by Insertion
ALCHEMY_XG_VARIATION_TO_GS_EFX = {
    (0x09, 0x00): (0x01, 0x55),  # ER 1 → EFX Reverb
    (0x09, 0x01): (0x01, 0x55),  # ER 2
    (0x0A, 0x00): (0x01, 0x56),  # Gate Reverb
    (0x0B, 0x00): (0x01, 0x56),  # Reverse Gate
    (0x10, 0x00): (0x01, 0x55),  # White Room
    (0x11, 0x00): (0x01, 0x55),  # Tunnel
    (0x12, 0x00): (0x01, 0x55),  # Canyon
    (0x13, 0x00): (0x01, 0x55),  # Basement
}

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
    ):
        # Alchemy may run with a single output (transcode-only path).
        # Classic router still requires at least two ports.
        min_ports = 1 if (alchemy or voodoo) else 2
        if len(out_names) < min_ports:
            raise ValueError(
                f"At least {min_ports} output port(s) required"
                + (" with --alchemy." if alchemy else ".")
            )

        self.mode = mode
        self.n_ports = len(out_names)
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
        self.vol = [None] * 16          # CC7
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

        # Output health / reconnect (Windows often invalidates ports when apps quit)
        self._out_offline = [False] * self.n_ports
        self._out_last_reconnect_attempt = [0.0] * self.n_ports
        self._out_last_ok = [0.0] * self.n_ports          # last successful send (monotonic)
        self._out_fail_logged = [False] * self.n_ports    # rate-limit fail log spam
        self._reconnect_cooldown = 2.0  # seconds between reconnect attempts per port

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
            "[bold]Y[/]=XG  [bold]M[/]=MT-32/Voodoo  [bold]B[/]=balance/rr  [bold]C[/]=clear log  [bold]Q[/]=quit"
        )
        # --voodoo: seed MT-32 format (so L can lock) then begin paced GM load
        if self.voodoo_requested:
            self.detected_format = "MT-32"
            self.format_pulse_time = time.monotonic() + 2.8
            self._voodoo_begin("startup --voodoo")

    # ------------------------------------------------------------------
    

    def _log_line(self, line: str) -> None:
        """Append one line to --log file (no-op if logging disabled)."""
        if getattr(self, "_log_file", None) is None or not line:
            return
        try:
            self._log_file.write(f"{time.strftime('%H:%M:%S')} {line}\n")
            self._log_file.flush()
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
        # 1) Roland model 0x45 (SC-ext / SCPOP setup dumps) – text optional
        # 2) Any Roland SysEx whose printable payload contains "SCPOP"
        if data[0] == 0x41 and len(data) >= 6 and not self.scpop_mode:
            try:
                ascii_payload = bytes(
                    b for b in data[4:] if 32 <= b <= 126
                ).decode("ascii", errors="ignore")
            except Exception:
                ascii_payload = ""
            model = data[2]
            triggered = False
            reason = ""
            if model == 0x45:
                triggered = True
                reason = "SCPOP/SC-ext (model 45)"
            elif "SCPOP" in ascii_payload.upper():
                triggered = True
                reason = "SCPOP banner in SysEx"
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

            # EFX Type (address 40 03 00)
            if aa == 0x40 and bb == 0x03 and cc == 0x00 and len(data) >= 9:
                msb, lsb = data[7], data[8]
                name = GS_EFX_TYPES.get((msb, lsb), f"{msb:02X} {lsb:02X}")
                return f"GS EFX {name}"

            # EFX On/Off for a part (address 40 xx 22)
            if aa == 0x40 and cc == 0x22 and len(data) >= 8:
                # bb is the block/part indicator
                # Common mapping for parts 1-16 is roughly 0x11-0x1F / 0x41-...
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

        # ----- SCPOP / SC extended (Roland Model ID 45) -----
        if data[0] == 0x41 and len(data) >= 6 and data[2] == 0x45:
            try:
                text_payload = bytes(
                    b for b in data[7:] if 32 <= b <= 126
                ).decode("ascii", errors="ignore").strip()
            except Exception:
                text_payload = ""
            if text_payload:
                if len(text_payload) > 40:
                    text_payload = text_payload[:37] + "…"
                return f"SCPOP: {text_payload}"
            return "SCPOP SysEx"

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
        
    def _resync_voice_counts(self):
        """Quietly rebuild counts from active notes. Never triggers steals by itself."""
        actual = [0] * self.n_ports
        for info in self.active.values():
            port = info["port"]
            if 0 <= port < self.n_ports:
                actual[port] += 1
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
        ports = self.active[key].get("ports", [port])
        for p in ports:
            self._send_routed(p, off)
            self.voice_counts[p] = max(0, self.voice_counts[p] - 1)
        del self.active[key]
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
        # Always send these
        if msg.type in ("sysex", "program_change", "reset", "stop", "start", "continue", "songpos", "song_select"):
            return True

        if msg.type == "control_change":
            # Always send Bank Select and mode messages
            if msg.control in (0, 32, 120, 121, 122, 123, 124, 125, 126, 127):
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
            self._out_last_ok[port] = time.monotonic()
            self._out_fail_logged[port] = False
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
            self._gs_dt1([0x40, self._gs_part_mid(p), 0x22], [0x01])
            for p in range(16)
        ]

    @staticmethod
    def _gs_mid_to_part(mid: int):
        """
        GS PART mid address → part index 0–15.
        Supports both classic SC-55/88 (10/11-1F) and SC-8850 EFX block (40-4F).
        """
        # SC-8850 / 11GT_EFX style: 40=Part1 … 4F=Part16
        if 0x40 <= mid <= 0x4F:
            return mid - 0x40
        # Classic: 11-19 = parts 1-9, 10 = part 10, 1A-1F = parts 11-16
        if mid == 0x10:
            return 9
        if 0x11 <= mid <= 0x19:
            return mid - 0x11
        if 0x1A <= mid <= 0x1F:
            return mid - 0x1A + 10
        return None

    @staticmethod
    def _gs_part_mid(part: int) -> int:
        """
        Roland GS PART block mid address for part index 0–15.
        Encoding is non-linear: 11-19, 10, 1A-1F (not 10+part).
        """
        if part < 9:
            return 0x11 + part          # parts 1–9 → 11h–19h
        if part == 9:
            return 0x10                # part 10 → 10h
        return 0x1A + (part - 10)      # parts 11–16 → 1Ah–1Fh

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
        mid = self._gs_part_mid(part)
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
                self._send(port, m)
                self._log_msg(port, m, note=note or "Alchemy multi")
            if label:
                self._set_status(f"Alchemy: {label} → out {port + 1}", duration=2.5)
            return
        out_msg = self._apply_mt32_pan_invert(port, out_msg)
        self._send(port, out_msg)
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
            self._set_status("Voodoo unavailable (voodoo_banks.py missing)", duration=4.0)
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


    def process(self, msg: mido.Message):
        # Any MIDI activity refreshes format-idle timer
        self.last_midi_time = time.monotonic()

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

            if is_note_on:
                now = time.monotonic()
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
                    port = self._choose_port(is_chord)
                    if port is None:
                        self.drop_count += 1
                        return
                    self.last_chord_port = port
                    targets = [port]

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
                    self._maybe_gs_efx_on_note(port, msg)
                    self._send_routed(port, msg)
                    self.voice_counts[port] += 1
                    sent_ports.append(port)

                if not sent_ports:
                    self.drop_count += 1
                    return

                primary = sent_ports[0]
                self.last_chord_port = primary
                self.active[key] = {
                    "port": primary,
                    "ports": sent_ports,
                    "time": now,
                    "velocity": msg.velocity,
                }

                total_now = sum(self.voice_counts)
                if total_now > self.peak_voices:
                    self.peak_voices = total_now
            else:
                # Note Off
                info = self.active.pop(key, None)
                if info is not None:
                    ports = info.get("ports") or [info["port"]]
                    for port in ports:
                        self._send_routed(port, msg)
                        self.voice_counts[port] = max(0, self.voice_counts[port] - 1)
                else:
                    for i in range(self.n_ports):
                        self._send_routed(i, msg)

                # Only resync if the drift is significant
                if abs(sum(self.voice_counts) - len(self.active)) > 1:
                    self._resync_voice_counts()

            return

        if self._is_panic(msg):
            self.panic(reason=f"received {msg}")
            return

        # SysEx → detect format, describe it, show in status, and forward
        if msg.type == "sysex":
            self._voodoo_on_mt32_sysex(msg)
            self._detect_format(msg)
            self._voodoo_maybe_auto()
            description = self._describe_sysex(msg)

            # Suppress pure noise
            if description in ("GS SysEx", "SysEx", "GM/Universal SysEx", "XG SysEx", "MT-32 SysEx"):
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

            for i in targets:
                self._send_routed(i, msg)
            return

        # Track common controllers per channel + timestamp
        # Bank select for Alchemy program mapping
        if msg.type == "control_change":
            if msg.control == 0:
                self.bank_msb[msg.channel] = msg.value
            elif msg.control == 32:
                self.bank_lsb[msg.channel] = msg.value

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
                self.vol[ch] = msg.value
                self.vol_time[ch] = now
            elif msg.control == 10:    # Pan
                self.pan[ch] = msg.value
                self.pan_time[ch] = now
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

        for i in targets:
            if self._should_send(i, msg):
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
        self.active.clear()
        self.voice_counts = [0] * self.n_ports
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

        # Notes per MIDI channel (1–16)
        channel_counts = [0] * 16
        for (ch, note) in self.active:
            channel_counts[ch] += 1

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
        if self.voodoo_loading:
            badge_voodoo = " [bold bright_red][Voodoo…][/]"
        elif self.voodoo_catchup:
            badge_voodoo = " [bold yellow][Voodoo↑][/]"
        elif self.voodoo_active:
            badge_voodoo = " [bold bright_red][Voodoo][/]"
        else:
            badge_voodoo = " " * 10  # len(" [Voodoo…]") approx
        mode_badges = f"{badge_crucible}{badge_alchemy}{badge_scpop}{badge_voodoo}"

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
        elif c == "c":
            self._clear_log()
        elif c == "l":
            self._toggle_format_lock()
        elif c == "q":
            self._set_status("Quit requested – panicking and exiting…", duration=2.0)
            self.panic(reason="hotkey Q")
            self.close()
            sys.exit(0)

    def _poll_hotkeys(self) -> None:
        """Non-blocking keyboard poll for format / control hotkeys."""
        try:
            import msvcrt  # Windows
            while msvcrt.kbhit():
                ch = msvcrt.getwch()
                self._handle_hotkey(ch)
        except ImportError:
            # Unix: best-effort non-blocking stdin (may not work under all terminals)
            try:
                import select
                if select.select([sys.stdin], [], [], 0)[0]:
                    ch = sys.stdin.read(1)
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

                        # Voodoo paced bank load / elastic catch-up
                        if self.voodoo_loading or self.voodoo_catchup:
                            self._voodoo_tick()

                        # Background reconnect for offline outputs
                        self._retry_offline_ports()

                        # Format idle clear (60s with no MIDI)
                        self._check_format_idle()

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
                    if self.voodoo_loading or self.voodoo_catchup:
                        self._voodoo_tick()
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
            "MIDI output port names. Optional format tag: Name:gs|xg|gm|gm2|mt32. "
            "Minimum 2 ports (or 1 with --alchemy). Example: --outs \"SC:gs\" \"MU:xg\""
        ),
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

    min_ports = 1 if (args.alchemy or args.voodoo) else 2
    out_formats: list[str] = []

    if args.outs:
        if len(args.outs) < min_ports:
            console.print(
                f"[red]Error: at least {min_ports} output port(s) required"
                + (" with --alchemy.[/]" if args.alchemy else ".[/]")
            )
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
        )
        router.run()
    except ValueError as e:
        console.print(f"[red]{e}[/]")
        sys.exit(1)

if __name__ == "__main__":
    main()
