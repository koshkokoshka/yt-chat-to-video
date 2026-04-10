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
- [ffmpeg](https://ffmpeg.org/download.html)
- Python packages:
    ```bash
    pip install Pillow requests
    ```

## Usage

1. Download the live chat replay using [yt-dlp](https://github.com/yt-dlp/yt-dlp):
    ```bash
    yt-dlp --skip-download --write-subs --sub-lang "live_chat" https://www.youtube.com/watch?v=CqnNp8kwE78
    ```

2. After running the above command, a file named `CqnNp8kwE78.live_chat.json` will appear in the current directory. This file contains the live chat data.<br>
   Pass this file to the script to convert it into a video:
    ```bash
    python yt-chat-to-video.py [options] CqnNp8kwE78.live_chat.json
    ```

3. Wait for the script to finish. It will generate a video file named `CqnNp8kwE78.mp4` in the current directory with the rendered chat replay.

## More common usage examples

### Render chat with a transparent background and overlay it on a video using ffmpeg
1. Download the YouTube video with live chat replay:
    ```bash
    yt-dlp --write-subs --sub-lang "live_chat" https://www.youtube.com/watch?v=CqnNp8kwE78
    ```
2. Run the script to generate a transparent chat video:
    ```bash
    python yt-chat-to-video.py "CqnNp8kwE78.live_chat.json" --transparent
    ```
3. Use ffmpeg to overlay the chat video on top of the recorded stream:
    ```bash
    ffmpeg -i "CqnNp8kwE78.mp4" -c:v libvpx-vp9 -i "CqnNp8kwE78.live_chat.webp" -filter_complex "[1:v]scale=400:-1[chat];[0:v][chat]overlay=W-w-10:H-h-10" output.mp4
    ```
   - (Note: without `-c:v libvpx-vp9` ffmpeg doesn't know how to handle transparent `.webp` files)

   - Change the `filter_complex` parameters to position the chat overlay as needed.

### Render chat at x2 scale (useful for downsampling)
```bash
python yt-chat-to-video.py "CqnNp8kwE78.live_chat.json" --scale 2 -w 800 -h 1080
```

## Command Line Arguments

| Option               | Description                                                           | Default           |
|----------------------|-----------------------------------------------------------------------|-------------------|
| `-o`, `--output`     | Output video file name                                                |                   |
| `--from`             | Start time (in seconds)                                               |                   |
| `--to`               | End time (in seconds)                                                 |                   |
| `-w`, `--width`      | Output video width (must be even)                                     | `400`             |
| `-h`, `--height`     | Output video height (must be even)                                    | `540`             |
| `-s`, `--scale`      | Chat resolution scale                                                 | `1`               |
| `-r`, `--frame-rate` | Output video framerate                                                | `10`              |
| `--transparent`      | Make chat background transparent (forces output to transparent .webm) |                   |
| `-b`, `--background` | Background color in hex                                               | `#0f0f0f`         |
| `-p`, `--padding`    | Inner padding in pixels                                               | `24`              |
| `--font-chat`        | Font for chat messages (must be installed on your system)             | `Roboto-Medium`   |
| `--font-author`      | Font for author names (must be installed on your system)              | `Roboto-Regiular` |
| `-u`, `--uppercase`  | Uppercase all chat message text                                       |                   |
| `--no-clip`          | Don\'t clip chat messages at the top                                  |                   |
| `--skip-avatars`     | Skip downloading user avatars                                         |                   |
| `--skip-emojis`      | Skip downloading emojis                                               |                   |
| `--cache`            | Cache downloaded avatars and emojis to disk                           |                   |
| `--proxy`            | HTTP/HTTPS/SOCKS proxy (`e.g. socks5://127.0.0.1:1080/`)              |                   |


## Fonts

This project includes the [Roboto](https://fonts.google.com/specimen/Roboto) font, licensed under the [Apache License, Version 2.0](https://www.apache.org/licenses/LICENSE-2.0).

- Roboto-Regular.ttf
- Roboto-Medium.ttf

Copyright (c) Google Fonts
