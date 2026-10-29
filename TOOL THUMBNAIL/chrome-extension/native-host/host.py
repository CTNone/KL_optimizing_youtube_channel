"""Flow TXT native host. Files are limited to the directory chosen in OS UI."""
import base64
import json
import os
from pathlib import Path
import re
import struct
import sys
import hashlib
import uuid

MAX_MESSAGE = 30 * 1024 * 1024


class Files:
    def stage_reference(self, data):
        from PIL import Image, ImageOps
        import io
        match = re.fullmatch(r'data:image/(?:png|jpeg|webp);base64,([A-Za-z0-9+/=]+)', data or '')
        if not match or len(data) > 6 * 1024 * 1024:
            raise ValueError('Ảnh tham chiếu không hợp lệ hoặc quá lớn.')
        payload = base64.b64decode(match[1], validate=True)
        with Image.open(io.BytesIO(payload)) as raw:
            image = ImageOps.exif_transpose(raw).convert('RGB')
            image.thumbnail((2048, 2048))
            output = io.BytesIO()
            image.save(output, format='JPEG', quality=90)
        folder = Path(__file__).parent / 'reference-cache'
        folder.mkdir(exist_ok=True)
        path = folder / ('reference_' + hashlib.sha256(output.getvalue()).hexdigest() + '.jpg')
        if not path.exists():
            path.write_bytes(output.getvalue())
        return {'ok': True, 'path': str(path.resolve())}
    def nctt_job(self, acknowledge=None):
        job_file = Path(__file__).parent / 'nctt-job.json'
        if not job_file.exists():
            return {'ok': True, 'job': None}
        if job_file.stat().st_size > 1024 * 1024:
            raise ValueError('Yêu cầu NCTT quá lớn.')
        job = json.loads(job_file.read_text(encoding='utf-8'))
        if acknowledge:
            if job.get('id') != acknowledge:
                raise ValueError('Yêu cầu NCTT đã thay đổi.')
            job_file.unlink()
            return {'ok': True}
        if not isinstance(job.get('prompt'), str) or not 0 < len(job['prompt']) <= 100000:
            raise ValueError('Prompt NCTT không hợp lệ.')
        if job.get('reference'):
            from PIL import Image, ImageOps
            import io
            source = Path(job['reference']).resolve(strict=True)
            source.relative_to(Path(__file__).resolve().parents[3] / 'TOOL NCTT')
            if source.suffix.lower() not in ('.jpg', '.jpeg', '.png', '.webp') or source.stat().st_size > 20 * 1024 * 1024:
                raise ValueError('Ảnh mẫu NCTT không hợp lệ.')
            with Image.open(source) as raw:
                image = ImageOps.exif_transpose(raw).convert('RGB')
                image.thumbnail((2048, 2048))
                output = io.BytesIO()
                image.save(output, format='JPEG', quality=90)
            payload = output.getvalue()
            if len(payload) > 4 * 1024 * 1024:
                raise ValueError('Ảnh mẫu sau xử lý vượt 4 MB.')
            token = uuid.uuid4().hex
            self.payloads[token] = payload
            job['referenceImage'] = {'token': token, 'size': len(payload), 'ext': 'jpg'}
        return {'ok': True, 'job': job}
    def __init__(self):
        self.directory = None
        self.payloads = {}
        self.saved_hashes = {}
        self.crops = {}

    def crop_image(self, source, persist=False):
        from PIL import Image, ImageOps
        import io
        info = self.inspect_image(source)
        key = (str(Path(source).resolve()), info['sha256'], persist)
        if key in self.crops and (persist or self.crops[key]['token'] in self.payloads):
            return self.crops[key]
        with Image.open(io.BytesIO(self.payloads[info['token']])) as raw:
            image = ImageOps.exif_transpose(raw)
            width, height = image.size
            # Largest exact 16:9 rectangle, anchored to the top. A 4:3
            # source loses 25% of its height; pixel rounding trims <16px.
            unit = min(width // 16, height // 9)
            out_width, out_height = unit * 16, unit * 9
            left = (width - out_width) // 2
            cropped = image.crop((left, 0, left + out_width, out_height))
            output = io.BytesIO()
            cropped.convert('RGB').save(output, format='JPEG', quality=95, subsampling=0)
        payload = output.getvalue()
        token = uuid.uuid4().hex
        self.payloads[token] = payload
        result = {'ok': True, 'token': token, 'width': out_width, 'height': out_height, 'ext': 'jpg', 'size': len(payload)}
        if persist:
            original = Path(source).resolve(strict=True)
            writer = Files()
            writer.directory = original.parent
            result.update(writer.save_bytes(original.stem + '_16x9.jpg', payload))
        self.crops[key] = result
        return result

    def choose(self):
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        try:
            chosen = filedialog.askdirectory(parent=root, title='Flow TXT — Chọn thư mục lưu ảnh', mustexist=True)
        finally:
            root.destroy()
        if not chosen:
            return {'cancelled': True}
        self.directory = Path(chosen).resolve(strict=True)
        return {'path': str(self.directory)}

    def write(self, path, data):
        if self.directory is None:
            raise ValueError('Chưa chọn thư mục Windows.')
        if not re.fullmatch(r'run_[\d_-]+/\d{4,}_\d{2}\.(png|jpg|webp|avif)', path or ''):
            raise ValueError('Đường dẫn ảnh không hợp lệ.')
        match = re.fullmatch(r'data:image/(png|jpeg|webp|avif);base64,([A-Za-z0-9+/=]+)', data or '')
        if not match or len(data) > MAX_MESSAGE:
            raise ValueError('Dữ liệu ảnh không hợp lệ.')
        payload = base64.b64decode(match[2], validate=True)
        if not payload or len(payload) > 20 * 1024 * 1024:
            raise ValueError('Ảnh rỗng hoặc vượt 20 MB.')
        signature = {'png': payload.startswith(b'\x89PNG\r\n\x1a\n'),
                     'jpeg': payload.startswith(b'\xff\xd8\xff'),
                     'webp': payload[:4] == b'RIFF' and payload[8:12] == b'WEBP',
                     'avif': payload[4:8] == b'ftyp' and b'avif' in payload[8:32]}
        if not signature[match[1]]:
            raise ValueError('Chữ ký file không khớp định dạng ảnh.')
        expected = {'png': '.png', 'jpeg': '.jpg', 'webp': '.webp', 'avif': '.avif'}[match[1]]
        if Path(path).suffix != expected:
            raise ValueError('Đuôi file không khớp dữ liệu ảnh.')
        return self.save_bytes(path, payload)

    def inspect_image(self, source):
        from PIL import Image
        original = Path(source or '')
        if not original.is_absolute() or original.suffix.lower() not in ('.png', '.jpg', '.jpeg', '.webp', '.avif'):
            raise ValueError('File tải không phải đường dẫn ảnh tuyệt đối.')
        if not 0 < original.stat().st_size <= 20 * 1024 * 1024:
            raise ValueError('File tải rỗng hoặc vượt 20 MB.')
        # Verify the exact bytes copied, avoiding a file-change race.
        import io
        payload = original.read_bytes()
        if len(payload) > 20 * 1024 * 1024:
            raise ValueError('File tải vượt 20 MB.')
        with Image.open(io.BytesIO(payload)) as image:
            width, height = image.size
            ext = {'PNG': '.png', 'JPEG': '.jpg', 'WEBP': '.webp', 'AVIF': '.avif'}.get(image.format)
            if not ext or max(width, height) < 2048:
                raise ValueError(f'Ảnh {width}×{height} chưa đạt 2K hoặc sai định dạng.')
            image.verify()
        token = uuid.uuid4().hex
        self.payloads = {token: payload}
        return {'ok': True, 'token': token, 'width': width, 'height': height, 'ext': ext[1:], 'size': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()}

    def import_image(self, path, source):
        if self.directory is None:
            raise ValueError('Chưa chọn thư mục Windows.')
        if not re.fullmatch(r'run_[\d_-]+/\d{4,}_\d{2}\.(png|jpg|webp|avif)', path or ''):
            raise ValueError('Đường dẫn ảnh không hợp lệ.')
        image = self.inspect_image(source)
        run = path.split('/')[0]
        if image['sha256'] in self.saved_hashes.get(run, set()):
            raise ValueError('Ảnh 2K trùng dữ liệu với ảnh đã lưu trong lượt này. Không lưu file trùng.')
        result = self.save_bytes(str(Path(path).with_suffix('.' + image['ext'])).replace('\\', '/'), self.payloads[image['token']])
        self.saved_hashes.setdefault(run, set()).add(image['sha256'])
        return {**result, **image}

    def chunk(self, token, offset):
        payload = self.payloads.get(token)
        if payload is None or not isinstance(offset, int) or offset < 0 or offset >= len(payload):
            raise ValueError('Lượt đọc file/offset không hợp lệ.')
        part = payload[offset:offset + 512 * 1024]
        return {'ok': True, 'base64': base64.b64encode(part).decode('ascii'), 'length': len(part)}

    def save_bytes(self, path, payload):
        target = self.directory / path
        # Resolve both before and after mkdir to reject junctions/symlinks.
        target.resolve().relative_to(self.directory)
        target.parent.mkdir(exist_ok=True)
        target.parent.resolve(strict=True).relative_to(self.directory)
        for index in range(10000):
            candidate = target if not index else target.with_name(f'{target.stem} ({index}){target.suffix}')
            try:
                with candidate.open('xb') as stream:
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
                if candidate.stat().st_size != len(payload):
                    raise OSError('Kích thước ảnh lưu không khớp.')
                return {'ok': True, 'filename': str(candidate.resolve())}
            except FileExistsError:
                continue
        raise OSError('Có quá nhiều file trùng tên.')


def read_message(stream):
    header = stream.read(4)
    if not header:
        return None
    if len(header) != 4:
        raise ValueError('Thiếu độ dài thông điệp.')
    length = struct.unpack('<I', header)[0]
    if not 0 < length <= MAX_MESSAGE:
        raise ValueError('Thông điệp quá lớn.')
    body = stream.read(length)
    if len(body) != length:
        raise ValueError('Thông điệp chưa đầy đủ.')
    return json.loads(body.decode('utf-8'))


def main():
    if sys.platform == 'win32':
        import msvcrt
        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
    files = Files()
    while True:
        message = read_message(sys.stdin.buffer)
        if message is None:
            return
        try:
            if message.get('type') == 'choose':
                result = files.choose()
            elif message.get('type') == 'write':
                result = files.write(message.get('path'), message.get('data'))
            elif message.get('type') == 'import':
                result = files.import_image(message.get('path'), message.get('source'))
            elif message.get('type') == 'inspect':
                result = files.inspect_image(message.get('source'))
            elif message.get('type') == 'chunk':
                result = files.chunk(message.get('token'), message.get('offset'))
            elif message.get('type') == 'crop':
                result = files.crop_image(message.get('source'), message.get('persist') is True)
            elif message.get('type') == 'ncttJob':
                result = files.nctt_job(message.get('acknowledge'))
            elif message.get('type') == 'stageReference':
                result = files.stage_reference(message.get('data'))
            else:
                raise ValueError('Lệnh không hợp lệ.')
        except Exception as error:
            result = {'error': str(error)}
        result['id'] = message.get('id')
        output = json.dumps(result, ensure_ascii=False).encode('utf-8')
        sys.stdout.buffer.write(struct.pack('<I', len(output)) + output)
        sys.stdout.buffer.flush()


if __name__ == '__main__':
    main()
