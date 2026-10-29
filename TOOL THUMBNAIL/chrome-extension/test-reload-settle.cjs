const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const data={},timers=[];let injections=0,resumes=0,url='https://flow.google.com/project/one';
const chrome={runtime:{onMessage:{addListener(){}}},tabs:{query:async()=>[{id:1,url}],onUpdated:{addListener(){}},sendMessage:async()=>{resumes++;return {ok:true};}},scripting:{executeScript:async()=>{injections++;}},storage:{session:{get:async()=>structuredClone(data),set:async value=>Object.assign(data,structuredClone(value))}}};
const ctx=vm.createContext({chrome,URL,setTimeout:(fn,ms)=>{assert.equal(ms,2000);timers.push(fn);}});
vm.runInContext(fs.readFileSync(__dirname+'/background.js','utf8'),ctx);
async function begin(id){
 await ctx.prepareRecovery({tab:{id:1},frameId:0},{id,nextAttempt:1,initialReload:true,args:{}});
 const pending=ctx.resumeAfterReload(1);
 for(let i=0;i<10&&!timers.length;i++)await new Promise(setImmediate);
 assert.equal(timers.length,1);assert.equal(data.recovery_1.phase,'settling');
 return {pending};
}
(async()=>{
 let run=await begin('normal');assert.equal(injections,0);assert.equal(resumes,0);
 await ctx.resumeAfterReload(1);assert.equal(timers.length,1);
 timers.shift()();await run.pending;assert.equal(injections,1);assert.equal(resumes,1);assert.equal(data.recovery_1.phase,'resumed');
 run=await begin('cancel');data.recovery_1.phase='cancelled';timers.shift()();await run.pending;
 assert.equal(injections,1);assert.equal(resumes,1);assert.equal(data.recovery_1.phase,'cancelled');
 run=await begin('changed');url='https://flow.google.com/project/two';timers.shift()();await run.pending;
 assert.equal(injections,1);assert.equal(resumes,1);assert.equal(data.recovery_1.phase,'failed');
 console.log('PASS: no injection or page interaction before the 2000ms timer; duplicate completion ignored; cancellation and changed project prevent dispatch.');
})().catch(error=>{console.error(error);process.exitCode=1;});
