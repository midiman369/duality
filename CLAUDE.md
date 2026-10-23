# Notes for Claude Code sessions

## Start here (every new session)

- **What this is**: Duality, the user's multi-device MIDI router (`duality.py` + `tables_*.py`). 1.0.0 is released on
  `main`; development continues on `dev` (now 1.0.007; the next build is 1.0.008). Songs are not in this repo (see "Songs" below).
- **Branch**: work on `dev` (`git checkout dev`). A cloud session may start on an auto-named `claude/...` branch:
  switch to `dev` and confirm with the user before the first push; never push to `main` (releases go by pull request).
- **What we are doing**: the "Next up" list below. When the user says "continue" or names something loosely ("the
  medleys", "the pickers"), match it to Next up; if it is still unclear, ask before doing anything.
- **Earlier conversations**: every past session's messages are in the duality-workdata clone,
  `memory/<session>/user-requests.md` and `conversation.md` (get the clone with `python3 tools/backup_workdata.py
  --clone`). Search them (e.g. `grep -n -i medley`) when the user refers to earlier work.
- **Keep the scratchpad lean**: the whole scratchpad is backed up to Gitea. Don't rebuild songs or copy test files or
  published pages into it just to check them; work on what the task needs.

## Next up (2026-10-18; keep this list current)

Done since the release (dev, 2026-10-18): 1.0.001 the Brass sfz `slow` trait; 1.0.002 the user's EFX picks for
strings (Reverb, Gate Reverb x1/2, 3D Delay x1/4) and reeds & pipes (Reverb, Gate Reverb, Space D / Stereo Delay /
Mod Delay x1/3); 1.0.003 the foley level (`--anima-foley`, a song's "duality: foley off / 25%" text event,
`parse_song_option`, `PlayerSong.options`, `_player_options`); 1.0.004 the family spread and the player's
look-ahead (Anima, see "Family spread" under the EFX rules); 1.0.005 lane seeds = the badge seed + 0101 per
port, locked or not (`_lane_seed`, `_lanes_seed_sync`; S is no longer a lane key); 1.0.006 song ports are those
with channel messages (`PlayerSong.port_moves`: a tempo / SysEx-only port plays with the first channel port; a
re-saved ONESTOP2 had every part on port F) and the panel's channel grid merges every lane
(`_make_status_panel`); 1.0.007 the at-note defer only when a gap is coming (`PlayerSong.gap_within`,
`_anima_gap_coming`, ANIMA_LOOKAHEAD_GAP 0.5 s). All three picker pages were rebuilt from the tables that day (they matched; `CHANGELOG.md`
"Unreleased" collects these for 1.1.0). After a picker change: pull its database, apply, bump, test, rebuild and
republish that page, send the zip.

1. **Songs: the other public-domain medleys** (the user, 2026-10-17: "take note of these learnings and work on the
   other medleys now"; Bald Mountain came first, then these): Jazz Age, Shanties & Folk, Bolero Ladder get the
   Halloween / Mars treatment. Details, sources and what needs the user's PDFs: duality-workdata `songs/NOTES.md`,
   "Next up". The last plan was Jazz Age next; ask which first.
2. **Halloween** (2026-10-18): the user's listening notes on the 4-port suite are done (prologue joins, Danse
   macabre, spiccato, no foley; duality-workdata `songs/NOTES.md`, "Halloween listening"); waits for the next notes.
3. **Duality, primary goal step 3**: multi-input (live sources on several ports), see "Primary goal" below.
4. Tabled ideas (below): only when the user picks one.

## Reference

- Develop on branch `dev`. After each change, send the user a zip of only the runtime files that changed
  in that version (e.g. `duality.py`, `tables_*.py`); leave out unchanged files, tests, tools and docs.
- Releases (1.0.0, 2026-10-18; the user's decision): `main` holds only what a user needs (`tools/make_release.py`
  RELEASE: duality.py, tables_*.py, voodoo_banks.py, requirements.txt, LICENSE, README.md, CHANGELOG.md, .gitignore,
  docs/images). Never merge dev into main or main into dev: `python3 tools/make_release.py <version> --push` builds
  `release/<version>` from origin/main in a worktree, then a pull request into main; the user merges it, then tag
  `v<version>` on main and attach the released songs (our originals only: onestop2, point_and_click_overture,
  adventure_game_night, the_hint_line, metal_gods; never public-domain or third-party ones unless the user says so).
  Cloud sessions cannot push tags or create releases (HTTP 403): send the user the release notes (the CHANGELOG
  entry + a song table) and the songs; they create the release on GitHub with a new tag on main.
  State (2026-10-18): 1.0.0 is published (release v1.0.0 on main aae9a4b, the five songs attached; no zip asset:
  GitHub's source archives hold the program). dev's history was rewritten that day (git filter-repo) to drop the
  song files, so every older dev commit id changed; the old history lives only in duality-workdata
  `songs/history/*.bundle` (see `songs/README.md`). Never push an old clone's dev: it would bring the songs back.
  Versions: dev builds after a release are <release>.001, .002 ... (1.0.001); the next release is 1.1.0. README.md
  and CHANGELOG.md are written for main's readers (no version tags in the README, no private pages or songs).
- Offline regression suite: `python tests/run_all.py` (fake MIDI ports + clock, no hardware).
- Test songs are **not** in the repo (copyright). A fresh clone only runs the three self-contained
  tests; the rest print SKIP. `tests/README.md` → "Where the songs came from" lists each file's
  original name and checksum: ask the user to upload the ones you need and put takes in
  `recordings/`, songs in `tests/midi/` (original names are fine; both are git-ignored).
- Duality writes `--log` to `logs/duality-<stamp>.log` (one per run, one per `--record` take with the
  take's stamp; C starts a new one) and `--record` takes to `recordings/` by default.
- Private backup of git-ignored work lives in the user's Gitea repo duality-workdata (never GitHub), kept current by
  `tools/backup_workdata.py` (2026-10-18): the Stop / SessionEnd hooks in `.claude/settings.json` run it detached in
  the background, at most every 30 min (BACKUP_INTERVAL); at each milestone also run it by hand
  (`python3 tools/backup_workdata.py`; `--dry-run` previews). Add / update only, per session: scratchpad, uploads, pasted
  images, the transcript (32 MiB gzipped pieces of whole lines: only new pieces upload), memory extracts
  (`tools/transcript_memory.py`: conversation, user requests, compaction summaries), plans, tasks; shared: tests/midi,
  recordings, logs. Layout in the backup's README. The clone also holds `songs/` (the song generators, edited and
  committed there by hand with their own messages; a backup run stages only its own folders, `OWNED`; before a
  hand commit there, wait for any running backup: `flock ~/.cache/duality-backup/lock true`). Needs GITEA_TOKEN and GITEA_BACKUP_URL (environment variables;
  cloud sessions only); it installs git-lfs, clones without LFS content beside the checkout, passes the token by a
  one-off credential helper and skips files that hold a credential; log ~/.cache/duality-backup/backup.log. Without
  the variables it does nothing: then send the user tarballs (each under 500 MiB) to push themselves.
- EFX palette picker (published page "Anima EFX Palettes"): rebuild with `tools/picker/build_picker.py`
  after palette changes; the user's picks live in its database (`palettes/<family>`: nums, step {type: n}).
- Both pickers use weight steps (0.19.037): +1 = x2, +2 = x3 ..., -1 = x1/2, -2 = x1/3 ...; a step is
  offered while that entry's share of its group stays within 1%..99%. In the tables a weight is 2 x the
  multiplier (EFX rows' 4th field, `ANIMA_TONE_PREFS` "w"); old 1/2/4 weights keep their seeded picks.
- Tone palette picker (published page "Anima Tone Palettes"): rebuild with `tools/picker/build_tone_picker.py`
  (names / one-shot flags / voices in `tools/picker/tone_info.json`). Picks live in its database
  (`tones/p001`..`p120`: per tone on, st (step), w, EFX level -2..+2, note). Apply with
  `tools/picker/apply_tone_picks.py <dir>` (generated block `ANIMA_TONE_PREFS` in `tables_8850.py`) and
  `tools/picker/apply_efx_picks.py <dir>` (rows of `tables_gs.ANIMA_EFX_GS`); the dir is an ArtifactData
  list with out_dir. EFX level moves the insert's wet/dry Balance (`40 03 12`, types in
  `ANIMA_EFX_BALANCE_TYPES`; driest part on a unit wins). Notes are read by Claude and turned into
  `tables_8850.ANIMA_TONE_TRAITS` (lfo / rotary / echo / interval / short / slow / low / sweep): propose new
  lines for new notes before adding them. A trait that trips steps down a tone set (`ANIMA_TONE_STEPDOWN`,
  e.g. 303SqDistBs3 -> 2 -> 1) instead of going to the capital; `ANIMA_TONE_SWEEP_SCALE` sets a milder sweep.
- CM-64 PCM picker (published page "CM-64 PCM Picks"): rebuild with `tools/picker/build_cm64_picker.py`
  (template `cm64_picker_template.html`). Picks live in its database (`cm64/g001`..`g128`: use la / pcm / layer, pcm
  tone 0-63, la and lv levels in %, note); apply with `tools/picker/apply_cm64_picks.py <dir>` (generated block
  `CM64_GM_PICKS` + `CM64_GM_NOTES` in `tables_cm64.py`). Duality 0.19.055 plays them under Voodoo: a pool of
  PCM parts on 2+ units; on one CM-64 live seats (0.19.056, default: channels move half at a PC by
  rewriting part receive channels) or `--cm64-seats fixed` (ch9, 11-15 with MT-TO-GM). The PCM half's pan is
  reversed like LA's: GM CC10 sent to a PCM part is 127 - value.
  0.19.061: PCM notes take the normal note path; `_send_routed` hands them to the part (`_cm64v_intercept`), so Anima and the
  display see them. Anima's GM-numbered sets use `_anima_gm_pc` (MT32_TO_GM / CM64_PCM_GM on native LA streams).
  CM sound effects under Voodoo (0.19.057, `tables_cm64.CM_VOODOO_SFX`): keys 82-108 factory, 76-81 moved to 24-29,
  rewritten after the kit on cm32 / cm64 outs, notes routed to CM units only.
- Songs (all song generation lives in the private duality-workdata repo, `songs/`, never on GitHub; 2026-10-18):
  generators, score modules, `pd_kit` / `score_kit` / `sc8850`, the OMR tools and every arranging / mixing /
  SC-8850 learning are there (`songs/README.md`: what each song is and how to build it; `songs/NOTES.md`: the
  notes that used to be here). Get the clone with `python3 tools/backup_workdata.py --clone` (beside this
  checkout); builds write to this checkout's `tests/midi/`. Read `songs/NOTES.md` before any song work.
- Milestones (standing rule): when a milestone step is done (a song delivered, a version shipped), prepare for
  compaction: put what the next session needs in this file (or the relevant README) and commit it, then say so.
- Tone candidates (0.19.036): every 8850-map variation; older-map (55 / 88 / 88Pro) and CM-64 tones unless their
  tone data (voices, waveforms, parameters) is an exact copy of an 8850 tone or of one already offered
  (by waveform alone was too strict: the 88Pro Piano 1 reuses samples yet is a different piano). The lists in
  `tables_8850.py` are generated from the ROM dump by `tools/gen_unique_tones.py <sc-8850.json>`
  (shingo45endo/tone-browser); rerun it rather than editing them.
- Anima GS EFX addresses and parameters come from the SC-8850 manual's Insertion Effect List
  (p.216-223) and MIDI Implementation (p.237); see comments in `tables_gs.py`.
- Fixed settings Anima writes with its own type live in `tables_gs.ANIMA_EFX_TYPE_SET` (0.19.043, by ear:
  GTR Multi 2 OD Sel = Dist, Overdrive Level 80 (0.19.047), GTR Multi 3 Level 127 plus a x1.2 CC7 lift on its players (0.19.046); its wah Peak is
  `ANIMA_EFX_WAH_PEAK`, 80). The OD1/OD2
  guitar split runs both sides as Distortion with OD1 Level 80. Harpsichord is `piano_acoustic`, not
  `keys_pluck`; a Jazz Gt. never gets a wah (`ANIMA_EFX_NO_WAH_PROGS`).

## Anima GS EFX rules (agreed; keep them)

1. No insert type change on a unit while any of its EFX players is sounding (dirt included).
2. Unpin and Part EFX Off are one action.
3. Channels with no family never plan.
4. An unheard program change does not evict a sounding family.
5. The setup burst (PC dump) is assigned once.
6. Never delay notes (reroute instead; no settle queue).
7. Insert type and Part EFX toggles change together.
8. No replan per note of a pinned channel.

Hero split (0.19.039): a featured line on a shared unit may take a spare unit with another type of its
family (`_anima_hero_split_tick`): only when every family is placed and no part makes harmony (seats come
first); type onto the empty unit, the hero moves in a breath; the hero unit yields to any family.
"Quiet" means the unit's EFX players only (Part EFX On there, their ghosts, queued strums), not dry parts.
Family priority lives in `tables_gs.ANIMA_EFX_PRIORITY` (a distorted guitar takes a unit from a pad).
The file's own insert always wins its home unit.
Family spread (1.0.004, `_anima_spread_tick`, after the hero split in `_check_anima_session_idle`): a family heard on
ANIMA_SPREAD_MIN (4) or more channels of one unit takes a spare unit of the same router / lane too (a second unit it
already holds, else an empty one typed with the family's insert while silent, else a unit another family left idle
ANIMA_SPREAD_IDLE_SEC); the right-hand half of its channels by pan (balanced by channels held) moves there, each in
a rest of its own (`_anima_ch_resting`, `_anima_spread_move`: Part On and pin there with Part Off on the old unit).
The spare is flagged `hero` + `spread`, so it yields like a hero unit and build_plan keeps its channels. Seat units
(harmony ghosts) are not taken. Found on the Halloween 4-port suite on six units (port A's second unit held only
the percussion kit through Bald Mountain).
Player look-ahead (1.0.004; live input unchanged): `PlayerSong.next_on` / `MidiPlayer.lookahead` / `_anima_next_note`
(a lane's `_anima_la`): an unplaced family is placed ANIMA_LOOKAHEAD_PREP (2 s) before its next note
(`_anima_lookahead_tick`); a type / owner change that `_anima_efx_place` would make right at a note is put off and
the part starts dry until its next gap (at most ANIMA_LOOKAHEAD_DEFER, 4 s; 1.0.007: only when the file shows a
gap of ANIMA_LOOKAHEAD_GAP within it, else it is placed at once); an owner that plays within
ANIMA_LOOKAHEAD_HOLD (3 s) is not stale; a channel moves only when its next note is ANIMA_LOOKAHEAD_MOVE (0.3 s) or
more away. On the 4-port suite (six units, seed DF14) Part EFX On writes landing within 100 ms of their channel's
next note went from 157 of 250 to 35 of 282 before the defer (the rest on the one-unit lanes C / D).

## Tabled — ideas for later (ask before starting)

- **EFX preset library**: named parameter sets per family + insert type (beyond the type's defaults).
- **Parameter randomisation**: seed-driven values inside a floor/ceiling per parameter.
- **More live parameter control**: the wah now follows the player (0.19.029), a file's set-and-left wah is played too (0.19.032, handed back on any later file EFX write), and rotary flips on held
  chords; next could be other knobs (flanger rate on held notes, drive on accents). Note: a Control
  Source ADDS to the stored value (Depth +100% ~ base + CC), and the LCD shows only the SysEx value.
- **Subtler orchestral inserts**: lower wet/dry Balance on strings / brass / pads, and bring Stereo Delay
  back to strings with low feedback. Confirmed from the Effect List (p.217): Balance is `40 03 12` on the
  chorus types (#16-20) and Stereo Flanger, 00 = D>0E, 40 = D=E, 7F = D0<E (LCD "D>nE" = effect at n% of
  dry, n = value x 1.54 rounded down, checked on SC-VA: 32 -> D>49E, 33 -> D>50E, 50 -> D>77E).
  Check each other type's page before writing it. The seat unit's Space D already uses it (D>50E).
- **Pitch shifter ↔ ghost harmony**: match the shifter's interval to the ghost harmony where the chord
  allows (today: key-safe doubler / octave / fifth only).
- **User notes (2026-10-01), GTR Multi 3**: (1) an "LP chorus" guitar clashes with the wah (check which
  insert/part that is before changing anything); (2) switch the wah itself (GTR Multi 3 Wah Sw `40 03 06`)
  off for chug-a-chug riffing and on for longer chord riffs, lead lines and solos. Test song:
  `tests/midi/dirty-women.mid` (Black Sabbath - Dirty Women; see tests/README.md).
  Per the user, once the insert is set the Wah Sw toggles On/Off with no hitching (no need to keep it off note onsets).
- **CM-64 Voodoo, next steps**: SN-U110 card sounds (PC 65-128; the user owns cards); a layer on one unit
  (today it plays PCM only). The user has a real CM-64, three MT-32s and the gearmulator CM-64.
- **Bulk-dump pacing for real hardware**: files that send a whole SC-8850 bulk dump at t=0 (e.g. Every
  Breath You Take) exceed the manual's 40 ms-per-packet rule; SC-VA does not care, a real unit may.
- **Organ CC7 lift vs file fade**: the organ volume lift can fight a file's own fade (parked).
- **Anima on XG outputs (before the Alchemy revival)**: give Anima's tone, EFX and articulation layers an
  XG target, the way GS / SC-8850 has one now. Four capability targets: (1) the baseline XG spec, (2)
  S-YXG50 / S-YXG100 (soft synths), (3) MU128, (4) MU2000. Per target, confirm from its own voice list and
  manual (don't trust memory): voice and drum-kit counts and bank layout (MSB 0 normal / 64 SFX / 126-127
  drums, LSB variations, per-model extras such as MU-basic / PLG banks), polyphony, and the effect blocks:
  the Variation effect (System or Insertion, per part), and the number of Insertion effects on MU128 /
  MU2000, their types and parameter addresses (the XG counterpart of the GS insert planner and its 8
  rules). Pickers like the GS ones would follow (XG tone palettes from each voice list; XG EFX palettes).
  `tables_xg.py` already has the XG effect type lists (MU128-based) used by Alchemy.
- **Anima with look-ahead in the file player** (the user, 2026-10-18; first steps DONE in 1.0.004, above: placing
  ahead, deferring at-note changes, no eviction of an owner about to play): the player knows what is coming, so it
  could place EFX type changes and Part EFX toggles cleanly (type a unit in a gap before its family's first note,
  never at the note; no ping-pong between families that take turns), and other Anima ideas could improve the same
  way. Duality as a live router stays the primary goal: anything built here must leave the live path as it is.
  Seen on Bald Mountain 4-port with Anima: port C retyped Reverb -> Enhancer at the brass layer's first note
  (20.98 s), after the strings had taken the brass's unit while it was unheard (3.73 s).
- **Drum EQ as an Anima family** (the user, 2026-10-18, tabled): a lowest-priority "boom" family (below fx) for the
  drum part + a timpani channel (GM 48): Stereo-EQ Low +10 dB, Hi 0, EFX send to reverb 127 (from the user's Movie
  Spectacular; `sc8850.drum_eq` has the addresses), only on a unit no other family wants, yielding like any owner;
  settings in tables_gs with an on/off switch. Today the drum channel has no family (rule 3), so it never plans.
- **Alchemy revival (GS<->XG)**: it broke because Duality could not set EFX properly back then; the insert
  work since 0.19 (per-unit placement, parameter addresses, Control Sources, Balance, reading the file's
  own EFX) removes that cause. Idea: on SC-8850 only, use the User Instrument banks (CC00 64/65) and user
  drum sets to hold the nearest GS tone reshaped toward the XG voice (filter / envelope; no new waveforms).
  Opt-in and limited to slots the user sets aside (they are persistent memory on a real unit); write in
  the setup burst with real-hardware pacing; check SC-VA / 88Emu50 support first. Needs the manual's User
  Instrument / User Drum MIDI Implementation pages.

## Primary goal (2026-10-17, user's decision): the player and more than 16 channels

In scope now and first in line: (1) a built-in MIDI file player in Duality (`--play` files / folders,
the user plays songs with Windows Media Player today, which sends SysEx fine but only one port);
DONE in 0.19.065: `PlayerSong` / `MidiPlayer` / `_NoInput` before `class Duality`, `_service()` is the shared
loop pass (live input + `_player_tick`), hotkeys Space / N / Z / T, `--play` / `--play-loop`, `--input` optional
with `--play`; port > 0 events are skipped with a note (`_player_send`) until multi-port lands; test
`tests/player_test.py` (self-contained);
(2) multi-port playback: each track's standard MIDI Port marker (FF 21, as in Roland's 32-channel
`05ORCHE.MID` demo) routes its events to their own units, a once-only request in the file asks for
"an open 8850" per port, a port with no unit that has the voices is dropped; test 2-4 ports;
DONE in 0.19.066: a multi-port song plays on *lanes* (`_lanes_start` / `_lanes_plan` / `_lane_make` /
`_lanes_stop`): one Duality instance per port on its own outs (`_LaneOut` views of the main router's
ports, so one send path / --record), built when the player's session starts and dropped when it ends;
the main router rests meanwhile and forgets its CC filter / tone caches / Anima session after. Requests:
"duality: 8850" text events (`parse_port_request`, `out_matches`); port A's system SysEx goes to every lane
(`player_system_sysex`). Tests: `tests/player_test.py` (synthetic 2- and 4-port songs) and
`tests/replay_multiport.py` (05ORCHE.MID, local only: Roland copyright);
(3) multi-input (live sources on several ports) after that; (4) the Halloween medley v3 written
for up to 4 ports, plus a 16-channel version for one-output players. One song can then drive
several kinds of synth at once (a port per device type).
DONE (4): the songs are in duality-workdata (`songs/NOTES.md`, "4-port songs").

## Out of scope unless the user asks

Seat units (0.19.024) only carry Anima's own harmony ghosts on a spare unit; generating new lines
there (players, motifs) is still out of scope.
Percussion / atonal mapping, SCPOP + Anima bypass, beat grid / motifs, extra orchestral players.
Keep seed performance, tone lock, ghosts, foley and the widened
family tables. Alchemy (GS↔XG rewrite) stays marked broken until the revival above is taken up. Anima is "for fun": a live stream player.
