import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from pathlib import Path
from core import Catalog, STATUSES

ROOT = Path(__file__).resolve().parent.parent

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Music Manager • Nhạc & ghi công')
        screen_width=self.winfo_screenwidth(); screen_height=self.winfo_screenheight()
        width=max(640,min(1460,screen_width-24))
        height=max(480,min(880,screen_height-80))
        x=max(0,(screen_width-width)//2); y=max(0,(screen_height-height-40)//2)
        self.geometry(f'{width}x{height}+{x}+{y}')
        self.minsize(min(1100,width),min(680,height))
        self.state('zoomed')
        self.catalog=Catalog(ROOT); self.catalog.backup(); self.catalog.scan()
        self.pid=None; self.tid=None; self.loading=False; self.dirty=False
        self.style=ttk.Style(self); self.style.theme_use('clam')
        self.style.configure('Treeview',rowheight=28,font=('Segoe UI',10))
        self.style.configure('Treeview.Heading',font=('Segoe UI',10,'bold'))
        self.style.configure('TButton',padding=(10,6),font=('Segoe UI',10))
        self.style.configure('TLabel',font=('Segoe UI',10))
        top=ttk.Frame(self,padding=12); top.pack(fill='x')
        ttk.Label(top,text='MUSIC MANAGER · PLAYLIST KÊNH · GHI CÔNG',font=('Segoe UI',17,'bold')).pack(side='left')
        ttk.Button(top,text='Quét lại thư viện',command=self.scan).pack(side='right',padx=4)
        ttk.Button(top,text='Sao lưu dữ liệu',command=self.backup).pack(side='right',padx=4)
        ttk.Button(top,text='Xuất danh mục CSV',command=self.export_catalog).pack(side='right',padx=4)
        self.summary=ttk.Label(self,padding=(12,0)); self.summary.pack(fill='x')
        filters=ttk.Frame(self,padding=12); filters.pack(fill='x')
        self.search=tk.StringVar(); self.group=tk.StringVar(value='Tất cả nhóm'); self.status_filter=tk.StringVar(value='Tất cả trạng thái')
        ttk.Label(filters,text='Tìm tên bài / nghệ sĩ:').pack(side='left')
        ttk.Entry(filters,textvariable=self.search,width=30).pack(side='left',padx=8)
        self.groupbox=ttk.Combobox(filters,textvariable=self.group,state='readonly',width=22); self.groupbox.pack(side='left',padx=5)
        ttk.Combobox(filters,textvariable=self.status_filter,values=('Tất cả trạng thái',*STATUSES,'Thiếu tệp','Đã dùng trong dự án','Trong kênh đang chọn'),state='readonly',width=25).pack(side='left',padx=5)
        self.only_unused=tk.BooleanVar(); ttk.Checkbutton(filters,text='Chưa dùng trong dự án nào',variable=self.only_unused,command=self.refresh_tracks).pack(side='left',padx=5)
        self.search.trace_add('write',lambda *_:self.refresh_tracks()); self.group.trace_add('write',lambda *_:self.refresh_tracks()); self.status_filter.trace_add('write',lambda *_:self.refresh_tracks())
        channel_bar=ttk.Frame(self,padding=(12,0,12,4)); channel_bar.pack(fill='x')
        ttk.Label(channel_bar,text='Playlist theo kênh Content Hub:').pack(side='left')
        self.channel_choice=tk.StringVar()
        self.channelbox=ttk.Combobox(channel_bar,textvariable=self.channel_choice,state='readonly',width=28)
        self.channelbox.pack(side='left',padx=6); self.channelbox.bind('<<ComboboxSelected>>',lambda *_:self.refresh_tracks())
        ttk.Button(channel_bar,text='Làm mới kênh',command=self.refresh_channels).pack(side='left',padx=3)
        ttk.Button(channel_bar,text='Gán bài đã chọn',command=self.assign_channel).pack(side='left',padx=3)
        ttk.Button(channel_bar,text='Bỏ khỏi kênh',command=self.unassign_channel).pack(side='left',padx=3)
        self.channel_count=ttk.Label(channel_bar,text=''); self.channel_count.pack(side='left',padx=10)

        self.tabs=ttk.Notebook(self); self.tabs.pack(fill='both',expand=True,padx=12,pady=6)
        library=ttk.Frame(self.tabs,padding=10); self.tabs.add(library,text='Thư viện nhạc')
        ttk.Label(library,text='Chọn một hoặc nhiều bài · Ctrl / Shift để chọn · nhấp đúp để nghe',font=('Segoe UI',11,'bold')).pack(anchor='w',pady=(0,6))
        self.table=self.tree(library,('title','artist','status','channels','files','uses','tags'),('Tên bài','Nghệ sĩ','Ghi công','Kênh','Tệp','Dự án','Phân loại cho Editor'),(260,170,170,220,55,70,260))
        self.table.bind('<<TreeviewSelect>>',self.select_track)
        self.table.bind('<Double-1>',lambda e:self.preview())
        for tag,color in [('unknown','#8a5200'),('required','#8c2648'),('missing','#a00000')]: self.table.tag_configure(tag,foreground=color)
        library_actions=ttk.Frame(library); library_actions.pack(fill='x',pady=(8,0))
        ttk.Button(library_actions,text='Nghe bài đã chọn',command=self.preview).pack(side='left')
        ttk.Button(library_actions,text='Phân loại cho Editor',command=self.classify_tracks).pack(side='left',padx=6)
        ttk.Button(library_actions,text='Mở hồ sơ ghi công',command=self.open_credit_tab).pack(side='left',padx=6)
        ttk.Button(library_actions,text='Thêm bài đã chọn vào dự án',command=self.add).pack(side='right')

        credits=ttk.Frame(self.tabs,padding=16); self.credit_tab=credits; self.tabs.add(credits,text='Hồ sơ ghi công')
        ttk.Label(credits,text='Hồ sơ ghi công · bạn tự kiểm tra giấy phép và nhập nguyên văn nội dung',font=('Segoe UI',11,'bold')).pack(anchor='w',pady=(0,8))
        self.track_label=ttk.Label(credits,text='Chưa chọn bài · quay lại Thư viện nhạc để chọn một bài',wraplength=1200)
        self.track_label.pack(fill='x',pady=(0,8))
        self.review_status=tk.StringVar(value=STATUSES[0]); self.source=tk.StringVar(); self.license=tk.StringVar()
        ttk.Label(credits,text='Trạng thái').pack(anchor='w')
        ttk.Combobox(credits,textvariable=self.review_status,values=STATUSES,state='readonly').pack(fill='x',pady=4)
        ttk.Label(credits,text='Nội dung ghi công chính xác (dán nguyên văn)').pack(anchor='w',pady=(8,2))
        self.credit=tk.Text(credits,height=10,wrap='word',font=('Segoe UI',10),undo=True)
        self.credit.pack(fill='both',expand=True)
        details=ttk.Frame(credits); details.pack(fill='x',pady=(8,0))
        details.columnconfigure(1,weight=1); details.columnconfigure(3,weight=1)
        ttk.Label(details,text='Link nguồn / trang kiểm tra').grid(row=0,column=0,sticky='w',padx=(0,8))
        ttk.Entry(details,textvariable=self.source).grid(row=0,column=1,sticky='ew',padx=(0,16))
        ttk.Label(details,text='Tên giấy phép').grid(row=0,column=2,sticky='w',padx=(0,8))
        ttk.Entry(details,textvariable=self.license).grid(row=0,column=3,sticky='ew')
        ttk.Label(credits,text='Ghi chú').pack(anchor='w',pady=(8,2))
        self.notes=tk.Text(credits,height=3,wrap='word',font=('Segoe UI',10),undo=True); self.notes.pack(fill='x')
        self.reviewed=ttk.Label(credits,text='',wraplength=1200); self.reviewed.pack(fill='x',pady=6)
        credit_actions=ttk.Frame(credits); credit_actions.pack(fill='x')
        ttk.Button(credit_actions,text='Lưu hồ sơ ghi công',command=self.save).pack(side='left')
        ttk.Button(credit_actions,text='Xem lịch sử kiểm tra',command=self.history).pack(side='left',padx=6)
        for var in (self.review_status,self.source,self.license): var.trace_add('write',self.changed)
        for widget in (self.credit,self.notes): widget.bind('<<Modified>>',self.text_changed)

        projects=ttk.Frame(self.tabs,padding=10); self.project_tab=projects; self.tabs.add(projects,text='Dự án CapCut')
        project_bar=ttk.Frame(projects); project_bar.pack(fill='x',pady=(0,8))
        ttk.Label(project_bar,text='Dự án đang quản lý:').pack(side='left')
        self.project_choice=tk.StringVar(); self.projectbox=ttk.Combobox(project_bar,textvariable=self.project_choice,state='readonly',width=36)
        self.projectbox.pack(side='left',padx=8); self.projectbox.bind('<<ComboboxSelected>>',self.choose_project)
        ttk.Button(project_bar,text='+ Tạo dự án mới',command=self.new_project).pack(side='left',padx=4)
        ttk.Button(project_bar,text='Xóa dự án đang chọn',command=self.delete_project).pack(side='left',padx=4)
        ttk.Label(projects,text='Chọn bài trong thư viện rồi bấm “Thêm bài đã chọn vào dự án”. Dùng ↑ / ↓ để đổi thứ tự bài.',wraplength=1200).pack(anchor='w',pady=(0,6))
        self.project_table=self.tree(projects,('title','status'),('Tên bài','Ghi công'),(900,240))
        self.project_table.bind('<<TreeviewSelect>>',self.select_project_track)
        self.project_table.bind('<Double-1>',lambda e:self.open_credit_tab())
        controls=ttk.Frame(projects); controls.pack(fill='x',pady=8)
        ttk.Button(controls,text='↑ Lên',command=lambda:self.move(-1)).pack(side='left')
        ttk.Button(controls,text='↓ Xuống',command=lambda:self.move(1)).pack(side='left',padx=4)
        ttk.Button(controls,text='Bỏ bài khỏi dự án',command=self.remove).pack(side='left',padx=4)
        self.project_summary=ttk.Label(controls,text='Chưa chọn dự án',wraplength=700); self.project_summary.pack(side='left',padx=12)
        ttk.Button(controls,text='Xem / sao chép ghi công',command=self.show_credits).pack(side='right',padx=4)
        ttk.Button(controls,text='Xuất nhạc + ghi công cho CapCut',command=self.export).pack(side='right',padx=4)

        guide=ttk.Frame(self.tabs,padding=16); self.tabs.add(guide,text='Hướng dẫn')
        guide_text=tk.Text(guide,wrap='word',font=('Segoe UI',10),height=16)
        guide_scroll=ttk.Scrollbar(guide,orient='vertical',command=guide_text.yview)
        guide_text.configure(yscrollcommand=guide_scroll.set)
        guide_text.pack(side='left',fill='both',expand=True); guide_scroll.pack(side='right',fill='y')
        guide_text.insert('1.0',self.help_text())
        guide_text.configure(state='disabled')
        ttk.Label(self,text='Thư viện, playlist kênh và ghi công dùng chung dữ liệu với Content Hub.',padding=(12,4)).pack(fill='x')
        self.protocol('WM_DELETE_WINDOW',self.close)
        self.refresh_channels(); self.refresh_tracks(); self.refresh_projects()

    def refresh_channels(self):
        channels=[c for c in self.catalog.channels() if not c['archived']]
        self.channel_map={c['name']:c['id'] for c in channels}
        names=list(self.channel_map); current=self.channel_choice.get() if hasattr(self,'channel_choice') else ''
        self.channelbox.configure(values=names)
        if current not in names: self.channel_choice.set(names[0] if names else '')
        self.refresh_channel_count()

    def refresh_channel_count(self):
        if not hasattr(self,'channel_count'): return
        name=self.channel_choice.get()
        count=len(self.catalog.channel_tracks(self.channel_map[name])) if name in self.channel_map else 0
        self.channel_count.configure(text=f'{count} bài trong kênh' if name else 'Chọn kênh trong Content Hub')

    def assign_channel(self):
        name=self.channel_choice.get(); channel_id=self.channel_map.get(name); ids=self.table.selection()
        if not channel_id:
            messagebox.showinfo('Chưa chọn kênh','Tạo hoặc chọn kênh trong Content Hub trước.',parent=self); return
        if not ids: return
        try:
            self.catalog.assign_channel(channel_id,ids); self.refresh_tracks()
        except Exception as e: messagebox.showerror('Không gán được bài',str(e),parent=self)

    def unassign_channel(self):
        channel_id=self.channel_map.get(self.channel_choice.get()); ids=self.table.selection()
        if channel_id and ids:
            self.catalog.unassign_channel(channel_id,ids); self.refresh_tracks()

    def tree(self,parent,cols,labels,widths):
        frame=ttk.Frame(parent); frame.pack(fill='both',expand=True)
        table=ttk.Treeview(frame,columns=cols,show='headings',selectmode='extended')
        scroll=ttk.Scrollbar(frame,orient='vertical',command=table.yview)
        horizontal=ttk.Scrollbar(frame,orient='horizontal',command=table.xview)
        table.configure(yscrollcommand=scroll.set,xscrollcommand=horizontal.set)
        table.grid(row=0,column=0,sticky='nsew'); scroll.grid(row=0,column=1,sticky='ns')
        horizontal.grid(row=1,column=0,sticky='ew')
        frame.rowconfigure(0,weight=1); frame.columnconfigure(0,weight=1)
        for c,label,width in zip(cols,labels,widths): table.heading(c,text=label); table.column(c,width=width,minwidth=35)
        return table

    def help_text(self):
        return (
            'QUẢN LÝ THƯ VIỆN NHẠC\n\n'
            '• Tìm theo tên bài hoặc nghệ sĩ; lọc theo nhóm, trạng thái, kênh hoặc bài chưa dùng. '
            'Ctrl / Shift để chọn nhiều bài. Nhấp đúp một bài để nghe.\n'
            '• Playlist theo kênh lấy từ Content Hub. Chọn kênh, chọn bài trong thư viện rồi dùng '
            'Gán bài đã chọn hoặc Bỏ khỏi kênh.\n\n'
            'KIỂM TRA GHI CÔNG\n\n'
            '• Chọn bài trong tab Thư viện nhạc, sau đó mở tab Hồ sơ ghi công. '
            'Tự kiểm tra điều kiện giấy phép; chọn trạng thái và dán nguyên văn nội dung ghi công nếu cần.\n'
            '• Điền nguồn, tên giấy phép, ghi chú rồi bấm Lưu hồ sơ ghi công. '
            'Xem lịch sử kiểm tra để tra các lần lưu trước.\n\n'
            'DỰ ÁN CAPCUT\n\n'
            '• Vào tab Dự án CapCut, bấm + Tạo dự án mới hoặc chọn dự án có sẵn. '
            'Nút Xóa dự án đang chọn xóa dự án cùng danh sách bài bên trong; các gói xuất cũ vẫn được giữ.\n'
            '• Quay lại Thư viện nhạc, chọn các bài có tệp rồi bấm Thêm bài đã chọn vào dự án. '
            'Trong tab Dự án CapCut, dùng Lên / Xuống để sắp thứ tự hoặc Bỏ bài khỏi dự án.\n'
            '• Xem / sao chép ghi công để lấy nội dung mô tả. Xuất nhạc + ghi công cho CapCut '
            'tạo thư mục Audio và tệp ghi công để nhập vào CapCut.\n\n'
            'DỮ LIỆU\n\n'
            'Thư viện, playlist kênh và hồ sơ ghi công dùng chung database với Content Hub. '
            'Ứng dụng sao lưu dữ liệu khi khởi động; nút Sao lưu dữ liệu tạo một bản sao lưu mới.'
        )

    def open_credit_tab(self):
        self.tabs.select(self.credit_tab)

    def changed(self,*_):
        if not self.loading and self.tid: self.dirty=True

    def text_changed(self,event):
        if event.widget.edit_modified(): self.changed(); event.widget.edit_modified(False)

    def guard(self):
        if not self.dirty: return True
        result=messagebox.askyesnocancel('Hồ sơ chưa lưu','Lưu thay đổi ghi công trước khi tiếp tục?',parent=self)
        if result is None: return False
        if result: return self.save()
        self.dirty=False; return True

    def refresh_tracks(self):
        if not hasattr(self,'table'): return
        selected=self.table.selection()
        self.rows=self.catalog.tracks(); self.by_id={r['id']:r for r in self.rows}
        groups=sorted({g for r in self.rows for g in (r['groups'] or '').split(', ') if g})
        self.groupbox.configure(values=('Tất cả nhóm',*groups))
        self.table.delete(*self.table.get_children())
        q=self.search.get().casefold(); shown=0
        channel_id=self.channel_map.get(self.channel_choice.get())
        selected_channel_ids = ({item['id'] for item in self.catalog.channel_tracks(channel_id)}
                                if channel_id and self.status_filter.get() == 'Trong kênh đang chọn' else None)
        for r in self.rows:
            if q not in (r['title']+' '+r['artist']).casefold(): continue
            if self.group.get()!='Tất cả nhóm' and self.group.get() not in (r['groups'] or '').split(', '): continue
            st=self.status_filter.get()
            if st in STATUSES and r['status']!=st: continue
            if st=='Thiếu tệp' and r['file_count']: continue
            if st=='Đã dùng trong dự án' and not r['uses']: continue
            if self.only_unused.get() and r['uses']: continue
            if selected_channel_ids is not None and r['id'] not in selected_channel_ids: continue
            tag='missing' if not r['file_count'] else 'unknown' if r['status']==STATUSES[0] else 'required' if r['status']==STATUSES[2] else ''
            self.table.insert('', 'end',iid=r['id'],values=(r['title'],r['artist'],r['status'],r['channels'] or '',r['file_count'],r['uses'],r['tags'] or ''),tags=(tag,)); shown+=1
        self.loading=True
        self.table.selection_set([tid for tid in selected if self.table.exists(tid)])
        self.loading=False
        existing=sum(bool(r['file_count']) for r in self.rows); unchecked=sum(r['status']==STATUSES[0] and r['file_count']>0 for r in self.rows)
        self.summary.configure(text=f'{existing} bài có tệp · {len(self.rows)-existing} bài thiếu tệp · {unchecked} bài chưa kiểm tra · đang hiển thị {shown} bài')
        self.refresh_channel_count()

    def select_track(self,event=None):
        if self.loading: return
        selected=self.table.selection()
        if len(selected)!=1: return
        self.load_track(selected[0])

    def load_track(self,tid):
        if tid==self.tid: return
        if not self.guard():
            self.loading=True
            if self.tid and self.table.exists(self.tid): self.table.selection_set(self.tid)
            self.loading=False
            return
        r=self.catalog.get(tid); self.loading=True; self.tid=tid
        self.track_label.configure(text=r['title']+'\n'+r['artist'])
        self.review_status.set(r['status']); self.source.set(r['source']); self.license.set(r['license'])
        for widget,text in ((self.credit,r['credit']),(self.notes,r['notes'])):
            widget.delete('1.0','end'); widget.insert('1.0',text); widget.edit_modified(False)
        self.reviewed.configure(text='Lần kiểm tra: '+(r['reviewed'] or 'Chưa kiểm tra'))
        self.loading=False; self.dirty=False

    def save(self):
        if not self.tid: return False
        try:
            self.catalog.save_review(self.tid,self.review_status.get(),self.credit.get('1.0','end-1c'),self.source.get(),self.license.get(),self.notes.get('1.0','end-1c'))
            self.dirty=False; self.refresh_tracks(); self.refresh_project_items()
            self.reviewed.configure(text='Đã lưu · '+self.catalog.get(self.tid)['reviewed']); return True
        except Exception as e: messagebox.showerror('Không lưu được',str(e),parent=self); return False

    def scan(self):
        if not self.guard(): return
        try:
            count=self.catalog.scan(); self.refresh_tracks(); self.refresh_project_items()
            messagebox.showinfo('Đã quét',f'Tìm thấy {count} tệp âm thanh. Hồ sơ ghi công đã lưu được giữ lại.',parent=self)
        except Exception as e: messagebox.showerror('Lỗi quét',str(e),parent=self)

    def preview(self):
        selection=self.table.selection(); tid=selection[0] if selection else self.tid
        if not tid: return
        path=self.catalog.source_file(tid)
        if not path: messagebox.showwarning('Thiếu tệp','Bài này chưa có tệp âm thanh.',parent=self); return
        try: os.startfile(str(path))
        except OSError as e: messagebox.showerror('Không mở được trình phát',str(e),parent=self)

    def classify_tracks(self):
        ids=list(self.table.selection())
        if not ids:
            messagebox.showinfo('Chọn bài','Chọn một hoặc nhiều bài trong thư viện trước.',parent=self)
            return
        win=tk.Toplevel(self); win.title('Phân loại nhạc cho Tool Edit'); win.geometry('520x410')
        win.transient(self); win.grab_set(); win.columnconfigure(1,weight=1)
        ttk.Label(win,text=f'Áp dụng nhãn cho {len(ids)} bài đã chọn. “Giữ nguyên” không thay đổi nhãn hiện có.',
                  wraplength=470).grid(row=0,column=0,columnspan=2,sticky='w',padx=16,pady=(16,10))
        choices={
            'genre':('Thể loại',('Jazz','Ambient','Classical','Acoustic','Celtic','Christmas','Electronic','Khác')),
            'instrument':('Nhạc cụ chính',('Piano','Guitar','Harp','Flute','Synth','Strings','Percussion','Khác')),
            'vocal':('Giọng hát',('Không lời','Có lời','Chưa rõ')),
            'mood':('Không khí',('Thư giãn','Tập trung','Ngủ','Không gian','Cafe','Lãng mạn','Thiên nhiên','Mùa lễ')),
        }
        vars_by_category={}
        for row,(category,(label,values)) in enumerate(choices.items(),1):
            ttk.Label(win,text=label).grid(row=row,column=0,sticky='w',padx=16,pady=6)
            var=tk.StringVar(value='Giữ nguyên'); vars_by_category[category]=var
            ttk.Combobox(win,textvariable=var,state='readonly',values=('Giữ nguyên','Xóa nhãn',*values)).grid(
                row=row,column=1,sticky='ew',padx=16,pady=6)
        ttk.Label(win,text='Mỗi lần có thể áp dụng một nhãn cho cả nhóm bài; chạy lại để thêm nhãn khác.',
                  wraplength=470).grid(row=5,column=0,columnspan=2,sticky='w',padx=16,pady=10)
        actions=ttk.Frame(win); actions.grid(row=6,column=0,columnspan=2,sticky='e',padx=16,pady=(4,16))
        def save():
            changes={}
            for category,var in vars_by_category.items():
                value=var.get()
                if value=='Giữ nguyên': continue
                changes[category]=[] if value=='Xóa nhãn' else [value]
            if changes: self.catalog.save_track_tags(ids,changes)
            win.destroy()
        ttk.Button(actions,text='Hủy',command=win.destroy).pack(side='right',padx=(6,0))
        ttk.Button(actions,text='Lưu phân loại',command=save).pack(side='right')

    def refresh_projects(self):
        self.project_map={f'{r["name"]} [#{r["id"]}]':r['id'] for r in self.catalog.projects()}
        self.projectbox.configure(values=list(self.project_map))
        current=next((k for k,v in self.project_map.items() if v==self.pid),None)
        if current:
            self.project_choice.set(current)
        elif self.project_map:
            self.project_choice.set(next(iter(self.project_map))); self.pid=self.project_map[self.project_choice.get()]
        else:
            self.pid=None; self.project_choice.set('')
        self.refresh_project_items()

    def choose_project(self,event=None):
        self.pid=self.project_map[self.project_choice.get()]; self.refresh_project_items()

    def new_project(self):
        name=simpledialog.askstring('Tạo dự án','Tên dự án CapCut:',parent=self)
        if name:
            self.pid=self.catalog.new_project(name); self.refresh_projects()

    def delete_project(self):
        if not self.pid:
            messagebox.showinfo('Chưa chọn dự án','Hãy tạo hoặc chọn dự án cần xóa.',parent=self)
            return
        project=next((item for item in self.catalog.projects() if item['id']==self.pid),None)
        if not project:
            self.pid=None; self.refresh_projects(); return
        confirm=messagebox.askyesno(
            'Xóa dự án',
            f'Xóa dự án “{project["name"]}” và danh sách bài đã chọn trong dự án?\n\n'
            'Các tệp nhạc và gói CapCut đã xuất trước đây sẽ được giữ nguyên.',
            parent=self,
        )
        if not confirm: return
        self.catalog.delete_project(self.pid)
        self.pid=None
        self.refresh_projects()

    def refresh_project_items(self):
        if not hasattr(self,'project_table'): return
        selected=self.project_table.selection(); self.project_table.delete(*self.project_table.get_children())
        rows=self.catalog.project_items(self.pid) if self.pid else []
        for i,r in enumerate(rows,1): self.project_table.insert('','end',iid=r['id'],values=(f'{i:02d}. '+r['title'],r['status']))
        self.project_table.selection_set([tid for tid in selected if self.project_table.exists(tid)])
        issues=self.catalog.issues(self.pid) if self.pid else []
        self.project_summary.configure(text=f'{len(rows)} bài đã chọn · {sum(r["status"]==STATUSES[2] for r in rows)} bài cần ghi công\n'+(f'{len(issues)} bài cần xử lý trước khi xuất hoàn chỉnh' if issues else 'Có thể xuất gói hoàn chỉnh' if rows else 'Chọn bài trong thư viện rồi bấm Thêm'))

    def select_project_track(self,event=None):
        ids=self.project_table.selection()
        if len(ids)==1: self.load_track(ids[0])

    def add(self):
        if not self.pid:
            self.tabs.select(self.project_tab)
            messagebox.showinfo('Chọn dự án','Hãy tạo hoặc chọn một dự án trong tab Dự án CapCut trước.',parent=self)
            return
        ids=self.table.selection()
        if not ids: return
        if any(not self.catalog.source_file(tid) for tid in ids): messagebox.showwarning('Thiếu tệp','Danh sách chọn có bài thiếu tệp. Chỉ thêm các bài đã có nhạc.',parent=self); return
        self.catalog.add(self.pid,ids); self.refresh_project_items(); self.refresh_tracks()

    def remove(self):
        if self.pid: self.catalog.remove(self.pid,self.project_table.selection()); self.refresh_project_items(); self.refresh_tracks()

    def move(self,delta):
        ids=list(self.project_table.get_children()); selected=self.project_table.selection()
        if len(selected)!=1: return
        i=ids.index(selected[0]); j=i+delta
        if 0<=j<len(ids):
            ids[i],ids[j]=ids[j],ids[i]; self.catalog.reorder(self.pid,ids); self.refresh_project_items(); self.project_table.selection_set(selected)

    def show_credits(self):
        if not self.pid or not self.guard(): return
        win=tk.Toplevel(self); win.title('Ghi công dự án'); win.geometry('780x600')
        issues=self.catalog.issues(self.pid)
        ttk.Label(win,text=f'{len(issues)} bài chưa xử lý. Nội dung bên dưới chỉ gồm các bài đã đánh dấu Cần ghi công.',wraplength=740,padding=12).pack(fill='x')
        text=tk.Text(win,wrap='word',font=('Segoe UI',11)); text.pack(fill='both',expand=True,padx=12)
        content=self.catalog.credit_text(self.pid); text.insert('1.0',content or 'Chưa có nội dung ghi công cần xuất.'); text.configure(state='disabled')
        def copy(): self.clipboard_clear(); self.clipboard_append(content); messagebox.showinfo('Đã sao chép','Đã sao chép nội dung ghi công.',parent=win)
        ttk.Button(win,text='Sao chép nội dung',command=copy).pack(pady=12)

    def export(self):
        if not self.pid or not self.guard(): return
        issues=self.catalog.issues(self.pid); draft=False
        if issues:
            content='\n'.join(f'• {title}: {reason}' for title,reason in issues[:12])
            if len(issues)>12: content+=f'\n… và {len(issues)-12} bài khác'
            draft=messagebox.askyesno('Chỉ có thể xuất bản nháp',content+'\n\nXuất bản nháp để dựng CapCut? Các bài chưa kiểm tra được liệt kê trong CAN_KIEM_TRA.txt. Cần kiểm tra trước khi đăng.',parent=self)
            if not draft: return
        try:
            self.configure(cursor='watch'); self.update_idletasks()
            path=self.catalog.export(self.pid,draft)
            messagebox.showinfo('Đã xuất '+('BẢN NHÁP' if draft else 'gói hoàn chỉnh'),f'{path}\n\nTrong CapCut: Import các tệp trong Audio. Ghi công nằm ở GHI_CONG.txt.',parent=self)
            os.startfile(str(path))
        except Exception as e: messagebox.showerror('Không xuất được',str(e),parent=self)
        finally: self.configure(cursor='')

    def history(self):
        if not self.tid: return
        import json
        rows=self.catalog.db.execute('SELECT * FROM history WHERE track_id=? ORDER BY id DESC',(self.tid,)).fetchall()
        win=tk.Toplevel(self); win.title('Lịch sử hồ sơ'); win.geometry('740x500')
        text=tk.Text(win,wrap='word'); text.pack(fill='both',expand=True)
        for r in rows:
            after=json.loads(r['after_json']); text.insert('end',f'{r["changed"]} · {after["status"]}\n{after["credit"]}\nNguồn: {after["source"]}\n\n')
        if not rows: text.insert('end','Chưa có lần lưu nào.')
        text.configure(state='disabled')

    def backup(self):
        path=self.catalog.backup(); messagebox.showinfo('Đã sao lưu',str(path),parent=self)

    def export_catalog(self):
        if not self.guard(): return
        path=filedialog.asksaveasfilename(parent=self,initialdir=str(self.catalog.output_root),initialfile='Danh_muc_nhac.csv',defaultextension='.csv',filetypes=[('CSV','*.csv')])
        if path:
            try: self.catalog.export_catalog(path); messagebox.showinfo('Đã xuất','Đã lưu danh mục nhạc và hồ sơ ghi công.',parent=self)
            except Exception as e: messagebox.showerror('Lỗi',str(e),parent=self)

    def close(self):
        if self.guard(): self.catalog.db.close(); self.destroy()

    def report_callback_exception(self,kind,value,tb):
        import traceback
        log=Path(__file__).parent/'error.log'
        with log.open('a',encoding='utf-8') as f: f.write(''.join(traceback.format_exception(kind,value,tb)))
        messagebox.showerror('Không thực hiện được',f'{value}\n\nChi tiết lỗi: {log}',parent=self)

if __name__=='__main__':
    try: App().mainloop()
    except Exception:
        import traceback
        log=Path(__file__).parent/'error.log'; log.write_text(traceback.format_exc(),encoding='utf-8')
        messagebox.showerror('Ứng dụng gặp lỗi',f'Chi tiết lỗi được lưu tại {log}')
        sys.exit(1)
