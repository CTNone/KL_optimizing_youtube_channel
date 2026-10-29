"""Read MP4 track geometry/duration without external executables."""
from pathlib import Path
import struct

def mp4_metadata(path):
    stream=Path(path).open('rb')
    result={}
    def scan(start,end,depth=0):
        if depth>6:return
        pos=start
        while pos+8<=end:
            stream.seek(pos);header=stream.read(8)
            if len(header)<8:return
            size,kind=struct.unpack('>I4s',header);offset=8
            if size==1:
                data=stream.read(8)
                if len(data)!=8:return
                size=struct.unpack('>Q',data)[0];offset=16
            if size==0:size=end-pos
            if size<offset or pos+size>end:return
            if kind in (b'moov',b'trak',b'mdia'):
                scan(pos+offset,pos+size,depth+1)
            elif kind==b'tkhd' and size>=offset+8:
                stream.seek(pos+size-8)
                width,height=struct.unpack('>II',stream.read(8))
                width>>=16;height>>=16
                if width and height:result.update(width=width,height=height)
            elif kind==b'mvhd':
                stream.seek(pos+offset);data=stream.read(min(size-offset,40))
                if len(data)>=20 and data[0]==0:
                    scale,duration=struct.unpack('>II',data[12:20])
                elif len(data)>=32 and data[0]==1:
                    scale=struct.unpack('>I',data[20:24])[0];duration=struct.unpack('>Q',data[24:32])[0]
                else:scale=0
                if scale:result['durationSeconds']=round(duration/scale,3)
            pos+=size
    try:scan(0,Path(path).stat().st_size)
    finally:stream.close()
    return result
