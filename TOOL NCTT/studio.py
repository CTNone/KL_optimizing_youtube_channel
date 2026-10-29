"""Launch the shared NCTT + Thumbnail interface from TOOL NCTT."""
from pathlib import Path
import importlib.util
import sys

THUMBNAIL_DIR = Path(__file__).resolve().parent.parent / 'TOOL THUMBNAIL'


def load_studio():
    entry = THUMBNAIL_DIR / 'integrated_app.py'
    if not entry.is_file():
        raise RuntimeError('Không tìm thấy TOOL THUMBNAIL/integrated_app.py. Giữ TOOL THUMBNAIL và TOOL NCTT cạnh nhau.')
    directory = str(THUMBNAIL_DIR)
    if directory not in sys.path:
        sys.path.insert(0, directory)
    spec = importlib.util.spec_from_file_location('nctt_shared_studio', entry)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    try:
        shared = load_studio()
        shared.main()
    except Exception as error:
        import traceback
        error_log = Path(__file__).resolve().parent / 'startup_error.log'
        error_log.write_text(traceback.format_exc(), encoding='utf-8')
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror('NCTT + Thumbnail', f'{error}\n\nChi tiết lỗi: {error_log}\n\nChạy run.bat để cài thư viện. Có thể mở riêng nghiên cứu bằng: python app.py --research-only', parent=root)
        root.destroy()
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
