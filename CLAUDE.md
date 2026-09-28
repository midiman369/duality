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
  `tables_8850.ANIMA_TONE_TRAITS` (lfo / rotary / echo / interval / short / slow / low): propose new
  lines for new notes before adding them.
- Tone candidates (0.19.036): every 8850-map variation; older-map (55 / 88 / 88Pro) and CM-64 tones unless their
  tone data (voices, waveforms, parameters) is an exact copy of an 8850 tone or of one already offered
  (by waveform alone was too strict: the 88Pro Piano 1 reuses samples yet is a different piano). The lists in
  `tables_8850.py` are generated from the ROM dump by `tools/gen_unique_tones.py <sc-8850.json>`
  (shingo45endo/tone-browser); rerun it rather than editing them.
- Anima GS EFX addresses and parameters come from the SC-8850 manual's Insertion Effect List
  (p.216-223) and MIDI Implementation (p.237); see comments in `tables_gs.py`.

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
  dry, about value x 100/64: value 50 shows D>77E on SC-VA, so D>50E is value 32).
  Check each other type's page before writing it. The seat unit's Space D already uses it (D>50E).
- **Pitch shifter ↔ ghost harmony**: match the shifter's interval to the ghost harmony where the chord
  allows (today: key-safe doubler / octave / fifth only).
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

## Out of scope unless the user asks

Seat units (0.19.024) only carry Anima's own harmony ghosts on a spare unit; generating new lines
there (players, motifs) is still out of scope.
Percussion / atonal mapping, SCPOP + Anima bypass, beat grid / motifs, extra orchestral players,
multi-input, a built-in file player. Keep seed performance, tone lock, ghosts, foley and the widened
family tables. Alchemy (GS↔XG rewrite) stays marked broken until the revival above is taken up. Anima is "for fun": a live stream player.
