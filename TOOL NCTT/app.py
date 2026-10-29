import os, re, csv, json, time, threading, webbrowser, traceback, random, hashlib, uuid
from datetime import datetime, timezone
import tkinter as tk
from tkinter import ttk, messagebox

try:
    import requests
except Exception:
    requests = None
try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.drawing.image import Image as ExcelImage
except Exception:
    Workbook = None

APP_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_ROOT = os.path.join(os.path.dirname(APP_DIR), 'TOOL Video Flow OUTPUT')
EXPORT_DIR = os.path.join(OUTPUT_ROOT, 'NCTT')
CACHE_DIR = os.path.join(APP_DIR, 'cache')
for d in (EXPORT_DIR, CACHE_DIR):
    os.makedirs(d, exist_ok=True)

API_URL = 'https://www.googleapis.com/youtube/v3'
API_KEY_FILE = os.path.join(APP_DIR, 'api_key.txt')
USAGE_FILE = os.path.join(APP_DIR, 'quota_usage.json')
SEARCH_DAILY_LIMIT = 100
OTHER_DAILY_LIMIT = 10000
DEFAULT_RESERVE_SEARCH = 5
DEFAULT_RESERVE_OTHER = 100


def quota_key(api_key):
    return hashlib.sha256(api_key.encode('utf-8')).hexdigest()[:16]

def today_key():
    return datetime.now().strftime('%Y-%m-%d')

def load_usage():
    try:
        with open(USAGE_FILE, 'r', encoding='utf8') as f: data=json.load(f)
        if data.get('date') != today_key(): return {'date': today_key(), 'keys': {}}
        return data
    except Exception: return {'date': today_key(), 'keys': {}}

def save_usage(data):
    tmp=USAGE_FILE+'.tmp'
    with open(tmp,'w',encoding='utf8') as f: json.dump(data,f,ensure_ascii=False,indent=2)
    os.replace(tmp,USAGE_FILE)

def quota_status(api_key):
    data=load_usage(); k=quota_key(api_key)
    u=data.setdefault('keys',{}).setdefault(k,{'search':0,'other':0})
    return u.get('search',0),u.get('other',0)

def quota_reserve_ok(api_key,kind,reserve_search=DEFAULT_RESERVE_SEARCH,reserve_other=DEFAULT_RESERVE_OTHER):
    su,ou=quota_status(api_key)
    return (su+1 <= SEARCH_DAILY_LIMIT-reserve_search) if kind=='search' else (ou+1 <= OTHER_DAILY_LIMIT-reserve_other)

def record_quota(api_key,kind,amount=1):
    data=load_usage(); k=quota_key(api_key)
    u=data.setdefault('keys',{}).setdefault(k,{'search':0,'other':0})
    u[kind]=u.get(kind,0)+amount; save_usage(data)

def quota_text(api_key):
    su,ou=quota_status(api_key)
    return f'Search API: {su}/{SEARCH_DAILY_LIMIT} • API khác: {ou}/{OTHER_DAILY_LIMIT}'

def clean(s):
    return re.sub(r'\s+', ' ', str(s or '')).strip()


def list_text(v):
    if v is None:
        return ''
    if isinstance(v, (list, tuple, set)):
        out=[]
        for x in v:
            if isinstance(x, (list, tuple)):
                out.extend(clean(y) for y in x if clean(y))
            elif clean(x):
                out.append(clean(x))
        return ', '.join(out)
    return clean(v)


def iso_year_bounds(year):
    return f'{year}-01-01T00:00:00Z', f'{int(year)+1}-01-01T00:00:00Z'


def fmt_duration(sec):
    if sec in ('', None): return ''
    sec=int(sec); h, rem=divmod(sec,3600); m,s=divmod(rem,60)
    return f'{h}:{m:02d}:{s:02d}' if h else f'{m}:{s:02d}'


def parse_iso_duration(v):
    if not v: return None
    m=re.fullmatch(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?',v)
    if not m:return None
    h=int(m.group(1) or 0); mi=int(m.group(2) or 0); s=int(m.group(3) or 0)
    return h*3600+mi*60+s


def parse_int(v):
    try:return int(v)
    except:return 0


def parse_channel_keywords(s):
    if not s:return []
    # YouTube commonly stores branding keywords as quoted phrases plus unquoted tokens.
    vals=[]
    for m in re.finditer(r'"([^"]+)"|(\S+)', str(s)):
        vals.append(clean(m.group(1) or m.group(2)))
    return [x for x in vals if x]


def api_get(endpoint, params, api_key, quota_kind='other', reserve_search=DEFAULT_RESERVE_SEARCH, reserve_other=DEFAULT_RESERVE_OTHER, quota_log=None):
    if not requests: raise RuntimeError('Thiếu requests. Hãy chạy run.bat để cài thư viện.')
    if not quota_reserve_ok(api_key,quota_kind,reserve_search,reserve_other):
        su,ou=quota_status(api_key)
        raise RuntimeError(f'TỰ ĐỘNG DỪNG: quota {"Search API" if quota_kind=="search" else "API khác"} đã tới ngưỡng an toàn ({su if quota_kind=="search" else ou}/{SEARCH_DAILY_LIMIT if quota_kind=="search" else OTHER_DAILY_LIMIT}).')
    p=dict(params); p['key']=api_key
    r=requests.get(API_URL+'/'+endpoint,params=p,timeout=30)
    if r.status_code != 200:
        try: msg=r.json().get('error',{}).get('message','')
        except: msg=r.text[:300]
        raise RuntimeError(f'YouTube API {r.status_code}: {msg}')
    record_quota(api_key,quota_kind,1)
    if quota_log: quota_log('Quota: '+quota_text(api_key))
    return r.json()


def search_candidates(api_key, keyword, year, pages, log):
    """Search one year ordered by viewCount, paging until exhausted/page cap."""
    after,before=iso_year_bounds(year)
    token=None; out=[]; seen=set()
    for page in range(1,pages+1):
        params={
            'part':'snippet', 'q':keyword, 'type':'video', 'order':'viewCount',
            'maxResults':50, 'publishedAfter':after, 'publishedBefore':before
        }
        if token: params['pageToken']=token
        data=api_get('search', params, api_key, 'search', quota_log=log)
        for item in data.get('items',[]):
            vid=item.get('id',{}).get('videoId')
            if not vid or vid in seen: continue
            seen.add(vid)
            sn=item.get('snippet',{})
            out.append({'video_id':vid,'title':clean(sn.get('title')),
                        'channel_id':sn.get('channelId',''),'channel':clean(sn.get('channelTitle')),
                        'published_at':sn.get('publishedAt',''),
                        'thumbnail_url':(sn.get('thumbnails',{}).get('high') or sn.get('thumbnails',{}).get('default') or {}).get('url',''),
                        'url':f'https://www.youtube.com/watch?v={vid}'})
        log(f'  Năm {year}: trang API {page}, nhận {len(data.get("items",[]))} kết quả, tổng ứng viên {len(out)}')
        token=data.get('nextPageToken')
        if not token: break
    return out


def batch_video_details(api_key, ids):
    out={}
    for i in range(0,len(ids),50):
        data=api_get('videos',{
            'part':'snippet,contentDetails,statistics','id':','.join(ids[i:i+50])
        },api_key,'other')
        for x in data.get('items',[]):
            sn=x.get('snippet',{}); st=x.get('statistics',{}); cd=x.get('contentDetails',{})
            out[x.get('id')]= {
                'title':clean(sn.get('title')),
                'channel':clean(sn.get('channelTitle')),
                'channel_id':sn.get('channelId',''),
                'published_at':sn.get('publishedAt',''),
                'description':sn.get('description',''),
                'video_tags':sn.get('tags',[]) or [],
                'category_id':sn.get('categoryId',''),
                'duration':parse_iso_duration(cd.get('duration')),
                'views':parse_int(st.get('viewCount')),
                'likes':parse_int(st.get('likeCount')),
                'comments':parse_int(st.get('commentCount')),
                'thumbnail_url':(sn.get('thumbnails',{}).get('maxres') or sn.get('thumbnails',{}).get('high') or sn.get('thumbnails',{}).get('default') or {}).get('url',''),
            }
    return out


def batch_channel_details(api_key, ids):
    out={}
    ids=[x for x in ids if x]
    for i in range(0,len(ids),50):
        data=api_get('channels',{
            'part':'snippet,statistics,brandingSettings','id':','.join(ids[i:i+50])
        },api_key,'other')
        for x in data.get('items',[]):
            sn=x.get('snippet',{}); st=x.get('statistics',{}); br=x.get('brandingSettings',{}).get('channel',{})
            out[x.get('id')]={
                'channel':clean(sn.get('title')),
                'subscribers':parse_int(st.get('subscriberCount')) if not st.get('hiddenSubscriberCount') else None,
                'channel_views':parse_int(st.get('viewCount')),
                'channel_video_count':parse_int(st.get('videoCount')),
                'channel_keywords':parse_channel_keywords(br.get('keywords','')),
                'channel_description':sn.get('description',''),
                'channel_url':f'https://www.youtube.com/channel/{x.get("id")}'
            }
    return out


def token_counts(rows, source='title'):
    stop=set('the a an and or of for to in on with from by is are this that music official video full mix playlist live new best more 2024 2025 2026 2023 hd 4k'.split())
    counts={}
    for r in rows:
        text=r.get(source,'') if source != 'tags' else list_text(r.get('video_tags',[]))
        for w in re.findall(r"[A-Za-zÀ-ỹ0-9']+",str(text).lower()):
            if len(w)<3 or w in stop:continue
            counts[w]=counts.get(w,0)+1
    return sorted(counts.items(), key=lambda x:(-x[1],x[0]))


def phrase_counts(rows, n=2):
    counts={}
    for r in rows:
        words=re.findall(r"[A-Za-zÀ-ỹ0-9']+",r.get('title','').lower())
        for i in range(len(words)-n+1):
            p=' '.join(words[i:i+n])
            if any(len(w)<3 for w in words[i:i+n]):continue
            counts[p]=counts.get(p,0)+1
    return sorted(counts.items(),key=lambda x:(-x[1],x[0]))


def create_run_dir(keyword):
    base=re.sub(r'[^A-Za-z0-9_-]+','_',keyword.lower()).strip('_') or 'research'
    stamp=datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    path=os.path.join(EXPORT_DIR,base+'_'+stamp+'_'+uuid.uuid4().hex[:8])
    os.makedirs(path,exist_ok=False)
    return path


def download_thumb(url, vid, thumb_dir):
    if not url or not requests:return ''
    os.makedirs(thumb_dir,exist_ok=True)
    path=os.path.join(thumb_dir,vid+'.jpg')
    if os.path.exists(path):return path
    try:
        r=requests.get(url,timeout=20); r.raise_for_status()
        with open(path,'wb') as f:f.write(r.content)
        return path
    except Exception:return ''


def export_results(rows, competitors, keywords, base_name, include_thumbs, run_dir=None, log=None):
    run_dir=run_dir or create_run_dir(base_name)
    xlsx=os.path.join(run_dir,base_name+'.xlsx')
    csvv=os.path.join(run_dir,base_name+'.csv')
    fields=['keyword','year','title','views','subscribers','views_per_sub','views_per_day','duration_seconds','duration','published_at','channel','channel_id','channel_keywords','video_tags','category_id','likes','comments','thumbnail_url','video_url']
    with open(csvv,'w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
        for r in rows:
            rr={k:r.get(k,'') for k in fields}; rr['channel_keywords']=list_text(r.get('channel_keywords')); rr['video_tags']=list_text(r.get('video_tags')); w.writerow(rr)
    wb=Workbook(); ws=wb.active; ws.title='VIDEOS'
    headers=['Keyword','Year','Title','Views','Subscribers','Views/Sub','Views/Day','Duration','Published','Channel','Channel ID','Channel Keywords','Video Tags','Category ID','Likes','Comments','Thumbnail URL','Video URL']
    if include_thumbs: headers.append('Thumbnail')
    ws.append(headers)
    for c in range(1,len(headers)+1):
        ws.cell(1,c).font=Font(bold=True); ws.cell(1,c).fill=PatternFill('solid',fgColor='D9EAF7'); ws.cell(1,c).alignment=Alignment(wrap_text=True)
    for r in rows:
        ws.append([r.get('keyword',''),r.get('year',''),r.get('title',''),r.get('views',''),r.get('subscribers',''),r.get('views_per_sub',''),r.get('views_per_day',''),fmt_duration(r.get('duration')),r.get('published_at',''),r.get('channel',''),r.get('channel_id',''),list_text(r.get('channel_keywords')),list_text(r.get('video_tags')),r.get('category_id',''),r.get('likes',''),r.get('comments',''),r.get('thumbnail_url',''),r.get('url','')])
    for col,w in {'A':18,'B':10,'C':65,'D':15,'E':15,'F':13,'G':15,'H':12,'I':24,'J':30,'K':25,'L':42,'M':42,'N':12,'O':14,'P':14,'Q':55,'R':55}.items(): ws.column_dimensions[col].width=w
    if include_thumbs:
        ws.column_dimensions['S'].width=29
        thumb_dir=os.path.join(run_dir,'thumbnails')
        for row_index,r in enumerate(rows,2):
            path=r.get('thumbnail_path') or download_thumb(r.get('thumbnail_url',''),r['video_id'],thumb_dir)
            if path:
                try:
                    image=ExcelImage(path)
                    scale=min(200/image.width,112/image.height)
                    image.width=round(image.width*scale); image.height=round(image.height*scale)
                    ws.add_image(image,f'S{row_index}')
                    ws.row_dimensions[row_index].height=90
                    for cell in ws[row_index]: cell.alignment=Alignment(vertical='center',wrap_text=True)
                    continue
                except Exception as e:
                    if log: log(f'Không chèn được thumbnail {r["video_id"]}: {e}')
            ws.cell(row_index,19,'Không tải được ảnh')
            if log: log(f'Thumbnail không khả dụng: {r["video_id"]}')
    ws.freeze_panes='A2'; ws.auto_filter.ref=ws.dimensions

    wc=wb.create_sheet('COMPETITORS'); wc.append(['Rank','Channel','Subscribers','Videos Found','Total Views','Avg Views','Max Views','Views/Sub Avg','Channel ID','Channel URL'])
    for c in range(1,11):wc.cell(1,c).font=Font(bold=True)
    for i,c in enumerate(competitors,1):wc.append([i,c.get('channel'),c.get('subscribers'),c.get('videos_found'),c.get('total_views'),c.get('avg_views'),c.get('max_views'),c.get('views_per_sub_avg'),c.get('channel_id'),c.get('channel_url')])

    wk=wb.create_sheet('SEO_KEYWORDS'); wk.append(['Keyword/Phrase','Frequency','Avg Views','Max Views','Source'])
    for c in range(1,6):wk.cell(1,c).font=Font(bold=True)
    all_terms=[]
    for term,f in token_counts(rows,'title')[:100]: all_terms.append((term,f,'Title'))
    for term,f in token_counts(rows,'tags')[:100]: all_terms.append((term,f,'Video Tags'))
    for term,f in phrase_counts(rows,2)[:100]: all_terms.append((term,f,'Title Phrase'))
    seen=set()
    for term,f,src in sorted(all_terms,key=lambda x:(-x[1],x[0])):
        key=(term.lower(),src)
        if key in seen:continue
        seen.add(key)
        vals=[]
        for r in rows:
            hay=(r.get('title','')+' '+list_text(r.get('video_tags'))).lower()
            if term.lower() in hay: vals.append(r.get('views') or 0)
        wk.append([term,f,int(sum(vals)/len(vals)) if vals else '',max(vals) if vals else '',src])

    ws2=wb.create_sheet('SUMMARY'); ws2.append(['Metric','Value'])
    for c in range(1,3):ws2.cell(1,c).font=Font(bold=True)
    vals=[('Videos exported',len(rows)),('Minimum requested',rows[0].get('_min_requested','') if rows else ''),('Maximum requested',rows[0].get('_max_requested','') if rows else ''),('Channels',len(competitors)),('Avg views',int(sum((r.get('views') or 0) for r in rows)/len(rows)) if rows else 0),('Top video',rows[0].get('title','') if rows else ''),('Top video views',rows[0].get('views','') if rows else '')]
    vals.append(('Shorts filter',rows[0].get('_shorts_filter','') if rows else 'Xem nhật ký phiên chạy'))
    for x in vals:ws2.append(list(x))

    wb.save(xlsx)
    return xlsx,csvv


def passes_shorts_filter(duration, include_shorts):
    # Public Data API has no Shorts flag; excluding <=3 min is conservative.
    return include_shorts or (isinstance(duration,(int,float)) and duration>180)


def run_research(api_key, keyword, years, min_views, min_videos, max_videos, pages_per_year, exact_phrase, include_thumbs, log, done, reserve_search=DEFAULT_RESERVE_SEARCH, reserve_other=DEFAULT_RESERVE_OTHER, include_shorts=True):
    try:
        if not api_key: raise RuntimeError('Bạn chưa nhập YouTube Data API v3 key.')
        if min_videos>max_videos: raise RuntimeError('Số video tối thiểu không được lớn hơn số video tối đa.')
        if Workbook is None: raise RuntimeError('Thiếu openpyxl. Hãy chạy run.bat để cài thư viện.')
        if include_thumbs:
            try: import PIL.Image
            except ImportError: raise RuntimeError('Thiếu Pillow để chèn thumbnail. Hãy chạy run.bat để cài thư viện.')
        run_dir=create_run_dir(keyword)
        log('Thư mục phiên chạy: '+run_dir)
        log('Dùng YouTube Data API v3 — không scraping HTML.')
        log('Quota ghi nhận trên máy: '+quota_text(api_key))
        log('Bộ lọc Shorts: '+('bao gồm mọi thời lượng.' if include_shorts else 'chỉ giữ video > 3 phút; cũng loại video thường ≤ 3 phút và video không rõ thời lượng.'))
        excluded_short=0
        candidates=[]; accepted_map={}; seen=set(); stopped=False
        for year in sorted(years,reverse=True):
            after,before=iso_year_bounds(year); token=None
            for page in range(1,pages_per_year+1):
                if not quota_reserve_ok(api_key,'search',reserve_search,reserve_other):
                    log('TỰ ĐỘNG DỪNG: Search API đã tới ngưỡng dự phòng.'); stopped=True; break
                params={'part':'snippet','q':keyword,'type':'video','order':'viewCount','maxResults':50,'publishedAfter':after,'publishedBefore':before}
                if token: params['pageToken']=token
                data=api_get('search',params,api_key,'search',reserve_search,reserve_other,log)
                page_items=[]
                for item in data.get('items',[]):
                    vid=item.get('id',{}).get('videoId')
                    if not vid or vid in seen: continue
                    seen.add(vid); sn=item.get('snippet',{})
                    page_items.append({'video_id':vid,'title':clean(sn.get('title')),'channel_id':sn.get('channelId',''),'channel':clean(sn.get('channelTitle')),'published_at':sn.get('publishedAt',''),'thumbnail_url':(sn.get('thumbnails',{}).get('high') or sn.get('thumbnails',{}).get('default') or {}).get('url',''),'url':f'https://www.youtube.com/watch?v={vid}'})
                candidates.extend(page_items)
                log(f'  Năm {year}: trang API {page}, nhận {len(data.get("items",[]))} kết quả, tổng ứng viên {len(candidates)}')
                if page_items:
                    details=batch_video_details(api_key,[x['video_id'] for x in page_items])
                    for c in page_items:
                        d=details.get(c['video_id']);
                        if not d: continue
                        title=d.get('title') or c.get('title',''); pub=d.get('published_at') or c.get('published_at',''); y=pub[:4]; views=d.get('views',0)
                        if y not in years or (exact_phrase and exact_phrase.lower() not in title.lower()) or views < min_views: continue
                        if not passes_shorts_filter(d.get('duration'),include_shorts):
                            excluded_short+=1
                            continue
                        r={**c,**d}; r['keyword']=keyword; r['year']=y; r['url']=c['url']; accepted_map[r['video_id']]=r
                    accepted=sorted(accepted_map.values(),key=lambda r:(r.get('views') or 0),reverse=True)
                    if len(accepted)>=max_videos:
                        accepted=accepted[:max_videos]; log(f'ĐÃ ĐỦ {max_videos} video đạt bộ lọc → tự động dừng tìm kiếm.'); stopped=True; break
                token=data.get('nextPageToken')
                if not token: break
            if stopped: break
        accepted=sorted(accepted_map.values(),key=lambda r:(r.get('views') or 0),reverse=True)[:max_videos]
        log(f'Tổng ứng viên từ Search API: {len(candidates)}')
        log(f'Video đạt bộ lọc: {len(accepted)}')
        if not include_shorts: log(f'Đã loại {excluded_short} ứng viên do thời lượng ≤ 3 phút hoặc không rõ thời lượng.')
        if len(accepted)<min_videos: log(f'CẢNH BÁO: chỉ tìm thấy {len(accepted)} video, thấp hơn mức tối thiểu {min_videos}.')
        channel_ids=list({r.get('channel_id') for r in accepted if r.get('channel_id')})
        log(f'Đang lấy thông tin {len(channel_ids)} kênh...')
        channels=batch_channel_details(api_key,channel_ids) if channel_ids else {}
        now=datetime.now(timezone.utc)
        for r in accepted:
            r.update(channels.get(r.get('channel_id'),{})); sub=r.get('subscribers'); r['views_per_sub']=round(r.get('views',0)/sub,2) if sub else ''
            try:
                dt=datetime.fromisoformat(r['published_at'].replace('Z','+00:00')); days=max((now-dt).total_seconds()/86400,1); r['views_per_day']=round(r.get('views',0)/days,1)
            except Exception:r['views_per_day']=''
        cmap={}
        for r in accepted:
            cid=r.get('channel_id')
            if not cid: continue
            c=cmap.setdefault(cid,{'channel':r.get('channel'),'subscribers':r.get('subscribers') or 0,'videos_found':0,'total_views':0,'max_views':0,'channel_id':cid,'channel_url':r.get('channel_url') or f'https://www.youtube.com/channel/{cid}'})
            c['videos_found']+=1;c['total_views']+=r.get('views') or 0;c['max_views']=max(c['max_views'],r.get('views') or 0);c['subscribers']=max(c['subscribers'],r.get('subscribers') or 0)
        competitors=list(cmap.values())
        for c in competitors:
            c['avg_views']=round(c['total_views']/c['videos_found']) if c['videos_found'] else 0
            vals=[r.get('views_per_sub') for r in accepted if r.get('channel_id')==c['channel_id'] and isinstance(r.get('views_per_sub'),(int,float))]; c['views_per_sub_avg']=round(sum(vals)/len(vals),2) if vals else ''
        competitors.sort(key=lambda x:(x.get('subscribers') or 0),reverse=True)
        for r in accepted:r['_min_requested']=min_videos;r['_max_requested']=max_videos;r['_shorts_filter']='Bao gồm mọi thời lượng' if include_shorts else 'Chỉ video > 3 phút (lọc Shorts theo thời lượng)'
        base=re.sub(r'[^A-Za-z0-9_-]+','_',keyword.lower()).strip('_') or 'research'
        xlsx,csvv=export_results(accepted,competitors,[],base,include_thumbs,run_dir,log)
        log('Quota cuối phiên: '+quota_text(api_key))
        done(xlsx,csvv,accepted,competitors,[],[])
    except Exception as e:
        log('LỖI/TỰ ĐỘNG DỪNG: '+str(e)); log('Quota hiện tại: '+(quota_text(api_key) if api_key else '')); done(None,None,[],[],[],[])


class App(tk.Tk):
    def __init__(self):
        super().__init__(); self.title('NCTT • Nghiên cứu thị trường'); self.geometry('1040x820'); self.minsize(950,700); self.build()
    def build(self):
        pad={'padx':8,'pady':5}
        self.research_panel=ttk.Frame(self)
        self.research_panel.pack(fill='both',expand=True)
        canvas=tk.Canvas(self.research_panel,highlightthickness=0)
        scroll=ttk.Scrollbar(self.research_panel,orient='vertical',command=canvas.yview)
        scroll.pack(side='right',fill='y');canvas.pack(side='left',fill='both',expand=True)
        canvas.configure(yscrollcommand=scroll.set)
        body=ttk.Frame(canvas)
        window=canvas.create_window(0,0,window=body,anchor='nw')
        body.bind('<Configure>',lambda event:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda event:canvas.itemconfigure(window,width=event.width))
        def wheel(event):
            if str(event.widget).startswith(str(self.research_panel)+'.') and event.widget.winfo_class()!='Text':
                canvas.yview_scroll(-1 if event.delta>0 else 1,'units')
        self.bind_all('<MouseWheel>',wheel,add='+')
        self.after_idle(self.research_panel.lift)
        top=ttk.Frame(body);top.pack(fill='x',**pad)
        ttk.Label(top,text='YOUTUBE MUSIC MARKET RESEARCH — API v3',font=('Segoe UI',18,'bold')).pack(anchor='w')
        ttk.Label(top,text='YouTube Data API v3 • Không scraping HTML • Không tự động nghe/like/comment/view').pack(anchor='w')
        self.quota_label=ttk.Label(top,text='Quota hôm nay: chưa kiểm tra',font=('Segoe UI',10,'bold')); self.quota_label.pack(anchor='w')
        f=ttk.LabelFrame(body,text='1. YouTube API');f.pack(fill='x',**pad)
        f.columnconfigure(1,weight=1)
        ttk.Label(f,text='API Key').grid(row=0,column=0,sticky='w',**pad)
        self.api=tk.StringVar(value='')
        try:
            if os.path.exists(API_KEY_FILE): self.api.set(open(API_KEY_FILE,'r',encoding='utf8').read().strip())
        except: pass
        ttk.Entry(f,textvariable=self.api,show='*').grid(row=0,column=1,sticky='ew',**pad)
        ttk.Button(f,text='Lưu API key',command=self.save_key).grid(row=0,column=2,**pad)
        ttk.Button(f,text='Xem quota',command=self.refresh_quota).grid(row=0,column=3,**pad)
        ttk.Label(f,text='API key chỉ lưu trong máy này ở api_key.txt').grid(row=1,column=1,sticky='w',**pad)

        g=ttk.LabelFrame(body,text='2. Bộ lọc nghiên cứu');g.pack(fill='x',**pad)
        for i in range(4):g.columnconfigure(i,weight=1)
        self.keyword=tk.StringVar(value='christmas jazz'); self.exact=tk.StringVar(value='christmas jazz')
        self.years=tk.StringVar(value='2025,2024'); self.minviews=tk.StringVar(value='1000000')
        self.minvid=tk.StringVar(value='20'); self.maxvid=tk.StringVar(value='100'); self.pages=tk.StringVar(value='10'); self.reserve_search=tk.StringVar(value=str(DEFAULT_RESERVE_SEARCH)); self.reserve_other=tk.StringVar(value=str(DEFAULT_RESERVE_OTHER))
        fields=[('Keyword',self.keyword),('Title phải chứa',self.exact),('Năm, ví dụ 2025,2024',self.years),('View tối thiểu',self.minviews),('Video tối thiểu',self.minvid),('Video tối đa',self.maxvid),('Trang Search tối đa / năm',self.pages),('Dự phòng Search quota',self.reserve_search),('Dự phòng API khác',self.reserve_other)]
        for idx,(lab,var) in enumerate(fields):
            row=idx//4*2; col=idx%4
            ttk.Label(g,text=lab).grid(row=row,column=col,sticky='w',**pad); ttk.Entry(g,textvariable=var).grid(row=row+1,column=col,sticky='ew',**pad)
        self.include_shorts=tk.BooleanVar(value=False)
        ttk.Checkbutton(g,text='Bao gồm video Shorts (lọc theo thời lượng)',variable=self.include_shorts).grid(row=7,column=0,columnspan=2,sticky='w',**pad)
        ttk.Label(g,text='Bỏ chọn: chỉ giữ video > 3 phút; cũng loại video thường ≤ 3 phút. API không xác định chính xác Shorts.',wraplength=960).grid(row=8,column=0,columnspan=4,sticky='w',**pad)
        self.thumbs=tk.BooleanVar(value=True); ttk.Checkbutton(g,text='Chèn thumbnail vào báo cáo Excel',variable=self.thumbs).grid(row=4,column=0,columnspan=2,sticky='w',**pad)
        ttk.Label(g,text='Search: 1 trang ≤ 50 ứng viên; tăng số trang để tìm rộng hơn, dùng thêm quota. Dừng sớm khi đủ video tối đa.').grid(row=6,column=0,columnspan=4,sticky='w',**pad)
        ttk.Label(g,text='Quota: ghi nhận usage theo ngày trên máy, hiển thị trước/trong/sau khi chạy và tự dừng trước ngưỡng dự phòng.').grid(row=5,column=0,columnspan=4,sticky='w',**pad)

        b=ttk.Frame(body);b.pack(fill='x',**pad)
        self.start=ttk.Button(b,text='🔍 BẮT ĐẦU NGHIÊN CỨU',command=self.start_research);self.start.pack(side='left')
        ttk.Button(b,text='📂 Mở exports',command=lambda:webbrowser.open(EXPORT_DIR)).pack(side='left',padx=8)
        self.progress=ttk.Progressbar(b,mode='indeterminate');self.progress.pack(side='left',fill='x',expand=True,padx=8)
        o=ttk.LabelFrame(body,text='3. Nhật ký');o.pack(fill='both',expand=True,**pad)
        self.logbox=tk.Text(o,height=10,wrap='word');self.logbox.pack(fill='both',expand=True,padx=8,pady=8)
        r=ttk.LabelFrame(body,text='4. Kết quả');r.pack(fill='x',**pad);self.result=tk.StringVar(value='Chưa chạy.');ttk.Label(r,textvariable=self.result,wraplength=980).pack(anchor='w',padx=10,pady=10)
    def refresh_quota(self):
        key=self.api.get().strip(); self.quota_label.config(text='Quota hôm nay: '+(quota_text(key) if key else 'chưa có API key'))

    def save_key(self):
        key=self.api.get().strip()
        if not key: messagebox.showwarning('API key','Chưa có API key.');return
        with open(API_KEY_FILE,'w',encoding='utf8') as f:f.write(key)
        messagebox.showinfo('Đã lưu','API key đã được lưu cục bộ.')
    def log(self,msg): self.after(0,lambda:(self.logbox.insert('end',msg+'\n'),self.logbox.see('end')))
    def start_research(self):
        try:
            mv=max(0,int(self.minviews.get())); mn=max(1,int(self.minvid.get())); mx=max(1,int(self.maxvid.get())); pages=max(1,min(50,int(self.pages.get())))
        except: messagebox.showerror('Input lỗi','View, số video và số trang phải là số.');return
        years={x.strip() for x in self.years.get().split(',') if x.strip()}
        if not years: messagebox.showerror('Input lỗi','Hãy nhập ít nhất một năm.');return
        if mn>mx: messagebox.showerror('Input lỗi','Video tối thiểu không được lớn hơn video tối đa.');return
        if not self.api.get().strip(): messagebox.showerror('API key','Bạn cần nhập YouTube Data API v3 key.');return
        self.start.config(state='disabled');self.progress.start(10);self.logbox.delete('1.0','end');self.result.set('Đang chạy...')
        try: rs=max(0,int(self.reserve_search.get())); ro=max(0,int(self.reserve_other.get()))
        except: messagebox.showerror('Input lỗi','Quota dự phòng phải là số.'); return
        self.quota_label.config(text='Quota hôm nay: '+quota_text(self.api.get().strip()))
        args=(self.api.get().strip(),self.keyword.get().strip(),years,mv,mn,mx,pages,self.exact.get().strip(),self.thumbs.get(),self.log,self.finished,rs,ro,self.include_shorts.get())
        threading.Thread(target=run_research,args=args,daemon=True).start()
    def finished(self,xlsx,csvv,rows,competitors,kw,watch):
        def ui():
            self.progress.stop();self.start.config(state='normal')
            if not xlsx:self.result.set('Không tạo được file. Xem Nhật ký.');return
            self.quota_label.config(text='Quota hôm nay: '+quota_text(self.api.get().strip()))
            self.result.set(f'Hoàn tất: {len(rows)} video • {len(competitors)} kênh.\nExcel: {xlsx}\nCSV: {csvv}')
            if messagebox.askyesno('Hoàn tất','Đã tạo Excel/CSV. Mở thư mục kết quả phiên này?'):webbrowser.open(os.path.dirname(xlsx))
        self.after(0,ui)

if __name__=='__main__':
    import sys
    if '--research-only' in sys.argv:
        App().mainloop()
    else:
        from studio import main
        raise SystemExit(main())
