"""Anima category maps (GM, MT-32 factory, Sierra banks).

Phrasing tunables stay in duality.py.
"""
from __future__ import annotations

# ----------------------------------------------------------------------
# MT-32 recognition tables (Based on Roland MT-32 and compatibles)
# ----------------------------------------------------------------------
MT32_REVERB_MODES = {
    0: "Room",
    1: "Hall",
    2: "Plate",
    3: "Tap Delay",
}
# MT-32 / CM-32L LA patches (CM-64 manual p.8-9, PC 1-128) -> the nearest GM program, for Anima's
# GM-numbered sets (mallet sticking, unroll, Hetfield, acoustic strum) on native MT-32 streams.
MT32_TO_GM = (
      0,  #   1 AcouPiano 1
      1,  #   2 AcouPiano 2
      0,  #   3 AcouPiano 3
      4,  #   4 ElecPiano 1
      5,  #   5 ElecPiano 2
      4,  #   6 ElecPiano 3
      5,  #   7 ElecPiano 4
      3,  #   8 Honkytonk
     16,  #   9 Elec Org 1
     17,  #  10 Elec Org 2
     18,  #  11 Elec Org 3
     16,  #  12 Elec Org 4
     19,  #  13 Pipe Org 1
     19,  #  14 Pipe Org 2
     20,  #  15 Pipe Org 3
     21,  #  16 Accordion
      6,  #  17 Harpsi 1
      6,  #  18 Harpsi 2
      6,  #  19 Harpsi 3
      7,  #  20 Clavi 1
      7,  #  21 Clavi 2
      7,  #  22 Clavi 3
      8,  #  23 Celesta 1
      8,  #  24 Celesta 2
     62,  #  25 SynBrass 1
     63,  #  26 SynBrass 2
     62,  #  27 SynBrass 3
     63,  #  28 SynBrass 4
     38,  #  29 Syn Bass 1
     39,  #  30 Syn Bass 2
     38,  #  31 Syn Bass 3
     39,  #  32 Syn Bass 4
     88,  #  33 Fantasy
     89,  #  34 Harmo Pan
     91,  #  35 Chorale
     98,  #  36 Glasses
     97,  #  37 Soundtrack
     99,  #  38 Atmosphere
     98,  #  39 Warm Bell
     85,  #  40 Funny Vox
    102,  #  41 Echo Bell
     96,  #  42 Ice Rain
     68,  #  43 Oboe 2001
     75,  #  44 Echo Pan
     80,  #  45 DoctorSolo
    100,  #  46 Schooldaze
     98,  #  47 Bellsinger
     80,  #  48 SquareWave
     48,  #  49 Str Sect 1
     49,  #  50 Str Sect 2
     48,  #  51 Str Sect 3
     45,  #  52 Pizzicato
     40,  #  53 Violin 1
     40,  #  54 Violin 2
     42,  #  55 Cello 1
     42,  #  56 Cello 2
     43,  #  57 Contrabass
     46,  #  58 Harp 1
     46,  #  59 Harp 2
     24,  #  60 Guitar 1
     25,  #  61 Guitar 2
     26,  #  62 Elec Gtr 1
     27,  #  63 Elec Gtr 2
    104,  #  64 Sitar
     32,  #  65 AcouBass 1
     32,  #  66 AcouBass 2
     33,  #  67 ElecBass 1
     34,  #  68 ElecBass 2
     36,  #  69 SlapBass 1
     37,  #  70 SlapBass 2
     35,  #  71 Fretless 1
     35,  #  72 Fretless 2
     73,  #  73 Flute 1
     73,  #  74 Flute 2
     72,  #  75 Piccolo 1
     72,  #  76 Piccolo 2
     74,  #  77 Recorder
     75,  #  78 Pan Pipes
     64,  #  79 Sax 1
     65,  #  80 Sax 2
     66,  #  81 Sax 3
     67,  #  82 Sax 4
     71,  #  83 Clarinet 1
     71,  #  84 Clarinet 2
     68,  #  85 Oboe
     69,  #  86 Engl Horn
     70,  #  87 Bassoon
     22,  #  88 Harmonica
     56,  #  89 Trumpet 1
     56,  #  90 Trumpet 2
     57,  #  91 Trombone 1
     57,  #  92 Trombone 2
     60,  #  93 Fr Horn 1
     60,  #  94 Fr Horn 2
     58,  #  95 Tuba
     61,  #  96 Brs Sect 1
     61,  #  97 Brs Sect 2
     11,  #  98 Vibe 1
     11,  #  99 Vibe 2
     11,  # 100 Syn Mallet
     14,  # 101 Windbell
      9,  # 102 Glock
     14,  # 103 Tube Bell
     13,  # 104 Xylophone
     12,  # 105 Marimba
    107,  # 106 Koto
    109,  # 107 Sho
     77,  # 108 Shakuhachi
     78,  # 109 Whistle 1
     78,  # 110 Whistle 2
     76,  # 111 Bottleblow
     76,  # 112 Breathpipe
     47,  # 113 Timpani
    117,  # 114 MelodicTom
    118,  # 115 Deep Snare
    118,  # 116 ElecPerc 1
    118,  # 117 ElecPerc 2
    116,  # 118 Taiko
    116,  # 119 Taiko Rim
    119,  # 120 Cymbal
    115,  # 121 Castanets
    115,  # 122 Triangle
     55,  # 123 Orche Hit
    124,  # 124 Telephone
    123,  # 125 Bird Tweet
     98,  # 126 OneNoteJam
    112,  # 127 WaterBells
    101,  # 128 JungleTune
)


def _gm_category(program: int) -> str:
    """Map GM program 0–127 to a coarse articulation category."""
    p = max(0, min(127, int(program)))
    if p <= 7:
        return "piano"
    if p <= 15:
        return "chromatic"
    if p <= 23:
        return "organ"
    if p <= 31:
        return "guitar"
    if p <= 39:
        return "bass"
    if p <= 47:
        return "strings"
    if p <= 55:
        return "ensemble"
    if p <= 63:
        return "brass"
    if p <= 79:
        return "wind"
    if p <= 87:
        return "lead"
    if p <= 95:
        return "pad"
    if p <= 103:
        return "fx"
    if p <= 111:
        return "ethnic"
    if p <= 119:
        return "percussive"
    return "sfx"


# Roland MT-32 factory timbre / default patch map (program 0–127).
# Used when the stream is native MT-32 (not a Voodoo GM bank).
_MT32_DEFAULT_CAT = [
    # Preset A 0–63
    "piano","piano","piano","piano","piano","piano","piano","piano",          # 0–7 pianos / honky
    "organ","organ","organ","organ","organ","organ","organ","organ",          # 8–15 organs / accordion
    "chromatic","chromatic","chromatic","chromatic","chromatic","chromatic","chromatic","chromatic",  # 16–23 harpsi/clavi/celesta
    "brass","brass","brass","brass","bass","bass","bass","bass",              # 24–31 syn brass / syn bass
    "pad","pad","ensemble","fx","pad","pad","chromatic","fx",                 # 32–39 Fantasy…Funny Vox
    "fx","fx","wind","fx","lead","fx","chromatic","lead",                     # 40–47 Echo Bell…Square Wave
    "strings","strings","strings","strings","strings","strings","strings","strings",  # 48–55 strings
    "strings","strings","strings","guitar","guitar","guitar","guitar","ethnic",       # 56–63 bass-str / harp / gtr / sitar
    # Preset B 64–127
    "bass","bass","bass","bass","bass","bass","bass","bass",                  # 64–71 basses
    "wind","wind","wind","wind","wind","wind","wind","wind",                  # 72–79 flute…sax2
    "wind","wind","wind","wind","wind","wind","wind","wind",                  # 80–87 sax3…harmonica
    "brass","brass","brass","brass","brass","brass","brass","ensemble",        # 88–95 Tpt…Tuba, Brs Sect 1
    "ensemble","chromatic","chromatic","chromatic","ethnic","wind","wind","chromatic",  # 96–103 Brs2, Vibe1/2, Kalimba/Marimba, Koto, Sho, Shak, Tinkle
    "percussive","percussive","percussive","percussive","percussive","percussive","ensemble","sfx",  # 104–111
    "fx","fx","fx","sfx","sfx","sfx","sfx","sfx",                              # 112–119
    "sfx","sfx","sfx","sfx","sfx","sfx","sfx","sfx",                          # 120–127
]


def _mt32_category(program: int) -> str:
    p = max(0, min(127, int(program)))
    return _MT32_DEFAULT_CAT[p]


# Detect Sierra (and similar) custom MT-32 banks from the *stream*, not Voodoo load.
# Match display text and distinctive timbre names that soundtrack MIDIs dump at start.
ANIMA_BANK_SIGNATURES = (
    # Title needles are unique. Do NOT use "Quest Studios" — every QS dump
    # ends with that credit and would steal the bank.
    (("leisure suit larry", "larry 3"),
     "lsl3", "sfx", "Larry 3"),
    (("space quest 4", "space quest iv"),
     "sq4", "sfx", "Space Quest 4"),
    (("king's quest 5", "king's quest v"),
     "kq5", "sfx", "King's Quest 5"),
)
# Extra timbre names only used if no title has locked a bank yet
ANIMA_BANK_NAME_HINTS = (
    (("open box", "airlock2", "coolphone"), "lsl3", "sfx", "Larry 3"),
    (("shipdoplr", "resosynth", "takeoff ms", "spaceguit"), "sq4", "sfx", "Space Quest 4"),
    (("firedart", "lone wolf", "frogger", "whiporill"), "kq5", "sfx", "King's Quest 5"),
)

ANIMA_SIERRA_PC = {
    "lsl3": {0: "P113", 1: "P114", 2: "P119", 3: "P113", 4: "P119", 5: "sfx", 6: "P124", 7: "P103", 8: "P51", 9: "P112", 10: "P84", 11: "P2", 12: "P108", 13: "P8", 14: "P63", 15: "P110", 16: "P107", 17: "P43", 18: "P32", 19: "sfx", 20: "P62", 21: "P78", 22: "P72", 23: "P44", 24: "P73", 25: "P75", 26: "P82", 27: "P62", 28: "P86", 29: "P105", 30: "P48", 31: "P50", 32: "P81", 33: "P62", 34: "P60", 35: "P95", 36: "P37", 37: "P68", 38: "P94", 39: "P64", 40: "P117", 41: "P7", 42: "P92", 43: "P70", 44: "P36", 45: "P90", 46: "P91", 47: "P34", 48: "P58", 49: "P109", 50: "P39", 51: "P7", 52: "P59", 53: "P95", 54: "P68", 55: "P3", 56: "P61", 57: "sfx", 58: "P89", 59: "P88", 60: "P59", 61: "P1", 62: "P97", 63: "P93", 64: "P50", 65: "P79", 66: "P47", 67: "P38", 68: "P122", 69: "P52", 70: "sfx", 71: "sfx", 72: "sfx", 73: "sfx", 74: "sfx", 75: "sfx", 76: "percussive", 77: "sfx", 78: "percussive", 79: "sfx", 80: "bass", 81: "sfx", 82: "sfx", 83: "sfx", 84: "sfx", 85: "sfx", 86: "sfx", 87: "sfx", 88: "sfx", 89: "sfx", 90: "sfx", 91: "sfx", 92: "sfx", 93: "P87", 94: "P104", 95: "P24", 96: "P96", 97: "P97", 98: "P98", 99: "P99", 100: "P100", 101: "P101", 102: "P102", 103: "P103", 104: "P104", 105: "P105", 106: "P106", 107: "P107", 108: "P108", 109: "P109", 110: "P110", 111: "P111", 112: "P112", 113: "P113", 114: "P114", 115: "P115", 116: "P116", 117: "P117", 118: "P118", 119: "P119", 120: "P120", 121: "P121", 122: "P122", 123: "P123", 124: "P124", 125: "P125", 126: "P126", 127: "P127"},
    "sq4": {0: "sfx", 1: "percussive", 2: "sfx", 3: "piano", 4: "P49", 5: "P50", 6: "P51", 7: "P34", 8: "pad", 9: "P37", 10: "P41", 11: "P88", 12: "P25", 13: "P30", 14: "P31", 15: "P32", 16: "P7", 17: "P92", 18: "P72", 19: "P101", 20: "P102", 21: "P38", 22: "P112", 23: "P43", 24: "lead", 25: "P122", 26: "P8", 27: "P104", 28: "P69", 29: "ensemble", 30: "sfx", 31: "sfx", 32: "brass", 33: "P12", 34: "P78", 35: "sfx", 36: "P87", 37: "P62", 38: "P64", 39: "guitar", 40: "P57", 41: "sfx", 42: "sfx", 43: "P86", 44: "chromatic", 45: "pad", 46: "sfx", 47: "sfx", 48: "sfx", 49: "P0", 50: "sfx", 51: "sfx", 52: "sfx", 53: "sfx", 54: "sfx", 55: "sfx", 56: "sfx", 57: "sfx", 58: "sfx", 59: "sfx", 60: "sfx", 61: "sfx", 62: "sfx", 63: "sfx", 64: "sfx", 65: "sfx", 66: "sfx", 67: "sfx", 68: "sfx", 69: "sfx", 70: "sfx", 71: "sfx", 72: "sfx", 73: "sfx", 74: "sfx", 75: "guitar", 76: "sfx", 77: "sfx", 78: "sfx", 79: "sfx", 80: "sfx", 81: "ensemble", 82: "bass", 83: "sfx", 84: "sfx", 85: "sfx", 86: "sfx", 87: "pad", 88: "sfx", 89: "sfx", 90: "sfx", 91: "sfx", 92: "sfx", 93: "sfx", 94: "P0", 95: "P0", 96: "P96", 97: "P97", 98: "P98", 99: "P99", 100: "P100", 101: "P101", 102: "P102", 103: "P103", 104: "P104", 105: "P105", 106: "P106", 107: "P107", 108: "P108", 109: "P109", 110: "P110", 111: "P111", 112: "P112", 113: "P113", 114: "P114", 115: "P115", 116: "P116", 117: "P117", 118: "P118", 119: "P119", 120: "P120", 121: "P121", 122: "P122", 123: "P123", 124: "P124", 125: "P125", 126: "P126", 127: "P127"},
    "kq5": {0: "P0", 1: "P0", 2: "P0", 3: "P0", 4: "P0", 5: "P59", 6: "strings", 7: "pad", 8: "brass", 9: "pad", 10: "wind", 11: "chromatic", 12: "brass", 13: "wind", 14: "strings", 15: "wind", 16: "strings", 17: "strings", 18: "P86", 19: "P85", 20: "P15", 21: "P112", 22: "P108", 23: "P89", 24: "P95", 25: "P56", 26: "P63", 27: "P57", 28: "wind", 29: "P49", 30: "P12", 31: "P0", 32: "P0", 33: "P0", 34: "P0", 35: "P0", 36: "P0", 37: "P0", 38: "P0", 39: "P0", 40: "P0", 41: "P0", 42: "P0", 43: "P0", 44: "P0", 45: "P0", 46: "P0", 47: "P0", 48: "sfx", 49: "sfx", 50: "sfx", 51: "sfx", 52: "sfx", 53: "sfx", 54: "sfx", 55: "sfx", 56: "sfx", 57: "sfx", 58: "sfx", 59: "sfx", 60: "sfx", 61: "P124", 62: "sfx", 63: "sfx", 64: "sfx", 65: "sfx", 66: "sfx", 67: "sfx", 68: "piano", 69: "sfx", 70: "sfx", 71: "sfx", 72: "sfx", 73: "sfx", 74: "sfx", 75: "sfx", 76: "sfx", 77: "sfx", 78: "sfx", 79: "sfx", 80: "sfx", 81: "sfx", 82: "sfx", 83: "sfx", 84: "sfx", 85: "sfx", 86: "sfx", 87: "sfx", 88: "sfx", 89: "sfx", 90: "sfx", 91: "sfx", 92: "sfx", 93: "chromatic", 94: "sfx", 95: "sfx", 96: "P96", 97: "P97", 98: "P98", 99: "P99", 100: "P100", 101: "P101", 102: "P102", 103: "P103", 104: "P104", 105: "P105", 106: "P106", 107: "P107", 108: "P108", 109: "P109", 110: "P110", 111: "P111", 112: "P112", 113: "P113", 114: "P114", 115: "P115", 116: "P116", 117: "P117", 118: "P118", 119: "P119", 120: "P120", 121: "P121", 122: "P122", 123: "P123", 124: "P124", 125: "P125", 126: "P126", 127: "P127"},
}


ANIMA_EXPR_CATS = frozenset(
    {"strings", "ensemble", "brass", "wind", "pad", "lead", "fx"}
)
ANIMA_MOD_CATS = frozenset(
    {"strings", "ensemble", "pad", "wind", "brass", "lead"}
)



# SC-8850 map: GM PC (0-based) -> allowed Bank MSB (CC00) values including capital 0.
# File-specified non-zero CC0/CC32 always wins in Duality; this is Anima-only.
ANIMA_TONE_VARS = {
    0: (0, 8),
    1: (0, 8),
    2: (0, 8),
    3: (0, 8),
    4: (0, 8),
    5: (0, 8),
    6: (0, 8),
    7: (0, 8),
    8: (0, 8),
    9: (0, 8),
    10: (0, 8),
    11: (0, 8),
    12: (0, 8),
    13: (0, 8),
    14: (0, 8),
    15: (0, 8),
    16: (0, 8),
    17: (0, 8),
    18: (0, 8),
    19: (0, 8),
    20: (0, 8),
    21: (0, 8),
    22: (0, 8),
    23: (0, 8),
    24: (0, 8),
    25: (0, 8),
    26: (0, 8),
    27: (0, 1, 8),
    28: (0, 8),
    29: (0, 8),
    30: (0, 8),
    31: (0, 8),
    32: (0, 1, 8),
    33: (0, 8),
    34: (0, 8),
    35: (0, 8),
    36: (0, 8),
    37: (0, 8),
    38: (0, 8),
    39: (0, 8),
    40: (0, 8),
    41: (0, 8),
    42: (0, 8),
    43: (0, 8),
    44: (0, 8),
    45: (0, 8),
    46: (0, 8),
    47: (0, 8),
    48: (0, 8),
    49: (0, 8),
    50: (0, 8),
    51: (0, 8),
    52: (0, 8),
    53: (0, 8),
    54: (0, 8),
    55: (0, 8),
    56: (0, 8),
    57: (0, 8),
    58: (0, 8),
    59: (0, 8),
    60: (0, 8),
    61: (0, 8),
    62: (0, 8),
    63: (0, 8),
    64: (0, 8),
    65: (0, 8),
    66: (0, 8),
    67: (0, 8),
    68: (0, 8),
    69: (0, 8),
    70: (0, 8),
    71: (0, 8),
    72: (0, 8),
    73: (0, 8),
    74: (0, 8),
    75: (0, 8),
    76: (0, 8),
    77: (0, 8),
    78: (0, 8),
    79: (0, 8),
    80: (0, 8),
    81: (0, 8),
    82: (0, 8),
    83: (0, 8),
    84: (0, 8),
    85: (0, 8),
    86: (0, 8),
    87: (0, 8),
    88: (0, 8),
    89: (0, 8),
    90: (0, 8),
    91: (0, 8),
    92: (0, 8),
    93: (0, 8),
    94: (0, 8),
    95: (0, 8),
    104: (0, 8),
    105: (0, 8),
    106: (0, 8),
    107: (0, 8),
    108: (0, 8),
    109: (0, 8),
    110: (0, 8),
    111: (0, 8),
}
