(() => {
  const visible=e=>e.getClientRects().length && getComputedStyle(e).visibility!=='hidden';
  const label=e=>[e.innerText || e.textContent || '',e.getAttribute('aria-label'),e.getAttribute('title')].filter(Boolean).join(' ').trim();
  function number(e) {
    const value=label(e);
    const match=value.match(/(?:^|\s)[x×]\s*([1-4])(?:\s|$)/i) || value.match(/(?:outputs?|images?|ảnh|kết quả)\s*[:：]?\s*([1-4])\b/i) || value.match(/^([1-4])\s*(?:images?|ảnh|outputs?)$/i);
    return match ? Number(match[1]) : null;
  }
  function current(editor,cfg) {
    if(cfg.countControl){const rows=[...document.querySelectorAll(cfg.countControl)].filter(visible);return rows.length===1?{element:rows[0],count:number(rows[0])}:null;}
    const box=editor.getBoundingClientRect();
    const controls=[...document.querySelectorAll('button,[role="button"],[role="combobox"]')].filter(visible).filter(e=>{
      const r=e.getBoundingClientRect();return r.top>=box.top-60 && r.top<=box.bottom+180 && r.left>=box.left-60 && r.right<=box.right+180;
    }).map(element=>({element,count:number(element)})).filter(x=>x.count!==null);
    if(controls.length===1)return controls[0];
    const checked=[...document.querySelectorAll('[aria-selected="true"],[aria-checked="true"],[data-state="checked"]')].filter(visible).map(element=>({element,count:number(element) || (/^[1-4]$/.test(label(element))?Number(label(element)):null)})).filter(x=>x.count!==null);
    return checked.length===1?checked[0]:null;
  }
  async function apply({editor,cfg,click,sleep,check}) {
    const wanted=Number(cfg.count);
    let control=current(editor(),cfg);
    if(!control) {
      const box=editor().getBoundingClientRect();
      const triggers=[...document.querySelectorAll('button,[role="button"]')].filter(visible).filter(e=>{
        const r=e.getBoundingClientRect();return /\b(settings|tune|options)\b|cài đặt|thiết lập/i.test(label(e)) && r.top>=box.top-60 && r.top<=box.bottom+180 && r.left>=box.left-60 && r.right<=box.right+180;
      });
      if(triggers.length===1) {
        await click(triggers[0]);
        for(let i=0;i<30;i++){check();control=current(editor(),cfg);if(control)break;await sleep(150);}
      }
    }
    if(!control)throw Object.assign(new Error('Chưa đọc được số ảnh trên Flow. Mở cài đặt Flow hoặc cấu hình bộ chọn số ảnh. Chưa gửi prompt.'),{code:'settings_failed'});
    if(control.count!==wanted) {
      await click(control.element);
      let matches=[];
      for(let i=0;i<30;i++) {
        check();
        const selector=cfg.countOption?.replace(/\{count\}/g,String(wanted)) || '[role="option"],[role="menuitem"],[role="menuitemradio"],[role="radio"],button';
        matches=[...document.querySelectorAll(selector)].filter(visible).filter(e=>!e.disabled && e.getAttribute('aria-disabled')!=='true' && (number(e)===wanted || label(e)===String(wanted)));
        if(matches.length===1)break;
        await sleep(150);
      }
      if(matches.length!==1)throw Object.assign(new Error('Không tìm thấy duy nhất lựa chọn x'+wanted+' trong cài đặt Flow. Chưa gửi.'),{code:'settings_failed'});
      await click(matches[0]);
      control=null;
      for(let i=0;i<30;i++){check();control=current(editor(),cfg);if(control?.count===wanted)break;await sleep(150);}
      if(control?.count!==wanted)throw Object.assign(new Error('Flow chưa xác nhận x'+wanted+'. Chưa gửi prompt.'),{code:'settings_failed'});
    }
    return wanted;
  }
  const ratios=['16:9','4:3','1:1','3:4','9:16'];
  function ratioRows() {
    return [...document.querySelectorAll('button,[role="radio"],[role="option"],[role="menuitem"]')].filter(visible).filter(e=>!e.disabled).map(element=>{
      const found=ratios.filter(r=>new RegExp('(?:^|\\s)'+r.replace(':','\\s*:\\s*')+'(?:\\s|$)').test(label(element)));
      return found.length===1?{element,ratio:found[0]}:null;
    }).filter(Boolean);
  }
  function selectedRatio(rows) {
    const marked=rows.filter(({element:e})=>e.getAttribute('aria-checked')==='true' || e.getAttribute('aria-selected')==='true' || ['checked','on','active'].includes(e.getAttribute('data-state')));
    if(marked.length===1)return marked[0].ratio;
    if(rows.length!==5 || new Set(rows.map(r=>r.ratio)).size!==5)return null;
    const colors=rows.map(r=>getComputedStyle(r.element).backgroundColor);
    const unique=rows.filter((r,i)=>colors[i] && !['transparent','rgba(0, 0, 0, 0)'].includes(colors[i]) && colors.filter(c=>c===colors[i]).length===1);
    return unique.length===1?unique[0].ratio:null;
  }
  async function applyRatio({editor,cfg,click,sleep,check}) {
    if(!cfg.aspectRatio)return null;
    const wanted=cfg.aspectRatio;
    if(!ratios.includes(wanted))throw Object.assign(new Error('Tỉ lệ ảnh không hợp lệ.'),{code:'settings_failed'});
    let rows=ratioRows();
    const open=async()=>{
      const trigger=current(editor(),cfg)?.element || globalThis.FlowModels?.detect(editor(),[])?.element;
      if(!trigger)throw Object.assign(new Error('Không tìm được nút cài đặt tỉ lệ cạnh prompt.'),{code:'settings_failed'});
      await click(trigger);
      for(let i=0;i<30;i++){check();rows=ratioRows();if(rows.length) return;await sleep(200);}
      throw Object.assign(new Error('Không thấy lựa chọn tỉ lệ ảnh trong cài đặt Flow. Chưa gửi.'),{code:'settings_failed'});
    };
    if(!rows.length)await open();
    if(selectedRatio(rows)===wanted)return wanted;
    const matches=rows.filter(r=>r.ratio===wanted);
    if(matches.length!==1)throw Object.assign(new Error('Không thấy duy nhất lựa chọn tỉ lệ '+wanted+'. Chưa gửi.'),{code:'settings_failed'});
    await click(matches[0].element);
    for(let i=0;i<30;i++){
      check();rows=ratioRows();
      if(!rows.length)await open();
      if(selectedRatio(rows)===wanted)return wanted;
      await sleep(200);
    }
    throw Object.assign(new Error('Chưa xác nhận Flow đã chọn tỉ lệ '+wanted+'. Chưa gửi prompt.'),{code:'settings_failed'});
  }
  globalThis.FlowSettings={current,apply,applyRatio,selectedRatio,ratioRows};
})();
