const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
let handler,reloads=0,resumes=0;const data={};const project='https://flow.google.com/project/one';
const chrome={
 runtime:{id:'test',getURL:p=>'chrome-extension://test/'+p,onMessage:{addListener:fn=>handler=fn}},
 tabs:{query:async()=>[{id:7,url:project}],reload:async id=>{assert.equal(id,7);reloads++;},onUpdated:{addListener(){}},sendMessage:async(id,message)=>{assert.equal(id,7);assert.equal(message.type,'resumeRun');assert.equal(message.checkpoint.nextAttempt,1);assert.equal(message.checkpoint.args.cfg.modelChoice,'Nano Banana Lite');resumes++;return {ok:true};}},
 scripting:{executeScript:async()=>{}},
 storage:{session:{get:async()=>structuredClone(data),set:async values=>Object.assign(data,structuredClone(values))}}
};
const context=vm.createContext({chrome,URL,Date,crypto:require('node:crypto').webcrypto,setTimeout:(fn,ms)=>{assert.equal(ms,2000);queueMicrotask(fn);}});vm.runInContext(fs.readFileSync(__dirname+'/background.js','utf8'),context);
const request={type:'startFreshRun',tabId:7,args:{prompt:'keep prompt',cfg:{modelChoice:'Nano Banana Lite',count:'2'},fileName:'one.txt'}};
const sender={id:'test',url:chrome.runtime.getURL('panel.html?tab=7')};
const send=()=>new Promise(resolve=>handler(request,sender,resolve));
(async()=>{
 assert.equal((await send()).ok,true);assert.equal(reloads,1);assert.equal(resumes,0);
 const cp=data.recovery_7.checkpoint;assert.equal(cp.initialReload,true);assert.equal(cp.nextAttempt,1);assert.equal(cp.args.cfg.count,'2');assert.equal(cp.args.prompt,'keep prompt');
 assert.ok((await send()).error);assert.equal(reloads,1);
 await context.resumeAfterReload(7);assert.equal(resumes,1);assert.equal(data.recovery_7.phase,'resumed');
 console.log('PASS: panel Run saves prompt/Lite/count, reloads exactly once before any generation, rejects another start during reload, then dispatches attempt 1.');
})().catch(error=>{console.error(error);process.exitCode=1;});
