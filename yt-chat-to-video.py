"""
YouTube Chat to Video Renderer Backend.
Downloads chat replay data, parses it, and renders it into a video overlay
with support for various styles, codecs, and EDL-based cutting.
"""

import os
import sys
import shutil
import json
import re
import argparse
import subprocess
from io import BytesIO

# Third-party imports
import requests
from PIL import Image, ImageDraw, ImageFont

# Check dependencies
if not shutil.which('ffmpeg'):
    print("Error: ffmpeg is not installed or not in PATH.")
    sys.exit(1)
    
HAS_YTDLP = shutil.which('yt-dlp') is not None

# Helper functions
def hex_to_rgb(h):
    """Converts a hex color string to an RGB tuple."""
    if not h:
        return (0, 0, 0)
    try:
        h = h.lstrip('#')
        if len(h) == 3:
            h = ''.join([c*2 for c in h])
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    except ValueError:
        return (0, 0, 0)

def blend_colors(a_color, b_color, opacity):
    """Blends two RGB colors with a given opacity."""
    return tuple(int(a * opacity + b * (1 - opacity)) for a, b in zip(a_color, b_color))

def download_chat(url_or_id):
    """Downloads YouTube chat data using yt-dlp."""
    if not HAS_YTDLP:
        print("Error: yt-dlp is required for downloading chat but is not installed/found.")
        sys.exit(1)
        
    print(f"Downloading chat for {url_or_id}...")
    sys.stdout.flush()
    # Clean up old temporary files
    if os.path.exists("temp_chat.live_chat.json"):
        os.remove("temp_chat.live_chat.json")
        
    cmd = [
        'yt-dlp',
        '--write-subs',
        '--sub-langs', 'live_chat',
        '--skip-download',
        '--output', 'temp_chat',
        url_or_id
    ]
    try:
        # Run yt-dlp and capture output so it doesn't spawn a terminal window
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
        if os.path.exists("temp_chat.live_chat.json"):
            return "temp_chat.live_chat.json"
        
        # Sometimes yt-dlp might name it differently or fail silently on subs
        print("Error: content downloaded but chat JSON not found. Does the video have a replayable live chat?")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Error running yt-dlp: {e}")
        sys.exit(1)

def get_author_role(renderer):
    """Determines the role of the chat author (owner, moderator, member, or normal)."""
    # Returns: 'owner', 'moderator', 'member', 'normal'
    if 'authorBadges' in renderer:
        for badge in renderer['authorBadges']:
            tooltip = badge['liveChatAuthorBadgeRenderer']['tooltip'].lower()
            if 'owner' in tooltip:
                return 'owner'
            if 'moderator' in tooltip:
                return 'moderator'
            if 'member' in tooltip:
                return 'member'
    return 'normal'

# Data classes for style
class StyleConfig:
    """Holds configuration for chat styling, including colors and fonts per role."""
    def __init__(self, args):
        self.bg_color = hex_to_rgb(args.background)
        self.outline_color = hex_to_rgb(args.outline_color)
        self.outline_width = int(args.outline_width * args.chat_scale)
        
        # Username colors
        self.author_colors = {
            'owner': hex_to_rgb(args.color_owner),
            'moderator': hex_to_rgb(args.color_moderator),
            'member': hex_to_rgb(args.color_member),
            'normal': hex_to_rgb(args.color_normal)
        }
        
        base_msg_color = hex_to_rgb(args.message_color)
        self.message_colors = {
            'owner': hex_to_rgb(args.msg_owner) if args.msg_owner else base_msg_color,
            'moderator': hex_to_rgb(args.msg_moderator) if args.msg_moderator else base_msg_color,
            'member': hex_to_rgb(args.msg_member) if args.msg_member else base_msg_color,
            'normal': base_msg_color
        }
        
        self.roles = {}
        for role in ['owner', 'moderator', 'member', 'normal']:
            # Helper to get arg value or global default
            def val(attr_name, global_val):
                # e.g. args.owner_author_font_size
                arg_name = f"{role}_{attr_name}"
                v = getattr(args, arg_name, None)
                if v is None:
                    return int(global_val * args.chat_scale)
                return int(v * args.chat_scale)

            self.roles[role] = {
                'author_font_size': val('author_font_size', args.author_font_size),
                'message_font_size': val('message_font_size', args.message_font_size),
                'line_height': val('line_height', args.line_height),
                'avatar_size': val('avatar_size', args.avatar_size),
                'emoji_size': val('emoji_size', args.emoji_size),
                'padding': val('padding', args.padding),
                'author_color': self.author_colors[role],
                'message_color': self.message_colors[role]
            }
            
            # Static legacy values (used for cache keys or fallbacks)
            self.emoji_size = int(args.emoji_size * args.chat_scale)
            self.avatar_size = int(args.avatar_size * args.chat_scale)
            self.author_padding = int(8 * args.chat_scale)
            self.avatar_padding = int(16 * args.chat_scale) # Fixed padding between avatar and name
            self.outline_width = int(args.outline_width * args.chat_scale)

# EDL Parser
class EDLParser:
    """Parses Edit Decision Lists (EDL) to extract cut segments."""
    @staticmethod
    def timecode_to_seconds(tc):
        """Converts HH:MM:SS:FF or HH:MM:SS timecode to seconds."""
        # Format HH:MM:SS:FF
        try:
            parts = tc.split(':')
            if len(parts) == 4:
                h, m, s, f = map(int, parts)
                return h*3600 + m*60 + s + (f/30.0) # Approx 30fps base
            elif len(parts) == 3:
                h, m, s = map(int, parts)
                return h*3600 + m*60 + s
            return 0.0
        except ValueError:
            return 0.0

    @staticmethod
    def parse_file(path, target_clip_name=None):
        """Parses an EDL file and returns a list of (start, end) source timestamps for the target clip."""
        segments = [] # List of (source_in, source_out)
        
        last_event = None
        
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        for line in lines:
            line = line.strip()
            if not line: continue
            
            # M2 Time Warp (Motion Effect) - Ignore for now but don't crash
            if line.startswith("M2"): continue

            parts = line.split()
            
            # Check if likely event line (starts with digit id)
            # Standard CMX3600: ID TAPE TRACK TRANS [DUR] SRC_IN SRC_OUT REC_IN REC_OUT
            if len(parts) >= 8 and parts[0].isdigit() and parts[2] == 'V':
                try:
                    transition = parts[3]
                    
                    # Columns shift if transition is not Cut
                    # Cut (C): ID TAPE V C SRC_IN SRC_OUT ... (Indices: 4, 5)
                    # Dissolve (D): ID TAPE V D 030 SRC_IN SRC_OUT ... (Indices: 5, 6)
                    # Wipe (W001): ID TAPE V W001 030 SRC_IN ... (Indices: 5, 6)
                    
                    src_in_idx = 4
                    src_out_idx = 5
                    
                    if transition.startswith('D') or transition.startswith('W'):
                         # There is a duration field at index 4
                         src_in_idx = 5
                         src_out_idx = 6
                    
                    if len(parts) > src_out_idx:
                        src_in = EDLParser.timecode_to_seconds(parts[src_in_idx])
                        src_out = EDLParser.timecode_to_seconds(parts[src_out_idx])
                        last_event = (src_in, src_out)
                except Exception as e:
                    print(f"Warning: Failed to parse EDL line: {line} ({e})")
                
            elif line.startswith('* FROM CLIP NAME:'):
                if last_event:
                    clip_name = line.split(':', 1)[1].strip()
                    if target_clip_name is None or clip_name == target_clip_name:
                         segments.append(last_event)
                    last_event = None # Consumed

        return segments

class TimeMapper:
    """Maps linear render time to source time based on EDL segments."""
    def __init__(self, segments, fps):
        self.segments = segments # List of (start_sec, end_sec)
        self.fps = fps
        self.total_duration = sum([end - start for start, end in segments])
        
    def get_source_time(self, render_frame_idx):
        """Calculates the source timestamp for a given render frame index."""
        # Map linear render frame (0...N) to source timestamp
        # segment 1 length in frames
        target_time = render_frame_idx / self.fps
        
        elapsed = 0
        for start, end in self.segments:
            duration = end - start
            if elapsed + duration > target_time:
                # Found segment
                offset = target_time - elapsed
                return start + offset
            elapsed += duration
            
        return self.segments[-1][1] # EOS

# Renderer Class
class ChatRenderer:
    """Handles parsing, loading, and rendering of chat messages."""
    def update_style(self, args):
        """Updates the styling configuration and resets scaling resources."""
        self.args = args
        self.style = StyleConfig(args)
        
        # Reload fonts? Since each role can have different sizes, we might need multiple fonts?
        # NO, usually we just scale, but TrueType fonts are optimized for specific sizes.
        # But PIL ImageFont.truetype takes one size.
        # If Owner is 30px and Normal is 12px, we need TWO font objects.
        # So we need a font cache keyed by size.
        self.font_cache = {} 
        
        # Reset canvas
        self.width = args.width
        self.height = args.height
        
        if args.transparent:
            self.img = Image.new('RGBA', (self.width, self.height), (0, 0, 0, 0))
        else:
            self.img = Image.new('RGB', (self.width, self.height))
        self.draw = ImageDraw.Draw(self.img)
        
        # Recreate masks - wait, different avatar sizes per role means different masks!
        self.avatar_masks = {}
        for role, style in self.style.roles.items():
            s = style['avatar_size']
            if s not in self.avatar_masks:
                self.avatar_masks[s] = self.create_avatar_mask(s, 4)

    def get_font(self, font_path, size):
        key = (font_path, size)
        if key not in self.font_cache:
            try:
                self.font_cache[key] = ImageFont.truetype(font_path, size)
            except:
                self.font_cache[key] = ImageFont.load_default()
        return self.font_cache[key]

    def draw_chat(self, current_message_index):
        if self.args.transparent:
            self.draw.rectangle([0, 0, self.width, self.height], fill=(0, 0, 0, 0))
        else:
            self.draw.rectangle([0, 0, self.width, self.height], fill=self.style.bg_color)

        y = self.height
        
        # Fonts paths (global for now, or per role?? User only asked for layout/colors, presumably fonts are shared)
        script_dir = os.path.dirname(os.path.realpath(__file__))
        msg_font_path = self.args.message_font or f"{script_dir}/fonts/Roboto-Regular.ttf"
        auth_font_path = self.args.author_font or f"{script_dir}/fonts/Roboto-Medium.ttf"

        layout = []
        for i in range(current_message_index, -1, -1):
            message_data = self.messages[i]
            msg_time, avatar_url, author_name, message_runs, author_role = message_data
            
            # Get Role Style
            style = self.style.roles.get(author_role, self.style.roles['normal'])
            
            chat_inner_width = self.width - (style['padding'] * 2)
            chat_inner_x = style['padding']

            avatar_x = chat_inner_x
            author_x = avatar_x + style['avatar_size'] + self.style.avatar_padding
            
            # Colors
            current_author_color = style['author_color']
            current_msg_color = style['message_color']
            
            # Fonts
            author_font = self.get_font(auth_font_path, style['author_font_size'])
            message_font = self.get_font(msg_font_path, style['message_font_size'])

            author_width = author_font.getbbox(author_name, stroke_width=self.style.outline_width)[2]
            runs_x = author_x + author_width + self.style.author_padding

            num_lines = 1
            processed_runs = []
            run_x, run_y = runs_x, 0
            
            for run_type, content in message_runs:
                if run_type == 0:  # text
                    for word in content.split(" "):
                        word_width = message_font.getbbox(word + " ", stroke_width=self.style.outline_width)[2]
                        if run_x + word_width > chat_inner_width:
                            num_lines += 1
                            run_x = author_x
                            run_y += style['line_height']
                        processed_runs.append((0, run_x, run_y, word))
                        run_x += word_width
                elif run_type == 1: # emoji
                    # Use emoji size from style
                    emoji_size = style['emoji_size']
                    emoji = self.get_image_from_cache(content, emoji_size)
                    emoji_width = emoji_size
                    if run_x + emoji_width > chat_inner_width:
                        num_lines += 1
                        run_x = author_x
                        run_y += style['line_height']
                    processed_runs.append((1, run_x, run_y, emoji))
                    run_x += emoji_width

            # Vertical offsets
            padding_v = int(4 * self.args.chat_scale)
            if num_lines == 1:
                content_height = max(style['avatar_size'], style['author_font_size'], style['message_font_size'])
                message_height = content_height + (padding_v * 2)
                avatar_y = padding_v
                author_y = (message_height - style['author_font_size']) // 2
                runs_y = (message_height - style['message_font_size']) // 2
            else:
                message_height = (num_lines * style['line_height']) + (padding_v * 2)
                avatar_y = padding_v
                author_y = padding_v
                runs_y = padding_v

            # Check fit
            if self.args.no_clip and (y - message_height < 0):
                break
            
            layout.append({
                'h': message_height, 'data': message_data, 
                'ax': avatar_x, 'ay': avatar_y, 
                'anx': author_x, 'any': author_y, 
                'ry': runs_y, 'runs': processed_runs, 
                'ac': current_author_color, 'mc': current_msg_color,
                'af': author_font, 'mf': message_font, # Store fonts for render
                'as': style['avatar_size']
            })
            y -= message_height
            
            if not self.args.no_clip and y < 0:
                break

        # Render Layout
        curr_y = self.height
        for item in layout:
            curr_y -= item['h']
            
            # Avatar
            avatar = self.get_image_from_cache(item['data'][1], item['as'])
            if avatar:
                # Get correct mask for this size
                mask = self.avatar_masks.get(item['as'])
                self.img.paste(avatar, (item['ax'], curr_y + item['ay']), mask=mask)
            
            # Author
            self.draw.text((item['anx'], curr_y + item['any']), item['data'][2], font=item['af'], fill=item['ac'], stroke_width=self.style.outline_width, stroke_fill=self.style.outline_color)
            
            # Message
            for r_type, rx, ry_run, content in item['runs']:
                if r_type == 0:
                    self.draw.text((rx, curr_y + item['ry'] + ry_run), content, font=item['mf'], fill=item['mc'], stroke_width=self.style.outline_width, stroke_fill=self.style.outline_color)
                elif r_type == 1 and content:
                    self.img.paste(content, (rx, curr_y + item['ry'] + ry_run), mask=content)

        return self.img

    def __init__(self, style_args):
        """Initializes the chat renderer with style arguments."""
        self.update_style(style_args) # Use update_style for initialization too
        self.cache = {}
        self.cache_folder = "yt-chat-to-video_cache"
        self.messages = []
        self._assets_loaded = False

    def create_avatar_mask(self, size, scale):
        """Creates a circular alpha mask for avatars."""
        hires_size = size * scale
        mask = Image.new("L", (hires_size, hires_size), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, hires_size, hires_size), fill=255)
        # pylint: disable=no-member
        mask = mask.resize((size, size), Image.Resampling.LANCZOS)
        return mask

    def get_cached_image_key(self, path):
        """Generates a safe filename key from a URL."""
        no_extension, _ = os.path.splitext(path)
        no_protocol = no_extension.split('://', 1)[-1]
        safe_key = re.sub(r'[^a-zA-Z0-9_-]', '_', no_protocol)
        return safe_key

    def get_image_from_cache(self, url, size):
        """Downloads or retrieves an image from memory/disk cache."""
        cache_key = self.get_cached_image_key(url)
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        try:
            response = requests.get(url, timeout=10)
            image_data = Image.open(BytesIO(response.content)).convert("RGBA")
            # pylint: disable=no-member
            image_data = image_data.resize((size, size), Image.Resampling.LANCZOS)
            self.cache[cache_key] = image_data
            if self.args.use_cache:
                image_data.save(f"{self.cache_folder}/{cache_key}.png")
            return image_data
        except Exception: # pylint: disable=broad-exception-caught
            return None

    def load_messages(self, msgs):
        """Loads messages into the renderer and pre-fetches assets."""
        self.messages = msgs
        # Only download if we haven't already loaded this exact message set or if force reload?
        # Actually checking if self.cache has entries is better?
        # But dummy messages are same every time.
        # Let's check if we already have the keys in cache?
        
        if not self.args.skip_avatars:
            # Check first message avatar to see if we did this already? 
            # Or just iterate but `get_image_from_cache` is fast if in memory?
            # It is fast if in self.cache.
            # BUT the logs say "Downloading avatars..." which prints BEFORE the check.
            # So we move the print inside or check optimization.
            pass

        # Optimization: Only print once
        if not hasattr(self, '_assets_loaded'):
             if not self.args.skip_avatars:
                 print("Downloading avatars...")
                 for msg in self.messages:
                     self.get_image_from_cache(msg[1], self.style.avatar_size)
             
             if not self.args.skip_emojis:
                 print("Downloading emojis...")
                 for msg in self.messages:
                     for run_item in msg[3]:
                         if run_item[0] == 1:
                             self.get_image_from_cache(run_item[1], self.style.emoji_size)
             self._assets_loaded = True



def get_ffmpeg_command(cli_args):
    """Constructs the ffmpeg command line arguments."""
    cmd = [
        'ffmpeg', '-y', '-f', 'rawvideo',
        '-pix_fmt', 'rgba' if cli_args.transparent else 'rgb24',
        '-s', f'{cli_args.width}x{cli_args.height}',
        '-r', str(cli_args.frame_rate),
        '-i', '-', '-an'
    ]
    
    vcodec = 'libx264'
    pix_fmt = 'yuv420p'
    extra_args = []
    
    if cli_args.codec == 'prores':
        if sys.platform == 'darwin' and cli_args.hwaccel:
            vcodec = 'prores_videotoolbox'
            extra_args = ['-profile:v', '4']
            pix_fmt = 'bgra' if cli_args.transparent else 'yuv422p10le'
        else:
            vcodec = 'prores_ks'
            extra_args = ['-profile:v', '4444' if cli_args.transparent else '3']
            pix_fmt = 'yuva444p10le' if cli_args.transparent else 'yuv422p10le'
            
    elif cli_args.codec == 'hevc':
        if sys.platform == 'darwin' and cli_args.hwaccel:
            vcodec = 'hevc_videotoolbox'
            if cli_args.transparent:
                extra_args = ['-alpha_quality', '0.75'] 
                pix_fmt = 'bgra'
            else:
                pix_fmt = 'yuv420p'
        else:
            vcodec = 'libx265'
            pix_fmt = 'yuv420p'
            
    elif cli_args.codec == 'av1':
        vcodec = 'libsvtav1'
        pix_fmt = 'yuv420p'
        
    elif cli_args.codec == 'h264':
        if sys.platform == 'darwin' and cli_args.hwaccel:
            vcodec = 'h264_videotoolbox'
        else:
            vcodec = 'libx264'
        pix_fmt = 'yuv420p'

    cmd.extend(['-vcodec', vcodec, '-pix_fmt', pix_fmt])
    cmd.extend(extra_args)
    cmd.append(cli_args.output)
    return cmd

# Helper for Preview Mode (Called by GUI)
def get_preview_image(cli_args, dummy_messages, renderer=None):
    """Generates a static preview frame."""
    if renderer is None:
        renderer = ChatRenderer(cli_args)
        renderer.load_messages(dummy_messages)
    else:
        renderer.update_style(cli_args)
        # We assume messages are already loaded if renderer is reused
        # But if dummy messages changed? They usually don't in preview.
        # Ensuring assets are loaded for current sizes:
        # load_messages re-checks cache with new sizes (emoji/avatar size)
        renderer.load_messages(dummy_messages) # This is fast if cached
        
    return renderer.draw_chat(len(dummy_messages) - 1), renderer

if __name__ == "__main__":
    parser = argparse.ArgumentParser("yt-chat-to-video", add_help=False)
    # ... (Same args as before, can reuse or import logic if needed, but for now copying ensures standalone)
    parser.add_argument('--help', action='help', default=argparse.SUPPRESS, help='Show this help message and exit.')
    parser.add_argument('input_source', help='Path to JSON file OR YouTube Video URL/ID')
    parser.add_argument('-o', '--output', help="Output filename")
    parser.add_argument('-w', '--width', type=int, default=400, help="Output video width")
    parser.add_argument('-h', '--height', type=int, default=540, help="Output video height")
    parser.add_argument('-s', '--scale', dest='chat_scale', type=float, default=1.0, help="Chat resolution scale")
    parser.add_argument('-r', '--frame-rate', type=float, default=60, help="Output video framerate (default 60)")
    parser.add_argument('-b', '--background', default="#0f0f0f", help="Chat background color")
    parser.add_argument('--transparent', action='store_true', help="Make chat background transparent")
    parser.add_argument('-p', '--padding', type=int, default=24, help="Chat inner padding")
    parser.add_argument('-f', '--from', type=float, default=0, help='Start time in seconds')
    parser.add_argument('-t', '--to', type=float, default=0, help='End time in seconds')
    parser.add_argument('--color-owner', default="#ffd600", help="Owner username color")
    parser.add_argument('--color-moderator', default="#5e84f1", help="Moderator username color")
    parser.add_argument('--color-member', default="#2ba640", help="Member username color")
    parser.add_argument('--color-normal', default="#ffffff", help="Normal username color")
    parser.add_argument('--message-color', default="#ffffff", help="Message text color (default for all)")
    parser.add_argument('--outline-color', default="#000000", help="Text outline color")
    parser.add_argument('--outline-width', type=int, default=1, help="Text outline thickness")
    parser.add_argument('--author-font-size', type=int, default=13, help="Author name font size")
    parser.add_argument('--message-font-size', type=int, default=13, help="Message text font size")
    parser.add_argument('--line-height', type=int, default=16, help="Chat line height")
    parser.add_argument('--avatar-size', type=int, default=24, help="User avatar size")
    parser.add_argument('--emoji-size', type=int, default=16, help="Emoji size")
    parser.add_argument('--msg-owner', help="Owner message color override")
    parser.add_argument('--msg-moderator', help="Moderator message color override")
    parser.add_argument('--msg-member', help="Member message color override")
    parser.add_argument('--author-font', help="Path to author font (.ttf)")
    parser.add_argument('--message-font', help="Path to message font (.ttf)")
    parser.add_argument('--codec', choices=['h264', 'hevc', 'prores', 'av1'], default='h264', help="Video codec")
    parser.add_argument('--hwaccel', action='store_true', help="Try to use hardware acceleration")
    parser.add_argument('--quality', choices=['standard', 'high', 'lossless'], default='high', help="Encoding quality")
    parser.add_argument('--skip-avatars', action='store_true', help='Skip downloading user avatars')
    parser.add_argument('--skip-emojis', action='store_true', help='Skip downloading YouTube emoji thumbnails')
    parser.add_argument('--no-clip', action='store_false', help='Don\'t clip chat messages at the top')
    parser.add_argument('--use-cache', action='store_true', help='Cache downloaded avatars and emojis to disk')
    parser.add_argument('--proxy', help='HTTP/HTTPS/SOCKS proxy (e.g. socks5://127.0.0.1:1080/)')
    
    # EDL Support
    parser.add_argument('--edl', help='Path to EDL file for timeline cutting')
    parser.add_argument('--clip-name', help='Specific clip name in EDL to process')

    # Role-based arguments generator
    roles = ['owner', 'moderator', 'member', 'normal']
    attrs = ['author_font_size', 'message_font_size', 'line_height', 'avatar_size', 'emoji_size', 'padding']
    for role in roles:
        for attr in attrs:
            arg_name = f"--{role}-{attr.replace('_', '-')}"
            parser.add_argument(arg_name, type=int, help=f"{role} {attr}")
    
    args = parser.parse_args()
    
    # Support for even dimensions (required by many codecs)
    # Support for even dimensions (required by many codecs)
    if args.width % 2 != 0:
        args.width += 1
    if args.height % 2 != 0:
        args.height += 1
    
    # Input Handling
    input_path = args.input_source
    if not input_path.endswith('.json'):
        input_path = download_chat(input_path)
        
    # Output logic
    if not args.output:
        if input_path.endswith('.json'):
            args.output = input_path.rsplit('.', 1)[0] + ".mp4"
        else:
            args.output = "output.mp4"
            
    # Load Messages
    chat_messages = []
    with open(input_path, "r", encoding='utf-8') as f:
        first_char = f.read(1)
        f.seek(0)
        if first_char == '[':
            try:
                chat_messages = json.load(f)
            except Exception: # pylint: disable=broad-exception-caught
                pass
        else:
            for line in f:
                if line.strip():
                    try:
                        chat_messages.append(json.loads(line))
                    except Exception: # pylint: disable=broad-exception-caught
                        continue

    # Process Messages
    messages = []
    for chat_message in chat_messages:
        chat_item = chat_message.get('replayChatItemAction', chat_message) # Handle simple format too
        
        # Simple extraction logic (same as before but robust)
        time_ms = 0
        if 'videoOffsetTimeMsec' in chat_item:
            time_ms = int(chat_item['videoOffsetTimeMsec'])
        
        # Handle different structures if needed, but primary is standard YT JSON
        actions = chat_item.get('actions', [])
        for action in actions:
            if 'addChatItemAction' in action:
                renderer = action['addChatItemAction']['item'].get('liveChatTextMessageRenderer')
                if not renderer:
                    continue
                
                author_role = get_author_role(renderer)
                avatar_url = renderer['authorPhoto']['thumbnails'][0]['url']
                author = renderer['authorName']['simpleText'] if 'authorName' in renderer else ''
                
                runs = []
                if 'message' in renderer and 'runs' in renderer['message']:
                    for run in renderer['message']['runs']:
                        if 'text' in run:
                            runs.append((0, run['text'].strip()))
                        elif 'emoji' in run:
                            runs.append((1, run['emoji']['image']['thumbnails'][0]['url']))
                
                messages.append((time_ms, avatar_url, author, runs, author_role))

    if not messages:
        print("Error: No messages found")
        sys.exit(1)

    # Time window & Segments
    time_mapper = None
    start_time_seconds = getattr(args, "from")
    end_time_seconds = getattr(args, "to")
    
    if args.edl:
        if not args.clip_name:
            print("Error: --clip-name is required when using --edl")
            sys.exit(1)
        print(f"Parsing EDL: {args.edl} for clip '{args.clip_name}'...")
        segments = EDLParser.parse_file(args.edl, args.clip_name)
        if not segments:
            print(f"Error: No segments found for clip '{args.clip_name}' in EDL.")
            sys.exit(1)
            
        print(f"Found {len(segments)} segments. Total cut duration: {sum(e-s for s,e in segments):.2f}s")
        time_mapper = TimeMapper(segments, args.frame_rate)
        duration = time_mapper.total_duration
        
        # Override start/end for filtering check
        # We need to keep ALL messages that might fall into ANY segment
        # Simplest: min start and max end
        min_start = min(s for s,e in segments)
        max_end = max(e for s,e in segments)
        
        # Filter renderer messages now or just handle all? 
        # Better to filter for memory efficiency
        renderer_messages = [m for m in messages if min_start*1000 <= m[0] <= max_end*1000]
        
    else:
        if end_time_seconds == 0:
            end_time_seconds = messages[-1][0] / 1000
        duration = end_time_seconds - start_time_seconds
        renderer_messages = [m for m in messages if start_time_seconds*1000 <= m[0] <= end_time_seconds*1000]
    
    # Initialize Renderer
    renderer = ChatRenderer(args)
    renderer.load_messages(renderer_messages) # Downloads assets
    
    # Start Render Loop
    print(f"Starting render: {args.width}x{args.height} @ {args.frame_rate}fps | Codec: {args.codec}")
    sys.stdout.flush()
    
    ffmpeg_cmd = get_ffmpeg_command(args)
    # Ensure output directory exists
    output_dir = os.path.dirname(os.path.abspath(args.output))
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    try:
        # pylint: disable=consider-using-with
        ffmpeg = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE, text=False)
        
        num_frames = int(args.frame_rate * duration)
        
        current_idx = -1
        
        for i in range(num_frames):
            if time_mapper:
                # EDl Mode
                timestamp_sec = time_mapper.get_source_time(i)
                time_ms = timestamp_sec * 1000
            else:
                # Linear Mode
                time_ms = (start_time_seconds + (i / args.frame_rate)) * 1000
            
            # Update index
            # If time jumped backwards (due to EDL cut ordering or restart), reset index
            if 0 <= current_idx < len(renderer_messages) and time_ms < renderer_messages[current_idx][0]:
                current_idx = -1

            while current_idx+1 < len(renderer_messages) and time_ms > renderer_messages[current_idx+1][0]:
                current_idx += 1
            
            # Draw
            # Optim: only draw if changed? Yes, handled in original logic but here we call draw every frame?
            # Original logic had redraw flag. Let's do that.
            # But DrawChat returns new image every time? No, it mutates self.img?
            # My Class implementation: self.draw writes to self.img.
            # So we only need to call DrawChat if current_idx changed OR first frame
            
            # Actually, to properly clear previous frame content if not transparent?
            # DrawChat handles clearing (rectangle fill).
            
            if i == 0 or (current_idx != -1 and time_ms > renderer_messages[current_idx][0]): # Simplification
                 # Revert to original robust logic:
                 # Check if we need to advance index
                 pass
            
            # To be safe and simple: Draw every frame. (Performance hit? Maybe. But accurate)
            # Original code only redrew on change.
            img = renderer.draw_chat(current_idx)
            img_data = img.tobytes()
            
            # Check for image size mismatch before writing
            expected_size = args.width * args.height * (4 if args.transparent else 3)
            if len(img_data) != expected_size:
                raise ValueError(f"Image data size mismatch. Expected {expected_size} bytes, got {len(img_data)} bytes. "
                                 f"This might indicate an issue with the renderer's output dimensions or pixel format.")

            try:
                ffmpeg.stdin.write(img_data)
            except BrokenPipeError as exc:
                _, stderr_out = ffmpeg.communicate()
                print(f"FFMPEG Error: {stderr_out.decode()}")
                raise RuntimeError("FFMPEG exited early.") from exc
            
            if i % max(1, int(args.frame_rate)) == 0:
                print(f"PROGRESS:{int(i/num_frames*100)}")
                sys.stdout.flush()
        
        print("PROGRESS:100")
        sys.stdout.flush()
        ffmpeg.stdin.close()
        ffmpeg.wait()
        print(f"OUTPUT_FILE:{os.path.abspath(args.output)}")
        sys.stdout.flush()
        
    except Exception as e: # pylint: disable=broad-exception-caught
        print(f"Error: {e}")
        try:
            ffmpeg.terminate()
        except Exception: # pylint: disable=broad-exception-caught
            pass
