const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
let handler, panelId, creates = 0, injections = 0, windowsCreated=0, flowIds=[1,3];
const projectUrl = 'https://flow.google.com/project/94997f68-7210-4ab9-ae88-6ee69aebede7';
const tabs = new Map([[1,{id:1,url:'https://labs.google/fx/tools/flow/project/demo'}],[2,{id:2,url:'https://example.com'}],[3,{id:3,url:projectUrl}]]);
const chrome = {
 runtime:{id:'test',getURL:p=>'chrome-extension://test/'+p,onMessage:{addListener:fn=>handler=fn}},
 tabs:{query:async()=>flowIds.map(id=>tabs.get(id)),get:async id=>{if(!tabs.has(id))throw Error('closed');return tabs.get(id);},
 create:async ({url})=>{creates++;const tab={id:100,url,windowId:1};tabs.set(100,tab);return tab;},
 update:async (id,changes)=>Object.assign(tabs.get(id),changes)},
 scripting:{executeScript:async()=>{injections++;}},
 windows:{update:async()=>{},create:async options=>{assert.equal(options.type,'popup');assert.equal(options.url,chrome.runtime.getURL('panel.html?tab=3'));windowsCreated++;const tab={id:101,url:options.url,windowId:8};tabs.set(101,tab);return {tabs:[tab]};}},
 storage:{session:{get:async()=>({panelId}),set:async data=>{panelId=data.panelId;}}},
 downloads:{download:async()=>42,search:async()=>[{state:'complete',mime:'image/png',filename:'test.png'}]}
};
const context = vm.createContext({chrome,URL,console});
vm.runInContext(fs.readFileSync(__dirname+'/background.js','utf8'),context);
const connect = id=>new Promise(resolve=>handler({type:'connect',tabId:id},{id:'test',url:chrome.runtime.getURL('popup.html')},resolve));
(async()=>{
 assert.equal(creates,0);
 assert.ok((await connect(2)).error);assert.equal(creates,0);
 flowIds=[1];
 assert.ok((await connect(1)).ok);assert.equal(creates,1);
 assert.ok((await connect(1)).ok);assert.equal(creates,1);
 assert.equal(injections,2);
 tabs.delete(100);
 assert.ok((await connect(1)).ok);assert.equal(creates,2);
 flowIds=[3];assert.ok((await connect(3)).ok);assert.equal(creates,2);
 assert.equal(tabs.get(100).url,chrome.runtime.getURL('panel.html?tab=3'));
 for(const url of [projectUrl,'https://flow.google/','https://labs.google/fx/vi/tools/flow/project/demo']) {
   assert.equal(context.isFlow(url),true);
 }
 for(const url of ['https://flow.google.com.evil.example/project/1','https://example.com/flow.google.com','http://flow.google.com/','https://labs.google/fx/tools/other']) {
   assert.equal(context.isFlow(url),false);
 }
 const downloaded = await new Promise(resolve=>handler({type:'download',url:'https://example.com/image.png',filename:'Flow_TXT/run_123/0001_01.png'},{id:'test',tab:{id:3},url:projectUrl},resolve));
 assert.equal(downloaded.id,42);
 const status = await new Promise(resolve=>handler({type:'downloadStatus',id:42},{id:'test',tab:{id:3},url:projectUrl},resolve));
 assert.equal(status.state,'complete');
 console.log('PASS: flow.google.com project connects and download messages are accepted; lookalike domains rejected.');
 console.log('PASS: wrong tab creates nothing; repeated connection reuses panel; closed panel recreated.');
 const desktop=()=>new Promise(resolve=>handler({type:'connect'},{id:'test',url:chrome.runtime.getURL('popup.html?desktop=1')},resolve));
 assert.ok((await desktop()).ok);assert.equal(windowsCreated,0);assert.equal(panelId,100);
 tabs.delete(100);assert.ok((await desktop()).ok);assert.equal(windowsCreated,1);assert.equal(panelId,101);
 assert.ok((await desktop()).ok);assert.ok((await connect(3)).ok);assert.equal(windowsCreated,1);assert.equal(creates,2);assert.equal(panelId,101);
 console.log('PASS: desktop and extension reuse the identical panel; desktop creates a popup window only when no panel exists.');
})().catch(e=>{console.error(e);process.exitCode=1;});
