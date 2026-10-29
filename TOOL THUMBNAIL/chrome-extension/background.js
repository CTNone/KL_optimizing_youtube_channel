function isFlow(url) {
  try {
    const u = new URL(url);
    return u.protocol === 'https:' && ((u.hostname === 'labs.google' && /^\/fx\/(?:[^/]+\/)?tools\/flow(?:\/|$)/.test(u.pathname)) || ['flow.google', 'flow.google.com'].includes(u.hostname));
  } catch { return false; }
}

let connecting = false;
async function singleFlow() {
  const found=(await chrome.tabs.query({url:['https://flow.google.com/*','https://flow.google/*','https://labs.google/fx/*']})).filter(tab=>isFlow(tab.url));
  if(found.length!==1)throw new Error(found.length ? `Có ${found.length} tab Flow. Hãy chỉ giữ một tab Flow trước khi kết nối/chạy.` : 'Chưa có tab Flow. Mở một dự án Flow rồi kết nối lại.');
  return found[0];
}
const recoveryKey=id=>'recovery_'+id;
const resuming=new Set();
async function resumeAfterReload(tabId) {
  if(resuming.has(tabId))return;
  resuming.add(tabId);
  const key=recoveryKey(tabId);
  try {
    const entry=(await chrome.storage.session.get(key))[key];
    if(!entry || entry.phase!=='waiting')return;
    if(Date.now()-entry.createdAt>120000)throw new Error('F5 quá 2 phút. Không tự gửi để tránh chạy lại ngoài dự kiến.');
    await chrome.storage.session.set({[key]:{...entry,phase:'settling',settleUntil:Date.now()+2000}});
    await new Promise(resolve=>setTimeout(resolve,2000));
    const settled=(await chrome.storage.session.get(key))[key];
    if(settled?.id!==entry.id || settled.phase!=='settling')return;
    const tab=await singleFlow();
    if(tab.id!==tabId || tab.url!==entry.url)throw new Error('Tab Flow hoặc dự án đã thay đổi. Đã hủy khôi phục.');
    await chrome.storage.session.set({[key]:{...entry,phase:'dispatching'}});
    await chrome.scripting.executeScript({target:{tabId},files:['flow-errors.js','flow-models.js','flow-settings.js','flow-downloads.js','flow-clicks.js','content.js']});
    if((await chrome.storage.session.get(key))[key]?.phase!=='dispatching')return;
    const result=await chrome.tabs.sendMessage(tabId,{type:'resumeRun',checkpoint:entry.checkpoint});
    if(!result?.ok)throw new Error(result?.error || 'Không khôi phục được lượt sau F5.');
    await chrome.storage.session.set({[key]:{...entry,phase:'resumed',checkpoint:null}});
  } catch(error) {
    const entry=(await chrome.storage.session.get(key))[key] || {};
    await chrome.storage.session.set({[key]:{...entry,phase:'failed',error:error.message,checkpoint:null}});
  } finally {resuming.delete(tabId);}
}
chrome.tabs.onUpdated?.addListener((tabId,change)=>{if(change.status==='complete')void resumeAfterReload(tabId);});
// Persist the armed download across service-worker suspension. Accept only a
// Flow download whose referrer identifies this project, never an arbitrary file.
let downloadClaims=Promise.resolve();
chrome.downloads?.onDeterminingFilename?.addListener((item,suggest)=>{
  downloadClaims=downloadClaims.catch(()=>{}).then(async()=>{
    const {flowDownload}=await chrome.storage.session.get('flowDownload');
    if(!flowDownload || flowDownload.id || Date.now()>flowDownload.expiresAt || !item.referrer)return suggest();
    const referrer=new URL(item.referrer),project=new URL(flowDownload.projectUrl);
    // Cross-origin downloads may expose only the origin via Referrer-Policy.
    if(referrer.origin!==project.origin || (referrer.pathname!=='/' && referrer.href!==project.href))return suggest();
    await chrome.storage.session.set({flowDownload:{...flowDownload,id:item.id}});
    const ext={'image/png':'png','image/jpeg':'jpg','image/webp':'webp','image/avif':'avif'}[item.mime];
    suggest({filename:ext?flowDownload.filename.replace(/\.[^.]+$/,'.'+ext):flowDownload.filename,conflictAction:'uniquify'});
  }).catch(()=>suggest());
  return true;
});
async function prepareRecovery(sender,checkpoint) {
  const tab=await singleFlow();
  if(tab.id!==sender.tab.id || sender.frameId!==0)throw new Error('Không xác định được duy nhất tab Flow cần F5.');
  if(!checkpoint?.id || ![1,2].includes(checkpoint.nextAttempt) || (checkpoint.nextAttempt===1 && !checkpoint.initialReload))throw new Error('Trạng thái khôi phục không hợp lệ.');
  const key=recoveryKey(tab.id),old=(await chrome.storage.session.get(key))[key];
  if(old?.id===checkpoint.id && (old.attempt || 2)>=checkpoint.nextAttempt)throw new Error('Lượt này đã sử dụng một lần F5 cho bước này. Không tải lại thêm.');
  await chrome.storage.session.set({[key]:{id:checkpoint.id,attempt:checkpoint.nextAttempt,phase:'waiting',url:tab.url,createdAt:Date.now(),checkpoint}});
  return tab.id;
}
let stateWrites = Promise.resolve();
function updateRecords(message) {
  const job=stateWrites.catch(()=>{}).then(async()=>{
    const stored=await chrome.storage.local.get(['runHistory','modelLimits','modelEvidence050']);
    const history=stored.runHistory || [], limits=stored.modelLimits || {};
    if(!stored.modelEvidence050){
      for(const row of Object.values(limits)) {
        row.disabled=(row.count || 0)>=3;
        delete row.source;
      }
      await chrome.storage.local.set({modelLimits:limits,modelEvidence050:true});
    }
    if(message.type==='quotaHit' && typeof message.model==='string' && message.model.length<100){
      const row=limits[message.model] || {count:0};
      const event=message.runId && Number.isInteger(message.attempt) ? message.runId+':'+message.attempt : null;
      if(event && row.events?.includes(event))return {limits};
      if(event)row.events=[...(row.events || []),event].slice(-100);
      row.count++;row.disabled=row.count>=3;row.updatedAt=new Date().toISOString();limits[message.model]=row;
      await chrome.storage.local.set({modelLimits:limits});return {limits};
    }
    if(message.type==='saveHistory'){
      const row=message.run;
      if(!row || typeof row.id!=='string') throw new Error('Lịch sử không hợp lệ.');
      const kept=history.filter(x=>x.id!==row.id);kept.unshift(row);
      await chrome.storage.local.set({runHistory:kept.slice(0,100)});return {ok:true};
    }
    return {history,limits};
  });
  stateWrites=job;return job;
}
const clickingTabs = new Set();
async function nativeClick(sender, token) {
  const tabId = sender.tab.id;
  if(sender.frameId !== 0 || sender.id !== chrome.runtime.id) throw new Error('Chỉ nhận thao tác từ trang Flow chính.');
  if(typeof token !== 'string' || token.length > 100) throw new Error('Yêu cầu bấm không hợp lệ.');
  if(clickingTabs.has(tabId)) throw new Error('Tab đang xử lý một lần bấm.');
  clickingTabs.add(tabId);
  const target = {tabId};
  let attached = false;
  let pressed = false;
  try {
    const tab = await chrome.tabs.get(tabId);
    if(!isFlow(tab.url)) throw new Error('Tab đã rời Google Flow.');
    if((await singleFlow()).id!==tabId)throw new Error('Không xác minh được tab Flow duy nhất.');
    await chrome.tabs.update(tabId,{active:true});
    await chrome.windows.update(tab.windowId,{focused:true});
    await chrome.debugger.attach(target,'1.3');
    attached = true;
    // Resolve AFTER activation/attachment, since viewport/layout may change.
    let point;
    let stable=false;
    for(let i=0;i<3;i++) {
      point=await chrome.tabs.sendMessage(tabId,{type:'resolveClick',token},{frameId:0});
      if(point?.error)throw new Error(point.error);
      if(!Number.isFinite(point?.x) || !Number.isFinite(point?.y) || point.x<0 || point.y<0)throw new Error('Không xác minh được điểm bấm.');
      await chrome.debugger.sendCommand(target,'Input.dispatchMouseEvent',{type:'mouseMoved',x:point.x,y:point.y});
      if(typeof setTimeout==='function')await new Promise(resolve=>setTimeout(resolve,100));
      const verified=await chrome.tabs.sendMessage(tabId,{type:'resolveClick',token},{frameId:0});
      if(verified?.error)throw new Error(verified.error);
      if(verified?.x===point.x && verified?.y===point.y){stable=true;break;}
    }
    if(!stable)throw new Error('Điều khiển chưa ổn định sau khi đưa chuột tới. Chưa bấm.');
    pressed = true; // A rejected CDP call may still have reached the page.
    await chrome.debugger.sendCommand(target,'Input.dispatchMouseEvent',{type:'mousePressed',x:point.x,y:point.y,button:'left',buttons:1,clickCount:1});
    await chrome.debugger.sendCommand(target,'Input.dispatchMouseEvent',{type:'mouseReleased',x:point.x,y:point.y,button:'left',buttons:0,clickCount:1});
    return {ok:true};
  } catch(error) {
    error.code=pressed?'click_uncertain':'click_not_sent';throw error;
  } finally {
    if(attached) await chrome.debugger.detach(target).catch(()=>{});
    clickingTabs.delete(tabId);
  }
}
async function nativeEscape(sender) {
  if(sender.id!==chrome.runtime.id || sender.frameId!==0)throw new Error('Nguồn đóng ảnh không hợp lệ.');
  const tab=await singleFlow();
  if(tab.id!==sender.tab.id || clickingTabs.has(tab.id))throw new Error('Tab Flow đang bận hoặc đã thay đổi.');
  const target={tabId:tab.id};let attached=false;
  clickingTabs.add(tab.id);
  try {
    await chrome.debugger.attach(target,'1.3');attached=true;
    await chrome.debugger.sendCommand(target,'Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
    await chrome.debugger.sendCommand(target,'Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
    return {ok:true};
  } finally {if(attached)await chrome.debugger.detach(target).catch(()=>{});clickingTabs.delete(tab.id);}
}
async function connect(tabId, desktop=false) {
  if (connecting) throw new Error('Đang kết nối. Vui lòng chờ.');
  connecting = true;
  try {
    const tab = await chrome.tabs.get(tabId);
    if (!isFlow(tab.url)) throw new Error('Tab này chưa được nhận diện là Google Flow. Hãy mở tab dự án Flow rồi bấm tiện ích tại tab đó.');
    await chrome.scripting.executeScript({target: {tabId}, files: ['flow-errors.js','flow-models.js','flow-settings.js','flow-downloads.js','flow-clicks.js','content.js']});
    const url = chrome.runtime.getURL(`panel.html?tab=${tabId}`);
    const {panelId} = await chrome.storage.session.get('panelId');
    if (Number.isInteger(panelId)) {
      try {
        const panel = await chrome.tabs.get(panelId);
        if (panel.url?.startsWith(chrome.runtime.getURL('panel.html'))) {
          // Do not reload a panel already connected to this tab (preserve its selected TXT).
          await chrome.tabs.update(panelId, panel.url === url ? {active:true} : {url, active:true});
          await chrome.windows.update(panel.windowId, {focused:true});
          return;
        }
      } catch { /* The previous panel was closed. */ }
    }
    let panel;
    if(desktop) {
      const window=await chrome.windows.create({url,type:'popup',width:1180,height:880,focused:true});
      panel=window.tabs?.[0];
      if(!Number.isInteger(panel?.id))throw new Error('Không tạo được cửa sổ Flow TXT.');
    } else panel = await chrome.tabs.create({url});
    await chrome.storage.session.set({panelId:panel.id});
  } finally { connecting = false; }
}

async function nativeUpload(sender,message) {
  if(sender.id!==chrome.runtime.id || sender.frameId!==0 || !/^[a-f0-9-]{36}$/.test(message.token || '') || !/reference-cache[\\/]reference_[a-f0-9]{64}\.jpg$/.test(message.path || ''))throw new Error('Nguồn ảnh tải lên không hợp lệ.');
  const tab=await singleFlow();if(tab.id!==sender.tab.id)throw new Error('Tab Flow đã thay đổi.');
  if(clickingTabs.has(tab.id))throw new Error('Đang thao tác trên Flow.');
  clickingTabs.add(tab.id);
  const target={tabId:tab.id};let attached=false,listener,timer;
  try {
    await chrome.debugger.attach(target,'1.3');attached=true;
    await chrome.debugger.sendCommand(target,'DOM.enable');
    const root=await chrome.debugger.sendCommand(target,'DOM.getDocument',{depth:0});
    const selected=await chrome.debugger.sendCommand(target,'DOM.querySelector',{nodeId:root.root.nodeId,selector:'[data-flowtxt-upload="'+message.token+'"]'});
    if(!selected.nodeId)throw new Error('Nút tải ảnh đã thay đổi.');
    if(message.input)await chrome.debugger.sendCommand(target,'DOM.setFileInputFiles',{nodeId:selected.nodeId,files:[message.path]});
    else {
      await chrome.debugger.sendCommand(target,'Page.enable');
      await chrome.debugger.sendCommand(target,'Page.setInterceptFileChooserDialog',{enabled:true});
      const chooser=new Promise((resolve,reject)=>{
        listener=(source,method,params)=>{if(source.tabId===tab.id && method==='Page.fileChooserOpened')resolve(params.backendNodeId);};
        chrome.debugger.onEvent.addListener(listener);
        timer=setTimeout(()=>reject(new Error('Flow không mở ô chọn file sau khi bấm tải lên.')),10000);
      });
      chooser.catch(()=>{});
      await chrome.debugger.sendCommand(target,'Runtime.evaluate',{expression:'document.querySelector(\'[data-flowtxt-upload="'+message.token+'"]\').click()',userGesture:true});
      const backendNodeId=await chooser;
      await chrome.debugger.sendCommand(target,'DOM.setFileInputFiles',{backendNodeId,files:[message.path]});
    }
    return {ok:true};
  } finally {
    if(timer)clearTimeout(timer);if(listener)chrome.debugger.onEvent.removeListener(listener);
    if(attached){await chrome.debugger.sendCommand(target,'Page.setInterceptFileChooserDialog',{enabled:false}).catch(()=>{});await chrome.debugger.detach(target).catch(()=>{});}
    clickingTabs.delete(tab.id);
  }
}
chrome.runtime.onMessage.addListener((message, sender, reply) => {
  if(message.type==='startFreshRun' && sender.id===chrome.runtime.id && sender.url===chrome.runtime.getURL(`panel.html?tab=${message.tabId}`)) {
    (async()=>{
      const tab=await singleFlow();
      if(tab.id!==message.tabId)throw new Error('Tab Flow đã thay đổi.');
      const pending=(await chrome.storage.session.get(recoveryKey(tab.id)))[recoveryKey(tab.id)];
      if(pending && ['waiting','settling','dispatching'].includes(pending.phase))throw new Error('Đang tải lại Flow cho một lượt đã bắt đầu.');
      const args=message.args;
      if(!args?.cfg || typeof args.prompt!=='string' || !args.prompt.trim())throw new Error('Thiếu prompt/cấu hình.');
      const cp={id:crypto.randomUUID(),nextAttempt:1,initialReload:true,args,attempts:[]};
      await prepareRecovery({tab,frameId:0},cp);
      try {await chrome.tabs.reload(tab.id);}catch(error){await chrome.storage.session.set({[recoveryKey(tab.id)]:{phase:'failed',error:error.message}});throw error;}
      return {ok:true};
    })().then(reply,error=>reply({error:error.message}));return true;
  }
  if (message.type === 'connect' && sender.id === chrome.runtime.id && [chrome.runtime.getURL('popup.html'),chrome.runtime.getURL('popup.html?desktop=1')].includes(sender.url)) {
    singleFlow().then(tab=>connect(tab.id,sender.url===chrome.runtime.getURL('popup.html?desktop=1'))).then(() => reply({ok:true}), error => reply({error:error.message}));
    return true;
  }
  if(sender.id===chrome.runtime.id && sender.url?.startsWith(chrome.runtime.getURL('panel.html')) && ['recoveryStatus','cancelRecovery','verifySingle'].includes(message.type)) {
    (async()=>{
      const key=recoveryKey(message.tabId);
      if(message.type==='verifySingle'){const tab=await singleFlow();if(tab.id!==message.tabId)throw new Error('Bảng điều khiển đang nối với tab khác. Kết nối lại Flow TXT.');return {ok:true};}
      const entry=(await chrome.storage.session.get(key))[key];
      if(message.type==='recoveryStatus' && entry && ['waiting','settling','dispatching'].includes(entry.phase) && Date.now()-entry.createdAt>120000) {
        const failed={...entry,phase:'failed',checkpoint:null,error:'Khôi phục sau F5 quá 2 phút. Đã dừng, không tự gửi thêm.'};
        await chrome.storage.session.set({[key]:failed});return {phase:failed.phase,error:failed.error};
      }
      if(message.type==='cancelRecovery'&&entry)await chrome.storage.session.set({[key]:{...entry,phase:'cancelled',checkpoint:null}});
      return {phase:entry?.phase,error:entry?.error,attempt:entry?.attempt};
    })().then(reply,error=>reply({error:error.message}));return true;
  }
  if (!sender.tab || !isFlow(sender.url)) return;
  (async () => {
    if(message.type==='armFlowDownload') {
      if(sender.id!==chrome.runtime.id || sender.frameId!==0)throw new Error('Nguồn tải ảnh không hợp lệ.');
      const tab=await singleFlow();
      if(tab.id!==sender.tab.id)throw new Error('Tab Flow đã thay đổi.');
      if(!/^Flow_TXT\/run_[\d_-]+\/\d{4,}_\d{2}\.(png|jpg|webp|avif)$/.test(message.filename || ''))throw new Error('Tên file tải không hợp lệ.');
      const {flowDownload:old}=await chrome.storage.session.get('flowDownload');
      if(old && Date.now()<old.expiresAt)throw new Error('Đang chờ một ảnh tải từ Flow.');
      const token=crypto.randomUUID();
      await chrome.storage.session.set({flowDownload:{token,tabId:tab.id,projectUrl:tab.url,filename:message.filename,expiresAt:Date.now()+180000}});
      reply({ok:true,token});
    } else if(['flowDownloadStatus','cancelFlowDownload','importFlowDownload','readFlowDownload'].includes(message.type)) {
      const {flowDownload:entry}=await chrome.storage.session.get('flowDownload');
      if(!entry || entry.token!==message.token || entry.tabId!==sender.tab.id)throw new Error('Lượt tải ảnh không còn hiệu lực.');
      if(['importFlowDownload','readFlowDownload'].includes(message.type)) {
        if(sender.id!==chrome.runtime.id || sender.frameId!==0 || !entry.id)throw new Error('Nguồn file tải không hợp lệ.');
        const [item]=await chrome.downloads.search({id:entry.id});
        if(item?.state!=='complete' || !item.filename)throw new Error('File 2K chưa tải xong.');
        if(!/^run_[\d_-]+\/\d{4,}_\d{2}\.(png|jpg|webp|avif)$/.test(message.path || ''))throw new Error('Đường dẫn lưu không hợp lệ.');
        const {panelId}=await chrome.storage.session.get('panelId');
        if(!Number.isInteger(panelId) || (await chrome.tabs.get(panelId)).url!==chrome.runtime.getURL(`panel.html?tab=${sender.tab.id}`))throw new Error('Bảng điều khiển lưu ảnh đã đóng/đổi tab.');
        const imported=await chrome.runtime.sendMessage({type:message.type==='readFlowDownload'?'processDownloadedImage':'importDownloadToFolder',tabId:sender.tab.id,path:message.path,source:item.filename});
        if(!imported?.ok)throw new Error(imported?.error || 'Không lưu được file 2K từ Downloads.');
        reply(imported);
      } else if(message.type==='cancelFlowDownload'){await chrome.storage.session.remove('flowDownload');reply({ok:true});}
      else if(entry.id){const [item]=await chrome.downloads.search({id:entry.id});reply(item ? {state:item.state,error:item.error,url:item.finalUrl || item.url,mime:item.mime,filename:item.filename,id:item.id} : {error:'Không thấy file tải từ Flow.'});}
      else reply({state:'waiting'});
    } else if(message.type==='recoverRun') {
      const tabId=await prepareRecovery(sender,message.checkpoint);
      reply({ok:true});
      try {await chrome.tabs.reload(tabId);}catch(error){await chrome.storage.session.set({[recoveryKey(tabId)]:{phase:'failed',error:error.message}});}
    } else if (['quotaHit','saveHistory','readRecords'].includes(message.type)) {
      reply(await updateRecords(message));
    } else if (message.type === 'writeImage') {
      if(sender.id !== chrome.runtime.id || sender.frameId !== 0) throw new Error('Nguồn lưu ảnh không hợp lệ.');
      if(!/^data:image\/(png|jpeg|webp|avif);base64,/.test(message.data || '') || message.data.length > 30*1024*1024) throw new Error('Dữ liệu ảnh không hợp lệ hoặc lớn hơn giới hạn 20 MB.');
      if(!/^run_[\d_-]+\/\d{4,}_\d{2}\.(png|jpg|webp|avif)$/.test(message.path || '')) throw new Error('Đường dẫn ảnh không hợp lệ.');
      const {panelId} = await chrome.storage.session.get('panelId');
      if(!Number.isInteger(panelId)) throw new Error('Bảng điều khiển đã đóng. Mở lại và chọn thư mục lưu.');
      const panel = await chrome.tabs.get(panelId);
      if(panel.url !== chrome.runtime.getURL(`panel.html?tab=${sender.tab.id}`)) throw new Error('Bảng điều khiển không còn kết nối tab này.');
      const result = await chrome.runtime.sendMessage({type:'saveToFolder',tabId:sender.tab.id,path:message.path,data:message.data});
      if(!result?.ok) throw new Error(result?.error || 'Chưa chọn thư mục hoặc bảng điều khiển không phản hồi.');
      reply(result);
    } else if (message.type === 'nativeUpload') {
      reply(await nativeUpload(sender,message));
    } else if (message.type === 'nativeEscape') {
      reply(await nativeEscape(sender));
    } else if (message.type === 'nativeClick') {
      reply(await nativeClick(sender,message.token));
    } else if (message.type === 'download') {
      const url = new URL(message.url);
      if (!['https:', 'data:'].includes(url.protocol) ||
          (url.protocol === 'data:' && !message.url.startsWith('data:image/'))) {
        throw new Error('URL ảnh không hợp lệ.');
      }
      if (!/^Flow_TXT\/run_[\d_-]+\/\d{4,}_\d{2}\.(png|jpg|webp|avif)$/.test(message.filename)) {
        throw new Error('Tên file không hợp lệ.');
      }
      const id = await chrome.downloads.download({url: message.url, filename: message.filename, saveAs: false, conflictAction: 'uniquify'});
      reply({id});
    } else if (message.type === 'downloadStatus') {
      const [item] = await chrome.downloads.search({id: message.id});
      reply({state: item?.state, error: item?.error, mime: item?.mime, filename: item?.filename});
    }
  })().catch(error => reply({error: error.message,code:error.code}));
  return true;
});
