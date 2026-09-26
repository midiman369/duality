"""Shared paths for the offline replay tests.

Songs are NOT in the repo. A test looks for its file, under the test name
or the original name, in:
  1. $DUALITY_TEST_MIDI (if set)
  2. tests/midi/          (source songs)
  3. recordings/          (Duality --record takes; git ignores it)
A test whose file is missing is skipped by run_all.py (exit 77).
"""
import os
import sys

TESTS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(TESTS)
MIDI_DIR = os.environ.get("DUALITY_TEST_MIDI", os.path.join(TESTS, "midi"))
IMAGES = os.path.join(REPO, "docs", "images")
SEARCH = [d for d in (os.environ.get("DUALITY_TEST_MIDI"), os.path.join(TESTS, "midi"),
                      os.path.join(REPO, "recordings")) if d]

# Test name -> original file name (see tests/README.md for checksums).
ORIGINAL = {
    "onestop-in-220022.mid": "IN-Duality-4-gs-20260924-220022.mid",
    "onestop-in-221619.mid": "IN-Duality-4-gs-20260924-221619.mid",
    "onestop-in-222922.mid": "IN-Duality-4-gs-20260924-222922.mid",
    "bass-in-000745.mid": "IN-Duality-4-gs-20260925-000745.mid",
    "every-breath-8850.mid": "Every_Breath_You_Take_8850.mid",
    "d_e1m1.mid": "D_E1M1.mid",
}

if REPO not in sys.path:
    sys.path.insert(0, REPO)
if TESTS not in sys.path:
    sys.path.insert(0, TESTS)


def midi(name: str) -> str:
    """Path of a test song; exit 77 (skip) if it is not there."""
    for folder in SEARCH:
        for candidate in (name, ORIGINAL.get(name)):
            if candidate:
                path = os.path.join(folder, candidate)
                if os.path.exists(path):
                    return path
    alt = f" or {ORIGINAL[name]}" if name in ORIGINAL else ""
    print(f"SKIP: {name}{alt} not found in {', '.join(SEARCH)} (see tests/README.md)")
    sys.exit(77)
