const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const html=fs.readFileSync(__dirname+'/panel.html','utf8');
const elements=Object.fromEntries([...html.matchAll(/id="([^"]+)"/g)].map(m=>[m[1],{value:'',textContent:'',disabled:false,files:[],renders:0,querySelectorAll(){return this.children || [];},replaceChildren(...items){this.children=items;this.renders++;}}]));
Object.assign(elements.count,{value:'2'});Object.assign(elements.timeout,{value:'240'});Object.assign(elements.image,{value:'img'});Object.assign(elements.saveMode,{value:'downloads'});Object.assign(elements.clickMode,{value:'native'});
let current={running:false,logs:[],items:[]},sent=null,poll,stored={},fileHandler,imports=0,crops=0;
const browserWindow={showDirectoryPicker:async()=>({name:'My Images'})};
vm.runInNewContext(fs.readFileSync(__dirname+'/panel.js','utf8'),{
 document:{getElementById:id=>{assert.ok(elements[id],'Unknown UI id: '+id);return elements[id];},createElement:()=>({textContent:'',dataset:{},append(...children){this.children=children;}})},
 URLSearchParams,location:{search:'?tab=1'},setInterval:fn=>{poll=fn;},window:browserWindow,
 NativeFiles:{directory:'C:\\Output',importImage:async()=>{imports++;return {ok:true,filename:'C:\\Output\\original.jpg',width:2048,height:1536};},cropImage:async()=>{if(++crops===1)throw new Error('crop disk error');return {filename:'C:\\Output\\original_16x9.jpg',width:2048,height:1152};}},
 chrome:{runtime:{id:'test',sendMessage:async m=>{if(m.type==='startFreshRun')sent={type:'run',...m.args,freshReload:true};return {ok:true};},onMessage:{addListener(fn){fileHandler=fn;}}},storage:{local:{get:async()=>stored,set:async()=>{}}},tabs:{sendMessage:async(id,m)=>{if(m.type==='status')return current;sent=m;return {ok:true};}}}
});
(async()=>{
 await new Promise(r=>setImmediate(r));
 assert.ok(elements.run.disabled);
 elements.file.files=[{name:'single.txt',size:100,text:async()=> '\ufeffFirst line\r\n---\r\nSecond line'}];
 await elements.file.onchange();
 assert.equal(elements.run.disabled,false);
 await elements.run.onclick();
 assert.equal(sent.prompt,'First line\n---\nSecond line');assert.equal(sent.fileName,'single.txt');assert.equal(sent.prompts,undefined);
 assert.equal(sent.freshReload,true);
 elements.promptEditor.value='Edited prompt\nwith two lines';elements.promptEditor.oninput();
 await elements.run.onclick();assert.equal(sent.prompt,'Edited prompt\nwith two lines');assert.match(elements.editStatus.textContent,/Đã chỉnh sửa/);
 elements.promptEditor.value='  ';elements.promptEditor.oninput();assert.equal(elements.run.disabled,true);
 elements.promptEditor.value='Restored';elements.promptEditor.oninput();
 current={running:false,fileName:'single.txt',flowMessage:'Exact message from Flow',logs:['System diagnostic'],items:[{status:'blocked_policy',error:'combined old detail',files:['run_123/0001_01.png'],croppedFiles:['run_123/0001_01_16x9.jpg']}]};
 await poll();
 assert.equal(elements.flowMessage.textContent,'Exact message from Flow');
 assert.equal(elements.status.textContent,'System diagnostic');
 assert.ok(!elements.summary.textContent.includes('Exact message'));
 assert.equal(elements.savedCount.textContent,'1 ảnh gốc · 1 bản 16:9');
 assert.equal(elements.files.children[0].textContent,'run_123/0001_01.png');
 assert.equal(elements.run.disabled,false);
 await elements.folder.onclick();assert.equal(elements.folderName.textContent,'Đã chọn: My Images');assert.equal(elements.saveMode.value,'folder');
 browserWindow.showDirectoryPicker=async()=>{throw Object.assign(new Error('cancel'),{name:'AbortError'});};
 await elements.folder.onclick();assert.equal(elements.folderName.textContent,'Đã chọn: My Images');
 elements.saveMode.value='downloads';elements.saveMode.onchange();assert.equal(elements.folderName.textContent,'Thư mục tải xuống của Chrome');
 stored={runHistory:[{id:'one',time:new Date().toISOString(),fileName:'failure.txt',status:'setup_error',prompt:'Prompt',attempts:[{attempt:1,model:'Nano Banana Pro',reason:'menu not ready'}]}],modelLimits:{'Nano Banana Pro':{count:2,disabled:false}}};
 await poll();const entry=elements.history.children[0];entry.open=true;const renders=elements.history.renders;
 await poll();await poll();assert.equal(elements.history.renders,renders);assert.equal(elements.history.children[0],entry);assert.equal(entry.open,true);
 stored.runHistory[0].status='done';await poll();assert.equal(elements.history.children[0].open,true);
 assert.ok(!elements.modelLimits.textContent.includes('Nano Banana Pro'));assert.match(elements.modelEvidence.textContent,/2\/3/);
 stored.modelLimits['Nano Banana Pro']={count:3,disabled:true};await poll();assert.match(elements.modelLimits.textContent,/Nano Banana Pro: 3/);
 assert.match(elements.plannedModel.textContent,/Nano Banana 2/);
 console.log('PASS: panel submits entire file once; system/Flow output separated; saved files visible; retry/new file controls enabled after error.');
 console.log('PASS: edited text submitted; empty prompt disabled; chosen folder displayed and preserved on cancel; Downloads mode accurately labeled.');
 console.log('PASS: history remains open across polls and updates; model limits list only 3+ confirmed failures; planned model skips blocked Pro.');
 elements.saveMode.value='windows';
 const process=()=>new Promise(resolve=>fileHandler({type:'processDownloadedImage',tabId:1,path:'run_123/0001_01.jpg',source:'C:\\Downloads\\one.jpg'},{id:'test'},resolve));
 assert.match((await process()).error,/crop disk error/);
 const pair=await process();assert.equal(pair.filename,'C:\\Output\\original.jpg');assert.equal(pair.croppedFilename,'C:\\Output\\original_16x9.jpg');assert.equal(imports,1);assert.equal(crops,2);
 await process();assert.equal(imports,1);assert.equal(crops,2);
 console.log('PASS: crop failure retains the saved original; retry produces the 16:9 pair without importing/downloading the original twice.');
})().catch(e=>{console.error(e);process.exitCode=1;});

