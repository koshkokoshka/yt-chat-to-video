import os
import re
import argparse
import subprocess
import requests
import json
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, features

script_dir = os.path.dirname(os.path.abspath(__file__))

# Helper functions
def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def blend_colors(a_color, b_color, opacity):
    return tuple(int(a * opacity + b * (1 - opacity)) for a, b in zip(a_color, b_color))

def format_time(value: int) -> str:
    if value < 0:
        return "-" + format_time(abs(value))
    if value < 60:
        return f"00:00:{value:02d}"
    if value < 3600:
        minutes, seconds = divmod(value, 60)
        return f"{minutes:02d}:{seconds:02d}"
    hours, remainder = divmod(value, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def safe_get(value, path, fallback=None):
    try:
        for part in path.split('.'):
            if '[' in part:
                key, index = part[:-1].split('[')  # Arrays
                value = value[key][int(index)]
            else:
                value = value[part]  # Fields
        return value
    except:
        return fallback

# Parse arguments
parser = argparse.ArgumentParser("yt-chat-to-video", add_help=False)
parser.add_argument('--help', action='help', default=argparse.SUPPRESS, help='Show this help message and exit.')
parser.add_argument('input_json_file', help='Path to YouTube live chat JSON file')
parser.add_argument('-o', '--output', help="Output filename")
parser.add_argument('-y', action='store_true', help="Skip confirmations")
parser.add_argument('-f', '--from', type=float, default=0, help='Start time in seconds')
parser.add_argument('-t', '--to', type=float, default=0, help='End time in seconds')
parser.add_argument('-w', '--width', type=int, default=400, help="Output video width")
parser.add_argument('-h', '--height', type=int, default=540, help="Output video height")
parser.add_argument('-s', '--scale', dest='chat_scale', type=int, default=1, help="Chat resolution scale")
parser.add_argument('-r', '--frame-rate', type=int, default=60, help="Output video framerate")
parser.add_argument('--ffmpeg-args', type=str, help="Pass additional arguments to FFmpeg")
parser.add_argument('--animation-time', type=int, default=50, help="Duration of the chat message appearance animation in ms (0 to disable)")
parser.add_argument('--transparent', action='store_true', help="Make chat background transparent (forces output to transparent .webm)")
parser.add_argument('-b', '--background', default="#0f0f0f", help="Chat background color")
parser.add_argument('-p', '--padding', type=int, default=24, help="Chat inner padding")
parser.add_argument('--font-chat', default="Roboto-Regular", help="Font for chat messages (must be installed on your system)")
parser.add_argument('--font-author', default="Roboto-Medium", help="Font for author names (must be installed on your system)")
parser.add_argument('--stroke-width', type=int, default=0, help="Stroke width for text")
parser.add_argument('--stroke-color', default="#000000", help="Stroke color for text")
parser.add_argument('-u', '--uppercase', action='store_true', help="Uppercase all chat message text")
parser.add_argument('--no-clip', action='store_false', help='Don\'t clip chat messages at the top')
parser.add_argument('--skip-avatars', action='store_true', help='Skip downloading user avatars')
parser.add_argument('--skip-emojis', action='store_true', help='Skip downloading YouTube emoji thumbnails')
parser.add_argument('--use-libcairo', action='store_true', help='Convert SVG icons using libcairo2')
parser.add_argument('--use-cache', '--cache', action='store_true', help='Cache downloaded avatars and emojis to disk')
parser.add_argument('--proxy', help='HTTP/HTTPS/SOCKS proxy (e.g. socks5://127.0.0.1:1080/)')
parser.add_argument('--youtube-api-key', help='YouTube Data API v3 key for downloading missing user avatars')
args = parser.parse_args()

# Import cairosvg
if args.use_libcairo:
    try:
        import cairosvg
    except Exception as e:
        print(e)
        print('')
        print("See https://www.cairographics.org/download/ for instructions on how to install Cairo on your system")
        if os.name == 'nt':  # Windows
            print("(if you're on Windows and have GIMP installed, just add the \"GIMP 3/bin\" directory to your PATH)")
        print('')
        exit(1)

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
start_time_seconds = getattr(args, "from")  # getattr is used because `from` is a reserved keyword
end_time_seconds = getattr(args, "to")

# Chat settings
chat_animation_time = args.animation_time
chat_background = hex_to_rgb(args.background)
chat_author_color = blend_colors(hex_to_rgb('#ffffff'), chat_background, 0.7)
chat_moderator_color = hex_to_rgb('#3ea6ff')
chat_message_color = hex_to_rgb('#ffffff')
chat_stroke_width = args.stroke_width
chat_stroke_color = hex_to_rgb(args.stroke_color)
chat_scale = args.chat_scale
chat_font_size = 14 * chat_scale
chat_padding = args.padding * chat_scale
chat_avatar_size = 24 * chat_scale
chat_badge_size = 16 * chat_scale
chat_emoji_size = 24 * chat_scale
chat_emoji_margin = 2 * chat_scale      # 2px margin around emojis
chat_line_height = 20 * chat_scale
chat_avatar_padding = 16 * chat_scale   # Space between avatar image and author name
chat_author_padding = 8 * chat_scale    # Space between author name and message text
chat_badge_padding = 2 * chat_scale     # Space between author name and badge icon
chat_message_padding = 4 * chat_scale   # Space between messages
chat_inner_x = chat_padding
chat_inner_width = width - (chat_padding * 2)

if chat_animation_time == 0 and fps > 10:
    print()
    print(f"Hint: Chat animation is disabled, but the FPS is set to a high value ({fps}).")
    print( "      Consider lowering the FPS to 5–10 to reduce the rendering time.")
    print( "      Use the -r <fps> option to adjust the frame rate.")
    print()

if chat_animation_time > 0 and fps * (chat_animation_time / 1000) < 3:
    print("")
    print(f"Note: The message appearance animation will have only ~{float(fps * (chat_animation_time / 1000.0)):.1f} frames and may look choppy.")
    print( "      Consider increasing the FPS to make the animation smoother.")
    print( "      Use the -r <fps> option to adjust the frame rate.")
    print("")

# If output filename is not specified, use input filename with .mp4 extension
if not args.output:
    if not args.input_json_file.endswith('.json'):
        print("Error: Input file must be a JSON file")
        exit(1)
    dot = args.input_json_file.rfind('.')
    args.output = args.input_json_file[:dot] + ".mp4"

# If transparent background is requested, force output to .webm format
if args.transparent:
    if not args.output.endswith('.webm'):
        print("Warning: Transparent background is requested, forcing output to .webm format")
        dot = args.output.rfind('.')
        args.output = args.output[:dot] + ".webm"

# Flags
skip_avatars = args.skip_avatars
skip_emojis = args.skip_emojis

# Cache
cache_to_disk = args.use_cache
cache_folder = f"{script_dir}/yt-chat-to-video_cache"

if chat_scale != 1:
    cache_folder += f"_x{chat_scale}"  # avoid cache mismatch error (fix suggested by @ExceptionFatale ❤️)

# Set proxy
if args.proxy:
    os.environ['HTTP_PROXY'] = args.proxy
    os.environ['HTTPS_PROXY'] = args.proxy

# Load chat font
def find_font(font_name):
    font_paths = [
        f"{script_dir}/fonts/{font_name}.ttf",
    ]
    if os.name == 'nt':  # Windows
        font_paths.extend([
            f"C:/Windows/Fonts/{font_name}.ttf",
        ])
    elif os.name == 'posix':  # macOS or Linux
        font_paths.extend([
            f"~/.local/share/fonts/{font_name}.ttf",   # Linux
            f"/usr/share/fonts/{font_name}.ttf",       # Linux
            f"~/Library/Fonts/{font_name}.ttf",        # macOS
            f"/Library/Fonts/{font_name}.ttf",         # macOS
            f"/System/Library/Fonts/{font_name}.ttf",  # macOS
        ])
    for path in font_paths:
        if os.path.exists(path):
            return path
    return None

if features.check_feature("raqm") == False:
    print("")
    print("Warning: Raqm is not available. Text kerning may not be accurate.")
    print("You can install libraqm to improve text rendering quality:")
    print("  sudo apt install libraqm-dev")
    print("or")
    print("  if you're on Windows, download a prebuilt \"fribidi\" artifact from:")
    print("  https://github.com/python-pillow/Pillow/actions/workflows/wheels.yml")
    print("  and then place fribidi.dll next to the .py file")
    print("")

try:
    chat_author_font = ImageFont.truetype(find_font(args.font_author), chat_font_size)
    chat_message_font = ImageFont.truetype(find_font(args.font_chat), chat_font_size)
except:
    print()
    print("Warning: Can't load chat font. Fallback to default (may look ugly and don't support unicode).")
    print()
    chat_author_font = ImageFont.load_default()
    chat_message_font = ImageFont.load_default()

# Load chat messages
chat_messages = []
with open(args.input_json_file, "r", encoding='utf-8') as f:
    for line in f:
        chat_messages.append(json.loads(line))

def get_chat_message_time_ms(chat_message):
    time_ms =(
           chat_message.get('videoOffsetTimeMsec')  # Chat downloaded during a live stream
        or safe_get(chat_message, 'replayChatItemAction.videoOffsetTimeMsec')  # Chat downloaded from an ended stream
    )
    if time_ms:
        return int(time_ms)
    return None

def get_chat_message_channel_id(renderer):
    return renderer['authorExternalChannelId']

def get_chat_message_avatar_url(renderer):
    return safe_get(renderer, 'authorPhoto.thumbnails[0].url')

def get_chat_message_author_name(renderer):
    return safe_get(renderer, 'authorName.simpleText', fallback='')

def get_chat_message_badge_icon(renderer):
    badges = renderer.get('authorBadges')
    if not badges:
        return None
    first_badge = badges[0]
    badge_renderer = first_badge['liveChatAuthorBadgeRenderer']
    if 'icon' in badge_renderer:
        return safe_get(badge_renderer, 'icon.iconType')
    # TODO: add `badge_renderer['customThumbnail']` support
    return None

def get_chat_message_text(run):
    text = run['text'].strip()
    if args.uppercase:
        text = text.upper()
    return text

def get_chat_message_emoji_url(run):
    return safe_get(run, 'emoji.image.thumbnails[0].url')

MESSAGE_TIME = 0  # tuple indices
MESSAGE_CHANNEL_ID = 1
MESSAGE_AVATAR_URL = 2
MESSAGE_AUTHOR_NAME = 3
MESSAGE_BADGE_ICON = 4
MESSAGE_RUNS = 5

messages = []  # processed messages
for chat_message in chat_messages:

    time_ms = get_chat_message_time_ms(chat_message)
    if not time_ms:
        continue
    if end_time_seconds != 0 and time_ms > end_time_seconds * 1000:
        break  # do not process messages that's not within current time window

    chat_item = chat_message.get('replayChatItemAction')
    if not chat_item:
        continue

    actions = chat_item.get('actions', [])
    for action in actions:
        renderer = safe_get(action, 'addChatItemAction.item.liveChatTextMessageRenderer')
        if not renderer:
            continue  # Process only "addChatItemAction" actions with "liveChatTextMessageRenderer"

        channel_id = get_chat_message_channel_id(renderer)
        avatar_url = get_chat_message_avatar_url(renderer)
        author_name = get_chat_message_author_name(renderer)
        badge_icon = get_chat_message_badge_icon(renderer)
        runs = []
        for run in renderer['message']['runs']:
            if 'text' in run:
                runs.append((0, get_chat_message_text(run)))
            elif 'emoji' in run:
                runs.append((1, get_chat_message_emoji_url(run)))
        messages.append((time_ms, channel_id, avatar_url, author_name, badge_icon, runs))

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

# Ask confirmation before continue
if not args.y:
    print("")
    print("Please review the settings before proceeding:")
    print("(use --help to change them, -y to skip this confirmation)")
    print("")
    print(f"  Input file:               {args.input_json_file}")
    print(f"  Output file:              {args.output}")
    print(f"  Time range:               {format_time(int(start_time_seconds))} - {format_time(int(end_time_seconds))}")
    print(f"  Video resolution:         {args.width}x{args.height}")
    print(f"  Frame rate:               {args.frame_rate}")
    print(f"  Chat scale:               x{args.chat_scale}")
    if args.animation_time > 0:
        print(f"  Animation:                {args.animation_time} ms ({float(fps * (chat_animation_time / 1000.0)):.1f} frames)")
    else:
        print(f"  Animation:                No")
    print(f"  Background:               {'Transparent' if args.transparent else args.background}")
    print(f"  Chat font:                {args.font_chat}")
    print(f"  Author font:              {args.font_author}")
    if args.stroke_width > 0:
        print(f"  Text stroke:                   {args.stroke_width}px {args.stroke_color}")
    else:
        print(f"  Text stroke:              No")
    print(f"  Uppercase messages:       {'Yes' if args.uppercase else 'No'}")
    print(f"  Clip messages:            {'Yes' if args.no_clip else 'No'}")
    print(f"  Cache downloaded images:  {'Yes' if args.use_cache else 'No [!]'}")
    print(f"  Download avatars:         {'No' if args.skip_avatars else 'Yes'}")
    print(f"  Download emojis:          {'No' if args.skip_emojis else 'Yes'}")
    print(f"  SVG support:              {'Enabled' if args.use_libcairo else 'Disabled'}")
    print(f"  Fetch missing avatars:    {'Yes' if args.youtube_api_key else 'No'}")
    print(f"  Additional FFmpeg args:   {args.ffmpeg_args or 'None'}")
    print("")
    response = input("Continue? [Y/n]: ").strip().lower()
    if response not in ('', 'y', 'yes'):
        print("Canceled")
        exit(0)

# Ask overwrite confirmation if file exists
if not args.y:
    if os.path.exists(args.output):
        print("")
        response = input(f"File '{args.output}' already exists. Overwrite? [y/N]: ").strip().lower()
        if response not in ('y', 'yes'):
            print("Canceled")
            exit(0)

# Launch ffmpeg subprocess
try:
    ffmpeg_args = [
        'ffmpeg',
        '-y',                        # Overwrite output file
        '-f', 'rawvideo',            # Input format: raw video
        '-pix_fmt', ('rgba' if args.transparent else 'rgb24'),         # Pixel format for raw input video
        '-s', f'{width}x{height}',   # Frame size
        '-r', str(fps),              # Frame rate
        '-i', '-',                   # Input from stdin
        '-an',                       # No audio
        '-vcodec', ('libvpx-vp9' if args.transparent else 'libx264'),  # Output codec
        '-pix_fmt', ('yuva420p' if args.transparent else 'yuv420p'),   # Pixel format for output
    ]

    if args.ffmpeg_args:
        ffmpeg_args += args.ffmpeg_args.split(" ")  # Additional ffmpeg args

    ffmpeg_args.append(args.output)  # Output file

    ffmpeg = subprocess.Popen(ffmpeg_args, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
except:
    print("Error: ffmpeg is not installed. Please install ffmpeg and try again.")
    print("You can install ffmpeg by running the following command:")
    print("  sudo apt install ffmpeg")
    print("or")
    print("  if you're on Windows, visit https://github.com/BtbN/FFmpeg-Builds/releases/")
    print("  to download prebuilt ffmpeg binary, then place ffmpeg.exe next to the .py file")
    exit(1)

# Create frame buffer with Pillow
if args.transparent:
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
else:
    img = Image.new('RGB', (width, height))
draw = ImageDraw.Draw(img)

# Cached images
cache = {}

def get_cached_image_key(path):
    no_extension, _ = os.path.splitext(path)                # Remove file extension (.png)
    no_protocol = no_extension.split('://', 1)[-1]          # Remove protocol (https://)
    safe_key = re.sub(r'[^a-zA-Z0-9_-]', '_', no_protocol)  # Replace all unsafe characters with '_'
    return safe_key

if cache_to_disk:
    if not os.path.exists(cache_folder):
        os.mkdir(cache_folder)
    else:
        # Load cached images from disk
        # TODO: Load images that appear only in the "--from" and "--to" range
        print("Loading cached images from disk...")
        for filename in os.listdir(cache_folder):
            cache_key = get_cached_image_key(filename)
            cache[cache_key] = Image.open(f"{cache_folder}/{filename}").convert("RGBA")
        print(f"{len(cache)} images loaded from cache")
else:
    print()
    print("Hint: You can enable caching by adding --cache argument,")
    print("      this will avoid downloading images again on the next run")
    print()

# Pre-download user avatars
if not skip_avatars:

    # Collect missing avatars
    missing_avatars = set()
    for message in messages:
        avatar_url = message[MESSAGE_AVATAR_URL]
        cache_key = get_cached_image_key(avatar_url)
        if cache_key not in cache:
            channel_id = message[MESSAGE_CHANNEL_ID]
            missing_avatars.add((channel_id, avatar_url))

    # Download user avatars
    for i, (channel_id, avatar_url) in enumerate(missing_avatars):
        print(f"[{i+1}/{len(missing_avatars)}] Downloading avatar: {avatar_url}")
        try:
            response = requests.get(avatar_url)
            avatar = Image.open(BytesIO(response.content)).convert("RGBA")
        except KeyboardInterrupt:
            print("\nInterrupted by user")
            exit(1)
        except:
            avatar = None

        # Fallback: Download missing avatar by channel ID using YouTube Data API
        if not avatar:
            if args.youtube_api_key:
                print(f'Falling back to downloading missing avatar for channel "{channel_id}" with the YouTube Data API...')
                try:
                    response = requests.get(f"https://www.googleapis.com/youtube/v3/channels?part=snippet&id={channel_id}&fields=items%2Fsnippet%2Fthumbnails&key={args.youtube_api_key}")
                    avatar_url = safe_get(response.json(), 'items[0].snippet.thumbnails.default.url')
                    response = requests.get(avatar_url)
                    avatar = Image.open(BytesIO(response.content)).convert("RGBA")
                except KeyboardInterrupt:
                    print("\nInterrupted by user")
                    exit(1)
                except:
                    print(f"Error: Can't download user avatar")
                    avatar = None
            else:
                print('Failed to download the user avatar. Use --youtube-api-key to fetch missing avatars via the YouTube Data API.')

        # TODO: add option to generate fallback avatars (colored circle with a user's first initial)
        if avatar is None:
            continue

        # Resize to desired output size
        avatar = avatar.resize((chat_avatar_size, chat_avatar_size), Image.LANCZOS)
        cache_key = get_cached_image_key(avatar_url)
        cache[cache_key] = avatar
        if cache_to_disk:
            avatar.save(f"{cache_folder}/{cache_key}.png")

def create_avatar_mask(size, scale):
    hires_size = size * scale
    mask = Image.new("L", (hires_size, hires_size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, hires_size, hires_size), fill=255)
    mask = mask.resize((size, size), Image.LANCZOS)
    return mask

avatar_mask = create_avatar_mask(chat_avatar_size, 4)  # Draw at x4 scale, then downscale using Lanczos algorithm

# Pre-download emojis
if not skip_emojis:

    # Collect missing emojis
    missing_emojis = set()
    for message in messages:
        for run in message[MESSAGE_RUNS]:
            if run[0] == 1:
                emoji_url = run[1]
                cache_key = get_cached_image_key(emoji_url)
                if cache_key not in cache:
                    missing_emojis.add(emoji_url)

    # Download emojis
    for i, emoji_url in enumerate(missing_emojis):
        print(f"[{i+1}/{len(missing_emojis)}] Downloading emoji: {emoji_url}")
        try:
            response = requests.get(emoji_url)
            if emoji_url.endswith('.svg'):
                if args.use_libcairo:
                    # Convert .svg to .png using "cairosvg"
                    image_data = cairosvg.svg2png(bytestring=response.content, output_height=chat_emoji_size)
                else:
                    print("Skipping .svg file (use --enable-svg to convert SVG files using libcairo2)")
                    continue
            else:
                image_data = response.content
            emoji = Image.open(BytesIO(image_data)).convert("RGBA")
            emoji = emoji.resize((chat_emoji_size, chat_emoji_size), Image.LANCZOS)  # Resize to desired output size
            cache_key = get_cached_image_key(emoji_url)
            cache[cache_key] = emoji
            if cache_to_disk:
                emoji.save(f"{cache_folder}/{cache_key}.png")
        except KeyboardInterrupt:
            print("\nInterrupted by user")
            exit(1)
        except:
            print(f"Error: Can't download emoji: {emoji_url}")

# Create badge icons (TODO: load form SVG files)
badge_icons = {
    'MODERATOR': Image.open(f"{script_dir}/icons/badge-moderator-96.png").convert("RGBA").resize((chat_badge_size, chat_badge_size), Image.LANCZOS)
}

# Chat rendering
current_message_index = -1
current_message_time = 0
current_animation_t = 0  # Animation factor (0.0 - start, 1.0 - end)

def draw_chat():
    # Clear all
    if args.transparent:
        draw.rectangle([0, 0, width, height], fill=(0, 0, 0, 0))
    else:
        draw.rectangle([0, 0, width, height], fill=chat_background)

    #
    # 1. Calculate messages layout
    #
    messages_layout = []
    y = 0
    for i in range(current_message_index, -1, -1):  # from current message towards the first one (inclusive)
        message = messages[i]

        # - Avatar
        avatar_url = message[MESSAGE_AVATAR_URL]
        avatar = cache.get(get_cached_image_key(avatar_url))
        avatar_x = chat_padding
        avatar_y = 0

        # - Author
        author = message[MESSAGE_AUTHOR_NAME]
        author_x = chat_padding + chat_avatar_size + chat_avatar_padding
        author_y = int(chat_avatar_size / 2)
        author_width = chat_author_font.getbbox(message[MESSAGE_AUTHOR_NAME])[2]

        # - Badge
        badge_url = message[MESSAGE_BADGE_ICON]
        badge = badge_icons.get(badge_url, None)
        badge_x = author_x + author_width + chat_badge_padding
        badge_y = int(chat_avatar_size / 2) - int(chat_badge_size / 2)

        author_color = chat_moderator_color if badge else chat_author_color

        # - Runs
        line_count = 1
        runs = []
        run_x = author_x + author_width + (chat_badge_size + chat_badge_padding if badge else 0) + chat_author_padding
        run_y = int(chat_avatar_size / 2)
        for run_type, run_content in message[MESSAGE_RUNS]:
            if run_type == 0:  # text
                for match in re.finditer(r'\S+\s*', run_content):  # Iterate over words (whitespace included)
                    word = match.group()
                    word_width = chat_message_font.getbbox(word)[2]

                    # Handle line wrap
                    if (run_x + word_width) > chat_inner_width:
                        run_x = author_x
                        run_y += chat_line_height
                        line_count += 1

                    runs.append((0, run_x, run_y, word))

                    run_x += word_width

            elif run_type == 1: # emoji
                emoji = cache.get(get_cached_image_key(run_content))
                if not emoji:
                    continue

                emoji_width, emoji_height = emoji.size

                emoji_width += chat_emoji_margin  # Margin left
                emoji_width += chat_emoji_margin  # Margin right

                # Handle line wrap
                if (run_x + emoji_width) > chat_inner_width:
                    run_x = author_x
                    run_y += chat_line_height
                    line_count += 1

                runs.append((1, run_x + chat_emoji_margin, run_y - int(chat_emoji_size / 2), emoji))

                run_x += emoji_width

        # Store layout information
        # TODO: Spacing between lines with emojis doesn't match the reference
        message_height = 0
        message_height += chat_message_padding  # Top 4px padding
        if line_count == 1:
            message_height += chat_avatar_size  # First line is always the size of the avatar
        elif line_count == 2:
            message_height += chat_avatar_size + chat_font_size  # Last line is always equals to the font size
        else:
            message_height += chat_avatar_size + ((line_count-2) * chat_line_height) + chat_font_size
        message_height += chat_message_padding  # Bottom 4px padding

        y += message_height
        no_more_space = y > height

        if not args.no_clip and no_more_space:
            break  # no more space for messages

        messages_layout.append((i, message_height, avatar, avatar_x, avatar_y, author, author_x, author_y, author_color, badge, badge_x, badge_y, runs))

        if args.no_clip and no_more_space:
            break  # no more space for messages

    #
    # 2. Draw calculated messages layout
    #
    y = height
    for i, message_height, avatar, avatar_x, avatar_y, author, author_x, author_y, author_color, badge, badge_x, badge_y, runs in messages_layout:
        if i == current_message_index:
            y -= round(current_animation_t * message_height)  # Animate message appearance
        else:
            y -= message_height

        # Draw avatar
        if avatar:
            img.paste(avatar, (avatar_x, y+avatar_y), mask=avatar_mask)

        # Draw author
        draw.text((author_x, y+author_y), author, anchor="lm", font=chat_author_font, fill=author_color, stroke_width=chat_stroke_width, stroke_fill=chat_stroke_color)

        # Draw badge
        if badge:
            img.paste(badge, (badge_x, y+badge_y), mask=badge)

        # Draw runs
        for run_type, run_x, run_y, run_content, in runs:
            if run_type == 0:  # text
                draw.text((run_x, y+run_y), run_content, anchor="lm", font=chat_message_font, fill=chat_message_color, stroke_width=chat_stroke_width, stroke_fill=chat_stroke_color)
            if run_type == 1:  # emoji
                img.paste(run_content, (run_x, y+run_y), mask=run_content)

def on_draw_chat_error(e):
    import traceback
    traceback.print_exc()
    print(f"\nError while drawing chat: {e}")
    print("Exiting...")

# Send frames to ffmpeg
redraw = True
animation_active = False
num_frames = round(fps * duration_seconds)
for i in range(num_frames):

    current_time_ms = (start_time_seconds + (i / fps)) * 1000

    # Update current message
    while current_message_index+1 < len(messages) and current_time_ms > messages[current_message_index+1][0]:
        current_message_index += 1
        current_message_time = messages[current_message_index][0]
        animation_active = True

    # Update animation
    if animation_active:
        redraw = True  # Redraw chat only when a new message appears or while animation is active
        time_since_last_message = current_time_ms - current_message_time

        if chat_animation_time > 0:
            current_animation_t = time_since_last_message / chat_animation_time
            current_animation_t = min(current_animation_t, 1.0)  # Clamp to [0.0, 1.0]
            current_animation_t = current_animation_t * current_animation_t * (3.0 - 2.0 * current_animation_t)  # Smoothstep
        else:
            current_animation_t = 1.0

        if time_since_last_message >= chat_animation_time:
            animation_active = False  # Animation done

    # Draw chat
    if redraw:
        try:
            draw_chat()
        except Exception as e:
            on_draw_chat_error(e)
            break
        redraw = False

    # Write raw RGB bytes to ffmpeg
    ffmpeg.stdin.write(img.tobytes())

    # Print progress
    print(f"\rGenerating video frames... {i+1}/{num_frames} ({round(((i+1) / num_frames) * 100)}%)", end="")

print("\nDone!")
ffmpeg.stdin.close()
ffmpeg.wait()
