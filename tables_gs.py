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

# Anima GS palettes, chosen per family with the EFX Palettes picker (2026-09).
# Row = (MSB, LSB, name, weight). Weight 2 = normal, 4 = favoured, 1 = less often.
ANIMA_EFX_GS = {
    "guitar_dist": [
        (0x01, 0x10, "Overdrive", 4),  # #5
        (0x01, 0x11, "Distortion", 4),  # #6
        (0x02, 0x00, "OD→Chorus", 2),  # #35
        (0x02, 0x01, "OD→Flanger", 2),  # #36
        (0x02, 0x02, "OD→Delay", 2),  # #37
        (0x02, 0x03, "DS→Chorus", 2),  # #38
        (0x02, 0x04, "DS→Flanger", 2),  # #39
        (0x02, 0x05, "DS→Delay", 2),  # #40
        (0x04, 0x00, "GTR Multi 1", 2),  # #48
        (0x04, 0x01, "GTR Multi 2", 1),  # #49
        (0x04, 0x02, "GTR Multi 3", 2),  # #50
        (0x11, 0x03, "OD1/OD2", 4),  # #59
    ],
    "guitar_mute": [
        (0x01, 0x10, "Overdrive", 2),  # #5
        (0x01, 0x20, "Phaser", 2),  # #7
        (0x01, 0x21, "Auto Wah", 2),  # #8
        (0x01, 0x22, "Rotary", 2),  # #9
        (0x01, 0x23, "Stereo Flanger", 2),  # #10
        (0x01, 0x30, "Compressor", 2),  # #14
        (0x01, 0x41, "Tremolo Chorus", 2),  # #17
        (0x01, 0x42, "Stereo Chorus", 2),  # #18
        (0x01, 0x50, "Stereo Delay", 4),  # #21
        (0x01, 0x52, "3 Tap Delay", 1),  # #23
        (0x01, 0x53, "4 Tap Delay", 1),  # #24
        (0x01, 0x54, "Tm Ctrl Delay", 4),  # #25
        (0x01, 0x57, "3D Delay", 1),  # #28
        (0x02, 0x06, "EH→Chorus", 2),  # #41
        (0x02, 0x07, "EH→Flanger", 2),  # #42
        (0x02, 0x08, "EH→Delay", 2),  # #43
        (0x02, 0x09, "Cho→Delay", 2),  # #44
        (0x02, 0x0A, "FL→Delay", 2),  # #45
        (0x02, 0x0B, "Cho→Flanger", 2),  # #46
        (0x04, 0x03, "Clean Gt Multi 1", 2),  # #51
        (0x04, 0x04, "Clean Gt Multi 2", 2),  # #52
        (0x11, 0x00, "Cho/Delay", 2),  # #56
        (0x11, 0x01, "FL/Delay", 2),  # #57
        (0x11, 0x02, "Cho/Flanger", 2),  # #58
        (0x11, 0x07, "PH/Rotary", 2),  # #63
        (0x11, 0x08, "PH/AutoWah", 2),  # #64
    ],
    "guitar_clean": [
        (0x01, 0x20, "Phaser", 2),  # #7
        (0x01, 0x21, "Auto Wah", 2),  # #8
        (0x01, 0x22, "Rotary", 1),  # #9
        (0x01, 0x23, "Stereo Flanger", 2),  # #10
        (0x01, 0x24, "Step Flanger", 2),  # #11
        (0x01, 0x25, "Tremolo", 1),  # #12
        (0x01, 0x30, "Compressor", 2),  # #14
        (0x01, 0x40, "Hexa Chorus", 2),  # #16
        (0x01, 0x41, "Tremolo Chorus", 1),  # #17
        (0x01, 0x42, "Stereo Chorus", 2),  # #18
        (0x01, 0x43, "Space D", 1),  # #19
        (0x01, 0x44, "3D Chorus", 2),  # #20
        (0x01, 0x50, "Stereo Delay", 2),  # #21
        (0x01, 0x51, "Mod Delay", 2),  # #22
        (0x01, 0x52, "3 Tap Delay", 1),  # #23
        (0x01, 0x53, "4 Tap Delay", 1),  # #24
        (0x01, 0x54, "Tm Ctrl Delay", 2),  # #25
        (0x01, 0x57, "3D Delay", 2),  # #28
        (0x01, 0x60, "2 Pitch Shifter", 1),  # #29
        (0x01, 0x61, "Fb P.Shifter", 1),  # #30
        (0x02, 0x06, "EH→Chorus", 2),  # #41
        (0x02, 0x07, "EH→Flanger", 2),  # #42
        (0x02, 0x08, "EH→Delay", 2),  # #43
        (0x02, 0x09, "Cho→Delay", 2),  # #44
        (0x02, 0x0A, "FL→Delay", 2),  # #45
        (0x02, 0x0B, "Cho→Flanger", 2),  # #46
        (0x03, 0x00, "Rotary Multi", 1),  # #47
        (0x04, 0x03, "Clean Gt Multi 1", 1),  # #51
        (0x04, 0x04, "Clean Gt Multi 2", 1),  # #52
        (0x04, 0x06, "Rhodes Multi", 2),  # #54
        (0x05, 0x00, "Keyboard Multi", 1),  # #55
        (0x11, 0x00, "Cho/Delay", 2),  # #56
        (0x11, 0x01, "FL/Delay", 2),  # #57
        (0x11, 0x02, "Cho/Flanger", 2),  # #58
        (0x11, 0x07, "PH/Rotary", 2),  # #63
        (0x11, 0x08, "PH/AutoWah", 2),  # #64
    ],
    "guitar_acoustic": [
        (0x01, 0x00, "Stereo-EQ", 2),  # #1
        (0x01, 0x02, "Enhancer", 4),  # #3
        (0x01, 0x56, "Gate Reverb", 2),  # #27
        (0x02, 0x06, "EH→Chorus", 2),  # #41
        (0x02, 0x07, "EH→Flanger", 2),  # #42
        (0x02, 0x08, "EH→Delay", 2),  # #43
        (0x04, 0x03, "Clean Gt Multi 1", 1),  # #51
    ],
    "organ_rotary": [
        (0x01, 0x22, "Rotary", 2),  # #9
        (0x01, 0x41, "Tremolo Chorus", 2),  # #17
        (0x03, 0x00, "Rotary Multi", 2),  # #47
        (0x11, 0x04, "OD/Rotary", 2),  # #60
    ],
    "harmonica": [
        (0x01, 0x02, "Enhancer", 4),  # #3
        (0x01, 0x03, "Humanizer", 4),  # #4
        (0x01, 0x20, "Phaser", 2),  # #7
        (0x01, 0x21, "Auto Wah", 2),  # #8
        (0x01, 0x30, "Compressor", 2),  # #14
        (0x01, 0x40, "Hexa Chorus", 2),  # #16
        (0x01, 0x41, "Tremolo Chorus", 2),  # #17
        (0x01, 0x42, "Stereo Chorus", 2),  # #18
        (0x01, 0x43, "Space D", 2),  # #19
        (0x01, 0x44, "3D Chorus", 2),  # #20
        (0x01, 0x56, "Gate Reverb", 2),  # #27
        (0x01, 0x57, "3D Delay", 2),  # #28
        (0x01, 0x60, "2 Pitch Shifter", 2),  # #29
        (0x01, 0x70, "3D Auto", 2),  # #31
        (0x01, 0x72, "Lo-Fi 1", 2),  # #33
    ],
    "organ_chorus": [
        (0x01, 0x02, "Enhancer", 2),  # #3
        (0x01, 0x40, "Hexa Chorus", 2),  # #16
        (0x01, 0x42, "Stereo Chorus", 2),  # #18
        (0x01, 0x43, "Space D", 2),  # #19
        (0x01, 0x55, "Reverb", 2),  # #26
        (0x01, 0x56, "Gate Reverb", 2),  # #27
        (0x01, 0x57, "3D Delay", 2),  # #28
        (0x02, 0x06, "EH→Chorus", 2),  # #41
    ],
    "plucked": [
        (0x01, 0x02, "Enhancer", 2),  # #3
        (0x01, 0x22, "Rotary", 1),  # #9
        (0x01, 0x23, "Stereo Flanger", 2),  # #10
        (0x01, 0x41, "Tremolo Chorus", 1),  # #17
        (0x01, 0x43, "Space D", 2),  # #19
        (0x01, 0x50, "Stereo Delay", 2),  # #21
        (0x01, 0x55, "Reverb", 2),  # #26
        (0x01, 0x56, "Gate Reverb", 2),  # #27
        (0x01, 0x60, "2 Pitch Shifter", 1),  # #29
        (0x02, 0x06, "EH→Chorus", 2),  # #41
        (0x02, 0x08, "EH→Delay", 2),  # #43
        (0x02, 0x09, "Cho→Delay", 2),  # #44
    ],
    "ep_rhodes": [
        (0x01, 0x20, "Phaser", 2),  # #7
        (0x01, 0x40, "Hexa Chorus", 2),  # #16
        (0x01, 0x41, "Tremolo Chorus", 2),  # #17
        (0x01, 0x42, "Stereo Chorus", 2),  # #18
        (0x01, 0x43, "Space D", 2),  # #19
        (0x01, 0x44, "3D Chorus", 2),  # #20
        (0x01, 0x70, "3D Auto", 2),  # #31
        (0x01, 0x72, "Lo-Fi 1", 2),  # #33
        (0x01, 0x73, "Lo-Fi 2", 2),  # #34
        (0x02, 0x06, "EH→Chorus", 2),  # #41
        (0x02, 0x07, "EH→Flanger", 2),  # #42
        (0x02, 0x0B, "Cho→Flanger", 2),  # #46
        (0x04, 0x06, "Rhodes Multi", 4),  # #54
        (0x11, 0x00, "Cho/Delay", 2),  # #56
        (0x11, 0x01, "FL/Delay", 2),  # #57
        (0x11, 0x02, "Cho/Flanger", 2),  # #58
        (0x11, 0x07, "PH/Rotary", 2),  # #63
        (0x11, 0x08, "PH/AutoWah", 2),  # #64
    ],
    "ep_dx": [
        (0x01, 0x23, "Stereo Flanger", 2),  # #10
        (0x01, 0x41, "Tremolo Chorus", 2),  # #17
        (0x01, 0x42, "Stereo Chorus", 2),  # #18
        (0x01, 0x44, "3D Chorus", 2),  # #20
        (0x01, 0x51, "Mod Delay", 2),  # #22
        (0x01, 0x70, "3D Auto", 2),  # #31
        (0x02, 0x0B, "Cho→Flanger", 2),  # #46
        (0x04, 0x06, "Rhodes Multi", 2),  # #54
        (0x05, 0x00, "Keyboard Multi", 4),  # #55
        (0x11, 0x02, "Cho/Flanger", 2),  # #58
    ],
    "keys_pluck": [
        (0x01, 0x02, "Enhancer", 4),  # #3
        (0x01, 0x03, "Humanizer", 2),  # #4
        (0x01, 0x20, "Phaser", 2),  # #7
        (0x01, 0x21, "Auto Wah", 2),  # #8
        (0x01, 0x23, "Stereo Flanger", 1),  # #10
        (0x01, 0x24, "Step Flanger", 1),  # #11
        (0x01, 0x30, "Compressor", 2),  # #14
        (0x01, 0x41, "Tremolo Chorus", 1),  # #17
        (0x01, 0x56, "Gate Reverb", 4),  # #27
        (0x04, 0x06, "Rhodes Multi", 1),  # #54
        (0x05, 0x00, "Keyboard Multi", 1),  # #55
    ],
    "lead": [
        (0x01, 0x10, "Overdrive", 1),  # #5
        (0x01, 0x11, "Distortion", 1),  # #6
        (0x01, 0x20, "Phaser", 2),  # #7
        (0x01, 0x23, "Stereo Flanger", 2),  # #10
        (0x01, 0x24, "Step Flanger", 1),  # #11
        (0x01, 0x40, "Hexa Chorus", 2),  # #16
        (0x01, 0x42, "Stereo Chorus", 2),  # #18
        (0x01, 0x44, "3D Chorus", 2),  # #20
        (0x01, 0x50, "Stereo Delay", 2),  # #21
        (0x01, 0x51, "Mod Delay", 2),  # #22
        (0x01, 0x60, "2 Pitch Shifter", 1),  # #29
        (0x01, 0x61, "Fb P.Shifter", 1),  # #30
        (0x02, 0x09, "Cho→Delay", 2),  # #44
        (0x02, 0x0A, "FL→Delay", 2),  # #45
        (0x02, 0x0B, "Cho→Flanger", 2),  # #46
        (0x05, 0x00, "Keyboard Multi", 1),  # #55
        (0x11, 0x00, "Cho/Delay", 2),  # #56
        (0x11, 0x01, "FL/Delay", 2),  # #57
        (0x11, 0x02, "Cho/Flanger", 2),  # #58
    ],
    "ethnic_wind": [
        (0x01, 0x43, "Space D", 2),  # #19
        (0x01, 0x50, "Stereo Delay", 1),  # #21
        (0x01, 0x51, "Mod Delay", 1),  # #22
        (0x01, 0x55, "Reverb", 2),  # #26
        (0x11, 0x00, "Cho/Delay", 2),  # #56
        (0x11, 0x01, "FL/Delay", 2),  # #57
        (0x11, 0x02, "Cho/Flanger", 2),  # #58
    ],
    "synth_brass": [
        (0x01, 0x02, "Enhancer", 1),  # #3
        (0x01, 0x20, "Phaser", 2),  # #7
        (0x01, 0x23, "Stereo Flanger", 1),  # #10
        (0x01, 0x42, "Stereo Chorus", 1),  # #18
        (0x01, 0x43, "Space D", 1),  # #19
        (0x01, 0x44, "3D Chorus", 1),  # #20
        (0x01, 0x50, "Stereo Delay", 2),  # #21
        (0x01, 0x56, "Gate Reverb", 2),  # #27
        (0x02, 0x06, "EH→Chorus", 2),  # #41
        (0x02, 0x07, "EH→Flanger", 2),  # #42
        (0x02, 0x08, "EH→Delay", 2),  # #43
        (0x02, 0x09, "Cho→Delay", 2),  # #44
        (0x02, 0x0A, "FL→Delay", 2),  # #45
        (0x02, 0x0B, "Cho→Flanger", 2),  # #46
        (0x04, 0x06, "Rhodes Multi", 1),  # #54
        (0x11, 0x00, "Cho/Delay", 2),  # #56
        (0x11, 0x01, "FL/Delay", 2),  # #57
        (0x11, 0x02, "Cho/Flanger", 2),  # #58
    ],
    "orch_brass": [
        (0x01, 0x00, "Stereo-EQ", 1),  # #1
        (0x01, 0x02, "Enhancer", 2),  # #3
        (0x01, 0x55, "Reverb", 2),  # #26
        (0x01, 0x56, "Gate Reverb", 1),  # #27
    ],
    "bass_electric": [
        (0x01, 0x20, "Phaser", 1),  # #7
        (0x01, 0x30, "Compressor", 1),  # #14
        (0x02, 0x0B, "Cho→Flanger", 2),  # #46
        (0x04, 0x05, "Bass Multi", 2),  # #53
        (0x11, 0x02, "Cho/Flanger", 1),  # #58
    ],
    "strings": [
        (0x01, 0x40, "Hexa Chorus", 2),  # #16
        (0x01, 0x42, "Stereo Chorus", 1),  # #18
        (0x01, 0x43, "Space D", 1),  # #19
        (0x01, 0x44, "3D Chorus", 1),  # #20
        (0x01, 0x55, "Reverb", 4),  # #26
        (0x01, 0x57, "3D Delay", 2),  # #28
    ],
    "pad": [
        (0x01, 0x42, "Stereo Chorus", 2),  # #18
        (0x01, 0x43, "Space D", 2),  # #19
        (0x01, 0x44, "3D Chorus", 1),  # #20
        (0x01, 0x50, "Stereo Delay", 1),  # #21
        (0x01, 0x51, "Mod Delay", 1),  # #22
        (0x01, 0x52, "3 Tap Delay", 1),  # #23
        (0x01, 0x53, "4 Tap Delay", 1),  # #24
        (0x01, 0x54, "Tm Ctrl Delay", 1),  # #25
        (0x01, 0x55, "Reverb", 2),  # #26
        (0x01, 0x56, "Gate Reverb", 2),  # #27
        (0x01, 0x57, "3D Delay", 2),  # #28
        (0x01, 0x73, "Lo-Fi 2", 1),  # #34
    ],
    "bass_wide": [
        (0x01, 0x02, "Enhancer", 2),  # #3
        (0x01, 0x20, "Phaser", 2),  # #7
        (0x01, 0x23, "Stereo Flanger", 2),  # #10
        (0x01, 0x24, "Step Flanger", 1),  # #11
        (0x01, 0x42, "Stereo Chorus", 2),  # #18
        (0x01, 0x43, "Space D", 1),  # #19
        (0x01, 0x60, "2 Pitch Shifter", 1),  # #29
        (0x02, 0x06, "EH→Chorus", 2),  # #41
        (0x02, 0x07, "EH→Flanger", 2),  # #42
        (0x02, 0x0B, "Cho→Flanger", 2),  # #46
        (0x04, 0x06, "Rhodes Multi", 1),  # #54
        (0x11, 0x02, "Cho/Flanger", 2),  # #58
    ],
    "bass_acoustic": [
        (0x01, 0x02, "Enhancer", 4),  # #3
        (0x01, 0x42, "Stereo Chorus", 2),  # #18
        (0x01, 0x43, "Space D", 2),  # #19
        (0x01, 0x55, "Reverb", 2),  # #26
        (0x01, 0x56, "Gate Reverb", 2),  # #27
    ],
    "piano_acoustic": [
        (0x01, 0x00, "Stereo-EQ", 2),  # #1
        (0x01, 0x02, "Enhancer", 2),  # #3
        (0x01, 0x43, "Space D", 1),  # #19
        (0x01, 0x44, "3D Chorus", 1),  # #20
        (0x01, 0x55, "Reverb", 2),  # #26
        (0x01, 0x56, "Gate Reverb", 4),  # #27
    ],
    "chromatic": [
        (0x01, 0x00, "Stereo-EQ", 2),  # #1
        (0x01, 0x02, "Enhancer", 2),  # #3
        (0x01, 0x20, "Phaser", 2),  # #7
        (0x01, 0x23, "Stereo Flanger", 2),  # #10
        (0x01, 0x40, "Hexa Chorus", 2),  # #16
        (0x01, 0x41, "Tremolo Chorus", 2),  # #17
        (0x01, 0x42, "Stereo Chorus", 2),  # #18
        (0x01, 0x43, "Space D", 2),  # #19
        (0x01, 0x44, "3D Chorus", 2),  # #20
        (0x01, 0x50, "Stereo Delay", 1),  # #21
        (0x01, 0x54, "Tm Ctrl Delay", 1),  # #25
        (0x01, 0x55, "Reverb", 2),  # #26
        (0x01, 0x56, "Gate Reverb", 4),  # #27
        (0x01, 0x57, "3D Delay", 2),  # #28
        (0x01, 0x60, "2 Pitch Shifter", 1),  # #29
        (0x01, 0x61, "Fb P.Shifter", 1),  # #30
        (0x01, 0x70, "3D Auto", 1),  # #31
        (0x01, 0x72, "Lo-Fi 1", 1),  # #33
        (0x02, 0x06, "EH→Chorus", 2),  # #41
        (0x02, 0x07, "EH→Flanger", 2),  # #42
        (0x02, 0x08, "EH→Delay", 2),  # #43
        (0x02, 0x09, "Cho→Delay", 2),  # #44
        (0x02, 0x0A, "FL→Delay", 2),  # #45
        (0x02, 0x0B, "Cho→Flanger", 2),  # #46
        (0x04, 0x06, "Rhodes Multi", 1),  # #54
        (0x11, 0x00, "Cho/Delay", 1),  # #56
        (0x11, 0x01, "FL/Delay", 1),  # #57
        (0x11, 0x02, "Cho/Flanger", 2),  # #58
    ],
    "fx": [
        (0x01, 0x40, "Hexa Chorus", 2),  # #16
        (0x01, 0x42, "Stereo Chorus", 2),  # #18
        (0x01, 0x43, "Space D", 2),  # #19
        (0x01, 0x44, "3D Chorus", 1),  # #20
        (0x01, 0x56, "Gate Reverb", 2),  # #27
        (0x01, 0x57, "3D Delay", 2),  # #28
        (0x01, 0x60, "2 Pitch Shifter", 1),  # #29
        (0x01, 0x61, "Fb P.Shifter", 1),  # #30
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
# Dirt types that keep a lone panned guitar on its side (param no. of the pan).
ANIMA_EFX_PAN_SLOT = {
    (0x01, 0x10): 19,  # Overdrive
    (0x01, 0x11): 19,  # Distortion
    (0x02, 0x00): 2, (0x02, 0x01): 2, (0x02, 0x02): 2,  # OD→ series: OD Pan
    (0x02, 0x03): 2, (0x02, 0x04): 2, (0x02, 0x05): 2,  # DS→ series: DS Pan
}

# ---------------------------------------------------------------------------
# Insert shaping, addresses from the SC-8850 OM list p.216-223 (40 03 xx).
# ---------------------------------------------------------------------------
# Pan: one address = the output follows the player's pan; two addresses =
# a parallel pair (or the two pitch voices), spread around the player's pan.
# OD1/OD2 is left to the guitar split logic.
ANIMA_EFX_PAN_PARAMS = {
    (0x01, 0x01): (0x15,),        # Spectrum
    (0x01, 0x03): (0x15,),        # Humanizer
    (0x01, 0x10): (0x15,),        # Overdrive
    (0x01, 0x11): (0x15,),        # Distortion
    (0x01, 0x21): (0x15,),        # Auto Wah
    (0x01, 0x30): (0x15,),        # Compressor
    (0x01, 0x31): (0x15,),        # Limiter
    (0x01, 0x54): (0x07,),        # Tm Ctrl Delay: EFX Pan
    (0x01, 0x61): (0x08,),        # Fb P.Shifter: EFX Pan
    (0x01, 0x72): (0x15,),        # Lo-Fi 1
    (0x01, 0x73): (0x15,),        # Lo-Fi 2: Pan (Mono)
    (0x02, 0x00): (0x04,), (0x02, 0x01): (0x04,), (0x02, 0x02): (0x04,),  # OD→
    (0x02, 0x03): (0x04,), (0x02, 0x04): (0x04,), (0x02, 0x05): (0x04,),  # DS→
    (0x01, 0x60): (0x06, 0x0A),   # 2 Pitch Shifter: EFX Pan 1 / 2
    (0x11, 0x00): (0x12, 0x14),   # Cho/Delay
    (0x11, 0x01): (0x12, 0x14),   # FL/Delay
    (0x11, 0x02): (0x12, 0x14),   # Cho/Flanger
    (0x11, 0x04): (0x12, 0x14),   # OD/Rotary
    (0x11, 0x05): (0x12, 0x14),   # OD/Phaser
    (0x11, 0x06): (0x12, 0x14),   # OD/AutoWah
    (0x11, 0x07): (0x12, 0x14),   # PH/Rotary
    (0x11, 0x08): (0x12, 0x14),   # PH/AutoWah
}
ANIMA_EFX_PAN_PAIR_SPREAD = 24   # a pair sits at player pan ±24 (CC10 units)

# Delay time scales (OM p.224 conversion table): value index -> ms.
def _dly_table(points):
    out = []
    for i in range(128):
        for (a, b, v0, step) in points:
            if a <= i <= b:
                out.append(v0 + (i - a) * step)
                break
        else:
            out.append(out[-1])
    return tuple(out)

GS_DLY_MS = {
    # *2 Delay Time 1: 200-1000 ms
    2: _dly_table([(0x00, 0x46, 200, 5), (0x47, 0x73, 560, 10), (0x74, 0x7F, 1000, 0)]),
    # *3 Delay Time 2: 200-1000 ms
    3: _dly_table([(0x00, 0x50, 200, 5), (0x51, 0x78, 610, 10), (0x79, 0x7F, 1000, 0)]),
    # *4 Delay Time 3: 0-500 ms
    4: _dly_table([(0x00, 0x32, 0.0, 0.1), (0x33, 0x3C, 5.5, 0.5), (0x3D, 0x5A, 11, 1),
                   (0x5B, 0x74, 50, 10), (0x75, 0x7E, 320, 20), (0x7F, 0x7F, 500, 0)]),
    # *5 Delay Time 4: 0-635 ms
    5: _dly_table([(0x00, 0x7F, 0, 5)]),
}

# Delay-type inserts: time params as (address, scale, beats) and feedback as
# (address, kind) where kind "pct" is -98..+98 % (0x40 = 0, 2 % per step)
# and "raw" is 0-127. Beats are fitted into the scale's range by halving or
# doubling, so a slow song still gets a musical echo.
ANIMA_EFX_DELAY = {
    (0x01, 0x50): {"times": ((0x03, 4, 0.5), (0x04, 4, 1.0)), "fb": (0x05, "pct")},           # Stereo Delay
    (0x01, 0x51): {"times": ((0x04, 4, 1.0),), "fb": (0x05, "pct")},                          # Mod Delay (L stays short)
    (0x01, 0x52): {"times": ((0x03, 2, 1.0), (0x04, 2, 0.5), (0x05, 2, 0.75)), "fb": (0x06, "pct")},  # 3 Tap
    (0x01, 0x53): {"times": ((0x03, 2, 1.0), (0x04, 2, 0.75), (0x05, 2, 1.5), (0x06, 2, 0.5)), "fb": (0x0B, "pct")},  # 4 Tap
    (0x01, 0x54): {"times": ((0x03, 3, 1.0),), "fb": (0x05, "pct")},                          # Tm Ctrl Delay
    (0x01, 0x57): {"times": ((0x03, 4, 1.0), (0x04, 4, 0.5), (0x05, 4, 0.75)), "fb": (0x06, "pct")},  # 3D Delay
    (0x02, 0x02): {"times": ((0x08, 4, 0.5),), "fb": (0x09, "pct")},                          # OD→Delay
    (0x02, 0x05): {"times": ((0x08, 4, 0.5),), "fb": (0x09, "pct")},                          # DS→Delay
    (0x02, 0x08): {"times": ((0x08, 4, 0.5),), "fb": (0x09, "pct")},                          # EH→Delay
    (0x02, 0x09): {"times": ((0x08, 4, 0.5),), "fb": (0x09, "pct")},                          # Cho→Delay
    (0x02, 0x0A): {"times": ((0x08, 4, 0.5),), "fb": (0x09, "pct")},                          # FL→Delay
    (0x11, 0x00): {"times": ((0x08, 4, 0.5),), "fb": (0x09, "pct")},                          # Cho/Delay
    (0x11, 0x01): {"times": ((0x08, 4, 0.5),), "fb": (0x09, "pct")},                          # FL/Delay
    (0x04, 0x00): {"times": ((0x13, 5, 0.5),), "fb": (0x14, "raw")},                          # GTR Multi 1
    (0x04, 0x02): {"times": ((0x13, 5, 0.25),), "fb": (0x14, "raw")},                         # GTR Multi 3
    (0x04, 0x03): {"times": ((0x11, 5, 0.25),), "fb": (0x12, "raw")},                         # Clean Gt Multi 1
    (0x05, 0x00): {"times": ((0x13, 5, 0.25),), "fb": (0x14, "raw")},                         # Keyboard Multi
    (0x01, 0x61): {"times": (), "fb": (0x05, "pct")},                                         # Fb P.Shifter
}
ANIMA_EFX_FB_CAP_PCT = 50        # never above +50 %
ANIMA_EFX_FB_PCT = 30            # echo families
ANIMA_EFX_FB_PCT_HELD = 16       # held families: strings, pads, organ, fx
ANIMA_EFX_FB_HELD_FAMS = frozenset({"strings", "pad", "organ_chorus", "organ_rotary", "fx", "synth_brass"})

# Pitch shifters: (coarse, fine) address per voice. Coarse 0x28-0x4C = -24..+12
# semitones (0x40 = 0); fine 0x0E-0x72 = -100..+100 cents, 2 cents a step.
ANIMA_EFX_PITCH = {
    (0x01, 0x60): ((0x03, 0x04), (0x07, 0x08)),  # 2 Pitch Shifter: voice 1, voice 2
    (0x01, 0x61): ((0x03, 0x04),),               # Fb P.Shifter
    (0x05, 0x00): ((0x0A, 0x0B),),               # Keyboard Multi: PS
}
# Intervals that stay in key whatever the chord: unison doubler, octave, fifth.
# (semitones, cents) per voice; the second voice is ignored by one-voice types.
ANIMA_EFX_PITCH_MODES = {
    "doubler": ((0, 8), (0, -8)),
    "octave":  ((12, 0), (-12, 0)),
    "oct_up":  ((12, 0), (0, 6)),
    "oct_dn":  ((-12, 0), (0, 6)),
    "power":   ((7, 0), (-5, 0)),
}
ANIMA_EFX_PITCH_FAM_MODES = {
    "bass_electric": ("oct_dn", "doubler"),
    "bass_wide": ("oct_dn", "doubler"),
    "bass_acoustic": ("oct_dn", "doubler"),
    "guitar_dist": ("power", "doubler"),
    "guitar_clean": ("doubler", "octave", "power"),
    "guitar_mute": ("doubler", "octave"),
    "lead": ("octave", "power", "doubler"),
    "synth_brass": ("octave", "doubler"),
    "harmonica": ("doubler", "octave"),
    "ethnic_wind": ("doubler", "oct_up"),
}
ANIMA_EFX_PITCH_DEFAULT_MODES = ("doubler", "oct_up")

# Dirt inserts sit after the part's volume, so a CC7/CC11 fade only drives
# the distortion softer and it stays loud. Their overall Level (40 03 16,
# param 20 on every type) follows the fade instead. Value = the type default.
ANIMA_EFX_DIRT_LEVEL = {
    (0x01, 0x10): 96,   # Overdrive
    (0x01, 0x11): 84,   # Distortion
    (0x02, 0x00): 80, (0x02, 0x01): 80, (0x02, 0x02): 80,   # OD→
    (0x02, 0x03): 72, (0x02, 0x04): 72, (0x02, 0x05): 72,   # DS→
    (0x03, 0x00): 96,   # Rotary Multi (OD on)
    (0x04, 0x00): 110, (0x04, 0x01): 80, (0x04, 0x02): 88,  # GTR Multi 1-3
    (0x04, 0x05): 76,   # Bass Multi (OD on)
    (0x11, 0x03): 127, (0x11, 0x04): 127, (0x11, 0x05): 127, (0x11, 0x06): 127,  # OD1/OD2, OD/…
}

# Gate Reverb: Type at 0x03, 02 = Sweep1, 03 = Sweep2 (they pop more).
ANIMA_EFX_GATE_TYPE = {(0x01, 0x56): (0x03, (0x02, 0x03))}
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
