"""MT-32 GM-style SysEx banks for Duality Voodoo.

Included banks
--------------
* **mtgm** – Roland MT-TO-GM (1993): MTGM.MID + MTR-STND / MTR-ORCH kits
* **kq6**  – Sierra King's Quest VI GM bank (KQ6.SYX / Quest Studios)

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
VOODOO_BANK_INFO = {
    "mtgm": {
        "label": "Roland MT-TO-GM",
        "loader": mtgm_sysex,
        "kits": True,
        "display": "MT-TO-GM Bank",
    },
    "kq6": {
        "label": "King's Quest VI (Sierra)",
        "loader": kq6_sysex,
        "kits": False,
        "display": "King's Quest 6",
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

