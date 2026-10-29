(() => {
  if (globalThis.__flowTxtInstalled) return;
  globalThis.__flowTxtInstalled = true;
  let stopped = false;
  let pickedGenerate = null;
  let pickedIdentity = null;
  let cancelPicker = null;
  let pendingClick = null;
  let failureMonitor = null;
  let runActive = false;
  let lastVerifiedModel=null;
  let attachedReference=false;
  async function attachReference(reference,cfg) {
    if(!reference || attachedReference)return;
    if(globalThis.__desktopReference) {
      const result=await globalThis.__desktopReference(reference);
      if(!result?.ok)throw Object.assign(new Error(result?.error || 'Desktop chưa tải được ảnh mẫu.'),{code:result?.code || 'reference_unverified'});
      attachedReference=true;log('Desktop đã xác nhận ảnh mẫu đính kèm trên Flow.');return;
    }
    if(!/^data:image\/(jpeg|png|webp);base64,/.test(reference.data || '') || reference.data.length>6*1024*1024)throw new Error('Ảnh mẫu NCTT không hợp lệ.');
    let composer=editor(cfg).parentElement;
    for(let i=0;i<2 && composer?.parentElement;i++)composer=composer.parentElement;
    if(!composer)throw new Error('Không xác định được vùng đính kèm ảnh của Flow.');
    const before=new Set([...composer.querySelectorAll('img')].map(e=>e.currentSrc || e.src));
    const inputs=()=>[...document.querySelectorAll('input[type="file"]')].filter(e=>!e.disabled && /image|\.png|\.jpg|\.jpeg|\.webp/i.test(e.getAttribute('accept') || ''));
    const controls=()=>[...document.querySelectorAll('button,[role="button"],[role="menuitem"]')].filter(visible).filter(e=>!e.disabled && e.getAttribute('aria-disabled')!=='true');
    const label=e=>[e.innerText || e.textContent || '',e.getAttribute('aria-label') || '',e.getAttribute('title') || ''].join(' ').trim();
    const upload=()=>controls().filter(e=>/tải (?:nội dung|hình ảnh|ảnh|tệp)|upload (?:image|media|file)|^upload$/i.test(label(e)));
    if(!inputs().length && !upload().length) {
      const plus=controls().filter(e=>composer.contains(e) && [e.innerText || e.textContent || '',e.getAttribute('aria-label') || '',e.getAttribute('title') || ''].some(value=>/^(?:add|add_2|\+|thêm|thêm nội dung|thêm thành phần|add media|add assets|add ingredients?)$/i.test(value.trim())));
      if(plus.length!==1)throw new Error('Không tìm được duy nhất nút + thêm ảnh cạnh prompt trên Flow.');
      plus[0].click();log('Đã mở bộ chọn tài nguyên Flow.');
      for(let i=0;i<40 && !inputs().length && !upload().length;i++){checkStop();await sleep(150);}
    }
    const candidates=inputs();
    if(reference.path) {
      const buttons=upload();const target=candidates.length===1?candidates[0]:buttons.length===1?buttons[0]:null;
      if(!target)throw new Error('Không tìm được duy nhất nút Tải nội dung lên trong bộ chọn Flow.');
      const token=crypto.randomUUID();target.setAttribute('data-flowtxt-upload',token);
      try {const result=await chrome.runtime.sendMessage({type:'nativeUpload',path:reference.path,token,input:target===candidates[0]});if(!result?.ok)throw new Error(result?.error || 'Không tải được ảnh lên Flow.');}
      finally {target.removeAttribute('data-flowtxt-upload');}
    } else {
      if(candidates.length!==1)throw new Error('Ảnh mẫu thiếu file cục bộ. Tải lại panel và chọn lại ảnh.');
      const blob=await (await fetch(reference.data)).blob();
      const transfer=new DataTransfer();transfer.items.add(new File([blob],reference.name || 'nctt_reference.jpg',{type:blob.type}));
      candidates[0].files=transfer.files;candidates[0].dispatchEvent(new Event('change',{bubbles:true}));
    }
    log('Đã tải ảnh mẫu; đang chờ Flow thêm vào câu lệnh.');
    const deadline=Date.now()+45000;let added=false;
    while(Date.now()<deadline) {
      checkStop();
      const box=editor(cfg).getBoundingClientRect();
      const previews=[...composer.querySelectorAll('img')].filter(visible).filter(e=>{
        const r=e.getBoundingClientRect();
        return e.complete && e.naturalWidth>0 && !before.has(e.currentSrc || e.src) && r.top>=box.top-240 && r.bottom<=box.bottom+120 && r.left>=box.left-40 && r.right<=box.right+40 && r.right-r.left<=260 && r.bottom-r.top<=260;
      });
      const add=controls().filter(e=>/thêm vào câu lệnh|add to prompt/i.test(label(e)));
      // Asset picker previews are not composer attachments. Complete its
      // explicit confirmation before accepting a new composer preview.
      if(!added && add.length===1){add[0].click();added=true;log('Đã bấm Thêm vào câu lệnh.');await sleep(300);continue;}
      if(previews.length && !add.length){attachedReference=true;log('Đã thấy ảnh mẫu NCTT được đính kèm trên Flow.');return;}
      await sleep(250);
    }
    throw new Error('Flow chưa hiển thị ảnh mẫu sau tải lên. Không gửi prompt để tránh tạo ảnh thiếu tham chiếu.');
  }
  const currentModelName = value => value==='Nano Banana 2'?'Nano Banana 2.1':value==='Nano Banana Lite'?'Nano Banana 2 Lite':value;
  const orderFor = cfg => (cfg.modelOrder?.trim() || 'Nano Banana Pro\nNano Banana 2.1\nNano Banana 2 Lite').split('\n').map(s=>currentModelName(s.trim())).filter(Boolean);
  async function dismissMenus() {
    const result=await chrome.runtime.sendMessage({type:'nativeEscape'});
    if(!result?.ok)throw new Error(result?.error || 'Không đóng được menu mô hình.');
  }
  async function clickControl(button,cfg) {
    checkStop();
    // Model menu controls are uniquely matched by FlowModels. Activate that
    // semantic button directly: portal/animation hit testing can reject a
    // perfectly valid row. This path never applies to Send or Download.
    if((globalThis.FlowModels?.isOption(button) || globalThis.FlowModels?.isControl(button)) && typeof button.click==='function') {
      if(!button.isConnected || !visible(button) || button.disabled || button.getAttribute('aria-disabled')==='true')throw Object.assign(new Error('Dòng mô hình đã thay đổi hoặc bị khóa. Chưa chọn.'),{code:'click_not_sent'});
      log((globalThis.FlowModels?.isOption(button)?'Chọn dòng mô hình':'Mở cài đặt/menu mô hình')+' bằng nút DOM: '+(button.innerText || button.textContent || '').trim());
      button.click();return;
    }
    const bounds=button.getBoundingClientRect();
    if(typeof innerHeight!=='undefined' && (bounds.top<0 || bounds.bottom>innerHeight || bounds.left<0 || bounds.right>innerWidth)) {
      button.scrollIntoView?.({block:'center',inline:'nearest'});
      await sleep(150);checkStop();
    }
    if(cfg.clickMode==='dom') {button.click();return;}
    pendingClick={button,token:crypto.randomUUID()};
    try {const response=await chrome.runtime.sendMessage({type:'nativeClick',token:pendingClick.token});if(!response?.ok)throw Object.assign(new Error(response?.error || 'Không bấm được điều khiển Flow.'),{code:response?.code || 'click_uncertain'});}
    finally {pendingClick=null;}
  }
  function clickPoint(button) {
    checkStop();
    if(globalThis.FlowClicks)return FlowClicks.point(button,{document,visible,width:innerWidth,height:innerHeight});
    if(!button?.isConnected || !visible(button) || button.disabled || button.getAttribute('aria-disabled') === 'true') throw new Error('Nút gửi đã biến mất hoặc đang bị khóa. Chưa bấm.');
    const r = button.getBoundingClientRect();
    const x = (r.left+r.right)/2, y = (r.top+r.bottom)/2;
    if(x < 0 || y < 0 || x >= innerWidth || y >= innerHeight) throw new Error('Nút gửi nằm ngoài vùng nhìn thấy. Chưa bấm.');
    const hit = document.elementFromPoint(x,y);
    if(!hit || (hit !== button && !button.contains(hit))) throw new Error(`Điểm bấm bị phần tử ${hit?.tagName || 'không rõ'} che. Đóng menu/hộp thoại trên Flow trước.`);
    return {x,y};
  }
  let state = {running:false, logs:[], items:[]};
  const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
  const visible = e => e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden';
  const all = (css, root = document) => [...root.querySelectorAll(css)];
  const log = text => { state.logs.push(`${new Date().toLocaleTimeString()} ${text}`); persist(); };
  const persist = () => chrome.storage.local.set({lastRun:state}).catch(() => {});
  const checkStop = () => {
    if(stopped) throw new Error('Đã dừng. Tác vụ đã gửi cho Google vẫn có thể đang chạy.');
    failureMonitor?.check();
  };
  function one(css) {
    const elements = all(css).filter(visible);
    if(elements.length !== 1) throw new Error(`Bộ chọn phải khớp đúng 1 phần tử hiển thị (hiện ${elements.length}): ${css}`);
    return elements[0];
  }
  function validate(cfg) {
    for(const key of ['prompt','generate','card','image']) {
      if(cfg[key]) all(cfg[key]);
    }
    if(cfg.original) all(cfg.original);
    if(!Number.isInteger(+cfg.count) || +cfg.count < 1 || +cfg.count > 8 || !Number.isFinite(+cfg.timeout) || +cfg.timeout < 10) throw new Error('Số ảnh 1–8 và thời gian chờ tối thiểu 10 giây.');
    editor(cfg);
    if(cfg.original && !cfg.card) throw new Error('Link ảnh gốc cần cấu hình thẻ chứa ảnh ở mục nâng cao.');
  }
  function editor(cfg) {
    if(cfg.prompt) return one(cfg.prompt);
    const candidates = all('textarea, [contenteditable="true"]').filter(visible);
    const named = candidates.filter(e => /Bạn muốn tạo|What do you want to create/i.test([e.getAttribute('placeholder'), e.getAttribute('data-placeholder'), e.getAttribute('aria-label'), e.textContent].join(' ')));
    if(named.length === 1) return named[0];
    if(candidates.length === 1) return candidates[0];
    throw new Error('Chưa nhận diện được duy nhất ô prompt. Đóng menu Flow rồi kiểm tra lại, hoặc cấu hình ô nhập ở mục nâng cao.');
  }
  function generate(cfg, afterFill = false) {
    if(cfg.generate) return one(cfg.generate);
    if(!afterFill && pickedGenerate?.isConnected && visible(pickedGenerate)) return pickedGenerate;
    const input = editor(cfg), box = input.getBoundingClientRect();
    const near = all('button, [role="button"]').filter(visible).filter(e => {
      const r = e.getBoundingClientRect();
      return r.left >= box.left && r.left <= box.right + 160 && r.top >= box.top - 24 && r.top <= box.bottom + 150;
    });
    const matches = near.filter(e => {
      const labels = [e.getAttribute('aria-label'), e.getAttribute('title'), e.textContent, ...all('svg title, i, [class*="material-symbol"], [class*="material-icon"]',e).map(n => n.textContent)].filter(Boolean).map(s => s.trim());
      return labels.some(s => /^(arrow_forward|arrow_upward|send|generate|create|tạo|tạo ảnh|gửi|→|↑)$/i.test(s));
    });
    const enabled = e => !e.disabled && e.getAttribute('aria-disabled') !== 'true';
    const semantic = afterFill ? matches.filter(enabled) : matches;
    if(semantic.length === 1) return semantic[0];
    if(afterFill && semantic.length === 0) {
      // Current Flow composer: active send is a small light circular control
      // at the lower right, distinct from the clear-text X above it.
      const visual = near.filter(e => {
        const r = e.getBoundingClientRect(), style = getComputedStyle(e);
        const channels = style.backgroundColor?.match(/[\d.]+/g)?.map(Number);
        const width = r.right-r.left, height = r.bottom-r.top;
        return enabled(e) && channels?.length >= 3 && channels.slice(0,3).every(v=>v>=220) &&
          (channels.length < 4 || channels[3] >= 0.9) && width >= 28 && width <= 64 && height >= 28 && height <= 64 &&
          Math.abs(width-height) <= 8 && r.left >= box.right-100 && r.top >= box.bottom-4;
      });
      if(visual.length === 1) return visual[0];
    }
    if(pickedIdentity) {
      if(pickedIdentity.manual) throw new Error('Phần tử gửi đã thay đổi. Chọn lại nút tạo trên Flow.');
      const replacements = near.filter(e => {
        const r = e.getBoundingClientRect();
        return e.tagName === pickedIdentity.tag &&
          (e.getAttribute('aria-label') || '') === pickedIdentity.label &&
          (e.getAttribute('title') || '') === pickedIdentity.title &&
          (e.textContent || '').trim() === pickedIdentity.text &&
          Math.abs((r.right - box.right) - pickedIdentity.right) < 40 &&
          Math.abs((r.bottom - box.bottom) - pickedIdentity.bottom) < 60;
      });
      if(replacements.length === 1) { pickedGenerate = replacements[0]; return pickedGenerate; }
      throw new Error('Flow đã thay đổi nút đã chọn. Hãy chọn lại mũi tên gửi lệnh.');
    }
    throw new Error('Chưa xác định chắc chắn nút tạo. Bấm “Chọn nút tạo trên Flow”, rồi chọn mũi tên bên phải ô prompt.');
  }
  function pickGenerate() {
    if(state.running) throw new Error('Dừng danh sách trước khi chọn nút.');
    cancelPicker?.();
    let selected = false;
    // Capture on our own layer: disabled buttons and pointer-events:none icons
    // do not reliably emit click/pointer events on the underlying button.
    const shield = document.createElement('div');
    Object.assign(shield.style,{position:'fixed',inset:'0',zIndex:'2147483646',cursor:'crosshair',background:'rgba(23,103,203,0.03)'});
    document.documentElement.append(shield);
    const banner = document.createElement('div');
    banner.textContent = 'Flow TXT: bấm mũi tên TẠO bên phải ô prompt. Lần bấm này chỉ chọn nút, không gửi prompt. Esc để hủy.';
    Object.assign(banner.style,{position:'fixed',top:'0',left:'0',right:'0',padding:'16px',background:'#1767cb',color:'white',zIndex:'2147483647',font:'16px sans-serif',pointerEvents:'none'});
    document.documentElement.append(banner);
    const cleanup = () => {
      for(const type of ['pointerdown','pointerup','mousedown','mouseup','click']) window.removeEventListener(type,capture,true);
      window.removeEventListener('keydown',escape,true); banner.remove(); shield.remove(); cancelPicker = null;
    };
    const escape = e => { if(e.key === 'Escape') { cleanup(); log('Đã hủy chọn nút.'); } };
    const capture = e => {
      e.preventDefault(); e.stopImmediatePropagation();
      if(selected || (e.type !== 'pointerdown' && e.type !== 'click')) return;
      try {
      shield.style.pointerEvents = 'none';
      let hit = document.elementFromPoint(e.clientX,e.clientY);
      while(hit?.shadowRoot?.elementFromPoint) {
        const inner = hit.shadowRoot.elementFromPoint(e.clientX,e.clientY);
        if(!inner || inner === hit) break;
        hit = inner;
      }
      shield.style.pointerEvents = 'auto';
      let target = hit?.closest('button, [role="button"]');
      if(!target) {
        const candidates = all('button, [role="button"]').filter(visible).filter(node => {
          const r = node.getBoundingClientRect();
          return e.clientX >= r.left && e.clientX <= r.right && e.clientY >= r.top && e.clientY <= r.bottom;
        });
        if(candidates.length === 1) target = candidates[0];
      }
      // Explicit user selection may be an SVG, span or custom element with a
      // delegated handler, rather than a semantic button. Do not require the
      // editor to be detected just to record that selection.
      if(!target && hit) target = hit.closest('[tabindex], [onclick]') || hit.closest('svg') || hit;
      if(!target || !target.tagName || ['HTML','BODY','IFRAME'].includes(target.tagName) || target.closest?.('input, textarea, [contenteditable="true"]')) {
        const detail = hit?.tagName || 'không có phần tử';
        banner.textContent = `Không chọn được tại điểm này (${detail}). Hãy bấm chính biểu tượng mũi tên. Esc để hủy.`;
        log(`Chọn nút thất bại: điểm ${Math.round(e.clientX)},${Math.round(e.clientY)}, phần tử ${detail}.`);
        return;
      }
      const r = target.getBoundingClientRect();
      let box = null;
      try { box = editor({}).getBoundingClientRect(); } catch { /* Choosing does not depend on editor detection. */ }
      pickedGenerate = target;
      pickedIdentity = {tag:target.tagName,label:target.getAttribute('aria-label') || '',title:target.getAttribute('title') || '',text:(target.textContent || '').trim(),right:box ? r.right-box.right : 0,bottom:box ? r.bottom-box.bottom : 0,manual:!box || !target.matches?.('button, [role="button"]')};
      selected = true;
      banner.textContent = 'Đã chọn nút tạo. Quay lại tab Flow TXT và bấm Kiểm tra nhận diện. Esc để đóng thanh này.';
      log(`Đã chọn nút gửi: ${pickedIdentity.tag} ${pickedIdentity.label || pickedIdentity.text || '(biểu tượng)'}. ${target.disabled ? 'Nút đang bị khóa khi prompt trống; tool sẽ chờ sau khi nhập.' : ''} Quay lại Flow TXT, bấm Kiểm tra nhận diện.`);
      } catch(error) {
        shield.style.pointerEvents = 'auto';
        banner.textContent = 'Lỗi chọn nút: ' + error.message;
        log('Lỗi chọn nút: ' + error.message);
      }
    };
    for(const type of ['pointerdown','pointerup','mousedown','mouseup','click']) window.addEventListener(type,capture,true);
    window.addEventListener('keydown',escape,true); cancelPicker = cleanup;
  }
  function results(cfg) {
    if(!cfg.card) {
      const input = editor(cfg);
      return all(cfg.image || 'img').filter(img => {
        const r = img.getBoundingClientRect();
        return visible(img) && r.width >= 200 && r.height >= 140 && !input.contains(img);
      }).map(img => ({card:img.parentElement,img,src:img.currentSrc || img.src})).filter(r => r.src);
    }
    return all(cfg.card).flatMap(card => {
      const imgs = all(cfg.image || 'img', card);
      if(imgs.length !== 1) return [];
      const img = imgs[0], src = img.currentSrc || img.src;
      return src ? [{card, img, src}] : [];
    });
  }
  function fill(element, text) {
    element.focus();
    if(element instanceof HTMLTextAreaElement || element instanceof HTMLInputElement) {
      const proto = element instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
      Object.getOwnPropertyDescriptor(proto, 'value').set.call(element, text);
      element.dispatchEvent(new Event('input', {bubbles:true}));
      element.dispatchEvent(new Event('change', {bubbles:true}));
    } else if(element.isContentEditable) {
      const selection = getSelection(), range = document.createRange();
      range.selectNodeContents(element); selection.removeAllRanges(); selection.addRange(range);
      if(!document.execCommand('insertText', false, text)) throw new Error('Không nhập được vào trình soạn thảo Flow.');
    } else throw new Error('Bộ chọn prompt không phải ô soạn thảo.');
  }
  async function download(url, filename) {
    if(url.startsWith('blob:')) {
      const response = await fetch(url), blob = await response.blob();
      url = await new Promise((resolve,reject) => { const reader = new FileReader(); reader.onload = () => resolve(reader.result); reader.onerror = reject; reader.readAsDataURL(blob); });
    }
    const result = await chrome.runtime.sendMessage({type:'download', url, filename});
    if(result.error) throw new Error(result.error);
    for(let i = 0; i < 240; i++) {
      checkStop();
      const item = await chrome.runtime.sendMessage({type:'downloadStatus', id:result.id});
      if(item.error || item.state === 'interrupted') throw new Error(item.error || 'Tải ảnh bị gián đoạn.');
      if(item.state === 'complete') {
        if(!item.mime?.startsWith('image/')) throw new Error(`File tải về chưa được xác nhận là ảnh (${item.mime || 'không rõ MIME'}). Kiểm tra file trước khi chạy tiếp.`);
        return item.filename;
      }
      await sleep(500);
    }
    throw new Error('Quá thời gian tải ảnh. Kiểm tra mục Downloads của Chrome.');
  }
  async function saveImageToFolder(url, path) {
    let response;
    try { response = await fetch(url,{credentials:'include',signal:AbortSignal.timeout(30000)}); }
    catch { response = await fetch(url,{credentials:'omit',signal:AbortSignal.timeout(30000)}); }
    if(!response.ok) throw new Error(`Không đọc được ảnh để lưu (HTTP ${response.status}). Chọn chế độ Chrome Downloads hoặc kiểm tra quyền truy cập ảnh.`);
    const blob = await response.blob();
    const extensions = {'image/png':'png','image/jpeg':'jpg','image/webp':'webp','image/avif':'avif'};
    const ext = extensions[blob.type.split(';')[0]];
    if(!ext || !blob.size || blob.size > 20*1024*1024) throw new Error('Ảnh không đúng định dạng hoặc vượt 20 MB. Chưa đánh dấu tải thành công.');
    const data = await new Promise((resolve,reject)=>{
      const reader = new FileReader(); reader.onload=()=>resolve(reader.result); reader.onerror=()=>reject(new Error('Không đọc được dữ liệu ảnh.')); reader.readAsDataURL(blob);
    });
    checkStop();
    const result = await chrome.runtime.sendMessage({type:'writeImage',path:path.replace(/\.[^.]+$/,'.'+ext),data});
    if(!result?.ok) throw new Error(result?.error || 'Không ghi được ảnh vào thư mục.');
    return result.filename;
  }
  async function runAttempt({cfg, prompt, fileName, attempt, reference}) {
    const preparedModel=state.model;
    const earlierLogs=state.logs || [];
    state = {running:true, fileName, flowMessage:null, logs:[...earlierLogs], items:[], folder:'Flow_TXT/run_' + new Date().toISOString().replace(/[^\d]/g, '_')};
    state.attempt=attempt;
    state.model=globalThis.FlowModels?.detect(editor(cfg),orderFor(cfg))?.name || preparedModel || null;
    log(`Lần ${attempt}/2 — mô hình: ${state.model || 'chưa nhận diện'}.`);
    try {
      {
        checkStop();
        const record = {number:1, prompt, status:'preparing', files:[], expected:Number(cfg.count)};
        state.items.push(record);
        failureMonitor?.disconnect();
        failureMonitor = globalThis.FlowErrors?.watch({visible,prompt,ignoreExisting:attempt>1}) || null;
        checkStop();
        validate(cfg);
        if(globalThis.FlowSettings) {
          record.status='configuring';
          const settings={editor:()=>editor(cfg),order:orderFor(cfg),click:e=>clickControl(e,cfg),sleep,check:checkStop};
          await globalThis.FlowModels?.prepare(settings);
          const ratio=await FlowSettings.applyRatio({...settings,cfg});
          if(ratio){state.flowRatio=ratio;record.aspectRatio=ratio;log('Đã xác nhận tỉ lệ ảnh trên Flow: '+ratio+'.');}
          state.flowCount=await FlowSettings.apply({...settings,cfg});
          const actual=await globalThis.FlowModels?.prepare(settings);
          if(cfg.modelChoice && actual?.name!==cfg.modelChoice)throw Object.assign(new Error('Flow đang chọn '+(actual?.name || 'không rõ')+' thay vì '+cfg.modelChoice+'. Chưa gửi prompt.'),{code:'settings_failed'});
          if(actual?.name)state.model=actual.name;
          log('Đã xác nhận số ảnh trên Flow: x'+state.flowCount+'.');
          await dismissMenus();await sleep(200);
        }
        const observationDelay=Number(cfg.observationDelayMs) || 0;
        const baselineSources=new Set(all('img').map(img=>img.currentSrc || img.src).filter(Boolean));
        await attachReference(reference,cfg);
        if(observationDelay){log('Ảnh mẫu đã đính kèm. Chờ giao diện ổn định trước khi nhập prompt…');await sleep(observationDelay*2);checkStop();}
        const imageIdentity=src=>globalThis.FlowDownloads?.identity?.(src) || src;
        for(const img of all('img'))if(img.currentSrc || img.src)baselineSources.add(img.currentSrc || img.src);
        const before = new Set([...baselineSources].map(imageIdentity));
        fill(editor(cfg), prompt);
        log('Đã nhập toàn bộ nội dung file. Đang tìm nút gửi…');
        let button;
        let recognitionError = '';
        const readyDeadline = Date.now() + 10000;
        do {
          await sleep(200);
          checkStop();
          try { button = generate(cfg, true); recognitionError = ''; }
          catch(error) { button = null; recognitionError = error.message; continue; }
          if(!button.disabled && button.getAttribute('aria-disabled') !== 'true') break;
        } while(Date.now() < readyDeadline);
        if(!button) throw new Error('Đã nhập prompt nhưng chưa tìm được nút gửi đang bật sau 10 giây. ' + recognitionError);
        if(button.disabled || button.getAttribute('aria-disabled') === 'true') throw new Error('Đã nhập prompt nhưng nút gửi vẫn bị khóa sau 10 giây. Kiểm tra nội dung trong ô Flow, chế độ tạo ảnh hoặc quota.');
        record.status = 'submitting'; persist();
        if(observationDelay){log('Chuẩn bị bấm Tạo ảnh. Chưa tải ảnh mẫu.');await sleep(observationDelay);checkStop();}
        // Refresh immediately before sending: uploaded assets can finish
        // rendering while prompt/settings are being prepared.
        for(const img of all('img'))if(img.currentSrc || img.src)before.add(imageIdentity(img.currentSrc || img.src));
        for(const identity of globalThis.__studioUploadWatch?.recent?.keys() || [])before.add(identity);
        record.sendButton = {tag:button.tagName,label:button.getAttribute('aria-label') || '',title:button.getAttribute('title') || '',text:(button.textContent || '').trim().slice(0,120)};
        if(cfg.clickMode === 'dom') {
          if(typeof button.click === 'function') button.click();
          else button.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,composed:true,view:window}));
        } else {
          pendingClick = {button, token:crypto.randomUUID()};
          try {
            const response = await chrome.runtime.sendMessage({type:'nativeClick',token:pendingClick.token});
            if(!response?.ok) throw new Error('Chrome chưa bấm được nút: ' + (response?.error || 'không có phản hồi') + '. Không tự gửi lại; kiểm tra Flow trước khi chạy tiếp.');
          } finally { pendingClick = null; }
        }
        record.submitted=true;
        if(cfg.verifySubmission) {
          let acknowledged=false;
          for(let i=0;i<50;i++) {
            checkStop();
            const input=editor(cfg);
            const value=('value' in input?input.value:input.innerText || input.textContent || '').trim();
            if(!value || button.disabled || button.getAttribute('aria-disabled')==='true' || input.getAttribute('aria-busy')==='true'){acknowledged=true;break;}
            await sleep(200);
          }
          if(!acknowledged)throw Object.assign(new Error('Đã bấm nhưng chưa xác nhận Flow nhận prompt tạo ảnh. Không tải ảnh và không tự gửi lại; kiểm tra ô prompt trên Flow.'),{code:'submission_uncertain'});
          log('Đã xác nhận Flow nhận lệnh tạo ảnh. Bắt đầu chờ kết quả mới.');
        }
        if(observationDelay)await sleep(observationDelay*3);
        log(`Đã bấm gửi bằng ${cfg.clickMode === 'dom' ? 'DOM' : 'chuột Chrome'}. Đang chờ ${cfg.count} ảnh.`);
        record.status = 'waiting'; persist();
        const deadline = Date.now() + Number(cfg.timeout)*1000;
        let found = [];
        let stableResults='',stablePolls=0;
        let extraResultsLogged=false;
        let generationFailure=null;
        while(Date.now() < deadline) {
          const input=editor(cfg),box=input.getBoundingClientRect();
          const candidates=results(cfg).filter(r => {
            const bounds=r.img.getBoundingClientRect();
            const composerPreview=bounds.width<=260 && bounds.height<=260 && bounds.top>=box.top-160 && bounds.bottom<=box.bottom+40 && bounds.left>=box.left-40 && bounds.right<=box.right+40;
            return !before.has(imageIdentity(r.src)) && !composerPreview && !r.img.closest?.('[role="dialog"], [contenteditable="true"]') && r.img.isConnected!==false && r.img.complete && r.img.naturalWidth>=256 && r.img.naturalHeight>=256;
          });
          // Count current assets, not every transient URL seen over time.
          // A thumbnail/placeholder replaced by a final image is one result.
          const assets=new Map();
          for(const result of candidates){
            const owner=result.img.closest?.('[data-asset-id],[data-media-id],[data-image-id]');
            const asset=owner?.getAttribute('data-asset-id') || owner?.getAttribute('data-media-id') || owner?.getAttribute('data-image-id');
            const key=asset?'asset:'+asset:imageIdentity(result.src);
            const previous=assets.get(key);
            if(!previous || result.img.getBoundingClientRect().width>previous.img.getBoundingClientRect().width)assets.set(key,result);
          }
          found=[...assets.values()];
          if(found.length>+cfg.count && !extraResultsLogged){log('Flow đang cập nhật nhiều ảnh xem trước. Tiếp tục chờ và gộp kết quả, chưa tải và không gửi lại.');extraResultsLogged=true;}
          try {checkStop();} catch(error) {if(stopped)throw error;generationFailure=error;break;}
          const signature=found.map(r=>imageIdentity(r.src)).sort().join('\n');
          stablePolls=signature===stableResults?stablePolls+1:0;stableResults=signature;
          if(found.length === +cfg.count && (!cfg.verifySubmission || stablePolls>=2)) break;
          await sleep(1000);
        }
        if(!found.length) throw generationFailure || Object.assign(new Error('Hết thời gian chờ, chưa nhận diện được ảnh mới. Chưa xác định Flow đã xử lý xong hay chưa.'),{code:'timeout'});
        if(found.length>+cfg.count)throw new Error('Có nhiều ảnh mới hơn dự kiến. Dừng để tránh lưu nhầm tác vụ khác.');
        if(generationFailure){record.warning=generationFailure.message;record.failureCode=generationFailure.code;if(generationFailure.flowMessage)state.flowMessage=generationFailure.flowMessage;}
        record.created=found.length;
        failureMonitor?.disconnect();failureMonitor=null;
        for(let j = 0; j < found.length; j++) {
          checkStop();
          record.status = 'saving';
          log(`Đang lưu ảnh ${j+1}/${found.length}…`);
          let url = found[j].src;
          if(cfg.original) {
            const links = all(cfg.original, found[j].card);
            if(links.length !== 1 || !links[0].href) throw new Error('Không tìm thấy đúng một link ảnh gốc trong thẻ.');
            url = links[0].href;
          }
          const ext = new URL(url, location.href).pathname.match(/\.(png|jpe?g|webp|avif)$/i)?.[1]?.toLowerCase() || (url.match(/^data:image\/(png|jpeg|webp|avif)/)?.[1]) || 'png';
          const filename = `${state.folder}/0001_${String(j+1).padStart(2,'0')}.${ext === 'jpeg' ? 'jpg' : ext}`;
          for(let saveTry=0;saveTry<2;saveTry++) {
            try {
              checkStop();
              let saved;
              if(globalThis.FlowDownloads) {
                // Keep the verified payload for a save retry: do not trigger a
                // second upscale/download when only the destination failed.
                if(!found[j].verified2k)found[j].verified2k=await FlowDownloads.save({result:found[j],cfg,filename,click:e=>clickControl(e,cfg),sleep,check:checkStop,log});
                const verified=found[j].verified2k;
                if(verified.warning)log('Ảnh 2K đã xác nhận; lưu ý giao diện: '+verified.warning);
                record.resolution={width:verified.image.width,height:verified.image.height};
                if(verified.native)saved=verified.native.filename;
                else if(cfg.saveMode==='downloads' && verified.download)saved=verified.download.filename;
                else if(cfg.saveMode==='downloads')saved=await download(verified.image.data,filename);
                else {
                  const type=verified.image.data.match(/^data:image\/(png|jpeg|webp|avif);/)[1];
                  const path=filename.replace(/^Flow_TXT\//,'').replace(/\.[^.]+$/,'.'+(type==='jpeg'?'jpg':type));
                  const reply=await chrome.runtime.sendMessage({type:'writeImage',path,data:verified.image.data});
                  if(!reply?.ok)throw new Error(reply?.error || 'Không ghi được file 2K.');
                  saved=reply.filename;
                }
                if(verified.sha256 && record.hashes?.includes(verified.sha256))throw Object.assign(new Error('Ảnh 2K trùng nội dung với ảnh đã lưu trong lượt này. Không tính là ảnh mới.'),{code:'duplicate_image'});
                if(verified.sha256)(record.hashes ||= []).push(verified.sha256);
                log(`Đã xác nhận ảnh ${verified.image.width}×${verified.image.height} từ Flow.`);
              } else saved = cfg.saveMode === 'folder'
                ? await saveImageToFolder(new URL(url, location.href).href,filename.replace(/^Flow_TXT\//,''))
                : await download(new URL(url, location.href).href, filename);
              record.files.push(saved);log(`Đã lưu file: ${saved}`);
              const crop=found[j].verified2k?.native?.croppedFilename;
              if(crop){(record.croppedFiles ||= []).push(crop);log('Đã lưu bản cắt 16:9: '+crop);}
              break;
            } catch(error) {
              if(stopped)throw error;
              (record.saveErrors ||= []).push(error.message);log('Lỗi lưu ảnh: '+error.message);
              if(error.code==='click_uncertain'){log('Chưa rõ kết quả nhấn Download/2K. Giữ ảnh đã tạo, không tự bấm lại.');break;}
              if(found[j].downloadStarted && !found[j].pendingDownload){log('Đã yêu cầu tải 2K một lần. Không bấm tải lại để tránh tạo file lặp.');break;}
              if(saveTry===0){log('Thử lưu lại ảnh này một lần, không tạo ảnh mới.');await sleep(500);}
            }
          }
          if(found[j].pendingDownload){await chrome.runtime.sendMessage({type:'cancelFlowDownload',token:found[j].pendingDownload.token}).catch(()=>{});delete found[j].pendingDownload;}
          persist();
        }
        if(!record.files.length)throw Object.assign(new Error('Ảnh đã tạo nhưng chưa lưu được file nào. '+(record.saveErrors || []).join('; ')),{code:'save_failed'});
        record.status = record.files.length < +cfg.count ? 'partial' : 'done';
        log(`Đã lưu ${record.files.length}/${cfg.count} ảnh. ${record.status==='partial'?'Chấp nhận thành công một phần, không tạo lại.':''}`);
      }
      log('HOÀN TẤT.');
    } catch(error) {
      const last = state.items.at(-1);
      if(last && last.status !== 'done') { last.status = last.files.length ? 'partial' : stopped ? 'stopped' : last.created ? 'save_failed' : error.code || 'needs_review'; last.error = error.message; }
      if(error.flowMessage) state.flowMessage = error.flowMessage;
      log('DỪNG: ' + error.message);
    } finally { failureMonitor?.disconnect(); failureMonitor = null; persist(); }
  }
  async function runSingle(args) {
    runActive=true;stopped=false;attachedReference=false;
    state={running:true,logs:[],items:[],fileName:args.fileName};
    const id=args.recovery?.id || Date.now()+'_'+Math.random().toString(36).slice(2);
    const attempts=args.recovery?.attempts || [];
    let handedOff=false;
    async function recover(reason) {
      if(args.recovery?.nextAttempt===2 || stopped || state.items[0]?.created || state.items[0]?.files?.length)return false;
      log('Gặp sự cố. Lưu trạng thái rồi F5 đúng tab Flow một lần.');
      const response=await chrome.runtime.sendMessage({type:'recoverRun',checkpoint:{id,args:{cfg:args.cfg,reference:args.reference,prompt:args.prompt,fileName:args.fileName},attempts,nextAttempt:2,reason,previousModel:state.model}});
      if(!response?.ok)throw new Error(response?.error || 'Không lên lịch F5 được.');
      handedOff=true;state.reloading=true;persist();return true;
    }
    try {
      if(args.recovery){
        const ready=Date.now()+15000;
        while(true){checkStop();try{editor(args.cfg);break;}catch(error){if(Date.now()>ready)throw error;await sleep(250);}}
      }
      const records=await chrome.runtime.sendMessage({type:'readRecords'});
      if(records?.error)throw new Error(records.error);
      let limits=records?.limits || {};
      if(globalThis.FlowModels?.prepare)await FlowModels.prepare({editor:()=>editor(args.cfg),order:orderFor(args.cfg),click:e=>clickControl(e,args.cfg),sleep,check:checkStop});
      const current=globalThis.FlowModels?.detect(editor(args.cfg),orderFor(args.cfg))?.name;
      state.model=current || null;
      let switched=false;
      if(globalThis.FlowModels && (args.recovery?.nextAttempt!==2 || args.cfg.modelChoice)) {
        state.selectingModel=true;
        const requested=currentModelName(args.cfg.modelChoice);
        if(requested)args.cfg.modelChoice=requested;
        log(requested?'Chọn đúng mô hình trong tool: '+requested+'.':'Kiểm tra menu mô hình: chọn mức ưu tiên cao nhất chưa bị khóa.');
        if(requested && limits[requested]?.disabled)throw new Error('Mô hình '+requested+' đã bị khóa sau 3 lần báo hạn mức. Chọn mô hình khác.');
        state.model=await FlowModels.chooseBest({editor:()=>editor(args.cfg),order:requested?[requested]:orderFor(args.cfg),blocked:limits,click:e=>clickControl(e,args.cfg),sleep,check:checkStop,dismiss:dismissMenus});
        state.selectingModel=false;log('Mô hình dùng cho lượt đầu: '+state.model);
        lastVerifiedModel={name:state.model,time:new Date().toISOString()};
        switched=true;
      } else if(current && limits[current]?.disabled) {
        log('Mô hình hiện tại đã bị đánh dấu không dùng. Đang chọn mô hình thấp hơn.');
        state.model=await FlowModels.downgrade({editor:()=>editor(args.cfg),order:orderFor(args.cfg),blocked:limits,click:e=>clickControl(e,args.cfg),sleep,check:checkStop,dismiss:dismissMenus});
        switched=true;
      }
      if(args.recovery?.nextAttempt===2 && !args.cfg.modelChoice && !switched && args.recovery.reason!=='blocked_policy' && ['blocked_model_limit','blocked_rate_limit','blocked_generation','timeout'].includes(args.recovery.reason) && globalThis.FlowModels && current) {
        log('Sau F5: chọn mô hình thấp hơn theo thứ tự ưu tiên.');
        state.model=await FlowModels.downgrade({editor:()=>editor(args.cfg),order:orderFor(args.cfg),blocked:limits,click:e=>clickControl(e,args.cfg),sleep,check:checkStop,dismiss:dismissMenus});
      }
      for(let attempt=args.recovery?.nextAttempt || 1;attempt<=2;attempt++) {
        checkStop();
        await runAttempt({...args,attempt});
        const item=state.items[0];
        attempts.push({attempt,model:state.model,time:new Date().toISOString(),status:item?.status,reason:item?.error || item?.warning || item?.saveErrors?.join('; ') || null,flowMessage:state.flowMessage,files:[...(item?.files || []),...(item?.croppedFiles || [])]});
        if(item?.submitted && state.model && (item?.status==='blocked_model_limit' || item?.failureCode==='blocked_model_limit')) {
          const reply=await chrome.runtime.sendMessage({type:'quotaHit',model:state.model,runId:id,attempt});limits=reply?.limits || limits;
          log(`Hạn mức ${state.model}: ${limits[state.model]?.count || 0}/3 lần. ${limits[state.model]?.disabled?'Đã đánh dấu không dùng.':''}`);
        }
        state.attempts=attempts;state.modelLimits=limits;
        await chrome.runtime.sendMessage({type:'saveHistory',run:{id,fileName:args.fileName,prompt:args.prompt.slice(0,20000),time:new Date().toISOString(),attempts,status:item?.status}});
        if(stopped || attempt===2 || item?.submitted || ['done','partial','save_failed','settings_failed','blocked_credit','reference_unverified'].includes(item?.status))break;
        if(await recover(item?.status || 'unknown'))return;
        break;
      }
    } catch(error) {
      log('Không tiếp tục tự động: '+error.message);
      if(stopped && state.items[0])state.items[0].status='stopped';
      if(state.items[0] && !['done','partial'].includes(state.items[0].status))state.items[0].error=error.message;
      state.historyError=error.message;
      attempts.push({attempt:args.recovery?.nextAttempt || 1,model:state.model || null,time:new Date().toISOString(),status:stopped?'stopped':'setup_error',reason:error.message,files:[]});
      if(args.recovery?.nextAttempt!==2 && !stopped && !handedOff) {
        try {if(await recover('setup_error'))return;}catch(recoveryError){log('Không F5 được: '+recoveryError.message);}
      }
    } finally {
      state.attempts=attempts;
      if(handedOff)return;
      state.running=false;state.selectingModel=false;runActive=false;persist();
      try {await chrome.runtime.sendMessage({type:'saveHistory',run:{id,fileName:args.fileName,prompt:args.prompt.slice(0,20000),time:new Date().toISOString(),attempts,status:state.items[0]?.status || 'not_submitted',reason:state.historyError || null}});} catch(error){log('Không ghi được lịch sử: '+error.message);}
    }
  }
  chrome.runtime.onMessage.addListener((message, sender, reply) => {
    if(sender.id !== chrome.runtime.id) return;
    try {
      if(message.type==='uploadProgress') {log(String(message.text).slice(0,300));reply({ok:true});return;}
      if(message.type === 'status') {
        let currentModel=null;
        try {currentModel=globalThis.FlowModels?.detect(editor(message.cfg || {}),orderFor(message.cfg || {}))?.name || null;}catch{}
        reply({...state,currentModel:currentModel || lastVerifiedModel?.name || null,modelVerifiedAt:lastVerifiedModel?.time || null});return;
      }
      if(message.type==='inspectSettings') {
        if(runActive || state.running)throw new Error('Đang xử lý lượt chạy.');
        runActive=true;stopped=false;state.running=true;state.inspectOnly=true;
        (async()=>{
          const cfg=message.cfg || {};
          const detected=await FlowModels.prepare({editor:()=>editor(cfg),order:orderFor(cfg),click:e=>clickControl(e,cfg),sleep,check:checkStop});
          lastVerifiedModel={name:detected.name,time:new Date().toISOString()};
          const count=globalThis.FlowSettings?.current(editor(cfg),cfg)?.count;
          await clickControl(editor(cfg),cfg);await sleep(200);
          return {ok:true,model:detected.name,count,text:'Mô hình đang chọn: '+detected.name+'. Số ảnh trên Flow: '+(count?'x'+count:'chưa đọc được')+'. Chưa gửi prompt.'};
        })().then(reply,error=>reply({error:error.message})).finally(()=>{state.running=false;state.inspectOnly=false;runActive=false;persist();});
        return true;
      }
      if(message.type==='resumeRun' && !sender.tab) {
        if(runActive)throw new Error('Lượt khôi phục đã chạy.');
        const cp=message.checkpoint;
        if(!cp?.id || ![1,2].includes(cp.nextAttempt) || (cp.nextAttempt===1&&!cp.initialReload) || typeof cp.args?.prompt!=='string')throw new Error('Dữ liệu khôi phục không hợp lệ.');
        void runSingle({...cp.args,recovery:cp});reply({ok:true});return;
      }
      if(message.type === 'resolveClick') {
        if(!state.running || !pendingClick || pendingClick.token !== message.token) throw new Error('Yêu cầu bấm đã hết hiệu lực.');
        reply(clickPoint(pendingClick.button)); return;
      }
      if(message.type === 'pickGenerate') { pickGenerate(); reply({ok:true}); return; }
      if(message.type === 'stop') { stopped = true; reply({ok:true}); return; }
      if(message.type === 'check') {
        cancelPicker?.();
        validate(message.cfg);
        generate(message.cfg);
        reply({text:`Đã nhận diện ô prompt và nút tạo. Mô hình: ${globalThis.FlowModels?.detect(editor(message.cfg),orderFor(message.cfg))?.name || 'chưa đọc được — sẽ mở cài đặt trước khi gửi'}. Số ảnh trên Flow: ${globalThis.FlowSettings?.current(editor(message.cfg),message.cfg)?.count || 'chưa đọc được'}. Ảnh nhận diện: ${results(message.cfg).length}. Chưa gửi prompt.`});
        return;
      }
      if(message.type === 'run') {
        if(runActive || state.running) throw new Error('Đang xử lý một prompt.');
        cancelPicker?.();
        if(!message.cfg || typeof message.cfg!=='object')throw new Error('Thiếu cấu hình lượt chạy.');
        if(typeof message.prompt !== 'string' || !message.prompt.trim() || message.prompts !== undefined || message.start !== undefined) throw new Error('Mỗi lượt chỉ nhận một prompt từ toàn bộ file TXT. Tải lại bảng điều khiển nếu đang dùng phiên bản cũ.');
        void runSingle({cfg:message.cfg,reference:message.reference,prompt:message.prompt,fileName:String(message.fileName || 'prompt.txt').slice(0,255)}); reply({ok:true});
      }
    } catch(error) { reply({error:error.message,code:error.code}); }
  });
})();
