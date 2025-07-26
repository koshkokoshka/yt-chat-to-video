# YouTube Chat to Video

Convert YouTube Live Chat JSON (`.live_chat.json`) from [yt-dlp](https://github.com/yt-dlp/yt-dlp) into an `.mp4` video for overlaying chat messages on recorded streams.

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
- [ffmpeg](https://ffmpeg.org/download.html)
- Python packages:
    ```bash
    pip install Pillow requests
    ```

## Usage

1. Download a YouTube video with live chat replay using [yt-dlp](https://github.com/yt-dlp/yt-dlp):
    ```bash
    yt-dlp --live-from-start --write-subs https://www.youtube.com/watch?v=CqnNp8kwE78
    ```

2. After the stream download completes, a `<video_id>.live_chat.json` file will appear in the directory.<br>
   Pass this file to the script:
    ```bash
    python yt-chat-to-video.py [options] <video_id>.live_chat.json -o output.mp4
    ```

3. When conversion is complete, you'll get an `output.mp4` with rendered live chat

## Examples

- Render chat at x2 scale in 1080p resolution (recommended for better quality):
    ```bash
    python .\yt-chat-to-video.py "CqnNp8kwE78.live_chat.json" --scale 2 -w 800 -h 1080
    ```

## Command Line Arguments

| Option               | Description                                              | Default      |
|----------------------|----------------------------------------------------------|--------------|
| `-o`, `--output`     | Output video file name                                   | `output.mp4` |
| `-w`, `--width`      | Output video width (must be even)                        | `400`        |
| `-h`, `--height`     | Output video height (must be even)                       | `540`        |
| `--scale`            | Chat resolution scale                                    | `1`          |
| `-r`, `--frame-rate` | Output video framerate                                   | `10`         |
| `-b`, `--background` | Background color in hex                                  | `#0f0f0f`    |
| `-p`, `--padding`    | Inner padding in pixels                                  | `24`         |
| `-s`, `--start`      | Start time (in seconds)                                  |              |
| `-e`, `--end`        | End time (in seconds)                                    |              |
| `--skip-avatars`     | Skip downloading user avatars                            | `false`      |
| `--skip-emojis`      | Skip downloading emojis                                  | `false`      |
| `--use-cache`        | Cache downloaded avatars and emojis to disk              | `false`      |
| `--no-clip`          | Don\'t clip chat messages at the top                     | `true`       |
| `--proxy`            | HTTP/HTTPS/SOCKS proxy (`e.g. socks5://127.0.0.1:1080/`) |              |


## Fonts

This project includes the [Roboto](https://fonts.google.com/specimen/Roboto) font, licensed under the [Apache License, Version 2.0](https://www.apache.org/licenses/LICENSE-2.0).

- Roboto-Regular.ttf
- Roboto-Medium.ttf

Copyright (c) Google Fonts
