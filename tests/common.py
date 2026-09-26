"""Shared paths for the offline replay tests.

Songs are NOT in the repo. Put your own recordings / files in tests/midi/
(or point DUALITY_TEST_MIDI at another folder) under the names in
tests/README.md. A test whose file is missing is skipped by run_all.py.
"""
import os
import sys

TESTS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(TESTS)
MIDI_DIR = os.environ.get("DUALITY_TEST_MIDI", os.path.join(TESTS, "midi"))
IMAGES = os.path.join(REPO, "docs", "images")

if REPO not in sys.path:
    sys.path.insert(0, REPO)
if TESTS not in sys.path:
    sys.path.insert(0, TESTS)


def midi(name: str) -> str:
    """Path of a test song; exit 77 (skip) if it is not there."""
    path = os.path.join(MIDI_DIR, name)
    if not os.path.exists(path):
        print(f"SKIP: {name} not found in {MIDI_DIR} (see tests/README.md)")
        sys.exit(77)
    return path
