"""Run every offline regression. Tests whose song is missing are skipped.

    python tests/run_all.py
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = [
    ("onestop_harness", "onestop_harness.py", {}),
    ("onestop_early", "onestop_early.py", {}),
    ("tempo", "tempo_test.py", {}),
    ("onestop 22:00", "onestop_replay.py", {}),
    ("onestop 22:16", "onestop_replay2.py", {}),
    ("onestop 22:29", "onestop_replay4.py", {}),
    ("bass sub", "replay_bass.py", {}),
    ("bulk dump", "replay_bulk_dump.py", {}),
    ("file EFX echo", "replay_file_efx_echo.py", {"GAME": "0", "PRE": "0"}),
    ("file EFX echo, game", "replay_file_efx_echo.py", {"GAME": "1", "PRE": "0"}),
    ("file EFX echo, after a song", "replay_file_efx_echo.py", {"GAME": "0", "PRE": "12"}),
    ("file EFX echo, game, after a song", "replay_file_efx_echo.py", {"GAME": "1", "PRE": "12"}),
    ("harmony, Death Gate 07", "replay_harmony.py", {"SONG": "07"}),
    ("harmony, Death Gate 03", "replay_harmony.py", {"SONG": "03"}),
    ("harmony, Death Gate 97", "replay_harmony.py", {"SONG": "97"}),
]
bad = 0
for name, script, env in RUNS:
    e = dict(os.environ, **env)
    r = subprocess.run([sys.executable, os.path.join(HERE, script)], env=e,
                       capture_output=True, text=True, timeout=1800)
    out = r.stdout.splitlines()
    if r.returncode == 77:
        status = "SKIP"
    elif r.returncode == 0 and "PASS" in out:
        status = "PASS"
    else:
        status = "FAIL"
        bad += 1
    print(f"{status:4s}  {name}")
    if status == "FAIL":
        tail = [l for l in out if l.startswith(("FAILS", "   ", "Traceback"))] or out[-8:] or r.stderr.splitlines()[-8:]
        for l in tail[:12]:
            print("      " + l)
sys.exit(1 if bad else 0)
