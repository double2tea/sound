---
name: sound
description: Find and download sound effects from Freesound for videos, using download counts, ratings, descriptions, and licenses to select clips.
allowed-tools: Bash(python3 *), Bash(ffmpeg *)
---
Use Freesound for all sound-effect searches and downloads. You can't hear these clips, so lean on what people who did hear them left behind: download counts, ratings, and the uploader's description.

Run the commands from the skill directory (the folder containing this `SKILL.md`).

```
S=scripts/sfx.py
python3 $S freesound "<English query>"     # ↓downloads ★rating(votes) license description
python3 $S freesound "<English query>" --license cc0
python3 $S get <dir> fs:<id>...            # parallel download of searched clips
```
`--urls` on a search adds preview links for the user to audition.

Reading the signals:
- Prefer the most-downloaded clip that fits the cue, and quote the numbers when proposing it. A high rating count beats a high average: ★4.4(380) is stronger evidence than ★4.9(6).
- The Freesound description is the closest thing to listening: "built-in mic" or "made with my mouth" means lo-fi; a named recorder (Zoom, Sound Devices) and a clear source ("cork from a wine bottle") mean you know what you'll get. Reject clips whose description shows a different source than the cue, however popular.
- Freesound licenses: CC0 is free; BY needs a credit (`get` prints it); avoid BY-NC for anything commercial (`--license cc0|by` filters).
- Popularity says nothing about fit: a widely downloaded "thud" can be a 3 s cinematic rumble. Check the duration, and measure with ffmpeg (tail length, where the energy sits) before trusting a top hit. Use `--urls` when the user wants to audition candidates.

- Freesound times out: check the terminal's `http(s)_proxy` settings; the scripts use the shell proxy and do not change network configuration.
- Freesound caps ~80 KB/s per connection: put all keys in one `get`.

## More free libraries

When Freesound has no good match, search the other libraries with one command:

```bash
L=scripts/sfxlib.py
python3 $L search "<English query>" --source all -n 10
python3 $L get <dir> mixkit:1489 archive:<identifier> orangefree:<filename>
```

Sources and licenses:
- `archive` — Internet Archive audio items; license varies, check the item page (public domain / CC).
- `mixkit` — Mixkit Free License; commercial use allowed, no attribution required, do not redistribute the sound as a standalone file.
- `orangefree` — CC BY-NC 4.0; non-commercial only, attribution required.

Search results are cached in `~/.cache/sfx-sources/multi.json`; `get` needs a key from the same search. For Internet Archive items with several audio files, `get archive:<identifier>/<filename>` selects one; without a filename it picks the best-quality audio file.

## Original files (OAuth2 API)

Preview MP3s are for auditioning. When the user needs the uploader's original
WAV/FLAC/AIFF, use the API script. Setup is in `references/api-setup.md`.

```bash
A=scripts/fs_api.py
python3 $A status                       # credential + token expiry
python3 $A auth --no-browser            # one-time; open the printed URL, click Authorize
python3 $A search "<English query>" -n 10
python3 $A hq <dir> <sound_id>...       # original files, 2 s apart
```

`hq` prints id, license, author, bytes and path. API downloads are limited to
30/min and 500/day. If the token is expired, `hq` refreshes it automatically.
