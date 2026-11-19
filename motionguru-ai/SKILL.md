---
name: motionguru
description: MotionGuru AI by Chaituverse. Edit talking-head videos like a pro editor, with approval-based cuts (silences, filler words, retakes: ask the person before removing anything), Envato/Fluxo-style animated captions, motion graphics (punch-in, shake, glitch, flash, spring titles, lower thirds with the creator's face, stat cards), cinematic grades and layered sound design. Use when the user types /motionguru, or asks to cut, trim, caption, add motion graphics, SFX, transitions or a full edit on a video. The 55 face-tracking effects from the engine are available through `motionguru engine`.
---

# MotionGuru AI: how to work

The user may not be technical. Keep replies short, do the work yourself, never ask them to type commands. All paths are relative to this folder. Run commands as `python -m motionguru ...` from here.

## 0. First run
`ffmpeg` and Python 3.10+ must exist (Mac `brew install ffmpeg`, Windows `winget install ffmpeg`). `pip install -r requirements.txt` once. Check `python -m motionguru brand` shows the right name, handle and `assets/avatar.png`; ask once if the handle is wrong and save it with `python -m motionguru brand --handle @x --name "..."`.

## 1. THE RULE: never cut without asking
Cuts change meaning. Always do it in this order:
1. `python -m motionguru cuts propose <video> --lang <en|hi|te|...>` prints every suggestion (silence, filler word, retake) with its time, the words around it and a decision hint (`cut` = confident, `ask` = needs a human).
2. Show the user the list in plain words, grouped: "Safe: 9 pauses and 4 'um's (5.2 s). Need your call: a possible retake at 0:12 to 0:19 ('how to edit videos' said twice)". Tell them the review page is at `<video>.review.html` (they can hear each moment and tap Cut or Keep).
3. Ask which to cut. Accept "all", "only the safe ones", or numbers like `1,3-5`.
4. Only then `python -m motionguru cuts apply <video> --approve <ids|safe|all>` or pass `--approve` to `edit`.
Never use `--approve all` unless the user said so. Retakes are never auto-approved.
Cuts shift every later timestamp. If they gave times for the ORIGINAL video, put effects on the original timeline only after step 4 by re-reading the trimmed result: or plan effects after cutting and use `--approve` in the same `edit` call (effect times are then on the NEW timeline, see step 3).

## 2. Words
Captions and word-timed effects need `<video>.words.json` (made automatically by faster-whisper). Read it and fix misheard names and numbers by hand, keeping one entry per word. Telugu or Hindi: set `--lang te` / `--lang hi` and `WHISPER_MODEL=medium` (or `large-v3`). Indic captions need a Noto Sans font for that script installed or in `fonts/`.

## 3. Plan, check, render
Write `<video>_plan.json` (see `plans/example.plan.json`). Times are seconds on the FINAL (post-cut) timeline.
```json
{"captions": {"style": "hormozi", "keywords": "claude|free|24/7", "y": 0.70},
 "sfx": true, "music": null,
 "effects": [{"fx":"grade","name":"cinematic"}, {"fx":"lower_third","start":0.4,"end":3.4},
             {"fx":"punch","start":4.0,"end":4.6}, {"fx":"title","start":5,"end":7,"text":"10 minutes"}]}
```
Check frames first: `python -m motionguru edit <video> --plan <plan> --approve <ids> --still 5.5` saves a PNG. Look at it yourself: nothing over the face, text readable, nothing under the Reels UI (keep captions at y 0.62 to 0.74). Then render without `--still`.

## Effects menu
Camera and colour: `punch` (amp), `shake`, `flash`, `glitch`, `grade` (cinematic, warm, cool, pop, bw, moody), `vignette`, `grain`.
Overlays: `title` (text, color), `lower_third` (name, handle: shows the creator's face), `stat` (value, label), `watermark` (face bug).
Caption styles: `hormozi` (big, one to two words, accent pop), `karaoke` (phrase, active word lit), `pill` (highlight pill on the active word), `minimal`, `neon`.
Sound is automatic: riser before a hook, whoosh on titles, impact on punch/shake, glitch on glitch, shutter on flash. `"sfx": false` on any effect mutes it. Final mix is normalised to -14 LUFS; `music` ducks under the voice.
Face-tracking effects that put things behind the head (orbit, spotlight, logo-link, card-drop, 50 more): `python -m motionguru engine <effect> in.mp4 out.mp4 ...` (see `engine/SKILL.md`). Run these as a separate final pass.

## Pacing rules
One effect every 3 to 6 seconds, 0.4 to 2.5 s each. Never stack two big things. Hook in the first 2 s gets a riser + `title` or `punch`. Use numbers the user actually said. Premium SFX the user owns go in `sfx_pack/`.
Tell the user where the file is and remind them: you draft, they approve.
