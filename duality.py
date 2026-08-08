#!/usr/bin/env python3
VERSION = "0.10.5-dev"

"""
Duality – Intelligent Multi-Device MIDI Polyphony Router
---------------------------------------------------------
Version {VERSION}

Routes MIDI notes across two or more sound modules / synthesizers
to maximize effective polyphony while keeping non-note messages
synchronized across all devices.

Features
--------
• Load-balancing or pure round-robin note assignment
• Chord preference (notes arriving close together stay on the same device)
• Smart voice stealing (lowest velocity first, then oldest)
• Independent polyphony limit per device
• Full panic / All Notes Off handling
• Live status panel with per-port meters, channel activity,
  Volume / Pan / Mod Wheel / Pitch Bend, and activity counters
• Rolling status history + format badge (GM / GM2 / GS / XG / MT-32)
• SysEx recognition & human-readable status for:
    – GS: Reset, Reverb/Chorus macros, EFX/MFX types, part EFX on/off, display text
    – XG: System On, Reverb/Chorus/Variation/Insertion types, display text
    – MT-32: Display text, reverb mode/time/level, master volume/tune
• Redundant controller filtering (keeps devices in sync while reducing traffic)
• Arbitrary number of output ports (default 2)
• Optional output format tags (--outs "Dev:gs" "Dev:xg")
• Crucible: format-aware routing (SysEx + note affinity)
• Alchemy: gate for future transcoding (allows single output)
• Format state: strong SysEx lock, opposite switch, 60s idle clear, F hotkey
• GM→GM2 port affinity; optional --crucible-gm-wide for GS/XG
• SCPOP / SC-ext detection (model 45 or banner) + optional --scpop force

Usage examples
--------------
# List available ports
python duality.py --list

# Two devices (classic)
python duality.py --input "loopMIDI Port" --outs "MS40 A" "MS40 B"

# Three devices with different polyphony limits
python duality.py \\
  --input "loopMIDI Port" \\
  --outs "Module A" "Module B" "Module C" \\
  --poly 28 32 24

# Custom chord window + silent mode
python duality.py --input "..." --outs "A" "B" --chord-ms 25 --no-status

# Tagged outs + Crucible (format-route)
python duality.py --input "loopMIDI Port" --outs "SC:gs" "MU:xg" --crucible

# Alchemy single-out (transcode path; conversion comes later)
python duality.py --alchemy --outs "MU128:xg" --input-format gs

# Show version
python duality.py --version
""".format(VERSION=VERSION)

import argparse
import signal
import sys
import time
from typing import List, Optional

import mido
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn
from rich.table import Table
from rich.text import Text
from rich.markup import escape

mido.set_backend("mido.backends.rtmidi")

POLY_DEFAULT = 24
CHORD_MS_DEFAULT = 30.0
FORMAT_IDLE_SEC = 60.0

# Port / stream format tags (CLI values → canonical)
FORMAT_ALIASES = {
    "gm": "gm",
    "gm2": "gm2",
    "gs": "gs",
    "xg": "xg",
    "mt32": "mt32",
    "mt-32": "mt32",
    "any": "any",
}
FORMAT_DISPLAY = {
    "gm": "GM",
    "gm2": "GM2",
    "gs": "GS",
    "xg": "XG",
    "mt32": "MT-32",
    "any": "ANY",
}
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
        crucible: bool = False,
        crucible_notes: str = "affinity",
        crucible_gm_wide: bool = False,
        input_format: str | None = None,
        scpop: bool = False,
    ):
        # Alchemy may run with a single output (transcode-only path).
        # Classic router still requires at least two ports.
        min_ports = 1 if alchemy else 2
        if len(out_names) < min_ports:
            raise ValueError(
                f"At least {min_ports} output port(s) required"
                + (" with --alchemy." if alchemy else ".")
            )

        self.mode = mode
        self.n_ports = len(out_names)
        self.chord_window = chord_window_ms / 1000.0
        self.show_status = show_status
        self.alchemy = alchemy
        self.crucible = crucible
        self.crucible_notes = crucible_notes if crucible_notes in ("affinity", "all") else "affinity"
        self.crucible_gm_wide = bool(crucible_gm_wide)

        # Per-port format tags ("any" = untagged / receive everything)
        if out_formats is None:
            self.out_formats = ["any"] * self.n_ports
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

        console.print(f"[bold cyan]Opening input[/] : {in_name}")
        self.inport = mido.open_input(in_name)

        self.outs = []
        self.port_names = out_names
        for i, name in enumerate(out_names):
            tag = self.out_formats[i]
            tag_disp = FORMAT_DISPLAY.get(tag, tag)
            console.print(
                f"[bold cyan]Opening out {i+1}[/] : {name} "
                f"(limit {self.poly_limits[i]}, format {tag_disp})"
            )
            self.outs.append(mido.open_output(name))

        self.active: dict[tuple[int, int], dict] = {}
        self.rr_next = 0
        self.last_note_time = 0.0
        self.last_chord_port: Optional[int] = None
        self.steal_count = 0
        self.start_time = time.monotonic()

        console.print(f"[green]Mode[/]          : {self.mode}")
        console.print(f"[green]Output ports[/]  : {self.n_ports}")
        console.print(f"[green]Chord window[/]  : {chord_window_ms:.0f} ms")
        if self.crucible:
            wide = ", gm-wide" if self.crucible_gm_wide else ""
            console.print(f"[green]Crucible[/]      : on (notes={self.crucible_notes}{wide})")
        if self.alchemy:
            console.print("[green]Alchemy[/]       : on (conversion not yet implemented)")
        if self.detected_format:
            console.print(f"[green]Input format[/]  : {self.detected_format} (assumed/seeded)")
        if self.scpop_forced:
            console.print("[green]SCPOP[/]         : forced on (--scpop) – broadcasting notes to format-matched ports")
        console.print(
            "[green]Ready.[/] Notes will be distributed. "
            "Ctrl+C to stop + panic. Press [bold]F[/] to clear format state.\n"
        )

    # ------------------------------------------------------------------
    
    def _set_status(self, message: str, duration: float = 5.0):
        """
        Show a temporary message in the bottom row.
        When a new message arrives, the previous one is moved into history.
        """
        now = time.monotonic()

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

    def _clear_format(self, reason: str = "manual") -> None:
        """Clear sticky session format (idle timeout, hotkey, or explicit)."""
        if self.detected_format is None and not self.scpop_mode:
            # Still acknowledge hotkey / explicit clear so the UI doesn't feel dead
            self._set_status(f"Format already clear ({reason})", duration=1.5)
            return
        prev = self.detected_format or "none"
        self.detected_format = None
        self.format_pulse_time = 0.0
        # --scpop stays armed; auto-detected SCPOP is cleared with format
        if not self.scpop_forced:
            self.scpop_mode = False
            self._set_status(f"Format cleared ({prev} → none, {reason})", duration=3.0)
        else:
            self.scpop_mode = True
            self._set_status(
                f"Format cleared ({prev} → none, {reason}); SCPOP still forced",
                duration=3.0,
            )

    def _check_format_idle(self) -> None:
        """Clear format after FORMAT_IDLE_SEC with no MIDI of any kind."""
        if self.detected_format is None:
            return
        if time.monotonic() - self.last_midi_time >= FORMAT_IDLE_SEC:
            self._clear_format("idle")

    def _port_matches_format(self, port_idx: int, fmt_display: str | None) -> bool:
        """
        True if this port should receive traffic for the given session format.
        Untagged ports are "any" and always match.
        GM always matches gm + gm2; with crucible_gm_wide, GM/GM2 also match gs + xg.
        """
        tag = self.out_formats[port_idx]
        if tag == "any":
            return True
        if fmt_display is None:
            # Unknown stream format → deliver everywhere
            return True
        stream_tag = DETECT_TO_TAG.get(fmt_display)
        if stream_tag is None:
            return True
        allowed = set(FORMAT_COMPAT.get(stream_tag, {stream_tag}))
        if self.crucible_gm_wide and stream_tag in ("gm", "gm2"):
            allowed |= {"gs", "xg"}
        return tag in allowed

    def _eligible_note_ports(self) -> list[int]:
        """Ports allowed to receive notes under current Crucible policy."""
        if not self.crucible or self.crucible_notes == "all":
            return list(range(self.n_ports))
        return [
            i for i in range(self.n_ports)
            if self._port_matches_format(i, self.detected_format)
        ]

    def _detect_format(self, msg: mido.Message) -> None:
        """
        Detect GM / GM2 / GS / XG / MT-32 from SysEx and update sticky format.
        Strong signals set or switch the session format (opposing signal switches).
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
            prev = self.detected_format
            self.detected_format = fmt
            self.format_pulse_time = time.monotonic() + 2.8
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
        self._set_status("Voice counts re-synchronized", duration=2.0)

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
            self.outs[p].send(off)
            self.voice_counts[p] = max(0, self.voice_counts[p] - 1)
        del self.active[key]
        self.steal_count += 1

    def _choose_port(self, is_chord: bool) -> int:
        counts = self.voice_counts   # fast path – no scanning
        eligible = self._eligible_note_ports()
        if not eligible:
            # No format-matched ports → fall back to all (avoid total silence)
            eligible = list(range(self.n_ports))

        if self.mode == "rr":
            # Round-robin among eligible ports only
            for _ in range(self.n_ports):
                port = self.rr_next % self.n_ports
                self.rr_next = (self.rr_next + 1) % self.n_ports
                if port in eligible:
                    return port
            return eligible[0]

        # balance mode – prefer continuing a chord (if still eligible)
        if is_chord and self.last_chord_port is not None and self.last_chord_port in eligible:
            preferred = self.last_chord_port
            limit = self.poly_limits[preferred]
            if counts[preferred] < limit:
                return preferred
            # Preferred is full → look for a meaningfully freer eligible port
            free = {i: self.poly_limits[i] - counts[i] for i in eligible}
            best_free = max(free.values())
            if free[preferred] < best_free - 1:
                for i, f in free.items():
                    if f == best_free:
                        return i

        # Classic load balance using remaining capacity among eligible
        remaining = {i: self.poly_limits[i] - counts[i] for i in eligible}
        max_remaining = max(remaining.values())
        candidates = [i for i, r in remaining.items() if r == max_remaining]

        if len(candidates) == 1:
            return candidates[0]

        # Tie → round-robin among candidates
        port = self.rr_next % self.n_ports
        self.rr_next = (self.rr_next + 1) % self.n_ports
        for c in candidates:
            if c == port:
                return c
        return candidates[0]
        
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
    def process(self, msg: mido.Message):
        # Any MIDI activity refreshes format-idle timer
        self.last_midi_time = time.monotonic()

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
                if not eligible:
                    eligible = list(range(self.n_ports))

                # SCPOP: broadcast the same note to every format-matched port.
                # After init only one SC input may produce sound, but we cannot
                # know which Duality out is Part A — broadcasting is safe.
                if self.scpop_mode:
                    targets = eligible
                else:
                    port = self._choose_port(is_chord)
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
                    self.outs[port].send(msg)
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
                        self.outs[port].send(msg)
                        self.voice_counts[port] = max(0, self.voice_counts[port] - 1)
                else:
                    for out in self.outs:
                        out.send(msg)

                # Only resync if the drift is significant
                if abs(sum(self.voice_counts) - len(self.active)) > 1:
                    self._resync_voice_counts()

            return

        if self._is_panic(msg):
            self.panic(reason=f"received {msg}")
            return

        # SysEx → detect format, describe it, show in status, and forward
        if msg.type == "sysex":
            self._detect_format(msg)
            description = self._describe_sysex(msg)

            # Suppress pure noise
            if description in ("GS SysEx", "SysEx", "GM/Universal SysEx", "XG SysEx", "MT-32 SysEx"):
                # Only show the generic message if history is empty
                if not self.status_history and not self.status_message:
                    self._set_status(description, duration=2.5)
            else:
                self._set_status(description, duration=3.5)

            # Crucible: format-specific SysEx only to matching (or any) ports
            for i, out in enumerate(self.outs):
                if self.crucible and not self._port_matches_format(i, self.detected_format):
                    continue
                out.send(msg)
            return

        # Track common controllers per channel + timestamp
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

        # Everything else → all devices, with optional deduplication
        for i, out in enumerate(self.outs):
            if self._should_send(i, msg):
                out.send(msg)

    def _is_panic(self, msg: mido.Message) -> bool:
        if msg.type == "control_change" and msg.control in (120, 123):
            return True
        if msg.type == "reset":
            return True
        return False

    def panic(self, reason: str = "manual"):
        for out in self.outs:
            out.panic()
            for ch in range(16):
                out.send(mido.Message("control_change", channel=ch, control=123, value=0))
                out.send(mido.Message("control_change", channel=ch, control=121, value=0))
        self.active.clear()
        self.voice_counts = [0] * self.n_ports          # ← add this
        self.last_chord_port = None
        self.last_sent.clear()
        self._set_status(f"PANIC ({reason}) – all devices silenced", duration=6.0)

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
            label = f"[{self.detected_format}]"
            # Pad plain label to 7 chars ([MT-32]=7) then style
            pad = " " * max(0, 7 - len(label))
            if time.monotonic() < self.format_pulse_time:
                format_badge = f" [bold {col}]{label}[/]{pad}"
            else:
                format_badge = f" [dim]{label}[/]{pad}"
        else:
            format_badge = " " * 8  # " " + 7-char field

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

            tag = self.out_formats[i]
            if tag and tag != "any":
                label = f"Port {i+1} [{FORMAT_DISPLAY.get(tag, tag)}]"
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
        mode_badges = f"{badge_crucible}{badge_alchemy}{badge_scpop}"

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

    def _poll_hotkeys(self) -> None:
        """Non-blocking keyboard poll. F = clear format state."""
        try:
            import msvcrt  # Windows
            while msvcrt.kbhit():
                ch = msvcrt.getwch()
                if ch.lower() == "f":
                    self._clear_format("hotkey")
        except ImportError:
            # Unix: best-effort non-blocking stdin (may not work under all terminals)
            try:
                import select
                if select.select([sys.stdin], [], [], 0)[0]:
                    ch = sys.stdin.read(1)
                    if ch.lower() == "f":
                        self._clear_format("hotkey")
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

                        # Format idle clear (60s with no MIDI)
                        self._check_format_idle()

                        # Hotkey: F clears sticky format state
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
                    self.panic(reason="exception")
                finally:
                    self.close()
        else:
            # No status panel – pure low-latency path
            try:
                for msg in self.inport:
                    self.process(msg)
            except Exception as e:
                console.print(f"[red]Error: {e}[/]")
                self.panic(reason="exception")
            finally:
                self.close()

    def close(self):
        try:
            self.inport.close()
        except Exception:
            pass
        for out in self.outs:
            try:
                out.close()
            except Exception:
                pass

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

def parse_out_spec(spec: str) -> tuple[str, str]:
    """
    Parse --outs entry: "Port Name" or "Port Name:gs".
    Returns (port_name, format_tag) with tag defaulting to "any".
    """
    if ":" not in spec:
        return spec, "any"
    # Split on last colon so names with colons are less likely to break
    name, _, tag = spec.rpartition(":")
    name = name.strip()
    tag = tag.strip().lower()
    if not name:
        raise ValueError(f"Invalid --outs entry (empty name): {spec!r}")
    if tag not in FORMAT_ALIASES:
        valid = ", ".join(sorted(set(FORMAT_ALIASES.values())))
        raise ValueError(f"Unknown format tag {tag!r} in {spec!r}. Valid: {valid}")
    return name, FORMAT_ALIASES[tag]


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
        "--alchemy",
        action="store_true",
        help="Enable Alchemy path (allows single output; format conversion comes in a later phase)",
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
    args = parser.parse_args()

    if args.list:
        list_ports()
        return

    inputs = mido.get_input_names()
    outputs = mido.get_output_names()

    in_name = resolve_port(args.input, inputs, "input port")

    min_ports = 1 if args.alchemy else 2
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
            out_formats.append("any")

    if len(set(out_names)) != len(out_names):
        console.print("[red]Error: all output ports must be unique.[/]")
        sys.exit(1)

    try:
        router = Duality(
            in_name=in_name,
            out_names=out_names,
            mode=args.mode,
            poly_limits=args.poly,
            chord_window_ms=args.chord_ms,
            show_status=not args.no_status,
            out_formats=out_formats,
            alchemy=args.alchemy,
            crucible=args.crucible,
            crucible_notes=args.crucible_notes,
            crucible_gm_wide=args.crucible_gm_wide,
            input_format=args.input_format,
            scpop=args.scpop,
        )
        router.run()
    except ValueError as e:
        console.print(f"[red]{e}[/]")
        sys.exit(1)

if __name__ == "__main__":
    main()
