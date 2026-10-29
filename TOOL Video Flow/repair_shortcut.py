from pathlib import Path
import struct
import os
import subprocess
p = Path.home() / 'Desktop' / 'NCTT + Thumbnail.lnk'
b = p.read_bytes()
flags = struct.unpack_from('<I', b, 20)[0]
assert flags & 128
pos = 76
if flags & 1:
    pos += 2 + struct.unpack_from('<H', b, pos)[0]
if flags & 2:
    pos += struct.unpack_from('<I', b, pos)[0]
start = pos
out = bytearray()
root = Path(__file__).resolve().parent
for flag in (4, 8, 16, 32, 64):
    if flags & flag:
        count = struct.unpack_from('<H', b, pos)[0]
        pos += 2
        value = b[pos:pos + count * 2].decode('utf-16le')
        pos += count * 2
        if flag == 16: value = str(root)
        if flag == 32: value = '"' + str(root / 'launcher.py') + '"'
        encoded = value.encode('utf-16le')
        out += struct.pack('<H', len(encoded) // 2) + encoded
p.write_bytes(b[:start] + out + b[pos:])
assert root.is_dir() and (root / 'launcher.py').is_file()
print('Shortcut Unicode paths repaired and verified')
os.startfile(str(p))
