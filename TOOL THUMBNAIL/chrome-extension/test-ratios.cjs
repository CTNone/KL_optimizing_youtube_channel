const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
let active='4:3';
const ratios=['16:9','4:3','1:1','3:4','9:16'];
const rows=ratios.map(r=>({innerText:r,getClientRects:()=>[1],getAttribute:key=>key==='aria-checked'?String(active===r):null}));
const context=vm.createContext({document:{querySelectorAll:()=>rows},getComputedStyle:e=>({visibility:'visible',backgroundColor:e.innerText===active?'rgb(80, 80, 80)':'rgb(20, 20, 20)'})});
vm.runInContext(fs.readFileSync(__dirname+'/flow-settings.js','utf8'),context);
(async()=>{
 for(const ratio of ratios){
  const value=await context.FlowSettings.applyRatio({editor:()=>({}),cfg:{aspectRatio:ratio},click:async e=>{active=e.innerText},sleep:async()=>{},check(){}});
  assert.equal(value,ratio);assert.equal(active,ratio);
 }
 for(const row of rows)row.getAttribute=()=>null;
 assert.equal(context.FlowSettings.selectedRatio(context.FlowSettings.ratioRows()),active);
 await assert.rejects(context.FlowSettings.applyRatio({editor:()=>({}),cfg:{aspectRatio:'4:3'},click:async()=>{},sleep:async()=>{},check(){}}),/Chưa xác nhận/);
 console.log('PASS: apply all five ratios; verify selected state and unique background; refuse unconfirmed ratio.');
})().catch(error=>{console.error(error);process.exitCode=1});
