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
| `grabbag.mid` | `01_GRABBAG.MID` (non-stop distorted rhythm guitars; seed 50FC deals both to GTR Multi 3) | sent on its own | 14287 | `928e50554b7e6682` |
| `death-gate-09.mid` | `09_-_Death_Gate.MID` (xylophone on ch2; for listening to mallet sticking) | sent on its own | 12943 | `c526c54a47b9fd14` |
| `lotr-8850.mid` | `LotR_8850.mid` (Lord of the Rings medley, 16 orchestral parts, 3 families) | sent on its own | 115132 | `9572b49f62912118` |
| `phobos-8850.mid` | `18_-_phobos_anomaly_8850.mid` (bulk dump sets GTR Multi 3, never touched again) | sent on its own | 65567 | `ac68f826d380875c` |
| `rose-gun-sight.mid` | `rose_in_the_gun_sight.mid` (performs its own wah: live Wah Man writes from 6:43) | sent on its own | 205850 | `c5d45c95b713db4b` |

The IN takes are Duality `--record` captures of the input stream (the
song as the player sent it), so they are the song too and stay local.

## Generated test song (no copyright, rebuild anywhere)

`python tests/make_funk_test.py` writes `tests/midi/anima_funk_test.mid`: an original E dorian funk
groove (100 BPM, ~85 s) for hearing Anima's EFX control. Drawbar organ with long held chords (rotary
flips) and short skanks (no flip), 16th-note muted guitar and off-beat clean guitar (wah candidates),
Rhodes comping and an alto sax melody in the bridge, a breakdown with the muted guitar alone.
Seeds that deal both a rotary organ and a wah guitar with the 0.19.028 palettes: `359A` (both
guitars on wah types, OD/Rotary), `5419` (Auto Wah, Rotary Multi on Control 2), `286A`, `0772`.

`python tests/make_metal_test.py` writes `tests/midi/anima_metal_test.mid`: an original heavy
metal piece (~106 s) for distorted-guitar EFX. Doom intro at 72 BPM (tritone riff), Priest-style
gallop and twin harmony leads at 168 BPM, a 16-bar solo (runs, two-handed tapping, whammy vibrato,
two dive bombs; bend range one octave), riff reprise and a doom outro with a final dive. Rhythm
guitars hard left/right, lead centre so it can get a GTR Multi. Seeds that put the lead on
GTR Multi 3 (wah on Control 1) with the 0.19.028 palettes: `08BA`, `0BC2`, `153B`, `2E9E`,
`31A6`, `0249`, `1233`, `1BAC` (about 8% of seeds).

`python tests/make_island_test.py` writes `tests/midi/anima_island_test.mid`: an original calypso piece
(108 BPM, ~88 s) for hearing mallet sticking. Steel drums lead with chord hits in the intro, marimba
ostinato and off-beat chords, a vibraphone melody in a minor cove section with xylophone answers, a
xylophone break (runs, then held notes), glockenspiel sparkles, tubular bells at each section and a
dulcimer harmony in the last chorus, over calypso bass, nylon skank and Latin percussion. Every mallet
program is present; steel drums join the chromatic family (0.19.038), so they share a unit with the
marimba, vibes, xylophone, glockenspiel and bells. Seeds that put that unit on a delay timed to the
mallets' spacing, with the 0.19.037 palettes: `3F87` (Stereo Delay, dulcimer Cho→Delay), `08CA`
(Tm Ctrl Delay), `4395` (3D Delay, dulcimer Stereo Delay), `06C3` (Cho→Delay on both).

`python tests/make_onestop2.py` writes `tests/midi/onestop2.mid`, "ONESTOP2 - A Brief History of Sound"
(8:37): medieval (with a bagpipe reprise), baroque to classical, an organ-led cathedral crescendo, big
band, boogie-woogie into Chuck Berry-style rock'n'roll on an overdrive guitar, a proto-synth machine
(synth brass, Fantasia, Bass & Lead) interleaved into analog synths, prog / hard rock (two rotary organ
crescendos, 7/8, organ vs Moog), then a Dio-style epic, a power groove, a screaming solo (long bent
notes over ringing chords), a NWOBHM gallop and a Priest-style anthem ending with the organ and choir.
Plays complete on one SC-8850 (GM capitals, GS drum sets, no file EFX); built for Duality on six GS
units. Every part is written in scale degrees of its section's key, and the build fails on a note
outside the section's allowed pitch classes, on a silence over 1.5 s outside the one intended rest, or
on a program change under a held note. Offline with seeds 0436, 1A2B, 7A18 (and 0436 in game mode): no
type change under a sounding player, nothing hanging, about 99.6% of what Duality sends inside the
file's local key (the rest are chords held longer than the 2 s check window). Seeds `1332`, `6030` and
`EE63` put the solo guitar (ch1) on GTR Multi 3 from the Dio section to the gallop (3 of 96 scanned).

## Tests

| Script | Checks |
|--------|--------|
| `onestop_harness.py`, `onestop_early.py` | Built-in ONESTOP-shaped timeline (no file): setup burst placed once, no insert retype under sounding EFX players, no Part Off under a pinned player |
| `onestop_replay*.py` | Same rules on real ONESTOP takes; `onestop_replay4.py` also checks CC1 rest, harmony height and delay types |
| `replay_bass.py` | Bass sub-octave never replaces the file's bass tone |
| `replay_bulk_dump.py` | A bulk-dump file keeps its own insert (P1 never retyped, ch7 on it) |
| `replay_file_efx_echo.py` | File Part EFX On is not swallowed as Anima's own echo; `GAME=0/1`, `PRE=0/12` (another song first) |
| `replay_harmony.py` | Harmony balance (`SONG=03/07/97`): ghost and hero velocity scales, tonal intervals (no 2nd/tritone/7th against the hero, no semitone rub with a held note), no upper ghost left over a line that starts above it, harmony count kept; 97 also checks the ch3 string solo (fast line) and the ch4 Metal Pad tune at 2:50 (slow line) are spotlit |
| `cc16_test.py` | EFX Control via CC16 per unit, no song: Control Source/Depth routing per the Effect List, rotary speed flips on a held organ chord and back, wah follows the playing (low Manual base, Peak, held notes open wider than fast notes, heel after the part stops), a power-chord part on GTR Multi 3 gets the rhythm Peak and no screamer, one channel switching chords → lead → chords opens up within 0.6 s and drops back only after a slower glide, no CC16 to other units (even with a seat unit written last) |
| `seat_test.py` | Seat units: harmony on the spare unit with mirrored pan (built-in tune, always runs), file pan moves mirrored, panic restores pans, the seat insert is set and a guitar arriving mid-song takes the unit over without a type write under sounding harmony; with `LotR_8850.mid`, five units share families over two spares |
| `mallet_test.py` | Mallet sticking, no song: chords struck by hands, doubles / triplets / rolls only where the part leaves room, cancelled by an early note or a program change, rolls alternate hands, nothing left hanging; a delay insert on the marimba is timed from its note spacing (Tm Ctrl Delay lands on the next chord, Stereo Delay folds into its 500 ms) |
| `file_wah_test.py` | A file's own wah (built-in, always runs): set and left → adopted (C.Src1 = CC16, Manual 30 below the file's, Peak untouched, rest in silence); a later file write hands it back at once; a Wah Man rewrite inside the setup re-centres the pedal on it; wah switch Off or a file-routed Control Source → left alone. With the songs: Phobos Anomaly adopted, Rose in the Gun Sight never |
| `tone_prefs_test.py` | Tone Palettes picks, no song: with no picks every program picks exactly as before; an unticked tone is never offered and a reserved one switched on is; a favoured tone is picked twice as often as a normal one; stepped weights (x3, x1/3) land on their ratio and the old 1/2/4 weights keep the original seeded roll |
| `hero_split_test.py` | Hero split, no song: a vibes tune sharing the chromatic unit with marimba chords moves to a spare unit with a different type, in a breath (no note within 100 ms of its Part EFX On, Part Off on the old unit at the same moment, no type write under a sounding player); no split when a harmony part wants the spares; a guitar arriving later takes the hero unit back and the vibes play on the family unit again |
| `tone_traits_test.py` | Tone Palettes EFX level and notes, no song: a -1 piano on Reverb gets Balance 38, unmarked parts write nothing; Perc.Organ 4 never gets a rotary or LFO insert, MandolinTrem no delay, MG 5th Bass no pitch shifter; no harmony or sub-octave on 5th Organ; Seq Bass held, Slow Tremolo played quick and Vcs&Cbs Pizz played high each go back to the capital once, at a rest; an unmarked tone stays |
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
