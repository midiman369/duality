"""Roland GS / SC-8850 lookup tables for Duality.

Recognition names, insertion types, and Anima GS EFX palettes.
Tunables (idle/hold seconds, CC16 LFO rate) stay in duality.py.
"""
from __future__ import annotations

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

# SC-8850 OM "Insertion Effect List" (p.216-223): #, name, (MSB, LSB) at 40 03 00.
# The SC-88Pro has the same 64 types at the same addresses.
GS_EFX_LIST = (
    # Filter (modify the tone)
    (1, "Stereo-EQ", 0x01, 0x00),
    (2, "Spectrum", 0x01, 0x01),
    (3, "Enhancer", 0x01, 0x02),
    (4, "Humanizer", 0x01, 0x03),
    # Distortion
    (5, "Overdrive", 0x01, 0x10),
    (6, "Distortion", 0x01, 0x11),
    # Modulation
    (7, "Phaser", 0x01, 0x20),
    (8, "Auto Wah", 0x01, 0x21),
    (9, "Rotary", 0x01, 0x22),
    (10, "Stereo Flanger", 0x01, 0x23),
    (11, "Step Flanger", 0x01, 0x24),
    (12, "Tremolo", 0x01, 0x25),
    (13, "Auto Pan", 0x01, 0x26),
    # Compressor
    (14, "Compressor", 0x01, 0x30),
    (15, "Limiter", 0x01, 0x31),
    # Chorus (broaden)
    (16, "Hexa Chorus", 0x01, 0x40),
    (17, "Tremolo Chorus", 0x01, 0x41),
    (18, "Stereo Chorus", 0x01, 0x42),
    (19, "Space D", 0x01, 0x43),
    (20, "3D Chorus", 0x01, 0x44),
    # Delay / reverb
    (21, "Stereo Delay", 0x01, 0x50),
    (22, "Mod Delay", 0x01, 0x51),
    (23, "3 Tap Delay", 0x01, 0x52),
    (24, "4 Tap Delay", 0x01, 0x53),
    (25, "Tm Ctrl Delay", 0x01, 0x54),
    (26, "Reverb", 0x01, 0x55),
    (27, "Gate Reverb", 0x01, 0x56),
    (28, "3D Delay", 0x01, 0x57),
    # Pitch shift
    (29, "2 Pitch Shifter", 0x01, 0x60),
    (30, "Fb P.Shifter", 0x01, 0x61),
    # Others
    (31, "3D Auto", 0x01, 0x70),
    (32, "3D Manual", 0x01, 0x71),
    (33, "Lo-Fi 1", 0x01, 0x72),
    (34, "Lo-Fi 2", 0x01, 0x73),
    # Series 2
    (35, "OD→Chorus", 0x02, 0x00),
    (36, "OD→Flanger", 0x02, 0x01),
    (37, "OD→Delay", 0x02, 0x02),
    (38, "DS→Chorus", 0x02, 0x03),
    (39, "DS→Flanger", 0x02, 0x04),
    (40, "DS→Delay", 0x02, 0x05),
    (41, "EH→Chorus", 0x02, 0x06),
    (42, "EH→Flanger", 0x02, 0x07),
    (43, "EH→Delay", 0x02, 0x08),
    (44, "Cho→Delay", 0x02, 0x09),
    (45, "FL→Delay", 0x02, 0x0A),
    (46, "Cho→Flanger", 0x02, 0x0B),
    # Series 3/4/5
    (47, "Rotary Multi", 0x03, 0x00),
    (48, "GTR Multi 1", 0x04, 0x00),
    (49, "GTR Multi 2", 0x04, 0x01),
    (50, "GTR Multi 3", 0x04, 0x02),
    (51, "Clean Gt Multi 1", 0x04, 0x03),
    (52, "Clean Gt Multi 2", 0x04, 0x04),
    (53, "Bass Multi", 0x04, 0x05),
    (54, "Rhodes Multi", 0x04, 0x06),
    (55, "Keyboard Multi", 0x05, 0x00),
    # Parallel 2
    (56, "Cho/Delay", 0x11, 0x00),
    (57, "FL/Delay", 0x11, 0x01),
    (58, "Cho/Flanger", 0x11, 0x02),
    (59, "OD1/OD2", 0x11, 0x03),
    (60, "OD/Rotary", 0x11, 0x04),
    (61, "OD/Phaser", 0x11, 0x05),
    (62, "OD/AutoWah", 0x11, 0x06),
    (63, "PH/Rotary", 0x11, 0x07),
    (64, "PH/AutoWah", 0x11, 0x08),
)
GS_EFX_TYPES = {(0x00, 0x00): "Thru"}
GS_EFX_TYPES.update({(m, l): name for _n, name, m, l in GS_EFX_LIST})

ANIMA_EFX_GS = {
    "organ_rotary": [          # Drawbar / Perc / Rock (PC 17–19)
        (0x03, 0x00, "Rotary Multi"),
        (0x01, 0x22, "Rotary"),
    ],
    "organ_chorus": [          # Church / Reed / Accordion
        (0x01, 0x42, "Stereo Chorus"),
        (0x01, 0x43, "Space-D"),
        (0x01, 0x40, "Hexa Chorus"),
        (0x01, 0x44, "3D Chorus"),
        (0x02, 0x06, "EH→Chorus"),
    ],
    "harmonica": [
        (0x01, 0x03, "Humanizer"),
        (0x01, 0x42, "Stereo Chorus"),
        (0x01, 0x43, "Space-D"),
    ],
    "guitar_dist": [
        (0x04, 0x00, "GTR Multi 1"),
        (0x04, 0x01, "GTR Multi 2"),
        (0x04, 0x02, "GTR Multi 3"),
        (0x11, 0x03, "OD1/OD2"),
        (0x01, 0x10, "Overdrive"),
        (0x01, 0x11, "Distortion"),
    ],
    "guitar_mute": [
        (0x11, 0x08, "PH/Auto Wah"),
        (0x02, 0x08, "EH→Delay"),
        (0x04, 0x04, "C.Gt Multi 2"),
    ],
    "guitar_clean": [
        (0x04, 0x03, "C.Gt Multi 1"),
        (0x11, 0x02, "Cho/Flanger"),
        (0x02, 0x08, "EH→Delay"),
        (0x04, 0x04, "C.Gt Multi 2"),  # ~25% of seed rolls
    ],
    "guitar_acoustic": [
        (0x01, 0x02, "Enhancer"),
        (0x02, 0x06, "EH→Chorus"),
        (0x02, 0x08, "EH→Delay"),
        (0x04, 0x03, "C.Gt Multi 1"),
    ],
    "plucked": [
        (0x01, 0x02, "Enhancer"),
        (0x02, 0x06, "EH→Chorus"),
        (0x02, 0x08, "EH→Delay"),
    ],
    "ep_rhodes": [
        (0x05, 0x00, "Keyboard Multi"),
        (0x04, 0x06, "Rhodes Multi"),
        (0x01, 0x41, "Tremolo Chorus"),
        (0x01, 0x20, "Phaser"),
    ],
    "ep_dx": [
        (0x04, 0x06, "Rhodes Multi"),
        (0x01, 0x41, "Tremolo Chorus"),
        (0x01, 0x20, "Phaser"),
    ],
    "keys_pluck": [
        (0x05, 0x00, "Keyboard Multi"),
        (0x01, 0x20, "Phaser"),
        (0x04, 0x06, "Rhodes Multi"),
    ],
    "lead": [
        (0x01, 0x42, "Stereo Chorus"),
        (0x01, 0x43, "Space-D"),
        (0x01, 0x23, "Stereo Flanger"),
        (0x01, 0x20, "Phaser"),
        (0x01, 0x50, "Stereo Delay"),
        (0x11, 0x00, "Cho/Delay"),
        (0x11, 0x01, "FL/Delay"),
        (0x01, 0x40, "Hexa Chorus"),
        (0x01, 0x10, "Overdrive"),   # has EFX Pan; Drive is lowered for leads
        (0x01, 0x11, "Distortion"),
    ],
    "ethnic_wind": [
        (0x01, 0x50, "Stereo Delay"),
        (0x01, 0x55, "Reverb"),
        (0x11, 0x00, "Cho/Delay"),
        (0x01, 0x51, "Mod Delay"),
        (0x01, 0x43, "Space-D"),
    ],

    "bass_acoustic": [
        (0x01, 0x42, "Stereo Chorus"),
        (0x01, 0x43, "Space-D"),
        (0x01, 0x02, "Enhancer"),
    ],
    "bass_electric": [
        (0x04, 0x05, "Bass Multi"),
    ],
    "bass_wide": [
        (0x01, 0x42, "Stereo Chorus"),
        (0x01, 0x43, "Space-D"),
        (0x01, 0x02, "Enhancer"),
        (0x02, 0x06, "EH→Chorus"),
    ],
    "orch_brass": [
        (0x01, 0x02, "Enhancer"),
        (0x01, 0x55, "Reverb"),
        (0x01, 0x00, "Stereo-EQ"),
    ],
    "synth_brass": [
        (0x01, 0x42, "Stereo Chorus"),
        (0x01, 0x43, "Space-D"),
        (0x01, 0x23, "Stereo Flanger"),
        (0x01, 0x20, "Phaser"),
        (0x01, 0x50, "Stereo Delay"),
        (0x11, 0x00, "Cho/Delay"),
    ],
    "strings": [               # sustained: no delay (feedback piled up the ONESTOP ending)
        (0x01, 0x42, "Stereo Chorus"),
        (0x01, 0x43, "Space-D"),
        (0x01, 0x44, "3D Chorus"),
    ],
    "pad": [
        (0x01, 0x43, "Space-D"),
        (0x01, 0x42, "Stereo Chorus"),
        (0x01, 0x44, "3D Chorus"),
    ],
    "piano_acoustic": [
        (0x01, 0x00, "Stereo-EQ"),
        (0x01, 0x44, "3D Chorus"),
        (0x01, 0x43, "Space-D"),
    ],
    "chromatic": [             # Honky / celesta / vibes / marimba / xylophone
        (0x01, 0x20, "Phaser"),
        (0x01, 0x00, "Stereo-EQ"),
        (0x01, 0x02, "Enhancer"),
        (0x01, 0x43, "Space-D"),
    ],
    "fx": [                    # Rain / soundtrack / crystal / atmosphere
        (0x01, 0x43, "Space-D"),
        (0x01, 0x44, "3D Chorus"),
        (0x01, 0x40, "Hexa Chorus"),  # FX 1-8 are mostly pads; no delay
        (0x01, 0x42, "Stereo Chorus"),
    ],
}
ANIMA_EFX_PRIORITY = (
    "guitar_dist", "guitar_mute", "guitar_clean", "guitar_acoustic",
    "organ_rotary", "harmonica", "organ_chorus", "plucked", "ep_rhodes", "ep_dx", "keys_pluck",
    "lead", "ethnic_wind", "synth_brass", "orch_brass", "bass_electric",
    "strings", "pad", "bass_wide", "bass_acoustic", "piano_acoustic",
    "chromatic", "fx",
)
# Dual-guitar parallel split (SC-8850 #59 OD1/OD2)
ANIMA_SPLIT_MSB, ANIMA_SPLIT_LSB = 0x11, 0x03
ANIMA_SPLIT_LABEL = "OD1/OD2"
ANIMA_SPLIT_PAN_LO = 40   # CC10 ≤ this counts as already-left
ANIMA_SPLIT_PAN_HI = 88   # CC10 ≥ this counts as already-right
# Drive at P1 (40 03 03): Overdrive, Distortion, OD→ and DS→ series.
ANIMA_EFX_DRIVE_03 = frozenset({
    (0x01, 0x10), (0x01, 0x11),
    (0x02, 0x00), (0x02, 0x01), (0x02, 0x02),
    (0x02, 0x03), (0x02, 0x04), (0x02, 0x05),
})
ANIMA_EFX_WAH = frozenset({
    (0x04, 0x02),  # GTR Multi 3
    (0x04, 0x04),  # C.Gt Multi 2
    (0x01, 0x21),  # Auto Wah
    (0x11, 0x06),  # OD/Auto Wah
    (0x11, 0x08),  # PH/Auto Wah
})
ANIMA_EFX_ROTARY = frozenset({
    (0x03, 0x00),  # Rotary Multi
    (0x01, 0x22),  # Rotary
    (0x11, 0x04),  # OD/Rotary
    (0x11, 0x07),  # PH/Rotary
})
# Wah Manual address per type (the base the CC16 LFO swings around).
ANIMA_EFX_WAH_MAN = {
    (0x04, 0x02): 0x04,  # GTR Multi 3: + Wah Man
    (0x04, 0x04): 0x04,  # Clean Gt Multi 2: + AW Man
    (0x01, 0x21): 0x05,  # Auto Wah: + Manual
    (0x11, 0x06): 0x0A,  # OD/AutoWah: # AW Man
    (0x11, 0x08): 0x0A,  # PH/AutoWah: # AW Man
}
# Types whose wah/rotary-speed knob is on EFX Control 2 (# in the OM list);
# their Control 1 (+) is OD Drive or PH Rate, which CC16 must not move.
ANIMA_EFX_CTRL2 = frozenset({
    (0x03, 0x00),  # Rotary Multi: + OD Drive, # RT Speed
    (0x11, 0x04),  # OD/Rotary:    + OD Drive, # RT Speed
    (0x11, 0x07),  # PH/Rotary:    + PH Rate,  # RT Speed
    (0x11, 0x06),  # OD/AutoWah:   + OD Drive, # AW Man
    (0x11, 0x08),  # PH/AutoWah:   + PH Rate,  # AW Man
})
ANIMA_HETFIELD_PC = frozenset(range(29, 31))  # OD / Distortion – down only

# File insertion types that mean "this clean guitar is actually dirty"
ANIMA_FILE_DIRT_TYPES = frozenset({
    (0x01, 0x10), (0x01, 0x11),           # Overdrive / Distortion
    (0x02, 0x00), (0x02, 0x01), (0x02, 0x02),  # OD→Chorus/Flanger/Delay
    (0x02, 0x03), (0x02, 0x04), (0x02, 0x05),  # DS→Chorus/Flanger/Delay
    (0x04, 0x00), (0x04, 0x01), (0x04, 0x02),  # GTR Multi 1–3
    (0x11, 0x03), (0x11, 0x04), (0x11, 0x05), (0x11, 0x06),  # OD1/OD2 + OD combos
})
ANIMA_FILE_DIRT_FAMS = frozenset({
    "guitar_clean", "guitar_acoustic", "guitar_mute",
})

# EFX types with a Pan parameter (SC-8850 param index 1-based → address 40 03 03+n)
# Overdrive / Distortion (OM p.91): P1 Drive, P2 Amp Type, P19 Output Pan (40 03 15).
ANIMA_EFX_PAN_SLOT = {
    (0x01, 0x10): 19,
    (0x01, 0x11): 19,
}
# Mono signature types: at most one live copy across all GS ports.
ANIMA_EFX_EXCLUSIVE = frozenset({
    (0x04, 0x00),  # GTR Multi 1
    (0x04, 0x01),  # GTR Multi 2
    (0x04, 0x02),  # GTR Multi 3
})


# Per-type EFX Parameter index (1-based → address 40 03 03+(n-1)).
# Phase 1: the knobs we already touch. Fill the rest from OM p.91–128 / list p.216.
GS_EFX_PARAMS = {
    # #53 Bass Multi (04 05) — OM p.118
    (0x04, 0x05): {
        "Cmp Atck": 1,
        "Cmp Sus": 2,
        "Cmp Level": 3,
        "Cmp Sw": 4,
        "OD Sel": 5,
        "OD Drive": 6,     # default 48; F.Bass/Harm wants ~16
        "OD Amp": 7,
        "OD Amp Sw": 8,
        "OD Sw": 9,
        "EQ L Gain": 10,
        "EQ M Fq": 11,
        "EQ M Q": 12,
        "EQ M Gain": 13,
        "EQ H Gain": 14,
        "CF Sel": 15,
        "CF Rate": 16,
        "CF Depth": 17,
        "CF Fb": 18,
        "CF Mix": 19,
        "Level": 20,
    },
    # #05 Overdrive / #06 Distortion — OM: P1 Drive, P2 Amp Type, P19 Pan
    (0x01, 0x10): {"Drive": 1, "Amp Type": 2, "Amp Sw": 3, "Pan": 19},
    (0x01, 0x11): {"Drive": 1, "Amp Type": 2, "Amp Sw": 3, "Pan": 19},
}
