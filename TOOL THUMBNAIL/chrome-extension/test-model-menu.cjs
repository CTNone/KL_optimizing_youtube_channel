const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
let selected='Nano Banana 2',open=true,closed=0,clicks=[],plain=false;
const base={getClientRects:()=>[1],getAttribute:()=>null,contains:()=>false,getBoundingClientRect:()=>({left:630,right:960,top:500,bottom:545})};
const editor={getBoundingClientRect:()=>({left:310,right:1020,top:710,bottom:750})};
const summary={...base,textContent:'Nano Banana 2 x2',getBoundingClientRect:()=>({left:780,right:980,top:762,bottom:802})};
const combo={...base,get textContent(){return selected;},getAttribute:k=>k==='role'?'combobox':null,getBoundingClientRect:()=>({left:620,right:970,top:600,bottom:645})};
const options=['Nano Banana Pro','Nano Banana 2','Nano Banana 2 Lite'].map(textContent=>({...base,textContent,getAttribute:k=>k==='role'?'menuitemradio':k==='aria-checked'?String(textContent===selected):null}));
const group={children:options};options.forEach(e=>e.parentElement=group);
const document={querySelectorAll:css=>css==='[role="combobox"]'?[combo]:css==='button,[role="button"]'?[summary]:css==='div,span,button,[role="button"]'&&plain&&open?options:css.startsWith('[role="option"]')&&open&&!plain?options:[]};
const context=vm.createContext({document,getComputedStyle:()=>({visibility:'visible'})});vm.runInContext(fs.readFileSync(__dirname+'/flow-models.js','utf8'),context);
(async()=>{
 assert.equal(context.FlowModels.detect(editor).element,combo);
 const next=await context.FlowModels.chooseBest({editor:()=>editor,order:['Nano Banana 2 Lite'],blocked:{},sleep:async()=>{},check(){},
 click:async e=>{assert.ok(options.includes(e),'Covered trigger/editor must not be clicked when options are already open');clicks.push(e.textContent);selected=e.textContent;open=false;},
 dismiss:async()=>{closed++;open=false;}});
 assert.equal(next,'Nano Banana 2 Lite');assert.deepEqual(clicks,['Nano Banana 2 Lite']);assert.equal(closed,1);
 console.log('PASS: screenshot-shaped portal menu uses active combobox and clicks Lite row directly, without clicking covered composer/trigger/editor.');
 plain=true;open=true;selected='Nano Banana 2';clicks=[];
 combo.contains=e=>options.includes(e);
 options.forEach(e=>{e.textContent='banana '+e.textContent+' check';e.getAttribute=()=>null;e.isConnected=true;e.closest=()=>combo;});
 vm.runInContext(fs.readFileSync(__dirname+'/flow-clicks.js','utf8'),context);
 await context.FlowModels.chooseBest({editor:()=>editor,order:['Nano Banana 2 Lite'],blocked:{},sleep:async()=>{},check(){},dismiss:async()=>{open=false;},click:async e=>{
   assert.equal(e,options[2]);assert.equal(context.FlowClicks.owner(e),e);
   const point=context.FlowClicks.point(e,{document:{elementFromPoint:()=>e},visible:()=>true,width:1920,height:1080});assert.ok(point.x>0);
   selected='Nano Banana 2 Lite';clicks.push(selected);open=false;
 }});
 assert.deepEqual(clicks,['Nano Banana 2 Lite']);
 console.log('PASS: unlabelled DIV/SPAN sibling model rows are selected directly and remain their own click owner even beneath a combobox ancestor.');
})().catch(e=>{console.error(e);process.exitCode=1;});

