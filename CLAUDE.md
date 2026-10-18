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
- Private backup of git-ignored work lives in the user's Gitea repo duality-workdata; at each milestone, push new
  scratchpad / tests-midi / recordings work there (never to GitHub). Layout and README as in the first snapshot
  (2026-10-18: scratchpad/, uploads/, session-images/, tests-midi/, recordings/, logs/, MANIFEST.sha256; first
  snapshot pushed as commit ef5c772). PNG / PDF / ZIP go to Git LFS (`apt-get install git-lfs`; clone it, add the new
  work, regenerate the manifest as its README says). Push with the GITEA_TOKEN environment secret through a one-off
  `-c credential.helper=` that reads the variable (never in a URL, config or file); without the secret, send the
  user tarballs (each under 500 MiB) to push themselves.
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
  (1867, 549 bars after the re-read; SPEED scales its tempo map; ppp bass-drum roll under its general pauses), then `bach_bwv565.py`:
  Diodati's SCPOP2000 MIDI (user's upload, local only in `tests/midi/` as "Bach - Toccata e Fuga in Re min BWV565
  2K.mid", a third-party performance: never in the repo; without it the suite skips Bach) for notes and timing,
  our organ registration (not his SCPOP SysEx), the fugue handed from the organ to the orchestra by voice roles
  (landmarks in his ticks at the top of the module), the organ back for the Molto adagio. Scans and OMR caches
  stay in the scratchpad (`hw/src`, `hw/bm` etc.; `two.sh`, `crop.sh` page viewers). The old medley is in git history.
  Every build also writes each piece alone (`halloween_<n>_<piece>[_4port].mid`, user's request 2026-10-17), cut
  from the suite's own events by `pd_kit.finish_parts` (never re-rendered: the shared RNG would change the notes);
  a new piece needs an entry in `build()`'s `ends` and in `PIECE_TITLES`.
- Prologue v3 (2026-10-18, 4:59; the user: the prologue "does drag on a bit at that 6 minutes", "keep to Chopin,
  Gounod and Berlioz, and transition to Mountain King"): `dies_irae(t0, ports)` = `procession()` (ours: drum, bell,
  Chopin's march tread on the organ and its riff in trombones / horns, `CHOPIN_RIFF`), `chant(CHANT_GROUPS[0])`
  (stanzas 0, 2), `cortege()` (`tests/hw_cortege.py`: Gounod's cortege bars 1-10 twice, read from the user's Lemoine
  copy; bassoon + pizz, then oboe over clarinet), `chant(CHANT_GROUPS[1])` (7, 19), `sabbath()` (`tests/hw_sabbat.py`:
  Berlioz's NBE score, the user's upload, bars 1-12, 102-186, 222-241 numbered 1-117 by `SB.B()`; `SB_CH` 16-ch, `SB4_CH`
  4-port, bells Church Bell on C9 / PA16). Each segment sets its own programs (`di_programs()` before a chant group).
  The scan stays in the scratchpad (`sabbat/sabbat.pdf`, PDF page = score page - 113; `dirge/` the Gounod).
  `pd_kit.finish_parts` now keeps the last of two tempos on one tick (it sorted by bpm and lost a fermata).
- Bald Mountain re-read (2026-10-17, in progress; the user: "all the accompaniment and no melody", the opening
  stab melody missing): the first reading flattened dense pages into held chords and misread clefs (trombones are
  in the alto clef). Fixed so far: bars 15-27 (the trombone / tuba theme E D E F G# A, trumpets, the held chords
  -> triplets -> stabs, the lost bar 27 restored by `insert_bar(27)`; sections above it keep their first-reading
  numbers, `shifted()` maps them, the generator's BM_MARKS go through it) and [2]'s copies (55-68; 63-66
  approximate), then pp. 22-27 (bars 67-90: D7 not D major, the D7b9 / E-flat calls, [3]'s staccato chords E7 - F -
  Dm - C7 and the falling-third sequence, the A - G# shakes; p. 27's lost bar restored by `insert_bar(89)`, so
  p. 28 starts at 91 as `hw/bmw/firstbar.json` says), then pp. 28-34 (bars 91-122: the horns' D drone, [104]'s C
  major, [5]'s winds in octaves not fifths, the 6/4 bars' leaps, the clarinets' climb a bar later and transposed).
  Then pp. 35-55 (bars 122-199: p. 35's lost bar 123 restored by `insert_bar(123)`, the B-flat blows without A-flat,
  [7]'s G-flat chatter, p. 42's brass call transposed, pp. 44-45's brass a bar later), then pp. 56-141 checked bar by
  bar against the scan (2026-10-17): the blows on beats 3-4 (197-200), p. 68 two bars shorter and the whole-tone
  descent (238-245), p. 75 three bars ([11] at 288), pp. 78-82 rebuilt (299-314), pp. 85-92 rebuilt from the first
  reading's bars (329-352, five fewer), pp. 101-102 and 108 one bar each fewer; `remove_bar()` drops a bar (both kinds
  are in INSERTED; `shifted()` maps first-reading numbers). Every page from p. 56 to the end now starts on the scan's
  bar. Note pass from bar 201 on (2026-10-17, the user: the opening "pretty good", "keep going ... through the end"):
  pp. 57-69, 72-78, 83-86, 93-101, 113-118 read again (blocks after the "the note pass from bar 201 on" marker, before
  "NOTE PASS END"); pp. 102-112 and 119-141 were compared at a glance and kept (they matched where checked). Bar 448
  was another extra bar (remove_bar). The piece is 549 bars, 12:52. For close reading render from the PDF at 300 dpi
  (`hw/cr.py pdf x0 x1 y0 y1 dpi`); the 1-bit OMR crops are too coarse for accidentals. `hw/bmw/firstbar.json`
  over-counts at every meter change; count bars by eye (two pages side by side at 60-90 dpi). Watch the first reading for
  transposing parts copied as written (the clarinets on p. 34 were) and for clef changes: horns I-II are in the
  bass clef (written + 2) up to p. 31 and the treble clef (written - 10) from p. 32 on; check each system's clefs. `ntv.py` follows the staff's skew (trust it over `zst.py`'s labels when they disagree by a
  line); it reads clefs from clefs.json, so tenor-clef bassoons (B-clef there) read 4 steps low. The scan (hw/src/bald1867.pdf) has
  score page 21 twice: PDF page = score page - 6 up to PDF 15, - 5 from PDF 17 on. Tools in the scratchpad
  `hw/bmw` (tools/omr copied; `clefs.json` per page; `nt2.py <pdf page>` caches heads, `ntv.py <pdf page>
  <first bar> <staves>` lists them, `zst.py <pdf page> <staves> x0 x1 <clefs>` = one staff enlarged with every
  line / space named; fix `hi/bars-NNN.json` by hand when barlines are missed). Accidentals by eye only.
  The user's arranging calls (2026-10-17, "make these our own slightly"): a Brass Section layer (part "brass": BM_CH
  ch9, the cornets share the trumpets' ch6; BM4_CH PC(8)) where the brass carries the tune or the stabs; and where a
  line passes from one section to another mid-phrase, the first section may keep doubling it so the line carries.
  Second listening note: the flutes' / oboes' / cornets' eighths in 13-20 are A G# G# A (we had B-flat / G: "off key").
  Third: the theme starts on F in bar 15 (with the trumpets' F octaves), E only from bar 16 ("missing the first brass note").
- SC-8850 tones (2026-10-18, the user: "the suite targets 8850s ... take advantage of the total SC-8850 set of
  patches"): `pd_kit.gs_mode()` (Halloween build) adds a GS Reset after GM System On (GM On makes the 8850 ignore
  bank selects) and CC0 = 0 before every plain program; `prog(..., variation=v)` sends CC0 v + CC32 4 (8850 map).
  `score_kit.render(..., variations={ch: var}, pizz_var={ch: (prog, var)})`. Bald Mountain only so far:
  `BM_VAR` / `BM_PIZZ` / `BM4_VAR` in make_pd_halloween.py (names from tools/picker/tone_info.json, key
  "var-4-pc0"). Duality passes CC0 / CC32 through (checked with the player replay on 1 and 4 ports).
  The user's picks: Wide FreHrns kept, violins Quad Strings ("to big-up violins"), likes Cello sect. and
  ContraBsSect. Ours on 4 ports only (their yes): `bm_layers()` on port D, St.ChoirAahs under the ff held brass
  chords, Warm Atmos pad under the quiet stretches (the Gamelan Gong layer is gone: real gongs, below).
  The user's favourite 8850 tones (2026-10-18, use them across the suite): Twin bones, Bones & Tuba, Bs. Trombone,
  Bones Sect., the falls (Brass Fall, Trumpet Fall, F.Horn Rip), the pizz variations (St.Pizzicato, Solo Pizz.)
  and the spiccatos (StringsSpic., Solo Spic.). Bald Mountain 4-port uses them: `Seat(spic=[ch])` +
  `score_kit.spiccato()` (staccato notes and short repeated-note chatter on StringsSpic., PC11 / PC12), the
  trombones' third chord note on Bs. Trombone (PC9), Bones & Tuba under the tuba (PC13), brass falls into general
  pauses and horn rips on ff entries (PC14-16, in `bm_layers`); 16-channel: St.Pizzicato for violins / violas.
  Solo Pizz. / Solo Spic. layers (port D, PD8 / PD9 / PD11 / PD12, x0.45) double the top note of the violins',
  violas' and cellos' pizz and spiccato notes (`Seat(pizz_layers=, spic_layers=)`; spiccato notes no longer get
  the arco Atk. layer).
- SC-8850 toolkit `tests/sc8850.py` (2026-10-18, the user: "save all these learnings ... in our tooling"; use it in
  every new song / remix / edit for the 8850): kit maps (Orchestra extras: held Snare Roll 25, Concert Snare 24,
  timpani 41-53 / 99-113, applause 88; the gongs are in the ETHNIC kit, PC 50: Big Gong 45, Small Gong 46, Bend 47,
  Thai 48), `gong()` / `gong_strokes()` / `move_off_gongs()`, the legato-enabled tones (Instrument List ":") with
  `mono()` / `legato_rows()`, the user's favourite tones, GS SysEx `gs()` / `hall()` / `drum_eq()`.
  score_kit.render takes `gongs={part: home kit or None}`, `held_rolls={part: key}`, `legato=(channels)`.
  Learned from the user's Movie Spectacular (Blue Max 1998, an upload, never in the repo): (1) gongs: the drum
  channel switches to ETHNIC for a stroke and back (they ring on); a roll alternates Big / Small every third of a
  beat loud to soft; an accent strikes both; (2) the hall: Reverb macro Hall 1 + Reverb Time 96, reverb sends high;
  (3) the drum part + timpani through the insert Stereo-EQ, Low +10 dB, Hi 0, EFX send to reverb 127. With
  several ports, give a spare port its own kit instead of switching (the user: "use multiple kits on other ports";
  Bald Mountain 4-port: port B's kit is ETHNIC, so A + B still play everything). The Halloween suite sets only
  the hall on every port at the start (`hall_setup`); no insert of its own (the user, 2026-10-18: "keep the reverb
  settings and leave the efx out and let anima do its thing with seeds"; a file's insert takes its unit from Anima).
  `pd_kit.finish_parts` chases the last SysEx per address into each piece's file. Legato: a
  legato-enabled tone handles legato itself, no Mono mode or other setting (the user, 2026-10-18); the piccolo and
  flute desks of Bald Mountain 4-port play Piccolo : / Flute 2 : with connected notes overlapping a touch
  (`legato=`). Duality copies only 40 00-02 SysEx from port A to every lane (insert and part assigns stay per port).
  Falls / rips (the user: "sounding late"): the gesture is in the one-shot sample (`sc8850.GESTURES`: slot roots and
  lengths from the ROM dump, 32 kHz assumed): a fall is the falling note itself, started so the gesture ends with
  the brass note and never before its attack (`gesture_seconds`); each note takes the fall tone whose sample is
  nearest above it, and none more than GESTURE_BELOW (7) semitones under a sample (lower, the gesture drags).
  Rips play their whole gesture from a quarter beat before the entry; where in the sample the rip arrives is unknown.
  2026-10-18 listening (`bm_extras`, ours): brass mirrors on the opposite side at mf and louder (4 ports, port D:
  Fr.Horn 2 right for the horns, Brass ff left for trumpets / cornets, Bright Tb left for the trombones); bridges
  (both versions: PD4 / 16-ch ch9): where the heavy brass (tp crn trb tuba brass) played 3+ beats and stops at f or
  louder while the rest plays on loud, a soft St.Orch Brs double of the carrying line (horns, else winds / strings
  top), fading over up to 8 beats ("at 28 ... keep a little brass in that cutover": bar 22; the user asked for the
  same "conscious choice" wherever sections cut over); the opening (bars 1-12) gets a sustained St. Strings chord
  read from each bar (bass, its stronger third, its fifth or sixth, only pitch classes played) and on 4 ports
  StringsSpic. doubling the fast notes. score_kit: winds -5 dB, brass +1 dB, `thin_unisons` (a wind note doubling
  another wind channel's same note at the same moment plays at 0.7), `brass_lift` (+8 velocity at f and louder:
  the SC brass brightens).
  Then the whole suite and Mars (the user: "give the rest of the Halloween suite and Mars the full treatment"):
  generic `score_kit.notes_of` / `place` / `mirror_rows` / `bridges`; make_pd_halloween `brass_extras` (mirrors PD1-3,
  bridge PD4 or a resting 16-ch brass channel), `articulate4` + `ART4_PROG` + `ORCH4_VAR` + `LEGATO4` (spiccato
  PC11 / PC12, solo layers PD8 / 9 / 11 / 12, Bs. Trombone PC9, Bones & Tuba PC13, Piccolo : / Flute 2 :) for
  Mountain King (MK_VAR / MK_PIZZ / MK4_VAR, no bridges: its brass never drops out), Danse macabre (DM_*; Death's
  fiddle on Violin Atk:) and Bald Mountain; the prologue (DI_VAR) and the Bach (BACH.VAR, BACH4["VAR"]) get the
  tones only. Mars (make_pd_mars.py): GS mode + hall, VAR16 / PIZZ16 (col legno St.Pizzicato) / VAR4 (tenor tuba
  on Euphonium), Big / Small Gong (16-ch kit switch; 4-port port C's kit ETHNIC), held snare rolls, spiccato +
  Solo Spic. seats (PD9 / 11 / 12 / 13), legato PB1-3, thin_unisons / brass_lift, mirrors PD14-16, bridges PD8 /
  16-ch ch8. sc8850.gong_strokes: soft rolls strike every beat (below mf) or two (below mp).
- Orchestral weight (2026-10-17, the user's mix order, loudest first: brass sections, percussion hits, single brass and
  strings, the bass, piano, woodwinds / saxes, harps / mallets; then non-melody parts): `score_kit.WEIGHT_DB` / `tier()` /
  `weigh(vol, program, drums, role)` nudge each channel's hand-set CC7 by its tier (+2 .. -3 dB; the bass is a role the
  caller names). Used by `make_pd_mars.py` (ROLE / ROLE4; the 4-port Brass Section layers now at 0.5 / 0.45 velocity)
  and by the Halloween score pieces (`render(..., weight=True, roles=..., timp=...)`, `MIX4` for 4 ports). Winds are -3
  dB and the line balance's PROG_DB no longer calls them soft ("our winds seem too loud with anything beside them").
- Bass drum (2026-10-17, "a little too machine-gun"): `score_kit.bass_drum()` takes BD_TRIM off every Orchestra-kit
  bass-drum stroke, shapes quick repeats (beat accent, alternating hands, a few ticks of timing) and doubles each
  stroke on the timpani channel (BD_TIMP of its velocity, the nearest timpani note, else the tonic) with the
  timpani panned right (the kit's drum sits left). Mars and the Halloween score pieces use it.
- Line balance (2026-10-17; the user: Mars's little side-melody brass a little too quiet, the Halloween pieces
  less so, the prologue harp a bit quiet): `score_kit.balance(rows, progs, pcs, label)` runs in `score_kit.render`
  and both Mars renders before the per-channel merge (rows carry a tag: part, start beat, bar, articulations).
  It finds covered melodic phrases (rules in its header comment) and lifts each by up to `LINE_MAX_DB` 3 dB of
  velocity (`LINE_TARGET` -4 dB margin, `LINE_K` 0.8; `PROG_DB` is a rough per-program loudness, by guess, not
  measured). Tune there from the user's ears; `K.DEBUG = []` before a build, then `K.DEBUG` / `K.LOG`, show each
  phrase's verdict and lift. The Bach (role-based, not score_kit) and the prologue (its own code; harp CC7 100,
  arpeggios at the stanza level -2) are not balanced by it.
- Arranging and mixing learnings (2026-10-17, from the user's Mars / Bald Mountain listening; apply to every song):
  1. The tune first: a melody or theme that is missing, wrong by a note, or started a note late is what the ear
     catches ("all the accompaniment and no melody", "missing the first brass note"). Check every main line note by
     note (from the score where there is one; clefs and transpositions read carefully), then the bass, then the rest.
  2. Wrong notes in accompaniment figures read as "off key" against the tune: check repeated figures too.
  3. Family loudness order, loudest first: brass sections, percussion hits, single brass and strings, the bass,
     piano, woodwinds / saxes, harps / mallets; non-melody parts under all of these (score_kit.WEIGHT_DB, weigh()).
     GM sounds are closer in level than an orchestra; woodwinds especially stick out on GS ("too loud with anything
     beside them").
  4. Side melodies must not drown: lift covered lines (score_kit.balance), never boost what was marked to sit under.
  5. Big brass moments get weight on GM: a Brass Section layer under the theme / stabs, accents where marked.
  6. A line that passes between sections mid-phrase may keep the first section doubling it so it carries.
  7. Concert bass drum: softer, shaped repeats (no machine-gun), a soft timpani double on the other side
     (score_kit.bass_drum).
  8. Harps / celesta need the texture thinned around them to shine; give them level where they are featured.
  9. Our own arranging touches are welcome where they serve the music ("make these our own slightly"); say what
     is ours in the docstring.
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
- **Anima with look-ahead in the file player** (the user, 2026-10-18): the player knows what is coming, so it
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
