# Offline tests

These scripts replay MIDI through Duality with fake MIDI ports and a fake
clock, then check what each output unit received. No hardware, no audio.

**Songs are not in the repo.** Each test finds its file under either its
test name or its original name, in `tests/midi/` (source songs) or
`recordings/` (Duality `--record` takes), or in `DUALITY_TEST_MIDI` if set.
Git ignores `.mid` in `tests/midi/` and all of `recordings/` and `logs/`.
A test whose file is missing prints `SKIP`.

From the flat test-data zip: the two songs → `tests/midi/`, the `IN-…` /
`OUT-…` takes → `recordings/`, the `duality-….log` files → `logs/`.

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
| `death-gate-03.mid`, `-07`, `-97` | Death Gate (XMI2MID; a stray byte after end-of-track, `common.load` copes) | `replay_harmony.py` |

## Where the songs came from

For a future session: ask the user for these by their original names and put
them in `recordings/` (takes) or `tests/midi/` (songs); no renaming needed.
The checksum (first 16 hex of SHA-256) confirms it is the same file.

| Test name | Original file (as sent) | Arrived in | Bytes | SHA-256 (16) |
|-----------|-------------------------|------------|-------|--------------|
| `onestop-in-220022.mid` | `IN-Duality-4-gs-20260924-220022.mid` | sent on its own | 28463 | `d5a61021374b87c4` |
| `onestop-in-221619.mid` | `IN-Duality-4-gs-20260924-221619.mid` | `duality-logrec.zip` | 46177 | `478585ce0aa570d2` |
| `onestop-in-222922.mid` | `IN-Duality-4-gs-20260924-222922.mid` | `latestlogrec.zip` | 46176 | `ac5880e0afdd7c9e` |
| `bass-in-000745.mid` | `IN-Duality-4-gs-20260925-000745.mid` | `OUT-SCVA2-8-gm2gs8850-20260925-000745.zip` | 867 | `9112e1401c63a525` |
| `every-breath-8850.mid` | `Every_Breath_You_Take_8850.mid` | sent on its own | 47765 | `97b45e8eadd03e05` |
| `d_e1m1.mid` | `D_E1M1.mid` | sent on its own | 18772 | `68b33cb4f045a6c8` |
| `death-gate-03.mid` | `03_-_Death_Gate.MID` | sent on its own | 10979 | `ea51ce60bb29345b` |
| `death-gate-07.mid` | `07_-_Death_Gate.MID` | sent on its own (plus take `duality-20260926-105647.zip`) | 16475 | `273e78ce59e18479` |
| `death-gate-97.mid` | `97_-_Death_Gate.MID` | sent on its own | 29260 | `52c4adef9c67f8a7` |
| `death-gate-09.mid` | `09_-_Death_Gate.MID` (xylophone on ch2; for listening to mallet sticking) | sent on its own | 12943 | `c526c54a47b9fd14` |

The IN takes are Duality `--record` captures of the input stream (the
song as the player sent it), so they are the song too and stay local.

## Tests

| Script | Checks |
|--------|--------|
| `onestop_harness.py`, `onestop_early.py` | Built-in ONESTOP-shaped timeline (no file): setup burst placed once, no insert retype under sounding EFX players, no Part Off under a pinned player |
| `onestop_replay*.py` | Same rules on real ONESTOP takes; `onestop_replay4.py` also checks CC1 rest, harmony height and delay types |
| `replay_bass.py` | Bass sub-octave never replaces the file's bass tone |
| `replay_bulk_dump.py` | A bulk-dump file keeps its own insert (P1 never retyped, ch7 on it) |
| `replay_file_efx_echo.py` | File Part EFX On is not swallowed as Anima's own echo; `GAME=0/1`, `PRE=0/12` (another song first) |
| `replay_harmony.py` | Harmony balance (`SONG=03/07/97`): ghost and hero velocity scales, tonal intervals (no 2nd/tritone/7th against the hero, no semitone rub with a held note), no upper ghost left over a line that starts above it, harmony count kept; 97 also checks the ch3 string solo (fast line) and the ch4 Metal Pad tune at 2:50 (slow line) are spotlit |
| `mallet_test.py` | Mallet sticking, no song: chords struck by hands, doubles / triplets / rolls only where the part leaves room, cancelled by an early note or a program change, rolls alternate hands, nothing left hanging |
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
