"""Import selected local Chrome session files without modifying the source."""
import csv
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import uuid


SESSION_FILES = ('Preferences', 'Secure Preferences', 'Cookies', 'Cookies-journal',
                 'Network/Cookies', 'Network/Cookies-journal', 'Local Storage',
                 'IndexedDB', 'Session Storage')


def discover_profiles(user_data=None):
    root = Path(user_data) if user_data else Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'Google/Chrome/User Data'
    if not root.is_dir():
        return []
    try:
        cache = json.loads((root / 'Local State').read_text(encoding='utf-8')).get('profile', {}).get('info_cache', {})
    except (OSError, ValueError):
        cache = {}
    profiles = []
    for folder in sorted(root.iterdir(), key=lambda p: p.name):
        if not folder.is_dir() or folder.is_symlink() or (hasattr(folder, 'is_junction') and folder.is_junction()):
            continue
        if folder.name not in cache and folder.name != 'Default' and not folder.name.startswith('Profile '):
            continue
        if not (folder / 'Preferences').is_file():
            continue
        metadata = cache.get(folder.name, {})
        profiles.append({'name': metadata.get('name') or folder.name, 'directory': folder.name, 'path': str(folder.resolve())})
    return profiles


def chrome_running():
    if os.name != 'nt':
        return False
    result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq chrome.exe', '/FO', 'CSV', '/NH'],
                            capture_output=True, text=True, check=True,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    return any(row and row[0].lower() == 'chrome.exe' for row in csv.reader(io.StringIO(result.stdout)))


def import_session(source, destination):
    source = Path(source).resolve(strict=True)
    destination = Path(destination).resolve()
    if not (source / 'Preferences').is_file() or not (source.parent / 'Local State').is_file():
        raise ValueError('Chọn thư mục hồ sơ Chrome (Default hoặc Profile 1…), nằm trong User Data.')
    if destination.exists():
        raise ValueError('Hồ sơ đích đã tồn tại. Đặt tên hồ sơ mới để giữ phiên hiện có.')
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError('Hồ sơ nguồn và đích phải nằm ở hai vị trí riêng.')
    if chrome_running():
        raise ValueError('Đóng các cửa sổ Chrome và tiến trình Chrome nền rồi nhập lại. Tool không tự đóng Chrome của bạn.')
    selected = [source.parent / 'Local State'] + [source / name for name in SESSION_FILES if (source / name).exists()]
    for item in selected:
        for path in [item, *item.rglob('*')] if item.is_dir() else [item]:
            if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
                raise ValueError('Không nhập hồ sơ có liên kết thư mục/tệp trong dữ liệu phiên.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.parent / ('session-import-' + uuid.uuid4().hex)
    try:
        (staging / 'Default').mkdir(parents=True)
        shutil.copy2(selected[0], staging / 'Local State')
        for item in selected[1:]:
            target = staging / 'Default' / item.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            if item.is_dir():
                shutil.copytree(item, target)
            else:
                shutil.copy2(item, target)
        staging.rename(destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return destination
