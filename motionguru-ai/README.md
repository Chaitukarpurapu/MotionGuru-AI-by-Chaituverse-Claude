<p align="center"><img src="assets/banner.png" alt="MotionGuru AI by Chaituverse"></p>

# MotionGuru AI
**by Chaituverse.** Drop a talking-head video into Claude Code (or run the CLI) and get an edit that asks before it cuts, with pro captions, motion graphics, your face on the lower third, and layered sound design, rendered in one pass.

MotionGuru builds on the open-source [claude-reel-effects](https://github.com/adamgodigital/claude-reel-effects) engine by Adam Digital (kept unmodified in `engine/`, MIT), which is based on claude-video-effects by Vibha Ramprakash. See [ANALYSIS.md](ANALYSIS.md) for what we changed and why.

## What's new vs the original
| | |
|---|---|
| **Cut here or not?** | `cuts propose` finds silences, fillers (um, uh) and retakes, shows the words around each, opens a review page where you hear every moment and tap Cut/Keep. Nothing is removed until you approve. |
| **Pro captions** | 5 styles (`hormozi`, `karaoke`, `pill`, `minimal`, `neon`), keyword colours, Reels-safe position, Telugu/Hindi ready. Output is an editable `.ass`. |
| **Motion graphics** | `punch`, `shake`, `flash`, `glitch`, spring-pop `title`, `lower_third` and `watermark` with your face, `stat` cards, cinematic grades, vignette, grain. |
| **Sound design** | 11 synthesised SFX, auto-placed (riser before the hit), premium-pack slot, -14 LUFS, music ducking. |
| **One pass** | cuts, effects, captions, audio in a single ffmpeg graph: one encode, GPU when available. |
| **55 face-tracking effects, in the same plan** | `backdrop-word`, `spotlight`, `orbit`, `logo-link`, `card-drop` and the rest put things *behind your head*. Write them in the plan next to `punch`, captions and sound: `plans/signature.plan.json`. Needs `opencv-python` + `mediapipe`. |

## Styles
One command applies a whole look and places the effects on your words (hook first, emphasis only on keywords, never more than one big effect every few seconds).
```bash
python -m motionguru style list
python -m motionguru style apply reel.mp4 --style hormozi --approve safe --keywords "AI|free|10"
python -m motionguru style apply reel.mp4 --style chaitu-signature --hook "CHAITU" --plan-only   # just write the plan, edit it, then render with `edit`
```
| style | look |
|---|---|
| `clean` | bright, minimal captions, subtle punch-ins, your face lower third |
| `hormozi` | huge one/two-word captions, punch + shake, flash on the hook |
| `cinematic` | curves, vignette, grain, soft captions, sub-drop on the hook |
| `neon` | moody grade, glowing captions, glitch hits, stat cards on numbers |
| `chaitu-signature` | giant word behind your head, spotlight, pill captions (needs the engine) |

Add your own: copy a file in `styles/` and edit it.

## Install
```bash
git clone https://github.com/Chaitukarpurapu/MotionGuru-AI-by-Chaituverse-Claude ~/.claude/skills/motionguru
cd ~/.claude/skills/motionguru && pip install -r requirements.txt
```
Needs `ffmpeg` (Mac `brew install ffmpeg`, Windows `winget install ffmpeg`). Then in Claude Code: `/motionguru full edit` and drag your video in.

## CLI
```bash
python -m motionguru cuts propose reel.mp4 --lang te          # suggestions + review.html, nothing cut
python -m motionguru cuts apply   reel.mp4 --approve 1,3-5    # or: safe | all | ask (answer y/n in terminal)
python -m motionguru captions reel.mp4 --style karaoke --keywords "AI|free"
python -m motionguru edit reel.mp4 --plan plans/example.plan.json --approve safe          # everything, one pass
python -m motionguru edit reel.mp4 --plan my.plan.json --approve safe --still 5.5         # one check frame
python -m motionguru brand --name "Chaitu" --handle "@yourhandle" --accent "#FFD400"
python -m motionguru engine spotlight reel.mp4 out.mp4 --text "FREE"                      # face-tracking pass
```
Effect times in a plan are on the **final (post-cut)** timeline. Engine effects run as one extra pass (one more encode); `--still` with engine effects renders the whole clip, so it is slower.

## Your face
`assets/avatar.png` is cropped from your photo and shows in `lower_third` and `watermark`. Swap it with `brand --avatar path.png`.

## Premium SFX
Put licensed `.wav/.mp3` in `sfx_pack/` named by role (`whoosh_01.wav`, `riser_02.mp3` ...). They replace the synth sounds and are git-ignored. See `sfx_pack/README.md`.

## Telugu / Hindi
`--lang te` or `--lang hi`, `WHISPER_MODEL=medium`, and install *Noto Sans Telugu / Devanagari* so captions don't show boxes.

## Test
`pip install pytest && pytest` (needs ffmpeg). CI is in `.github/workflows/ci.yml`.

## Credits
- **Effects engine** (`engine/`): [claude-reel-effects](https://github.com/adamgodigital/claude-reel-effects) by Adam Digital, based on claude-video-effects by Vibha Ramprakash. All 55 effects and the original captions, pause trimming and sound effects come from there.
- **MotionGuru additions** by Chaituverse: approval-based cut review, filler and retake detection, ASS caption styles, camera/overlay motion graphics, face brand kit, sound design and mixing, one-pass renderer, styles system.
- Face tracking: OpenCV YuNet (MIT). Person cut-out: MediaPipe Selfie Segmenter (Apache 2.0). Word timing: faster-whisper (MIT). Logos: Simple Icons (CC0), trademarks of their owners. Fonts: see `engine/fonts/`.

## Licence
MIT. Original copyright notices for Vibha Ramprakash and Adam Digital are preserved in `LICENSE`, `NOTICE.md` and `engine/`. Brand logos are trademarks of their owners.
