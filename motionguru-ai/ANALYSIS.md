# Analysis of claude-reel-effects (what we found, what MotionGuru changes)

Read from the repo you uploaded (`scripts/fx.py` 2,714 lines, `trim.py`, `words.py`, `sfx.py`, `SKILL.md`, `requirements.txt`).

| # | Drawback in the original | Evidence | MotionGuru AI fix |
|---|---|---|---|
| 1 | **Cuts are automatic, never approved.** One loudness threshold decides what dies. | `trim.py`: `speech()` uses a fixed dB window; `SKILL.md` says "Tell them how much time it saved" after the fact | `cuts propose` lists every candidate with context, a review page to hear each one, and `--approve` ids. Retakes are never auto-approved. |
| 2 | **Only silences.** No filler words ("um", "uh"), no retakes. | `trim.py` works on audio energy only | Filler and retake detection from word timings. |
| 3 | **Cut joins can click.** Hard `aselect` with no fades. | `trim.py` filter graph | 12 ms micro-fades on every join. |
| 4 | **Timings break after trimming.** | `SKILL.md`: "every time after a cut moves" | `words.remap()` moves the transcript onto the new timeline; the cut and the edit run in one graph. |
| 5 | **Multiple re-encodes.** trim, then effects, then sfx mux, all at CRF 17. | `trim.py` and `fx.py` each call libx264 | One filter graph, one encode. |
| 6 | **Slow renderer.** Every frame goes through Python/NumPy/PIL, single process, CPU H.264 only. | `fx.py` `main()` loop, no multiprocessing or hardware encoder | Captions, grades, shake, zoom, glitch run inside ffmpeg (C speed); NVENC/VideoToolbox auto-used when they really work. |
| 7 | **Frame rate capped at 30.** | `probe()`: `min(fps, 30.0)` | Output keeps up to 60 fps. |
| 8 | **Captions can't do Indian languages.** The bundled fonts have no Telugu/Devanagari glyphs; PIL draws boxes. | `fonts/` list | ASS captions pick a Noto script font automatically and warn if it is missing. Whisper `--lang te/hi`. |
| 9 | **Captions locked to 4 hard-coded looks**, drawn in Python. | `cap_pill()` etc. in `fx.py` | 5 styles as data, output is an editable `.ass` file. |
| 10 | **Thin sound design.** 4 sounds, deliberately quiet, no risers/glitch/sub-drops, no loudness target, no music ducking. | `sfx.py` `SOUNDS` | 11 synthesised sounds, riser-before-hit timing, premium-pack slot, -14 LUFS, sidechain ducking. Also fixed a per-sample Python loop in the low-pass. |
| 11 | **`requirements.txt` is incomplete and unpinned.** faster-whisper is pip-installed at runtime mid-job. | `words.py` `subprocess ... pip install` | Declared in requirements; clear error if missing. |
| 12 | **No tests, no CI.** | no `tests/` | 5 end-to-end tests + GitHub Actions. |
| 13 | **Instagram-shaped.** Follow buttons, comment box, reels grids, "Edited by Claude" pill. | effects 11-13, 23, 30, 45 | Brand kit (your face, name, handle, colours); effects are neutral overlays. YouTube/Shorts safe positions are a roadmap item. |
| 14 | **Single-person talking head only.** Selfie segmenter at 540 px wide, face detection falls back to a guess. | `Tracker` class | Kept in `engine/` untouched; MotionGuru's own effects need no segmentation. |
| 15 | **Doc inconsistencies.** README says 55 effects; SKILL.md heading says "The 51 effects". | headings | Single source of truth in SKILL.md. |
| 16 | **Licensing trap for forks.** MIT needs the original copyright notices kept; logos are trademarks. | `LICENSE`, `README` credits | `NOTICE.md` and `engine/` licences kept intact. |

## Honest limits of MotionGuru v0.1
- It is not After Effects or Premiere. Effects are ffmpeg filters and overlays: strong for reels/shorts, no 3D, no node compositor, no real motion blur.
- The face-tracking effects still come from the vendored upstream engine and are a separate pass.
- Retake detection finds repeated openings of 3 words; it will miss paraphrased retakes. That is why it asks.
- Synthesised SFX are tasteful but not Hollywood. Put licensed packs in `sfx_pack/`.
- Tested on a synthetic clip, not a real talking-head video, and not on Windows/macOS.

## Roadmap
1. `speedramp`, whip-pan / zoom / glitch **transitions** between cuts (xfade), J- and L-cuts.
2. Auto B-roll slots + stock/AI image overlays with Ken Burns.
3. Real Lottie/After Effects (`.json`) overlay support via a Chromium renderer.
4. Emoji and animated-sticker captions; word-level translation (Telugu <-> English).
5. Local web UI: timeline with the cut review built in, drag effects, export plan JSON.
6. 9:16 / 1:1 / 16:9 safe-zone overlays per platform; auto-reframe.
7. Pinned dependencies, Windows and macOS CI.
