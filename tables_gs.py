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
    # SC-8850 Insertion list #47–55 (manual: 47 Rotary = 03 00, 48 GTR Multi 1 = 04 00)
    (0x03, 0x00): "Rotary Multi",      # #47
    (0x04, 0x00): "GTR Multi 1",       # #48
    (0x04, 0x01): "GTR Multi 2",       # #49
    (0x04, 0x02): "GTR Multi 3",       # #50
    (0x04, 0x03): "Clean Gt Multi 1",  # #51
    (0x04, 0x04): "Clean Gt Multi 2",  # #52
    (0x04, 0x05): "Bass Multi",        # #53
    (0x04, 0x06): "EP Multi",      # #54
    (0x05, 0x00): "Keyboard Multi",    # #55
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
        (0x02, 0x08, "Enh→Chorus"),
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
    ],
    "guitar_mute": [
        (0x11, 0x08, "PH/Auto Wah"),
        (0x02, 0x0A, "Enh→Delay"),
        (0x04, 0x04, "C.Gt Multi 2"),
    ],
    "guitar_clean": [
        (0x04, 0x03, "C.Gt Multi 1"),
        (0x11, 0x02, "Cho/Flanger"),
        (0x02, 0x0A, "Enh→Delay"),
        (0x04, 0x04, "C.Gt Multi 2"),  # ~25% of seed rolls
    ],
    "guitar_acoustic": [
        (0x01, 0x02, "Enhancer"),
        (0x02, 0x08, "Enh→Chorus"),
        (0x02, 0x0A, "Enh→Delay"),
        (0x04, 0x03, "C.Gt Multi 1"),
    ],
    "plucked": [
        (0x01, 0x02, "Enhancer"),
        (0x02, 0x08, "Enh→Chorus"),
        (0x02, 0x0A, "Enh→Delay"),
    ],
    "ep_rhodes": [
        (0x05, 0x00, "Keyboard Multi"),
        (0x04, 0x06, "EP Multi"),
        (0x01, 0x41, "Tremolo Chorus"),
        (0x01, 0x20, "Phaser"),
    ],
    "ep_dx": [
        (0x04, 0x06, "EP Multi"),
        (0x01, 0x41, "Tremolo Chorus"),
        (0x01, 0x20, "Phaser"),
    ],
    "keys_pluck": [
        (0x05, 0x00, "Keyboard Multi"),
        (0x01, 0x20, "Phaser"),
        (0x04, 0x06, "EP Multi"),
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
        (0x01, 0x10, "Overdrive"),   # has EFX Pan — last resort
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
    "strings": [
        (0x01, 0x42, "Stereo Chorus"),
        (0x01, 0x43, "Space-D"),
        (0x01, 0x50, "Stereo Delay"),
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
}
ANIMA_EFX_PRIORITY = (
    "guitar_dist", "guitar_mute", "guitar_clean", "guitar_acoustic",
    "organ_rotary", "harmonica", "organ_chorus", "plucked", "ep_rhodes", "ep_dx", "keys_pluck",
    "lead", "ethnic_wind", "synth_brass", "orch_brass", "bass_electric", "strings", "pad", "bass_wide", "bass_acoustic", "piano_acoustic",
)
# Dual-guitar parallel split (SC-8850 #59 OD1/OD2)
ANIMA_SPLIT_MSB, ANIMA_SPLIT_LSB = 0x11, 0x03
ANIMA_SPLIT_LABEL = "OD1/OD2"
ANIMA_SPLIT_PAN_LO = 8    # CC10 ≤ this counts as already-left
ANIMA_SPLIT_PAN_HI = 119  # CC10 ≥ this counts as already-right
ANIMA_EFX_DRIVE_03 = frozenset({
    (0x01, 0x10), (0x01, 0x11),
    (0x02, 0x00), (0x02, 0x01), (0x02, 0x02), (0x02, 0x03),
    (0x02, 0x04), (0x02, 0x05), (0x02, 0x06), (0x02, 0x07),
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
ANIMA_HETFIELD_PC = frozenset(range(29, 31))  # OD / Distortion – down only

# File insertion types that mean "this clean guitar is actually dirty"
ANIMA_FILE_DIRT_TYPES = frozenset({
    (0x01, 0x10), (0x01, 0x11),           # Overdrive / Distortion
    (0x02, 0x00), (0x02, 0x01), (0x02, 0x02), (0x02, 0x03),
    (0x02, 0x04), (0x02, 0x05), (0x02, 0x06), (0x02, 0x07),
    (0x04, 0x00), (0x04, 0x01), (0x04, 0x02),  # GTR Multi 1–3
    (0x11, 0x03), (0x11, 0x04), (0x11, 0x05), (0x11, 0x06),  # OD1/OD2 + OD combos
})
ANIMA_FILE_DIRT_FAMS = frozenset({
    "guitar_clean", "guitar_acoustic", "guitar_mute",
})

# EFX types with a Pan parameter (SC-8850 param index 1-based → address 40 03 03+n)
# Overdrive / Distortion: P1 Drive, P2 Pan
ANIMA_EFX_PAN_SLOT = {
    (0x01, 0x10): 2,
    (0x01, 0x11): 2,
}
