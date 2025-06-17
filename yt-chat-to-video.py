import os
import re
import argparse
import subprocess
import requests
import json
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

# Helper functions
def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def blend_colors(a_color, b_color, opacity):
    return tuple(int(a * opacity + b * (1 - opacity)) for a, b in zip(a_color, b_color))

# Parse arguments
parser = argparse.ArgumentParser("yt-chat-to-video", add_help=False)
parser.add_argument('--help', action='help', default=argparse.SUPPRESS, help='Show this help message and exit.')
parser.add_argument('input_json_file', help='Path to YouTube live chat JSON file')
parser.add_argument('-o', '--output', default="output.mp4", help="Output filename")
parser.add_argument('-w', '--width', type=int, default=400, help="Output video width")
parser.add_argument('-h', '--height', type=int, default=540, help="Output video height")
parser.add_argument('-r', '--frame-rate', type=int, default=10, help="Output video framerate")
parser.add_argument('-b', '--background', default="#0f0f0f", help="Chat background color")
parser.add_argument('-p', '--padding', type=int, default=24, help="Chat inner padding")
parser.add_argument('-s', '--start', '--from', dest='start_time', type=float, default=0, help='Start time in seconds')
parser.add_argument('-e', '--end', '--to', dest='end_time', type=float, default=0, help='End time in seconds')
parser.add_argument('--skip-avatars', action='store_true', help='Skip downloading user avatars')
parser.add_argument('--skip-emojis', action='store_true', help='Skip downloading YouTube emoji thumbnails')
parser.add_argument('--no-clip', action='store_false', help='Don\'t clip chat messages at the top')
parser.add_argument('--cache', action='store_true', help='Cache downloaded avatars and emojis to disk')
#parser.add_argument('--youtube-api-key', help='(Optional) Specify YouTube API key to download missing user avatars')  # TODO: implement this feature
args = parser.parse_args()

# Video settings
width, height = args.width, args.height
fps = args.frame_rate

if width < 2:
    print("Error: Width must be greater than 2")
    exit(1)
if width % 2 != 0:
    print("Error: Width must be even number")
    exit(1)
if width < 100:
    print("Error: Width can't be less than 100px")
    exit(1)
if height < 32:
    print("Error: Height can't be less than 32px")
    exit(1)
if height % 2 != 0:
    print("Error: Height must be even number")
    exit(1)
if fps < 1:
    print("Error: FPS can't be less than 1")
    exit(1)

# Timing settings
start_time_seconds = args.start_time
end_time_seconds = args.end_time

# Chat settings
chat_background = hex_to_rgb(args.background)
chat_author_color = blend_colors(hex_to_rgb('#ffffff'), chat_background, 0.7)
chat_message_color = hex_to_rgb('#ffffff')
chat_padding = args.padding
chat_avatar_size = 24
chat_emoji_size = 16      # TODO: should be 24px (youtube size)
chat_line_height = 16
chat_avatar_padding = 16  # Space between avatar image and author name
char_author_padding = 8   # Space between author name and message text
chat_inner_x = chat_padding
chat_inner_width = width - (chat_padding * 2)

# Flags
skip_avatars = args.skip_avatars
skip_emojis = args.skip_emojis

# Cache
cache_to_disk = args.cache
cache_folder = "_cache"

# Load chat font
try:
    script_dir = os.path.dirname(os.path.realpath(__file__))
    chat_message_font = ImageFont.truetype(f"{script_dir}/fonts/Roboto-Regular.ttf", 13)
    chat_author_font = ImageFont.truetype(f"{script_dir}/fonts/Roboto-Medium.ttf", 13)
except:
    print("\n")
    print("Warning: Can't load chat font. Fallback to default (may look ugly and don't support unicode).")
    print("         Make sure Roboto-Regular.ttf and Roboto-Medium.ttf files are in the /fonts directory")
    print("         You can download them from Google Fonts: https://fonts.google.com/specimen/Roboto")
    print("\n")
    chat_message_font = ImageFont.load_default()
    chat_author_font = ImageFont.load_default()

# Load chat messages
chat_messages = []
with open(args.input_json_file, "r", encoding='utf-8') as f:
    for line in f:
        chat_messages.append(json.loads(line))

messages = []  # processed messages
for chat_message in chat_messages:
    chat_item = chat_message['replayChatItemAction']

    time_ms = chat_item['videoOffsetTimeMsec']
    if end_time_seconds != 0 and int(time_ms) > end_time_seconds * 1000:
        break  # do not process messages that's not within current time window

    for action in chat_item['actions']:
        if 'addChatItemAction' in action:
            renderer = action['addChatItemAction']['item'].get('liveChatTextMessageRenderer')
            if not renderer:
                continue
            avatar_url = renderer['authorPhoto']['thumbnails'][0]['url']
            author = renderer['authorName']['simpleText'] if 'authorName' in renderer else ''
            runs = []
            for run in renderer['message']['runs']:
                if 'text' in run:
                    runs.append((0, run['text'].strip()))
                elif 'emoji' in run:
                    emoji_url = run['emoji']['image']['thumbnails'][0]['url']
                    runs.append((1, emoji_url))
            messages.append((int(time_ms), avatar_url, author, runs))

if len(messages) == 0:
    if end_time_seconds != 0:
        print("Error: No messages within selected time window")
    else:
        print("Error: No messages found in the chat file")
    exit(1)

# Calculate actual duration of the video
max_duration_seconds = messages[-1][0] / 1000   # max duration = last message time
if end_time_seconds == 0:
    end_time_seconds = max_duration_seconds     # make sure end time is correct

duration_seconds = end_time_seconds - start_time_seconds

# Launch ffmpeg subprocess
try:
    ffmpeg = subprocess.Popen([
        'ffmpeg',
        '-y',                        # Overwrite output file
        '-f', 'rawvideo',            # Input format: raw video
        '-pix_fmt', 'rgb24',         # Pixel format
        '-s', f'{width}x{height}',   # Frame size
        '-r', str(fps),              # Frame rate
        '-i', '-',                   # Input from stdin
        '-an',                       # No audio
        '-vcodec', 'libx264',        # Output codec
        '-pix_fmt', 'yuv420p',       # Pixel format required for compatibility
        args.output                  # Output file
    ], stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
except:
    print("Error: ffmpeg is not installed. Please install ffmpeg and try again.")
    print("You can install ffmpeg by running the following command:")
    print("  sudo apt install ffmpeg")
    print("or")
    print("  if you're on Windows, visit https://github.com/BtbN/FFmpeg-Builds/releases/")
    print("  to download prebuilt ffmpeg binary, then place ffmpeg.exe next to the .py file")
    exit(1)

# Create frame buffer with Pillow
img = Image.new('RGB', (width, height))
draw = ImageDraw.Draw(img)

# Cached images
cache = {}

def GetCachedImageKey(path):
    no_extension, _ = os.path.splitext(path)                # Remove file extension (.png)
    no_protocol = no_extension.split('://', 1)[-1]          # Remove protocol (https://)
    safe_key = re.sub(r'[^a-zA-Z0-9_-]', '_', no_protocol)  # Replace all unsafe characters with '_'
    return safe_key

# Load cached images from disk
if cache_to_disk:
    if not os.path.exists(cache_folder):
        os.mkdir(cache_folder)
    else:
        print("Loading cached images from disk...")
        for filename in os.listdir(cache_folder):
            cache_key = GetCachedImageKey(filename)
            cache[cache_key] = Image.open(f"{cache_folder}/{filename}").convert("RGBA")
        print(f"{len(cache)} images loaded")
else:
    print("\n")
    print("Hint: You can enable caching by adding --cache argument,")
    print("      this will avoid downloading images again on the next run")
    print("\n")

# Pre-download avatar images
if not skip_avatars:
    for message in messages:
        avatar_url = message[1]
        cache_key = GetCachedImageKey(avatar_url)
        if cache_key not in cache:
            print(f"Downloading avatar: {avatar_url}")
            response = requests.get(avatar_url)
            avatar = Image.open(BytesIO(response.content)).convert("RGBA")
            avatar = avatar.resize((chat_avatar_size, chat_avatar_size), Image.LANCZOS)  # Resize to desired output size
            cache[cache_key] = avatar
            if cache_to_disk:
                avatar.save(f"{cache_folder}/{cache_key}.png")

def CreateAvatarMask(size, scale):
    hires_size = size * scale
    mask = Image.new("L", (hires_size, hires_size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, hires_size, hires_size), fill=255)
    mask = mask.resize((size, size), Image.LANCZOS)
    return mask

avatar_mask = CreateAvatarMask(chat_avatar_size, 4)

# Pre-download emojis
if not skip_emojis:
    for message in messages:
        for run in message[3]:
            if run[0] == 1:
                emoji_url = run[1]
                cache_key = GetCachedImageKey(emoji_url)
                if cache_key not in cache:
                    print(f"Downloading emoji: {emoji_url}")
                    response = requests.get(emoji_url)
                    emoji = Image.open(BytesIO(response.content)).convert("RGBA")
                    emoji = emoji.resize((chat_emoji_size, chat_emoji_size), Image.LANCZOS)  # Resize to desired output size
                    cache[cache_key] = emoji
                    if cache_to_disk:
                        emoji.save(f"{cache_folder}/{cache_key}.png")

# Chat drawing method
current_message_index = -1

def DrawChat():
    draw.rectangle([0, 0, width, height], fill=chat_background)

    y = 0

    # Calculate layout to draw each visible message
    layout = []
    for i in range(current_message_index, -1, -1):  # from current message towards the first one (inclusive)
        message = messages[i]

        # Calculate horizontal offsets
        avatar_x = chat_inner_x
        author_x = avatar_x + chat_avatar_size + chat_avatar_padding
        runs_x = author_x + chat_author_font.getbbox(message[2])[2] + char_author_padding  # author_x + author_width + author_padding

        # Process message runs
        num_lines = 1
        runs = []
        run_x, run_y = runs_x, 0
        for run_type, content in message[3]:
            if run_type == 0:  # text
                for word in content.split(" "):
                    word_width = chat_message_font.getbbox(word + " ")[2]

                   # Wrap to new line
                    if run_x + word_width > chat_inner_width:
                        num_lines += 1
                        run_x  = author_x
                        run_y += chat_line_height

                    runs.append((0, run_x, run_y, word))
                    run_x += word_width

            if run_type == 1:  # emoji
               emoji = cache.get(GetCachedImageKey(content))
               if emoji:
                   emoji_width = emoji.size[0]

                   # Wrap to new line
                   if run_x + emoji_width > chat_inner_width:
                       num_lines += 1
                       run_x  = author_x
                       run_y += chat_line_height

                   runs.append((1, run_x, run_y, emoji))
                   run_x += emoji_width

        # Calculate vertical offsets (youtube chat message has 4px padding from top and bottom)
        if num_lines == 1:
            message_height = chat_avatar_size + 4 + 4
            avatar_y = 4
            author_y = 8
            runs_y = 8
        else:
            message_height = (num_lines * chat_line_height) + 4 + 4
            avatar_y = 4  # add top padding to avatar on multiline lines
            author_y = 4
            runs_y = 4

        y += message_height
        no_more_space = y > height

        if not args.no_clip and no_more_space:
            break  # no more space for messages

        # Store layout information
        layout.append((message_height, message, avatar_x, avatar_y, author_x, author_y, runs_y, runs))

        if args.no_clip and no_more_space:
            break  # no more space for messages

    # Draw messages from bottom up
    y = height
    for message_height, message, avatar_x, avatar_y, author_x, author_y, runs_y, runs in layout:
        _, avatar_url, author, _ = message

        y -= message_height

        # Draw avatar
        avatar = cache.get(GetCachedImageKey(avatar_url))
        if avatar:
            img.paste(avatar, (avatar_x, y + avatar_y), mask=avatar_mask)

        # Draw author
        draw.text((author_x, y + author_y), author, font=chat_author_font, fill=chat_author_color)

        # Draw message
        for run_type, run_x, run_y, content in runs:
            if run_type == 0:  # text
                draw.text((run_x, y + runs_y + run_y), content, font=chat_message_font, fill=chat_message_color)
            if run_type == 1:  # emoji
                img.paste(content, (run_x, y + runs_y + run_y), mask=content)

# Send frames to ffmpeg
redraw = True
num_frames = round(fps * duration_seconds)
for i in range(num_frames):

    time_ms = (start_time_seconds + (i / fps)) * 1000
    while current_message_index+1 < len(messages) and time_ms > messages[current_message_index+1][0]:
        current_message_index += 1
        redraw = True # redraw chat only on change

    if redraw:
        DrawChat()
        redraw = False

    # Write raw RGB bytes to ffmpeg
    ffmpeg.stdin.write(img.tobytes())

    # Print progress
    print(f"\rGenerating video frames... {i+1}/{num_frames} ({round(((i+1) / num_frames) * 100)}%)", end="")

print("\nDone!")
ffmpeg.stdin.close()
ffmpeg.wait()
