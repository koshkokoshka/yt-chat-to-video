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
    yt-dlp --skip-download --write-subs --sub-lang "live_chat" https://www.youtube.com/watch?v=CqnNp8kwE78
    ```

2. After the stream download completes, a `<video_id>.live_chat.json` file will appear in the directory.<br>
   Pass this file to the script:
    ```bash
    python yt-chat-to-video.py [options] <video_id>.live_chat.json -o output.mp4
    ```

3. When conversion is complete, you'll get an `output.mp4` with rendered live chat

## More common usage examples

### Render chat with transparent background and overlay it on a video using ffmpeg
1. Download YouTube video with live chat replay:
    ```bash
    yt-dlp --write-subs --sub-lang "live_chat" https://www.youtube.com/watch?v=CqnNp8kwE78
    ```
2. Run the script to generate a transparent chat video:
    ```bash
    python yt-chat-to-video.py "CqnNp8kwE78.live_chat.json" --transparent
    ```
3. Use ffmpeg to overlay the chat video on top of recorded stream:
    ```bash
    ffmpeg -i "CqnNp8kwE78.mp4" -c:v libvpx-vp9 -i "CqnNp8kwE78.live_chat.webp" -filter_complex "[1:v]scale=400:-1[chat];[0:v][chat]overlay=W-w-10:H-h-10" output.mp4
    ```
   - (Note: without `-c:v libvpx-vp9` ffmpeg doesn't know how to handle transparent `.webp` files)

   - Change `filter_complex` parameters to position the chat overlay as needed.

### Render chat at x2 scale in 1080p resolution (useful for downsampling)
```bash
python yt-chat-to-video.py "CqnNp8kwE78.live_chat.json" --scale 2 -w 800 -h 1080
```

## Command Line Arguments

| Option               | Description                                                           | Default   |
|----------------------|-----------------------------------------------------------------------|-----------|
| `-o`, `--output`     | Output video file name                                                |           |
| `-w`, `--width`      | Output video width (must be even)                                     | `400`     |
| `-h`, `--height`     | Output video height (must be even)                                    | `540`     |
| `--scale`            | Chat resolution scale                                                 | `1`       |
| `-r`, `--frame-rate` | Output video framerate                                                | `10`      |
| `-b`, `--background` | Background color in hex                                               | `#0f0f0f` |
| `--transparent`      | Make chat background transparent (forces output to transparent .webm) | `false`   |
| `-p`, `--padding`    | Inner padding in pixels                                               | `24`      |
| `-s`, `--start`      | Start time (in seconds)                                               |           |
| `-e`, `--end`        | End time (in seconds)                                                 |           |
| `--skip-avatars`     | Skip downloading user avatars                                         | `false`   |
| `--skip-emojis`      | Skip downloading emojis                                               | `false`   |
| `--use-cache`        | Cache downloaded avatars and emojis to disk                           | `false`   |
| `--no-clip`          | Don\'t clip chat messages at the top                                  | `true`    |
| `--proxy`            | HTTP/HTTPS/SOCKS proxy (`e.g. socks5://127.0.0.1:1080/`)              |           |


## Fonts

This project includes the [Roboto](https://fonts.google.com/specimen/Roboto) font, licensed under the [Apache License, Version 2.0](https://www.apache.org/licenses/LICENSE-2.0).

- Roboto-Regular.ttf
- Roboto-Medium.ttf

Copyright (c) Google Fonts
