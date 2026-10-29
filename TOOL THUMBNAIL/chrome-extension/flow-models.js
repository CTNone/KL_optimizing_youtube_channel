(() => {
  const names = /Nano Banana(?:\s+\d+(?:\.\d+)*)?(?:\s+(?:Pro|Lite))?|Imagen\s+\d+(?:\s+(?:Ultra|Fast))?/i;
  const optionOwners=new WeakSet();
  const modelControls=new WeakSet();
  function plainOptions(order) {
    const exact=e=>{
      // Material Symbols expose their ligature (for example "banana")
      // through innerText; those words are icons, not part of the model.
      const model=name(e,order);
      if(!model)return false;
      const value=(e.innerText || e.textContent || '').replace(/\s+/g,' ').trim();
      const start=value.toLowerCase().indexOf(model.toLowerCase());
      if(start<0)return false;
      const rest=(value.slice(0,start)+' '+value.slice(start+model.length)).replace(/🍌/gu,'').replace(/\b(?:banana|check|check_small|done|keyboard_arrow_down|expand_more)\b/gi,'').trim();
      return !rest;
    };
    const labels=[...document.querySelectorAll('div,span,button,[role="button"]')].filter(visible).filter(exact);
    const rows=[];
    for(const label of labels) {
      let row=label;
      for(let depth=0;depth<4 && row?.parentElement;depth++,row=row.parentElement) {
        if(!exact(row))break;
        const siblings=[...row.parentElement.children].filter(visible).filter(exact);
        if(new Set(siblings.map(e=>name(e,order))).size<2)continue;
        for(const sibling of siblings){optionOwners.add(sibling);if(!rows.includes(sibling))rows.push(sibling);}
        break;
      }
    }
    return rows;
  }
  const visible = e => e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden';
  const text = e => [e.innerText || e.textContent || '',e.getAttribute?.('aria-label'),e.getAttribute?.('title'),e.getAttribute?.('data-value')].filter(Boolean).join(' ').trim();
  function name(e, order=[]) {
    const value = text(e);
    const standard=value.match(names)?.[0];
    if(standard)return order.find(n=>n.toLowerCase()===standard.toLowerCase()) || standard;
    return [...order].sort((a,b)=>b.length-a.length).find(n=>value.toLowerCase().includes(n.toLowerCase())) || null;
  }
  function detect(editor, order=[]) {
    const combos=[...document.querySelectorAll('[role="combobox"]')].filter(visible).map(element=>({element,name:name(element,order)})).filter(row=>row.name);
    if(combos.length===1)return combos[0];
    const box = editor.getBoundingClientRect();
    const found = [...document.querySelectorAll('button,[role="button"]')].filter(visible).filter(e=>{
      const r=e.getBoundingClientRect();return r.top>=box.top-30 && r.top<=box.bottom+180 && r.left>=box.left-30 && r.right<=box.right+180;
    }).filter(e=>!['option','menuitem','menuitemradio'].includes(e.getAttribute('role'))).map(e=>({element:e,name:name(e,order)})).filter(x=>x.name);
    if(found.length===1)return found[0];
    // Settings may be a portal outside the composer. Only selected controls
    // identify the active model; ordinary menu options are never evidence.
    const selected=[...document.querySelectorAll('[role="combobox"],[aria-selected="true"],[role="menuitemradio"][aria-checked="true"],[data-state="checked"]')].filter(visible).map(e=>({element:e,name:name(e,order)})).filter(x=>x.name);
    return selected.length===1 ? selected[0] : null;
  }
  async function waitFor(read,sleep,check,description) {
    for(let i=0;i<30;i++){check();const value=read();if(value)return value;await sleep(150);}
    throw new Error(description);
  }
  async function prepare({editor,order,click,sleep,check}) {
    const current=detect(editor(),order);
    if(current)return current;
    const box=editor().getBoundingClientRect();
    const settings=[...document.querySelectorAll('button,[role="button"]')].filter(visible).filter(e=>{
      const r=e.getBoundingClientRect();
      return /\b(settings|tune|options)\b|cài đặt|thiết lập/i.test(text(e)) && r.top>=box.top-60 && r.top<=box.bottom+180 && r.left>=box.left-60 && r.right<=box.right+180;
    });
    if(settings.length!==1)throw new Error('Không thấy duy nhất nút cài đặt mô hình cạnh ô prompt. Chưa gửi.');
    modelControls.add(settings[0]);await click(settings[0]);
    return waitFor(()=>detect(editor(),order),sleep,check,'Đã mở cài đặt nhưng chưa đọc được mô hình đang chọn.');
  }
  function lower(current, available, order, blocked) {
    const usable=available.filter(n=>n!==current&&!blocked[n]?.disabled);
    if(order.length){const i=order.indexOf(current);return i<0?null:order.slice(i+1).find(n=>usable.includes(n)) || null;}
    // Only infer tiers within the same family/version; never rank unrelated models.
    const family=n=>n.replace(/\s+(Pro|Ultra|Lite|Fast)$/i,'').toLowerCase();
    const tier=n=>/\b(Pro|Ultra)$/i.test(n)?3:/\b(Lite|Fast)$/i.test(n)?1:2;
    return usable.filter(n=>family(n)===family(current)&&tier(n)<tier(current)).sort((a,b)=>tier(b)-tier(a))[0] || null;
  }
  async function downgrade({editor,order,blocked,click,sleep,check,dismiss,highest=false}) {
    const current=await prepare({editor,order,click,sleep,check});
    const close=async()=>{if(dismiss)await dismiss();else await click(editor());await sleep(200);check();};
    if(highest && order.find(n=>!blocked[n]?.disabled)===current.name){if(dismiss)await close();return current.name;}
    const optionsOnPage=()=>{
      const rows=[...document.querySelectorAll('[role="option"],[role="menuitem"],[role="menuitemradio"],[role="menu"] button,[role="listbox"] button')].filter(visible).filter(e=>name(e,order));
      const semantic=rows.filter(e=>!rows.some(child=>child!==e && e.contains?.(child)));
      semantic.forEach(e=>optionOwners.add(e));
      return semantic.length?semantic:plainOptions(order);
    };
    // If the dropdown is already open, use its options. The underlying
    // trigger may legitimately be covered by the dropdown portal.
    let options=optionsOnPage();
    if(!options.length) {
      modelControls.add(current.element);
      await click(current.element);check();
      options=await waitFor(()=>{
        const rows=optionsOnPage();if(rows.length)return rows;
        // Composer settings and the model dropdown are separate layers.
        // Re-read the controls after Flow renders the settings portal.
        const fresh=detect(editor(),order);
        const triggers=[...document.querySelectorAll('button,[role="button"],[role="combobox"]')].filter(visible).filter(e=>e!==current.element&&name(e,order)===current.name);
        return fresh?.element!==current.element && fresh?.name===current.name || triggers.length===1 ? [] : null;
      },sleep,check,'Menu mô hình chưa sẵn sàng sau khi mở cài đặt.');
    }
    if(!options.some(e=>name(e,order))) {
      const fresh=detect(editor(),order);
      const triggers=fresh?.element!==current.element && fresh?.name===current.name?[fresh.element]:[...document.querySelectorAll('button,[role="button"],[role="combobox"]')].filter(visible).filter(e=>name(e,order)===current.name && e!==current.element);
      if(triggers.length!==1) throw new Error('Không tìm thấy menu mô hình. Đóng menu Flow trước khi chạy lại.');
      modelControls.add(triggers[0]);await click(triggers[0]);
      options=await waitFor(()=>{const rows=optionsOnPage();return rows.some(e=>name(e,order))?rows:null;},sleep,check,'Không đọc được danh sách mô hình.');
    }
    const selectable=options.filter(e=>!e.disabled && e.getAttribute('aria-disabled')!=='true');
    const available=selectable.map(e=>name(e,order)).filter(Boolean);
    const next=highest ? order.find(n=>available.includes(n)&&!blocked[n]?.disabled) : lower(current.name,available,order,blocked);
    if(!next) {
      await close();
      if(highest)throw new Error('Không có mô hình khả dụng được xác minh trong menu và danh sách ưu tiên.');
      if(blocked[current.name]?.disabled)throw new Error('Mô hình đã bị vô hiệu hóa và không có mô hình thay thế.');
      return current.name;
    }
    const matches=selectable.filter(e=>name(e,order)===next);
    if(matches.length!==1) throw new Error('Mô hình thay thế không khớp duy nhất hoặc bị khóa.');
    try {await click(matches[0]);}
    catch(error){throw Object.assign(new Error('Không bấm được dòng mô hình '+next+' ('+matches[0].tagName+', role='+matches[0].getAttribute('role')+'): '+error.message),{code:error.code});}
    // Verify after dismissing: a highlighted menu item is not evidence that
    // the composer is actually configured to use that model.
    await close();
    await waitFor(()=>detect(editor(),order)?.name===next,sleep,check,'Chưa xác nhận Flow đã chuyển sang '+next+'. Không gửi prompt.');
    return next;
  }
  globalThis.FlowModels={detect,prepare,lower,downgrade,isOption:e=>optionOwners.has(e),isControl:e=>modelControls.has(e),chooseBest:options=>downgrade({...options,highest:true})};
})();
