# Notes for Claude Code sessions

- Develop on branch `dev`. The user downloads `duality.py` + `tables_gs.py` as a zip after each change.
- Offline regression suite: `python tests/run_all.py` (fake MIDI ports + clock, no hardware).
- Test songs are **not** in the repo (copyright). A fresh clone only runs the three self-contained
  tests; the rest print SKIP. `tests/README.md` → "Where the songs came from" lists each file's
  original name and checksum: ask the user to upload the ones you need, then copy them into
  `tests/midi/` under the listed test names (git ignores `.mid` there).
- Anima GS EFX addresses and parameters come from the SC-8850 manual's Insertion Effect List
  (p.216-223) and MIDI Implementation (p.237); see comments in `tables_gs.py`.
