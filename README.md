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

## Usage

1. Download the live chat replay using [yt-dlp](https://github.com/yt-dlp/yt-dlp):
    ```bash
    yt-dlp --skip-download --write-subs --sub-lang "live_chat" https://www.youtube.com/watch?v=<video_id>
    ```

2. After running the above command, a file named `<video_id>>.live_chat.json` will appear in the current directory. This file contains the live chat data.<br>
   Pass this file to the script to convert it into a video:
    ```bash
    python yt-chat-to-video.py [options] <video_id>.live_chat.json
    ```

3. Wait for the script to finish. It will generate a video file named `<video_id>.mp4` in the current directory with the rendered chat replay.

## More common usage examples

### Render chat with a transparent background and overlay it on a video using ffmpeg
1. Download the YouTube video with live chat replay:
    ```bash
    yt-dlp --write-subs --sub-lang "live_chat" https://www.youtube.com/watch?v=<video_id>
    ```
2. Run the script to generate a transparent chat video:
    ```bash
    python yt-chat-to-video.py "<video_id>.live_chat.json" --transparent
    ```
3. Use ffmpeg to overlay the chat video on top of the recorded stream:
    ```bash
    ffmpeg -i "<video_id>.mp4" -c:v libvpx-vp9 -i "<video_id>.live_chat.webm" -filter_complex "[1:v]scale=-1:360:flags=lanczos[chat];[0:v][chat]overlay=W-w-10:H-h-10" output.mp4
    ```
   - `-c:v libvpx-vp9` codec to decode transparent `.webm` files
   - `scale=-1:360` to set the chat size (width: auto, height: 360)
   - `flags=lanczos` for high-quality downsampling
   - `overlay=W-w-10:H-h-10` to position the chat overlay in the bottom-right corner with 10px padding

### Speedup transparent .webm encoding
- Pass additional ffmpeg options `--ffmpeg-args "-deadline realtime -cpu-used 8 -row-mt 1"` to improve encoding speed

### Render chat at x2 scale (useful for downsampling)
- `python yt-chat-to-video.py "<video_id>.live_chat.json" --scale 2 -w 800 -h 1080`

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


## Fonts

This project includes the [Roboto](https://fonts.google.com/specimen/Roboto) font, licensed under the [SIL Open Font License, Version 1.1](https://openfontlicense.org/open-font-license-official-text/).

Copyright (c) 2011, The Roboto Project Authors

See `fonts/LICENSE-OFL.txt` for details.