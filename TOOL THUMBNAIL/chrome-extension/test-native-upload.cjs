const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
let eventListener,attached=0,detached=0;const calls=[];
const chrome={runtime:{id:'test',onMessage:{addListener(){}}},tabs:{query:async()=>[{id:1,url:'https://flow.google.com/project/one'}],onUpdated:{addListener(){}}},debugger:{attach:async()=>{attached++;},detach:async()=>{detached++;},onEvent:{addListener:fn=>eventListener=fn,removeListener:()=>eventListener=null},sendCommand:async(target,method,params)=>{
 calls.push({method,params});if(method==='DOM.getDocument')return {root:{nodeId:1}};if(method==='DOM.querySelector')return {nodeId:5};
 if(method==='Runtime.evaluate')eventListener({tabId:1},'Page.fileChooserOpened',{backendNodeId:9});return {};
}}};
const ctx=vm.createContext({chrome,URL,setTimeout,clearTimeout});vm.runInContext(fs.readFileSync(__dirname+'/background.js','utf8'),ctx);
const sender={id:'test',frameId:0,tab:{id:1}},message={token:'12345678-1234-1234-1234-123456789abc',path:'C:\\reference-cache\\reference_'+ 'a'.repeat(64)+'.jpg'};
(async()=>{
 await ctx.nativeUpload(sender,{...message,input:true});assert.equal(calls.filter(e=>e.method==='DOM.setFileInputFiles').length,1);assert.equal(calls.find(e=>e.method==='DOM.setFileInputFiles').params.nodeId,5);
 calls.length=0;await ctx.nativeUpload(sender,{...message,input:false});assert.equal(calls.find(e=>e.method==='DOM.setFileInputFiles').params.backendNodeId,9);assert.equal(eventListener,null);assert.equal(attached,detached);
 await assert.rejects(ctx.nativeUpload({...sender,frameId:2},message),/không hợp lệ/);
 await assert.rejects(ctx.nativeUpload(sender,{...message,path:'C:\\secret.txt'}),/không hợp lệ/);
 console.log('PASS: real file upload supports an existing input or intercepted chooser; cleanup detaches debugger and rejects invalid files/subframes.');
})().catch(e=>{console.error(e);process.exitCode=1;});
