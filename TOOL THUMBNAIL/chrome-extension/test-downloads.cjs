const assert=require('node:assert/strict');const vm=require('node:vm');const fs=require('node:fs');
let width=2048,height=1152,phase='grid',paid=false,clicks=[],messages=[],replaceOnHover=false,uncertain=false,escapeFailure=false,wrongPreview=false,readFailure=false,fetches=0;
const base={getClientRects:()=>[1],getAttribute:()=>null};
const image={...base,textContent:'image',currentSrc:'https://example.test/a.png',getBoundingClientRect:()=>({width:400,height:300})};
const preview={...base,complete:true,naturalWidth:1024,get currentSrc(){return wrongPreview?'https://example.test/old.png':image.currentSrc;},getBoundingClientRect:()=>({width:900,height:675})};
const download={...base,textContent:'Download'};
let freshDownload=download;
const twoK={...base,get textContent(){return paid?'2K 10 credits':'2K';}};
const card={parentElement:null,querySelectorAll:()=>[]};
const context=vm.createContext({
 URL,
 document:{body:{},querySelectorAll:css=>css.includes('img')?(phase!=='grid'?[preview]:[]):phase==='preview'?[freshDownload]:phase==='menu'?[twoK]:[]},
 getComputedStyle:()=>({visibility:'visible'}),AbortSignal,
 fetch:async()=>{fetches++;throw new Error('Remote fetch must never run for completed downloads');},
 createImageBitmap:async()=>({width,height,close(){}}),
 FileReader:class{readAsDataURL(){this.result='data:image/png;base64,AAAA';this.onload();}},
 chrome:{runtime:{sendMessage:async m=>{messages.push(m.type);if(m.type==='armFlowDownload')return {ok:true,token:'one'};if(m.type==='flowDownloadStatus')return {state:'complete',url:'https://example.test/original.png',filename:'C:\\Downloads\\2k.png'};if(m.type==='readFlowDownload'){if(readFailure){readFailure=false;return {error:'disk busy'};}return Math.max(width,height)<2048?{error:'chưa đạt 2K'}:{ok:true,width,height,filename:'C:\\Output\\a.png',sha256:image.currentSrc};}if(m.type==='nativeEscape'){const previous=phase;phase='grid';if(escapeFailure&&previous==='downloading')return {error:'preview close failed'};}return {ok:true};}}}
});
vm.runInContext(fs.readFileSync(__dirname+'/flow-downloads.js','utf8'),context);
const args={result:{card,img:image},cfg:{},filename:'Flow_TXT/run_1/0001_01.png',click:async e=>{clicks.push(e);
 if(e===freshDownload && uncertain)throw Object.assign(new Error('press response lost'),{code:'click_uncertain'});
 if(e===freshDownload && replaceOnHover){replaceOnHover=false;freshDownload={...download,isConnected:true};throw Object.assign(new Error('Download rerendered'),{code:'click_not_sent'});}
 phase=e===image?'preview':e===freshDownload?'menu':'downloading';},sleep:async()=>{},check(){}};
(async()=>{
 const result=await context.FlowDownloads.save(args);
 assert.equal(result.image.width,2048);assert.equal(result.image.height,1152);
 assert.deepEqual(clicks,[image,download,twoK]);assert.equal(phase,'grid');
 const originalPreviewBounds=preview.getBoundingClientRect;
 preview.getBoundingClientRect=()=>({width:350,height:263});
 assert.equal((await context.FlowDownloads.save(args)).image.width,2048);
 preview.getBoundingClientRect=originalPreviewBounds;
 const readNodes=context.document.querySelectorAll,clickOriginal=args.click,originalResult=args.result;
 const replacement={...image,isConnected:true,complete:true,currentSrc:image.currentSrc+'?size=preview'};
 context.document.querySelectorAll=css=>css==='img'&&phase==='grid'?[replacement]:readNodes(css);
 args.result={card,img:{...image,isConnected:false},src:image.currentSrc};
 args.click=async e=>{if(e===replacement){clicks.push(e);phase='preview';return;}return clickOriginal(e);};
 clicks=[];
 assert.equal((await context.FlowDownloads.save(args)).image.width,2048);
 assert.deepEqual(clicks,[replacement,download,twoK]);
 context.document.querySelectorAll=readNodes;args.click=clickOriginal;args.result=originalResult;
 assert.ok(messages.indexOf('armFlowDownload')<messages.indexOf('flowDownloadStatus'));
 width=1024;height=1024;await assert.rejects(context.FlowDownloads.save(args),/chưa đạt 2K/);assert.equal(phase,'grid');
 delete args.result.pendingDownload;
 paid=true;messages=[];await assert.rejects(context.FlowDownloads.save(args),/có phí/);assert.ok(!messages.includes('armFlowDownload'));
 paid=false;width=2048;height=1152;phase='grid';clicks=[];replaceOnHover=true;
 assert.equal((await context.FlowDownloads.save(args)).image.width,2048);
 assert.deepEqual(clicks,[image,download,freshDownload,twoK]);assert.equal(phase,'grid');
 uncertain=true;clicks=[];await assert.rejects(context.FlowDownloads.save(args),/press response lost/);
 assert.equal(clicks.filter(e=>e===freshDownload).length,1);uncertain=false;
 escapeFailure=true;const kept=await context.FlowDownloads.save(args);assert.equal(kept.image.width,2048);assert.match(kept.warning,/preview close failed/);
 escapeFailure=false;wrongPreview=true;messages=[];await assert.rejects(context.FlowDownloads.save(args),/chưa khớp/);assert.ok(!messages.includes('armFlowDownload'));wrongPreview=false;
 readFailure=true;messages=[];await assert.rejects(context.FlowDownloads.save(args),/disk busy/);assert.ok(args.result.pendingDownload);
 assert.equal((await context.FlowDownloads.save(args)).image.width,2048);assert.equal(messages.filter(t=>t==='armFlowDownload').length,1);assert.equal(fetches,0);
 console.log('PASS: wrong/stale preview never downloads; local file read avoids CORS; destination retry reuses one downloaded file instead of downloading duplicates.');
 console.log('PASS: reacquire Download replaced by hover only before any press; uncertain clicks are not repeated; completed 2K result survives preview-close failure.');
 console.log('PASS: open image → Download → free 2K; verify actual dimensions; reject 1K and paid 2K; close preview after download.');
})().catch(e=>{console.error(e);process.exitCode=1;});
