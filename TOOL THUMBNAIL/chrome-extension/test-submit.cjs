const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
let handler, filled = false, clicks = 0, downloaded = 0, failureCode = null, writeFailure = false, partial = false, policyFirstOnly=false,badImageUrl=false,downloadModule;
const base = {isConnected:true,querySelectorAll:()=>[],getClientRects:()=>[1],getAttribute:()=>null,contains:()=>false};
class Textarea {
 set value(text) {this._value=text;filled=true;}
 get value(){return this._value;}
}
const input = Object.assign(new Textarea(),base,{focus(){},dispatchEvent(){},textContent:'',getBoundingClientRect:()=>({left:500,right:1200,top:800,bottom:850})});
const button = {...base,tagName:'BUTTON',textContent:'',getBoundingClientRect:()=>({left:1220,right:1260,top:870,bottom:910}),click(){assert.ok(filled);clicks++;}};
const img = {...base,complete:true,naturalWidth:1024,naturalHeight:1024,get currentSrc(){return badImageUrl?'http://[':`https://example.com/new${clicks}.png`;},getBoundingClientRect:()=>({width:400,height:300})};
const document = {elementFromPoint:()=>button,querySelectorAll:css=>{
 if(css==='textarea, [contenteditable="true"]')return [input];
 if(css==='button, [role="button"]')return filled ? [button] : [];
 if(css==='img')return clicks && (!failureCode || partial || (policyFirstOnly&&clicks>1)) ? [img] : [];
 return [];
}};
function boot(){vm.runInNewContext(fs.readFileSync(__dirname+'/content.js','utf8'),{
 document,Date,URL,FlowDownloads:downloadModule,crypto:require('node:crypto').webcrypto,innerWidth:1400,innerHeight:1000,location:{href:'https://flow.google.com/project/test'},Event:class{},HTMLTextAreaElement:Textarea,HTMLInputElement:class{},
 FlowErrors:{watch:()=>{const baseline=clicks;return {check(){if(failureCode&&clicks>baseline&&(!policyFirstOnly||clicks===1))throw Object.assign(new Error('Flow blocked'),{code:failureCode,flowMessage:'Exact Flow notification'});},disconnect(){}};}},
 setTimeout:fn=>setTimeout(fn,0),getComputedStyle:e=>({visibility:'visible',backgroundColor:e===button?'rgb(255, 255, 255)':'rgb(0, 0, 0)'}),
 chrome:{runtime:{id:'test',onMessage:{addListener:fn=>handler=fn},sendMessage:async m=>{
 if(m.type==='recoverRun'){setTimeout(()=>{boot();send({type:'resumeRun',checkpoint:m.checkpoint});},0);return {ok:true};}
 if(m.type==='nativeClick'){
   const point=send({type:'resolveClick',token:m.token});
   assert.equal(point.x,1240);assert.equal(point.y,890);
   button.click();return {ok:true};
 }
 if(m.type==='download'){downloaded++;return writeFailure?{error:'download denied'}:{id:42};}return {state:'complete',mime:'image/png',filename:'result.png'};
 }},storage:{local:{set:async()=>{}}}}
});}
boot();
function send(message){let result;handler(message,{id:'test'},r=>result=r);return result;}
(async()=>{
 const cfg={prompt:'',generate:'',card:'',image:'img',original:'',count:'1',timeout:'10',clickMode:'dom'};
 assert.ok(send({type:'run',cfg,prompts:['one','two'],start:0}).error);
 assert.ok(send({type:'run',cfg,prompt:'sample\n---\nsecond paragraph',fileName:'one.txt'}).ok);
 assert.ok(send({type:'run',cfg,prompt:'duplicate'}).error);
 for(let i=0;i<100&&send({type:'status'}).running;i++)await new Promise(r=>setTimeout(r,5));
 const state=send({type:'status'});
 assert.equal(state.running,false);
 assert.equal(state.items[0].status,'done',JSON.stringify(state.logs));
 assert.equal(clicks,1);assert.equal(downloaded,1);
 assert.equal(input.value,'sample\n---\nsecond paragraph');
 assert.equal(state.fileName,'one.txt');
 console.log('PASS: no send button before input; white send appears after input; clicked once and image downloaded.');
 filled=false;clicks=0;downloaded=0;cfg.clickMode='native';
 assert.ok(send({type:'run',cfg,prompt:'second sample'}).ok);
 for(let i=0;i<100&&send({type:'status'}).running;i++)await new Promise(r=>setTimeout(r,5));
 const nativeState=send({type:'status'});
 assert.equal(nativeState.items[0].status,'done',JSON.stringify(nativeState.logs));
 assert.equal(clicks,1);assert.equal(downloaded,1);
 assert.ok(send({type:'resolveClick',token:'expired'}).error);
 console.log('PASS: native click request validates live point and completes queue; expired click rejected.');
 for(const code of ['blocked_credit','blocked_policy']){
   filled=false;clicks=0;downloaded=0;failureCode=code;
   assert.ok(send({type:'run',cfg,prompt:'rejected file'}).ok);
   for(let i=0;i<100&&send({type:'status'}).running;i++)await new Promise(r=>setTimeout(r,5));
   const stopped=send({type:'status'});
   assert.equal(stopped.items.length,1);assert.equal(stopped.items[0].status,code);assert.equal(clicks,code==='blocked_credit'?1:2);assert.equal(downloaded,0);assert.equal(stopped.flowMessage,'Exact Flow notification');
 }
 failureCode=null;writeFailure=true;filled=false;clicks=0;downloaded=0;
 assert.ok(send({type:'run',cfg,prompt:'save failure'}).ok);
 for(let i=0;i<100&&send({type:'status'}).running;i++)await new Promise(r=>setTimeout(r,5));
 assert.equal(send({type:'status'}).items.length,1);assert.equal(clicks,1);assert.equal(send({type:'status'}).items[0].status,'save_failed');assert.equal(downloaded,2);
 writeFailure=false;filled=false;clicks=0;downloaded=0;
 assert.ok(send({type:'run',cfg,prompt:'new independent file',fileName:'new.txt'}).ok);
 for(let i=0;i<100&&send({type:'status'}).running;i++)await new Promise(r=>setTimeout(r,5));
 assert.equal(send({type:'status'}).items[0].status,'done');assert.equal(send({type:'status'}).flowMessage,null);assert.equal(clicks,1);
 console.log('PASS: multiline stays one prompt; legacy queues rejected; duplicate start rejected; new run succeeds after failed run without stale Flow error.');
 failureCode='blocked_generation';partial=true;filled=false;clicks=0;downloaded=0;cfg.count='4';
 assert.ok(send({type:'run',cfg,prompt:'four requested one produced'}).ok);
 for(let i=0;i<100&&send({type:'status'}).running;i++)await new Promise(r=>setTimeout(r,5));
 assert.equal(send({type:'status'}).items[0].status,'partial');assert.equal(downloaded,1);assert.equal(clicks,1);
 partial=false;filled=false;clicks=0;downloaded=0;
 assert.ok(send({type:'run',cfg,prompt:'retry once only'}).ok);
 for(let i=0;i<200&&send({type:'status'}).running;i++)await new Promise(r=>setTimeout(r,5));
 assert.equal(clicks,2);assert.equal(send({type:'status'}).attempts.length,2);
 console.log('PASS: one of four images is saved with no regeneration; generation failure gets exactly one retry.');
 policyFirstOnly=true;failureCode='blocked_policy';filled=false;clicks=0;downloaded=0;cfg.count='1';
 assert.ok(send({type:'run',cfg,prompt:'same prompt both attempts'}).ok);
 for(let i=0;i<200&&send({type:'status'}).running;i++)await new Promise(r=>setTimeout(r,5));
 const recovered=send({type:'status'});
 assert.equal(clicks,2);assert.equal(downloaded,1);assert.equal(recovered.items[0].status,'done');assert.equal(recovered.flowMessage,null);
 assert.equal(recovered.attempts[0].status,'blocked_policy');assert.equal(recovered.attempts[1].status,'done');assert.equal(input.value,'same prompt both attempts');
 console.log('PASS: policy then success retries unchanged prompt once; current status succeeds and first failure remains only in history.');
 failureCode=null;policyFirstOnly=false;badImageUrl=true;filled=false;clicks=0;downloaded=0;
 assert.ok(send({type:'run',cfg,prompt:'created image but invalid result URL'}).ok);
 for(let i=0;i<100&&send({type:'status'}).running;i++)await new Promise(r=>setTimeout(r,5));
 assert.equal(send({type:'status'}).items[0].status,'save_failed');assert.equal(clicks,1);assert.equal(send({type:'status'}).attempts.length,1);
 badImageUrl=false;filled=false;clicks=0;let downloadsAttempted=0;
 downloadModule={save:async()=>{downloadsAttempted++;throw Object.assign(new Error('Download press result unknown'),{code:'click_uncertain'});}};boot();
 assert.ok(send({type:'run',cfg,prompt:'uncertain Download click'}).ok);
 for(let i=0;i<100&&send({type:'status'}).running;i++)await new Promise(r=>setTimeout(r,5));
 assert.equal(downloadsAttempted,1);assert.equal(clicks,1);assert.equal(send({type:'status'}).items[0].status,'save_failed');
 console.log('PASS: unexpected post-generation error never F5/regenerates; uncertain Download click is attempted once with existing image retained.');
})().catch(e=>{console.error(e);process.exitCode=1;});
