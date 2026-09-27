"""SC-8850 unique tone slots for Anima.

Each slot is (cc00, cc32, pc) with:
  pc    0-based MIDI program (UI patch = pc + 1; French Horns = 61)
  cc32  4 = SC-8850, 3 = 88Pro, 2 = SC-88, 1 = SC-55
  cc00  126/127 + cc32 1 = CM-64 PCM / LA (SC-55 map)

SFX PCs 120–127 are omitted (gesture / foley only).
"""

# 0-based GM PC -> CC00 values that exist on the 8850 column (manual pp.167–183).
_C00 = {
    0: [0, 1, 2, 8, 9, 16, 24, 25, 26, 27],
    1: [0, 1, 2, 8, 9, 16],
    2: [0, 1, 2, 8],
    3: [0, 8],
    4: [0, 8, 9, 10, 16, 17, 24, 25, 26],
    5: [0, 1, 8, 9, 10, 16, 24, 32],
    6: [0, 1, 2, 8, 16, 24, 32],
    7: [0, 1, 2, 3, 8, 16, 17, 24, 32, 33, 35, 36, 37, 38, 39],
    8: [0, 1],
    9: [0],
    10: [0, 1, 8],
    11: [0, 1, 8, 9],
    12: [0, 8, 16, 17, 24],
    13: [0, 8],
    14: [0, 8, 9, 10, 16],
    15: [0, 1, 2, 8, 16, 17, 24],
    16: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 16, 17, 18, 19, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 40, 48],
    17: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 32, 33, 34, 35],
    18: [0, 8, 16, 17, 18, 24],
    19: [0, 8, 16, 24, 32, 33],
    20: [0, 8, 16],
    21: [0, 8, 9, 16, 24, 25],
    22: [0, 1, 8, 9],
    23: [0, 8, 16],
    24: [0, 8, 16, 24, 32, 40],
    25: [0, 8, 9, 10, 16, 17, 18, 32, 33],  # 17 = MandolinTrem
    26: [0, 1, 8],
    27: [0, 1, 2, 3, 4, 5, 8, 9, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25],
    28: [0, 1, 2, 8, 16, 24],
    29: [0, 1, 2, 3, 4, 5, 8, 9, 10, 11, 12],
    30: [0, 1, 2, 3, 4, 5, 8, 9, 16, 17, 18, 24, 25, 26],
    31: [0, 8, 9, 16, 24],
    32: [0, 1, 8, 9, 16],
    33: [0, 1, 2, 3, 4, 5, 6, 7, 8, 16],
    34: [0, 1, 2, 3, 4, 8, 16],
    35: [0, 1, 2, 3, 4, 5, 8],
    36: [0, 1, 8, 9],
    37: [0, 1, 8],
    38: [0, 1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 32, 33, 34, 35, 36, 40, 41, 42, 43, 44],
    39: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42],
    40: [0, 1, 8],
    41: [0, 1],
    42: [0, 1],
    43: [0],
    44: [0, 2, 8, 9, 10],
    45: [0, 1, 2, 3, 8, 16, 17],
    46: [0, 1, 2, 8, 16, 24, 25, 26],
    47: [0],
    48: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 24, 32, 33, 34, 40],
    49: [0, 1, 2, 8, 9, 10, 11, 12, 13],
    50: [0, 1, 2, 3, 4, 8, 9, 10, 11, 12, 16, 17, 24, 25],
    51: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    52: [0, 8, 9, 10, 11, 12, 13, 14, 16, 24, 32, 33],
    53: [0, 1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12, 16, 17, 18, 19, 20, 21, 22, 23, 24, 32, 33, 34, 35, 36, 37, 40],
    54: [0, 1, 2, 8, 9, 10, 16, 17, 18, 19],
    55: [0, 1, 2, 3, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27],
    56: [0, 1, 2, 3, 4, 8, 16, 24, 25, 26, 27, 32],
    57: [0, 1, 2, 3, 4, 8, 16],
    58: [0, 1, 8],
    59: [0, 1, 2, 3, 8],
    60: [0, 1, 2, 3, 8, 9, 16, 24],
    61: [0, 1, 2, 3, 4, 5, 8, 9, 10, 12, 14, 16, 17, 24, 25, 26, 32, 33, 35, 36, 37, 38],
    62: [0, 1, 2, 3, 4, 5, 8, 9, 10, 16, 17, 18, 19],
    63: [0, 1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12, 16, 17],
    64: [0, 8],
    65: [0, 8, 9, 16, 17],
    66: [0, 1, 8, 9],
    67: [0, 1, 8],
    68: [0, 8, 16],
    69: [0],
    70: [0],
    71: [0, 8, 16, 17],
    72: [0, 1, 8, 9, 16],
    73: [0, 1, 2, 3, 8, 9, 16, 17],
    74: [0],
    75: [0, 8, 16, 17, 24, 25, 26],
    76: [0],
    77: [0, 1],
    78: [0, 1],
    79: [0],
    80: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35],
    81: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 40, 41, 42, 43, 44, 45, 46, 47],
    82: [0, 1, 2, 8, 9],
    83: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    84: [0, 1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12, 16, 17, 18, 19, 20, 21, 22, 24, 25, 26],
    85: [0, 1, 8, 9, 10],
    86: [0, 1, 2, 3, 4, 5, 6, 8],
    87: [0, 1, 2, 3, 4, 5, 6, 7],
    88: [0, 1, 2, 3, 4, 5, 6, 7],
    89: [0, 1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12, 13],
    90: [0, 1, 2, 3, 4, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 24],
    91: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    92: [0, 1, 2, 3, 4, 5],
    93: [0, 1, 2, 3, 4, 5],
    94: [0, 1, 2, 8, 9, 10, 11, 12],
    95: [0, 1, 2, 3, 4, 8, 9, 10, 11, 12, 13, 14, 15],
    96: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
    97: [0, 1, 2, 3, 4, 5, 8],
    98: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 16, 17, 18, 19, 20, 21, 22, 23],
    99: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
    100: [0, 1, 2, 3, 4, 5, 6, 7, 8],
    101: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32],
    102: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
    103: [0, 1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 16, 17, 18, 19],
    104: [0, 1, 2, 3, 4, 5, 8, 16],
    105: [0, 1, 8, 9, 16, 24, 28, 32],
    106: [0, 1, 8],
    107: [0, 1, 8, 16, 19, 24],
    108: [0, 8, 9, 10],
    109: [0, 8, 9, 10, 11],
    110: [0, 8, 9],
    111: [0, 1, 8, 16, 24, 32, 33],
    112: [0, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 32, 40, 41, 42],
    113: [0, 8, 16],
    114: [0, 1],
    115: [0, 8, 16, 17, 24, 32, 40],
    116: [0, 1, 8, 9, 16, 17, 18, 24, 25, 26, 27, 28, 32, 40, 41, 42, 43],
    117: [0, 1, 2, 3, 4, 8, 9, 16, 17, 18, 19, 24, 40, 41, 42, 43, 44],
    118: [0, 8, 9, 10, 11, 12, 13],
    119: [0, 1, 2, 3, 8, 9, 16, 17, 24, 25, 26, 27, 40, 41, 42, 43, 44, 45, 46],
}


# --- generated by tools/gen_unique_tones.py: do not edit by hand ---
# Older-map tones (CC32 3 = 88Pro, 2 = SC-88, 1 = SC-55) with a waveform the 8850 map lacks.
_OLD_MAP_UNIQUE = {
    0: ((0, 2, 0), (16, 2, 0), (16, 1, 0),),  # 001 Piano 1 [88] / Piano 1d [88] / Piano 1d [55]
    1: ((0, 3, 1), (0, 2, 1), (0, 1, 1),),  # 002 Piano 2 [88Pro] / Piano 2 [88] / Piano 2 [55]
    3: ((0, 3, 3), (8, 3, 3), (0, 2, 3), (8, 2, 3), (0, 1, 3),),  # 004 Honky-tonk [88Pro] / Honky-tonk 2 [88Pro] / Honky-tonk [88] / Old Upright [88] / Honky-tonk [55]
    4: ((24, 2, 4), (16, 1, 4), (24, 1, 4),),  # 005 60'sE.Piano [88] / E.Piano 1v [55] / 60s E.Piano [55]
    6: ((24, 1, 6),),  # 007 Harpsi.o [55]
    7: ((0, 1, 7),),  # 008 Clav. [55]
    13: ((0, 1, 13),),  # 014 Xylophone [55]
    14: ((0, 3, 14),),  # 015 Tubular-bell [88Pro]
    16: ((9, 2, 16), (0, 1, 16), (16, 1, 16), (32, 1, 16),),  # 017 Organ 109 [88] / Organ 1 [55] / 60's Organ1 [55] / Organ 4 [55]
    17: ((8, 2, 17), (0, 1, 17), (8, 1, 17), (32, 1, 17),),  # 018 DetunedOr.2 [88] / Organ 2 [55] / Detuned Or2 [55] / Organ 5 [55]
    19: ((8, 1, 19), (16, 1, 19),),  # 020 Church Org2 [55] / Church Org3 [55]
    21: ((8, 2, 21), (0, 1, 21), (8, 1, 21),),  # 022 AccordionIt [88] / Accordion F [55] / Accordion I [55]
    22: ((0, 3, 22), (0, 2, 22), (1, 2, 22), (0, 1, 22),),  # 023 Harmonica [88Pro] / Harmonica [88] / Harmonica 2 [88] / Harmonica [55]
    23: ((0, 2, 23), (0, 1, 23),),  # 024 Bandoneon [88] / Bandoneon [55]
    24: ((8, 1, 24),),  # 025 Ukulele [55]
    25: ((8, 2, 25), (0, 1, 25), (8, 1, 25), (16, 1, 25),),  # 026 12-str.Gt [88] / Steel Gt. [55] / 12-str.Gt [55] / Mandolin [55]
    26: ((0, 2, 26), (8, 1, 26),),  # 027 Jazz Gt. [88] / Hawaiian Gt [55]
    27: ((8, 1, 27),),  # 028 Chorus Gt. [55]
    28: ((0, 1, 28), (8, 1, 28), (16, 1, 28),),  # 029 Muted Gt. [55] / Funk Gt. [55] / Funk Gt.2 [55]
    32: ((0, 2, 32), (0, 1, 32),),  # 033 AcousticBs. [88] / Acoustic Bs [55]
    33: ((1, 2, 33), (0, 1, 33),),  # 034 FingeredBs2 [88] / Fingered Bs [55]
    34: ((0, 1, 34),),  # 035 Picked Bass [55]
    36: ((0, 1, 36),),  # 037 Slap Bass 1 [55]
    37: ((0, 1, 37),),  # 038 Slap Bass 2 [55]
    39: ((0, 1, 39), (8, 1, 39),),  # 040 Syn.Bass 2 [55] / Syn.Bass 4 [55]
    40: ((8, 1, 40),),  # 041 Slow Violin [55]
    41: ((0, 2, 41), (0, 1, 41),),  # 042 Viola [88] / Viola [55]
    42: ((0, 2, 42), (0, 1, 42),),  # 043 Cello [88] / Cello [55]
    43: ((0, 3, 43), (0, 2, 43), (0, 1, 43),),  # 044 Contrabass [88Pro] / Contrabass [88] / Contrabass [55]
    45: ((0, 1, 45),),  # 046 Pizzicato [55]
    46: ((0, 1, 46),),  # 047 Harp [55]
    47: ((0, 1, 47),),  # 048 Timpani [55]
    48: ((0, 1, 48),),  # 049 Strings [55]
    55: ((0, 1, 55),),  # 056 Orchest.Hit [55]
    57: ((0, 2, 57), (1, 2, 57), (0, 1, 57),),  # 058 Trombone [88] / Trombone 2 [88] / Trombone [55]
    58: ((0, 1, 58),),  # 059 Tuba [55]
    60: ((0, 1, 60),),  # 061 French Horn [55]
    62: ((16, 1, 62),),  # 063 Analog Brs1 [55]
    64: ((0, 1, 64),),  # 065 Soprano Sax [55]
    65: ((0, 2, 65), (8, 2, 65), (0, 1, 65),),  # 066 Alto Sax [88] / Hyper Alto [88] / Alto Sax [55]
    66: ((0, 2, 66), (0, 1, 66),),  # 067 Tenor Sax [88] / Tenor Sax [55]
    67: ((0, 1, 67),),  # 068 BaritoneSax [55]
    68: ((0, 1, 68),),  # 069 Oboe [55]
    69: ((0, 1, 69),),  # 070 EnglishHorn [55]
    70: ((0, 1, 70),),  # 071 Bassoon [55]
    71: ((0, 2, 71), (0, 1, 71),),  # 072 Clarinet [88] / Clarinet [55]
    72: ((0, 1, 72),),  # 073 Piccolo [55]
    81: ((0, 2, 81),),  # 082 Saw Wave [88]
    105: ((0, 1, 105),),  # 106 Banjo [55]
    108: ((0, 1, 108),),  # 109 Kalimba [55]
    109: ((0, 1, 109),),  # 110 Bagpipe [55]
    113: ((0, 1, 113),),  # 114 Agogo [55]
    118: ((8, 1, 118),),  # 119 808 Tom [55]
}
# CM-64 tones whose tone data duplicates an 8850 tone or an earlier CM-64 slot.
_CM_DUP = frozenset({
    (126, 1, 1),  # Piano 2
    (126, 1, 2),  # Piano 2
    (126, 1, 5),  # Piano 2
    (126, 1, 6),  # Piano 2
    (126, 1, 38),  # Organ 1
    (126, 1, 39),  # Organ 1
    (126, 1, 41),  # Organ 1
    (126, 1, 42),  # Organ 1
    (126, 1, 43),  # Organ 2
    (126, 1, 44),  # Organ 2
    (126, 1, 45),  # Organ 2
    (126, 1, 11),  # Steel Gt.
    (126, 1, 24),  # Fingered Bs
    (126, 1, 26),  # Picked Bass
    (126, 1, 16),  # Slap Bass 1
    (126, 1, 17),  # Slap Bass 1
    (126, 1, 18),  # Slap Bass 1
    (126, 1, 20),  # Slap Bass 2
    (126, 1, 21),  # Slap Bass 2
    (126, 1, 22),  # Slap Bass 2
    (126, 1, 35),  # SynStrings3
    (126, 1, 36),  # SynStrings3
    (126, 1, 30),  # Choir Aahs
    (126, 1, 31),  # Choir Aahs
    (126, 1, 32),  # Choir Aahs
    (126, 1, 47),  # Trumpet
    (126, 1, 49),  # Trombone
    (126, 1, 50),  # Trombone
    (126, 1, 51),  # Trombone
    (126, 1, 52),  # Trombone
    (126, 1, 53),  # Trombone
    (126, 1, 59),  # Brass 1
    (126, 1, 61),  # Brass 2
    (126, 1, 62),  # Brass 1
    (126, 1, 57),  # Alto Sax
})
# --- end generated ---

# CM-64 extras: (cc00, cc32, pc_0based) added onto the GM PC family listed.
# PCM = 126 / LA = 127, always CC32=1 (SC-55 map).
def _cm_extras():
    out = {i: [] for i in range(120)}
    def add(gm_pc, cc00, pc1):
        # CM-64 PCM/LA on the 8850: CC32=1 (SC-55 map) then CC00=126/127.
        # CC32=0/4 + 126/127 is empty (No Instrument) on native/8850 maps.
        out[gm_pc].append((cc00, 1, (pc1 - 1) & 0x7F))
    # PCM 126 → nearest GM capital
    for pc, gm in (
        (1, 1), (2, 1), (3, 1), (4, 3), (5, 0), (6, 1), (7, 1),
        (8, 4), (9, 4), (10, 5),
        (11, 25), (12, 25), (13, 25), (14, 28), (15, 28),
        (16, 36), (17, 36), (18, 36), (19, 36), (20, 37), (21, 37), (22, 37), (23, 37),
        (24, 33), (25, 33), (26, 34), (27, 34), (28, 35), (29, 32),
        (30, 52), (31, 52), (32, 52), (33, 52),
        (34, 49), (35, 48), (36, 50), (37, 50),
        (38, 16), (39, 16), (40, 16), (41, 17), (42, 16), (43, 16),
        (44, 17), (45, 17), (46, 17),
        (47, 56), (48, 56), (49, 57), (50, 57), (51, 57), (52, 57), (53, 57), (54, 57),
        (55, 65), (56, 66), (57, 67), (58, 65),
        (59, 61), (60, 61), (61, 61), (62, 61), (63, 61), (64, 55),
    ):
        add(gm, 126, pc)
    # LA 127
    for pc, gm in (
        (1, 0), (2, 1), (3, 2), (4, 4), (5, 4), (6, 5), (7, 5), (8, 3),
        (9, 16), (10, 16), (11, 17), (12, 17), (13, 19), (14, 19), (15, 19), (16, 21),
        (17, 6), (18, 6), (19, 6), (20, 7), (21, 7), (22, 7), (23, 8), (24, 8),
        (25, 62), (26, 62), (27, 63), (28, 63),
        (29, 38), (30, 38), (31, 39), (32, 39),
        (33, 88), (34, 89), (35, 52), (37, 97), (38, 99), (39, 89),
        (42, 96), (45, 81), (48, 80),
        (49, 48), (50, 48), (51, 48), (52, 45), (53, 40), (54, 40), (55, 42), (56, 42),
        (57, 43), (58, 46), (59, 46),
        (60, 24), (61, 25), (62, 27), (63, 27), (64, 104),
        (65, 32), (66, 32), (67, 33), (68, 34), (69, 36), (70, 37), (71, 35), (72, 35),
        (73, 73), (74, 73), (75, 72), (76, 72), (77, 74), (78, 75),
        (79, 65), (80, 66), (81, 66), (82, 67), (83, 71), (84, 71), (85, 68), (86, 69),
        (87, 70), (88, 22),
        (89, 56), (90, 56), (91, 57), (92, 57), (93, 60), (94, 60), (95, 57), (96, 61), (97, 61),
        (98, 11), (99, 11), (102, 9), (103, 14), (104, 13), (105, 12), (106, 107),
        (108, 77), (109, 78), (110, 78), (111, 76),
        (113, 47),
    ):
        add(gm, 127, pc)
    return out


_CM = _cm_extras()

# Overdrive / Dist / Harmonics may also use these Clean Gt (PC 28) colors.
# CC00 on 8850 map: JC Clean, four Tele pickups, three LP rears, Mid Tone.
_CLEAN_FOR_DIST = (
    (4, 4, 27),    # JC Clean Gt
    (16, 4, 27),   # TC FrontPick
    (17, 4, 27),   # TC Rear Pick
    (18, 4, 27),   # TC Clean ff
    (19, 4, 27),   # TC Clean 2
    (20, 4, 27),   # LP Rear Pick
    (21, 4, 27),   # LP Rear 2
    (22, 4, 27),   # LP RearAtack
    (23, 4, 27),   # Mid Tone GTR
)



def anima_cm_to_gm(cc00: int, pc: int) -> int | None:
    """CM-64 bank 126/127 program (0-based) → GM capital we tagged it under."""
    cc00, pc = int(cc00) & 0x7F, int(pc) & 0x7F
    if cc00 not in (126, 127):
        return None
    for gm, keys in _CM.items():
        for c0, _c32, p in keys:
            if c0 == cc00 and p == pc:
                return gm
    return None


# (cc00, pc_0based) → keep 1 in N times Anima would have picked it.
# MandolinTrem (Steel-str.Gt CC00=17) is a looped tremolo — too sticky at equal weight.
ANIMA_TONE_RARE = {
    (17, 25): 8,
}

# Never pick as a standing variation. Reserved for a future one-shot articulation.
# Keys are (CC00, PC_0based). UI patch = PC_0based + 1.
ANIMA_TONE_BLOCK = {
    (24, 60),   # UI 061 / CC00 024  F.Horn Rip
    (16, 61),   # UI 062 / CC00 016  Brass Fall
    (17, 61),   # UI 062 / CC00 017  Trumpet Fall
}

# The user's picks from the "Anima Tone Palettes" page (tools/picker/build_tone_picker.py),
# per GM program (0-based): {(cc00, cc32, pc): {"w": 0|1|2|4, "efx": -2..2, "note": "..."}}.
# w 0 = never pick, 1 = less often (x1/2), 2 = normal, 4 = favoured (x2). A listed tone
# overrides ANIMA_TONE_RARE / ANIMA_TONE_BLOCK. efx and note are recorded for Anima's
# insert balance and phrasing; a program with no entry picks exactly as before.
ANIMA_TONE_PREFS: dict = {}


def anima_tone_pref(gm_pc: int, key) -> dict:
    """The user's pick for one tone slot under a GM program ({} = default)."""
    return (ANIMA_TONE_PREFS.get(int(gm_pc) & 0x7F) or {}).get(tuple(key)) or {}


def anima_tone_weight(gm_pc: int, key) -> int:
    """Pick weight: 0 never, 1 less often, 2 normal, 4 favoured."""
    w = anima_tone_pref(gm_pc, key).get("w")
    return 2 if w is None else max(0, int(w))


def anima_tone_slots(pc: int) -> list[tuple[int, int, int]]:
    """Unique (cc00, cc32, pc) choices for a GM program (0-based). Empty = leave capital."""
    p = pc & 0x7F
    if p >= 120:
        return []
    slots = []
    seen = set()
    for cc0 in _C00.get(p, [0]):
        if (cc0, p) in ANIMA_TONE_BLOCK and not anima_tone_pref(p, (cc0, 4, p)).get("w"):
            continue
        key = (cc0, 4, p)
        if key not in seen:
            seen.add(key)
            slots.append(key)
    for key in _OLD_MAP_UNIQUE.get(p, ()):
        if key not in seen:
            seen.add(key)
            slots.append(key)
    for key in _CM.get(p, []):
        if key in _CM_DUP and not anima_tone_pref(p, key).get("w"):
            continue
        if key not in seen:
            seen.add(key)
            slots.append(key)
    if p in (29, 30, 31):
        for key in _CLEAN_FOR_DIST:
            if key not in seen:
                seen.add(key)
                slots.append(key)
    if ANIMA_TONE_PREFS.get(p):
        slots = [k for k in slots if anima_tone_weight(p, k) > 0]
    return slots


def anima_combo_ok(cc0: int, cc32: int, pc: int) -> bool:
    """True if this bank/map/PC exists on an SC-8850 (no No-Instrument)."""
    cc0, cc32, pc = int(cc0) & 0x7F, int(cc32) & 0x7F, int(pc) & 0x7F
    if cc0 == 126:
        return cc32 == 1 and pc < 64
    if cc0 == 127:
        return cc32 == 1
    if cc0 == 0:
        return cc32 in (0, 1, 2, 3, 4)
    # Variations live on 8850 (4) and classic (0), but GS files often
    # address the same CC00 on maps 1–3 (55 / 88 / Pro).
    if cc32 not in (0, 1, 2, 3, 4):
        return False
    if (cc0, cc32, pc) in _OLD_MAP_UNIQUE.get(pc, ()):
        return True
    if cc0 in _C00.get(pc, (0,)):
        return True
    # SFX / atmosphere PCs are sparsely tabled; trust the file.
    if pc >= 119 and 0 < cc0 <= 48:
        return True
    return False
