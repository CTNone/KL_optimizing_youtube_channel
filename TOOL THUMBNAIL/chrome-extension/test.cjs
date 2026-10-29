const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
let handler, clicks = 0;
const element = {getClientRects: () => [1], click: () => clicks++};
const document = {querySelectorAll: css => {
  if (css === '#prompt' || css === '#generate') return [element];
  if (css === '#duplicate') return [element, element];
  return [];
}};
const context = vm.createContext({document, getComputedStyle: () => ({visibility:'visible'}), chrome:{
  runtime:{id:'test', onMessage:{addListener: fn => {handler = fn;}}},
  storage:{local:{set:async () => {}}}
}});
vm.runInContext(fs.readFileSync(__dirname + '/content.js','utf8'), context);
function send(message) { let result; handler(message, {id:'test'}, value => {result = value;}); return result; }
const cfg = {prompt:'#prompt',generate:'#generate',card:'.card',image:'img',original:'',count:'1',timeout:'240'};
assert.equal(send({type:'status'}).running, false);
assert.match(send({type:'check',cfg}).text, /Ảnh nhận diện: 0/);
assert.match(send({type:'check',cfg:{...cfg,prompt:'#duplicate'}}).error, /2/);
assert.ok(send({type:'check',cfg:{...cfg,count:'0'}}).error);
assert.ok(send({type:'run',cfg,prompts:[],start:0}).error);
assert.ok(send({type:'run',cfg,prompts:['hello'],start:2}).error);
assert.equal(clicks,0);
assert.equal(send({type:'status'}).running,false);
console.log('PASS: validation, ambiguous selectors, empty queue, invalid start; no prompt submitted.');
