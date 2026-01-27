import sys
import subprocess
import threading
import queue
import os
import platform
import shutil
import json
import tkinter as tk
import tkinter.font
import tkinter.filedialog
import tkinter.colorchooser
from PIL import Image, ImageDraw
import customtkinter as ctk
import shlex



# Import backend for preview
try:
    if os.getcwd() not in sys.path:
        sys.path.append(os.getcwd())
    import importlib.util
    spec = importlib.util.spec_from_file_location("yt_chat_to_video", os.path.join(os.path.dirname(__file__), "yt-chat-to-video.py"))
    yt_chat_to_video = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(yt_chat_to_video)
except Exception as e:
    print(f"Error importing backend: {e}")

# Theme Settings
ctk.set_appearance_mode("Dark")

class PreviewArgs:
    """Helper class to store preview arguments."""
    # pylint: disable=too-many-instance-attributes
    def __init__(self):
        self.width = 400
        self.height = 540
        self.chat_scale = 1.0
        self.background = "#000000"
        self.outline_color = "#000000"
        self.outline_width = 1
        self.transparent = False
        self.author_font_size = 13
        self.message_font_size = 13
        self.line_height = 16
        self.avatar_size = 24
        self.emoji_size = 16
        self.padding = 24
        self.color_owner = ""
        self.color_moderator = ""
        self.color_member = ""
        self.color_normal = ""
        self.msg_owner = ""
        self.msg_moderator = ""
        self.msg_member = ""
        self.message_color = ""
        self.author_font = ""
        self.message_font = ""
        self.skip_avatars = False
        self.skip_emojis = False
        self.use_cache = True
        self.no_clip = True
        self.is_dark_mode = True
        self.frame_rate = 60 # Added missing attribute

ctk.set_default_color_theme("blue")

# Dummy Data for Preview (Using placeholder images to prevent network lag/errors)
# We will intercept the cache lookup in backend or just use simple logic?
# Actually, let's just use valid URLs but handle failure gracefully.
# Better: Use local generated images if possible, but backend expects URLs.
# We will use these, and hope the backend cache logic handles them or we pre-seed cache?
# For now, let's trust the backend's try-except on network.
DUMMY_MESSAGES = [
    (1000, "https://lh3.googleusercontent.com/a/default-user=s88-c-k-c0x00ffffff-no-rj", "StreamOwner", [(0, "Hello everyone! Welcome to the stream.")], "owner"),
    (2000, "https://lh3.googleusercontent.com/a/default-user=s88-c-k-c0x00ffffff-no-rj", "SuperMod", [(0, "Please follow the rules!")], "moderator"),
    (3000, "https://lh3.googleusercontent.com/a/default-user=s88-c-k-c0x00ffffff-no-rj", "LongTimeMember", [(0, "HYPE HYPE HYPE!")], "member"),
    (4000, "https://lh3.googleusercontent.com/a/default-user=s88-c-k-c0x00ffffff-no-rj", "NewViewer", [(0, "Is this live?")], "normal"),
]


# pylint: disable=too-many-public-methods
class ChatRendererGUI(ctk.CTk):
    """
    Main GUI class for the YouTube Chat to Video Renderer.
    Handles configuration, preview generation, and process management.
    """
    def __init__(self):
        super().__init__()
        
        # Initialize UI Attributes to avoid Pylint W0201
        self.tab_view = None
        self.tab_main = None
        self.tab_video = None
        self.tab_style = None
        self.tab_advanced = None
        self.log_window = None
        self.url_entry = None
        self.file_path_var = None
        self.file_entry = None
        self.output_entry = None
        self.export_dir_var = None
        self.export_dir_entry = None
        self.width_entry = None
        self.height_entry = None
        self.fps_entry = None
        self.available_codecs = None
        self.codec_var = None
        self.ext_var = None
        self.bg_color = None
        self.bg_picker_btn = None
        self.check_transparent = None
        self.hwaccel_var = None
        self.scale = None
        self.outline_width = None
        self.role_tabs = None
        self.system_fonts = None
        self.author_font_var = None
        self.author_font_entry = None
        self.message_font_var = None
        self.message_font_entry = None
        self.edl_path_var = None
        self.edl_entry = None
        self.analyze_btn = None
        self.use_edl_switch = None
        self.edl_clip_var = None
        self.edl_status = None
        self.start_time = None
        self.end_time = None
        self.use_cache = None
        self.skip_avatars = None
        self.no_clip = None
        self.proxy_entry = None
        self.action_frame = None
        self.render_btn = None
        self.stop_btn = None
        self.progress_bar = None
        self.progress_label = None
        self.reveal_btn = None
        self.preview_renderer = None
        self._preview_job = None
        self.tk_image = None
        self.log_box = None
        self.process = None
        self.last_output_file = None
        self.paned_window = None
        self.preview_frame = None
        self.appearance_mode_menu = None
        self.duration_label = None
        self.canvas_container = None
        self.preview_label = None
        self.right_frame = None
        self.main_scroll = None
        self.cli_frame = None
        self.cli_box = None
        self.copy_cli_btn = None


        self.title("YT Chat Render Pro")
        self.geometry("1200x850")
        
        # Modern Theme
        ctk.set_appearance_mode("System") # Default to system, toggle overrides
        ctk.set_default_color_theme("dark-blue")
        
        # Custom Colors (Light, Dark) Tuples for automatic switching
        self.colors = {
            "bg": ("#f0f2f5", "#0f0f10"),       # Main BG
            "panel": ("#ffffff", "#18181b"),    # Cards/Sidebar
            "accent": ("#6366f1", "#818cf8"),   # Indigo/Purple
            "success": ("#10b981", "#34d399"),  # Emerald
            "error": ("#ef4444", "#f87171"),    # Red
            "text": ("#18181b", "#f4f4f5"),     # Main Text
            "text_dim": ("#71717a", "#a1a1aa"), # Secondary Text
            "border": ("#e4e4e7", "#27272a")    # Borders
        }
        self.configure(fg_color=self.colors["bg"])

        # Track manual edits to CLI box to avoid loops
        self.ignore_cli_change = False
        
        # Icons - using Emojis now
        # self.icons removed

        
        # Threading for preview
        self.preview_queue = queue.Queue()
        self.preview_lock = threading.Lock()
        self.last_preview_args = None
        self.is_preview_running = False
        
        # Main Split Layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # PanedWindow for resizing (Styled)
        # Note: PanedWindow bg doesn't support tuples directly, needs event listener or manual update.
        # For now we set a neutral gray or check mode.
        self.paned_window = tk.PanedWindow(self, orient=tk.HORIZONTAL, bg="#3f3f46", sashwidth=2, sashrelief="flat")
        self.paned_window.grid(row=0, column=0, sticky="nsew")

        # Preview Sidebar (Left)
        self.preview_frame = ctk.CTkFrame(self.paned_window, width=420, corner_radius=0, fg_color=self.colors["panel"])
        self.paned_window.add(self.preview_frame, minsize=350)

        self.preview_frame.grid_propagate(False)

        # Preview Header
        header_frame = ctk.CTkFrame(self.preview_frame, fg_color="transparent")
        header_frame.pack(fill="x", pady=(25, 15), padx=20)
        ctk.CTkLabel(header_frame, text="Live Preview", font=("SF Pro Display", 22, "bold"), text_color=self.colors["text"]).pack(side="left")
        
        # Theme Toggle (Styled)
        # Theme Toggle (Styled)
        # Replaced Switch with OptionMenu for System/Dark/Light
        self.appearance_mode_menu = ctk.CTkOptionMenu(header_frame, values=["System", "Dark", "Light"],
                                                      command=self.change_appearance_mode,
                                                      width=100, height=30,
                                                      fg_color=self.colors["panel"], 
                                                      button_color=self.colors["accent"],
                                                      button_hover_color=self.colors["accent"],
                                                      text_color=self.colors["text"])
        self.appearance_mode_menu.set("System")
        self.appearance_mode_menu.pack(side="right")
        
        # Duration Label - Hidden by default
        self.duration_label = ctk.CTkLabel(header_frame, text="", font=("SF Pro Text", 12), text_color=self.colors["accent"])
        self.duration_label.pack(side="right", padx=15)
        self.duration_label.pack_forget()

        
        # Preview Canvas container
        self.canvas_container = ctk.CTkFrame(self.preview_frame, fg_color="#000000", width=400, height=540, corner_radius=12, border_width=1, border_color="#333333")
        self.canvas_container.pack(padx=20, pady=10, expand=True)
        # self.canvas_container.pack_propagate(False) # Let it expand if resized? No, keep it fixed aspect or centered?
        # User wants resizing. Let's keep fixed canvas size but centered.
        
        self.preview_label = ctk.CTkLabel(self.canvas_container, text="")
        self.preview_label.pack(expand=True, fill="both")

        # Scrollable Main Content (Right)
        self.right_frame = ctk.CTkFrame(self.paned_window, corner_radius=0, fg_color=self.colors["bg"])
        self.paned_window.add(self.right_frame, minsize=450)
        
        self.right_frame.grid_columnconfigure(0, weight=1)
        self.right_frame.grid_rowconfigure(0, weight=1)
        
        self.main_scroll = ctk.CTkScrollableFrame(self.right_frame, label_text="CONFIGURATION", label_font=("SF Pro Display", 16, "bold"), fg_color="transparent")
        self.main_scroll.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        # Initialize UI Components within Scrollable Frame
        self.init_ui()

        # Load Settings
        self.load_settings()
        
        # Start queue checker
        self.after(100, self.check_preview_queue)

        # CLI Preview Box (Added below preview)
        self.cli_frame = ctk.CTkFrame(self.preview_frame, fg_color="transparent")
        self.cli_frame.pack(fill="x", padx=20, pady=(0, 20), side="bottom")
        
        ctk.CTkLabel(self.cli_frame, text="Command Preview (Editable):", font=("SF Pro Display", 12, "bold"), text_color=self.colors["text_dim"]).pack(anchor="w")
        
        self.cli_box = ctk.CTkTextbox(self.cli_frame, height=120, font=("Menlo", 12), fg_color="#000000", text_color="#00ff00", wrap="word")
        self.cli_box.pack(fill="x", pady=5)
        self.cli_box.bind("<Return>", self.on_cli_submit)
        self.cli_box.bind("<FocusOut>", self.on_cli_submit)
        
        self.copy_cli_btn = ctk.CTkButton(self.cli_frame, text="📋 Copy Command", width=120, height=25, 
                                          font=("SF Pro Text", 11), fg_color=self.colors["panel"], 
                                          text_color=self.colors["text"], hover_color=self.colors["accent"],
                                          command=self.copy_cli_command)
        self.copy_cli_btn.pack(anchor="e")

        
        # Hide Scrollbar when not needed
        self._scrollbar_visible = True
        self.main_scroll.bind("<Configure>", self.autohide_scrollbar)
        
        # Trigger initial preview update
        self.after(1000, self.update_preview)

    def get_available_codecs(self):
        try:
            output = subprocess.check_output(['ffmpeg', '-encoders'], text=True)
            codecs = set()
            for line in output.split('\n'):
                line = line.strip()
                if not line.startswith('V'): continue
                parts = line.split(maxsplit=2)
                if len(parts) < 2: continue
                encoder = parts[1]
                
                # Group common ones
                if "prores" in encoder: codecs.add("prores")
                elif "264" in encoder: codecs.add("h264")
                elif "265" in encoder or "hevc" in encoder: codecs.add("hevc")
                elif "av1" in encoder: codecs.add("av1")
                elif "vp9" in encoder: codecs.add("vp9")
                elif "mpeg4" in encoder: codecs.add("mpeg4")
            
            return sorted(list(codecs)) if codecs else ["h264", "hevc", "prores"]
        except:
            return ["h264", "hevc", "prores", "av1"]

    def supports_hw_accel(self, codec_family):
        """Checks if the system's ffmpeg supports hardware acceleration for the given codec."""
        try:
            output = subprocess.check_output(['ffmpeg', '-encoders'], text=True)
            expected = []
            if codec_family == "h264": expected = ["videotoolbox", "nvenc", "amf", "qsv"]
            elif codec_family == "hevc": expected = ["videotoolbox", "nvenc", "amf", "qsv"]
            elif codec_family == "prores": expected = ["videotoolbox"]
            elif codec_family == "av1": expected = ["nvenc", "qsv", "amf"] # av1_nvenc exists on new cards
            
            for line in output.split('\n'):
                if not line.strip().startswith('V'): continue
                parts = line.strip().split(maxsplit=2)
                if len(parts) < 2: continue
                encoder = parts[1]
                
                # Check if this encoder belongs to family and is HW
                if codec_family in encoder or (codec_family=="h264" and "264" in encoder) or (codec_family=="hevc" and "265" in encoder):
                     for hw_kw in expected:
                         if hw_kw in encoder: return True
            return False
        except:
            return False

    def copy_cli_command(self):
        cmd = self.cli_box.get("1.0", "end-1c")
        self.clipboard_clear()
        self.clipboard_append(cmd)
        self.copy_cli_btn.configure(text="✅ Copied!")
        self.after(2000, lambda: self.copy_cli_btn.configure(text="📋 Copy Command"))

    def get_system_theme(self):
        """Detects the system-wide appearance preference (Light/Dark)."""
        try:
            # macOS check
            if sys.platform == "darwin":
                res = subprocess.run(['defaults', 'read', '-g', 'AppleInterfaceStyle'], capture_output=True, text=True)
                if "Dark" in res.stdout: return "Dark"
                return "Light"
        except: pass
        return "Light" # Default fallback


    def autohide_scrollbar(self, event=None):
        """Toggles sidebar scrollbar visibility based on content height."""
        try:
            # Access internal scrollbar safely
            if not hasattr(self.main_scroll, "_scrollbar"): return
            
            # Get content height from the canvas
            canvas = self.main_scroll._parent_canvas
            # Check if bbox is ready
            bbox = canvas.bbox("all")
            if not bbox: return
            
            content_height = bbox[3]
            frame_height = self.main_scroll.winfo_height()
            
            # Toggle visibility
            if content_height <= frame_height:
                if self._scrollbar_visible:
                    self.main_scroll._scrollbar.grid_remove()
                    self._scrollbar_visible = False
            else:
                if not self._scrollbar_visible:
                    self.main_scroll._scrollbar.grid()
                    self._scrollbar_visible = True
        except:
            pass

    def change_appearance_mode(self, new_mode):
        ctk.set_appearance_mode(new_mode)
        self.schedule_preview_update()

    def on_cli_submit(self, event=None):
        # Allow shift+enter for new line if needed? No, standard enter submits/updates.
        # Check if user just typed
        if self.ignore_cli_change: return
        
        cmd = self.cli_box.get("1.0", "end-1c").strip()
        if not cmd: return
        
        if event and event.keysym == "Return":
             # prevent newline insertion if possible, or strip it
             pass 

        self.apply_cli_command(cmd)
        return "break" if event and event.keysym == "Return" else None

    def apply_cli_command(self, cmd_str):
        try:
            # Parse using simple split (won't handle complex quotes perfectly but good enough for generated cmds)
            # Parse using simple split (won't handle complex quotes perfectly but good enough for generated cmds)
            parts = shlex.split(cmd_str)
            
            # Helper to find value next to flag
            def get_arg(flags, is_bool=False):
                for flag in flags:
                    if flag in parts:
                        if is_bool:
                            return True
                        idx = parts.index(flag)
                        if idx + 1 < len(parts):
                            return parts[idx+1]
                return None if not is_bool else False

            # Map CLI flags back to GUI
            # 1. URL/File
            # We skip input source reverse mapping for safety or handle it carefully
            # Let's focus on style settings as requested "update the same settings"
            
            # Width/Height
            w = get_arg(['-w', '--width'])
            if w:
                self.width_entry.delete(0, "end")
                self.width_entry.insert(0, w)
            
            h = get_arg(['-h', '--height'])
            if h:
                self.height_entry.delete(0, "end")
                self.height_entry.insert(0, h)
            
            fps = get_arg(['-r', '--frame-rate'])
            if fps:
                self.fps_entry.delete(0, "end")
                self.fps_entry.insert(0, fps)
            
            codec = get_arg(['--codec'])
            # pylint: disable=protected-access
            if codec and codec in self.codec_var._values:
                self.codec_var.set(codec)
            
            scale = get_arg(['-s', '--scale'])
            if scale:
                self.scale.delete(0, "end")
                self.scale.insert(0, scale)
            
            outline = get_arg(['--outline-width'])
            if outline:
                self.outline_width.delete(0, "end")
                self.outline_width.insert(0, outline)
            
            # Bool flags
            if get_arg(['--transparent'], is_bool=True):
                self.check_transparent.select()
            else:
                self.check_transparent.deselect()
                
            # BG
            bg = get_arg(['-b', '--background'])
            if bg and not self.check_transparent.get():
                self.bg_color.delete(0, "end")
                self.bg_color.insert(0, bg)
            
            # Trigger update
            self.schedule_preview_update()
            
        except Exception as e: # pylint: disable=broad-exception-caught
            tkinter.messagebox.showerror("Invalid Command", f"Could not parse command: {e}")

    def toggle_theme(self):
        """Deprecated toggler, replaced by appearance menu."""
    
    def init_ui(self):
        """Initializes the main UI structure (tabs, actions, logs)."""
        # Tab View (Modern Style)
        # Colors: (Light, Dark)
        self.tab_view = ctk.CTkTabview(self.main_scroll, fg_color=self.colors["panel"], 
                                     text_color=self.colors["text"],
                                     segmented_button_fg_color=self.colors["bg"], 
                                     segmented_button_selected_color=self.colors["accent"], 
                                     segmented_button_selected_hover_color=self.colors["accent"], 
                                     corner_radius=12)
        self.tab_view.pack(fill="x", padx=15, pady=15)

        self.tab_main = self.tab_view.add("Main")
        self.tab_video = self.tab_view.add("Video Settings")
        self.tab_style = self.tab_view.add("Style & Colors")
        self.tab_advanced = self.tab_view.add("Advanced")

        self.init_main_tab()
        self.init_video_tab()
        self.init_style_tab()
        self.init_advanced_tab()
        
        # Action Bar (Fixed at bottom of scroll frame? No, append to scroll frame)
        self.init_actions()
        
        # Logs Window (Hidden by default, as requested)
        self.log_window = None

    def init_main_tab(self):
        """Initializes the Main tab inputs."""
        t = self.tab_main
        t.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(t, text="INPUT SOURCE", font=("SF Pro Display", 14, "bold"), text_color=self.colors["accent"]).grid(row=0, column=0, sticky="w", padx=10, pady=(20, 10))
        
        ctk.CTkLabel(t, text="YouTube URL / ID:").grid(row=1, column=0, sticky="w", padx=20, pady=5)
        self.url_entry = ctk.CTkEntry(t, placeholder_text="video url...")
        self.url_entry.grid(row=1, column=1, columnspan=2, sticky="ew", padx=20, pady=5)

        ctk.CTkLabel(t, text="OR Local JSON:").grid(row=2, column=0, sticky="w", padx=20, pady=5)
        self.file_path_var = tk.StringVar()
        self.file_entry = ctk.CTkEntry(t, textvariable=self.file_path_var, placeholder_text="Select path", height=35)
        self.file_entry.grid(row=2, column=1, sticky="ew", padx=(20, 10), pady=5)
        ctk.CTkButton(t, text="📂", width=40, height=35, command=self.browse_file, fg_color=self.colors["panel"], hover_color=self.colors["accent"], text_color=self.colors["text"]).grid(row=2, column=2, padx=(0, 20), pady=5)

        ctk.CTkFrame(t, height=2, fg_color=self.colors["border"]).grid(row=3, column=0, columnspan=3, sticky="ew", padx=10, pady=20)

        ctk.CTkLabel(t, text="OUTPUT OPTIONS", font=("SF Pro Display", 14, "bold"), text_color=self.colors["accent"]).grid(row=4, column=0, sticky="w", padx=10, pady=(5, 5))
        
        ctk.CTkLabel(t, text="Filename (Optional):").grid(row=5, column=0, sticky="w", padx=20, pady=5)
        self.output_entry = ctk.CTkEntry(t, placeholder_text="my_video", height=35)
        self.output_entry.grid(row=5, column=1, columnspan=2, sticky="ew", padx=20, pady=5)

        ctk.CTkLabel(t, text="Export Folder:").grid(row=6, column=0, sticky="w", padx=20, pady=5)
        self.export_dir_var = tk.StringVar()
        self.export_dir_entry = ctk.CTkEntry(t, textvariable=self.export_dir_var, placeholder_text="Default folder", height=35)
        self.export_dir_entry.grid(row=6, column=1, sticky="ew", padx=(20, 10), pady=5)
        ctk.CTkButton(t, text="📂", width=40, height=35, command=self.browse_export_dir, fg_color=self.colors["panel"], hover_color=self.colors["accent"], text_color=self.colors["text"]).grid(row=6, column=2, padx=(0, 20), pady=5)


    def init_video_tab(self):
        """Initializes the Video Settings tab components."""
        t = self.tab_video
        t.grid_columnconfigure((1, 3), weight=1)
        self._init_video_format_section(t)
        self._init_video_background_section(t)

    def _init_video_format_section(self, t):
        """Video format controls (Resolution, FPS, Codec)."""
        ctk.CTkLabel(t, text="FORMAT & LAYOUT", font=("SF Pro Display", 14, "bold"), text_color=self.colors["accent"]).grid(row=0, column=0, columnspan=4, sticky="w", padx=10, pady=(20, 10))
        
        ctk.CTkLabel(t, text="Width:").grid(row=1, column=0, padx=10, pady=10)
        self.width_entry = ctk.CTkEntry(t, width=80, height=35)
        self.width_entry.insert(0, "400")
        self.width_entry.grid(row=1, column=1, sticky="w", padx=10)
        self.width_entry.bind("<KeyRelease>", self.schedule_preview_update)

        ctk.CTkLabel(t, text="Height:").grid(row=1, column=2, padx=10, pady=10)
        self.height_entry = ctk.CTkEntry(t, width=80, height=35)
        self.height_entry.insert(0, "540")
        self.height_entry.grid(row=1, column=3, sticky="w", padx=10)
        self.height_entry.bind("<KeyRelease>", self.schedule_preview_update)

        ctk.CTkLabel(t, text="FPS:").grid(row=2, column=0, padx=10, pady=10)
        self.fps_entry = ctk.CTkEntry(t, width=80, height=35)
        self.fps_entry.insert(0, "60")
        self.fps_entry.grid(row=2, column=1, sticky="w", padx=10)
        self.fps_entry.bind("<KeyRelease>", self.schedule_preview_update)

        # Codec Logic
        ctk.CTkLabel(t, text="Codec:").grid(row=3, column=0, padx=10, pady=10)
        self.available_codecs = self.get_available_codecs()
        self.codec_var = ctk.CTkOptionMenu(t, values=self.available_codecs, command=self.on_codec_change, height=35, fg_color=self.colors["panel"], button_color=self.colors["accent"], button_hover_color=self.colors["accent"], text_color=self.colors["text"])
        self.codec_var.set(self.available_codecs[0] if self.available_codecs else "h264")
        self.codec_var.grid(row=3, column=1, sticky="w", padx=10)
        
        ctk.CTkLabel(t, text="Extension:").grid(row=3, column=2, padx=10, pady=10)
        self.ext_var = ctk.CTkOptionMenu(t, values=[".mov"], height=35, fg_color=self.colors["panel"], button_color=self.colors["accent"], button_hover_color=self.colors["accent"], text_color=self.colors["text"])
        self.ext_var.grid(row=3, column=3, sticky="w", padx=10)

    def _init_video_background_section(self, t):
        """Background settings components."""
        ctk.CTkFrame(t, height=2, fg_color=self.colors["border"]).grid(row=4, column=0, columnspan=4, sticky="ew", padx=10, pady=15)
        
        ctk.CTkLabel(t, text="BACKGROUND", font=("SF Pro Display", 14, "bold"), text_color=self.colors["accent"]).grid(row=5, column=0, columnspan=4, sticky="w", padx=10, pady=(5, 10))
        
        # bg_color_btn unused
        self.bg_color = ctk.CTkEntry(t, width=120, height=35)
        self.bg_color.insert(0, "#0f0f0f")
        self.bg_color.grid(row=6, column=1, sticky="w", padx=10)
        self.bg_color.bind("<KeyRelease>", self.schedule_preview_update)
        ctk.CTkLabel(t, text="BG Color (Hex):").grid(row=6, column=0, padx=10)
        
        # Color picker btn
        self.bg_picker_btn = ctk.CTkButton(t, text="", width=35, height=35, fg_color="#0f0f0f", border_width=1, 
                                            command=lambda: self.pick_color(self.bg_color, self.bg_picker_btn))
        self.bg_picker_btn.grid(row=6, column=2, padx=10, sticky="w")

        self.check_transparent = ctk.CTkCheckBox(t, text="Transparent Background", command=self.on_transparent_change, fg_color=self.colors["accent"], hover_color=self.colors["accent"])
        self.check_transparent.select()
        self.check_transparent.grid(row=7, column=1, columnspan=2, padx=10, pady=10, sticky="w")
        
        self.hwaccel_var = ctk.CTkCheckBox(t, text="Use Hardware Acceleration", fg_color=self.colors["accent"], hover_color=self.colors["accent"])
        self.hwaccel_var.select()
        self.hwaccel_var.grid(row=8, column=0, columnspan=2, padx=10, pady=5)

    def init_style_tab(self):
        """Initializes components of the Style & Colors tab."""
        t = self.tab_style
        
        self._init_style_global(t)
        self._init_style_roles(t)
        self._init_style_fonts(t)

    def _init_style_global(self, t):
        """Global style inputs."""
        top_frame = ctk.CTkFrame(t, fg_color="transparent")
        top_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(top_frame, text="Global Scale:").pack(side="left", padx=10)
        self.scale = ctk.CTkEntry(top_frame, width=60, height=35)
        self.scale.insert(0, "1")
        self.scale.pack(side="left", padx=5)
        self.scale.bind("<KeyRelease>", self.schedule_preview_update)

        ctk.CTkLabel(top_frame, text="Outline Width:").pack(side="left", padx=10)
        self.outline_width = ctk.CTkEntry(top_frame, width=60, height=35)
        self.outline_width.insert(0, "1")
        self.outline_width.pack(side="left", padx=5)
        self.outline_width.bind("<KeyRelease>", self.schedule_preview_update)

    def _init_style_roles(self, t):
        """Role-based styling inputs tabview."""
        self.role_tabs = ctk.CTkTabview(t, fg_color=self.colors["bg"], 
                                      text_color=self.colors["text"],
                                      segmented_button_fg_color=self.colors["panel"], 
                                      segmented_button_selected_color=self.colors["accent"],
                                      corner_radius=10, height=400)
        self.role_tabs.pack(fill="both", expand=True, padx=5, pady=5)
        
        roles = [
            ("owner", "Owner", "#ffd600"), 
            ("moderator", "Moderator", "#5e84f1"), 
            ("member", "Member", "#2ba640"), 
            ("normal", "Normal", "#ffffff")
        ]
        
        # Fields to create for each role
        layout_fields = [
            ("Author Size", "author_font_size", "13"),
            ("Msg Size", "message_font_size", "13"),
            ("Line Height", "line_height", "16"),
            ("Avatar Size", "avatar_size", "24"),
            ("Emoji Size", "emoji_size", "16"),
            ("Padding", "padding", "24"),
        ]

        for role_key, role_label, default_color in roles:
            self._create_role_tab(role_key, role_label, default_color, layout_fields)

    def _create_role_tab(self, role_key, role_label, default_color, layout_fields):
        """Helper to create a single role's config tab."""
        rt = self.role_tabs.add(role_label)
        rt.grid_columnconfigure((1, 3), weight=1)
        
        # Colors Section
        c_frame = ctk.CTkFrame(rt, fg_color="transparent")
        c_frame.pack(fill="x", padx=5, pady=5)
        c_frame.grid_columnconfigure((1,3), weight=1)
        
        ctk.CTkLabel(c_frame, text="Colors", font=("SF Pro Display", 14, "bold"), text_color=self.colors["accent"]).grid(row=0, column=0, sticky="w", padx=10, pady=5)
        
        # Helper for color input
        def add_color_input(parent, row, col, default, _):
             entry = ctk.CTkEntry(parent, width=80, height=35)
             entry.insert(0, default)
             entry.grid(row=row, column=col, padx=(10, 5), sticky="ew")
             
             btn = ctk.CTkButton(parent, text="", width=35, height=35, fg_color=default, border_width=1)
             btn.configure(command=lambda e=entry, b=btn: self.pick_color(e, b))
             btn.grid(row=row, column=col+1, padx=(0, 10), sticky="w")
             
             entry.bind("<KeyRelease>", self.schedule_preview_update)
             return entry

        ctk.CTkLabel(c_frame, text="Username Color:").grid(row=1, column=0, padx=10, sticky="w")
        u_entry = add_color_input(c_frame, 1, 1, default_color, f"{role_key}_username")
        u_attr = f"{role_key}_username_color"
        setattr(self, u_attr, u_entry)
        
        ctk.CTkLabel(c_frame, text="Message Color:").grid(row=1, column=3, padx=10, sticky="w")
        m_entry = add_color_input(c_frame, 1, 4, "#ffffff", f"{role_key}_message")
        m_attr = f"{role_key}_message_color"
        setattr(self, m_attr, m_entry)

        # Layout Section
        l_frame = ctk.CTkFrame(rt)
        l_frame.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkLabel(l_frame, text="Layout / Fonts", font=("Roboto", 14, "bold")).grid(row=0, column=0, columnspan=4, sticky="w", padx=10, pady=5)
        
        r, c = 1, 0
        for label, field_suffix, default_val in layout_fields:
            ctk.CTkLabel(l_frame, text=label+":").grid(row=r, column=c, padx=5, pady=5, sticky="e")
            l_entry = ctk.CTkEntry(l_frame, width=50, height=35)
            l_entry.insert(0, default_val)
            l_entry.grid(row=r, column=c+1, padx=5, pady=5, sticky="w")
            l_entry.bind("<KeyRelease>", self.schedule_preview_update)
            
            # Attribute: e.g. self.owner_author_font_size
            attr_name = f"{role_key}_{field_suffix}"
            setattr(self, attr_name, l_entry)
            
            c += 2
            if c > 4:
                c = 0
                r += 1

    def _init_style_fonts(self, t):
        """Global fonts selection."""
        f_frame = ctk.CTkFrame(t, fg_color="transparent")
        f_frame.pack(fill="x", padx=10, pady=10)
        f_frame.grid_columnconfigure(1, weight=1)
        
        # Get System Fonts
        try:
            self.system_fonts = sorted(list(tkinter.font.families()))
        except Exception:
            self.system_fonts = ["Arial", "Helvetica", "Times New Roman"]

        ctk.CTkLabel(f_frame, text="Author Font (All):").grid(row=0, column=0, padx=10, pady=5)
        self.author_font_var = tk.StringVar(value="")
        self.author_font_entry = ctk.CTkComboBox(f_frame, values=[""] + self.system_fonts, variable=self.author_font_var, height=35, command=lambda _: self.schedule_preview_update())
        self.author_font_entry.grid(row=0, column=1, sticky="ew", padx=10)
        ctk.CTkButton(f_frame, text="📂", width=40, height=35, command=self.browse_author_font, fg_color=self.colors["panel"], hover_color=self.colors["accent"], text_color=self.colors["text"]).grid(row=0, column=2, padx=10)
        self.author_font_entry.bind("<KeyRelease>", self.schedule_preview_update)

        ctk.CTkLabel(f_frame, text="Message Font (All):").grid(row=1, column=0, padx=10, pady=5)
        self.message_font_var = tk.StringVar(value="")
        self.message_font_entry = ctk.CTkComboBox(f_frame, values=[""] + self.system_fonts, variable=self.message_font_var, height=35, command=lambda _: self.schedule_preview_update())
        self.message_font_entry.grid(row=1, column=1, sticky="ew", padx=10)
        ctk.CTkButton(f_frame, text="📂", width=40, height=35, command=self.browse_message_font, fg_color=self.colors["panel"], hover_color=self.colors["accent"], text_color=self.colors["text"]).grid(row=1, column=2, padx=10)
        self.message_font_entry.bind("<KeyRelease>", self.schedule_preview_update)


    def init_advanced_tab(self):
        """Initializes the Advanced Settings tab."""
        t = self.tab_advanced
        t.grid_columnconfigure(0, weight=1)
        
        # EDL Section
        ctk.CTkLabel(t, text="EDL TIMELINE CUT", font=("SF Pro Display", 14, "bold"), text_color=self.colors["accent"]).pack(anchor="w", padx=10, pady=(20, 10))
        
        edl_frame = ctk.CTkFrame(t, fg_color="transparent")
        edl_frame.pack(fill="x", padx=10, pady=5)
        edl_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(edl_frame, text="EDL File:").grid(row=0, column=0, sticky="w")
        self.edl_path_var = tk.StringVar()
        self.edl_entry = ctk.CTkEntry(edl_frame, textvariable=self.edl_path_var, placeholder_text="Select .edl file", height=30)
        self.edl_entry.grid(row=0, column=1, sticky="ew", padx=10)
        ctk.CTkButton(edl_frame, text="📂", width=40, height=30, command=self.browse_edl, fg_color=self.colors["panel"], hover_color=self.colors["accent"], text_color=self.colors["text"]).grid(row=0, column=2)

        # Controls
        ctrl_frame = ctk.CTkFrame(t, fg_color="transparent")
        ctrl_frame.pack(fill="x", padx=10, pady=5)
        
        self.analyze_btn = ctk.CTkButton(ctrl_frame, text="Analyze & Load Clips", command=self.analyze_edl, height=30)
        self.analyze_btn.pack(side="left", padx=(0,10))
        
        self.use_edl_switch = ctk.CTkCheckBox(ctrl_frame, text="Filter by EDL", command=self.on_edl_toggle, fg_color=self.colors["accent"])
        self.use_edl_switch.pack(side="left")

        # Clip Select
        clip_frame = ctk.CTkFrame(t, fg_color="transparent")
        clip_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(clip_frame, text="Clip:").pack(side="left")
        self.edl_clip_var = ctk.CTkOptionMenu(clip_frame, values=["Load EDL first..."], command=lambda _: self.update_duration_display(), width=250, height=30, fg_color=self.colors["panel"], button_color=self.colors["accent"], text_color=self.colors["text"])
        self.edl_clip_var.pack(side="left", padx=10, fill="x", expand=True)

        self.edl_status = ctk.CTkLabel(t, text="", text_color=self.colors["text_dim"], font=("SF Pro Text", 11))
        self.edl_status.pack(anchor="w", padx=10, pady=(0,10))

        # Start/End Time
        ctk.CTkLabel(t, text="MANUAL TIMING", font=("SF Pro Display", 14, "bold"), text_color=self.colors["accent"]).pack(anchor="w", padx=10, pady=(10, 5))
        
        time_frame = ctk.CTkFrame(t, fg_color="transparent")
        time_frame.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(time_frame, text="Start (s):").pack(side="left", padx=10)
        self.start_time = ctk.CTkEntry(time_frame, width=60, height=35)
        self.start_time.insert(0, "0")
        self.start_time.pack(side="left")
        self.start_time.bind("<KeyRelease>", self.on_manual_timing_change)
        
        ctk.CTkLabel(time_frame, text="End (s):").pack(side="left", padx=10)
        self.end_time = ctk.CTkEntry(time_frame, width=60, height=35)
        self.end_time.insert(0, "0")
        self.end_time.pack(side="left")
        self.end_time.bind("<KeyRelease>", self.on_manual_timing_change)
        
        # Flags
        self.use_cache = ctk.CTkCheckBox(t, text="Cache Images to Disk", fg_color=self.colors["accent"], hover_color=self.colors["accent"])
        self.use_cache.pack(anchor="w", padx=20, pady=5)
        
        self.skip_avatars = ctk.CTkCheckBox(t, text="Skip Avatars", fg_color=self.colors["accent"], hover_color=self.colors["accent"])
        self.skip_avatars.pack(anchor="w", padx=20, pady=5)
        
        self.no_clip = ctk.CTkCheckBox(t, text="No Clip (Don't hide tops)", fg_color=self.colors["accent"], hover_color=self.colors["accent"])
        self.no_clip.pack(anchor="w", padx=20, pady=5)
        
        ctk.CTkButton(t, text="Clear Cache", command=self.clear_cache, width=120, height=35, fg_color=self.colors["panel"], hover_color=self.colors["error"], text_color=self.colors["text"]).pack(padx=20, pady=20, anchor="w")
        
        # Proxy
        proxy_frame = ctk.CTkFrame(t, fg_color="transparent")
        proxy_frame.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(proxy_frame, text="Proxy:").pack(side="left", padx=10)
        self.proxy_entry = ctk.CTkEntry(proxy_frame, height=35)
        self.proxy_entry.pack(side="left", fill="x", expand=True, padx=10)

    def init_actions(self):
        """Initializes action buttons (Render, Stop, Logs, Reveal)."""
        self.action_frame = ctk.CTkFrame(self.main_scroll, fg_color="transparent")
        self.action_frame.pack(pady=30, fill="x", padx=15)
        
        self.render_btn = ctk.CTkButton(self.action_frame, text="▶ START RENDER", command=self.start_render,
                                      fg_color=self.colors["success"], hover_color=self.colors["accent"], 
                                      text_color=("white", "black"), height=45, 
                                      font=("SF Pro Display", 15, "bold"), corner_radius=22)
        self.render_btn.pack(side="left", expand=True, fill="x", padx=(0, 10))
        
        self.stop_btn = ctk.CTkButton(self.action_frame, text="⏹ STOP", command=self.stop_render,
                                    fg_color=self.colors["error"], hover_color="#b91c1c", 
                                    text_color="white", height=45, corner_radius=22, state="disabled",
                                    width=60)
        self.stop_btn.pack(side="left")
        
        # Show Logs Button
        ctk.CTkButton(self.main_scroll, text="Show Logs", command=self.toggle_logs, fg_color="#444444").pack(pady=5)
        
        # Progress
        self.progress_bar = ctk.CTkProgressBar(self.main_scroll)
        self.progress_bar.pack(fill="x", padx=20, pady=5)
        self.progress_bar.set(0)
        self.progress_bar.pack_forget() # Hide
        
        self.progress_label = ctk.CTkLabel(self.main_scroll, text="Progress: 0%")
        self.progress_label.pack()
        self.progress_label.pack_forget()

        # Reveal
        self.reveal_btn = ctk.CTkButton(self.main_scroll, text="📂 Reveal Output", command=self.reveal_file)
        self.reveal_btn.pack(pady=10)
        self.reveal_btn.pack_forget()

    # --- Logic ---

    def on_codec_change(self, choice):
        """Updates UI options based on selected video codec."""
        # Update extensions
        if choice == "prores":
            self.ext_var.configure(values=[".mov"])
            self.ext_var.set(".mov")
        elif choice == "hevc":
             self.ext_var.configure(values=[".mov", ".mp4", ".mkv"])
             self.ext_var.set(".mov" if self.check_transparent.get() else ".mp4")
        elif choice == "h264":
             self.ext_var.configure(values=[".mp4", ".mov", ".mkv"])
             self.ext_var.set(".mp4")
        elif choice == "av1":
             self.ext_var.configure(values=[".mp4", ".webm", ".mkv"])
             self.ext_var.set(".mp4")
        elif choice == "vp9":
             self.ext_var.configure(values=[".webm", ".mkv"])
             self.ext_var.set(".webm")
        else:
             self.ext_var.configure(values=[".mp4", ".mkv", ".mov"])
             self.ext_var.set(".mp4")
        
        # HW Accel Visibility
        if self.supports_hw_accel(choice):
            self.hwaccel_var.grid()
        else:
            self.hwaccel_var.deselect()
            self.hwaccel_var.grid_remove()

        # Re-check transparency comp.
        if choice == "h264" and self.check_transparent.get():
             self.check_transparent.deselect() # H264 no alpha
             
             
        self.on_transparent_change() # Re-verify logic

    def on_transparent_change(self):
        """Toggles transparency options based on codec compatibility."""
        is_trans = self.check_transparent.get()
        codec = self.codec_var.get()
        
        # Hide/Show logic based on codec
        # If codec is h264, we force unchecked and hide/disable?
        # User requested: "dynamically show or hide transperent background option"
        
        supports_alpha = codec in ["prores", "hevc", "qtrle", "vp9", "png"] # AV1 alpha support in ffmpeg is complex/rare, assume no for safety unless known
        # Actually HEVC alpha is Apple only usually.
        # But we let user try if they want, except H264 which def no.
        
        if codec == "h264": supports_alpha = False
        
        if supports_alpha:
            self.check_transparent.configure(state="normal")
            if not self.check_transparent.winfo_viewable():
                self.check_transparent.grid() # Reveal
        else:
             self.check_transparent.deselect()
             self.check_transparent.configure(state="disabled")
             # Or hide? User asked show or hide.
             # self.check_transparent.grid_remove() # Logic in grid layout needs care if hidden.
             # Grid remove might shift things up.
             # Let's try disable + visual cue or grid_remove.
             # Grid remove is safer for "clean" UI.
             self.check_transparent.grid_remove()

        if codec == "h264" and is_trans:
            self.check_transparent.deselect()
            is_trans = False

        self.schedule_preview_update()

    def update_preview(self, event=None):
        """Manages the preview generation thread."""
        # pylint: disable=unused-argument
        self.update_cli_preview() # Ensure CLI is always synced with preview refresh
        # Collect arguments
        try:
            args = PreviewArgs()
            
            def safe_int(val, default=0):
                try:
                    return int(val)
                except ValueError:
                    return default
            def safe_float(val, default=1.0):
                try:
                    return float(val)
                except ValueError:
                    return default

            args.width = safe_int(self.width_entry.get(), 400)
            args.height = safe_int(self.height_entry.get(), 540)
            args.chat_scale = safe_float(self.scale.get(), 1.0)
            args.background = self.bg_color.get()
            args.outline_color = "#000000"
            args.outline_width = safe_int(self.outline_width.get(), 1)
            args.transparent = bool(self.check_transparent.get())
            
            # Common defaults for fallbacks (using Normal role)
            args.author_font_size = safe_int(self.normal_author_font_size.get(), 13)
            args.message_font_size = safe_int(self.normal_message_font_size.get(), 13)
            args.line_height = safe_int(self.normal_line_height.get(), 16)
            args.avatar_size = safe_int(self.normal_avatar_size.get(), 24)
            args.emoji_size = safe_int(self.normal_emoji_size.get(), 16)
            args.padding = safe_int(self.normal_padding.get(), 24)

            # Colors
            args.color_owner = self.owner_username_color.get()
            args.color_moderator = self.moderator_username_color.get()
            args.color_member = self.member_username_color.get()
            args.color_normal = self.normal_username_color.get()
            
            args.msg_owner = self.owner_message_color.get()
            args.msg_moderator = self.moderator_message_color.get()
            args.msg_member = self.member_message_color.get()
            args.message_color = self.normal_message_color.get()

            # Fonts
            args.author_font = self.author_font_var.get()
            args.message_font = self.message_font_var.get()
            
            # Flags
            args.skip_avatars = False
            args.skip_emojis = False
            args.use_cache = True 
            args.no_clip = True

            args.no_clip = True

            # Determine effective dark mode for preview generation
            # If System, check real system theme
            mode = ctk.get_appearance_mode()
            if mode == "System":
                 args.is_dark_mode = (self.get_system_theme() == "Dark")
            else:
                 args.is_dark_mode = (mode == "Dark")
            
            # Dynamically attach all per-role attrs
            
            # Dynamically attach all per-role attrs
            roles = ["owner", "moderator", "member", "normal"]
            attrs = ["author_font_size", "message_font_size", "line_height", "avatar_size", "emoji_size", "padding"]
            for role in roles:
                for attr in attrs:
                    # Arg: owner_author_font_size
                    # GUI: owner_author_font_size
                    key = f"{role}_{attr}"
                    setattr(args, key, safe_int(getattr(self, key).get(), 0))

            # Threaded Execution
            self.last_preview_args = args
            if not self.is_preview_running:
                threading.Thread(target=self.preview_worker).start()
                
        except Exception as e:
            print(f"Preview Setup Error: {e}")

    def preview_worker(self):
        """Background thread for generating preview frames."""
        # pylint: disable=too-many-locals
        with self.preview_lock:
            self.is_preview_running = True
            try:
                args = self.last_preview_args
                # Generate
                current_renderer = getattr(self, 'preview_renderer', None)
                img, self.preview_renderer = yt_chat_to_video.get_preview_image(args, DUMMY_MESSAGES, renderer=current_renderer)
                
                # Checkboard background
                if args.transparent:
                     # Check Mode
                     if getattr(args, 'is_dark_mode', True):
                         c1, c2 = (30, 30, 30, 255), (50, 50, 50, 255)
                     else:
                         c1, c2 = (200, 200, 200, 255), (150, 150, 150, 255)
                         
                     bg = Image.new("RGBA", (args.width, args.height), c1)
                     checker = Image.new("RGBA", (args.width, args.height), c2)
                     mask = Image.new("L", (args.width, args.height), 0)
                     draw = ImageDraw.Draw(mask)
                     step = 20
                     for y in range(0, args.height, step):
                         for x in range(0, args.width, step):
                             if (x//step + y//step) % 2 == 0:
                                 draw.rectangle((x, y, x+step, y+step), fill=255)
                     bg.paste(checker, (0,0), mask=mask)
                     
                     # Ensure img is RGBA
                     if img.mode != 'RGBA':
                         img = img.convert('RGBA')
                     
                     bg.alpha_composite(img)
                     img = bg

                # Resize
                display_w, display_h = 400, 540
                aspect = args.width / args.height
                if aspect > display_w / display_h:
                    target_w = display_w
                    target_h = int(display_w / aspect)
                else:
                    target_h = display_h
                    target_w = int(display_h * aspect)
                
                tk_image = ctk.CTkImage(light_image=img, dark_image=img, size=(target_w, target_h))
                self.preview_queue.put(tk_image)
                
            except Exception as e:
                print(f"Preview Worker Error: {e}")
            
            self.is_preview_running = False

    def schedule_preview_update(self, event=None):
        """Debounces preview updates."""
        # pylint: disable=unused-argument
        self.update_cli_preview() # Update text immediately
        if hasattr(self, '_preview_job'):
            try:
                self.after_cancel(self._preview_job)
            except ValueError:
                pass
        self._preview_job = self.after(500, self.update_preview)

    def update_cli_preview(self):
        """Generates the command line preview string."""
        # pylint: disable=too-many-locals, too-many-branches, too-many-statements
        self.ignore_cli_change = True # Loop prevention
        try:
            cmd = ["python3", "yt-chat-to-video.py"]
            
            # Input
            url = self.url_entry.get()
            local = self.file_path_var.get()
            if local:
                cmd.append(f'"{local}"')
            elif url:
                cmd.append(f'"{url}"')
            else:
                cmd.append("[INPUT]")
            
            # EDL
            if self.use_edl_switch.get():
                e_path = self.edl_path_var.get()
                e_clip = self.edl_clip_var.get()
                if e_path and e_clip:
                    cmd.extend(["--edl", f'"{e_path}"', "--clip-name", f'"{e_clip}"'])
            
            # Output
            out = self.output_entry.get()
            if out:
                cmd.extend(["-o", f'"{out}.{self.ext_var.get().replace(".", "")}"'])
            
            # Format
            cmd.extend(["-w", self.width_entry.get(), "-h", self.height_entry.get()])
            cmd.extend(["-r", self.fps_entry.get()])
            cmd.extend(["--codec", self.codec_var.get()])
            cmd.extend(["-s", self.scale.get()])
            if self.check_transparent.get():
                cmd.append("--transparent")
            cmd.extend(["--outline-width", self.outline_width.get()])
            
            # BG
            if not self.check_transparent.get():
                cmd.extend(["-b", f'"{self.bg_color.get()}"'])
                
            # Roles
            roles = ["owner", "moderator", "member", "normal"]
            attrs = ["username_color", "message_color", "author_font_size", "message_font_size", 
                     "line_height", "avatar_size", "emoji_size", "padding"]
            
            for role in roles:
                for attr in attrs:
                    val = getattr(self, f"{role}_{attr}").get()
                    
                    if attr == "username_color":
                        cmd.extend([f"--color-{role}", f'"{val}"'])
                    elif attr == "message_color":
                        cmd.extend([f"--msg-{role}", f'"{val}"'])
                    else:
                        cli_flag = f"--{role}-{attr.replace('_', '-')}"
                        cmd.extend([cli_flag, str(val)])
                        
            # Fonts
            af = self.author_font_var.get()
            if af:
                cmd.extend(["--author-font", f'"{af}"'])
            mf = self.message_font_var.get()
            if mf:
                cmd.extend(["--message-font", f'"{mf}"'])
            
            cmd_str = " ".join(cmd)
            
            if hasattr(self, 'cli_box'):
                self.cli_box.delete("1.0", "end")
                self.cli_box.insert("end", cmd_str)
        except Exception: # pylint: disable=broad-exception-caught
            pass
        finally:
            self.ignore_cli_change = False

    def check_preview_queue(self):
        """Checks for new preview images in the thread-safe queue."""
        try:
            while True:
                tk_image = self.preview_queue.get_nowait()
                self.tk_image = tk_image # Store reference to prevent garbage collection
                self.preview_label.configure(image=self.tk_image, text="") # Remove placeholder text
        except queue.Empty:
            pass
        self.after(100, self.check_preview_queue) # Check again after 100ms

    def toggle_logs(self):
        """Toggles the visibility of the debug log window."""
        if self.log_window is None or not self.log_window.winfo_exists():
            self.log_window = ctk.CTkToplevel(self)
            self.log_window.title("Logs")
            self.log_window.geometry("500x300")
            self.log_box = ctk.CTkTextbox(self.log_window)
            self.log_box.pack(fill="both", expand=True)
        else:
            self.log_window.focus()

    def log(self, msg):
        """Logs a message to stdout and the log window."""
        print(msg) # Print to stdout for debug
        if self.log_window and self.log_window.winfo_exists():
            self.log_box.insert("end", str(msg) + "\n")
            self.log_box.see("end")

    # Reuse existing logic for settings load/save/start render with minor updates for new fields
    def get_settings_file(self):
        """Returns the path to the settings JSON file."""
        home = os.path.expanduser("~")
        config_dir = os.path.join(home, ".yt-chat-renderer")
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)
        return os.path.join(config_dir, "settings.json")

    # Load/Save need loop update
    # Load/Save
    def load_settings(self):
        """Loads settings from the JSON configuration file."""
        try:
            path = self.get_settings_file()
            if not os.path.exists(path):
                return
            with open(path, "r", encoding='utf-8') as f:
                settings = json.load(f)
            
            self._load_basic_settings(settings)
            self._load_appearance_settings(settings)
            self._load_edl_settings(settings)
            self._load_role_settings(settings)

            # Trigger initial updates
            self.on_codec_change(self.codec_var.get())
            self.on_edl_toggle()

        except Exception as e: # pylint: disable=broad-exception-caught
            print(f"Load settings error: {e}")

    def _set_entry(self, entry, key, settings):
        """Helper to set entry value from settings dict."""
        if key in settings:
            entry.delete(0, "end")
            entry.insert(0, str(settings[key]))

    def _set_check(self, chk, key, settings):
        """Helper to set checkbox state from settings dict."""
        if key in settings:
            if settings[key]:
                 chk.select()
            else:
                 chk.deselect()

    def _load_basic_settings(self, settings):
        """Loads core validation input/output settings."""
        self._set_entry(self.url_entry, "url", settings)
        if "file" in settings:
            self.file_path_var.set(settings["file"])
        self._set_entry(self.output_entry, "output", settings)
        if "export_dir" in settings:
            self.export_dir_var.set(settings["export_dir"])
        
        self._set_entry(self.width_entry, "width", settings)
        self._set_entry(self.height_entry, "height", settings)
        self._set_entry(self.fps_entry, "fps", settings)
        if "codec" in settings:
            self.codec_var.set(settings["codec"])
        self._set_entry(self.scale, "scale", settings)
        self._set_entry(self.outline_width, "outline_width", settings)
        
        self._set_check(self.check_transparent, "trans", settings)
        self._set_entry(self.bg_color, "bg", settings)

    def _load_appearance_settings(self, settings):
        """Loads theme and appearance settings."""
        if "theme" in settings:
            self.appearance_mode_menu.set(settings["theme"])
            ctk.set_appearance_mode(settings["theme"])

    def _load_edl_settings(self, settings):
        """Loads EDL-specific settings."""
        if "edl_path" in settings:
            self.edl_path_var.set(settings["edl_path"])
        if "edl_active" in settings:
            self._set_check(self.use_edl_switch, "edl_active", settings)

    def _load_role_settings(self, settings):
        """Loads role-based style settings."""
        roles = ["owner", "moderator", "member", "normal"]
        attrs_map = {
            "username_color": {"owner": "c_owner", "moderator": "c_mod", "member": "c_member", "normal": "c_normal"},
            "message_color": {"owner": "m_owner", "moderator": "m_mod", "member": "m_member", "normal": "m_normal"},
            "author_font_size": "afs",
            "message_font_size": "mfs",
            "line_height": "lh",
            "avatar_size": "as",
            "emoji_size": "es",
            "padding": "pad"
        }
        
        for role in roles:
            for attr, legacy_key in attrs_map.items():
                gui_attr = f"{role}_{attr}"
                if not hasattr(self, gui_attr):
                    continue
                
                entry = getattr(self, gui_attr)
                
                if gui_attr in settings:
                    self._set_entry(entry, gui_attr, settings)
                else:
                    if isinstance(legacy_key, dict):
                        old_key = legacy_key.get(role)
                        if old_key and old_key in settings:
                            self._set_entry(entry, old_key, settings)
                    elif isinstance(legacy_key, str):
                        if legacy_key in settings:
                            self._set_entry(entry, legacy_key, settings)

    def save_settings(self):
        """Persists current UI state to settings JSON."""
        try:
            settings = {
                "url": self.url_entry.get(),
                "file": self.file_path_var.get(),
                "output": self.output_entry.get(),
                "export_dir": self.export_dir_var.get(),
                "width": self.width_entry.get(),
                "height": self.height_entry.get(),
                "fps": self.fps_entry.get(),
                "codec": self.codec_var.get(),
                "scale": self.scale.get(),
                "outline_width": self.outline_width.get(),
                "trans": bool(self.check_transparent.get()),
                "bg": self.bg_color.get(),
                "theme": self.appearance_mode_menu.get(),
                "edl_path": self.edl_path_var.get(),
                "edl_active": bool(self.use_edl_switch.get())
            }
            
            # Save Roles
            roles = ["owner", "moderator", "member", "normal"]
            attrs = ["username_color", "message_color", "author_font_size", "message_font_size", 
                     "line_height", "avatar_size", "emoji_size", "padding"]
            
            for role in roles:
                for attr in attrs:
                    key = f"{role}_{attr}"
                    if hasattr(self, key):
                        settings[key] = getattr(self, key).get()

            with open(self.get_settings_file(), "w", encoding='utf-8') as f:
                json.dump(settings, f)
        except Exception: # pylint: disable=broad-exception-caught
            pass

    def browse_edl(self):
        """Open file dialog for EDL file selection."""
        path = tkinter.filedialog.askopenfilename(filetypes=[("EDL Files", "*.edl"), ("All Files", "*.*")])
        if path:
            self.edl_path_var.set(path)
            self.use_edl_switch.select()
            self.on_edl_toggle()
            self.analyze_edl()

    def on_manual_timing_change(self, _=None):
        """Updates duration display on manual time input change."""
        self.update_duration_display()
        self.schedule_preview_update()

    def on_edl_toggle(self):
        """Toggles manual timing inputs based on EDL switch state."""
        # Enforce UI state
        if self.use_edl_switch.get():
             self.start_time.configure(state="disabled", fg_color=self.colors["panel"])
             self.end_time.configure(state="disabled", fg_color=self.colors["panel"])
        else:
             self.start_time.configure(state="normal", fg_color=["#F9F9FA", "#343638"]) # Default ctk entry colors
             self.end_time.configure(state="normal", fg_color=["#F9F9FA", "#343638"])
        self.update_duration_display()
        self.schedule_preview_update()

    def update_duration_display(self):
        """Calculates and updates the estimated video duration label."""
        duration = 0
        show_label = False
        
        if self.use_edl_switch.get():
            # Calculate from EDL segments
            path = self.edl_path_var.get()
            clip = self.edl_clip_var.get()
            if path and clip and os.path.exists(path):
                show_label = True
                # Use backend parser
                try:
                    segments = yt_chat_to_video.EDLParser.parse_file(path, clip)
                    duration = sum(e-s for s,e in segments)
                except Exception: # pylint: disable=broad-exception-caught
                    duration = 0
            else:
                 show_label = False
        else:
            # Manual diff - User requested to ONLY show when EDL is loaded.
            # So we force show_label = False for manual mode.
            show_label = False
            
        if show_label:
            self.duration_label.pack(side="right", padx=15)
            # Format MM:SS
            m = int(duration // 60)
            s = int(duration % 60)
            self.duration_label.configure(text=f"Est. Duration: {m:02d}:{s:02d}")
        else:
            self.duration_label.pack_forget()

    def analyze_edl(self):
        """Parses the selected EDL file and populates the clip dropdown."""
        path = self.edl_path_var.get()
        if not os.path.exists(path):
            return
        
        try:
             # Basic Parse to find unique clip names
             clips = set()
             with open(path, 'r', encoding='utf-8') as f:
                 for line in f:
                     if "FROM CLIP NAME:" in line:
                         name = line.split(':', 1)[1].strip()
                         clips.add(name)
             
             if clips:
                 sorted_clips = sorted(list(clips))
                 self.edl_clip_var.configure(values=sorted_clips)
                 
                 # Logic: "Auto-detect most frequently used"
                 counts = {}
                 with open(path, 'r', encoding='utf-8') as f:
                      for line in f:
                          if "FROM CLIP NAME:" in line:
                              name = line.split(':', 1)[1].strip()
                              counts[name] = counts.get(name, 0) + 1
                 most_used = max(counts, key=counts.get)
                 self.edl_clip_var.set(most_used)
                 self.edl_status.configure(text=f"Auto-selected '{most_used}' ({counts[most_used]} cuts).")
                 
             else:
                 self.edl_status.configure(text="No clip names found in EDL comments.")
                 
             self.update_duration_display()
                 
        except Exception as e: # pylint: disable=broad-exception-caught
            self.edl_status.configure(text=f"Error reading EDL: {e}")

    def start_render(self):
        """Builds and executes the CLI command for rendering."""
        self.save_settings()
        self.render_btn.configure(state="disabled", text="Rendering...")
        self.stop_btn.configure(state="normal")
        self.progress_bar.pack(fill="x", padx=20, pady=5)
        self.progress_label.pack()
        
        # Build Command
        script_path = os.path.join(os.path.dirname(__file__), "yt-chat-to-video.py")
        target = self.file_path_var.get() or self.url_entry.get()
        if not target: 
             self.log("Error: No Input Source")
             self.finish_render()
             return
        
        cmd = [sys.executable, script_path, target]
        
        # Dimensions
        cmd.extend(self._build_dimension_args())
        
        # Style (Per Role)
        cmd.extend(self._build_style_args())

        # Global overrides
        self._add_global_args(cmd)
        
        # EDL
        self._add_edl_args(cmd)

        # Video
        self._add_video_args(cmd)
        
        # Output
        self._add_output_args(cmd)
        
        # Flags
        self._add_flags(cmd)
        
        if self.proxy_entry.get():
             cmd.extend(["--proxy", self.proxy_entry.get()])

        threading.Thread(target=self.run_process, args=(cmd,)).start()

    def _safe_val(self, entry, default):
        v = entry.get()
        return v if v.strip() else str(default)

    def _build_dimension_args(self):
        cmd = []
        cmd.extend(["--width", self._safe_val(self.width_entry, 400)])
        cmd.extend(["--height", self._safe_val(self.height_entry, 540)])
        cmd.extend(["--frame-rate", self._safe_val(self.fps_entry, 60)])
        if float(self._safe_val(self.start_time, 0)) > 0:
             cmd.extend(["--from", self._safe_val(self.start_time, 0)])
        if float(self._safe_val(self.end_time, 0)) > 0:
             cmd.extend(["--to", self._safe_val(self.end_time, 0)])
        return cmd

    def _build_style_args(self):
        cmd = []
        roles = ["owner", "moderator", "member", "normal"]
        
        # Colors Legacy Mapping
        cmd.extend(["--color-owner", self.owner_username_color.get()])
        cmd.extend(["--color-moderator", self.moderator_username_color.get()])
        cmd.extend(["--color-member", self.member_username_color.get()])
        cmd.extend(["--color-normal", self.normal_username_color.get()])
        
        cmd.extend(["--msg-owner", self.owner_message_color.get()])
        cmd.extend(["--msg-moderator", self.moderator_message_color.get()])
        cmd.extend(["--msg-member", self.member_message_color.get()])
        cmd.extend(["--message-color", self.normal_message_color.get()])
        
        # Extended Layout Attributes
        attrs = ["author_font_size", "message_font_size", "line_height", "avatar_size", "emoji_size", "padding"]
        for role in roles:
            for attr in attrs:
                cli_arg = f"--{role}-{attr.replace('_', '-')}"
                gui_attr = f"{role}_{attr}"
                val = self._safe_val(getattr(self, gui_attr), 0)
                cmd.extend([cli_arg, val])
        return cmd

    def _add_global_args(self, cmd):
        cmd.extend(["--scale", self._safe_val(self.scale, 1)])
        cmd.extend(["--outline-width", self._safe_val(self.outline_width, 1)])
        
        if self.author_font_var.get():
             cmd.extend(["--author-font", self.author_font_var.get()])
        if self.message_font_var.get():
             cmd.extend(["--message-font", self.message_font_var.get()])

    def _add_edl_args(self, cmd):
        if self.use_edl_switch.get():
            e_path = self.edl_path_var.get()
            e_clip = self.edl_clip_var.get()
            if e_path and e_clip:
                cmd.extend(["--edl", e_path, "--clip-name", e_clip])

    def _add_video_args(self, cmd):
        cmd.extend(["--codec", self.codec_var.get()])
        if self.check_transparent.get():
             cmd.append("--transparent")
        cmd.extend(["--background", self.bg_color.get()])
        if self.hwaccel_var.get():
             cmd.append("--hwaccel")

    def _add_output_args(self, cmd):
        out = self.output_entry.get()
        export = self.export_dir_var.get()
        ext = self.ext_var.get()
        
        if out:
             if not any(out.lower().endswith(x) for x in ['.mov', '.mp4', '.mkv', '.webm', '.avi']):
                 out += ext
        
        if out and export: 
             if not os.path.isabs(out):
                  out = os.path.join(export, out)
        elif export: 
             out = os.path.join(export, "output" + ext)
             
        if out:
             cmd.extend(["--output", out])

    def _add_flags(self, cmd):
        if self.use_cache.get():
             cmd.append("--use-cache")
        if self.skip_avatars.get():
             cmd.append("--skip-avatars")
        if self.no_clip.get():
             cmd.append("--no-clip")

    def run_process(self, cmd):
        """Runs the FFmpeg process in a separate thread/subprocess."""
        # pylint: disable=consider-using-with
        self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, universal_newlines=True)
        
        for line in self.process.stdout:
            line = line.strip()
            if not line:
                continue
            
            if "PROGRESS:" in line:
                 try:
                     # e.g. PROGRESS:25
                     val = line.split(":")[1]
                     p = int(val)
                     self.after(0, lambda v=p: self.progress_bar.set(v/100))
                     self.after(0, lambda v=p: self.progress_label.configure(text=f"Progress: {v}%"))
                 except ValueError:
                     pass
            elif "OUTPUT_FILE:" in line:
                 self.last_output_file = line.split(":", 1)[1].strip()
            else:
                self.after(0, lambda msg=line: self.log(msg))
        
        self.process.wait()
        
        # Schedule finish_render on main thread
        self.after(0, self.finish_render)

    def finish_render(self):
        """Resets UI state after rendering completes."""
        self.render_btn.configure(state="normal", text="START RENDER")
        self.stop_btn.configure(state="disabled")
        if hasattr(self, 'last_output_file') and self.last_output_file:
             self.reveal_btn.configure(text=f"📂 Reveal: {os.path.basename(self.last_output_file)}")
             self.reveal_btn.pack()

    def browse_file(self):
        """Open file dialog for local JSON source."""
        f = tk.filedialog.askopenfilename()
        if f:
            self.file_path_var.set(f)
    def browse_export_dir(self):
        """Open directory dialog for export folder."""
        d = tk.filedialog.askdirectory()
        if d:
            self.export_dir_var.set(d)
    def browse_author_font(self):
        """Open file dialog for author custom font."""
        f = tk.filedialog.askopenfilename()
        if f:
            self.author_font_var.set(f)
    def browse_message_font(self):
        """Open file dialog for message custom font."""
        f = tk.filedialog.askopenfilename()
        if f:
            self.message_font_var.set(f)
    def pick_color(self, entry, btn=None):
        """Open color picker dialog and update entry/button."""
        current = entry.get()
        color = tkinter.colorchooser.askcolor(initialcolor=current)
        if color and color[1]:
            entry.delete(0, "end")
            entry.insert(0, color[1])
            if btn:
                btn.configure(fg_color=color[1])
            self.schedule_preview_update()

    def stop_render(self):
        """Terminates the running backend process."""
        if self.process:
             self.process.terminate()
             self.log("Stopping render...")

    def reveal_file(self):
        """Reveals the output file in the system file manager."""
        if not hasattr(self, 'last_output_file') or not self.last_output_file:
            return
        f = self.last_output_file
        if not os.path.exists(f):
            return
        
        self.log(f"Revealing: {f}")
        try:
            if platform.system() == "Windows":
                 subprocess.run(["explorer", "/select,", os.path.normpath(f)], check=False)
            elif platform.system() == "Darwin":
                 subprocess.run(["open", "-R", f], check=False)
            else:
                 subprocess.run(["xdg-open", os.path.dirname(f)], check=False)
        except Exception as e: # pylint: disable=broad-exception-caught
            self.log(f"Error revealing: {e}")

    def clear_cache(self):
        """Clears the local cache directory."""
        cache = "yt-chat-to-video_cache"
        if os.path.exists(cache):
            shutil.rmtree(cache)
            self.log("Cache cleared.")
        else:
            self.log("Cache already empty.")

if __name__ == "__main__":
    app = ChatRendererGUI()
    app.mainloop()
