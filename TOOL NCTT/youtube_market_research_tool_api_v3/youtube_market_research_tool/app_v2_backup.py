import os, re, csv, json, time, threading, webbrowser, traceback, random
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
except Exception:
    Workbook = None

APP_DIR = os.path.dirname(os.path.abspath(__file__))
EXPORT_DIR = os.path.join(APP_DIR, 'exports')
THUMB_DIR = os.path.join(APP_DIR, 'thumbnails')
CACHE_DIR = os.path.join(APP_DIR, 'cache')
for d in (EXPORT_DIR, THUMB_DIR, CACHE_DIR):
    os.makedirs(d, exist_ok=True)

API_URL = 'https://www.googleapis.com/youtube/v3'
API_KEY_FILE = os.path.join(APP_DIR, 'api_key.txt')


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


def api_get(endpoint, params, api_key):
    if not requests: raise RuntimeError('Thiếu requests. Hãy chạy run.bat để cài thư viện.')
    p=dict(params); p['key']=api_key
    r=requests.get(API_URL+'/'+endpoint, params=p, timeout=30)
    if r.status_code != 200:
        try: msg=r.json().get('error',{}).get('message','')
        except: msg=r.text[:300]
        raise RuntimeError(f'YouTube API {r.status_code}: {msg}')
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
        data=api_get('search', params, api_key)
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
        },api_key)
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
        },api_key)
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


def download_thumb(url, vid):
    if not url or not requests:return ''
    path=os.path.join(THUMB_DIR,vid+'.jpg')
    if os.path.exists(path):return path
    try:
        r=requests.get(url,timeout=20); r.raise_for_status()
        with open(path,'wb') as f:f.write(r.content)
        return path
    except Exception:return ''


def export_results(rows, competitors, keywords, base_name, include_thumbs):
    stamp=datetime.now().strftime('%Y%m%d_%H%M%S')
    xlsx=os.path.join(EXPORT_DIR,base_name+'_'+stamp+'.xlsx')
    csvv=os.path.join(EXPORT_DIR,base_name+'_'+stamp+'.csv')
    fields=['keyword','year','title','views','subscribers','views_per_sub','views_per_day','duration_seconds','duration','published_at','channel','channel_id','channel_keywords','video_tags','category_id','likes','comments','thumbnail_url','video_url']
    with open(csvv,'w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
        for r in rows:
            rr={k:r.get(k,'') for k in fields}; rr['channel_keywords']=list_text(r.get('channel_keywords')); rr['video_tags']=list_text(r.get('video_tags')); w.writerow(rr)
    wb=Workbook(); ws=wb.active; ws.title='VIDEOS'
    headers=['Keyword','Year','Title','Views','Subscribers','Views/Sub','Views/Day','Duration','Published','Channel','Channel ID','Channel Keywords','Video Tags','Category ID','Likes','Comments','Thumbnail URL','Video URL']
    ws.append(headers)
    for c in range(1,len(headers)+1):
        ws.cell(1,c).font=Font(bold=True); ws.cell(1,c).fill=PatternFill('solid',fgColor='D9EAF7'); ws.cell(1,c).alignment=Alignment(wrap_text=True)
    for r in rows:
        ws.append([r.get('keyword',''),r.get('year',''),r.get('title',''),r.get('views',''),r.get('subscribers',''),r.get('views_per_sub',''),r.get('views_per_day',''),fmt_duration(r.get('duration')),r.get('published_at',''),r.get('channel',''),r.get('channel_id',''),list_text(r.get('channel_keywords')),list_text(r.get('video_tags')),r.get('category_id',''),r.get('likes',''),r.get('comments',''),r.get('thumbnail_url',''),r.get('url','')])
    for col,w in {'A':18,'B':10,'C':65,'D':15,'E':15,'F':13,'G':15,'H':12,'I':24,'J':30,'K':25,'L':42,'M':42,'N':12,'O':14,'P':14,'Q':55,'R':55}.items(): ws.column_dimensions[col].width=w
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
    for x in vals:ws2.append(list(x))

    wb.save(xlsx)
    return xlsx,csvv


def run_research(api_key, keyword, years, min_views, min_videos, max_videos, pages_per_year, exact_phrase, include_thumbs, log, done):
    try:
        if not api_key: raise RuntimeError('Bạn chưa nhập YouTube Data API v3 key.')
        if min_videos>max_videos: raise RuntimeError('Số video tối thiểu không được lớn hơn số video tối đa.')
        log('Dùng YouTube Data API v3 — không scraping HTML.')
        candidates=[]
        for year in years:
            candidates += search_candidates(api_key,keyword,year,pages_per_year,log)
        # De-duplicate across years/search pages.
        uniq={x['video_id']:x for x in candidates}
        candidates=list(uniq.values())
        log(f'Tổng ứng viên từ Search API: {len(candidates)}')
        details=batch_video_details(api_key,[x['video_id'] for x in candidates])
        accepted=[]
        for c in candidates:
            d=details.get(c['video_id'])
            if not d: continue
            title=d.get('title') or c.get('title','')
            pub=d.get('published_at') or c.get('published_at','')
            year=pub[:4]
            views=d.get('views',0)
            if year not in years: continue
            if exact_phrase and exact_phrase.lower() not in title.lower(): continue
            if views < min_views: continue
            r={**c,**d}; r['keyword']=keyword; r['year']=year; r['url']=c['url']
            accepted.append(r)
        accepted.sort(key=lambda r:(r.get('views') or 0),reverse=True)
        accepted=accepted[:max_videos]
        log(f'Video đạt bộ lọc: {len(accepted)}')
        if len(accepted)<min_videos:
            log(f'CẢNH BÁO: chỉ tìm thấy {len(accepted)} video, thấp hơn mức tối thiểu {min_videos}.')
        channel_ids=list({r.get('channel_id') for r in accepted if r.get('channel_id')})
        log(f'Đang lấy thông tin {len(channel_ids)} kênh...')
        channels=batch_channel_details(api_key,channel_ids)
        now=datetime.now(timezone.utc)
        for r in accepted:
            ch=channels.get(r.get('channel_id'),{})
            r.update(ch)
            sub=r.get('subscribers')
            r['views_per_sub']=round(r.get('views',0)/sub,2) if sub else ''
            try:
                dt=datetime.fromisoformat(r['published_at'].replace('Z','+00:00'))
                days=max((now-dt).total_seconds()/86400,1)
                r['views_per_day']=round(r.get('views',0)/days,1)
            except Exception:r['views_per_day']=''
            if include_thumbs: r['thumbnail_path']=download_thumb(r.get('thumbnail_url',''),r['video_id'])
        cmap={}
        for r in accepted:
            cid=r.get('channel_id')
            if not cid:continue
            c=cmap.setdefault(cid,{'channel':r.get('channel'),'subscribers':r.get('subscribers') or 0,'videos_found':0,'total_views':0,'max_views':0,'channel_id':cid,'channel_url':r.get('channel_url') or f'https://www.youtube.com/channel/{cid}'})
            c['videos_found']+=1; c['total_views']+=r.get('views') or 0; c['max_views']=max(c['max_views'],r.get('views') or 0)
            c['subscribers']=max(c['subscribers'],r.get('subscribers') or 0)
        competitors=list(cmap.values())
        for c in competitors:
            c['avg_views']=round(c['total_views']/c['videos_found']) if c['videos_found'] else 0
            vals=[r.get('views_per_sub') for r in accepted if r.get('channel_id')==c['channel_id'] and isinstance(r.get('views_per_sub'),(int,float))]
            c['views_per_sub_avg']=round(sum(vals)/len(vals),2) if vals else ''
        competitors.sort(key=lambda x:(x.get('subscribers') or 0),reverse=True)
        for r in accepted:r['_min_requested']=min_videos;r['_max_requested']=max_videos
        base=re.sub(r'[^A-Za-z0-9_-]+','_',keyword.lower()).strip('_') or 'research'
        xlsx,csvv=export_results(accepted,competitors,[],base,include_thumbs)
        done(xlsx,csvv,accepted,competitors,[],[])
    except Exception as e:
        log('LỖI: '+str(e)); log(traceback.format_exc()); done(None,None,[],[],[],[])


class App(tk.Tk):
    def __init__(self):
        super().__init__(); self.title('YouTube Music Market Research — API v2'); self.geometry('1040x820'); self.minsize(950,700); self.build()
    def build(self):
        pad={'padx':8,'pady':5}
        top=ttk.Frame(self);top.pack(fill='x',**pad)
        ttk.Label(top,text='YOUTUBE MUSIC MARKET RESEARCH — API v2',font=('Segoe UI',18,'bold')).pack(anchor='w')
        ttk.Label(top,text='YouTube Data API v3 • Không scraping HTML • Không tự động nghe/like/comment/view').pack(anchor='w')
        f=ttk.LabelFrame(self,text='1. YouTube API');f.pack(fill='x',**pad)
        f.columnconfigure(1,weight=1)
        ttk.Label(f,text='API Key').grid(row=0,column=0,sticky='w',**pad)
        self.api=tk.StringVar(value='')
        try:
            if os.path.exists(API_KEY_FILE): self.api.set(open(API_KEY_FILE,'r',encoding='utf8').read().strip())
        except: pass
        ttk.Entry(f,textvariable=self.api,show='*').grid(row=0,column=1,sticky='ew',**pad)
        ttk.Button(f,text='Lưu API key',command=self.save_key).grid(row=0,column=2,**pad)
        ttk.Label(f,text='API key chỉ lưu trong máy này ở api_key.txt').grid(row=1,column=1,sticky='w',**pad)

        g=ttk.LabelFrame(self,text='2. Bộ lọc nghiên cứu');g.pack(fill='x',**pad)
        for i in range(4):g.columnconfigure(i,weight=1)
        self.keyword=tk.StringVar(value='christmas jazz'); self.exact=tk.StringVar(value='christmas jazz')
        self.years=tk.StringVar(value='2025,2024'); self.minviews=tk.StringVar(value='1000000')
        self.minvid=tk.StringVar(value='20'); self.maxvid=tk.StringVar(value='100'); self.pages=tk.StringVar(value='10')
        fields=[('Keyword',self.keyword),('Title phải chứa',self.exact),('Năm, ví dụ 2025,2024',self.years),('View tối thiểu',self.minviews),('Video tối thiểu',self.minvid),('Video tối đa',self.maxvid),('Trang Search tối đa / năm',self.pages)]
        for idx,(lab,var) in enumerate(fields):
            row=idx//4*2; col=idx%4
            ttk.Label(g,text=lab).grid(row=row,column=col,sticky='w',**pad); ttk.Entry(g,textvariable=var).grid(row=row+1,column=col,sticky='ew',**pad)
        self.thumbs=tk.BooleanVar(value=False); ttk.Checkbutton(g,text='Tải thumbnail về máy (nặng hơn)',variable=self.thumbs).grid(row=4,column=0,columnspan=2,sticky='w',**pad)
        ttk.Label(g,text='Số video là KHOẢNG: tool tiếp tục phân trang đến khi đạt tối đa; nếu không đủ sẽ báo số tìm thấy.').grid(row=5,column=0,columnspan=4,sticky='w',**pad)

        b=ttk.Frame(self);b.pack(fill='x',**pad)
        self.start=ttk.Button(b,text='🔍 BẮT ĐẦU NGHIÊN CỨU',command=self.start_research);self.start.pack(side='left')
        ttk.Button(b,text='📂 Mở exports',command=lambda:webbrowser.open(EXPORT_DIR)).pack(side='left',padx=8)
        self.progress=ttk.Progressbar(b,mode='indeterminate');self.progress.pack(side='left',fill='x',expand=True,padx=8)
        o=ttk.LabelFrame(self,text='3. Nhật ký');o.pack(fill='both',expand=True,**pad)
        self.logbox=tk.Text(o,height=22,wrap='word');self.logbox.pack(fill='both',expand=True,padx=8,pady=8)
        r=ttk.LabelFrame(self,text='4. Kết quả');r.pack(fill='x',**pad);self.result=tk.StringVar(value='Chưa chạy.');ttk.Label(r,textvariable=self.result,wraplength=980).pack(anchor='w',padx=10,pady=10)
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
        args=(self.api.get().strip(),self.keyword.get().strip(),years,mv,mn,mx,pages,self.exact.get().strip(),self.thumbs.get(),self.log,self.finished)
        threading.Thread(target=run_research,args=args,daemon=True).start()
    def finished(self,xlsx,csvv,rows,competitors,kw,watch):
        def ui():
            self.progress.stop();self.start.config(state='normal')
            if not xlsx:self.result.set('Không tạo được file. Xem Nhật ký.');return
            self.result.set(f'Hoàn tất: {len(rows)} video • {len(competitors)} kênh.\nExcel: {xlsx}\nCSV: {csvv}')
            if messagebox.askyesno('Hoàn tất','Đã tạo Excel/CSV. Mở thư mục exports?'):webbrowser.open(EXPORT_DIR)
        self.after(0,ui)

if __name__=='__main__': App().mainloop()
