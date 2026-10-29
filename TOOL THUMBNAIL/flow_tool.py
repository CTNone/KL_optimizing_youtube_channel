"""Local sequential Google Flow UI runner. No private API or credential extraction."""
import json
import queue
import threading
import time
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

ROOT = Path(__file__).resolve().parent
OUTPUT_ROOT = ROOT.parent / "TOOL Video Flow OUTPUT" / "Flow TXT"
DEFAULTS = {
    "url": "https://labs.google/fx/tools/flow",
    "prompt": 'textarea, [contenteditable="true"][role="textbox"]',
    "generate": 'button:has-text("arrow_forward"), button[aria-label="Generate"], button[aria-label="Tạo"]',
    "card": "",
    "image": "img",
    "download": 'button[aria-label*="Download"], button[aria-label*="Tải xuống"], button:has-text("download")',
    "menu": "",
    "timeout": "240",
    "count": "1",
}


def parse_prompts(text, mode):
    text = text.lstrip("\ufeff").replace("\r\n", "\n")
    parts = text.split("\n") if mode == "Mỗi dòng một prompt" else text.split("\n---\n")
    return [part.strip() for part in parts if part.strip()]


class Runner:
    def __init__(self, events):
        self.events = events
        self.commands = queue.Queue()
        self.stop = threading.Event()
        threading.Thread(target=self.loop, daemon=True).start()

    def log(self, text):
        self.events.put(("log", text))

    def check(self):
        if self.stop.is_set():
            raise RuntimeError("Đã dừng. Kiểm tra ảnh đang tạo trên Flow trước khi chạy tiếp.")

    def loop(self):
        context = None
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as pw:
                while True:
                    command, data = self.commands.get()
                    try:
                        if command == "open":
                            if context is None:
                                context = pw.chromium.launch_persistent_context(
                                    str(ROOT / "browser-profile"), headless=False, accept_downloads=True,
                                    viewport={"width": 1400, "height": 950})
                            page = context.pages[0] if context.pages else context.new_page()
                            page.goto(data, wait_until="domcontentloaded")
                            self.log("Hãy đăng nhập, mở dự án và chọn chế độ tạo ẢNH. Sau đó bấm Chạy.")
                        elif command == "run":
                            if context is None:
                                raise RuntimeError("Bấm Mở Google Flow trước.")
                            pages = [p for p in context.pages if "flow" in p.url]
                            if len(pages) != 1:
                                raise RuntimeError("Giữ đúng một tab Google Flow mở trong trình duyệt của tool.")
                            self.run_batch(pages[0], **data)
                    except Exception as exc:
                        self.log(f"DỪNG: {exc}")
                    finally:
                        self.events.put(("idle", None))
        except Exception as exc:
            self.log(f"Không khởi động được: {exc}. Hãy chạy start.bat.")
            self.events.put(("idle", None))

    def run_batch(self, page, prompts, output, cfg, start):
        self.stop.clear()
        timeout = int(cfg["timeout"]) * 1000
        expected = int(cfg["count"])
        page.set_default_timeout(10000)
        folder = Path(output) / datetime.now().strftime("Flow_%Y%m%d_%H%M%S_%f")
        folder.mkdir(parents=True)
        journal = {"prompts": prompts, "start": start + 1, "items": []}
        def save():
            (folder / "progress.json").write_text(json.dumps(journal, ensure_ascii=False, indent=2), encoding="utf-8")
        save()
        self.log(f"Lưu tại: {folder}")
        for index in range(start, len(prompts)):
            self.check()
            record = {"number": index + 1, "prompt": prompts[index], "status": "preparing", "files": []}
            journal["items"].append(record)
            save()
            try:
                editor = page.locator(cfg["prompt"]).filter(visible=True)
                generate = page.locator(cfg["generate"]).filter(visible=True)
                if editor.count() != 1 or generate.count() != 1:
                    raise RuntimeError("Bộ chọn ô prompt/nút tạo phải khớp đúng một phần tử đang hiển thị.")
                cards = page.locator(cfg["card"])
                def fingerprints():
                    result = set()
                    for card in cards.all():
                        for img in card.locator(cfg["image"]).all():
                            src = img.get_attribute("src")
                            if src:
                                result.add(src)
                    return result
                before = fingerprints()
                editor.fill(prompts[index])
                self.check()
                record["status"] = "submitting"
                save()
                generate.click()
                record["status"] = "waiting"
                save()
                self.log(f"[{index + 1}/{len(prompts)}] Đã gửi, đang đợi {expected} ảnh…")
                deadline = time.monotonic() + timeout / 1000
                found = {}
                while time.monotonic() < deadline:
                    self.check()
                    for card in cards.all():
                        if not card.is_visible():
                            continue
                        images = card.locator(cfg["image"])
                        if images.count() != 1:
                            continue
                        img = images.first
                        src = img.get_attribute("src")
                        if not src or src in before or src in found:
                            continue
                        loaded = img.evaluate("e => e.complete && e.naturalWidth >= 256 && e.naturalHeight >= 256")
                        if loaded:
                            found[src] = card
                    if len(found) >= expected:
                        break
                    page.wait_for_timeout(500)
                if len(found) != expected:
                    raise RuntimeError(f"Nhận diện {len(found)}/{expected} ảnh mới. Kiểm tra Flow/bộ chọn; không tự gửi lại.")
                for ordinal, card in enumerate(found.values(), 1):
                    self.check()
                    card.hover()
                    button = card.locator(cfg["download"]).filter(visible=True)
                    if button.count() != 1:
                        raise RuntimeError("Không xác định được đúng một nút tải trong thẻ ảnh mới.")
                    with page.expect_download(timeout=30000) as pending:
                        button.click()
                        if cfg["menu"].strip():
                            page.locator(cfg["menu"]).click()
                    download = pending.value
                    suffix = Path(download.suggested_filename).suffix.lower()
                    if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".avif"}:
                        raise RuntimeError(f"File tải về không phải định dạng ảnh được hỗ trợ: {suffix}")
                    name = f"{index + 1:04d}_{ordinal:02d}{suffix}"
                    download.save_as(str(folder / name))
                    if not (folder / name).stat().st_size:
                        raise RuntimeError("File ảnh rỗng.")
                    record["files"].append(name)
                    save()
                record["status"] = "done"
                save()
                self.log(f"[{index + 1}/{len(prompts)}] Đã lưu {len(record['files'])} ảnh.")
            except Exception as exc:
                record["status"] = "needs_review"
                record["error"] = str(exc)
                save()
                try:
                    page.screenshot(path=str(folder / "error.png"))
                except Exception:
                    pass
                raise
        self.log("HOÀN TẤT danh sách prompt.")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Flow — Tạo ảnh từ file TXT")
        self.geometry("940x810")
        self.events = queue.Queue()
        self.runner = Runner(self.events)
        self.file = tk.StringVar()
        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        self.output = tk.StringVar(value=str(OUTPUT_ROOT))
        self.mode = tk.StringVar(value="Mỗi dòng một prompt")
        self.start = tk.StringVar(value="1")
        saved = {}
        try:
            saved = json.loads((ROOT / "settings.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
        self.cfg = {k: tk.StringVar(value=saved.get(k, v)) for k, v in DEFAULTS.items()}
        box = ttk.Frame(self, padding=16)
        box.pack(fill="both", expand=True)
        ttk.Label(box, text="Google Flow • Danh sách prompt → ảnh", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(box, text="Dùng phiên đăng nhập của bạn. Flow vẫn áp dụng hạn mức/credit của tài khoản.").pack(anchor="w", pady=8)
        for label, var, action in [("File .txt", self.file, self.choose_file), ("Lưu ảnh", self.output, self.choose_output)]:
            row = ttk.Frame(box)
            row.pack(fill="x", pady=4)
            ttk.Label(row, text=label, width=14).pack(side="left")
            ttk.Entry(row, textvariable=var).pack(side="left", fill="x", expand=True)
            ttk.Button(row, text="Chọn…", command=action).pack(side="left", padx=4)
        row = ttk.Frame(box)
        row.pack(fill="x", pady=8)
        ttk.Combobox(row, textvariable=self.mode, values=["Mỗi dòng một prompt", "Ngăn prompt bằng dòng ---"], state="readonly", width=30).pack(side="left")
        ttk.Label(row, text="   Bắt đầu từ prompt số ").pack(side="left")
        ttk.Entry(row, textvariable=self.start, width=6).pack(side="left")
        advanced = ttk.LabelFrame(box, text="Cấu hình giao diện Flow (CSS / Playwright selector)", padding=8)
        advanced.pack(fill="x", pady=8)
        labels = {"url": "URL dự án Flow", "prompt": "Ô nhập prompt", "generate": "Nút tạo", "card": "Thẻ chứa MỘT ảnh", "image": "Ảnh trong thẻ", "download": "Nút tải trong thẻ", "menu": "Mục tải sau menu (nếu có)", "timeout": "Chờ tối đa (giây)", "count": "Số ảnh / prompt"}
        for key, label in labels.items():
            row = ttk.Frame(advanced)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=label, width=29).pack(side="left")
            ttk.Entry(row, textvariable=self.cfg[key]).pack(side="left", fill="x", expand=True)
        row = ttk.Frame(box)
        row.pack(fill="x", pady=8)
        self.open_button = ttk.Button(row, text="1. Mở Google Flow", command=self.open_flow)
        self.open_button.pack(side="left")
        self.run_button = ttk.Button(row, text="2. Chạy lần lượt", command=self.run)
        self.run_button.pack(side="left", padx=8)
        ttk.Button(row, text="Dừng", command=self.runner.stop.set).pack(side="left")
        self.log = tk.Text(box, height=12, wrap="word", state="disabled")
        self.log.pack(fill="both", expand=True)
        self.after(100, self.poll)

    def choose_file(self):
        path = filedialog.askopenfilename(filetypes=[("Danh sách prompt", "*.txt")])
        if path:
            self.file.set(path)

    def choose_output(self):
        path = filedialog.askdirectory(initialdir=str(OUTPUT_ROOT))
        if path:
            self.output.set(path)

    def busy(self, value):
        for button in (self.open_button, self.run_button):
            button.config(state="disabled" if value else "normal")

    def open_flow(self):
        self.busy(True)
        self.runner.commands.put(("open", self.cfg["url"].get()))

    def run(self):
        try:
            output = Path(self.output.get()).resolve()
            output.relative_to(OUTPUT_ROOT.resolve())
        except ValueError:
            messagebox.showerror("Thư mục lưu", f"Chọn thư mục nằm trong {OUTPUT_ROOT}.")
            return
        try:
            prompts = parse_prompts(Path(self.file.get()).read_text(encoding="utf-8-sig"), self.mode.get())
            cfg = {k: v.get().strip() for k, v in self.cfg.items()}
            start = int(self.start.get()) - 1
            if not prompts or not 0 <= start < len(prompts):
                raise ValueError("File rỗng hoặc số prompt bắt đầu không hợp lệ.")
            if not cfg["card"]:
                raise ValueError("Cần cấu hình bộ chọn thẻ ảnh theo giao diện Flow hiện tại. Xem README.md.")
            if int(cfg["timeout"]) < 10 or not 1 <= int(cfg["count"]) <= 8:
                raise ValueError("Thời gian chờ ít nhất 10 giây; số ảnh từ 1 đến 8.")
            (ROOT / "settings.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
            self.busy(True)
            self.runner.commands.put(("run", dict(prompts=prompts, output=self.output.get(), cfg=cfg, start=start)))
        except Exception as exc:
            messagebox.showerror("Chưa chạy được", str(exc))

    def poll(self):
        while not self.events.empty():
            kind, value = self.events.get_nowait()
            if kind == "idle":
                self.busy(False)
            else:
                self.log.config(state="normal")
                self.log.insert("end", f"{datetime.now():%H:%M:%S}  {value}\n")
                self.log.see("end")
                self.log.config(state="disabled")
        self.after(100, self.poll)


if __name__ == "__main__":
    App().mainloop()
