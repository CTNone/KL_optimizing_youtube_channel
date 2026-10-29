(() => {
 const visible=e=>!!e.getClientRects().length && getComputedStyle(e).visibility!=='hidden' && !e.disabled && e.getAttribute('aria-disabled')!=='true';
 const text=e=>{
   const copy=e.cloneNode(true);
   copy.querySelectorAll('svg,[aria-hidden="true"],.material-icons,.material-symbols-outlined,.material-symbols-rounded,[class*="material-symbol"],mat-icon,.google-symbols').forEach(n=>n.remove());
   return [...new Set([copy.textContent,e.getAttribute('aria-label'),e.getAttribute('title')].filter(Boolean).map(v=>v.replace(/\s+/g,' ').trim()))].join(' ').replace(/\b(?:videocam|image|crop_landscape|crop_portrait|dashboard|view_quilt|keyboard_arrow_down|expand_more|check|check_small|done)\b/gi,' ').replace(/\s+/g,' ').trim();
 };
 const controls=()=>[...document.querySelectorAll('button,[role=button],[role=option],[role=menuitem],[role=menuitemradio],[role=radio],[role=tab],[role=combobox]')].filter(visible);
 function find(pattern,token) {
   const regex=new RegExp(pattern,'i');
   const rows=controls().filter(e=>regex.test(text(e)));
   const unique=rows.filter(e=>!rows.some(child=>child!==e&&e.contains(child)));
   if(unique.length===1)unique[0].setAttribute('data-video-control',token);
   return {count:unique.length,labels:unique.map(text)};
 }
 function trigger(token) {
   const editors=[...document.querySelectorAll('textarea,[contenteditable=true]')].filter(visible);
   if(editors.length!==1)return {count:0,reason:'Chưa thấy duy nhất ô prompt'};
   const box=editors[0].getBoundingClientRect();
   const near=controls().filter(e=>{
     const r=e.getBoundingClientRect();
     return r.top>=box.top-80&&r.top<=box.bottom+200&&r.left>=box.left-80&&r.right<=box.right+200 && !['option','menuitem','radio','tab','menuitemradio'].includes(e.getAttribute('role'));
   });
   const groups=[
     near.filter(e=> /settings|tune|options|cài đặt|thiết lập/i.test(text(e))),
     near.filter(e=> /(?:video|hình ảnh|images?|veo|nano banana)/i.test(text(e)) && (/\b[x×]\s*[1-4]\b|\d{3,4}p|\d+\s*(?:giây|sec)|veo|nano banana/i.test(text(e)) || e.getAttribute('aria-haspopup'))),
     near.filter(e=> /\b[x×]\s*[1-4]\b/i.test(text(e))),
     near.filter(e=> /(?:video|hình ảnh|images?)/i.test(text(e)) && e.getAttribute('aria-haspopup'))
   ];
   for(const rows of groups){
     const unique=rows.filter(e=>!rows.some(child=>child!==e&&e.contains(child)));
     if(unique.length===1){unique[0].setAttribute('data-video-control',token);return {count:1,label:text(unique[0])};}
     if(unique.length>1)return {count:unique.length,labels:unique.map(text)};
   }
   return {count:0,labels:near.map(text)};
 }
 const canonical=s=>s.toLowerCase().replace(/[\s\-–—]/g,'');
 function modelName(e) {
   const names=[...text(e).matchAll(/Veo\s*\d+(?:\.\d+)*(?:\s*[-–—]?\s*(?:Lite|Fast|Quality))?/gi)].map(m=>m[0]);
   const unique=[...new Set(names.map(canonical))];
   return unique.length===1?unique[0]:null;
 }
 function models(wanted,phase,token) {
   const name=canonical(wanted);
   let rows;
   if(phase==='options') {
     rows=controls().filter(e=>['option','menuitem','menuitemradio','radio'].includes(e.getAttribute('role')) || e.closest('[role=menu],[role=listbox]'));
     if(!rows.length) {
       // Thumbnail's fallback: plain div rows grouped as a model list.
       const labels=[...document.querySelectorAll('div,span,button')].filter(visible).filter(e=>modelName(e));
       rows=[];
       for(const label of labels){
         let row=label;
         for(let i=0;i<4&&row.parentElement;i++,row=row.parentElement){
           if(!modelName(row))break;
           const siblings=[...row.parentElement.children].filter(visible).filter(e=>modelName(e));
           if(new Set(siblings.map(modelName)).size>=2 || row.closest('[role=menu],[role=listbox]')) {
             rows.push(...siblings);break;
           }
         }
       }
     }
   } else {
     rows=controls().filter(e=>!['option','menuitem','menuitemradio','radio'].includes(e.getAttribute('role')) && !e.closest('[role=menu],[role=listbox]'));
   }
   rows=[...new Set(rows)].filter(e=>modelName(e)===name);
   rows=rows.filter(e=>!rows.some(child=>child!==e&&e.contains(child)));
   if(rows.length===1)rows[0].setAttribute('data-video-control',token);
   return {count:rows.length, labels:rows.map(text), available:[...new Set(controls().map(modelName).filter(Boolean))]};
 }
 function send(token) {
   const editors=[...document.querySelectorAll('textarea,[contenteditable=true]')].filter(visible);
   if(editors.length!==1)return {count:0,reason:'Chưa xác định duy nhất ô prompt'};
   const box=editors[0].getBoundingClientRect();
   const near=[...document.querySelectorAll('button,[role=button]')].filter(visible).filter(e=>{
     const r=e.getBoundingClientRect();
     return r.left>=box.left && r.left<=box.right+160 && r.top>=box.top-24 && r.top<=box.bottom+150;
   });
   const semantic=near.filter(e=>{
     // Read raw icon ligatures: generic text normalization removes icon spans.
     const labels=[e.getAttribute('aria-label'),e.getAttribute('title'),e.textContent,...[...e.querySelectorAll('svg title,i,mat-icon,.google-symbols,[class*="material-symbol"],[class*="material-icon"]')].map(n=>n.textContent)].filter(Boolean).map(v=>v.trim());
     return labels.some(v=>/^(arrow_forward|arrow_upward|send|generate|create|tạo|tạo video|gửi|→|↑)$/i.test(v));
   });
   let matches=semantic;
   if(!matches.length){
     // Same geometry and color checks as Thumbnail's generate(afterFill).
     matches=near.filter(e=>{
       const r=e.getBoundingClientRect(),style=getComputedStyle(e);
       const channels=style.backgroundColor.match(/[\d.]+/g)?.map(Number);
       const width=r.width,height=r.height;
       return channels?.length>=3 && channels.slice(0,3).every(v=>v>=220) &&
         (channels.length<4||channels[3]>=.9) && width>=28&&width<=64&&height>=28&&height<=64 &&
         Math.abs(width-height)<=8 && r.left>=box.right-100 && r.top>=box.bottom-4;
     });
   }
   if(matches.length===1)matches[0].setAttribute('data-video-control',token);
   return {count:matches.length,labels:matches.map(text)};
 }
 const videoIdentity=src=>{
   try{
     const url=new URL(src,location.href);
     const ids=['id','assetId','mediaId','name'].filter(k=>url.searchParams.has(k)).map(k=>k+'='+url.searchParams.get(k)).join('&');
     return url.origin+url.pathname+(ids?'?'+ids:'');
   }catch{return src;}
 };
 function videoNodes(source){return [...document.querySelectorAll('video')].filter(visible).filter(v=>videoIdentity(v.currentSrc||v.getAttribute('src')||v.querySelector('source[src]')?.src)===videoIdentity(source));}
 const downloadLabel=e=>[e.textContent,e.getAttribute('aria-label'),e.getAttribute('title'),...[...e.querySelectorAll('svg title,i,mat-icon,.google-symbols,[class*="material-symbol"],[class*="material-icon"]')].map(n=>n.textContent)].filter(Boolean).some(v=>/^(download|download_2|file_download|tải.*xuống|tải về|tải video)$/i.test(v.trim()));
 function downloadControl(source,token,preview=false,originalWidth=0){
   const videos=videoNodes(source);
   let rows=[];
   for(const video of videos){
     let card=video.parentElement;
     for(let i=0;i<10&&card;i++,card=card.parentElement){
       const sources=new Set([...card.querySelectorAll('video')].map(v=>videoIdentity(v.currentSrc||v.src)).filter(Boolean));
       if(sources.size>1)break;
       const found=[...card.querySelectorAll('button,[role=button]')].filter(visible).filter(downloadLabel);
       if(found.length){rows.push(...found);break;}
     }
   }
   if(!rows.length&&preview){
     const correct=location.pathname.includes('/edit/')||videos.some(v=>v.closest('[role=dialog],[data-state=open],.cdk-overlay-pane')||v.getBoundingClientRect().width>Math.max(512,originalWidth*1.2));
     if(correct)rows=[...document.querySelectorAll('button,[role=button]')].filter(visible).filter(downloadLabel);
   }
   rows=[...new Set(rows)];
   if(rows.length===1)rows[0].setAttribute('data-video-control',token);
   return {count:rows.length,labels:rows.map(text),videos:videos.length};
 }
 function preview(source,originalWidth,originalHeight=0){
   const videos=videoNodes(source).filter(v=>v.closest('[role=dialog],[data-state=open],.cdk-overlay-pane')||v.getBoundingClientRect().width>Math.max(512,originalWidth*1.2)||originalHeight>0&&v.getBoundingClientRect().height>Math.max(360,originalHeight*1.3)&&v.getBoundingClientRect().width*v.getBoundingClientRect().height>originalWidth*originalHeight*1.4);
   return {verified:videos.length>0,count:videos.length};
 }
 function resolutions(token){
   const containers=[...document.querySelectorAll('[role=menu],[role=listbox]')].filter(visible);
   const roots=containers.length?containers:[document.body];
   const semantic='button,[role=menuitem],[role=option],[role=menuitemradio],[role=button]';
   let rows=[...new Set(roots.flatMap(root=>[...root.querySelectorAll(semantic)]))].filter(visible);
   const label=e=>(e.querySelector('.label')?.textContent||text(e)).trim();
   const rank=e=>{
     if(/gif/i.test(text(e)))return 0;
     const value=label(e);
     const m=value.match(/^(?:(?:download|tải xuống|tải về|upscale)\s*[:·-]?\s*)?(?:(\d{3,4})\s*p|([248])\s*k)(?:$|\s)/i);
     return m?m[1]?+m[1]:+m[2]*540:0;
   };
   const allowed=e=>{
     const owner=e.closest('flow-menu-item')||e;
     for(const row of [e,owner]){
       if(row.disabled||row.getAttribute('aria-disabled')==='true'||row.hasAttribute('data-disabled')&&row.getAttribute('data-disabled')!=='false')return false;
       if(/upgrade|nâng cấp|buy|mua gói|requires? (?:pro|ultra|subscription)|yêu cầu.*(?:gói|đăng ký)/i.test(text(row)))return false;
       if([...row.querySelectorAll('mat-icon,.google-symbols,[class*="material-symbol"],[class*="material-icon"]')].some(n=>/^(lock|lock_outline)$/i.test(n.textContent.trim())))return false;
     }
     return true;
   };
   rows=rows.filter(e=>rank(e)>0&&allowed(e));
   rows=rows.filter(e=>!rows.some(child=>child!==e&&e.contains(child)));
   const top=Math.max(0,...rows.map(rank)),best=rows.filter(e=>rank(e)===top);
   if(best.length===1)best[0].setAttribute('data-video-control',token);
   return {count:best.length,label:best.length===1?label(best[0]):null,rank:top,available:rows.map(label)};
 }
 function openClip(source,token){
   const nodes=[...document.querySelectorAll('video')].filter(v=>videoIdentity(v.currentSrc||v.getAttribute('src')||v.querySelector('source[src]')?.src)===videoIdentity(source));
   const remembered=[...document.querySelectorAll('flow-video-tile[data-video-source]')].filter(tile=>tile.getAttribute('data-video-source')===videoIdentity(source));
   let targets=remembered.map(tile=>{const image=tile.querySelector('img.thumbnail');return image&&visible(image)?image:visible(tile)?tile:null;}).filter(Boolean);
   if(!targets.length)targets=nodes.map(v=>{
     const tile=v.closest('flow-video-tile');
     const image=tile?.querySelector('img.thumbnail');
     return image&&visible(image)?image:visible(v)?v:null;
   }).filter(Boolean);
   if(!targets.length){
     targets=[...document.querySelectorAll('flow-video-tile img.thumbnail')].filter(visible).filter(img=>(videoIdentity(img.src)===videoIdentity(source)||videoIdentity(img.src).replace('/image/','/video/')===videoIdentity(source)));
   }
   if(targets.length===1){targets[0].setAttribute('data-video-control',token);const r=targets[0].getBoundingClientRect();return {count:1,width:r.width,height:r.height};}
   return {count:targets.length};
 }
 function results(includeHidden=false){
   const rows=[],seenTiles=new Set();
   const normalize=s=>(s||'').replace(/\s+/g,' ').trim();
   const busy=element=>{
     let card=element;
     for(let depth=0;depth<6&&card;depth++,card=card.parentElement){
       if(card.querySelectorAll('flow-video-tile').length>1||card.querySelectorAll('video').length>1)break;
       if(card.matches('[aria-busy=true],[data-status=generating],[data-state=loading]')||card.querySelector('[aria-busy=true],[data-status=generating],[data-state=loading]'))return true;
       // Generation progress is distinct from the player's .progress-bar.
       const progress=[...card.querySelectorAll('[role=progressbar]')];
       if(progress.some(e=>{const value=Number(e.getAttribute('aria-valuenow')),max=Number(e.getAttribute('aria-valuemax')||100);return !e.hasAttribute('aria-valuenow')||!Number.isFinite(value)||value<max;}))return true;
     }
     return false;
   };
   const add=(element,source,video=null)=>{
     if(!source||busy(element))return;
     const tile=element.closest('flow-video-tile');
     const row=element.closest('flow-grid-tile-container')||element.closest('.tile-row');
     const prompts=row?[...row.querySelectorAll('span,p,div')].filter(e=>!e.querySelector('video')&&!e.closest('button')).map(e=>normalize(e.textContent)).filter(Boolean):[];
     const poster=tile?.querySelector('img.thumbnail');
     const posterKey=poster?.src?'poster:'+videoIdentity(poster.src):null;
     tile?.setAttribute('data-video-source',videoIdentity(source));
     if(tile)seenTiles.add(tile);
     rows.push({src:source,key:videoIdentity(source),posterKey,prompts,duration:video&&Number.isFinite(video.duration)?video.duration:0,readyState:video?.readyState||0});
   };
   for(const video of document.querySelectorAll('video')){
     if(!includeHidden&&!visible(video)&&!visible(video.closest('flow-video-tile')||video))continue;
     if(video.error)continue;
     add(video,video.currentSrc||video.getAttribute('src')||video.querySelector('source[src]')?.src,video);
   }
   // Real Flow can publish the completed thumbnail before mounting any player.
   // Open that generated-video tile directly; never wait for hover or playback.
   for(const tile of document.querySelectorAll('flow-video-tile')){
     if(seenTiles.has(tile)||!includeHidden&&!visible(tile))continue;
     const poster=tile.querySelector('img.thumbnail');
     if(poster?.src&&poster.complete&&poster.naturalWidth>0)add(poster,poster.src);
   }
   return [...new Map(rows.map(row=>[row.key,row])).values()];
 }
 function snapshot(){
   const keys=results(true).flatMap(row=>[row.key,row.posterKey]).filter(Boolean);
   for(const image of document.querySelectorAll('flow-video-tile img.thumbnail'))
     if(image.src)keys.push('poster:'+videoIdentity(image.src));
   return [...new Set(keys)];
 }
 globalThis.VideoControls={find,trigger,text,models,send,videoIdentity,downloadControl,resolutions,preview,results,openClip,snapshot};
})();
