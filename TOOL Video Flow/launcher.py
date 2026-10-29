"""Desktop entry point: one Studio instance, visible errors and diagnostics."""
from pathlib import Path
import traceback
import ctypes
import hashlib

if __name__ == '__main__':
    root=Path(__file__).resolve().parent
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p]
    kernel.CreateMutexW.restype=ctypes.c_void_p
    kernel.CloseHandle.argtypes=[ctypes.c_void_p]
    name='Local\\YouTubeMusicStudio_'+hashlib.sha256(str(root).encode()).hexdigest()[:20]
    mutex=kernel.CreateMutexW(None,False,name)
    if not mutex:raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error()==183:
        ctypes.windll.user32.MessageBoxW(None,'Studio đang mở. Dùng cửa sổ hiện tại hoặc đóng rồi mở lại để nạp bản mới.','YouTube Music Studio',64)
        kernel.CloseHandle(mutex)
        raise SystemExit(0)
    try:
        from studio_app import main
        main()
    except Exception:
        error=traceback.format_exc()
        log=root/'startup-error.log'
        log.write_text(error,encoding='utf-8')
        ctypes.windll.user32.MessageBoxW(None,f'Không mở được Studio. Chi tiết: {log}\n\n{error[-1800:]}','YouTube Music Studio',16)
    finally:
        kernel.CloseHandle(mutex)
