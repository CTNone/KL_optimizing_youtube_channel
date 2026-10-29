(() => {
  const visible=e=>e.getClientRects().length && getComputedStyle(e).visibility!=='hidden';
  const label=e=>[e.innerText || e.textContent || '',e.getAttribute('aria-label'),e.getAttribute('title')].filter(Boolean).join(' ').trim();
  const enabled=e=>!e.disabled && e.getAttribute('aria-disabled')!=='true';
  function identity(src) {
    try {
      const url=new URL(src);
      const ids=['id','assetId','mediaId','name'].filter(k=>url.searchParams.has(k)).map(k=>k+'='+url.searchParams.get(k)).join('&');
      const path=/googleusercontent\.com$/i.test(url.hostname)?url.pathname.replace(/=(?:[swh]\d+)(?:-[a-z0-9]+)*$/i,''):url.pathname;
      return url.origin+path+(ids?'?'+ids:'');
    } catch {return src;}
  }
  async function pixels(url) {
    const response=await fetch(url,{credentials:'include',signal:AbortSignal.timeout(30000)});
    if(!response.ok)throw new Error('Không đọc được file 2K (HTTP '+response.status+').');
    const blob=await response.blob();
    if(!/^image\/(png|jpeg|webp|avif)$/.test(blob.type) || !blob.size || blob.size>20*1024*1024)throw new Error('File 2K không đúng định dạng ảnh hoặc vượt 20 MB.');
    const bitmap=await createImageBitmap(blob);
    const width=bitmap.width,height=bitmap.height;bitmap.close();
    if(Math.max(width,height)<2048)throw new Error(`Ảnh tải chỉ ${width}×${height}; chưa đạt 2K. Không lưu ảnh xem trước.`);
    const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(new Error('Không đọc được file 2K.'));reader.readAsDataURL(blob);});
    return {data,width,height};
  }
  async function save({result,cfg,filename,click,sleep,check,log=()=>{}}) {
    let openedImage=false;
    let token=null;
    let completed=null;
    let failure=null;
    async function clickFresh(read,description) {
      let lastError;
      for(let i=0;i<4;i++) {
        check();
        const rows=read().filter(visible).filter(enabled).filter(e=>e.isConnected!==false);
        if(rows.length===1) {
          try {await click(rows[0]);return;}
          catch(error) {if(error.code!=='click_not_sent')throw error;lastError=error;}
        }
        await sleep(150);
      }
      throw Object.assign(new Error(description+(lastError?' '+lastError.message:'')),{code:'download_control_unavailable'});
    }
    async function readLocal(item) {
      const verified=await chrome.runtime.sendMessage({type:'readFlowDownload',token,path:filename.replace(/^Flow_TXT\//,'')});
      if(!verified?.ok)throw new Error(verified?.error || 'Không kiểm tra được file 2K trên máy.');
      completed={image:{width:verified.width,height:verified.height},native:verified,download:item,sha256:verified.sha256,source:'flow_2k'};
      delete result.pendingDownload;
      return completed;
    }
    try {
    if(result.pendingDownload) {token=result.pendingDownload.token;return await readLocal(result.pendingDownload.item);}
    // An explicitly supplied original URL must still pass the pixel check.
    if(cfg.original) {
      const links=[...result.card.querySelectorAll(cfg.original)];
      if(links.length!==1 || !links[0].href)throw new Error('Không thấy duy nhất link ảnh gốc 2K.');
      return {image:await pixels(links[0].href),source:'original'};
    }
    const labels=e=>[e.innerText || e.textContent || '',e.getAttribute('aria-label'),e.getAttribute('title')].filter(Boolean).map(s=>s.trim());
    const download=e=>labels(e).some(s=>/^(download|tải xuống|tải về|tải ảnh|file_download|download_2)$/i.test(s));
    let buttons=[];
    {
      const closed=await chrome.runtime.sendMessage({type:'nativeEscape'});
      if(!closed?.ok)throw new Error(closed?.error || 'Chưa đóng được bản xem trước khi mở ảnh kế tiếp.');
      await sleep(Number(cfg.observationDelayMs) || 300);check();
      const source=result.src || result.img.currentSrc || result.img.src;
      const freshImage=()=>{
        if(result.img.isConnected!==false && identity(result.img.currentSrc || result.img.src)===identity(source))return [result.img];
        return [...document.querySelectorAll('img')].filter(visible).filter(e=>e.complete && identity(e.currentSrc || e.src)===identity(source) && e.getBoundingClientRect().width>=200);
      };
      log('Mở đúng ảnh vừa tạo để tải 2K…');
      await clickFresh(freshImage,'Ảnh đã thay đổi khi mở bản xem.');
      openedImage=true;
      const expected=identity(result.src || result.img.currentSrc || result.img.src);
      const previewImages=()=>{
        let rows=[...document.querySelectorAll('[role="dialog"] img,[data-state="open"] img')].filter(visible).filter(e=>e!==result.img && e.complete && e.naturalWidth>=256);
        // A full-page preview can be smaller than a wide gallery tile.
        // Verify asset identity; display size is not proof of a new asset.
        if(!rows.length)rows=[...document.querySelectorAll('img')].filter(visible).filter(e=>e!==result.img && e.complete && e.naturalWidth>=256 && e.getBoundingClientRect().width>=256);
        return rows.sort((a,b)=>b.getBoundingClientRect().width*b.getBoundingClientRect().height-a.getBoundingClientRect().width*a.getBoundingClientRect().height);
      };
      let correct=false;
      for(let i=0;i<100;i++) {check();const active=previewImages().find(e=>identity(e.currentSrc || e.src)===expected);if(active){correct=true;break;}await sleep(200);}
      if(!correct)throw new Error('Ảnh đang mở chưa khớp ảnh cần tải. Dừng để tránh tải trùng ảnh trước.');
      log('Đã xác nhận bản xem đúng ảnh kết quả. Đang tìm nút Download…');
      for(let i=0;i<30;i++) {
        check();
        buttons=[...document.querySelectorAll(cfg.downloadButton || '[role="dialog"] button,[role="dialog"] [role="button"],button,[role="button"]')].filter(visible).filter(enabled).filter(download);
        if(buttons.length===1)break;
        await sleep(150);
      }
    }
    if(buttons.length!==1)throw new Error('Đã mở ảnh nhưng chưa thấy duy nhất nút Download. Cấu hình nút tải trong mục nâng cao.');
    const downloadControls=()=>[...document.querySelectorAll(cfg.downloadButton || '[role="dialog"] button,[role="dialog"] [role="button"],button,[role="button"]')].filter(download);
    await clickFresh(downloadControls,'Nút Download chưa ổn định sau khi mở ảnh.');
    const menuControls=()=>[...document.querySelectorAll('[role="menuitem"],[role="option"],[role="menu"] button,[role="dialog"] button,button')].filter(visible).filter(enabled);
    let chosen=null;
    let submenuClicked=false;
    const twoKControls=()=> (cfg.download2k ? [...document.querySelectorAll(cfg.download2k)].filter(visible).filter(enabled) : menuControls()).filter(e=>/\b2\s*k\b|2048/i.test(label(e)));
    for(let i=0;i<30;i++) {
      check();
      const candidates=twoKControls();
      if(candidates.length===1){chosen=candidates[0];break;}
      const submenu=menuControls().filter(download);
      if(submenu.length===1 && !submenuClicked){await clickFresh(()=>menuControls().filter(download),'Menu Download chưa sẵn sàng.');submenuClicked=true;}
      await sleep(150);
    }
    if(!chosen)throw new Error('Không tìm thấy lựa chọn tải 2K khả dụng trong menu Flow. Chưa tải bản thấp hơn.');
    const freeControls=()=>twoKControls().map(e=>{
      if(/(?:[1-9]\d*)\s*(?:credits?|tín dụng)|(?:cost|tốn|phí)\s*[:：]?\s*[1-9]|upgrade|nâng cấp|buy|mua/i.test(label(e)))throw new Error('Tùy chọn 2K có phí hoặc cần nâng cấp. Không thực hiện.');
      return e;
    });
    freeControls();
    const armed=await chrome.runtime.sendMessage({type:'armFlowDownload',filename});
    if(!armed?.ok)throw new Error(armed?.error || 'Không theo dõi được file tải 2K.');
    token=armed.token;
      log('Đã chọn tải 2K. Chờ file tải xong; không tạo lại ảnh.');
      result.downloadStarted=true;
      await clickFresh(freeControls,'Lựa chọn 2K đã thay đổi.');
      for(let i=0;i<180;i++) {
        check();
        const item=await chrome.runtime.sendMessage({type:'flowDownloadStatus',token:armed.token});
        if(item.error || item.state==='interrupted')throw new Error(item.error || 'Tải 2K bị gián đoạn.');
        if(item.state==='complete') {
          result.pendingDownload={token,item};
          return await readLocal(item);
        }
        await sleep(1000);
      }
      throw new Error('Hết thời gian chờ file 2K từ Flow.');
    } catch(error) {failure=error;throw error;} finally {
      if(token && !result.pendingDownload)await chrome.runtime.sendMessage({type:'cancelFlowDownload',token}).catch(()=>{});
      if(openedImage) {
        try {
          const closed=await chrome.runtime.sendMessage({type:'nativeEscape'});
          if(!closed?.ok)throw new Error(closed?.error || 'Không đóng được ảnh sau khi tải.');
          await sleep(Number(cfg.observationDelayMs) || 300);
          const closedAgain=await chrome.runtime.sendMessage({type:'nativeEscape'});
          if(!closedAgain?.ok)throw new Error(closedAgain?.error || 'Chưa trở về giao diện tạo ảnh.');
        } catch(error) {
          if(completed)completed.warning=error.message;
          else if(failure)failure.message+=' · Đóng bản xem: '+error.message;
          else throw error;
        }
      }
    }
  }
  globalThis.FlowDownloads={save,pixels,identity};
})();
