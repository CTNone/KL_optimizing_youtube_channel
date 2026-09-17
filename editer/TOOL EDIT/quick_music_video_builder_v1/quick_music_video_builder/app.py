import os
import sys
import random
import shutil
import subprocess
import tempfile
import threading
import queue
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP_NAME = "Quick Music Video Builder"
TARGET_SECONDS = 60 * 60
WIDTH = 2560
HEIGHT = 1440
FPS = 30

AUDIO_EXTS = {
    ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma"
}


def resource_path(*parts):
    """Resolve files both in source mode and in a PyInstaller bundle."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base.joinpath(*parts)


def no_window_flag():
    return subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def find_binary(name):
    exe = f"{name}.exe" if os.name == "nt" else name

    candidates = [
        resource_path("tools", exe),
        Path(__file__).resolve().parent / "tools" / exe,
    ]
    for p in candidates:
        if p.exists():
            return str(p)

    found = shutil.which(name)
    if found:
        return found
    return None


def ffconcat_escape(path):
    # FFmpeg concat list uses single-quoted file paths.
    # Escape single quote as: '\''
    s = str(Path(path).resolve()).replace("\\", "/")
    return s.replace("'", "'\\''")


def get_duration(ffprobe, path):
    cmd = [
        ffprobe,
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    cp = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=no_window_flag(),
    )
    if cp.returncode != 0:
        raise RuntimeError(cp.stderr.strip() or f"Không đọc được thời lượng: {path}")
    try:
        return float(cp.stdout.strip())
    except ValueError:
        raise RuntimeError(f"FFprobe trả về thời lượng không hợp lệ: {path}")


class MusicVideoApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("1080x760")
        self.minsize(940, 660)

        self.image_path = tk.StringVar()
        self.music_folder = tk.StringVar()
        self.output_path = tk.StringVar()
        self.status = tk.StringVar(value="Sẵn sàng")
        self.progress_value = tk.DoubleVar(value=0.0)

        self.track_paths = []
        self.track_names = []
        self.slot_vars = [tk.StringVar() for _ in range(5)]

        self.log_queue = queue.Queue()
        self.current_process = None
        self.cancel_requested = False
        self.worker_thread = None

        self._build_ui()
        self.after(100, self._drain_log_queue)

    def _build_ui(self):
        pad = {"padx": 10, "pady": 6}

        main = ttk.Frame(self, padding=12)
        main.pack(fill="both", expand=True)

        title = ttk.Label(main, text=APP_NAME, font=("Segoe UI", 18, "bold"))
        title.pack(anchor="w", pady=(0, 8))

        subtitle = ttk.Label(
            main,
            text="Ảnh thumbnail + folder nhạc → video 1 giờ, 2560×1440, 30 fps",
        )
        subtitle.pack(anchor="w", pady=(0, 12))

        inputs = ttk.LabelFrame(main, text="1. Đầu vào")
        inputs.pack(fill="x")

        ttk.Label(inputs, text="Ảnh thumbnail:").grid(row=0, column=0, sticky="w", **pad)
        ttk.Entry(inputs, textvariable=self.image_path).grid(
            row=0, column=1, sticky="ew", **pad
        )
        ttk.Button(inputs, text="Chọn ảnh", command=self.choose_image).grid(
            row=0, column=2, **pad
        )

        ttk.Label(inputs, text="Folder nhạc:").grid(row=1, column=0, sticky="w", **pad)
        ttk.Entry(inputs, textvariable=self.music_folder).grid(
            row=1, column=1, sticky="ew", **pad
        )
        ttk.Button(inputs, text="Chọn folder", command=self.choose_music_folder).grid(
            row=1, column=2, **pad
        )

        ttk.Label(inputs, text="File xuất:").grid(row=2, column=0, sticky="w", **pad)
        ttk.Entry(inputs, textvariable=self.output_path).grid(
            row=2, column=1, sticky="ew", **pad
        )
        ttk.Button(inputs, text="Chọn nơi lưu", command=self.choose_output).grid(
            row=2, column=2, **pad
        )
        inputs.columnconfigure(1, weight=1)

        middle = ttk.Frame(main)
        middle.pack(fill="both", expand=True, pady=(12, 0))

        fixed = ttk.LabelFrame(middle, text="2. Chỉ định 5 bài đầu tiên")
        fixed.pack(side="left", fill="both", expand=True, padx=(0, 6))

        ttk.Label(
            fixed,
            text="Mỗi bài chỉ được chọn một lần. Các bài còn lại sẽ được xáo trộn ngẫu nhiên.",
            wraplength=430,
        ).pack(anchor="w", padx=10, pady=(8, 6))

        self.combos = []
        for i in range(5):
            row = ttk.Frame(fixed)
            row.pack(fill="x", padx=10, pady=4)
            ttk.Label(row, text=f"#{i+1}", width=4).pack(side="left")
            combo = ttk.Combobox(
                row,
                textvariable=self.slot_vars[i],
                state="readonly",
                values=[],
            )
            combo.pack(side="left", fill="x", expand=True)
            self.combos.append(combo)

        actions = ttk.Frame(fixed)
        actions.pack(fill="x", padx=10, pady=10)
        ttk.Button(actions, text="Tự điền 5 bài đầu", command=self.autofill_first_five).pack(
            side="left"
        )
        ttk.Button(actions, text="Xóa lựa chọn", command=self.clear_slots).pack(
            side="left", padx=8
        )

        info = ttk.LabelFrame(middle, text="3. Thông tin / Log")
        info.pack(side="left", fill="both", expand=True, padx=(6, 0))

        self.track_count_label = ttk.Label(info, text="Chưa quét folder nhạc.")
        self.track_count_label.pack(anchor="w", padx=10, pady=(8, 4))

        self.log_text = tk.Text(
            info,
            height=17,
            wrap="word",
            state="disabled",
            font=("Consolas", 9),
        )
        self.log_text.pack(fill="both", expand=True, padx=10, pady=(4, 10))

        bottom = ttk.LabelFrame(main, text="4. Xuất video")
        bottom.pack(fill="x", pady=(12, 0))

        settings_line = ttk.Frame(bottom)
        settings_line.pack(fill="x", padx=10, pady=(8, 4))
        ttk.Label(settings_line, text="Độ dài: 01:00:00").pack(side="left")
        ttk.Label(settings_line, text="   |   2560×1440").pack(side="left")
        ttk.Label(settings_line, text="   |   30 fps").pack(side="left")
        ttk.Label(settings_line, text="   |   AAC 320 kbps").pack(side="left")

        self.progress = ttk.Progressbar(
            bottom,
            variable=self.progress_value,
            maximum=100,
            mode="determinate",
        )
        self.progress.pack(fill="x", padx=10, pady=6)

        status_line = ttk.Frame(bottom)
        status_line.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Label(status_line, textvariable=self.status).pack(side="left")

        self.generate_btn = ttk.Button(
            status_line, text="TẠO VIDEO 1 GIỜ", command=self.start_generation
        )
        self.generate_btn.pack(side="right")

        self.cancel_btn = ttk.Button(
            status_line, text="Hủy", command=self.cancel_generation, state="disabled"
        )
        self.cancel_btn.pack(side="right", padx=8)

        ttk.Button(
            status_line, text="Xem thứ tự playlist", command=self.preview_playlist
        ).pack(side="right", padx=8)

    def log(self, text):
        self.log_queue.put(("log", text))

    def set_status(self, text):
        self.log_queue.put(("status", text))

    def set_progress(self, value):
        self.log_queue.put(("progress", max(0.0, min(100.0, value))))

    def _drain_log_queue(self):
        try:
            while True:
                kind, value = self.log_queue.get_nowait()
                if kind == "log":
                    self.log_text.configure(state="normal")
                    self.log_text.insert("end", value + "\n")
                    self.log_text.see("end")
                    self.log_text.configure(state="disabled")
                elif kind == "status":
                    self.status.set(value)
                elif kind == "progress":
                    self.progress_value.set(value)
                elif kind == "done":
                    self.generate_btn.configure(state="normal")
                    self.cancel_btn.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(100, self._drain_log_queue)

    def choose_image(self):
        p = filedialog.askopenfilename(
            title="Chọn thumbnail",
            filetypes=[
                ("Image files", "*.jpg *.jpeg *.png *.webp *.bmp"),
                ("All files", "*.*"),
            ],
        )
        if p:
            self.image_path.set(p)
            if not self.output_path.get():
                self.output_path.set(str(Path(p).with_name(Path(p).stem + "_1H_2K.mp4")))

    def choose_music_folder(self):
        p = filedialog.askdirectory(title="Chọn folder chứa nhạc")
        if not p:
            return
        self.music_folder.set(p)
        self.scan_music_folder()

    def choose_output(self):
        initial = self.output_path.get()
        p = filedialog.asksaveasfilename(
            title="Lưu video",
            defaultextension=".mp4",
            initialfile=Path(initial).name if initial else "music_video_1H_2K.mp4",
            filetypes=[("MP4 video", "*.mp4")],
        )
        if p:
            self.output_path.set(p)

    def scan_music_folder(self):
        folder = Path(self.music_folder.get())
        if not folder.is_dir():
            messagebox.showerror("Lỗi", "Folder nhạc không tồn tại.")
            return

        tracks = [
            p for p in folder.rglob("*")
            if p.is_file() and p.suffix.lower() in AUDIO_EXTS
        ]
        tracks.sort(key=lambda p: p.name.lower())

        self.track_paths = tracks
        self.track_names = [p.name for p in tracks]

        for combo in self.combos:
            combo["values"] = self.track_names

        self.clear_slots()
        if len(tracks) >= 5:
            self.autofill_first_five()

        self.track_count_label.configure(
            text=f"Tìm thấy {len(tracks)} file nhạc hỗ trợ."
        )
        self.log(f"Đã quét: {folder}")
        self.log(f"Tìm thấy {len(tracks)} bài.")

    def autofill_first_five(self):
        if len(self.track_names) < 5:
            return
        for i in range(5):
            self.slot_vars[i].set(self.track_names[i])

    def clear_slots(self):
        for v in self.slot_vars:
            v.set("")

    def _selected_first_five(self):
        names = [v.get().strip() for v in self.slot_vars]
        if any(not n for n in names):
            raise ValueError("Bạn phải chọn đủ 5 bài đầu tiên.")
        if len(set(names)) != 5:
            raise ValueError("5 bài đầu tiên không được trùng nhau.")

        name_to_paths = {}
        for p in self.track_paths:
            name_to_paths.setdefault(p.name, []).append(p)

        selected = []
        for n in names:
            choices = name_to_paths.get(n, [])
            if len(choices) != 1:
                # Duplicate filenames in subfolders are ambiguous.
                raise ValueError(
                    f"Tên file bị trùng trong folder/subfolder: {n}\n"
                    "Hãy đổi tên các file trùng nhau để mỗi bài có tên duy nhất."
                )
            selected.append(choices[0])
        return selected

    def validate_inputs(self):
        image = Path(self.image_path.get())
        folder = Path(self.music_folder.get())
        output = Path(self.output_path.get())

        if not image.is_file():
            raise ValueError("Bạn chưa chọn ảnh thumbnail hợp lệ.")
        if not folder.is_dir():
            raise ValueError("Bạn chưa chọn folder nhạc hợp lệ.")
        if len(self.track_paths) < 5:
            raise ValueError("Folder phải có ít nhất 5 bài nhạc.")
        first_five = self._selected_first_five()

        if not output.name:
            raise ValueError("Bạn chưa chọn file xuất.")
        if output.suffix.lower() != ".mp4":
            output = output.with_suffix(".mp4")
            self.output_path.set(str(output))
        output.parent.mkdir(parents=True, exist_ok=True)

        ffmpeg = find_binary("ffmpeg")
        ffprobe = find_binary("ffprobe")
        if not ffmpeg or not ffprobe:
            raise ValueError(
                "Không tìm thấy FFmpeg/FFprobe.\n\n"
                "Hãy đặt ffmpeg.exe và ffprobe.exe vào folder tools "
                "hoặc cài FFmpeg vào PATH."
            )

        return image, output, first_five, ffmpeg, ffprobe

    def build_cycle(self, first_five):
        first_set = {p.resolve() for p in first_five}
        remaining = [p for p in self.track_paths if p.resolve() not in first_set]
        random.shuffle(remaining)
        return first_five + remaining

    def build_sequence_for_one_hour(self, first_five, durations):
        sequence = []
        total = 0.0
        cycle_index = 0

        while total < TARGET_SECONDS:
            cycle = self.build_cycle(first_five)
            cycle_index += 1
            for p in cycle:
                sequence.append(p)
                total += durations[p]
                if total >= TARGET_SECONDS:
                    break
            if not cycle:
                break

        return sequence, total, cycle_index

    def preview_playlist(self):
        try:
            image, output, first_five, ffmpeg, ffprobe = self.validate_inputs()
        except Exception as e:
            messagebox.showerror("Chưa đủ thông tin", str(e))
            return

        self.set_status("Đang đọc thời lượng bài hát...")
        self.generate_btn.configure(state="disabled")

        def work():
            try:
                durations = {}
                for i, p in enumerate(self.track_paths, 1):
                    durations[p] = get_duration(ffprobe, p)
                    self.set_progress(i / max(1, len(self.track_paths)) * 100)

                seq, total, cycles = self.build_sequence_for_one_hour(first_five, durations)

                lines = []
                running = 0.0
                for i, p in enumerate(seq, 1):
                    d = durations[p]
                    lines.append(
                        f"{i:03d}. {self.fmt_time(running)}  {p.name}  ({self.fmt_time(d)})"
                    )
                    running += d
                    if running >= TARGET_SECONDS:
                        break

                text = "\n".join(lines)
                self.log("===== PLAYLIST DỰ KIẾN =====")
                self.log(text)
                self.log(
                    f"Đủ 1 giờ sau {len(seq)} lượt bài; "
                    f"đã dùng {cycles} vòng playlist."
                )
                self.set_status("Đã tạo preview playlist.")
            except Exception as e:
                self.log(f"LỖI: {e}")
                self.set_status("Có lỗi.")
                self.after(0, lambda: messagebox.showerror("Lỗi", str(e)))
            finally:
                self.set_progress(0)
                self.after(0, lambda: self.generate_btn.configure(state="normal"))

        threading.Thread(target=work, daemon=True).start()

    @staticmethod
    def fmt_time(seconds):
        seconds = max(0, int(seconds))
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        if h:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    def start_generation(self):
        try:
            args = self.validate_inputs()
        except Exception as e:
            messagebox.showerror("Chưa đủ thông tin", str(e))
            return

        if self.worker_thread and self.worker_thread.is_alive():
            return

        self.cancel_requested = False
        self.progress_value.set(0)
        self.generate_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.status.set("Đang chuẩn bị...")

        self.worker_thread = threading.Thread(
            target=self.generate_video,
            args=args,
            daemon=True,
        )
        self.worker_thread.start()

    def cancel_generation(self):
        self.cancel_requested = True
        self.set_status("Đang hủy...")
        p = self.current_process
        if p and p.poll() is None:
            try:
                p.terminate()
            except Exception:
                pass

    def generate_video(self, image, output, first_five, ffmpeg, ffprobe):
        temp_dir_obj = None
        try:
            self.log("===== BẮT ĐẦU =====")
            self.log(f"Ảnh: {image}")
            self.log(f"Output: {output}")
            self.log(f"FFmpeg: {ffmpeg}")

            self.set_status("Đang đọc thời lượng các bài hát...")
            durations = {}
            for i, p in enumerate(self.track_paths, 1):
                if self.cancel_requested:
                    raise RuntimeError("Đã hủy theo yêu cầu.")
                durations[p] = get_duration(ffprobe, p)
                self.set_progress((i / max(1, len(self.track_paths))) * 8.0)

            sequence, planned_total, cycles = self.build_sequence_for_one_hour(
                first_five, durations
            )

            self.log("5 bài đầu:")
            for i, p in enumerate(first_five, 1):
                self.log(f"  {i}. {p.name}")

            self.log(f"Số bài/lượt dùng cho 1 giờ: {len(sequence)}")
            self.log(f"Số vòng playlist cần dùng: {cycles}")
            self.log(f"Tổng audio nguồn đã xếp: {self.fmt_time(planned_total)}")
            self.log("Video cuối sẽ cắt chính xác ở 01:00:00.")

            temp_dir_obj = tempfile.TemporaryDirectory(prefix="qmvb_")
            concat_file = Path(temp_dir_obj.name) / "playlist.ffconcat"

            with concat_file.open("w", encoding="utf-8", newline="\n") as f:
                f.write("ffconcat version 1.0\n")
                for p in sequence:
                    f.write(f"file '{ffconcat_escape(p)}'\n")

            vf = (
                f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
                f"crop={WIDTH}:{HEIGHT},format=yuv420p"
            )

            cmd = [
                ffmpeg,
                "-y",
                "-hide_banner",
                "-loglevel", "warning",
                "-loop", "1",
                "-framerate", str(FPS),
                "-i", str(image),
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_file),
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-vf", vf,
                "-r", str(FPS),
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-tune", "stillimage",
                "-crf", "18",
                "-c:a", "aac",
                "-b:a", "320k",
                "-ar", "48000",
                "-ac", "2",
                "-t", str(TARGET_SECONDS),
                "-movflags", "+faststart",
                "-progress", "pipe:1",
                "-nostats",
                str(output),
            ]

            self.set_status("Đang render video 2K...")
            self.log("Đang chạy FFmpeg...")

            self.current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=no_window_flag(),
            )

            stderr_lines = []

            def read_stderr():
                if not self.current_process or not self.current_process.stderr:
                    return
                for line in self.current_process.stderr:
                    line = line.rstrip()
                    if line:
                        stderr_lines.append(line)
                        if len(stderr_lines) > 40:
                            stderr_lines.pop(0)

            stderr_thread = threading.Thread(target=read_stderr, daemon=True)
            stderr_thread.start()

            if self.current_process.stdout:
                for line in self.current_process.stdout:
                    if self.cancel_requested:
                        try:
                            self.current_process.terminate()
                        except Exception:
                            pass
                        break

                    line = line.strip()
                    if "=" not in line:
                        continue
                    key, value = line.split("=", 1)

                    seconds = None
                    if key in ("out_time_us", "out_time_ms"):
                        # Modern FFmpeg commonly reports microseconds here.
                        try:
                            raw = float(value)
                            seconds = raw / 1_000_000.0
                        except ValueError:
                            pass
                    elif key == "out_time":
                        try:
                            hh, mm, ss = value.split(":")
                            seconds = int(hh) * 3600 + int(mm) * 60 + float(ss)
                        except Exception:
                            pass

                    if seconds is not None:
                        render_pct = min(100.0, seconds / TARGET_SECONDS * 100.0)
                        # First 8% was probing; render occupies 8..100.
                        self.set_progress(8.0 + render_pct * 0.92)
                        self.set_status(
                            f"Đang render: {render_pct:5.1f}%  "
                            f"({self.fmt_time(seconds)} / 01:00:00)"
                        )

            return_code = self.current_process.wait()
            stderr_thread.join(timeout=1.0)
            self.current_process = None

            if self.cancel_requested:
                if output.exists():
                    try:
                        output.unlink()
                    except Exception:
                        pass
                raise RuntimeError("Đã hủy theo yêu cầu.")

            if return_code != 0:
                err = "\n".join(stderr_lines[-20:]) or "FFmpeg kết thúc với lỗi không xác định."
                raise RuntimeError(
                    "FFmpeg không thể tạo video.\n\n"
                    "Một nguyên nhân thường gặp là các file nhạc trong folder "
                    "có codec/stream quá khác nhau.\n\n"
                    f"Chi tiết cuối:\n{err}"
                )

            self.set_progress(100)
            self.set_status("Hoàn tất.")
            size_gb = output.stat().st_size / (1024 ** 3) if output.exists() else 0
            self.log(f"HOÀN TẤT: {output}")
            self.log(f"Kích thước file: {size_gb:.2f} GB")
            self.after(
                0,
                lambda: messagebox.showinfo(
                    "Hoàn tất",
                    f"Đã tạo video 1 giờ 2K:\n\n{output}"
                ),
            )

        except Exception as e:
            self.log(f"LỖI: {e}")
            self.set_status("Đã hủy." if self.cancel_requested else "Có lỗi.")
            if not self.cancel_requested:
                self.after(0, lambda: messagebox.showerror("Lỗi", str(e)))
        finally:
            self.current_process = None
            if temp_dir_obj is not None:
                try:
                    temp_dir_obj.cleanup()
                except Exception:
                    pass
            self.log_queue.put(("done", None))


if __name__ == "__main__":
    app = MusicVideoApp()
    app.mainloop()
