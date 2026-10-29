const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
let handler,model='Nano Banana 2 Lite',count=1,menu=null,submitted=0,saved=0,filled=false,expectedModel='Nano Banana Pro',nativeCalls=0;
const rect={left:50,right:400,top:100,bottom:130};
const base={isConnected:true,getClientRects:()=>[1],getAttribute:()=>null,contains:()=>false,querySelectorAll:()=>[],getBoundingClientRect:()=>({left:100,right:150,top:140,bottom:170})};
class Textarea{set value(v){this._value=v;filled=!!v;}get value(){return this._value;}}
const input=Object.assign(new Textarea(),base,{focus(){menu=null;},dispatchEvent(){},click(){menu=null;},getBoundingClientRect:()=>rect});
let referenceUploaded=false,pickerMode=false,pickerPhase=0;const referenceSteps=[];
const composer={querySelectorAll:()=>referenceUploaded?[{...base,src:'blob:reference',complete:true,naturalWidth:640}]:[]};
const plus={...base,textContent:'add',click(){pickerPhase=1;referenceSteps.push('open');}};
const upload={...base,textContent:'Tải nội dung lên',setAttribute(){},removeAttribute(){}};
const addPrompt={...base,textContent:'Thêm vào câu lệnh',click(){pickerPhase=3;referenceSteps.push('confirm');}};
composer.contains=e=>e===plus;
input.parentElement=composer;
const uploadInput={getAttribute:()=> 'image/*',dispatchEvent(){referenceUploaded=true;}};
const modelButton={...base,get textContent(){return model;},click(){menu='models';}};
const countButton={...base,get textContent(){return 'x'+count;},click(){menu='count';}};
const modelOptions=['Nano Banana Pro','Nano Banana 2','Nano Banana 2 Lite'].map(textContent=>({...base,textContent,click(){model=textContent;menu=null;}}));
const countOptions=[1,2,3,4].map(n=>({...base,textContent:String(n),click(){count=n;menu=null;}}));
const send={...base,textContent:'send',tagName:'BUTTON',getBoundingClientRect:()=>({left:380,right:410,top:140,bottom:170}),click(){assert.equal(model,expectedModel);assert.equal(count,4);assert.ok(filled);assert.equal(menu,null);submitted++;}};
const images=[1,2,3,4].map(n=>({...base,complete:true,naturalWidth:1024,naturalHeight:1024,currentSrc:'https://example.test/'+n+'.png',getBoundingClientRect:()=>({width:400,height:300})}));
const document={querySelectorAll:css=>{
 if(css==='input[type="file"]')return pickerMode?[]:[uploadInput];
 if(css==='button,[role="button"],[role="menuitem"]')return pickerMode?pickerPhase===0?[plus]:pickerPhase===1?[upload]:pickerPhase===2?[addPrompt]:[]:[];
 if(css==='textarea, [contenteditable="true"]')return [input];
 if(css==='button,[role="button"]')return [modelButton,countButton];
 if(css==='button, [role="button"]')return filled?[modelButton,countButton,send]:[modelButton,countButton];
 if(css==='button,[role="button"],[role="combobox"]')return [modelButton,countButton];
 if(css.startsWith('[role="option"]'))return menu==='models'?modelOptions:menu==='count'?countOptions:[];
 if(css==='img')return submitted?images:[];
 return [];
}};
const context=vm.createContext({document,Date,URL,fetch,File:class extends Blob{constructor(parts,name,options){super(parts,options);this.name=name;}},DataTransfer:class{constructor(){this.files=[];this.items={add:file=>this.files.push(file)};}},crypto:require('node:crypto').webcrypto,Event:class{},HTMLTextAreaElement:Textarea,HTMLInputElement:class{},
 location:{href:'https://flow.google.com/project/test'},getComputedStyle:()=>({visibility:'visible'}),setTimeout:fn=>setTimeout(fn,0),
 FlowDownloads:{save:async()=>({image:{data:'data:image/png;base64,AAAA',width:2048,height:2048},source:'flow_2k'})},
 chrome:{runtime:{id:'test',onMessage:{addListener:fn=>handler=fn},sendMessage:async m=>{
  if(m.type==='readRecords')return {limits:{}};
  if(m.type==='nativeEscape'){menu=null;return {ok:true};}
  if(m.type==='nativeUpload'){assert.equal(pickerPhase,1);pickerPhase=2;referenceUploaded=true;referenceSteps.push('upload');return {ok:true};}
  if(m.type==='nativeClick'){nativeCalls++;if(nativeCalls===1)send.click();else throw new Error('Unexpected native model row click');return {ok:true};}
  if(m.type==='writeImage'){saved++;return {ok:true,filename:'C:\\Output\\'+m.path};}
  if(m.type==='recoverRun')throw new Error('First attempt must succeed without F5');
  return {ok:true};
 }},storage:{local:{set:async()=>{}}}}
});
for(const file of ['flow-models.js','flow-settings.js','content.js'])vm.runInContext(fs.readFileSync(__dirname+'/'+file,'utf8'),context);
function message(m){let result;handler(m,{id:'test'},r=>result=r);return result;}
(async()=>{
 const cfg={count:'4',timeout:'10',clickMode:'dom',saveMode:'folder',image:'img'};
 assert.equal(message({type:'run',cfg,prompt:'one prompt'}).ok,true);
 for(let i=0;i<100 && message({type:'status'}).running;i++)await new Promise(r=>setTimeout(r,5));
 const state=message({type:'status'});
 assert.equal(state.running,false);assert.equal(state.items[0].status,'done',JSON.stringify(state));
 assert.equal(state.attempts.length,1);assert.equal(state.attempts[0].model,'Nano Banana Pro');
 assert.equal(submitted,1);assert.equal(saved,4);assert.equal(state.flowCount,4);
 model='Nano Banana 2';expectedModel='Nano Banana 2 Lite';count=1;submitted=0;saved=0;filled=false;
 const cp={id:'fresh-one',initialReload:true,nextAttempt:1,args:{cfg:{...cfg,modelChoice:'Nano Banana Lite'},prompt:'explicit Lite after F5'},attempts:[]};
 assert.equal(message({type:'resumeRun',checkpoint:cp}).ok,true);
 for(let i=0;i<100 && message({type:'status'}).running;i++)await new Promise(r=>setTimeout(r,5));
 const fresh=message({type:'status'});assert.equal(fresh.items[0].status,'done',JSON.stringify(fresh));assert.equal(fresh.attempts[0].attempt,1);assert.equal(fresh.attempts[0].model,'Nano Banana 2 Lite');assert.equal(submitted,1);
 console.log('PASS: initial F5 resumes attempt 1, explicitly switches Flow from Nano Banana 2 to Lite, and never sends using the old model.');
 console.log('PASS: integrated model selection + Flow count setting + send + 4 verified 2K saves succeed on first attempt without F5.');
 model='Nano Banana 2';count=4;submitted=0;saved=0;filled=false;nativeCalls=0;
 assert.equal(message({type:'run',cfg:{...cfg,clickMode:'native',modelChoice:'Nano Banana 2 Lite'},prompt:'choose Lite through DOM row'}).ok,true);
 for(let i=0;i<100 && message({type:'status'}).running;i++)await new Promise(r=>setTimeout(r,5));
 const native=message({type:'status'});assert.equal(native.items[0].status,'done',JSON.stringify(native));assert.equal(native.model,'Nano Banana 2 Lite');assert.equal(nativeCalls,1);assert.equal(submitted,1);
 assert.ok(native.logs.some(line=>line.includes('Chọn dòng mô hình bằng nút DOM')));
 console.log('PASS: native mode opens settings and sends via Chrome, but selects the uniquely matched Lite row through DOM without hit-testing that row.');
 submitted=0;saved=0;filled=false;
 assert.equal(message({type:'run',cfg:{...cfg,modelChoice:'Nano Banana 2 Lite'},reference:{data:'data:image/jpeg;base64,aGVsbG8=',name:'market.jpg'},prompt:'new scene with market reference'}).ok,true);
 for(let i=0;i<100 && message({type:'status'}).running;i++)await new Promise(r=>setTimeout(r,5));
 const referenced=message({type:'status'});assert.equal(referenced.items[0].status,'done',JSON.stringify(referenced));assert.equal(referenceUploaded,true);assert.equal(submitted,1);
 assert.ok(referenced.logs.some(line=>line.includes('ảnh mẫu NCTT được đính kèm')));
 console.log('PASS: reference upload dispatches the file input change and confirms the preview before submitting the prompt.');
 submitted=0;saved=0;filled=false;referenceUploaded=false;pickerMode=true;pickerPhase=0;
 assert.equal(message({type:'run',cfg:{...cfg,modelChoice:'Nano Banana 2 Lite'},reference:{data:'data:image/jpeg;base64,aGVsbG8=',name:'market.jpg',path:'C:\\reference-cache\\reference_'+ 'a'.repeat(64)+'.jpg'},prompt:'asset picker upload'}).ok,true);
 for(let i=0;i<100 && message({type:'status'}).running;i++)await new Promise(r=>setTimeout(r,5));
 const picker=message({type:'status'});assert.equal(picker.items[0].status,'done',JSON.stringify(picker));assert.equal(submitted,1);assert.deepEqual(referenceSteps,['open','upload','confirm']);
 console.log('PASS: screenshot-shaped asset picker opens +, uploads local file, confirms Add to prompt, then sends exactly once.');
})().catch(error=>{console.error(error);process.exitCode=1;});


