# YouTube Chat to Video

This script converts YouTube Live Chat JSON (`.live_chat.json`) from [yt-dlp](https://github.com/yt-dlp/yt-dlp) into a video format (`.mp4` or `.webm`). It allows you to render a chat replay as an overlay for a video. This script supports downloading user avatars and emojis, and can also generate videos with transparent backgrounds.

<br/>
<div align="center">
   <img alt="screenshot_1" src="https://github.com/user-attachments/assets/35971241-e2df-470f-9813-b0ca8908457f">
   <br/>
   <br/>
   <img alt="screenshot_2" src="https://github.com/user-attachments/assets/b67d78f3-8863-4830-a003-46c58400d9c7">
</div>
<br/>

## Requirements

- Python 3.6+
- Python packages: `pip install Pillow requests`
- FFmpeg:
  - **Linux**: `sudo apt install ffmpeg`
  - **Windows**: https://ffmpeg.org/download.html

### (Optional) For better kerning:
`libraqm` can improve text rendering and kerning accuracy
- **Linux**: `sudo apt install libraqm-dev`
- **Windows**: download a prebuilt `fribidi-windows-<x86/AMD64>` artifact from the [Pillow GitHub Actions](https://github.com/python-pillow/Pillow/actions/workflows/wheels.yml?query=branch%3Amain), then place `fribidi.dll` next to the `.py` file

### (Optional) For SVG support
> You may not actually need SVG support, as modern YouTube uses `.png` icons. Older chat recordings, however, may contain `.svg` icons.

- `pip install cairosvg`
- **Linux**: `sudo apt install libcairo2-dev`
- **Windows**: https://www.cairographics.org/download/ (or if you have GIMP installed, just add the `GIMP 3/bin` directory to your `PATH`)

Then run the script with the `--use-libcairo` option

## Basic usage

### 1. Clone the repository

```bash
git clone https://github.com/koshkokoshka/yt-chat-to-video.git
```

### 2. Download the live chat replay

Use [yt-dlp](https://github.com/yt-dlp/yt-dlp) to download the live chat replay:
```bash
yt-dlp --skip-download --write-subs --sub-lang "live_chat" https://www.youtube.com/watch?v=<video_id>
```

This will create `<video_id>.live_chat.json` in the current directory, containing the live chat data.

### 3. Render the chat

Pass the downloaded file to the script:
```bash
python yt-chat-to-video.py [options] <video_id>.live_chat.json
```

The script will generate `<video_id>.mp4` containing the rendered chat replay.

## Real-world usage example

This example shows how to render the chat at x2 scale with a transparent background and overlay it onto the recorded stream using FFmpeg.

### 1. Download the video and live chat replay

**Video**:
```bash
yt-dlp --live-from-start https://www.youtube.com/watch?v=<video_id>
```

**Chat**:
```
yt-dlp --skip-download --write-subs --sub-lang "live_chat" https://www.youtube.com/watch?v=<video_id>
```

### 2. Render the chat

```bash
python yt-chat-to-video.py \
    --transparent \
    --stroke-width 2 \
    --scale 2 \
    --width 720 \
    --height 720 \
    --cache \
    --ffmpeg-args "-deadline realtime -cpu-used 8 -row-mt 1" \
    -y \
    "<video_id>.live_chat.json"
```

- The chat will be rendered at x2 scale, so the video resolution is increased to 720x720 (it will be downscaled to 480p in the next step)
- The additional `--ffmpeg-args` options are used to improve encoding speed

### 3. Overlay the chat onto the video:

Use FFmpeg to overlay the rendered chat onto the recorded stream:
```bash
ffmpeg \
    -i "<video_id>.mp4" \
    -c:v libvpx-vp9 \
    -i "<video_id>.live_chat.webm" \
    -filter_complex "[1:v]scale=-1:480:flags=lanczos[chat];[0:v][chat]overlay=0:H-h-16" \
    "output.mp4"
```

- `-c:v libvpx-vp9` - use the VP9 codec for the transparent `.webm` file
- `scale=-1:480` - set the chat size (width: auto, height: 480px)
- `flags=lanczos` - use high-quality downsampling algorithm
- `overlay=0:H-h-16` - position the chat overlay in the bottom-left corner with 16px padding from the bottom

## Command Line Arguments

| Option               | Description                                                                                              | Default           |
|----------------------|----------------------------------------------------------------------------------------------------------|-------------------|
| `-o`, `--output`     | Output video file name                                                                                   |                   |
| `-y`                 | Skip confirmations                                                                                       |                   |
| `--from`             | Start time (in seconds)                                                                                  |                   |
| `--to`               | End time (in seconds)                                                                                    |                   |
| `-w`, `--width`      | Output video width (must be even)                                                                        | `400`             |
| `-h`, `--height`     | Output video height (must be even)                                                                       | `540`             |
| `-s`, `--scale`      | Chat resolution scale                                                                                    | `1`               |
| `-r`, `--frame-rate` | Output video framerate                                                                                   | `60`              |
| `--ffmpeg-args`      | Pass additional arguments to FFmpeg                                                                      |                   |
| `--animation-time`   | Duration of the chat message appearance animation in ms (0 to disable)                                   | `50`              |
| `--transparent`      | Make the chat background transparent (forces output to a transparent .webm)                              |                   |
| `-b`, `--background` | Background color in hex                                                                                  | `#0f0f0f`         |
| `-p`, `--padding`    | Inner padding in pixels                                                                                  | `24`              |
| `--font-chat`        | Font for chat messages (must be installed on your system)                                                | `Roboto-Medium`   |
| `--font-author`      | Font for author names (must be installed on your system)                                                 | `Roboto-Regiular` |
| `-u`, `--uppercase`  | Uppercase all chat messages                                                                              |                   |
| `--stroke-width`     | Stroke width for chat messages                                                                           |                   |
| `--stroke-color`     | Stroke color for chat messages in hex                                                                    |                   |
| `--no-clip`          | Don\'t clip chat messages at the top                                                                     |                   |
| `--skip-avatars`     | Skip downloading user avatars                                                                            |                   |
| `--skip-emojis`      | Skip downloading emojis                                                                                  |                   |
| `--use-libcairo`     | Convert SVG icons using libcairo2 (make sure it's installed)                                             | `false`           |
| `--cache`            | Cache downloaded avatars and emojis to disk                                                              |                   |
| `--proxy`            | HTTP/HTTPS/SOCKS proxy (`e.g. socks5://127.0.0.1:1080/`)                                                 |                   |
| `--youtube-api-key`  | [YouTube Data API v3](https://developers.google.com/youtube/v3) key for downloading missing user avatars |                   |

## License

This project includes the [Roboto](https://fonts.google.com/specimen/Roboto) font, licensed under the [SIL Open Font License, Version 1.1](https://openfontlicense.org/open-font-license-official-text/).

Copyright (c) 2011, The Roboto Project Authors

See `fonts/LICENSE-OFL.txt` for details.