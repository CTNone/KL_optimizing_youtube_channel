from pathlib import Path
import openpyxl, json, re, csv
ROOT=Path(__file__).resolve().parent
OUTPUT_ROOT=ROOT.parents[1]/'TOOL Video Flow OUTPUT'/'Music Library'
OUTPUT_ROOT.mkdir(parents=True,exist_ok=True)
TRACKS_ROOT=OUTPUT_ROOT/'Tracks'
NAMES=['Chrismas','Winter_Cozy','Cafe_Jazz','Study_Reading','Deep_Relax','Romantic_Dinner']
def norm(s):
    return re.sub(r'[^\w]+','',s.casefold())
def safe(s):
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',s).strip().rstrip('.')
files=[p for base in (ROOT,TRACKS_ROOT) if base.exists() for p in base.rglob('*') if p.is_file() and p.suffix.lower() in ('.mp3','.wav','.m4a','.ogg','.flac')]
w=openpyxl.load_workbook(ROOT/'YouTube_Library_600_Tracks.xlsx',read_only=True,data_only=True)
rows=[]
for sheet,folder in zip([s for s in w if s.title!='README'],NAMES):
    for r in list(sheet.values)[4:]:
        if not isinstance(r[0],(int,float)) or not r[1] or not r[2]: continue
        title,artist=r[1:3]
        key=norm(safe(f'{title} - {artist}'))
        matches=[p for p in files if norm(re.sub(r'^\d+\s*-\s*','',p.stem))==key and p.stat().st_size>10000]
        rows.append(dict(sheet=sheet.title,folder=folder,no=int(r[0]),title=title,artist=artist,filename=safe(f'{int(r[0]):03d} - {title} - {artist}.mp3'),existing=[str(p.resolve()) for p in matches]))
(OUTPUT_ROOT/'library_audit.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
for folder in NAMES:
    rr=[r for r in rows if r['folder']==folder]
    print(json.dumps(dict(folder=folder,expected=len(rr),unique=len(set((r['title'],r['artist']) for r in rr)),available_anywhere=sum(bool(r['existing']) for r in rr),missing=sum(not r['existing'] for r in rr)),ensure_ascii=False))
print('Unique missing tracks:',len(set((r['title'],r['artist']) for r in rows if not r['existing'])))
print('Other file types:',dict((ext,sum(p.suffix.lower()==ext for base in (ROOT,TRACKS_ROOT) if base.exists() for p in base.rglob('*') if p.is_file())) for ext in ['.mp4','.webm','.part']))
