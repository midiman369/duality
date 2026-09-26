# Notes for Claude Code sessions

- Develop on branch `dev`. The user downloads `duality.py` + `tables_gs.py` as a zip after each change.
- Offline regression suite: `python tests/run_all.py` (fake MIDI ports + clock, no hardware).
- Test songs are **not** in the repo (copyright). A fresh clone only runs the three self-contained
  tests; the rest print SKIP. `tests/README.md` → "Where the songs came from" lists each file's
  original name and checksum: ask the user to upload the ones you need and put takes in
  `recordings/`, songs in `tests/midi/` (original names are fine; both are git-ignored).
- Duality writes `--log` to `logs/duality-<stamp>.log` (one per run, one per `--record` take with the
  take's stamp; C starts a new one) and `--record` takes to `recordings/` by default.
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

"Quiet" means the unit's EFX players only (Part EFX On there, their ghosts, queued strums), not dry parts.
Family priority lives in `tables_gs.ANIMA_EFX_PRIORITY` (a distorted guitar takes a unit from a pad).
The file's own insert always wins its home unit.

## Tabled — ideas for later (ask before starting)

- **EFX preset library**: named parameter sets per family + insert type (beyond the type's defaults).
- **Parameter randomisation**: seed-driven values inside a floor/ceiling per parameter.
- **More live parameter control**: now that EFX Control 1/2 routing is right, drive more than drive
  level / rotary speed / wah manual.
- **Subtler orchestral inserts**: lower wet/dry Balance (param 16, `40 03 12`) on strings / brass / pads,
  and bring Stereo Delay back to strings with low feedback. Addresses are known (OM p.216-224).
- **Pitch shifter ↔ ghost harmony**: match the shifter's interval to the ghost harmony where the chord
  allows (today: key-safe doubler / octave / fifth only).
- **Bulk-dump pacing for real hardware**: files that send a whole SC-8850 bulk dump at t=0 (e.g. Every
  Breath You Take) exceed the manual's 40 ms-per-packet rule; SC-VA does not care, a real unit may.
- **Organ CC7 lift vs file fade**: the organ volume lift can fight a file's own fade (parked).

## Out of scope unless the user asks

Percussion / atonal mapping, SCPOP + Anima bypass, beat grid / motifs, extra orchestral players,
multi-input, a built-in file player. Keep seed performance, tone lock, ghosts, foley and the widened
family tables. Alchemy (GS↔XG rewrite) stays marked broken. Anima is "for fun": a live stream player.
