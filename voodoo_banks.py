"""MT-32 GM-style SysEx banks for Duality Voodoo.

Included banks
--------------
* **mtgm** – Roland MT-TO-GM (1993): MTGM.MID + MTR-STND / MTR-ORCH kits
* **kq6**  – Sierra King's Quest VI GM bank (KQ6.SYX / Quest Studios)
* **lsl3** – Sierra Leisure Suit Larry 3 custom bank
* **sq4**  – Sierra Space Quest IV custom bank
* **kq5**  – Sierra King's Quest V custom bank

Payloads are zlib-compressed, length-prefixed (uint16 BE) mido SysEx data[]
(no F0/F7). Checksums are those from the original files.
"""
from __future__ import annotations
import base64
import zlib

def _unpack(blob: bytes) -> list[bytes]:
    raw = zlib.decompress(blob)
    msgs: list[bytes] = []
    i = 0
    while i < len(raw):
        n = (raw[i] << 8) | raw[i + 1]
        i += 2
        msgs.append(bytes(raw[i : i + n]))
        i += n
    return msgs

_MTGM_B64 = (
    "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"
)

_MTR_STND_B64 = (
    "eNqVkLcOwkAQRG9lECALZFHQUfAH5JxMzjkHiWIl+At+nYehoqN4mrm59XnuJOg6saglztMEzC93"
    "/TCGEeShCE0NyBsycWGsIemiOQ1LT/3SQa9om6yPZtGWWjLAZ9Ch2tLQsKmrbXb4GmdOOKOqfnPB"
    "V8hXzK2Zn5LPYM7cgvWSfIPfwpn8QHZCj1D2Mtvs+T9dpQBJ5lPMFNUnJShrRNKs3/1T3/5JSJiL"
    "9xKW87mJ7d0gy9dVr3VIaCU3/IP955/EXyuNPtg="
)

_MTR_ORCH_B64 = (
    "eNqVkMcKwlAQRd8QQ5SgBBeu3Vtjr6AuFLH3FsHFLPwLf92TED/AxeHO3CmvSHLs5bKWeB/jmB9T"
    "dcwTZjCHNlRj7UBBHQnBkyIsNBVp5T9MyFldGaJLdpTVNgFxSV2zV0sOassKfw0b+rbkO/wj8Qke"
    "+Fe8O3qDXuS55qJpaXFGO7qjJT49HU1IF3qakRr5iJoP4/gdvgmin7C8PFmTTU+6GkwP0Drb+3gv"
    "4jf1z59MvodjPVg="
)

_KQ6_B64 = (
    "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"
)

def mtgm_sysex() -> list[bytes]:
    """Roland MT-TO-GM full dump (64 memory timbres + patch map + system)."""
    return _unpack(base64.b64decode(_MTGM_B64))

def mtr_stnd_sysex() -> list[bytes]:
    """GM Standard drum kit (rhythm section only) — MT-TO-GM companion."""
    return _unpack(base64.b64decode(_MTR_STND_B64))

def mtr_orch_sysex() -> list[bytes]:
    """GM Orchestra drum kit (rhythm section only) — MT-TO-GM companion."""
    return _unpack(base64.b64decode(_MTR_ORCH_B64))

def kq6_sysex() -> list[bytes]:
    """Sierra King's Quest VI GM bank (display + system + patches + rhythm + timbres)."""
    return _unpack(base64.b64decode(_KQ6_B64))

# GM channel-10 program numbers (0-based) that select Orchestra kit (MT-TO-GM only)
GM_ORCHESTRA_KIT_PC = frozenset({48})  # GM program 49

# Registry used by Duality Voodoo
# kits=True  → ch10 PC can swap Standard/Orchestra via MTR-* dumps
# kits=False → rhythm is baked into the bank; ch10 PC is passed through

_LSL3_B64 = (
    "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"
)

def lsl3_sysex() -> list[bytes]:
    """Sierra Leisure Suit Larry 3 custom MT-32 bank."""
    return _unpack(base64.b64decode(_LSL3_B64))

_SQ4_B64 = (
    "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"
)

def sq4_sysex() -> list[bytes]:
    """Sierra Space Quest IV custom MT-32 bank."""
    return _unpack(base64.b64decode(_SQ4_B64))

_KQ5_B64 = (
    "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"
    "FyyfeSc="
)

def kq5_sysex() -> list[bytes]:
    """Sierra King's Quest V custom MT-32 bank."""
    return _unpack(base64.b64decode(_KQ5_B64))

VOODOO_BANK_INFO = {
    "mtgm": {
        "label": "Roland MT-TO-GM",
        "loader": mtgm_sysex,
        "kits": True,
        "display": "MT-TO-GM Bank",
        "anima_map": "gm",
    },
    "kq6": {
        "label": "King's Quest VI (Sierra)",
        "loader": kq6_sysex,
        "kits": False,
        "display": "King's Quest 6",
        "anima_map": "gm",
    },
    "lsl3": {
        "label": "Leisure Suit Larry 3 (Sierra)",
        "loader": lsl3_sysex,
        "kits": False,
        "display": "Larry 3",
        "anima_map": "sfx",
    },
    "sq4": {
        "label": "Space Quest IV (Sierra)",
        "loader": sq4_sysex,
        "kits": False,
        "display": "Space Quest 4",
        "anima_map": "sfx",
    },
    "kq5": {
        "label": "King's Quest V (Sierra)",
        "loader": kq5_sysex,
        "kits": False,
        "display": "King's Quest 5",
        "anima_map": "sfx",
    },
}
VOODOO_BANK_NAMES = tuple(VOODOO_BANK_INFO.keys())
DEFAULT_VOODOO_BANK = "mtgm"


def get_bank_sysex(name: str) -> list[bytes]:
    """Return paced SysEx list for a registered bank name."""
    key = (name or DEFAULT_VOODOO_BANK).lower().strip()
    info = VOODOO_BANK_INFO.get(key)
    if info is None:
        raise KeyError(f"Unknown Voodoo bank {name!r}; choose from {VOODOO_BANK_NAMES}")
    return list(info["loader"]())


def bank_has_kits(name: str) -> bool:
    key = (name or DEFAULT_VOODOO_BANK).lower().strip()
    info = VOODOO_BANK_INFO.get(key)
    return bool(info and info.get("kits"))


def bank_label(name: str) -> str:
    key = (name or DEFAULT_VOODOO_BANK).lower().strip()
    info = VOODOO_BANK_INFO.get(key)
    return info["label"] if info else key


def bank_display(name: str) -> str:
    key = (name or DEFAULT_VOODOO_BANK).lower().strip()
    info = VOODOO_BANK_INFO.get(key)
    return info["display"] if info else key[:20]


def bank_anima_map(name: str) -> str:
    """How Anima should classify programs for this bank: gm | mt32 | sfx."""
    key = (name or DEFAULT_VOODOO_BANK).lower().strip()
    info = VOODOO_BANK_INFO.get(key) or {}
    return str(info.get("anima_map") or "gm")
