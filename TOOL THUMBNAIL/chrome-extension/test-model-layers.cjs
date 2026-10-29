const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
let phase=0,model='Nano Banana 2',ticks=0;const clicked=[];
const base={getClientRects:()=>[1],getAttribute:()=>null,contains:()=>false,getBoundingClientRect:()=>({left:100,right:350,top:120,bottom:150})};
const editor={getBoundingClientRect:()=>({left:80,right:450,top:100,bottom:140})};
const summary={...base,get textContent(){return model;}};
const trigger={...base,get textContent(){return model;},getAttribute:k=>k==='role'?'combobox':null};
const rows=['Nano Banana Pro','Nano Banana 2','Nano Banana 2 Lite'].map(textContent=>({...base,textContent}));
const document={querySelectorAll:css=>css==='[role="combobox"]'?phase>=2?[trigger]:[]:css==='button,[role="button"]'?[summary]:css==='button,[role="button"],[role="combobox"]'?phase>=2?[summary,trigger]:[summary]:css.startsWith('[role="option"]')&&phase===3?rows:[]};
const ctx=vm.createContext({document,getComputedStyle:()=>({visibility:'visible'})});vm.runInContext(fs.readFileSync(__dirname+'/flow-models.js','utf8'),ctx);
(async()=>{
 const selected=await ctx.FlowModels.chooseBest({editor:()=>editor,order:['Nano Banana 2 Lite'],blocked:{},check(){},sleep:async()=>{if(phase===1 && ++ticks===3)phase=2;},dismiss:async()=>{phase=0;},click:async e=>{
   clicked.push(e);if(e===summary){assert.ok(ctx.FlowModels.isControl(e));phase=1;}else if(e===trigger){assert.ok(ctx.FlowModels.isControl(e));phase=3;}else{assert.equal(e,rows[2]);model=e.textContent;phase=2;}
 }});
 assert.equal(selected,'Nano Banana 2 Lite');assert.deepEqual(clicked,[summary,trigger,rows[2]]);assert.equal(ticks,3);
 console.log('PASS: delayed settings portal and separate dropdown trigger are opened exactly once in order, then Lite is verified after dismissal.');
})().catch(e=>{console.error(e);process.exitCode=1;});
