const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
let handler, clicks = 0;
const listeners = new Map();
const base = {querySelectorAll:()=>[],isConnected:true,getClientRects:()=>[1],getAttribute:()=>null,contains:()=>false};
const input = {...base,textContent:'',getBoundingClientRect:()=>({left:500,right:1200,top:800,bottom:850})};
const makeButton = () => ({...base,tagName:'BUTTON',matches:()=>true,textContent:'',disabled:true,getBoundingClientRect:()=>({left:1220,right:1260,top:870,bottom:910}),click:()=>clicks++});
let button = makeButton();
const document = {
 querySelectorAll:css=>css === 'textarea, [contenteditable="true"]' ? [input] : css === 'button, [role="button"]' ? [button] : [],
 createElement:()=>({style:{},remove(){}}),documentElement:{append(){}},
 addEventListener:(type,fn)=>listeners.set(type,fn),removeEventListener:type=>listeners.delete(type),
 // Simulate pointer-events:none on a disabled button: hit testing returns its parent.
 elementFromPoint:()=>({closest:()=>null})
};
vm.runInNewContext(fs.readFileSync(__dirname+'/content.js','utf8'),{document,window:document,Date,getComputedStyle:()=>({visibility:'visible'}),chrome:{runtime:{id:'test',onMessage:{addListener:fn=>handler=fn}},storage:{local:{set:async()=>{}}}}});
function send(message){let result;handler(message,{id:'test'},r=>result=r);return result;}
const cfg = {prompt:'',generate:'',card:'',image:'img',original:'',count:'1',timeout:'240'};
assert.ok(send({type:'pickGenerate'}).ok);
let blocked = 0;
listeners.get('pointerdown')({type:'pointerdown',clientX:1240,clientY:890,preventDefault:()=>blocked++,stopImmediatePropagation:()=>blocked++});
assert.equal(blocked,2);
assert.match(send({type:'status'}).logs.join('\n'),/Đã chọn nút gửi: BUTTON/);
assert.match(send({type:'check',cfg}).text,/Đã nhận diện/);
assert.equal(listeners.has('pointerdown'),false);
button.isConnected = false;
button = makeButton();
assert.match(send({type:'check',cfg}).text,/Đã nhận diện/);
assert.equal(clicks,0);
button.isConnected = false;
button = {...makeButton(),textContent:'different action'};
assert.match(send({type:'check',cfg}).error,/chọn lại/);
console.log('PASS: disabled hit-test fallback, selection never submits, replacement button found, changed action rejected.');
// A custom icon must be selectable even before the editor can be identified.
const icon = {...base,tagName:'svg',textContent:'',matches:()=>false,closest:()=>null,getBoundingClientRect:()=>({left:50,right:80,top:50,bottom:80})};
document.querySelectorAll = () => [];
document.elementFromPoint = () => icon;
assert.ok(send({type:'pickGenerate'}).ok);
listeners.get('pointerdown')({type:'pointerdown',clientX:60,clientY:60,preventDefault(){},stopImmediatePropagation(){}});
assert.match(send({type:'status'}).logs.at(-1),/Đã chọn nút gửi: svg/);
assert.equal(clicks,0);
console.log('PASS: custom SVG selection succeeds without editor recognition and never submits.');
