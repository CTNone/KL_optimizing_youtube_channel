const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
let handler, extra = false, clicks = 0;
const base = {querySelectorAll:()=>[],getClientRects:()=>[1], getAttribute:()=>null, contains:()=>false};
const input = {...base,textContent:'',getAttribute:k=>k === 'placeholder' ? 'Bạn muốn tạo những gì?' : null,getBoundingClientRect:()=>({left:500,right:1200,top:800,bottom:850})};
const arrow = {...base,textContent:'arrow_forward',getBoundingClientRect:()=>({left:1220,top:870}),click:()=>clicks++};
const img = {...base,currentSrc:'https://example.com/old.png',getBoundingClientRect:()=>({width:400,height:300})};
const document = {querySelectorAll:css=>{
 if(css === 'textarea, [contenteditable="true"]') return [input];
 if(css === 'button, [role="button"]') return extra ? [arrow,{...arrow}] : [arrow];
 if(css === 'img') return [img];
 return [];
}};
vm.runInNewContext(fs.readFileSync(__dirname+'/content.js','utf8'),{document,getComputedStyle:()=>({visibility:'visible'}),chrome:{runtime:{id:'test',onMessage:{addListener:fn=>handler=fn}},storage:{local:{set:async()=>{}}}}});
function send(message) {let result;handler(message,{id:'test'},r=>result=r);return result;}
const cfg = {prompt:'',generate:'',card:'',image:'img',original:'',count:'1',timeout:'240'};
assert.match(send({type:'check',cfg}).text,/Ảnh nhận diện: 1/);
extra = true;
assert.match(send({type:'check',cfg}).error,/Chọn nút tạo trên Flow/);
assert.equal(clicks,0);
console.log('PASS: blank selectors auto-detect composer, arrow and large image; ambiguity stops without clicking.');
