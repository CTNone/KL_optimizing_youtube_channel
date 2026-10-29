const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
let calls=[],blocked=false,failRelease=false,hoverMoves=false,resolves=0;
const chrome={
 runtime:{id:'test',getURL:p=>'chrome-extension://test/'+p,onMessage:{addListener(){}}},
 tabs:{query:async()=>[{id:7,url:'https://flow.google.com/project/test'}],get:async()=>({url:'https://flow.google.com/project/test',windowId:1}),update:async()=>{},sendMessage:async()=>blocked?{error:'overlay blocks button'}:{x:100,y:200}},
 windows:{update:async()=>{}},
 debugger:{attach:async()=>calls.push('attach'),detach:async()=>calls.push('detach'),sendCommand:async(target,method,params)=>{assert.equal(target.tabId,7);assert.equal(method,'Input.dispatchMouseEvent');calls.push(params.type);if(failRelease&&params.type==='mouseReleased')throw Error('release failed');}}
};
const context=vm.createContext({chrome,URL,console});
vm.runInContext(fs.readFileSync(__dirname+'/background.js','utf8'),context);
const sender={id:'test',tab:{id:7},frameId:0};
(async()=>{
 assert.ok((await context.nativeClick(sender,'token')).ok);
 assert.deepEqual(calls,['attach','mouseMoved','mousePressed','mouseReleased','detach']);
 calls=[];blocked=true;
 await assert.rejects(context.nativeClick(sender,'token'),e=>/overlay/.test(e.message) && e.code==='click_not_sent');
 assert.deepEqual(calls,['attach','detach']);
 calls=[];blocked=false;failRelease=true;
 await assert.rejects(context.nativeClick(sender,'token'),e=>/release failed/.test(e.message) && e.code==='click_uncertain');
 assert.deepEqual(calls,['attach','mouseMoved','mousePressed','mouseReleased','detach']);
 calls=[];
 await assert.rejects(context.nativeClick({...sender,frameId:1},'token'),/trang Flow chính/);
 assert.deepEqual(calls,[]);
 failRelease=false;calls=[];
 chrome.tabs.sendMessage=async()=>({x:++resolves===1?100:120,y:200});
 assert.ok((await context.nativeClick(sender,'token')).ok);
 assert.deepEqual(calls,['attach','mouseMoved','mouseMoved','mousePressed','mouseReleased','detach']);
 console.log('PASS: hover movement is stabilized before a single press; definitely unclicked failures and uncertain clicks have distinct codes.');
 console.log('PASS: Chrome press/release once; overlay aborts; failures detach without retry; subframes rejected.');
})().catch(e=>{console.error(e);process.exitCode=1;});
