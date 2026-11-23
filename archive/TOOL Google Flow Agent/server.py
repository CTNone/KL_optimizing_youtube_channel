"""Local REST bridge for the existing, logged-in Google Flow Chrome controller."""
from __future__ import annotations

import base64
import json
import mimetypes
import re
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
THUMBNAIL = PROJECT / 'TOOL THUMBNAIL'
VIDEO = PROJECT / 'TOOL Video Flow'
UPLOADS = ROOT / 'uploads'
OUTPUTS = ROOT / 'outputs'
for path in (UPLOADS, OUTPUTS):
    path.mkdir(parents=True, exist_ok=True)

import sys
sys.path.insert(0, str(THUMBNAIL))
sys.path.insert(0, str(VIDEO))
from video_flow import StudioFlow
from chrome_profile import discover_profiles

VIDEO_CREDIT_COST = 10
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
LOCK = threading.RLock()
STATE = {'connected': False, 'running': False, 'logs': [], 'items': [], 'job': None,
         'pending_video': None, 'error': None}


def on_state(value):
    with LOCK:
        STATE.update(value)
        if value.get('finished'):
            STATE['running'] = False
            if STATE.get('job'):
                STATE['job']['status'] = 'completed' if not value.get('error') else 'failed'
                STATE['job']['message'] = value.get('error') or (value.get('logs') or ['Hoàn tất'])[-1]


def on_error(value):
    with LOCK:
        STATE['error'] = str(value)


flow = StudioFlow(on_state, on_error)


def classify_intent(text: str) -> str:
    """Conservative local classifier; callers can explicitly override with intent."""
    normalized = text.casefold()
    video_terms = ('video', 'clip', 'veo', 'image to video', 'ảnh thành video',
                   'tạo video', 'làm video', 'chuyển ảnh thành video', 'image-to-video')
    image_terms = ('thumbnail', 'ảnh', 'image', 'hình', 'vẽ', 'tạo ảnh', 'generate image')
    has_video = any(term in normalized for term in video_terms)
    has_image = any(term in normalized for term in image_terms)
    if has_video:
        return 'video'
    if has_image:
        return 'image'
    return 'unknown'


def safe_media_path(relative: str) -> Path:
    candidate = (ROOT / unquote(relative)).resolve(strict=True)
    if candidate != ROOT and ROOT not in candidate.parents:
        raise ValueError('Đường dẫn media không hợp lệ.')
    if not candidate.is_file():
        raise ValueError('Không tìm thấy tệp media.')
    return candidate


class Handler(BaseHTTPRequestHandler):
    server_version = 'FlowAgentLocal/1.0'

    def log_message(self, *_args):
        pass

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        size = int(self.headers.get('Content-Length', '0'))
        if size > MAX_UPLOAD_BYTES * 2:
            raise ValueError('Yêu cầu vượt quá giới hạn kích thước.')
        return json.loads(self.rfile.read(size) or b'{}')

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == '/api/state':
            with LOCK:
                view = dict(STATE)
                pending = STATE.get('pending_video')
                view['pending_video'] = ({'id': pending['id'], 'prompt': pending['prompt'],
                    'question': 'Bạn có muốn tôi bắt đầu tạo 1 video này với chi phí là 10 tín dụng không?',
                    'cost': VIDEO_CREDIT_COST} if pending else None)
                return self.send_json(view)
        if parsed.path == '/api/profiles':
            return self.send_json({'profiles': discover_profiles()})
        if parsed.path == '/api/media':
            rows = []
            for file in OUTPUTS.rglob('*'):
                if file.is_file() and file.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp', '.mp4', '.webm'):
                    relative = file.relative_to(ROOT).as_posix()
                    rows.append({'name': file.name, 'url': '/media/' + relative, 'referenceId': relative,
                                 'type': mimetypes.guess_type(file.name)[0] or 'application/octet-stream'})
            return self.send_json({'media': rows[-100:]})
        if parsed.path == '/':
            return self.serve(ROOT / 'index.html')
        if parsed.path.startswith('/media/'):
            try:
                return self.serve(safe_media_path(parsed.path[len('/media/'):]))
            except (OSError, ValueError) as error:
                return self.send_json({'error': str(error)}, 404)
        return self.send_json({'error': 'Không tìm thấy endpoint.'}, 404)

    def serve(self, path):
        data = path.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', mimetypes.guess_type(path.name)[0] or 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        try:
            body = self.read_json()
            path = urlparse(self.path).path
            routes = {'/api/connect': self.connect, '/api/upload': self.upload,
                      '/api/chat': self.chat, '/api/approve': self.approve,
                      '/api/decline': self.decline, '/api/cancel': self.cancel}
            if path not in routes:
                return self.send_json({'error': 'Không tìm thấy endpoint.'}, 404)
            return routes[path](body)
        except Exception as error:
            return self.send_json({'error': str(error)}, 400)

    def connect(self, body):
        profile = body.get('profile')
        known = {item['path'] for item in discover_profiles()}
        if profile not in known:
            return self.send_json({'error': 'Hãy chọn hồ sơ Chrome được liệt kê.'}, 400)
        future = flow.submit(flow.connect_existing(profile))
        try:
            tabs = future.result(timeout=75)
        except Exception as error:
            return self.send_json({'error': str(error)}, 400)
        with LOCK:
            STATE['connected'] = True
            STATE['tabs'] = tabs
            STATE['error'] = None
        return self.send_json({'connected': True, 'tabs': tabs})

    def upload(self, body):
        name = Path(body.get('name', 'upload.png')).name
        data_url = body.get('dataUrl', '')
        match = re.fullmatch(r'data:image/(?:png|jpeg|webp);base64,([A-Za-z0-9+/=]+)', data_url)
        if not match:
            return self.send_json({'error': 'Chỉ hỗ trợ ảnh PNG, JPG hoặc WebP.'}, 400)
        raw = base64.b64decode(match.group(1), validate=True)
        if not raw or len(raw) > MAX_UPLOAD_BYTES:
            return self.send_json({'error': 'Ảnh phải nhỏ hơn 20 MB.'}, 400)
        extension = Path(name).suffix.lower()
        if extension not in ('.png', '.jpg', '.jpeg', '.webp'):
            extension = '.jpg' if 'jpeg' in data_url[:32] else '.' + data_url[11:data_url.index(';')]
        target = UPLOADS / (uuid.uuid4().hex + extension)
        target.write_bytes(raw)
        return self.send_json({'id': 'uploads/' + target.name, 'name': name, 'url': '/media/uploads/' + target.name,
                               'path': str(target)})

    def chat(self, body):
        text = str(body.get('message', '')).strip()
        intent = body.get('intent') or classify_intent(text)
        if not text:
            return self.send_json({'error': 'Nhập prompt trước.'}, 400)
        if intent not in ('image', 'video'):
            return self.send_json({'intent': 'unknown', 'reply': 'Bạn muốn tạo ảnh hay tạo video? Hãy ghi rõ loại nội dung.'})
        with LOCK:
            if not STATE.get('connected'):
                return self.send_json({'error': 'Kết nối Chrome có Flow đang đăng nhập trước.'}, 409)
            if STATE.get('running') or flow.busy:
                return self.send_json({'error': 'Đang có lượt chạy. Vui lòng chờ hoàn tất.'}, 409)
        reference_id = body.get('referenceId')
        reference = None
        if reference_id:
            reference_key = str(reference_id).replace('\\', '/')
            if not (reference_key.startswith('uploads/') or reference_key.startswith('outputs/')):
                return self.send_json({'error': 'Ảnh tham chiếu không thuộc thư viện local.'}, 400)
            reference = str(safe_media_path(reference_key))
            if Path(reference).suffix.lower() not in ('.png', '.jpg', '.jpeg', '.webp'):
                return self.send_json({'error': 'Chỉ có thể dùng ảnh làm tham chiếu.'}, 400)
        if intent == 'video':
            if not reference:
                return self.send_json({'error': 'Video cần chọn hoặc upload một ảnh tham chiếu.'}, 400)
            pending = {'id': uuid.uuid4().hex, 'prompt': text, 'reference': reference,
                       'referenceName': Path(reference).name, 'model': body.get('videoModel', 'Veo 3.1 - Lite'),
                       'mode': body.get('videoMode', 'Thành phần'), 'ratio': body.get('ratio', '16:9'),
                       'count': 1, 'cost': VIDEO_CREDIT_COST}
            with LOCK:
                if STATE.get('running') or flow.busy:
                    return self.send_json({'error': 'Đang có lượt chạy. Vui lòng chờ hoàn tất.'}, 409)
                if STATE.get('pending_video'):
                    return self.send_json({'error': 'Hãy phê duyệt hoặc từ chối action card video hiện tại trước.'}, 409)
                STATE['pending_video'] = pending
            return self.send_json({'intent': 'video', 'reply': 'Video cần bạn phê duyệt trước khi gửi sang Google Flow.',
                'actionCard': {'id': pending['id'], 'question': 'Bạn có muốn tôi bắt đầu tạo 1 video này với chi phí là 10 tín dụng không?',
                               'cost': VIDEO_CREDIT_COST, 'prompt': text}})
        model = body.get('imageModel', 'Nano Banana 2 Lite')
        count = int(body.get('imageCount', 1))
        if not 1 <= count <= 4:
            return self.send_json({'error': 'Số ảnh phải nằm trong khoảng 1–4.'}, 400)
        job_id = uuid.uuid4().hex
        destination = OUTPUTS / job_id
        destination.mkdir(parents=True)
        with LOCK:
            if STATE.get('running') or flow.busy:
                return self.send_json({'error': 'Đang có lượt chạy. Vui lòng chờ hoàn tất.'}, 409)
            STATE.update({'running': True, 'job': {'id': job_id, 'type': 'image', 'status': 'running'}, 'error': None})
        future = flow.submit(flow.start(text, reference, model, count, str(destination)))
        future.add_done_callback(lambda f: self.job_done(f, job_id))
        return self.send_json({'intent': 'image', 'jobId': job_id, 'reply': 'Đã gửi yêu cầu tạo ảnh lên Flow.'}, 202)

    def approve(self, body):
        job_id = uuid.uuid4().hex
        folder = OUTPUTS / job_id
        folder.mkdir(parents=True)
        with LOCK:
            pending = STATE.get('pending_video')
            if not pending or body.get('id') != pending['id']:
                return self.send_json({'error': 'Yêu cầu phê duyệt đã hết hạn hoặc không hợp lệ.'}, 409)
            if flow.busy or STATE.get('running'):
                return self.send_json({'error': 'Một lượt khác đang chạy.'}, 409)
            STATE['pending_video'] = None  # Consume confirmation before scheduling.
            STATE.update({'running': True, 'job': {'id': job_id, 'type': 'video', 'status': 'running'}, 'error': None})
        future = flow.submit(flow.start_video(pending['prompt'], pending['reference'], pending['model'],
            pending['mode'], pending['ratio'], 1, str(folder)))
        future.add_done_callback(lambda f: self.job_done(f, job_id))
        return self.send_json({'jobId': job_id, 'reply': 'Đã phê duyệt. Đang gửi một yêu cầu video lên Flow.'}, 202)

    def decline(self, body):
        with LOCK:
            pending = STATE.get('pending_video')
            if not pending or body.get('id') != pending['id']:
                return self.send_json({'error': 'Action card đã hết hạn hoặc không hợp lệ.'}, 409)
            STATE['pending_video'] = None
        return self.send_json({'declined': True})

    def job_done(self, future, job_id):
        error = None
        try:
            future.result()
        except Exception as exc:
            error = str(exc)
        with LOCK:
            if STATE.get('job', {}).get('id') == job_id:
                STATE['running'] = False
                STATE['job']['status'] = 'failed' if error else 'completed'
                STATE['job']['message'] = error or 'Hoàn tất.'
                if error:
                    STATE['error'] = error

    def cancel(self, _body):
        future = flow.submit(flow.stop())
        future.add_done_callback(lambda _f: None)
        return self.send_json({'stopping': True})


if __name__ == '__main__':
    host, port = '127.0.0.1', 8765
    print(f'Google Flow Agent local: http://{host}:{port}')
    ThreadingHTTPServer((host, port), Handler).serve_forever()
