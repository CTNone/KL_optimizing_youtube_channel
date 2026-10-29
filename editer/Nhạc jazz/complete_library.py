from pathlib import Path
import json,csv,io,urllib.request,time,shutil,concurrent.futures,threading
from audit_library import ROOT,NAMES,OUTPUT_ROOT,TRACKS_ROOT
rows=json.loads((OUTPUT_ROOT/'library_audit.json').read_text(encoding='utf-8'))
BASE='https://raw.githubusercontent.com/Windows81/youtube-audio-library/master/'
catalog=list(csv.DictReader(io.StringIO(urllib.request.urlopen(BASE+'music.csv',timeout=60).read().decode('utf-8-sig'))))
lookup={}
def catalog_key(s): return ' '.join(s.replace('’',"'").split()).casefold()
for r in catalog: lookup.setdefault(catalog_key(r['title']),[]).append(r)
cache=ROOT/'.audio_cache'
cache.mkdir(exist_ok=True)
lock=threading.Lock()
def valid(p):
    try:
        data=p.read_bytes()
        if len(data)<10000: return False
        start=0
        if data[:3]==b'ID3': start=10+sum((data[6+i]&127)<<(21-7*i) for i in range(4))
        frames=0; duration=0
        while start+4<len(data):
            h=int.from_bytes(data[start:start+4],'big')
            version=(h>>19)&3; layer=(h>>17)&3; rate=(h>>12)&15; sample=(h>>10)&3
            if h>>21!=2047 or version==1 or layer!=1 or rate in (0,15) or sample==3:
                if frames: break
                start+=1
                if start>100000: return False
                continue
            hz=[44100,48000,32000][sample]//({3:1,2:2,0:4}[version])
            bitrate=([0,32,40,48,56,64,80,96,112,128,160,192,224,256,320] if version==3 else [0,8,16,24,32,40,48,56,64,80,96,112,128,144,160])[rate]*1000
            size=(144 if version==3 else 72)*bitrate//hz+((h>>9)&1)
            if start+size>len(data): return False
            duration+=(1152 if version==3 else 576)/hz
            frames+=1; start+=size
        return frames>100 and duration>5 and len(data)-start<4096
    except Exception: return False
def obtain(item):
    title,artist=item
    sources=[Path(p) for r in rows if (r['title'],r['artist'])==item for p in r['existing']]
    for p in sources:
        if valid(p): return item,p,'existing',''
    matches=lookup.get(catalog_key(f'{title} - {artist}'),[])
    if title=='Lost In Prayer' and artist=='Doug Maxwell/Media Right Productions':
        matches=lookup.get(catalog_key('Lost In Prayer - Doug Maxwell'),[])
    if len(matches)!=1: return item,None,'failed',f'Exact catalog matches: {len(matches)}'
    p=cache/(matches[0]['num']+'.mp3')
    if valid(p): return item,p,'cached',''
    url=BASE+'music/'+matches[0]['num']+'.mp3'
    for attempt in range(3):
        try:
            tmp=p.with_suffix('.download')
            with urllib.request.urlopen(url,timeout=90) as response, tmp.open('wb') as f: shutil.copyfileobj(response,f)
            if not valid(tmp): raise ValueError('Invalid or incomplete MP3')
            tmp.replace(p)
            return item,p,'downloaded',''
        except Exception as e:
            error=str(e)
            time.sleep(attempt+1)
    return item,None,'failed',error
items=list(dict.fromkeys((r['title'],r['artist']) for r in rows))
results={}
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
    for i,result in enumerate(pool.map(obtain,items),1):
        item,p,status,error=result
        results[item]=(p,status,error)
        if i%20==0 or status=='failed': print(f'{i}/{len(items)} {status}: {item[0]} {error}',flush=True)
report=[]
for r in rows:
    folder=TRACKS_ROOT/r['folder']; folder.mkdir(parents=True,exist_ok=True)
    target=folder/r['filename']
    p,status,error=results[(r['title'],r['artist'])]
    if p:
        if not valid(target): shutil.copy2(p,target)
        status='complete' if valid(target) else 'invalid'
    report.append({**{k:r[k] for k in ('folder','no','title','artist')},'status':status,'error':error,'path':str(target.relative_to(OUTPUT_ROOT))})
with (OUTPUT_ROOT/'library_completion_report.csv').open('w',encoding='utf-8-sig',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=report[0].keys()); writer.writeheader(); writer.writerows(report)
for folder in NAMES:
    rr=[r for r in report if r['folder']==folder]
    print(folder,sum(r['status']=='complete' for r in rr),'/',len(rr),flush=True)
print('Downloaded unique tracks:',sum(status=='downloaded' for p,status,error in results.values()),flush=True)
