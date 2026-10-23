# Changelog

## Unreleased (dev 1.0.007)

- Anima look-ahead: an insert change at a part's first note waits for the part's next gap only when the file shows one coming; a part that plays straight on gets its insert at once (an organ entering mid-riff in ONESTOP2 had played its first six seconds dry).
- Player: a port with only tempo / SysEx (a sequencer's port marker on the tempo track) no longer counts as a port of its own, so a 16-channel song re-saved with its parts on another port plays on every out instead of being split into lanes.
- Panel: while a multi-port song plays, the channel grid (MIDI channel, voice count, Vol, Pan, Mod, Pitch) shows every port merged instead of port A alone.
- Anima seeds on multi-port songs: every port now plays the badge's seed plus 0101 per port, locked or not (unlocked, each port used to roll a seed of its own the badge did not show), so a take heard with seed DF14 comes back with `--anima-seed DF14` or **S**; X rerolls all of them together.
- Anima family spread: a family heard on four or more channels of one unit also takes a spare unit, half its channels moving over one by one in their rests (a big string section plays from two units); the spare yields to any family that needs it.
- Anima look-ahead while the file player plays: inserts are placed before a family's first note instead of at it, changes that would land on a note wait for the part's next gap, and a unit is not taken from a family about to play.
- Foley level: `--anima-foley off | on | <percent>`, and a song can ask for its own with a text event, `duality: foley off` or `duality: foley 25%`, which holds while the player plays it.
- Anima EFX palettes for orchestral parts, chosen by ear from listening: strings and choir now get Reverb, Gate Reverb
  (×½) or 3D Delay (×¼), with no chorus types; reeds and pipes get Reverb or Gate Reverb, and only now and then
  (×⅓ each) Space D, Stereo Delay or Mod Delay, with no parallel chorus / flanger / delay types.
- Anima tone traits: Brass sfz and Brass sfz 2 (Brass Section variations) have a built-in sforzando swell, so a
  part playing quick short notes on them goes back to the plain brass at its next rest.

## 1.0.0 (2026-10-18)

The first release. Everything since 0.18.40, the last version on `main`; the development builds in between were
numbered 0.18.41 – 0.19.068.

### Player and multi-port songs
- **Built-in MIDI file player** (`--play` files, folders or wildcards as a playlist, `--play-loop`): the same path as
  live input, so routing, Crucible, Voodoo, Anima and `--record` all apply; reads the tempo map, every SysEx and each
  track's MIDI Port marker. Hotkeys **Space** / **N** / **Z** / **T**; a Player row in the panel. `--input` is optional.
- **More than 16 channels**: a multi-port song (32 – 64 channels) plays each port on units of its own (*lanes*).
  Ports ask for a kind of unit with a text event (`duality: 8850`, `duality: port C mt32 x2`, `duality: 8850, cm64`
  in order of preference); port A's system SysEx reaches every port's units.
- `--input-format` takes the same names as the `--outs` tags (`8850`, `88pro`, `scva`, `cm64`, …).

### CM-64 and Voodoo
- **CM-64 outs** (`:cm64`): ch 11–16 go to the CM-32P half, voices counted per half (31 PCM partials, 1 or 2 per tone),
  PCM pan reversed like the LA half.
- **Voodoo on the PCM half**: GM programs with a fitting PCM tone play on CM-64 PCM parts (`tables_cm64.py`): a pool on
  two or more units; on one unit live seats (receive channels rewritten at each program change) or `--cm64-seats fixed`.
- The CM-32L sound effects stay playable under Voodoo on CM outs (keys 82–108, and 24–29 for the six GM percussion
  shares).
- A GM / GM2 System On keeps Voodoo loaded; the load is paced by each unit's own MIDI line and reports ready only when
  every unit has its last byte; a drum kit is resent only when the kit changes.
- Anima and the display see notes played on CM-64 PCM parts; native MT-32 / CM-32P programs map to GM families.

### Anima
- **GM files sound in color on a Sound Canvas**: a file's GM System On becomes a GS Reset on `:gs` ports (XG On on
  `:xg`), so CC00 / CC32 variations and the CM-64 maps play. Full SC-8850 tone tables; same-PC variations stay in family.
- **Tone colors**: older-map (SC-55 / 88 / 88Pro) and CM-64 tones that are not exact copies (compared by tone data from
  the ROM), every tone weighted by ear (605 tones on 101 programs), an EFX level per tone, and traits from listening
  notes (no LFO insert on a tone that already moves, no harmony on a tone with built-in fifths, one-shots back to the
  capital when held, squeal tones stepping down a tone set).
- **GS insert EFX rebuilt** on fixed rules: one insert per unit by family priority, the opening program-change burst
  placed once, never a type change under a sounding player, a sounding family never evicted by an unheard program
  change, notes never delayed (rerouted instead). Guitars pair on OD1/OD2 by pan; the file's own insert (also from a
  bulk dump) keeps its unit.
- **All 64 insertion types** of the SC-8850 / SC-88Pro, with palettes per family picked by ear and stepped weights.
- **Insert shaping**: pan follows the file, delays lock to the beat, pitch shifters play doubler / octave / fifth, Gate
  Reverb types by seed, dirt inserts fade with the file, levels set by ear per type.
- **Live insert control on CC16**: the wah follows the player (quack, sweep, held-note moves, lead vs rhythm, a rare
  scream), rotary speed flips on held chords, and a file's own set-and-left wah gets played and handed back.
- **Hero split**: a featured line can take a spare unit with another type of its family.
- **Harmony ghosts** balanced and tonal (melody / accompaniment / thin source, never a second, tritone or seventh
  against the line); **seat units** play the harmony on an idle unit with mirrored pan; bass sub-octaves never replace
  the file's bass tone.
- **Featured lines**: fast runs and slow tunes are lifted and competing parts step back.
- **Mallet sticking**: chords struck by hands, doubles, triplets and rolls where the part leaves room; delay inserts
  timed from a mallet part's own spacing.
- Game mode: idle ignores held notes; a new cue plans only its own channels.
- On mixed rigs Anima leaves idle GS units alone under Voodoo / MT-32 routing; no harmony ghosts on native MT-32 / CM
  music; the touch layers work on LA outs.
- Seed on the badge and in the log; `--anima-seed` / **S** lock a keeper.

### Record and log
- Logs go to `logs/duality-<stamp>.log`, one per run and one per recorded take; **C** starts a new log.
- Recordings go to `recordings/` by default (`IN-` / `OUT-` per port).

### Demo songs
- Five original songs come with the release: ONESTOP2 – A Brief History of Sound, Point & Click Overture, Adventure
  Game Night, The Hint Line and A Tribute to the Metal Gods (see the README's Demo songs).

## 0.18.40 and earlier

See the git history of `main`.
