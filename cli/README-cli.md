# BeatViz CLI (bundled with the app)

The macOS DMG ships a command-line binary alongside the app.

## Location

```
/Applications/BeatViz.app/Contents/Resources/cli/beatviz-cli
```

## Optional: global `beatviz` command

```bash
sudo ln -sf "/Applications/BeatViz.app/Contents/Resources/cli/beatviz-cli" /usr/local/bin/beatviz
```

## Usage

```bash
# list all 58 templates
beatviz --list-looks

# horizontal Full HD video
beatviz track.mp3 --look beatbars --duration 30 -o out.mp4

# vertical 9:16 (1080x1920) for Reels/TikTok
beatviz track.mp3 --look aura --width 1080 --height 1920 -o reels.mp4

# MIDI-aware looks (draw actual notes) — put a .mid next to the audio
beatviz track.mp3 --look piano --midi track.mid -o piano.mp4
```

The bundled binary uses the app's own Python + Pillow and needs `ffmpeg`
(ships inside the bundle; falls back to the one on your PATH).

فارسی:

باینری خط فرمان BeatViz داخل اپ نصب می‌شود در:
`/Applications/BeatViz.app/Contents/Resources/cli/beatviz-cli`

برای دستور سراسری:
`sudo ln -sf "/Applications/BeatViz.app/Contents/Resources/cli/beatviz-cli" /usr/local/bin/beatviz`
