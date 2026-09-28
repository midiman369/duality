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
# Older-map tones (CC32 3 = 88Pro, 2 = SC-88, 1 = SC-55) whose tone data no 8850-map tone shares.
_OLD_MAP_UNIQUE = {
    0: ((0, 3, 0), (8, 3, 0), (24, 3, 0), (0, 2, 0), (8, 2, 0), (16, 2, 0), (0, 1, 0), (8, 1, 0), (16, 1, 0),),  # 001 Piano 1 [88Pro] / Piano 1w [88Pro] / Piano + Str. [88Pro] / Piano 1 [88] / Piano 1w [88] / Piano 1d [88] / Piano 1 [55] / Piano 1w [55] / Piano 1d [55]
    1: ((0, 3, 1), (8, 3, 1), (0, 2, 1), (8, 2, 1), (0, 1, 1), (8, 1, 1),),  # 002 Piano 2 [88Pro] / Piano 2w [88Pro] / Piano 2 [88] / Piano 2w [88] / Piano 2 [55] / Piano 2w [55]
    2: ((0, 2, 2), (1, 2, 2), (8, 2, 2), (0, 1, 2), (8, 1, 2),),  # 003 Piano 3 [88] / EG+Rhodes 1 [88] / Piano 3w [88] / Piano 3 [55] / Piano 3w [55]
    3: ((0, 3, 3), (8, 3, 3), (0, 2, 3), (8, 2, 3), (0, 1, 3), (8, 1, 3),),  # 004 Honky-tonk [88Pro] / Honky-tonk 2 [88Pro] / Honky-tonk [88] / Old Upright [88] / Honky-tonk [55] / HonkyTonk w [55]
    4: ((0, 2, 4), (24, 2, 4), (0, 1, 4), (8, 1, 4), (16, 1, 4), (24, 1, 4),),  # 005 E.Piano 1 [88] / 60'sE.Piano [88] / E.Piano 1 [55] / Detuned EP1 [55] / E.Piano 1v [55] / 60s E.Piano [55]
    5: ((0, 1, 5), (8, 1, 5), (16, 1, 5),),  # 006 E.Piano 2 [55] / Detuned EP2 [55] / E.Piano 2v [55]
    6: ((0, 3, 6), (16, 3, 6), (24, 3, 6), (0, 1, 6), (16, 1, 6), (24, 1, 6),),  # 007 Harpsichord [88Pro] / Harpsi.w [88Pro] / Harpsi.o [88Pro] / Harpsichord [55] / Harpsi.w [55] / Harpsi.o [55]
    7: ((0, 3, 7), (24, 3, 7), (0, 1, 7),),  # 008 Clav. [88Pro] / Clav.o [88Pro] / Clav. [55]
    9: ((0, 1, 9),),  # 010 Glockenspl [55]
    10: ((0, 3, 10), (0, 1, 10),),  # 011 Music Box [88Pro] / Music Box [55]
    11: ((0, 2, 11), (1, 2, 11), (8, 2, 11), (0, 1, 11),),  # 012 Vibraphone [88] / Hard Vibe [88] / Vib.w [88] / Vibraphone [55]
    12: ((0, 1, 12), (8, 1, 12),),  # 013 Marimba [55] / Marimba w [55]
    13: ((0, 1, 13),),  # 014 Xylophone [55]
    14: ((0, 3, 14),),  # 015 Tubular-bell [88Pro]
    15: ((0, 3, 15),),  # 016 Santur [88Pro]
    16: ((0, 2, 16), (1, 2, 16), (8, 2, 16), (9, 2, 16), (16, 2, 16), (17, 2, 16), (18, 2, 16), (32, 2, 16), (0, 1, 16), (8, 1, 16), (16, 1, 16), (32, 1, 16),),  # 017 Organ 1 [88] / Organ 101 [88] / DetunedOr.1 [88] / Organ 109 [88] / 60'sOrgan 1 [88] / 60'sOrgan 2 [88] / 60'sOrgan 3 [88] / Organ 4 [88] / Organ 1 [55] / Detuned Or1 [55] / 60's Organ1 [55] / Organ 4 [55]
    17: ((0, 2, 17), (1, 2, 17), (8, 2, 17), (32, 2, 17), (0, 1, 17), (8, 1, 17), (32, 1, 17),),  # 018 Organ 2 [88] / Organ 201 [88] / DetunedOr.2 [88] / Organ 5 [88] / Organ 2 [55] / Detuned Or2 [55] / Organ 5 [55]
    19: ((0, 1, 19), (8, 1, 19), (16, 1, 19),),  # 020 Church Org1 [55] / Church Org2 [55] / Church Org3 [55]
    21: ((0, 2, 21), (8, 2, 21), (0, 1, 21), (8, 1, 21),),  # 022 AccordionFr [88] / AccordionIt [88] / Accordion F [55] / Accordion I [55]
    22: ((0, 3, 22), (0, 2, 22), (1, 2, 22), (0, 1, 22),),  # 023 Harmonica [88Pro] / Harmonica [88] / Harmonica 2 [88] / Harmonica [55]
    23: ((0, 2, 23), (0, 1, 23),),  # 024 Bandoneon [88] / Bandoneon [55]
    24: ((0, 2, 24), (16, 2, 24), (32, 2, 24), (0, 1, 24), (8, 1, 24), (16, 1, 24), (32, 1, 24),),  # 025 Nylonstr.Gt [88] / Nylon Gt.o [88] / Nylon Gt.2 [88] / Nylon Gt. [55] / Ukulele [55] / Nylon Gt.o [55] / Nylon Gt.2 [55]
    25: ((0, 2, 25), (8, 2, 25), (9, 2, 25), (0, 1, 25), (8, 1, 25), (16, 1, 25),),  # 026 Steelstr.Gt [88] / 12-str.Gt [88] / Nylon+Steel [88] / Steel Gt. [55] / 12-str.Gt [55] / Mandolin [55]
    26: ((0, 2, 26), (8, 1, 26),),  # 027 Jazz Gt. [88] / Hawaiian Gt [55]
    27: ((0, 2, 27), (8, 2, 27), (0, 1, 27), (8, 1, 27),),  # 028 Clean Gt. [88] / Chorus Gt. [88] / Clean Gt. [55] / Chorus Gt. [55]
    28: ((0, 2, 28), (0, 1, 28), (8, 1, 28), (16, 1, 28),),  # 029 Muted Gt. [88] / Muted Gt. [55] / Funk Gt. [55] / Funk Gt.2 [55]
    29: ((0, 2, 29), (0, 1, 29),),  # 030 OverdriveGt [88] / OverdriveGt [55]
    30: ((0, 2, 30), (1, 2, 30), (17, 2, 30), (0, 1, 30), (8, 1, 30),),  # 031 DistortionGt [88] / Dist. Gt2 [88] / Power Gt.2 [88] / Dist.Gt. [55] / Feedback Gt [55]
    32: ((0, 3, 32), (0, 2, 32), (0, 1, 32),),  # 033 Acoustic Bs. [88Pro] / AcousticBs. [88] / Acoustic Bs [55]
    33: ((0, 2, 33), (1, 2, 33), (0, 1, 33),),  # 034 FingeredBs. [88] / FingeredBs2 [88] / Fingered Bs [55]
    34: ((0, 2, 34), (8, 2, 34), (0, 1, 34),),  # 035 Picked Bass [88] / MutePickBs. [88] / Picked Bass [55]
    35: ((1, 2, 35), (0, 1, 35),),  # 036 FretlessBs2 [88] / Fretless Bs [55]
    36: ((0, 1, 36),),  # 037 Slap Bass 1 [55]
    37: ((0, 1, 37),),  # 038 Slap Bass 2 [55]
    38: ((0, 1, 38), (8, 1, 38),),  # 039 Syn.Bass 1 [55] / Syn.Bass 3 [55]
    39: ((16, 2, 39), (0, 1, 39), (8, 1, 39),),  # 040 Rubber Bass [88] / Syn.Bass 2 [55] / Syn.Bass 4 [55]
    40: ((0, 2, 40), (8, 2, 40), (0, 1, 40), (8, 1, 40),),  # 041 Violin [88] / Slow Violin [88] / Violin [55] / Slow Violin [55]
    41: ((0, 2, 41), (0, 1, 41),),  # 042 Viola [88] / Viola [55]
    42: ((0, 3, 42), (1, 3, 42), (0, 2, 42), (0, 1, 42),),  # 043 Cello [88Pro] / Cello Atk. [88Pro] / Cello [88] / Cello [55]
    43: ((0, 3, 43), (0, 2, 43), (0, 1, 43),),  # 044 Contrabass [88Pro] / Contrabass [88] / Contrabass [55]
    44: ((0, 1, 44),),  # 045 Tremolo Str [55]
    45: ((0, 1, 45),),  # 046 Pizzicato [55]
    46: ((0, 1, 46),),  # 047 Harp [55]
    47: ((0, 1, 47),),  # 048 Timpani [55]
    48: ((0, 3, 48), (2, 3, 48), (24, 3, 48), (32, 3, 48), (0, 2, 48), (1, 2, 48), (8, 2, 48), (9, 2, 48), (11, 2, 48), (16, 2, 48), (0, 1, 48), (8, 1, 48),),  # 049 Strings [88Pro] / ChamberStr [88Pro] / Velo Strings [88Pro] / Oct Strings1 [88Pro] / Strings [88] / Strings 2 [88] / Orchestra [88] / Orchestra 2 [88] / Choir Str. [88] / St.Strings [88] / Strings [55] / Orchestra [55]
    49: ((0, 3, 49), (1, 3, 49), (0, 2, 49), (1, 2, 49), (10, 2, 49), (0, 1, 49),),  # 050 Slow Strings [88Pro] / SlowStrings2 [88Pro] / SlowStrings [88] / Slow Str. 2 [88] / St.SlowStr. [88] / SlowStrings [55]
    50: ((0, 2, 50), (1, 2, 50), (0, 1, 50),),  # 051 SynStrings1 [88] / OB Strings [88] / SynStrings1 [55]
    52: ((0, 2, 52), (8, 2, 52), (9, 2, 52), (32, 2, 52), (0, 1, 52), (32, 1, 52),),  # 053 Choir Aahs [88] / St.Choir [88] / Mello Choir [88] / ChoirAahs 2 [88] / Choir Aahs [55] / Choir Aahs2 [55]
    53: ((0, 3, 53), (0, 1, 53),),  # 054 Voice Oohs [88Pro] / Voice Oohs [55]
    55: ((0, 1, 55),),  # 056 Orchest.Hit [55]
    56: ((0, 3, 56), (0, 2, 56), (24, 2, 56), (0, 1, 56),),  # 057 Trumpet [88Pro] / Trumpet [88] / Bright Tp. [88] / Trumpet [55]
    57: ((0, 3, 57), (0, 2, 57), (1, 2, 57), (0, 1, 57),),  # 058 Trombone [88Pro] / Trombone [88] / Trombone 2 [88] / Trombone [55]
    58: ((0, 3, 58), (0, 1, 58),),  # 059 Tuba [88Pro] / Tuba [55]
    59: ((0, 1, 59),),  # 060 MuteTrumpet [55]
    60: ((8, 2, 60), (16, 2, 60), (0, 1, 60),),  # 061 Fr.HornSolo [88] / Horn Orch [88] / French Horn [55]
    61: ((0, 2, 61), (8, 2, 61), (0, 1, 61), (8, 1, 61),),  # 062 Brass 1 [88] / Brass 2 [88] / Brass 1 [55] / Brass 2 [55]
    62: ((0, 2, 62), (1, 2, 62), (8, 2, 62), (9, 2, 62), (16, 2, 62), (0, 1, 62), (16, 1, 62),),  # 063 SynthBrass1 [88] / Poly Brass [88] / Syn.Brass 3 [88] / Quack Brass [88] / OctaveBrass [88] / Syn.Brass 1 [55] / Analog Brs1 [55]
    63: ((0, 2, 63), (1, 2, 63), (8, 2, 63), (17, 2, 63), (16, 1, 63),),  # 064 Syn.Brass 2 [88] / Soft Brass [88] / Syn.Brass 4 [88] / VeloBrass 2 [88] / Analog Brs2 [55]
    64: ((0, 2, 64), (0, 1, 64),),  # 065 Soprano Sax [88] / Soprano Sax [55]
    65: ((0, 2, 65), (8, 2, 65), (0, 1, 65),),  # 066 Alto Sax [88] / Hyper Alto [88] / Alto Sax [55]
    66: ((0, 2, 66), (8, 2, 66), (0, 1, 66),),  # 067 Tenor Sax [88] / BreathyTnr. [88] / Tenor Sax [55]
    67: ((0, 2, 67), (0, 1, 67),),  # 068 BaritoneSax [88] / BaritoneSax [55]
    68: ((0, 3, 68), (0, 2, 68), (0, 1, 68),),  # 069 Oboe [88Pro] / Oboe [88] / Oboe [55]
    69: ((0, 1, 69),),  # 070 EnglishHorn [55]
    70: ((0, 1, 70),),  # 071 Bassoon [55]
    71: ((0, 3, 71), (0, 2, 71), (0, 1, 71),),  # 072 Clarinet [88Pro] / Clarinet [88] / Clarinet [55]
    72: ((0, 1, 72),),  # 073 Piccolo [55]
    73: ((0, 1, 73),),  # 074 Flute [55]
    75: ((0, 1, 75),),  # 076 Pan Flute [55]
    76: ((0, 1, 76),),  # 077 Bottle Blow [55]
    80: ((0, 2, 80), (1, 2, 80), (8, 2, 80),),  # 081 Square Wave [88] / Square [88] / Sine Wave [88]
    81: ((40, 3, 81), (0, 2, 81), (1, 2, 81),),  # 082 SequenceSaw1 [88Pro] / Saw Wave [88] / Saw [88]
    89: ((1, 2, 89), (4, 2, 89),),  # 090 Thick Pad [88] / Soft Pad [88]
    104: ((0, 3, 104),),  # 105 Sitar [88Pro]
    105: ((0, 1, 105),),  # 106 Banjo [55]
    107: ((0, 2, 107), (8, 1, 107),),  # 108 Koto [88] / Taisho Koto [55]
    108: ((0, 2, 108), (0, 1, 108),),  # 109 Kalimba [88] / Kalimba [55]
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


# (cc00, pc_0based) → keep 1 in N times Anima would have picked it (a tone the picks list overrides it).
# MandolinTrem (Steel-str.Gt CC00=18; 17 is Mandolin 2) is a looped tremolo — too sticky at equal weight.
ANIMA_TONE_RARE = {
    (18, 25): 8,
}

# Never pick as a standing variation. Reserved for a future one-shot articulation.
# Keys are (CC00, PC_0based). UI patch = PC_0based + 1.
ANIMA_TONE_BLOCK = {
    (24, 60),   # UI 061 / CC00 024  F.Horn Rip
    (16, 61),   # UI 062 / CC00 016  Brass Fall
    (17, 61),   # UI 062 / CC00 017  Trumpet Fall
}

# The user's picks from the "Anima Tone Palettes" page (tools/picker/build_tone_picker.py),
# per GM program (0-based): {(cc00, cc32, pc): {"w": w, "efx": -2..2, "note": "..."}}.
# w = 2 x the page's multiplier: 0 never, 2 normal, 4 x2, 6 x3 ..., 1 x1/2, 2/3 x1/3 .... A listed tone
# overrides ANIMA_TONE_RARE / ANIMA_TONE_BLOCK. efx and note are recorded for Anima's
# insert balance and phrasing; a program with no entry picks exactly as before.
# --- generated by tools/picker/apply_tone_picks.py from the Tone Palettes page ---
ANIMA_TONE_PREFS: dict = {
    0: {  # 001 Piano 1
        (0, 1, 0): {'efx': -1},  # Piano 1
        (0, 2, 0): {'efx': -1},  # Piano 1
        (0, 3, 0): {'efx': -1},  # Piano 1
        (0, 4, 0): {'w': 8, 'efx': -1},  # Piano 1
        (1, 4, 0): {'w': 1.0, 'efx': -1},  # UprightPiano
        (126, 1, 4): {'efx': -1},  # Piano 1
        (127, 1, 0): {'efx': -1},  # Acou Piano1
        (16, 1, 0): {'efx': -1},  # Piano 1d
        (16, 2, 0): {'efx': -1},  # Piano 1d
        (16, 4, 0): {'efx': -1},  # European Pf
        (2, 4, 0): {'w': 1.0, 'efx': -1},  # Mild Piano
        (24, 3, 0): {'efx': -1},  # Piano + Str.
        (24, 4, 0): {'efx': -1, 'note': 'stings attack fast like normal strings'},  # Piano + Str.
        (25, 4, 0): {'efx': -1, 'note': 'strings attack more like slow strings'},  # Piano + Str2
        (26, 4, 0): {'efx': -1},  # Piano+Choir1
        (27, 4, 0): {'efx': -1},  # Piano+Choir2
        (8, 1, 0): {'efx': -1},  # Piano 1w
        (8, 2, 0): {'efx': -1},  # Piano 1w
        (8, 3, 0): {'efx': -1},  # Piano 1w
        (8, 4, 0): {'efx': -1},  # Upright P w
        (9, 4, 0): {'efx': -1},  # Mild Piano w
    },
    1: {  # 002 Piano 2
        (0, 1, 1): {'efx': -1},  # Piano 2
        (0, 2, 1): {'efx': -1},  # Piano 2
        (0, 3, 1): {'efx': -1},  # Piano 2
        (0, 4, 1): {'w': 8, 'efx': -1},  # Piano 2
        (1, 4, 1): {'efx': -1},  # Pop Piano
        (126, 1, 0): {'efx': -1},  # Piano 2
        (127, 1, 1): {'efx': -1},  # Acou Piano2
        (16, 4, 1): {'efx': -1},  # Dance Piano
        (2, 4, 1): {'efx': -1},  # Rock Piano
        (8, 1, 1): {'efx': -1},  # Piano 2w
        (8, 2, 1): {'efx': -1},  # Piano 2w
        (8, 3, 1): {'efx': -1},  # Piano 2w
        (8, 4, 1): {'efx': -1},  # Pop Piano w
        (9, 4, 1): {'efx': -1},  # Rock Piano w
    },
    2: {  # 003 Piano 3
        (0, 1, 2): {'efx': -1},  # Piano 3
        (0, 2, 2): {'efx': -1},  # Piano 3
        (0, 4, 2): {'w': 8, 'efx': -1},  # Piano 3
        (1, 2, 2): {'efx': -1},  # EG+Rhodes 1
        (1, 4, 2): {'efx': -1},  # EG+Rhodes 1
        (127, 1, 2): {'efx': -1},  # Acou Piano3
        (2, 4, 2): {'w': 4, 'efx': -1},  # EG+Rhodes 2
        (8, 1, 2): {'efx': -1},  # Piano 3w
        (8, 2, 2): {'efx': -1},  # Piano 3w
        (8, 4, 2): {'w': 4, 'efx': -1},  # Piano 3w
    },
    3: {  # 004 Honky-tonk
        (0, 1, 3): {'efx': -1},  # Honky-tonk
        (0, 2, 3): {'efx': -1},  # Honky-tonk
        (0, 3, 3): {'efx': -1},  # Honky-tonk
        (0, 4, 3): {'w': 8, 'efx': -1},  # Honky-tonk
        (126, 1, 3): {'efx': -1},  # Honky-tonk
        (127, 1, 7): {'efx': -1},  # Honkytonk
        (8, 1, 3): {'efx': -1},  # HonkyTonk w
        (8, 2, 3): {'w': 4, 'efx': -1},  # Old Upright
        (8, 3, 3): {'efx': -1},  # Honky-tonk 2
        (8, 4, 3): {'efx': -1},  # Honky-tonk 2
    },
    4: {  # 005 E.Piano 1
        (0, 4, 4): {'w': 8},  # E.Piano 1
        (10, 4, 4): {'w': 4},  # SilentRhodes
        (9, 4, 4): {'w': 1.0},  # Cho. E.Piano
    },
    5: {  # 006 E.Piano 2
        (0, 4, 5): {'w': 8},  # E.Piano 2
        (16, 4, 5): {'w': 4},  # St.FM EP
    },
    6: {  # 007 Harpsichord
        (0, 1, 6): {'efx': -1},  # Harpsichord
        (0, 3, 6): {'efx': -1},  # Harpsichord
        (0, 4, 6): {'efx': -1},  # Harpsichord
        (1, 4, 6): {'efx': -1},  # Harpsichord2
        (127, 1, 16): {'efx': -1},  # Harpsi 1
        (127, 1, 17): {'efx': -1},  # Harpsi 2
        (127, 1, 18): {'efx': -1},  # Harpsi 3
        (16, 1, 6): {'efx': -1},  # Harpsi.w
        (16, 3, 6): {'efx': -1},  # Harpsi.w
        (16, 4, 6): {'efx': -1},  # Harpsi.w
        (2, 4, 6): {'efx': -1},  # Harpsichord3
        (24, 1, 6): {'efx': -1},  # Harpsi.o
        (24, 3, 6): {'efx': -1},  # Harpsi.o
        (24, 4, 6): {'efx': -1},  # Harpsi.o
        (32, 4, 6): {'w': 1.0, 'efx': -1},  # Synth Harpsi
        (8, 4, 6): {'w': 4, 'efx': -1},  # Coupled Hps.
    },
    7: {  # 008 Clav.
        (16, 4, 7): {'efx': -1},  # Reso Clav.
        (17, 4, 7): {'efx': -1},  # Phase Clav
        (8, 4, 7): {'w': 1.0},  # Comp Clav.
    },
    8: {  # 009 Celesta
        (0, 4, 8): {'efx': -1},  # Celesta
        (1, 4, 8): {'efx': -1},  # Pop Celesta
        (127, 1, 22): {'efx': -1},  # Celesta 1
        (127, 1, 23): {'efx': -1},  # Celesta 2
    },
    11: {  # 012 Vibraphone
        (1, 4, 11): {'w': 4},  # Pop Vibe.
        (9, 4, 11): {'w': 8},  # Vibraphones
    },
    12: {  # 013 Marimba
        (0, 1, 12): {'w': 1.0},  # Marimba
        (127, 1, 104): {'w': 1.0},  # Marimba
        (16, 4, 12): {'w': 6},  # Barafon
        (8, 4, 12): {'w': 4},  # Marimba w
    },
    13: {  # 014 Xylophone
        (0, 1, 13): {'efx': -1},  # Xylophone
        (0, 4, 13): {'efx': -1},  # Xylophone
        (127, 1, 103): {'efx': -1},  # Xylophone
        (8, 4, 13): {'w': 4, 'efx': -1},  # Xylophone w
    },
    15: {  # 016 Santur
        (0, 3, 15): {'w': 1.0, 'efx': -1},  # Santur
        (0, 4, 15): {'efx': -1},  # Santur
        (1, 4, 15): {'efx': -1},  # Santur 2
        (16, 4, 15): {'efx': -1},  # Zither 1
        (17, 4, 15): {'efx': -1},  # Zither 2
        (2, 4, 15): {'efx': -1},  # Santur 3
        (24, 4, 15): {'w': 4, 'efx': -1},  # Dulcimer
        (8, 4, 15): {'efx': -1},  # Cimbalom
    },
    16: {  # 017 Organ 1
        (0, 4, 16): {'w': 4},  # Organ 1
        (1, 2, 16): {'w': 1.0},  # Organ 101
        (1, 4, 16): {'w': 1.0},  # Organ 101
        (127, 1, 8): {'w': 4},  # Elec Org 1
        (127, 1, 9): {'w': 4},  # Elec Org 2
        (16, 2, 16): {'note': 'has a fast vibrato'},  # 60'sOrgan 1
        (17, 2, 16): {'note': 'has a fast vibrato'},  # 60'sOrgan 2
        (17, 4, 16): {'w': 4},  # 60's Organ 2
        (18, 2, 16): {'note': 'has a fast vibrato'},  # 60'sOrgan 3
        (2, 4, 16): {'w': 4},  # Ful Organ 1
        (24, 4, 16): {'w': 1.0},  # Cheese Organ
        (25, 4, 16): {'w': 4},  # D-50 Organ
        (28, 4, 16): {'w': 1.0},  # VS Organ
        (29, 4, 16): {'w': 1.0},  # Digi Church
        (30, 4, 16): {'w': 1.0},  # JX8 Organ
        (33, 4, 16): {'w': 8},  # Even Bar
        (40, 4, 16): {'w': 1.0},  # Organ Bass
        (48, 4, 16): {'w': 1.0, 'efx': -1, 'note': 'plays fifths - may need to be voiced appropriately'},  # 5th Organ
        (8, 1, 16): {'w': 1.0},  # Detuned Or1
        (8, 2, 16): {'w': 1.0, 'efx': -1},  # DetunedOr.1
    },
    17: {  # 018 Organ 2
        (0, 4, 17): {'w': 4},  # Organ 2
        (1, 4, 17): {'w': 6},  # Jazz Organ
        (127, 1, 10): {'w': 4},  # Elec Org 3
        (127, 1, 11): {'w': 4},  # Elec Org 4
        (32, 4, 17): {'w': 4},  # Perc. Organ
        (34, 4, 17): {'note': 'thinner sounding'},  # Perc.Organ 3
        (35, 4, 17): {'note': 'waveform has rotary'},  # Perc.Organ 4
        (5, 4, 17): {'w': 1.0},  # Jazz Organ 4
        (8, 4, 17): {'efx': -1},  # Chorus Or.2
        (9, 4, 17): {'note': 'has built-in -12 octave'},  # Octave Organ
    },
    18: {  # 019 Organ 3
        (17, 4, 18): {'w': 4},  # Rock Organ 1
    },
    19: {  # 020 Church Org.1
        (127, 1, 12): {'w': 10},  # Pipe Org 1
        (127, 1, 13): {'w': 6},  # Pipe Org 2
        (16, 1, 19): {'w': 4},  # Church Org3
        (16, 4, 19): {'w': 8},  # Church Org.3
        (24, 4, 19): {'note': 'soft and intimate'},  # Organ Flute
        (32, 4, 19): {'efx': -1, 'note': 'now with built-in tremolo'},  # Trem.Flute
        (33, 4, 19): {'w': 1.0, 'efx': -1, 'note': 'very fast tremolo'},  # Theater Org.
        (8, 1, 19): {'w': 4},  # Church Org2
    },
    20: {  # 021 Reed Organ
        (0, 4, 20): {'efx': -1},  # Reed Organ
        (16, 4, 20): {'w': 1.0, 'efx': -1, 'note': 'calliope-like but bigger and deeper.'},  # Puff Organ
        (8, 4, 20): {'w': 4, 'efx': -1, 'note': 'Nice. less accordion-like the regular reed organ.'},  # Wind Organ
    },
    21: {  # 022 Accordion Fr
        (0, 1, 21): {'w': 1.0},  # Accordion F
        (0, 2, 21): {'w': 0.6667},  # AccordionFr
        (16, 4, 21): {'w': 1.0},  # Cho. Accord
        (8, 2, 21): {'w': 0.6667},  # AccordionIt
        (8, 4, 21): {'w': 4},  # Accordion It
        (9, 4, 21): {'w': 1.0},  # Dist. Accord
    },
    23: {  # 024 Bandoneon
        (8, 4, 23): {'w': 4},  # Bandoneon 2
    },
    24: {  # 025 Nylon-str.Gt
        (0, 4, 24): {'w': 8},  # Nylon-str.Gt
        (127, 1, 59): {'w': 1.0},  # Guitar 1
        (24, 4, 24): {'w': 8},  # Velo Harmnix
        (32, 4, 24): {'w': 4},  # Nylon Gt.2
        (8, 1, 24): {'note': 'shorter sustain, flatter sound'},  # Ukulele
        (8, 4, 24): {'note': 'shorter sustain'},  # Ukulele
    },
    25: {  # 026 Steel-str.Gt
        (0, 4, 25): {'w': 4},  # Steel-str.Gt
        (10, 4, 25): {'w': 4},  # Atk Steel Gt
        (127, 1, 60): {'w': 1.0},  # Guitar 2
        (17, 4, 25): {'w': 1.0},  # Mandolin 2
        (18, 4, 25): {'w': 1.0, 'note': 'has a sustained tremolo strumming sample.  play accordingly.'},  # MandolinTrem
        (32, 4, 25): {'w': 4, 'note': 'more prominent high-tone in the sound.'},  # Steel Gt.2
        (33, 4, 25): {'note': 'nice separation, probably better for solos'},  # Steel + Body
        (8, 4, 25): {'w': 4, 'note': '12 string style color.'},  # 12-str.Gt
        (9, 4, 25): {'note': 'great separation, probably good for solos.'},  # Nylon+Steel
    },
    32: {  # 033 Acoustic Bs.
        (1, 4, 32): {'w': 6},  # Rockabilly
        (16, 4, 32): {'w': 1.0},  # Bass + OHH
    },
    33: {  # 034 Fingered Bs.
        (16, 4, 33): {'w': 1.0},  # F.Bass/Harm.
        (4, 4, 33): {'w': 4.0},  # Rock Bass
        (5, 4, 33): {'w': 4.0},  # Heart Bass
    },
    34: {  # 035 Picked Bass
        (16, 4, 34): {'w': 1.0},  # P.Bass/Harm.
    },
    35: {  # 036 Fretless Bs.
        (5, 4, 35): {'w': 4},  # Mr.Smooth
    },
    36: {  # 037 Slap Bass 1
        (0, 4, 36): {'w': 4},  # Slap Bass 1
        (1, 4, 36): {'w': 6, 'note': 'Seinfeld!'},  # Slap Pop
        (126, 1, 15): {'w': 1.0},  # Slap Bass 1
        (127, 1, 68): {'w': 1.0},  # Slap Bass 1
        (8, 4, 36): {'w': 1.0, 'note': 'built-in filter resonance.'},  # Reso Slap
        (9, 4, 36): {'w': 4},  # Unison Slap
    },
    37: {  # 038 Slap Bass 2
        (1, 4, 37): {'w': 4},  # Slap Bass 3
    },
    38: {  # 039 Synth Bass 1
        (0, 4, 38): {'w': 4},  # Synth Bass 1
        (1, 4, 38): {'w': 4},  # SynthBass101
        (10, 4, 38): {'w': 1.0},  # Tekno Bass
        (16, 4, 38): {'w': 4},  # Reso SH Bass
        (17, 4, 38): {'w': 1.0},  # TB303 Sqr Bs
        (18, 4, 38): {'w': 1.0},  # TB303 DistBs
        (21, 4, 38): {'note': 'basically a subwoofer bass sound.'},  # Jungle Bass
        (24, 4, 38): {'w': 1.0, 'note': 'has a sustained arpeggio sound'},  # Arpeggio Bs
        (42, 4, 38): {'w': 1.0},  # 303SqDistBs3
        (44, 4, 38): {'w': 1.0},  # TeeBee
        (9, 4, 38): {'w': 4},  # TB303 Bass
    },
    39: {  # 040 Synth Bass 2
        (0, 4, 39): {'w': 4},  # Synth Bass 2
        (1, 4, 39): {'w': 4},  # SynthBass201
        (13, 4, 39): {'w': 4},  # RubberBass 1
        (16, 4, 39): {'w': 6},  # RubberBass 2
        (25, 4, 39): {'note': 'plays fifths.'},  # MG 5th Bass
        (26, 4, 39): {'note': 'sustain has a random sounding arpeggiation.'},  # RND Bass
        (3, 4, 39): {'note': 'short stab'},  # Seq Bass
        (33, 4, 39): {'note': 'short stab'},  # Seq Bass 2
        (34, 4, 39): {'note': 'plays thirds'},  # 3rd Bass
        (35, 4, 39): {'note': 'has -12 sub octave built-in'},  # MG Oct Bass
        (5, 4, 39): {'note': 'has -12 sub octave built-in'},  # Mg Oct Bass1
        (6, 4, 39): {'note': 'has -12 sub octave built-in'},  # MG Oct Bass2
    },
    40: {  # 041 Violin
        (0, 4, 40): {'w': 4, 'note': 'has built-in legato support.'},  # Violin
        (1, 4, 40): {'w': 4, 'note': 'slightly faster attack transient and has built-in legato support.'},  # Violin Atk
        (8, 4, 40): {'note': 'slightly slower attack transient.'},  # Slow Violin
    },
    41: {  # 042 Viola
        (0, 4, 41): {'w': 4, 'note': 'has built-in legato support.'},  # Viola
        (1, 4, 41): {'w': 4, 'note': 'slightly deeper attack transient and has built-in legato support.'},  # Viola Atk.
    },
    42: {  # 043 Cello
        (0, 4, 42): {'w': 6, 'note': 'has built-in legato support.'},  # Cello
        (1, 4, 42): {'w': 6, 'note': 'slightly thicker attack transient and has built-in legato support.'},  # Cello Atk.
    },
    44: {  # 045 Tremolo Str
        (0, 4, 44): {'note': 'tremolo, probably best to not select too thick or fast chorus or other LFO type effect.'},  # Tremolo Str
        (10, 4, 44): {'note': 'Nice wider mix of normal and tremolo strings'},  # SuspenseStr2
        (2, 4, 44): {'w': 4},  # Trem Str.St.
        (8, 4, 44): {'w': 1.0, 'note': 'slow attack.  use for slower or known longer sustained notes, or as a tension fade-in.  Then stab with something else!'},  # Slow Tremolo
        (9, 4, 44): {'note': 'Nice wider mix of normal and tremolo strings'},  # Suspense Str
    },
    45: {  # 046 PizzicatoStr
        (1, 4, 45): {'note': 'Cello & Contrabass Pizz only.  useful for low end ensemble pizz parts, or maybe an alternative as a sort of big group-type acoustic bass'},  # Vcs&Cbs Pizz
        (16, 4, 45): {'note': 'not pizz, but spiccato!  great for accents or solo spiccato string playing.'},  # Solo Spic.
        (17, 4, 45): {'note': 'not pizz, but spiccato!  great for accents of ensemble spiccato string playing'},  # StringsSpic.
        (2, 4, 45): {'w': 4, 'note': 'more intimate pizz section.'},  # Chamber Pizz
        (3, 4, 45): {'w': 4, 'note': 'nice and wide full string ensemble pizz.'},  # St.Pizzicato
        (8, 4, 45): {'note': 'very intimate, as it says, great for a solo Pizz phrase.'},  # Solo Pizz.
    },
    46: {  # 047 Harp
        (0, 4, 46): {'w': 4},  # Harp
        (16, 4, 46): {'note': 'synth harp sound.'},  # Synth Harp
        (2, 4, 46): {'w': 6},  # Harp St.
        (8, 4, 46): {'w': 4},  # Uillean Harp
    },
    81: {  # 082 Saw Wave
        (40, 4, 81): {'note': "short stab sound that doesn't loop, we should select/play accordingly. good for arp style playing only probably."},  # SequenceSaw1
        (41, 4, 81): {'note': "short stab sound that doesn't loop, we should select/play accordingly. good for arp style playing only probably."},  # SequenceSaw2
    },
    114: {  # 115 Steel Drums
        (1, 4, 114): {'w': 4},  # Island Mlt
    },
}
# --- end generated picks ---

# What the Tone Palettes notes mean for Duality: (cc00, cc32, pc) -> traits.
#   lfo      the sample already moves: no chorus / flanger / phaser / tremolo / auto-pan / rotary insert
#   rotary   a rotary speaker is in the sample: no rotary insert, no CC16 speed flips
#   echo     no delay insert
#   interval the tone plays extra pitches (fifths, a third, an octave, a sub): no harmony ghosts,
#            no bass sub-octave, no pitch-shifter insert
#   short    a stab that does not loop: if the part holds notes, back to the capital at a rest
#   slow     slow attack: if the part plays short quick notes, back to the capital at a rest
#   low      a low-register tone: if the part plays high, back to the capital at a rest
ANIMA_TONE_TRAITS = {
    (16, 2, 16): frozenset({"lfo"}),              # 60'sOrgan 1 [88]: fast vibrato
    (17, 2, 16): frozenset({"lfo"}),              # 60'sOrgan 2 [88]: fast vibrato
    (18, 2, 16): frozenset({"lfo"}),              # 60'sOrgan 3 [88]: fast vibrato
    (48, 4, 16): frozenset({"interval"}),         # 5th Organ: plays fifths
    (35, 4, 17): frozenset({"lfo", "rotary"}),    # Perc.Organ 4: rotary in the waveform
    (9, 4, 17): frozenset({"interval"}),          # Octave Organ: built-in -12
    (32, 4, 19): frozenset({"lfo"}),              # Trem.Flute: built-in tremolo
    (33, 4, 19): frozenset({"lfo"}),              # Theater Org.: very fast tremolo
    (18, 4, 25): frozenset({"lfo", "echo"}),      # MandolinTrem: sustained tremolo strumming
    (21, 4, 38): frozenset({"interval"}),         # Jungle Bass: a sub-woofer bass already
    (24, 4, 38): frozenset({"lfo", "interval"}),  # Arpeggio Bs: sustained arpeggio
    (25, 4, 39): frozenset({"interval"}),         # MG 5th Bass: plays fifths
    (26, 4, 39): frozenset({"lfo", "interval"}),  # RND Bass: random arpeggiation in the sustain
    (3, 4, 39): frozenset({"short"}),             # Seq Bass: short stab
    (33, 4, 39): frozenset({"short"}),            # Seq Bass 2: short stab
    (34, 4, 39): frozenset({"interval"}),         # 3rd Bass: plays thirds
    (35, 4, 39): frozenset({"interval"}),         # MG Oct Bass: -12 built in
    (5, 4, 39): frozenset({"interval"}),          # Mg Oct Bass1: -12 built in
    (6, 4, 39): frozenset({"interval"}),          # MG Oct Bass2: -12 built in
    (0, 4, 44): frozenset({"lfo"}),               # Tremolo Str: no thick / fast chorus or LFO
    (8, 4, 44): frozenset({"lfo", "slow"}),       # Slow Tremolo: slow attack, long notes
    (1, 4, 45): frozenset({"low"}),               # Vcs&Cbs Pizz: cellos and basses only
    (40, 4, 81): frozenset({"short"}),            # SequenceSaw1: stab, does not loop
    (41, 4, 81): frozenset({"short"}),            # SequenceSaw2: stab, does not loop
}


def anima_tone_traits(key) -> frozenset:
    """Traits of the tone at (cc00, cc32, pc); a file bank on CC32 0 reads as the 8850 map."""
    if not key:
        return frozenset()
    c0, c32, p = (int(x) & 0x7F for x in key)
    return ANIMA_TONE_TRAITS.get((c0, c32, p)) or (ANIMA_TONE_TRAITS.get((c0, 4, p)) if c32 == 0 else None) or frozenset()


def anima_tone_pref(gm_pc: int, key) -> dict:
    """The user's pick for one tone slot under a GM program ({} = default)."""
    return (ANIMA_TONE_PREFS.get(int(gm_pc) & 0x7F) or {}).get(tuple(key)) or {}


def anima_tone_weight(gm_pc: int, key) -> float:
    """Pick weight, 2 x the multiplier: 0 never, 2 normal, 4 x2, 1 x1/2 ..."""
    w = anima_tone_pref(gm_pc, key).get("w")
    return 2 if w is None else max(0.0, float(w))


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
