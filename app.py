import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image, UnidentifiedImageError

APP_NAME = "Music Video Tool"
APP_VERSION = "2.1"
BG = "#323339"
PANEL = "#292b30"
BTN = "#282b30"
BTN_HOVER = "#3a3d44"
ACCENT = "#287e29"
ACCENT_HOVER = "#1f5f20"
DANGER = "#8a2d2d"
DANGER_HOVER = "#6f2222"
TEXT = "#e6e6e6"
MUTED = "#b3b3b3"
GOOD = "#70c970"
WARN = "#e2b75b"
AUDIO_EXTS = {".flac", ".mp3", ".wav", ".m4a", ".aac", ".ogg", ".opus", ".wma"}
RESOLUTIONS = {
    "Original image size": None,
    "YouTube 1080p (1920×1080)": (1920, 1080),
    "YouTube 1440p (2560×1440)": (2560, 1440),
    "YouTube 4K (3840×2160)": (3840, 2160),
    "Square (1080×1080)": (1080, 1080),
}
FIT_MODES = ["Fit with black bars", "Crop to fill", "Stretch"]
OVERWRITE_MODES = ["Skip existing videos", "Overwrite existing videos"]


def app_dir():
    return Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent


APP_DIR = app_dir()
DATA_DIR = Path(os.getenv("APPDATA") or Path.home()) / APP_NAME
DATA_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_PATH = DATA_DIR / "config.json"
FFMPEG_PATH = APP_DIR / "ffmpeg.exe"


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        self.title(f"{APP_NAME} {APP_VERSION}")
        self.geometry("820x760")
        self.minsize(760, 680)
        self.configure(fg_color=BG)

        self.input_folder = ""
        self.output_folder = ""
        self.cover_path = ""
        self.preview_image = None
        self.cancel_event = threading.Event()
        self.events = queue.Queue()
        self.process = None
        self.exporting = False

        self.recursive_var = ctk.BooleanVar(value=False)
        self.resolution_var = ctk.StringVar(value="YouTube 1080p (1920×1080)")
        self.fit_var = ctk.StringVar(value="Fit with black bars")
        self.overwrite_var = ctk.StringVar(value="Skip existing videos")

        self.build_ui()
        self.load_config()
        self.refresh_paths()
        self.update_ffmpeg_status()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(100, self.drain_events)

    def build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        outer = ctk.CTkFrame(self, fg_color=BG)
        outer.grid(row=0, column=0, sticky="nsew", padx=20, pady=18)
        outer.grid_columnconfigure(0, weight=1)
        outer.grid_rowconfigure(5, weight=1)

        title = ctk.CTkFrame(outer, fg_color="transparent")
        title.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        title.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(title, text=APP_NAME, text_color=TEXT, font=("Segoe UI Semibold", 24)).grid(row=0, column=0, sticky="w")
        self.ffmpeg_status = ctk.CTkLabel(title, text="FFmpeg: checking...", text_color=MUTED, font=("Segoe UI", 12))
        self.ffmpeg_status.grid(row=0, column=1, sticky="e")

        source = ctk.CTkFrame(outer, fg_color=PANEL, corner_radius=10)
        source.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        source.grid_columnconfigure(1, weight=1)
        self.input_button, self.input_label = self.add_picker(source, 0, "Select Input Folder", self.select_input)
        self.output_button, self.output_label = self.add_picker(source, 1, "Select Output Folder", self.select_output)
        self.image_button, self.image_label = self.add_picker(source, 2, "Select Cover Image", self.select_image, bottom=True)

        middle = ctk.CTkFrame(outer, fg_color="transparent")
        middle.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        middle.grid_columnconfigure(1, weight=1)

        preview = ctk.CTkFrame(middle, fg_color=PANEL, corner_radius=10, width=260, height=250)
        preview.grid(row=0, column=0, sticky="nsw", padx=(0, 10))
        preview.grid_propagate(False)
        preview.grid_columnconfigure(0, weight=1)
        preview.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(preview, text="COVER PREVIEW", text_color=MUTED, font=("Segoe UI Semibold", 11)).grid(row=0, column=0, pady=(12, 4))
        self.image_preview = ctk.CTkLabel(preview, text="No image selected", text_color=MUTED, width=220, height=200)
        self.image_preview.grid(row=1, column=0, padx=15, pady=(0, 15))

        options = ctk.CTkFrame(middle, fg_color=PANEL, corner_radius=10)
        options.grid(row=0, column=1, sticky="nsew")
        options.grid_columnconfigure(1, weight=1)
        self.resolution_menu = self.add_option(options, 0, "Resolution", list(RESOLUTIONS), self.resolution_var)
        self.fit_menu = self.add_option(options, 1, "Image handling", FIT_MODES, self.fit_var)
        self.overwrite_menu = self.add_option(options, 2, "Existing files", OVERWRITE_MODES, self.overwrite_var)
        self.recursive_check = ctk.CTkCheckBox(options, text="Include audio files inside subfolders", variable=self.recursive_var, fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color=TEXT)
        self.recursive_check.grid(row=3, column=0, columnspan=2, padx=14, pady=(10, 14), sticky="w")

        controls = ctk.CTkFrame(outer, fg_color="transparent")
        controls.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        controls.grid_columnconfigure(0, weight=1)
        self.generate_button = ctk.CTkButton(controls, text="GENERATE VIDEOS", command=self.start_export, fg_color=ACCENT, hover_color=ACCENT_HOVER, height=44, font=("Arial Black", 15))
        self.generate_button.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.cancel_button = ctk.CTkButton(controls, text="CANCEL", command=self.cancel_export, fg_color=DANGER, hover_color=DANGER_HOVER, width=120, height=44, state="disabled")
        self.cancel_button.grid(row=0, column=1, padx=(0, 8))
        self.open_output_button = ctk.CTkButton(controls, text="OPEN OUTPUT", command=self.open_output, fg_color=BTN, hover_color=BTN_HOVER, width=130, height=44)
        self.open_output_button.grid(row=0, column=2)

        progress = ctk.CTkFrame(outer, fg_color=PANEL, corner_radius=10)
        progress.grid(row=4, column=0, sticky="ew", pady=(0, 10))
        progress.grid_columnconfigure(0, weight=1)
        self.current_label = ctk.CTkLabel(progress, text="Ready", text_color=TEXT, anchor="w")
        self.current_label.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 4))
        self.progress_bar = ctk.CTkProgressBar(progress, progress_color=ACCENT, fg_color=BTN)
        self.progress_bar.grid(row=1, column=0, sticky="ew", padx=14, pady=5)
        self.progress_bar.set(0)
        self.progress_count = ctk.CTkLabel(progress, text="0 / 0", text_color=MUTED, anchor="e")
        self.progress_count.grid(row=2, column=0, sticky="e", padx=14, pady=(2, 10))

        log = ctk.CTkFrame(outer, fg_color=PANEL, corner_radius=10)
        log.grid(row=5, column=0, sticky="nsew")
        log.grid_columnconfigure(0, weight=1)
        log.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(log, text="ACTIVITY LOG", text_color=MUTED, font=("Segoe UI Semibold", 11)).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 4))
        self.log_box = ctk.CTkTextbox(log, fg_color="#222429", text_color=TEXT, wrap="word", font=("Consolas", 11))
        self.log_box.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.log_box.configure(state="disabled")

    def add_picker(self, parent, row, text, command, bottom=False):
        button = ctk.CTkButton(parent, text=text, command=command, fg_color=BTN, hover_color=BTN_HOVER, width=180)
        pady = (6, 12) if bottom else ((12, 6) if row == 0 else 6)
        button.grid(row=row, column=0, padx=12, pady=pady, sticky="w")
        label = ctk.CTkLabel(parent, text="Not selected", text_color=MUTED, anchor="w", justify="left", wraplength=510)
        label.grid(row=row, column=1, padx=(0, 12), pady=pady, sticky="ew")
        return button, label

    def add_option(self, parent, row, title, values, variable):
        ctk.CTkLabel(parent, text=title, text_color=TEXT).grid(row=row, column=0, padx=14, pady=(14, 7) if row == 0 else 7, sticky="w")
        menu = ctk.CTkOptionMenu(parent, values=values, variable=variable, fg_color=BTN, button_color=BTN, button_hover_color=BTN_HOVER, dropdown_fg_color=BTN)
        menu.grid(row=row, column=1, padx=14, pady=(14, 7) if row == 0 else 7, sticky="ew")
        return menu

    def load_config(self):
        if not CONFIG_PATH.exists():
            return
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            self.input_folder = data.get("input_folder", "")
            self.output_folder = data.get("output_folder", "")
            self.cover_path = data.get("cover_path", "")
            self.recursive_var.set(bool(data.get("recursive", False)))
            if data.get("resolution") in RESOLUTIONS:
                self.resolution_var.set(data["resolution"])
            if data.get("fit_mode") in FIT_MODES:
                self.fit_var.set(data["fit_mode"])
            if data.get("overwrite_mode") in OVERWRITE_MODES:
                self.overwrite_var.set(data["overwrite_mode"])
        except Exception as exc:
            self.append_log(f"Could not load config: {exc}")

    def save_config(self):
        data = {
            "input_folder": self.input_folder,
            "output_folder": self.output_folder,
            "cover_path": self.cover_path,
            "recursive": self.recursive_var.get(),
            "resolution": self.resolution_var.get(),
            "fit_mode": self.fit_var.get(),
            "overwrite_mode": self.overwrite_var.get(),
        }
        try:
            CONFIG_PATH.write_text(json.dumps(data, indent=4), encoding="utf-8")
        except OSError as exc:
            self.append_log(f"Could not save config: {exc}")

    def refresh_paths(self):
        self.input_label.configure(text=self.input_folder or "Not selected")
        self.output_label.configure(text=self.output_folder or "Not selected")
        self.image_label.configure(text=self.cover_path or "Not selected")
        if self.cover_path and Path(self.cover_path).is_file():
            self.load_preview(self.cover_path)

    def select_input(self):
        path = filedialog.askdirectory(title="Select folder containing audio files", initialdir=self.input_folder or None)
        if path:
            self.input_folder = path
            self.input_label.configure(text=path)
            self.save_config()

    def select_output(self):
        path = filedialog.askdirectory(title="Select output folder", initialdir=self.output_folder or None)
        if path:
            self.output_folder = path
            self.output_label.configure(text=path)
            self.save_config()

    def select_image(self):
        path = filedialog.askopenfilename(title="Select cover image", filetypes=[("Image files", "*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff"), ("All files", "*.*")])
        if not path:
            return
        try:
            with Image.open(path) as image:
                image.verify()
        except (OSError, UnidentifiedImageError) as exc:
            messagebox.showerror("Invalid Image", f"That file could not be opened as an image.\n\n{exc}")
            return
        self.cover_path = path
        self.image_label.configure(text=path)
        self.load_preview(path)
        self.save_config()

    def load_preview(self, path):
        try:
            image = Image.open(path)
            image.thumbnail((220, 200), Image.Resampling.LANCZOS)
            self.preview_image = ctk.CTkImage(light_image=image.copy(), dark_image=image.copy(), size=image.size)
            self.image_preview.configure(image=self.preview_image, text="")
        except Exception:
            self.image_preview.configure(image=None, text="Preview unavailable")

    def resolve_ffmpeg(self):
        if FFMPEG_PATH.is_file():
            return str(FFMPEG_PATH)
        return shutil.which("ffmpeg")

    def update_ffmpeg_status(self):
        if self.resolve_ffmpeg():
            self.ffmpeg_status.configure(text="FFmpeg: ready", text_color=GOOD)
        else:
            self.ffmpeg_status.configure(text="FFmpeg: missing", text_color=WARN)

    def collect_audio(self, folder):
        iterator = folder.rglob("*") if self.recursive_var.get() else folder.iterdir()
        return sorted([p for p in iterator if p.is_file() and p.suffix.lower() in AUDIO_EXTS], key=lambda p: str(p).lower())

    def validate(self):
        input_dir = Path(self.input_folder)
        output_dir = Path(self.output_folder)
        cover = Path(self.cover_path)
        if not input_dir.is_dir():
            messagebox.showerror("Input Folder", "Select a valid input folder.")
            return None
        if not self.output_folder:
            messagebox.showerror("Output Folder", "Select an output folder.")
            return None
        output_dir.mkdir(parents=True, exist_ok=True)
        if input_dir.resolve() == output_dir.resolve():
            messagebox.showerror("Folder Conflict", "The input and output folders must be different.")
            return None
        if not cover.is_file():
            messagebox.showerror("Cover Image", "Select a valid cover image.")
            return None
        ffmpeg = self.resolve_ffmpeg()
        if not ffmpeg:
            messagebox.showerror("FFmpeg Missing", "FFmpeg is not available. Reinstall the application.")
            return None
        return input_dir, output_dir, cover, ffmpeg

    def start_export(self):
        if self.exporting:
            return
        valid = self.validate()
        if not valid:
            return
        input_dir, output_dir, cover, ffmpeg = valid
        files = self.collect_audio(input_dir)
        if not files:
            messagebox.showerror("No Audio Files", "No supported audio files were found.")
            return
        self.save_config()
        self.clear_log()
        self.cancel_event.clear()
        self.exporting = True
        self.set_controls(True)
        self.progress_bar.set(0)
        self.progress_count.configure(text=f"0 / {len(files)}")
        self.append_log(f"Found {len(files)} audio file(s).")
        settings = {
            "input_dir": input_dir,
            "output_dir": output_dir,
            "cover": cover,
            "ffmpeg": ffmpeg,
            "files": files,
            "recursive": self.recursive_var.get(),
            "resolution": self.resolution_var.get(),
            "fit_mode": self.fit_var.get(),
            "overwrite": self.overwrite_var.get() == "Overwrite existing videos",
        }
        threading.Thread(target=self.worker, args=(settings,), daemon=True).start()

    def set_controls(self, exporting):
        state = "disabled" if exporting else "normal"
        for widget in [self.input_button, self.output_button, self.image_button, self.resolution_menu, self.fit_menu, self.overwrite_menu, self.recursive_check, self.generate_button]:
            widget.configure(state=state)
        self.cancel_button.configure(state="normal" if exporting else "disabled")

    def cancel_export(self):
        self.cancel_event.set()
        self.cancel_button.configure(state="disabled")
        self.current_label.configure(text="Cancelling...")
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
            except OSError:
                pass

    def video_filter(self, name, fit_mode):
        resolution = RESOLUTIONS.get(name)
        if resolution is None:
            return "scale=trunc(iw/2)*2:trunc(ih/2)*2"
        width, height = resolution
        if fit_mode == "Crop to fill":
            return f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}"
        if fit_mode == "Stretch":
            return f"scale={width}:{height}"
        return f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black"

    def worker(self, s):
        completed = skipped = failed = 0
        used = set()
        total = len(s["files"])
        for index, audio in enumerate(s["files"], 1):
            if self.cancel_event.is_set():
                break
            rel = audio.parent.relative_to(s["input_dir"]) if s["recursive"] else Path()
            dest_dir = s["output_dir"] / rel
            dest_dir.mkdir(parents=True, exist_ok=True)
            output = dest_dir / f"{audio.stem}.mp4"
            key = str(output.resolve()).lower()
            if key in used:
                output = dest_dir / f"{audio.stem}_{audio.suffix.lower().lstrip('.')}.mp4"
                key = str(output.resolve()).lower()
            used.add(key)
            if output.exists() and not s["overwrite"]:
                skipped += 1
                self.emit("log", f"SKIPPED: {output.name}")
                self.emit("progress", index, total, audio.name)
                continue
            self.emit("current", f"Creating {audio.name}")
            cmd = [s["ffmpeg"], "-hide_banner", "-loglevel", "error", "-y" if s["overwrite"] else "-n", "-loop", "1", "-framerate", "30", "-i", str(s["cover"]), "-i", str(audio), "-map", "0:v:0", "-map", "1:a:0", "-vf", self.video_filter(s["resolution"], s["fit_mode"]), "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-tune", "stillimage", "-r", "30", "-c:a", "aac", "-b:a", "320k", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-shortest", str(output)]
            startupinfo = None
            flags = 0
            if os.name == "nt":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                flags = subprocess.CREATE_NO_WINDOW
            try:
                self.process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", startupinfo=startupinfo, creationflags=flags)
                while self.process.poll() is None:
                    if self.cancel_event.is_set():
                        self.process.terminate()
                        break
                    time.sleep(0.1)
                _, stderr = self.process.communicate()
                if self.cancel_event.is_set():
                    output.unlink(missing_ok=True)
                    break
                if self.process.returncode == 0 and output.is_file() and output.stat().st_size > 0:
                    completed += 1
                    self.emit("log", f"DONE: {output.name}")
                else:
                    failed += 1
                    output.unlink(missing_ok=True)
                    lines = [line.strip() for line in (stderr or "").splitlines() if line.strip()]
                    self.emit("log", f"FAILED: {audio.name}")
                    if lines:
                        self.emit("log", "  " + " | ".join(lines[-3:])[:700])
            except Exception as exc:
                failed += 1
                self.emit("log", f"FAILED: {audio.name} — {exc}")
            finally:
                self.process = None
            self.emit("progress", index, total, audio.name)
        self.emit("finished", {"completed": completed, "skipped": skipped, "failed": failed, "total": total, "cancelled": self.cancel_event.is_set()})

    def emit(self, kind, *payload):
        self.events.put((kind, payload))

    def drain_events(self):
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "log":
                    self.append_log(payload[0])
                elif kind == "current":
                    self.current_label.configure(text=payload[0])
                elif kind == "progress":
                    index, total, name = payload
                    self.progress_bar.set(index / total)
                    self.progress_count.configure(text=f"{index} / {total}")
                    self.current_label.configure(text=f"Processed: {name}")
                elif kind == "finished":
                    self.finish_export(payload[0])
        except queue.Empty:
            pass
        self.after(100, self.drain_events)

    def finish_export(self, summary):
        self.exporting = False
        self.set_controls(False)
        c, s, f = summary["completed"], summary["skipped"], summary["failed"]
        status = f"Finished — {c} completed, {s} skipped, {f} failed."
        if summary["cancelled"]:
            status = f"Cancelled — {c} completed, {s} skipped, {f} failed."
        self.current_label.configure(text=status)
        self.append_log(status)
        if summary["cancelled"]:
            messagebox.showwarning("Export Cancelled", status)
        elif f:
            messagebox.showwarning("Export Finished with Errors", status + "\n\nCheck the activity log for details.")
        else:
            self.progress_bar.set(1)
            messagebox.showinfo("Export Complete", status)

    def append_log(self, text):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def clear_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    def open_output(self):
        if not self.output_folder or not Path(self.output_folder).is_dir():
            messagebox.showerror("Output Folder", "Select a valid output folder first.")
            return
        os.startfile(self.output_folder)

    def on_close(self):
        if self.exporting and not messagebox.askyesno("Export in Progress", "Cancel the export and close the program?"):
            return
        self.cancel_event.set()
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
            except OSError:
                pass
        self.save_config()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
