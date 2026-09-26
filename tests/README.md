# Offline tests

These scripts replay MIDI through Duality with fake MIDI ports and a fake
clock, then check what each output unit received. No hardware, no audio.

**Songs are not in the repo.** Put your own copies in `tests/midi/` (or set
`DUALITY_TEST_MIDI` to another folder). Git ignores `.mid` files there. A
test whose file is missing prints `SKIP`.

```bash
python tests/run_all.py
```

## Files expected in `tests/midi/`

| Name | What it is | Used by |
|------|------------|---------|
| `onestop-in-220022.mid` | Duality `--record` IN take of ONESTOP, 2026-09-24 22:00:22 | `onestop_replay.py` |
| `onestop-in-221619.mid` | IN take, 22:16:19 | `onestop_replay2.py` |
| `onestop-in-222922.mid` | IN take, 22:29:22 | `onestop_replay4.py`, `render_status.py`, `render_crucible.py` |
| `bass-in-000745.mid` | IN take of the bass sub-octave test, 2026-09-25 00:07:45 | `replay_bass.py` |
| `every-breath-8850.mid` | Every Breath You Take (SC-8850 bulk-dump setup) | `replay_bulk_dump.py` |
| `d_e1m1.mid` | DOOM E1M1 (file OD1/OD2 on parts 1+2) | `replay_file_efx_echo.py` |

## Tests

| Script | Checks |
|--------|--------|
| `onestop_harness.py`, `onestop_early.py` | Built-in ONESTOP-shaped timeline (no file): setup burst placed once, no insert retype under sounding EFX players, no Part Off under a pinned player |
| `onestop_replay*.py` | Same rules on real ONESTOP takes; `onestop_replay4.py` also checks CC1 rest, harmony height and delay types |
| `replay_bass.py` | Bass sub-octave never replaces the file's bass tone |
| `replay_bulk_dump.py` | A bulk-dump file keeps its own insert (P1 never retyped, ch7 on it) |
| `replay_file_efx_echo.py` | File Part EFX On is not swallowed as Anima's own echo; `GAME=0/1`, `PRE=0/12` (another song first) |
| `tempo_test.py` | Beat tracker: exact on MIDI clock, musical relative on note onsets |

Timing check: a note within 100 ms of its unit's insert type change or its
Part EFX On is a "hitch". Foley (8850 SFX programs 121/122) is exempt; it
joins its host's insert on purpose.

## Doc images

`render_status.py`, `render_crucible.py` and `render_tables.py` regenerate
`docs/images/` in a Windows Terminal frame (`wt_svg.py`). `svgshot.py`
turns an SVG into a PNG (needs Playwright + Chromium).

```bash
python tests/render_status.py 196.5 docs/images/status-hero.svg 38.0 docs/images/status-panel.svg
python tests/render_crucible.py
python tests/render_tables.py
```
