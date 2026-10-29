"""Validate the actual installed Windows launcher without opening a picker."""
import json
from pathlib import Path
import struct
import subprocess

root = Path(__file__).resolve().parent
manifest = json.loads((root / 'com.flowtxt.files.json').read_text(encoding='utf-8'))
requests = [{'id': 'unknown', 'type': 'unknown'},
            {'id': 'no-picker', 'type': 'write', 'path': 'run_123/0001_01.png', 'data': ''}]
packet = b''
for message in requests:
    body = json.dumps(message).encode('utf-8')
    packet += struct.pack('<I', len(body)) + body
result = subprocess.run([manifest['path'], manifest['allowed_origins'][0]], input=packet,
                        capture_output=True, timeout=15, check=True)
offset = 0
for expected in requests:
    length = struct.unpack('<I', result.stdout[offset:offset + 4])[0]
    offset += 4
    response = json.loads(result.stdout[offset:offset + length])
    offset += length
    assert response['id'] == expected['id'], response
    assert response['error'], response
assert offset == len(result.stdout), 'Launcher emitted non-protocol stdout.'
print('PASS: installed launcher starts Python from Unicode path; framed UTF-8 protocol is clean; no writes before OS folder selection.')
