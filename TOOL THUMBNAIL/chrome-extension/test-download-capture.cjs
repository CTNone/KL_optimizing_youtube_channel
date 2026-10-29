const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
let handler,determine;const data={};
const project='https://flow.google.com/project/demo';
const chrome={runtime:{id:'test',getURL:p=>'chrome-extension://test/'+p,onMessage:{addListener:fn=>handler=fn}},tabs:{query:async()=>[{id:1,url:project}],onUpdated:{addListener(){}}},storage:{session:{get:async()=>structuredClone(data),set:async values=>Object.assign(data,structuredClone(values)),remove:async key=>delete data[key]}},downloads:{onDeterminingFilename:{addListener:fn=>determine=fn},search:async()=>[{id:42,state:'complete',mime:'image/webp',filename:'C:\\Downloads\\image.webp',url:'https://example.test/2k.webp'}]}};
const context=vm.createContext({chrome,URL,Date,crypto:require('node:crypto').webcrypto});vm.runInContext(fs.readFileSync(__dirname+'/background.js','utf8'),context);
const sender={id:'test',tab:{id:1},frameId:0,url:project};
const send=m=>new Promise(resolve=>handler(m,sender,resolve));
const event=item=>new Promise(resolve=>determine(item,resolve));
(async()=>{
 const armed=await send({type:'armFlowDownload',filename:'Flow_TXT/run_123/0001_01.png'});assert.equal(armed.ok,true);
 await event({id:99,referrer:'https://example.test/',mime:'image/png'});assert.equal(data.flowDownload.id,undefined);
 await event({id:98,referrer:'https://flow.google.com/project/another',mime:'image/png'});assert.equal(data.flowDownload.id,undefined);
 const rename=await event({id:42,referrer:'https://flow.google.com/',mime:'image/webp'});assert.equal(rename.filename,'Flow_TXT/run_123/0001_01.webp');
 assert.equal((await send({type:'flowDownloadStatus',token:armed.token})).state,'complete');
 assert.ok((await send({type:'flowDownloadStatus',token:'wrong'})).error);
 await send({type:'cancelFlowDownload',token:armed.token});assert.equal(data.flowDownload,undefined);
 console.log('PASS: capture only armed Flow download; handle origin-only referrer; reject other project/source and expired tokens; preserve MIME extension.');
})().catch(error=>{console.error(error);process.exitCode=1;});
