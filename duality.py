#!/usr/bin/env python3
VERSION = "0.9.4"

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
• Redundant controller filtering (keeps devices in sync while reducing traffic)
• Arbitrary number of output ports (default 2)

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

mido.set_backend("mido.backends.rtmidi")

POLY_DEFAULT = 24
CHORD_MS_DEFAULT = 30.0

# ----------------------------------------------------------------------
# GS recognition tables
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
    ):
        if len(out_names) < 2:
            raise ValueError("At least two output ports are required.")

        self.mode = mode
        self.n_ports = len(out_names)
        self.chord_window = chord_window_ms / 1000.0
        self.show_status = show_status

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
        self.status_history: list[tuple[float, str]] = []   # (timestamp, message)
        self.STATUS_HISTORY_MAX = 6
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
            console.print(f"[bold cyan]Opening out {i+1}[/] : {name} (limit {self.poly_limits[i]})")
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
        console.print("[green]Ready.[/] Notes will be distributed. Ctrl+C to stop + panic.\n")

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
            display = msg if len(msg) <= 26 else msg[:23] + "…"
            lines.append(f"[{style}]{display}[/]")

        if not lines:
            return Text("")

        return Text.from_markup("\n".join(lines))

    def _detect_format(self, msg: mido.Message) -> None:
        """
        Detect GM / GM2 / GS / XG / MT-32 from SysEx and light the format badge.
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

        if fmt:
            self.detected_format = fmt
            self.format_pulse_time = time.monotonic() + 2.8
            # Optional short status message (comment out if you prefer quieter)
            #self._set_status(f"Detected {fmt}", duration=2.0)
          
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

            # Delay (generic for now)
            if aa == 0x40 and bb == 0x01 and 0x40 <= cc <= 0x4F:
                return "GS Delay"

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

            return "GS SysEx"

        # Fallbacks
        if data[0] == 0x7E:
            return "GM/Universal SysEx"
        if data[0] == 0x43:
            return "XG SysEx"
        if data[0] == 0x41 and len(data) >= 3 and data[2] == 0x16:
            return "MT-32 SysEx"

        return "SysEx"
  
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
            if info["port"] == port:
                candidates.append((info.get("velocity", 64), info["time"], key))

        if not candidates:
            return

        # Sort by velocity (ascending), then by time (ascending = oldest first)
        candidates.sort()

        # Steal the first one (quietest, then oldest)
        _, _, key = candidates[0]
        ch, note = key

        off = mido.Message("note_off", channel=ch, note=note, velocity=0)
        self.outs[port].send(off)
        del self.active[key]
        self.voice_counts[port] = max(0, self.voice_counts[port] - 1)
        self.steal_count += 1

    def _choose_port(self, is_chord: bool) -> int:
        counts = self.voice_counts   # fast path – no scanning

        if self.mode == "rr":
            port = self.rr_next
            self.rr_next = (self.rr_next + 1) % self.n_ports
            return port

        # balance mode – prefer continuing a chord
        if is_chord and self.last_chord_port is not None:
            preferred = self.last_chord_port
            limit = self.poly_limits[preferred]
            if counts[preferred] < limit:
                return preferred
            # Preferred is full → look for a meaningfully freer port
            free = [lim - c for lim, c in zip(self.poly_limits, counts)]
            best_free = max(free)
            if free[preferred] < best_free - 1:
                return free.index(best_free)

        # Classic load balance using remaining capacity
        remaining = [lim - c for lim, c in zip(self.poly_limits, counts)]
        max_remaining = max(remaining)
        candidates = [i for i, r in enumerate(remaining) if r == max_remaining]

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

                port = self._choose_port(is_chord)
                self.last_chord_port = port

                # Real count for this port (more reliable than the running counter)
                real_count = sum(1 for info in self.active.values() if info["port"] == port)

                if real_count >= self.poly_limits[port]:
                    self._steal_least_important(port)

                # Re-check after possible steal
                real_count = sum(1 for info in self.active.values() if info["port"] == port)
                if real_count >= self.poly_limits[port]:
                    self.drop_count += 1
                    return          # still full → drop the new note

                self.active[key] = {
                    "port": port,
                    "time": now,
                    "velocity": msg.velocity
                }
                self.voice_counts[port] += 1
                self.outs[port].send(msg)

                # Update peak
                total_now = sum(self.voice_counts)
                if total_now > self.peak_voices:
                    self.peak_voices = total_now
            else:
                # Note Off
                info = self.active.pop(key, None)
                if info is not None:
                    port = info["port"]
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

            for out in self.outs:
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
        bar_width = max(24, term_width - 26)   #was 36 # was -42, now more aggressive

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

        # Activity pulse – always present so layout stays stable
        if time.monotonic() - self.last_activity_time < 0.15:
            pulse = "  [bold bright_green]♪[/]"
        else:
            pulse = "  [dim]♪[/]"          # grayed-out residual

        # Format badge / pulse
        format_badge = ""
        if self.detected_format:
            colours = {
                "GM": "bright_cyan",
                "GM2": "bright_cyan",
                "GS": "bright_magenta",
                "XG": "bright_yellow",
                "MT-32": "bright_red",
            }
            col = colours.get(self.detected_format, "white")
            if time.monotonic() < self.format_pulse_time:
                # Bright while the pulse is active
                format_badge = f"  [bold {col}][{self.detected_format}][/]"
            else:
                # Dim residual so you can still see the last format
                format_badge = f"  [dim][{self.detected_format}][/]"

        # If the bottom status message has just expired, move it into history
        now = time.monotonic()
        if self.status_message and now >= self.status_message_time:
            self.status_history.insert(0, (now, self.status_message))
            self.status_history = self.status_history[: self.STATUS_HISTORY_MAX]
            self.status_message = ""

        # --- Port bars ---
        table = Table(show_header=False, box=None, padding=(0, 1), expand=True)
        table.add_column("label", style="cyan", width=8, no_wrap=True)   # slightly tighter
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

            table.add_row(
                f"Port {i+1}",
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

        channel_table = Table(show_header=False, box=None, padding=(0, 1), expand=True)
        channel_table.add_column("label", style="cyan", width=14, no_wrap=True)
        channel_table.add_column("values", ratio=1)
        channel_table.add_row("MIDI Channel", Text.from_markup(sep.join(ch_num_parts)))
        channel_table.add_row("Voice Count",  Text.from_markup(sep.join(voice_parts)))
        channel_table.add_row("Vol",          Text.from_markup(sep.join(vol_parts)))
        channel_table.add_row("Pan",          Text.from_markup(sep.join(pan_parts)))
        channel_table.add_row("Mod",          Text.from_markup(sep.join(mod_parts)))
        channel_table.add_row("Pitch",        Text.from_markup(sep.join(pitch_parts)))

        # Header
        header = Text.from_markup(
            f"[bold]Live Status[/] • "
            f"Total: [bold]{total:3d}[/] • Peak: [bold]{self.peak_voices:3d}[/] • "
            f"Util: [bold]{util_pct:2d}%[/] • "
            f"Drops: {self.drop_count} • Steals: {self.steal_count} • Filtered: {self.filtered_count}"
            f"{pulse}{format_badge}"
        )

        # Footer
        if self.last_chord_port is not None:
            chord_text = (
                f"Last Chord Size: {self.current_chord_size} "
                f"(Peak {self.peak_chord_size}) → Port {self.last_chord_port + 1}"
            )
        else:
            chord_text = f"Last Chord Size: {self.current_chord_size} (Peak {self.peak_chord_size})"

        footer = Text.from_markup(
            f"[dim]{chord_text}     Last Activity: {last_activity}[/]"
        )

        # Status message row (auto-clears)
        status_line = Text("")
        if self.status_message and time.monotonic() < self.status_message_time:
            status_line = Text.from_markup(f"[bold yellow]{self.status_message}[/]")
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

            # 2. Labelled footer (Chord / Activity)
            footer_row = Text.from_markup(
                f"[cyan]More Stats:[/]   [dim]{chord_text}   Last Activity: {last_activity}[/]"
            )
            left_column.add_row(footer_row)

            # 3. Labelled status message (can wrap)
            if self.status_message and time.monotonic() < self.status_message_time:
                # Allow wrapping for longer messages
                status_row = Text.from_markup(
                    f"[cyan]Status Message:[/]   [bold yellow]{self.status_message}[/]"
                )
            else:
                status_row = Text.from_markup("[cyan]Status Message:[/]   [dim]—[/]")
                self.status_message = ""
            left_column.add_row(status_row)

            # History panel – height 9 now matches the taller left column
            history_panel = Panel(
                history_text if str(history_text).strip() else Text(" "),
                border_style="bright_blue",
                padding=(0, 0),
                height=9,
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
        help="MIDI output port names (minimum 2). Example: --outs \"Dev A\" \"Dev B\"",
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

    if args.outs:
        if len(args.outs) < 2:
            console.print("[red]Error: at least two output ports are required.[/]")
            sys.exit(1)
        out_names = [resolve_port(name, outputs, f"output port '{name}'") for name in args.outs]
    else:
        # Interactive – always default to exactly 2 ports
        console.print("\n[cyan]No --outs provided → interactive setup for 2 ports[/]")
        out_names = []
        for i in range(2):
            name = pick_port(outputs, f"Select output device {i+1} of 2:")
            while name in out_names:
                console.print("[yellow]That port is already selected.[/]")
                name = pick_port(outputs, f"Select output device {i+1} of 2:")
            out_names.append(name)

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
        )
        router.run()
    except ValueError as e:
        console.print(f"[red]{e}[/]")
        sys.exit(1)

if __name__ == "__main__":
    main()
