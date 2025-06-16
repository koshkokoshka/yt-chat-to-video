# YouTube Chat to Video

Convert YouTube Live Chat JSON (.live_chat.json) from [yt-dlp](https://github.com/yt-dlp/yt-dlp) into an `.mp4` video for overlaying chat messages on recorded streams.

<br/>
<div align="center">
   <img alt="screenshot_1" src="https://github.com/koshkokoshka/yt-dlp-chat-to-video/assets/12164048/1267472b-9905-4b83-93f3-14b3a42e2a10" height="280">
   <img alt="screenshot_2" src="https://github.com/koshkokoshka/yt-dlp-chat-to-video/assets/12164048/e8ca4552-399c-4401-a1da-f9af8182cfde" height="360">
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

## Command Line Arguments

| Option               | Description                                 | Default      |
| -------------------- |---------------------------------------------|--------------|
| `-o`, `--output`     | Output video file name                      | `output.mp4` |
| `-w`, `--width`      | Output video width (must be even)           | `400`        |
| `-h`, `--height`     | Output video height (must be even)          | `540`        |
| `-r`, `--frame-rate` | Output video framerate                      | `10`         |
| `-b`, `--background` | Background color in hex                     | `#0f0f0f`    |
| `-p`, `--padding`    | Inner padding in pixels                     | `24`         |
| `-s`, `--start`      | Start time (in seconds)                     |              |
| `-e`, `--end`        | End time (in seconds)                       |              |
| `--skip-avatars`     | Skip downloading user avatars               |              |
| `--skip-emojis`      | Skip downloading emojis                     |              |
| `--no-clip`          | Don\'t clip chat messages at the top        |              |
| `--cache`            | Cache downloaded avatars and emojis to disk |              |


## Fonts

This project includes the [Roboto](https://fonts.google.com/specimen/Roboto) font, licensed under the [Apache License, Version 2.0](https://www.apache.org/licenses/LICENSE-2.0).

- Roboto-Regular.ttf
- Roboto-Medium.ttf

Copyright (c) Google Fonts
