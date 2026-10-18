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
| `doom-game-223128.mid` | IN take, DOOM in DosBox with `--anima-game`, 2026-10-01 22:31:28 (a take: `recordings/` works too) | `replay_game_cue.py` |
| `replay_game_cue.py` | Game mode (DOOM take): after a new cue only its own channels plan, so E1M1's two guitars get a unit each (no OD1/OD2 while units are free) and no unit is a seat for a channel the cue does not use; the reroll places the next cue at once; no insert type write under a sounding player |

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
| `doom-game-223128.mid` | `IN-Duality-4-gs-20261001-223128.mid` (DOOM in DosBox, game mode: title, menu, E1M1, intermission, next cue) | `duality-20261001-223128.zip` | 24570 | `0fc14de4b7b5e584` |
| `dirty-women.mid` | `Black_Sabbath_-_Dirty_Women.mid` (riffing vs lead lines: wah switch on/off candidate) | sent on its own | 36565 | `0f8364c3277fd742` |
| `05orche.mid` | `05ORCHE.MID` (Roland's SC-8850 demo "Space Flight", 32 channels on ports A / B; multi-port test) | sent on its own (with its README.TXT) | 36611 | `ef4472b2c6ef1652` |
| `Bach - Toccata e Fuga in Re min BWV565 2K.mid` (keep this name) | the same, R. Diodati's SCPOP2000 organ performance of BWV 565 (1997); the Halloween suite (duality-workdata `songs/`) reads it for its finale | sent on its own | 52299 | `bad8421e6de7b203` |

The IN takes are Duality `--record` captures of the input stream (the
song as the player sent it), so they are the song too and stay local.

## Songs we wrote

`tests/onestop2.mid` is ONESTOP2 - A Brief History of Sound, one of our own songs (released with Duality 1.0),
kept here as test data: the doc images replay it. The song generators (ONESTOP2, the Voodoo demos, Metal Gods,
the Anima listening tests, the public-domain arrangements and score transcriptions) live in the user's private
duality-workdata repo, `songs/` (moved there 2026-10-18; never on GitHub). Their builds land in `tests/midi/`.

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
| `mallet_test.py` | Mallet sticking, no song: chords struck by hands, doubles / triplets / rolls only where the part leaves room, cancelled by an early note or a program change, rolls alternate hands, nothing left hanging; a delay insert on the marimba is timed from its note spacing (Tm Ctrl Delay lands on the next chord, Stereo Delay folds into its 500 ms); every key strictly balanced (never a second note-on while it sounds, no hanging notes), also with the run loop stalling so strokes and their notes come due together (0.19.062) |
| `file_wah_test.py` | A file's own wah (built-in, always runs): set and left → adopted (C.Src1 = CC16, Manual 30 below the file's, Peak untouched, rest in silence); a later file write hands it back at once; a Wah Man rewrite inside the setup re-centres the pedal on it; wah switch Off or a file-routed Control Source → left alone. With the songs: Phobos Anomaly adopted, Rose in the Gun Sight never |
| `tone_prefs_test.py` | Tone Palettes picks, no song: with no picks every program picks exactly as before; an unticked tone is never offered and a reserved one switched on is; a favoured tone is picked twice as often as a normal one; stepped weights (x3, x1/3) land on their ratio and the old 1/2/4 weights keep the original seeded roll |
| `hero_split_test.py` | Hero split, no song: a vibes tune sharing the chromatic unit with marimba chords moves to a spare unit with a different type, in a breath (no note within 100 ms of its Part EFX On, Part Off on the old unit at the same moment, no type write under a sounding player); no split when a harmony part wants the spares; a guitar arriving later takes the hero unit back and the vibes play on the family unit again |
| `tone_traits_test.py` | Tone Palettes EFX level and notes, no song: a -1 piano on Reverb gets Balance 38, unmarked parts write nothing; Perc.Organ 4 never gets a rotary or LFO insert, MandolinTrem no delay, MG 5th Bass no pitch shifter; no harmony or sub-octave on 5th Organ; Seq Bass held, Slow Tremolo played quick and Vcs&Cbs Pizz played high each go back to the capital once, at a rest; an unmarked tone stays; 303SqDistBs3 with notes shorter than its squeal steps down 42 -> 41 -> 40 at rests and stays on 40, while long low notes, short high notes and 303SqDistBs2 past its half-length squeal keep their tone |
| `cm64_test.py` | CM-64 outs, no song: `cm64` / `cm-64` tags show as CM-64; an MT-32 stream spreads ch2-10 over two MT-32s and the CM-64, ch11-16 go to the CM-64 only; on a CM-64 the LA half (--poly) and the PCM half (31 partials) count and steal apart, so a full PCM half never takes a quieter LA note; 15 notes of a 2-partial A.PIANO 1 fill the PCM half and a part counts its power-on patch until a program change; a CM-32L-only out gets MT-32 streams under Crucible; X sends it and the CM-64 the MT-32 reset; Voodoo sets the CM-64's PCM part channels OFF and back to ch11-16 on exit; PCM-half pan is not squeezed onto the LA table |
| `cm64_voodoo_test.py` | CM-64 PCM half under Voodoo, no song: pool on three CM-64s (reserve, receive channels clear of each unit's LA channels, a piano claims a part on its LA owner's unit and never plays on LA, CC10 as is, a lead stays on LA, a held note's off reaches its part after a PC to LA, 16 two-partial notes steal one, a layer at LA 50% / PCM 80% plays both halves and restores LA CC7 after), one MT-32 + one CM-64 (six parts; a seventh channel waits on LA until a part's owner rests 10 s), exit silences and restores, one CM-64 fixed seats on ch9 and 11-15 with the nearest PCM tone; one CM-64 live seats (a PC burst moves channels to the half they want, freed parts pass on, a held note ends before its channel changes half); GM pan reversed on PCM parts; CM sound effects written after the kit on CM units only, routed to them, rewritten after a kit switch; a GM / GM2 System On keeps Voodoo loaded, a GS reset still leaves it; Voodoo loads a drum kit only when the kit changes (ONESTOP2's eight ch10 PCs: 3 loads) |
| `anima_la_test.py` | Anima on LA outs, no song: a CM-64 PCM piano under Voodoo counts in the display (active notes, the unit's voices) and its quick repeats reach the part humanized; Anima's CC1 / CC11 swell on held PCM strings reaches the part's channel; a PCM nylon chord is strummed; a seat's notes count too; the panel shows [Voodoo] [CM-64 LA+PCM] with PCM parts and [MT-32] without; on a native MT-32 stream organs (PC 9-16) are not mallets while Marimba and Harp unroll; a native CM-64 PCM part on ch11 with PC 24 is a bass (FINGERED 1), the LA part with PC 24 stays a celesta; on two SC-8850s + a CM-64, Voodoo and a native MT-32 stream plan nothing on the idle GS units (no inserts, seats, GS SysEx or EFX messages) while a GS stream still gets its inserts; no harmony ghosts on native LA music (two MT-32s, one CM-64) |
| `tempo_test.py` | Beat tracker: exact on MIDI clock, musical relative on note onsets |

Timing check: a note within 100 ms of its unit's insert type change or its
Part EFX On is a "hitch". Foley (8850 SFX programs 121/122) is exempt; it
joins its host's insert on purpose.

## Doc images

`render_status.py`, `render_crucible.py` and `render_tables.py` regenerate
`docs/images/` in a Windows Terminal frame (`wt_svg.py`). The panels and the
Crucible stills replay ONESTOP2 (`tests/onestop2.mid`, our own song, so no
copyrighted song is needed): the hero at the screaming solo and the panel in the
analog synths (seed FC6C, four GS units, an XG and an MT-32 out); the Crucible
stills at the busiest moment of the big-band shout chorus, plus
`crucible-demo.gif` from them. `svgshot.py` turns an SVG into a PNG; the GIF
step needs Playwright + Chromium and Pillow.

```bash
python tests/render_status.py 470.0 docs/images/status-hero.svg 320.0 docs/images/status-panel.svg
python tests/render_crucible.py
python tests/render_tables.py
```
