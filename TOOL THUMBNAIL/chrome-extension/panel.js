const $ = id => document.getElementById(id);
const tab = Number(new URLSearchParams(location.search).get('tab'));
const keys = ['prompt', 'generate', 'card', 'image', 'original', 'count', 'aspectRatio', 'timeout', 'clickMode', 'saveMode', 'modelOrder','modelChoice','countControl','countOption','downloadButton','download2k'];
let directory = null;
let historySignature=null;
const savedDigests=new Map();
const processedImages=new Map();
let referenceData=null;
let referenceReading=false;
$('referenceFile').onchange=async()=>{
  referenceReading=true;controls();
  try {
    const file=$('referenceFile').files[0];if(!file)return;
    if(file.size>4*1024*1024 || !/^image\/(png|jpeg|webp)$/.test(file.type))throw new Error('Chọn ảnh PNG/JPG/WebP không quá 4 MB.');
    const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(new Error('Không đọc được ảnh.'));reader.readAsDataURL(file);});
    referenceData={data,name:file.name};$('referenceLabel').textContent=file.name;$('referencePreview').src=data;$('referencePreview').hidden=false;
  }catch(e){error(e);}
  finally{referenceReading=false;controls();}
};
$('referenceClear').onclick=()=>{referenceData=null;$('referenceLabel').textContent='Không dùng ảnh mẫu.';$('referencePreview').hidden=true;$('referencePreview').src='';};
$('ncttImport').onclick=async()=>{
  if(submitting || inspecting || state?.running)return;
  inspecting=true;controls();
  try {
    const result=await NativeFiles.request({type:'ncttJob'});
    if(!result.job)throw new Error('Chưa có yêu cầu từ NCTT.');
    const job=result.job;
    const image=job.referenceImage?await NativeFiles.imageData(job.referenceImage,true):null;
    $('promptEditor').value=job.prompt;fileName='NCTT '+job.id.slice(0,8);raw=job.prompt;
    $('modelChoice').value=job.model || 'Nano Banana 2 Lite';$('count').value=String(job.count || 1);
    referenceData=image?{data:image.data,name:'nctt_reference.jpg',source:job.reference}:null;
    $('referenceLabel').textContent=job.reference || 'Không dùng ảnh mẫu.';
    $('referencePreview').hidden=!image;if(image)$('referencePreview').src=image.data;
    await NativeFiles.request({type:'ncttJob',acknowledge:job.id});
    $('notice').textContent='Đã nhận NCTT. Kiểm tra prompt, ảnh mẫu và thư mục lưu trước khi bấm Tạo ảnh.';controls();
  }catch(e){error(e);}
  finally{inspecting=false;controls();}
};
$('extensionId').textContent=chrome.runtime.id;
$('installCommand').textContent='.\\native-host\\install.ps1 -ExtensionId '+chrome.runtime.id;
$('folder').onclick = async () => {
  try {
    if($('saveMode').value==='windows') {
      const result=await NativeFiles.choose();
      if(result.cancelled)return;
      destination();
      $('notice').textContent='Đã chọn đúng thư mục Windows: '+result.path;
      return;
    }
    directory = await window.showDirectoryPicker({mode:'readwrite',id:'flow-images'});
    $('saveMode').value = 'folder';
    destination();
    $('notice').textContent = 'Đã chọn nơi lưu: ' + directory.name + '. Ảnh sẽ được ghi vào thư mục này.';
  } catch(e) { if(e.name !== 'AbortError') error(e); }
};
chrome.runtime.onMessage.addListener((message,sender,reply)=>{
  if(sender.id !== chrome.runtime.id || !['saveToFolder','importDownloadToFolder','processDownloadedImage'].includes(message.type) || message.tabId !== tab) return;
  (async()=>{
    if(message.type==='processDownloadedImage') {
      const cacheKey=message.path+'|'+message.source+'|'+$('saveMode').value;
      let original=processedImages.get(cacheKey);
      if(!original && $('saveMode').value==='windows') {
        original=await NativeFiles.importImage(message.path,message.source);
        processedImages.set(cacheKey,original);
      }
      if(!original) {
      const image=await NativeFiles.readImage(message.source,$('saveMode').value==='folder');
      const run=message.path.split('/')[0];
      if(savedDigests.get(run)?.has(image.sha256))throw new Error('Ảnh 2K trùng dữ liệu với ảnh đã lưu trong lượt này. Không ghi file trùng.');
      let filename=message.source;
      if($('saveMode').value==='folder')filename=await FlowFiles.write(directory,message.path.replace(/\.[^.]+$/,'.'+image.ext),image.data);
      if(!savedDigests.has(run))savedDigests.set(run,new Set());savedDigests.get(run).add(image.sha256);
      original={...image,data:undefined,ok:true,filename};processedImages.set(cacheKey,original);
      }
      if(!original.croppedFilename) {
        const folderMode=$('saveMode').value==='folder';
        const cropped=await NativeFiles.cropImage(folderMode?message.source:original.filename,!folderMode);
        original.croppedFilename=folderMode?await FlowFiles.write(directory,message.path.replace(/\.[^.]+$/,'_16x9.jpg'),cropped.data):cropped.filename;
        original.crop={width:cropped.width,height:cropped.height};
      }
      reply(original);return;
    }
    if(message.type==='importDownloadToFolder') {
      if($('saveMode').value!=='windows')throw new Error('Chế độ lưu Windows đã thay đổi.');
      reply(await NativeFiles.importImage(message.path,message.source));return;
    }
    const filename = $('saveMode').value==='windows' ? (await NativeFiles.write(message.path,message.data)).filename : await FlowFiles.write(directory,message.path,message.data);
    reply({ok:true,filename});
  })().catch(e=>reply({error:e.message}));
  return true;
});
let raw = '', fileName = '', state = null, connected = false, submitting = false, reading = false, readVersion = 0, inspecting = false, refreshing = false;
function normalize(text) { return text.replace(/^\uFEFF/, '').replace(/\r\n?/g, '\n').trim(); }
function promptText() { return normalize($('promptEditor').value); }
function destination() {
  if($('saveMode').value==='windows') {
    $('folderName').textContent=globalThis.NativeFiles?.directory || 'Chưa chọn thư mục Windows.';
    $('folderDetail').textContent='Đường dẫn đầy đủ lấy trực tiếp từ Windows. Ảnh lưu trong thư mục con run_…; file trùng tên được thêm số.';
    $('folder').textContent='Chọn thư mục Windows…';return;
  }
  const direct = $('saveMode').value === 'folder';
  $('folderName').textContent = direct ? (directory ? 'Đã chọn: ' + directory.name : 'Chưa chọn thư mục.') : 'Thư mục tải xuống của Chrome';
  $('folderDetail').textContent = direct ? (directory ? `Ảnh sẽ nằm trong ${directory.name}/run_…/. Trùng tên sẽ thêm số, không ghi đè. Chrome không cung cấp đường dẫn tuyệt đối.` : 'Chọn thư mục bất kỳ mà Chrome và hệ điều hành cho phép ghi.') : 'Lưu vào Flow_TXT/run_… trong vị trí Downloads đã cấu hình của Chrome.';
  $('folder').textContent = directory ? 'Đổi thư mục…' : 'Chọn thư mục…';
}
$('saveMode').onchange = destination;
$('promptEditor').oninput = () => {
  $('editStatus').textContent = promptText() === normalize(raw) ? 'Nội dung giống file gốc.' : 'Đã chỉnh sửa trên tool. File gốc không bị thay đổi.';
  controls();
};
function controls() {
  const busy = submitting || inspecting || referenceReading || !!state?.running;
  $('run').disabled = busy || reading || !connected || !promptText();
  $('promptEditor').disabled = busy || reading;
  $('stop').disabled = !state?.running;
  for(const id of ['file','folder','count','auto','pick','check','ncttImport','referenceClear','referenceFile',...keys]) $(id).disabled = busy;
}
$('file').onchange = async () => {
  const file = $('file').files[0];
  const version = ++readVersion;
  reading = true;
  raw = ''; fileName = ''; controls();
  try {
    if(file && file.size > 1024*1024) throw new Error('File lớn hơn 1 MB. Hãy chọn file chỉ chứa một prompt.');
    const text = file ? await file.text() : '';
    if(version !== readVersion) return;
    raw = text; fileName = file?.name || '';
    $('promptEditor').value = normalize(raw);
    $('editStatus').textContent = 'Có thể sửa prompt ngay trong ô trên. File gốc không bị thay đổi.';
    $('notice').textContent = file ? `Đã chọn ${fileName}: toàn bộ nội dung sẽ được gửi một lần.` : '';
  } catch(e) { if(version === readVersion) { $('promptEditor').value = ''; error(e); } }
  finally { if(version === readVersion) { reading = false; controls(); } }
};
function cfg() { return Object.fromEntries(keys.map(k => [k, $(k).value.trim()])); }
async function send(message) {
  const result = await chrome.tabs.sendMessage(tab, message);
  if (result?.error) throw new Error(result.error);
  return result;
}
function error(e) { $('notice').textContent = e.message + '\nNếu vừa tải lại/đổi tab Flow, bấm biểu tượng tiện ích trên tab Flow để kết nối lại.'; }
$('auto').onclick = async () => {
  for(const key of ['prompt','generate','card','original']) $(key).value = '';
  $('image').value = 'img';
  await chrome.storage.local.set({config:cfg()});
  $('notice').textContent = 'Đã bật nhận diện tự động. Bấm Kiểm tra nhận diện trước khi chạy.';
};
$('pick').onclick = async () => {
  try {
    $('generate').value = '';
    await send({type:'pickGenerate'});
    await chrome.tabs.update(tab,{active:true});
    $('notice').textContent = 'Chọn mũi tên tạo trên Flow, sau đó quay lại tab này.';
  } catch(e) { error(e); }
};
$('check').onclick = async () => {
  if(inspecting || submitting || state?.running)return;
  inspecting=true;controls();
  try { const result = await send({type:'inspectSettings', cfg:cfg()}); $('notice').textContent = result.text; await refresh(); }
  catch(e) { error(e); }
  finally {inspecting=false;controls();}
};
$('run').onclick = async () => {
  if(submitting || inspecting || referenceReading || state?.running) return;
  submitting = true; controls();
  try {
    const config = cfg();
    const verified=await chrome.runtime.sendMessage({type:'verifySingle',tabId:tab});
    if(!verified?.ok)throw new Error(verified?.error || 'Không kiểm tra được tab Flow duy nhất.');
    if(config.saveMode === 'folder' && !directory) throw new Error('Bấm Chọn thư mục lưu ảnh trước khi chạy.');
    if(config.saveMode === 'windows' && !NativeFiles.directory)throw new Error('Chọn thư mục Windows trước khi chạy. Nếu chưa cài bộ hỗ trợ, xem hướng dẫn ở mục nâng cao.');
    $('notice').textContent = '';
    await chrome.storage.local.set({config});
    if(!promptText()) throw new Error('Nhập nội dung prompt trước khi tạo ảnh.');
    if(promptText().length > 1024*1024) throw new Error('Prompt quá dài. Giới hạn 1 triệu ký tự.');
    let reference=referenceData;
    if(reference){const staged=await NativeFiles.request({type:'stageReference',data:reference.data});reference={...reference,path:staged.path};}
    const started=await chrome.runtime.sendMessage({type:'startFreshRun',tabId:tab,args:{cfg:config,reference,prompt:promptText(),fileName:fileName || 'Prompt nhập trực tiếp'}});
    if(!started?.ok)throw new Error(started?.error || 'Không F5 được trước lượt đầu.');
    await refresh();
  } catch(e) { error(e); }
  finally { submitting = false; controls(); }
};
$('stop').onclick = async () => {
  await chrome.runtime.sendMessage({type:'cancelRecovery',tabId:tab}).catch(()=>{});
  try { await send({type:'stop'}); } catch { $('notice').textContent='Đã hủy khôi phục sau F5.'; }
};
$('export').onclick = () => {
  const blob = new Blob([JSON.stringify(state, null, 2)], {type:'application/json'});
  const url = URL.createObjectURL(blob), a = document.createElement('a');
  a.href = url; a.download = 'flow-progress.json'; a.click(); setTimeout(() => URL.revokeObjectURL(url), 5000);
};
async function refresh() {
  if(refreshing)return;
  refreshing=true;
  try {
    const recovery=await chrome.runtime.sendMessage({type:'recoveryStatus',tabId:tab});
    if(['waiting','settling','dispatching'].includes(recovery?.phase)) {
      state={...(state || {}),running:true};connected=false;
      $('connection').textContent='Đang F5 / kết nối lại';
      $('phase').textContent=recovery.phase==='settling'?'Chờ Flow ổn định 2 giây':recovery.attempt===1?'F5 trước lần gửi 1/2':'Khôi phục lần 2/2';
      $('notice').textContent='Đang chờ đúng tab Flow. Tool chưa chọn mô hình hoặc gửi prompt trong thời gian chờ.';
      return;
    }
    state = await send({type:'status',cfg:cfg()});
    connected = true; $('connection').textContent = 'Đã kết nối tab Flow';
    const item = state.items?.[0];
    const labels = {configuring:'Đang đặt số ảnh trên Flow',settings_failed:'Chưa xác nhận cài đặt Flow',setup_error:'Lỗi chuẩn bị trước khi gửi',preparing:'Đang nhập prompt',submitting:'Đang bấm gửi',waiting:'Đang chờ ảnh',saving:'Đang tải và lưu ảnh 2K',done:'Đã hoàn tất',partial:'Đã lưu ảnh thành công một phần',blocked_model_limit:'Mô hình đạt hạn mức',blocked_generation:'Flow tạo ảnh thất bại',timeout:'Hết thời gian chờ',save_failed:'Không lưu được ảnh',blocked_credit:'Dừng: không đủ credit',blocked_policy:'Dừng: nội dung bị từ chối',blocked_rate_limit:'Dừng: giới hạn yêu cầu',needs_review:'Cần kiểm tra',stopped:'Đã dừng'};
    $('phase').textContent = labels[item?.status] || 'Sẵn sàng';
    if(state.reloading)$('phase').textContent='Đang F5 Flow để thử lại';
    if(state.selectingModel)$('phase').textContent='Đang kiểm tra và chọn mô hình';
    const actions = {blocked_credit:'Lượt này đã dừng. Cần đủ credit trên Flow trước khi chạy lại.',blocked_policy:state.running?'Flow báo chính sách ở lần hiện tại. Tool sẽ thử lại nguyên prompt tối đa một lần, cùng mô hình.':'Lượt tool đã kết thúc với thông báo chính sách. Xem lịch sử từng lần thử; thao tác tạo thủ công sau đó không thuộc lượt này.',blocked_rate_limit:'Flow giới hạn yêu cầu. Xem nhật ký để biết tool đang chờ thử lại hay đã dừng.'};
    $('summary').textContent = item?.status==='partial' ? `Đã lưu ${item.files.length}/${item.expected} ảnh. Giữ kết quả này, không tạo lại. ${item.warning || ''}` : actions[item?.status] || (item?.status === 'done' ? 'Ảnh đã được xác nhận lưu thành công. Bạn có thể chọn file tiếp theo.' : item?.error || (state.running ? 'Tool đang xử lý một prompt. Giữ tab Flow và bảng điều khiển mở.' : 'Chọn một file TXT để bắt đầu.'));
    $('runFile').textContent = state.fileName ? 'Lượt hiện tại / gần nhất: ' + state.fileName : '';
    $('flowMessage').textContent = state.flowMessage || 'Chưa ghi nhận thông báo lỗi từ Flow.';
    $('currentModel').textContent = 'Mô hình trên Flow: '+(state.currentModel || (state.running?state.model:null) || 'chưa đọc được — kiểm tra cài đặt trước khi gửi')+(state.running ? ` · Lần ${state.attempt || 1}/2` : '');
    $('flowCount').textContent='Số ảnh: tool x'+$('count').value+' · Flow '+(state.flowCount?'đã xác nhận x'+state.flowCount:'sẽ đặt và xác nhận trước khi gửi');
    const files = [...(item?.files || []),...(item?.croppedFiles || [])];
    $('savedCount').textContent = (item?.files?.length || 0) + ' ảnh gốc · '+(item?.croppedFiles?.length || 0)+' bản 16:9';
    $('emptyFiles').hidden = !!files.length;
    $('files').replaceChildren(...files.map(path=>{const li=document.createElement('li');li.textContent=path;return li;}));
    $('status').textContent = state.logs.join('\n') || 'Sẵn sàng.';
    const stored=await chrome.storage.local.get(['runHistory','modelLimits']);
    const history=stored.runHistory || [];
    const order=($('modelOrder').value.trim() || 'Nano Banana Pro\nNano Banana 2.1\nNano Banana 2 Lite').split('\n').map(s=>s.trim()).filter(Boolean);
    const blocked=name=>stored.modelLimits?.[name]?.disabled;
    $('priority').replaceChildren(...order.map(name=>{const li=document.createElement('li');li.textContent=name+(blocked(name)?' — BỎ QUA':name===state.currentModel?' — đang chọn trên Flow':' — sẽ kiểm tra trong menu');return li;}));
    const index=order.indexOf(state.currentModel || state.model);
    const next=index<0?null:order.slice(index+1).find(name=>!blocked(name));
    const best=order.find(name=>!blocked(name));
    const planned=$('modelChoice').value || best;
    $('plannedModel').textContent='Mô hình sẽ dùng: '+(state.running && state.model ? state.model : planned || 'không còn mô hình khả dụng')+(blocked(planned)?' — đã khóa, chọn mô hình khác':'');
    $('nextModel').textContent=`Bắt đầu lượt mới: ưu tiên ${best || 'không còn mô hình'}. `+(index<0?'Chưa xác định mô hình đang chọn.':next?`Nếu mô hình hiện tại hết lượt: ưu tiên ${next} sau F5.`:'Không còn mô hình thấp hơn trong danh sách.');
    const signature=JSON.stringify(history);
    if(signature!==historySignature) {
    const opened=new Set([...($('history').querySelectorAll?.('details') || [])].filter(e=>e.open).map(e=>e.dataset.runId));
    $('history').replaceChildren(...history.slice(0,20).map(run=>{
      const entry=document.createElement('details'),title=document.createElement('summary'),body=document.createElement('pre');
      entry.dataset.runId=run.id;entry.open=opened.has(run.id);
      title.textContent=`${new Date(run.time).toLocaleString()} · ${run.fileName} · ${labels[run.status] || run.status}`;
      body.textContent=(run.attempts || []).map(a=>`Lần ${a.attempt} · ${a.model || 'Không rõ mô hình'} · ${labels[a.status] || a.status}\n${a.flowMessage || a.reason || 'Không ghi nhận lỗi'}\n${(a.files || []).join('\n')}`).join('\n\n')+(run.reason?'\n'+run.reason:'')+'\n\nPrompt:\n'+(run.prompt || '');
      entry.append(title,body);return entry;
    }));
    if(!history.length)$('history').textContent='Chưa có lịch sử.';
    historySignature=signature;
    }
    $('modelLimits').textContent=Object.entries(stored.modelLimits || {}).filter(([,value])=>value.disabled && value.count>=3).map(([name,value])=>`${name}: ${value.count} lần Flow báo hạn mức sau khi gửi — KHÔNG DÙNG`).join('\n') || 'Chưa có mô hình đủ 3 lần báo hạn mức.';
    $('modelEvidence').textContent=Object.entries(stored.modelLimits || {}).filter(([,value])=>!value.disabled && value.count>0).map(([name,value])=>`${name}: ${value.count}/3 lần báo hạn mức — tiếp tục theo dõi`).join('\n');
  } catch(e) {
    connected = false;
    const recovery=await chrome.runtime.sendMessage({type:'recoveryStatus',tabId:tab}).catch(()=>null);
    if(['waiting','settling','dispatching'].includes(recovery?.phase)) {
      state={...(state || {}),running:true};$('connection').textContent='Đang F5 / kết nối lại';$('phase').textContent=recovery.attempt===1?'F5 trước lần gửi 1/2':'Khôi phục lần 2/2';
      $('notice').textContent='Đã lưu prompt và cài đặt. Đang F5 đúng tab Flow trước khi gửi; không cần bấm Tạo ảnh thêm.';
    } else {if(state)state.running=false;$('connection').textContent='Mất kết nối';error(new Error(recovery?.error || e.message));}
  } finally {refreshing=false;controls();}
}
(async () => {
  const {config} = await chrome.storage.local.get('config');
  if(config?.modelChoice==='Nano Banana Lite')config.modelChoice='Nano Banana 2 Lite';
  if(config?.modelChoice==='Nano Banana 2')config.modelChoice='Nano Banana 2.1';
  if(config?.modelOrder)config.modelOrder=config.modelOrder.split('\n').map(s=>s.trim()==='Nano Banana 2'?'Nano Banana 2.1':s.trim()==='Nano Banana Lite'?'Nano Banana 2 Lite':s).join('\n');
  if(config) for(const k of keys) if(config[k] !== undefined) $(k).value = config[k];
  if(!$('modelOrder').value.trim())$('modelOrder').value='Nano Banana Pro\nNano Banana 2.1\nNano Banana 2 Lite';
  for(const id of ['modelChoice','count'])$(id).onchange=()=>void refresh();
  destination();
  await refresh();
  setInterval(refresh, 2000);
})();
