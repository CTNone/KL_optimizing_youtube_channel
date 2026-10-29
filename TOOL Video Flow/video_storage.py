"""Validation and atomic persistence for downloaded video artifacts."""
from pathlib import Path
import hashlib
import json
import os
import time

def atomic_json(path, value):
    path=Path(path)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    for attempt in range(5):
        try:
            os.replace(temporary,path)
            return
        except PermissionError:
            if attempt==4:raise
            time.sleep(.1)

def validate_video(path):
    path=Path(path)
    size=path.stat().st_size
    with path.open('rb') as stream:header=stream.read(64)
    if size<16 or not (header[4:8] in (b'ftyp',b'moov',b'mdat',b'wide') or header[:4]==b'\x1aE\xdf\xa3'):
        raise ValueError('File tải về không có cấu trúc video hợp lệ (có thể là trang lỗi/HTML).')
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
    from video_metadata import mp4_metadata
    geometry=mp4_metadata(path) if header[:4]!=b'\x1aE\xdf\xa3' else {}
    return {'bytes':size,'sha256':digest.hexdigest(),**geometry}

def record_download(record,index,source,filename,resolution):
    for field,value in [('files',filename),('resolutions',resolution)]:
        rows=record.setdefault(field,[])
        while len(rows)<index:rows.append('')
        rows[index-1]=value
    entries=record.setdefault('downloads',{})
    entries[str(index)]={'source':source,'filename':filename,'resolution':resolution}
    if Path(filename).is_file():entries[str(index)].update(validate_video(filename))

