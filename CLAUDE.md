# Notes for Claude Code sessions

- Develop on branch `dev`. After each change, send the user a zip of only the runtime files that changed
  in that version (e.g. `duality.py`, `tables_*.py`); leave out unchanged files, tests, tools and docs.
- Offline regression suite: `python tests/run_all.py` (fake MIDI ports + clock, no hardware).
- Test songs are **not** in the repo (copyright). A fresh clone only runs the three self-contained
  tests; the rest print SKIP. `tests/README.md` → "Where the songs came from" lists each file's
  original name and checksum: ask the user to upload the ones you need and put takes in
  `recordings/`, songs in `tests/midi/` (original names are fine; both are git-ignored).
- Duality writes `--log` to `logs/duality-<stamp>.log` (one per run, one per `--record` take with the
  take's stamp; C starts a new one) and `--record` takes to `recordings/` by default.
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
  rewritten after the kit on cm32 / cm64 outs, notes routed to CM units only. Demo songs: `tests/make_voodoo_demo.py`, `make_voodoo_demo2.py`, `make_voodoo_demo3.py`;
  public-domain demos `tests/make_pd_*.py` (helpers `tests/pd_kit.py`; tunes from memory, docstrings say which
  are quoted; our own arrangements, never a modern arrangement's harmony / riffs). Mars is the exception:
  a full transcription of Holst's score (`tests/mars_score.py`, from the IMSLP scan the user supplied).
- Score transcriptions (Mars, 0.19.064 era): read from the user's IMSLP PDF with `tools/omr/` (README there:
  setup, per-page workflow, transposition list); scans and work caches stay in a scratch folder, never in the
  repo. IMSLP downloads are gated by JavaScript: give the user the work-page links and let them upload the PDF
  (don't circumvent the gate). Mars: data `tests/mars_score.py`, generator `tests/make_pd_mars.py` (16 GM
  channels, one family each, ch10 Orchestra kit: concert keys 36/38/57/59, its timpani keys 41-53 unused).
- Halloween suite v2 (delivered 2026-10-17, 38:31): `tests/make_pd_halloween.py` plays complete pieces from
  scores, back to back, each a data module rendered by `tests/score_kit.py`: `hw_dies_irae.py` (LU 1810-1813; the
  prologue's setting lives in the generator), `hw_mountain_king.py`, `hw_danse_macabre.py`, `hw_bald_mountain.py`
  (1867, 557 bars; SPEED scales its tempo map; ppp bass-drum roll under its general pauses), then `bach_bwv565.py`:
  Diodati's SCPOP2000 MIDI (user's upload, local only in `tests/midi/` as "Bach - Toccata e Fuga in Re min BWV565
  2K.mid", a third-party performance: never in the repo; without it the suite skips Bach) for notes and timing,
  our organ registration (not his SCPOP SysEx), the fugue handed from the organ to the orchestra by voice roles
  (landmarks in his ticks at the top of the module), the organ back for the Molto adagio. Scans and OMR caches
  stay in the scratchpad (`hw/src`, `hw/bm` etc.; `two.sh`, `crop.sh` page viewers). The old medley is in git history.
  Every build also writes each piece alone (`halloween_<n>_<piece>[_4port].mid`, user's request 2026-10-17), cut
  from the suite's own events by `pd_kit.finish_parts` (never re-rendered: the shared RNG would change the notes);
  a new piece needs an entry in `build()`'s `ends` and in `PIECE_TITLES`.
- Line balance (2026-10-17; the user: Mars's little side-melody brass a little too quiet, the Halloween pieces
  less so, the prologue harp a bit quiet): `score_kit.balance(rows, progs, pcs, label)` runs in `score_kit.render`
  and both Mars renders before the per-channel merge (rows carry a tag: part, start beat, bar, articulations).
  It finds covered melodic phrases (rules in its header comment) and lifts each by up to `LINE_MAX_DB` 3 dB of
  velocity (`LINE_TARGET` -4 dB margin, `LINE_K` 0.8; `PROG_DB` is a rough per-program loudness, by guess, not
  measured). Tune there from the user's ears; `K.DEBUG = []` before a build, then `K.DEBUG` / `K.LOG`, show each
  phrase's verdict and lift. The Bach (role-based, not score_kit) and the prologue (its own code; harp CC7 100,
  arpeggios at the stanza level -2) are not balanced by it.
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
DONE (4): `make_pd_halloween.py` and `make_pd_mars.py` each write the 16-channel file (the notes as before)
and a `*_4port.mid`. Tooling: pd_kit channels 16-63 are ports B-D (`_out`, `emit`, `is_drums`; `finish()` writes a
port's tracks with FF 21 and a "duality: 8850" text, checks over every port); score_kit `Seat` (desks for chord
notes top-down, pizz / tremolo channels, layers); layouts `MK4_CH` / `DM4_CH` / `BM4_CH` / `PROLOGUE4` / `BACH4`
(module globals swapped by `layout4()`; the prologue and Bach read optional channels ORG4 / PED16 / CHOIR_SATB /
ORG_G4 / CB_CH / STRING_LAYERS ...) and Mars `SEATS4` / `render4`. Halloween: ports A+B hold the whole suite, C/D
add layers (2 units play it all); Mars: A-C hold the score, D the layers (3 units).

## Out of scope unless the user asks

Seat units (0.19.024) only carry Anima's own harmony ghosts on a spare unit; generating new lines
there (players, motifs) is still out of scope.
Percussion / atonal mapping, SCPOP + Anima bypass, beat grid / motifs, extra orchestral players.
Keep seed performance, tone lock, ghosts, foley and the widened
family tables. Alchemy (GS↔XG rewrite) stays marked broken until the revival above is taken up. Anima is "for fun": a live stream player.
