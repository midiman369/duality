"""Roland MT-TO-GM (1993) SysEx banks for Duality Voodoo.

Source: official Roland MT-TO-GM package (MTGM.MID, MTR-STND.MID, MTR-ORCH.MID).
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

def mtgm_sysex() -> list[bytes]:
    """Full GM mode dump (64 memory timbres + patch map + system)."""
    return _unpack(base64.b64decode(_MTGM_B64))

def mtr_stnd_sysex() -> list[bytes]:
    """GM Standard drum kit (rhythm section only)."""
    return _unpack(base64.b64decode(_MTR_STND_B64))

def mtr_orch_sysex() -> list[bytes]:
    """GM Orchestra drum kit (rhythm section only)."""
    return _unpack(base64.b64decode(_MTR_ORCH_B64))

# GM channel-10 program numbers (0-based) that select Orchestra kit
GM_ORCHESTRA_KIT_PC = frozenset({48})  # GM program 49

